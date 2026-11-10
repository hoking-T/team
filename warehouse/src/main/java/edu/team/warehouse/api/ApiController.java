package edu.team.warehouse.api;
import java.util.*;
import jakarta.validation.Valid;
import edu.team.warehouse.common.SqlStore;
import edu.team.warehouse.catalog.CatalogService;
import edu.team.warehouse.inventory.InventoryService;
import edu.team.warehouse.orders.OrderService;
import edu.team.warehouse.logistics.LogisticsService;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api")
public class ApiController {
 private final SqlStore s;private final CatalogService catalog;private final InventoryService inventory;private final OrderService orders;private final LogisticsService logistics;
 public ApiController(SqlStore s,CatalogService catalog,InventoryService inventory,OrderService orders,LogisticsService logistics){this.s=s;this.catalog=catalog;this.inventory=inventory;this.orders=orders;this.logistics=logistics;}
 @GetMapping("/products") public Object products(){return s.db.queryForList("SELECT * FROM product ORDER BY id DESC");}
 @PostMapping("/products") public Object product(@Valid @RequestBody Requests.Product p){return Map.of("id",catalog.create(p));}
 @GetMapping("/locations") public Object locations(){return s.db.queryForList("SELECT * FROM location ORDER BY id");}
 @GetMapping("/stocks") public Object stocks(@RequestParam(required=false) Long productId){
  String sql="SELECT p.id AS product_id,p.code,p.name,p.unit,l.code AS location,s.quantity FROM stock s JOIN product p ON p.id=s.product_id JOIN location l ON l.id=s.location_id";
  return productId==null?s.db.queryForList(sql+" ORDER BY p.id,l.id"):s.db.queryForList(sql+" WHERE p.id=? ORDER BY l.id",productId);
 }
 @PostMapping("/inbounds") public Object receive(@Valid @RequestBody Requests.Movement m){return Map.of("id",inventory.receive(m));}
 @GetMapping("/inbounds") public Object inbounds(){return s.db.queryForList("SELECT i.*,p.name,l.code AS location FROM inbound i JOIN product p ON p.id=i.product_id JOIN location l ON l.id=i.location_id ORDER BY i.id DESC");}
 @PostMapping("/orders") public Object create(@Valid @RequestBody Requests.Movement m){return Map.of("id",orders.create(m));}
 @GetMapping("/orders") public Object orders(){return s.db.queryForList("SELECT o.*,p.name,l.code AS location FROM outbound_order o JOIN product p ON p.id=o.product_id JOIN location l ON l.id=o.location_id ORDER BY o.id DESC");}
 @PostMapping("/orders/{id}/ship") public Object ship(@PathVariable long id){orders.ship(id);return Map.of("message","出库成功，物流单已生成");}
 @GetMapping("/shipments") public Object shipments(){return s.db.queryForList("SELECT s.*,p.name,o.quantity FROM shipment s JOIN outbound_order o ON o.id=s.order_id JOIN product p ON p.id=o.product_id ORDER BY s.id DESC");}
 @GetMapping("/shipments/{id}/tracking") public Object tracking(@PathVariable long id){s.require("shipment",id);return s.db.queryForList("SELECT * FROM tracking WHERE shipment_id=? ORDER BY created_at,id",id);}
 @PostMapping("/shipments/{id}/advance") public Object advance(@PathVariable long id,@Valid @RequestBody Requests.Advance a){logistics.advance(id,a.status());return Map.of("message","物流状态已更新");}
 @GetMapping("/events") public Object events(){return s.db.queryForList("SELECT * FROM event_log ORDER BY created_at,event_id");}
}
