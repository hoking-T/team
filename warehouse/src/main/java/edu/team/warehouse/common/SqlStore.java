package edu.team.warehouse.common;
import java.sql.Statement;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.stereotype.Component;
@Component
public class SqlStore {
 public final JdbcTemplate db;
 public SqlStore(JdbcTemplate db){this.db=db;}
 public long insert(String sql,Object... args){
  var key=new GeneratedKeyHolder();
  db.update(c->{var ps=c.prepareStatement(sql,Statement.RETURN_GENERATED_KEYS);for(int i=0;i<args.length;i++)ps.setObject(i+1,args[i]);return ps;},key);
  return key.getKeyList().get(0).values().stream().filter(Number.class::isInstance).map(Number.class::cast).findFirst().orElseThrow().longValue();
 }
 public void require(String table,long id){
  // table 只能由服务代码传入常量，不能接收用户输入。
  if(db.queryForObject("SELECT COUNT(*) FROM "+table+" WHERE id=?",Long.class,id)==0)throw new BusinessException(404,"记录不存在："+table);
 }
}
