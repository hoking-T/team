package edu.team.warehouse.events;
import edu.team.warehouse.common.SqlStore;
import edu.team.warehouse.logistics.LogisticsService;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.*;
@Component
public class EventHandlers {
 private final SqlStore s; private final LogisticsService logistics;
 public EventHandlers(SqlStore s,LogisticsService logistics){this.s=s;this.logistics=logistics;}
 @EventListener @Transactional(propagation=Propagation.MANDATORY)
 public void handle(DomainEvent event){
  if(s.db.queryForObject("SELECT COUNT(*) FROM event_log WHERE event_id=?",Long.class,event.id())>0)return;
  s.db.update("INSERT INTO event_log(event_id,event_type,aggregate_id,details) VALUES(?,?,?,?)",event.id(),event.type(),event.aggregateId(),event.details());
  if(event.type().equals("ORDER_SHIPPED"))logistics.createForOrder(event.aggregateId());
  // 不吞异常，不启动异步线程：失败传播给调用者，让事务整体回滚后再重试。
 }
}
