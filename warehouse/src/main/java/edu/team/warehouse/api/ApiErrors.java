package edu.team.warehouse.api;
import java.util.Map;
import edu.team.warehouse.common.BusinessException;
import org.springframework.http.ResponseEntity;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
@RestControllerAdvice
public class ApiErrors {
 @ExceptionHandler(BusinessException.class) public ResponseEntity<?> business(BusinessException e){return ResponseEntity.status(e.status).body(Map.of("message",e.getMessage()));}
 @ExceptionHandler({MethodArgumentNotValidException.class,HttpMessageNotReadableException.class,MethodArgumentTypeMismatchException.class}) public ResponseEntity<?> invalid(Exception e){return ResponseEntity.badRequest().body(Map.of("message","输入不合法：必填项不能为空，数量须为1至1000000的整数，商品编号仅限字母、数字、下划线和短横线"));}
 @ExceptionHandler(DataIntegrityViolationException.class) public ResponseEntity<?> conflict(Exception e){return ResponseEntity.status(409).body(Map.of("message","数据冲突：商品编号重复或违反数据约束"));}
 @ExceptionHandler(Exception.class) public ResponseEntity<?> unexpected(Exception e){org.slf4j.LoggerFactory.getLogger(getClass()).error("请求失败",e);return ResponseEntity.status(500).body(Map.of("message","操作失败，事务已回滚；请查看运行窗口日志后重试"));}
}
