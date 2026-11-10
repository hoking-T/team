package edu.team.warehouse.orders;
import edu.team.warehouse.api.Requests.Movement;
import edu.team.warehouse.common.*;
import edu.team.warehouse.events.DomainEvent;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service
public class OrderService {
 private final SqlStore s; private final ApplicationEventPublisher events;
 public OrderService(SqlStore s,ApplicationEventPublisher events){this.s=s;this.events=events;}
 @Transactional public long create(Movement m){
  s.require("product",m.productId());s.require("location",m.locationId());
  long id=s.insert("INSERT INTO outbound_order(product_id,location_id,quantity) VALUES(?,?,?)",m.productId(),m.locationId(),m.quantity());
  events.publishEvent(DomainEvent.of("ORDER_CREATED",id,"PENDING"));return id;
 }
 @Transactional public void ship(long id){
  var rows=s.db.queryForList("SELECT * FROM outbound_order WHERE id=? FOR UPDATE",id);
  if(rows.isEmpty())throw new BusinessException(404,"订单不存在");
  var order=rows.get(0);
  if(!"PENDING".equals(order.get("STATUS")))throw new BusinessException(409,"订单已经出库，不能重复扣减");
  long quantity=((Number)order.get("QUANTITY")).longValue();
  // 数据库条件更新持有行锁；不同订单抢同一库存时也不能超扣。
  int changed=s.db.update("UPDATE stock SET quantity=quantity-? WHERE product_id=? AND location_id=? AND quantity>=?",quantity,order.get("PRODUCT_ID"),order.get("LOCATION_ID"),quantity);
  if(changed!=1)throw new BusinessException(409,"库存不足，订单保持待出库");
  s.db.update("UPDATE outbound_order SET status='SHIPPED' WHERE id=?",id);
  events.publishEvent(DomainEvent.of("STOCK_SHIPPED",id,"product="+order.get("PRODUCT_ID")+",location="+order.get("LOCATION_ID")+",delta=-"+quantity));
  // 同步事件监听器在本事务内执行，监听失败时库存、订单、物流全部回滚。
  events.publishEvent(DomainEvent.of("ORDER_SHIPPED",id,"SHIPPED"));
 }
}
