package edu.team.warehouse.catalog;
import edu.team.warehouse.api.Requests.Product;
import edu.team.warehouse.common.SqlStore;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service
public class CatalogService {
 private final SqlStore s;
 public CatalogService(SqlStore s){this.s=s;}
 @Transactional public long create(Product p){
  long id=s.insert("INSERT INTO product(code,name,unit) VALUES(?,?,?)",p.code().trim().toUpperCase(java.util.Locale.ROOT),p.name().trim(),p.unit().trim());
  // 预建商品与货位组合，确保首次并发入库也可直接使用原子 UPDATE。
  s.db.update("INSERT INTO stock(product_id,location_id,quantity) SELECT ?,id,0 FROM location",id);
  return id;
 }
}
