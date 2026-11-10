package edu.team.warehouse;
import edu.team.warehouse.api.Requests.*;
import edu.team.warehouse.catalog.CatalogService;
import edu.team.warehouse.inventory.InventoryService;
import edu.team.warehouse.orders.OrderService;
import edu.team.warehouse.logistics.LogisticsService;
import edu.team.warehouse.events.*;
import edu.team.warehouse.common.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
@SpringBootTest(properties={"spring.datasource.url=jdbc:h2:mem:test;DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=10000"})
@AutoConfigureMockMvc
class WarehouseTests {
 @Autowired CatalogService catalog; @Autowired InventoryService inventory; @Autowired OrderService orders;
 @Autowired LogisticsService logistics; @Autowired SqlStore s; @Autowired MockMvc http;
 @Autowired ApplicationEventPublisher events; @Autowired PlatformTransactionManager tx;
 long product;
 @BeforeEach void setup(){product=catalog.create(new Product("T"+UUID.randomUUID().toString().replace("-",""),"键盘","个"));}
 Movement move(long n){return new Movement(product,1L,n);}
 long quantity(){return s.db.queryForObject("SELECT quantity FROM stock WHERE product_id=? AND location_id=1",Long.class,product);}
 long shipment(long order){return s.db.queryForObject("SELECT id FROM shipment WHERE order_id=?",Long.class,order);}
 @Test void completeFlow(){inventory.receive(move(100));assertThat(quantity()).isEqualTo(100);long o=orders.create(move(20));assertThat(quantity()).isEqualTo(100);orders.ship(o);assertThat(quantity()).isEqualTo(80);long sh=shipment(o);logistics.advance(sh,"TRANSIT");logistics.advance(sh,"DELIVERED");assertThat(s.db.queryForList("SELECT status FROM tracking WHERE shipment_id=? ORDER BY id",sh)).extracting(r->r.get("STATUS")).containsExactly("WAITING","TRANSIT","DELIVERED");}
 @Test void accumulationAndLocations(){inventory.receive(move(40));inventory.receive(move(60));inventory.receive(new Movement(product,2L,7L));assertThat(quantity()).isEqualTo(100);assertThat(s.db.queryForObject("SELECT quantity FROM stock WHERE product_id=? AND location_id=2",Long.class,product)).isEqualTo(7);}
 @Test void insufficientStockRollsBack(){inventory.receive(move(10));long o=orders.create(move(11));assertThatThrownBy(()->orders.ship(o)).isInstanceOf(BusinessException.class).hasMessageContaining("库存不足");assertThat(quantity()).isEqualTo(10);assertThat(s.db.queryForObject("SELECT status FROM outbound_order WHERE id=?",String.class,o)).isEqualTo("PENDING");assertThat(s.db.queryForObject("SELECT COUNT(*) FROM shipment WHERE order_id=?",Long.class,o)).isZero();}
 @Test void exactStockAndDuplicate(){inventory.receive(move(20));long o=orders.create(move(20));orders.ship(o);assertThat(quantity()).isZero();assertThatThrownBy(()->orders.ship(o)).hasMessageContaining("不能重复");assertThat(quantity()).isZero();}
 @Test void missingOrder(){assertThatThrownBy(()->orders.ship(-1)).hasMessageContaining("不存在");}
 @Test void invalidLogisticsTransitions(){inventory.receive(move(20));long o=orders.create(move(20));orders.ship(o);long sh=shipment(o);assertThatThrownBy(()->logistics.advance(sh,"DELIVERED")).hasMessageContaining("跳级");logistics.advance(sh,"TRANSIT");assertThatThrownBy(()->logistics.advance(sh,"TRANSIT")).hasMessageContaining("跳级");logistics.advance(sh,"DELIVERED");assertThatThrownBy(()->logistics.advance(sh,"TRANSIT")).hasMessageContaining("跳级");assertThatThrownBy(()->logistics.advance(-1,"TRANSIT")).hasMessageContaining("不存在");}
 @Test void duplicateEventsDoNotDuplicateShipment(){inventory.receive(move(20));long o=orders.create(move(20));orders.ship(o);var e=DomainEvent.of("ORDER_SHIPPED",o,"replay");new TransactionTemplate(tx).executeWithoutResult(status->{events.publishEvent(e);events.publishEvent(e);events.publishEvent(DomainEvent.of("ORDER_SHIPPED",o,"new id replay"));});assertThat(s.db.queryForObject("SELECT COUNT(*) FROM shipment WHERE order_id=?",Long.class,o)).isEqualTo(1);assertThat(s.db.queryForObject("SELECT COUNT(*) FROM tracking WHERE shipment_id=?",Long.class,shipment(o))).isEqualTo(1);}
 @Test void eventFailureRollsBackEntireShipment(){inventory.receive(move(100));long o=orders.create(move(20));s.db.execute("ALTER TABLE shipment ADD CONSTRAINT test_fail CHECK(order_id<>"+o+")");try{assertThatThrownBy(()->orders.ship(o)).isInstanceOf(RuntimeException.class);assertThat(quantity()).isEqualTo(100);assertThat(s.db.queryForObject("SELECT status FROM outbound_order WHERE id=?",String.class,o)).isEqualTo("PENDING");assertThat(s.db.queryForObject("SELECT COUNT(*) FROM event_log WHERE aggregate_id=? AND event_type IN ('ORDER_SHIPPED','STOCK_SHIPPED')",Long.class,o)).isZero();}finally{s.db.execute("ALTER TABLE shipment DROP CONSTRAINT test_fail");}orders.ship(o);assertThat(quantity()).isEqualTo(80);}
 @Test void concurrentOrdersCannotOversell() throws Exception {inventory.receive(move(100));long a=orders.create(move(70)),b=orders.create(move(70));assertThat(race(()->orders.ship(a),()->orders.ship(b))).isEqualTo(1);assertThat(quantity()).isEqualTo(30);}
 @Test void concurrentSameOrderCannotDeductTwice() throws Exception {inventory.receive(move(100));long o=orders.create(move(20));assertThat(race(()->orders.ship(o),()->orders.ship(o))).isEqualTo(1);assertThat(quantity()).isEqualTo(80);}
 @Test void concurrentReceiptsAccumulate() throws Exception {assertThat(race(()->inventory.receive(move(40)),()->inventory.receive(move(60)))).isEqualTo(2);assertThat(quantity()).isEqualTo(100);}
 int race(Runnable a,Runnable b) throws Exception {var pool=Executors.newFixedThreadPool(2);var gate=new CountDownLatch(1);try{List<Future<Boolean>> futures=new ArrayList<>();for(var task:List.of(a,b))futures.add(pool.submit(()->{gate.await();try{task.run();return true;}catch(BusinessException e){return false;}}));gate.countDown();int ok=0;for(var future:futures)if(future.get(15,TimeUnit.SECONDS))ok++;return ok;}finally{pool.shutdownNow();}}
 @Test void illegalQuantitiesRejectedAtApi() throws Exception {for(String q:List.of("0","-1","1.5","1000001","null","\"abc\"")){http.perform(post("/api/inbounds").contentType("application/json").content("{\"productId\":"+product+",\"locationId\":1,\"quantity\":"+q+"}")).andExpect(status().isBadRequest());}assertThat(quantity()).isZero();}
 @Test void productValidationAndDuplicate() throws Exception {http.perform(post("/api/products").contentType("application/json").content("{\"code\":\"INVALID\",\"name\":\" \",\"unit\":\"个\"}")).andExpect(status().isBadRequest());String code="D"+product;catalog.create(new Product(code,"商品","个"));http.perform(post("/api/products").contentType("application/json").content("{\"code\":\""+code.toLowerCase()+"\",\"name\":\"商品\",\"unit\":\"个\"}")).andExpect(status().isConflict());}
 @Test void invalidReferencesAndStockCap() throws Exception {http.perform(post("/api/orders").contentType("application/json").content("{\"productId\":9999999,\"locationId\":1,\"quantity\":1}")).andExpect(status().isNotFound());s.db.update("UPDATE stock SET quantity=1000000000 WHERE product_id=? AND location_id=1",product);assertThatThrownBy(()->inventory.receive(move(1))).hasMessageContaining("上限");assertThat(quantity()).isEqualTo(1000000000);}
 @Test void queryFilterAndPage() throws Exception {http.perform(get("/api/stocks").param("productId",String.valueOf(product))).andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(3));http.perform(get("/")).andExpect(status().isOk());}
}
