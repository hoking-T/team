package edu.team.warehouse.inventory;
import edu.team.warehouse.api.Requests.Movement;
import edu.team.warehouse.common.*;
import edu.team.warehouse.events.DomainEvent;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service
public class InventoryService {
 private final SqlStore s; private final ApplicationEventPublisher events;
 public InventoryService(SqlStore s,ApplicationEventPublisher events){this.s=s;this.events=events;}
 @Transactional public long receive(Movement m){
  s.require("product",m.productId());s.require("location",m.locationId());
  if(s.db.update("UPDATE stock SET quantity=quantity+? WHERE product_id=? AND location_id=? AND quantity<=1000000000-?",m.quantity(),m.productId(),m.locationId(),m.quantity())!=1)
   throw new BusinessException(409,"库存超过上限");
  long id=s.insert("INSERT INTO inbound(product_id,location_id,quantity) VALUES(?,?,?)",m.productId(),m.locationId(),m.quantity());
  events.publishEvent(DomainEvent.of("STOCK_RECEIVED",id,"product="+m.productId()+",location="+m.locationId()+",delta="+m.quantity()));
  return id;
 }
}
