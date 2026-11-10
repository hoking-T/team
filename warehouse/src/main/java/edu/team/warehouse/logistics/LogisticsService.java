package edu.team.warehouse.logistics;
import edu.team.warehouse.common.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service
public class LogisticsService {
 private final SqlStore s;
 public LogisticsService(SqlStore s){this.s=s;}
 @Transactional public void createForOrder(long orderId){
  var rows=s.db.queryForList("SELECT status FROM outbound_order WHERE id=? FOR UPDATE",orderId);
  if(rows.isEmpty()||!"SHIPPED".equals(rows.get(0).get("STATUS")))throw new BusinessException(409,"只有已出库订单可以生成物流单");
  // 锁同一订单并以唯一键兜底，即使新事件 ID 重放也只生成一个物流单。
  if(s.db.queryForObject("SELECT COUNT(*) FROM shipment WHERE order_id=?",Long.class,orderId)>0)return;
  long id=s.insert("INSERT INTO shipment(order_id,status) VALUES(?,'WAITING')",orderId);
  s.db.update("INSERT INTO tracking(shipment_id,status) VALUES(?,'WAITING')",id);
 }
 @Transactional public void advance(long id,String target){
  var rows=s.db.queryForList("SELECT status FROM shipment WHERE id=? FOR UPDATE",id);
  if(rows.isEmpty())throw new BusinessException(404,"物流单不存在");
  String current=(String)rows.get(0).get("STATUS");
  boolean valid=(current.equals("WAITING")&&target.equals("TRANSIT"))||(current.equals("TRANSIT")&&target.equals("DELIVERED"));
  if(!valid)throw new BusinessException(409,"状态只能按待揽收→运输中→已签收推进，不能重复或跳级");
  s.db.update("UPDATE shipment SET status=? WHERE id=?",target,id);
  s.db.update("INSERT INTO tracking(shipment_id,status) VALUES(?,?)",id,target);
 }
}
