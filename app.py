# -*- coding: utf-8 -*-
"""智慧仓储物流协同系统 —— 后端服务（Python 标准库实现，零第三方依赖）

启动：python app.py
访问：http://localhost:8000
"""
import json
import os
import re
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
PORT = int(os.environ.get("WMS_PORT", "8000"))

TOKENS = {}          # token -> {"id","username","name","role","permissions"}
TOKEN_LOCK = threading.Lock()

#注释可删
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def gen_no(prefix):
    return "{}{}{:03d}".format(prefix, datetime.now().strftime("%Y%m%d%H%M%S"),
                               int.from_bytes(uuid.uuid4().bytes[:2], "big") % 1000)


class ApiError(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.message = message
        self.code = code


def log_op(user, action, target="", detail=""):
    db.execute("INSERT INTO operation_logs(username,action,target,detail,created_at) VALUES(?,?,?,?,?)",
              (user or "-", action, target, detail, now()))


def emit_event(event_type, aggregate_id, payload):
    """业务事件总线：写入事件表，模拟事件驱动架构中事件的发布与消费。"""
    db.execute("INSERT INTO business_events(event_type,aggregate_id,payload,status,created_at) VALUES(?,?,?,?,?)",
              (event_type, str(aggregate_id), json.dumps(payload, ensure_ascii=False), "已消费", now()))


# ---------------------------------------------------------------- 业务逻辑
def biz_login(body):
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()
    if not username or not password:
        raise ApiError("用户名和密码不能为空")
    u = db.query_one("SELECT u.*, r.code AS role_code, r.name AS role_name, r.permissions FROM users u "
                     "JOIN roles r ON r.id=u.role_id WHERE u.username=?", (username,))
    if not u or u["password"] != password:
        raise ApiError("用户名或密码错误", 401)
    if u["status"] != 1:
        raise ApiError("账号已停用，请联系管理员", 403)
    token = uuid.uuid4().hex
    perms = json.loads(u["permissions"])
    info = {"id": u["id"], "username": u["username"], "name": u["name"],
            "role": u["role_code"], "roleName": u["role_name"], "permissions": perms}
    with TOKEN_LOCK:
        TOKENS[token] = info
    log_op(u["username"], "登录系统", "登录", "角色：" + u["role_name"])
    return {"token": token, "user": info}


def biz_dashboard(user):
    whs = db.query("SELECT COUNT(*) c FROM warehouses WHERE status=1")[0]["c"]
    locs = db.query("SELECT COUNT(*) c FROM locations WHERE status=1")[0]["c"]
    skus = db.query("SELECT COUNT(*) c FROM products WHERE status=1")[0]["c"]
    stock_total = db.query("SELECT COALESCE(SUM(qty),0) s FROM stock")[0]["s"]
    warn = db.query("SELECT COUNT(*) c FROM (SELECT s.product_id, SUM(s.qty) qty, p.warn_threshold wt "
                    "FROM stock s JOIN products p ON p.id=s.product_id GROUP BY s.product_id) t "
                    "WHERE t.qty <= t.wt")[0]["c"]
    pending_in = db.query("SELECT COUNT(*) c FROM inbound_orders WHERE status<>'已完成' AND status<>'已取消'")[0]["c"]
    pending_out = db.query("SELECT COUNT(*) c FROM outbound_orders WHERE status<>'已出库' AND status<>'已取消'")[0]["c"]
    pending_check = db.query("SELECT COUNT(*) c FROM check_bills WHERE status<>'已完成'")[0]["c"]
    pending_pick = db.query("SELECT COUNT(*) c FROM pick_tasks WHERE status='待拣货'")[0]["c"]
    events = db.query("SELECT * FROM business_events ORDER BY id DESC LIMIT 8")
    warnings = db.query("SELECT p.sku, p.name, SUM(s.qty) qty, p.warn_threshold wt FROM stock s "
                        "JOIN products p ON p.id=s.product_id GROUP BY s.product_id HAVING qty <= p.warn_threshold "
                        "ORDER BY qty ASC")
    trend = db.query("SELECT substr(created_at,1,10) d, SUM(qty) qty FROM stock_moves "
                     "WHERE move_type LIKE '%入库%' GROUP BY d ORDER BY d DESC LIMIT 7")
    return {
        "cards": {"warehouses": whs, "locations": locs, "skus": skus, "stockTotal": float(stock_total),
                  "warnCount": warn, "pendingInbound": pending_in, "pendingOutbound": pending_out,
                  "pendingCheck": pending_check, "pendingPick": pending_pick},
        "events": events, "warnings": warnings, "inboundTrend": list(reversed(trend)),
    }


# ---------------------------------------------------------------- 通用 CRUD 辅助
def crud_list(table, where="", params=()):
    return db.query("SELECT * FROM {} {} ORDER BY id DESC".format(table, where), params)


def ensure_not_empty(body, fields):
    for f in fields:
        if body.get(f) in (None, "", []):
            raise ApiError("参数 {} 不能为空".format(f))


# ---------------------------------------------------------------- 入库
def inbound_list(user, params):
    wh = params.get("warehouse_id")
    sql = ("SELECT o.*, s.name AS supplier_name, w.name AS warehouse_name FROM inbound_orders o "
           "LEFT JOIN suppliers s ON s.id=o.supplier_id LEFT JOIN warehouses w ON w.id=o.warehouse_id ")
    cond, args = [], []
    if wh:
        cond.append("o.warehouse_id=?")
        args.append(int(wh))
    if params.get("status"):
        cond.append("o.status=?")
        args.append(params["status"])
    sql += ("WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY o.id DESC"
    rows = db.query(sql, tuple(args))
    for r in rows:
        r["items"] = db.query(
            "SELECT i.*, p.sku, p.name AS product_name, p.unit, l.code AS location_code FROM inbound_items i "
            "LEFT JOIN products p ON p.id=i.product_id LEFT JOIN locations l ON l.id=i.location_id "
            "WHERE i.order_id=? ORDER BY i.id", (r["id"],))
    return rows


def inbound_create(user, body):
    ensure_not_empty(body, ["supplier_id", "warehouse_id", "items"])
    items = body["items"]
    if not items:
        raise ApiError("入库明细不能为空")
    order_no = gen_no("IN")
    total = sum(int(i.get("plan_qty") or 0) for i in items)
    if total <= 0:
        raise ApiError("入库数量必须大于 0")
    oid = db.execute_returning_id(
        "INSERT INTO inbound_orders(order_no,supplier_id,warehouse_id,status,total_qty,created_by,created_at,remark) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (order_no, int(body["supplier_id"]), int(body["warehouse_id"]), "待收货", total,
         user["username"], now(), body.get("remark") or ""))
    for it in items:
        db.execute("INSERT INTO inbound_items(order_id,product_id,plan_qty,status) VALUES(?,?,?,?)",
                   (oid, int(it["product_id"]), int(it["plan_qty"]), "待收货"))
    log_op(user["username"], "创建入库单", order_no, "总数量 {}".format(total))
    emit_event("InboundOrderCreatedEvent", order_no, {"orderNo": order_no, "totalQty": total})
    return {"id": oid, "order_no": order_no}


def inbound_receive(user, oid_s, body):
    o = require_inbound(oid_s)
    if o["status"] not in ("待收货", "收货中"):
        raise ApiError("当前状态[{}]不允许收货验货".format(o["status"]))
    rows = body.get("items") or []
    if not rows:
        raise ApiError("请填写实际收货数量")
    received = 0
    for r in rows:
        item = db.query_one("SELECT * FROM inbound_items WHERE id=? AND order_id=?", (int(r["id"]), o["id"]))
        if not item:
            continue
        recv = int(r.get("recv_qty") or 0)
        qualified = int(r.get("qualified_qty") if r.get("qualified_qty") is not None else recv)
        if qualified > recv:
            raise ApiError("合格数量不能大于实收数量")
        if recv < 0:
            raise ApiError("实收数量不能为负数")
        db.execute("UPDATE inbound_items SET recv_qty=?, qualified_qty=?, status=? WHERE id=?",
                   (recv, qualified, "待上架" if qualified > 0 else "收货完成", item["id"]))
        received += qualified
    db.execute("UPDATE inbound_orders SET status=? WHERE id=?", ("待上架", o["id"]))
    log_op(user["username"], "收货验货", o["order_no"], "合格数量 {}".format(received))
    emit_event("InboundAcceptedEvent", o["order_no"], {"received": received})
    return {"ok": True, "qualified": received}


def inbound_putaway(user, oid_s, body):
    """上架：将验货合格品入库位，生成库存与库存流水。"""
    o = require_inbound(oid_s)
    if o["status"] != "待上架":
        raise ApiError("当前状态[{}]不允许上架，请先完成收货验货".format(o["status"]))
    rows = body.get("items") or []
    if not rows:
        raise ApiError("请为明细指定上架库位")
    put = 0
    for r in rows:
        item = db.query_one("SELECT * FROM inbound_items WHERE id=? AND order_id=?", (int(r["id"]), o["id"]))
        if not item:
            continue
        if int(item["qualified_qty"]) <= 0:
            continue
        loc_id = int(r.get("location_id") or 0)
        loc = db.query_one("SELECT * FROM locations WHERE id=?", (loc_id,))
        if not loc:
            raise ApiError("库位不存在")
        if loc["warehouse_id"] != o["warehouse_id"]:
            raise ApiError("库位[{}]不属于单据所在仓库".format(loc["code"]))
        qty = int(item["qualified_qty"])
        batch = r.get("batch_no") or "B" + datetime.now().strftime("%Y%m%d")
        exists = db.query_one("SELECT * FROM stock WHERE location_id=? AND product_id=? AND batch_no=?",
                              (loc_id, item["product_id"], batch))
        if exists:
            db.execute("UPDATE stock SET qty=qty+?, updated_at=? WHERE id=?", (qty, now(), exists["id"]))
        else:
            db.execute("INSERT INTO stock(warehouse_id,location_id,product_id,qty,locked_qty,batch_no,updated_at) "
                       "VALUES(?,?,?,?,0,?,?)", (o["warehouse_id"], loc_id, item["product_id"], qty, batch, now()))
        db.execute("INSERT INTO stock_moves(move_type,product_id,location_id,qty,ref_no,operator,created_at) "
                   "VALUES(?,?,?,?,?,?,?)", ("入库上架", item["product_id"], loc_id, qty, o["order_no"],
                                             user["username"], now()))
        db.execute("UPDATE inbound_items SET location_id=?, status=? WHERE id=?", (loc_id, "已上架", item["id"]))
        put += qty
    db.execute("UPDATE inbound_orders SET status=?, finish_at=? WHERE id=?", ("已完成", now(), o["id"]))
    log_op(user["username"], "上架入库", o["order_no"], "上架数量 {}".format(put))
    emit_event("GoodsInEvent", o["order_no"], {"putawayQty": put, "orderNo": o["order_no"]})
    return {"ok": True, "putaway": put}


def require_inbound(oid_s):
    o = db.query_one("SELECT * FROM inbound_orders WHERE id=?", (int(oid_s),))
    if not o:
        raise ApiError("入库单不存在", 404)
    return o


# ---------------------------------------------------------------- 库存
def inventory_list(user, params):
    sql = ("SELECT s.id, s.location_id, s.product_id, s.qty, s.locked_qty, s.batch_no, s.updated_at, "
           "p.sku, p.name, p.category, p.unit, p.warn_threshold, l.code AS location_code, l.zone, "
           "w.id AS warehouse_id, w.name AS warehouse_name "
           "FROM stock s JOIN products p ON p.id=s.product_id JOIN locations l ON l.id=s.location_id "
           "JOIN warehouses w ON w.id=s.warehouse_id ")
    cond, args = [], []
    if params.get("warehouse_id"):
        cond.append("s.warehouse_id=?")
        args.append(int(params["warehouse_id"]))
    if params.get("keyword"):
        cond.append("(p.sku LIKE ? OR p.name LIKE ? OR l.code LIKE ?)")
        k = "%{}%".format(params["keyword"])
        args += [k, k, k]
    sql += ("WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY s.id DESC"
    return db.query(sql, tuple(args))


def inventory_warning(user, params):
    return db.query("SELECT p.id, p.sku, p.name, p.unit, p.warn_threshold, SUM(s.qty) qty FROM stock s "
                    "JOIN products p ON p.id=s.product_id GROUP BY s.product_id "
                    "HAVING qty <= p.warn_threshold ORDER BY qty ASC")


def stock_move_list(user, params):
    return db.query("SELECT m.*, p.sku, p.name AS product_name, l.code AS location_code FROM stock_moves m "
                    "LEFT JOIN products p ON p.id=m.product_id LEFT JOIN locations l ON l.id=m.location_id "
                    "ORDER BY m.id DESC LIMIT 200")


def check_create(user, body):
    ensure_not_empty(body, ["warehouse_id"])
    wh = int(body["warehouse_id"])
    bill_no = gen_no("ST")
    bid = db.execute_returning_id(
        "INSERT INTO check_bills(bill_no,warehouse_id,status,diff_count,created_by,created_at) VALUES(?,?,?,?,?,?)",
        (bill_no, wh, "待录入", 0, user["username"], now()))
    rows = db.query("SELECT s.* FROM stock s WHERE s.warehouse_id=?", (wh,))
    for r in rows:
        db.execute("INSERT INTO check_items(bill_id,product_id,location_id,book_qty) VALUES(?,?,?,?)",
                   (bid, r["product_id"], r["location_id"], r["qty"]))
    log_op(user["username"], "生成盘点单", bill_no, "盘点明细 {} 条".format(len(rows)))
    return {"id": bid, "bill_no": bill_no}


def check_list(user, params):
    rows = db.query("SELECT c.*, w.name AS warehouse_name FROM check_bills c LEFT JOIN warehouses w "
                    "ON w.id=c.warehouse_id ORDER BY c.id DESC")
    for r in rows:
        r["items"] = db.query("SELECT i.*, p.sku, p.name AS product_name, l.code AS location_code FROM check_items i "
                              "LEFT JOIN products p ON p.id=i.product_id LEFT JOIN locations l ON l.id=i.location_id "
                              "WHERE i.bill_id=?", (r["id"],))
    return rows


def check_input(user, bid_s, body):
    bill = db.query_one("SELECT * FROM check_bills WHERE id=?", (int(bid_s),))
    if not bill:
        raise ApiError("盘点单不存在", 404)
    if bill["status"] != "待录入":
        raise ApiError("当前状态[{}]不允许录入".format(bill["status"]))
    rows = body.get("items") or []
    diff = 0
    for r in rows:
        real = r.get("real_qty")
        if real is None or real == "":
            continue
        real = int(real)
        item = db.query_one("SELECT * FROM check_items WHERE id=? AND bill_id=?", (int(r["id"]), bill["id"]))
        if not item:
            continue
        db.execute("UPDATE check_items SET real_qty=?, diff_reason=? WHERE id=?",
                   (real, r.get("diff_reason") or "", item["id"]))
        if real != item["book_qty"]:
            diff += 1
    db.execute("UPDATE check_bills SET status=?, diff_count=? WHERE id=?", ("待审核", diff, bill["id"]))
    log_op(user["username"], "录入盘点结果", bill["bill_no"], "差异明细 {} 条".format(diff))
    return {"ok": True, "diff": diff}


def check_approve(user, bid_s, body):
    bill = db.query_one("SELECT * FROM check_bills WHERE id=?", (int(bid_s),))
    if not bill:
        raise ApiError("盘点单不存在", 404)
    if bill["status"] != "待审核":
        raise ApiError("当前状态[{}]不允许审核".format(bill["status"]))
    items = db.query("SELECT * FROM check_items WHERE bill_id=? AND real_qty IS NOT NULL", (bill["id"],))
    adjusted = 0
    for it in items:
        delta = it["real_qty"] - it["book_qty"]
        if delta == 0:
            continue
        st = db.query_one("SELECT * FROM stock WHERE location_id=? AND product_id=?",
                          (it["location_id"], it["product_id"]))
        if st:
            db.execute("UPDATE stock SET qty=?, updated_at=? WHERE id=?", (it["real_qty"], now(), st["id"]))
        else:
            db.execute("INSERT INTO stock(warehouse_id,location_id,product_id,qty,locked_qty,batch_no,updated_at) "
                       "VALUES(?,?,?,?,0,?,?)", (bill["warehouse_id"], it["location_id"], it["product_id"],
                                                 it["real_qty"], "盘盈", now()))
        db.execute("INSERT INTO stock_moves(move_type,product_id,location_id,qty,ref_no,operator,created_at) "
                   "VALUES(?,?,?,?,?,?,?)", ("盘点调整", it["product_id"], it["location_id"], delta,
                                             bill["bill_no"], user["username"], now()))
        adjusted += 1
    db.execute("UPDATE check_bills SET status=?, finish_at=? WHERE id=?", ("已完成", now(), bill["id"]))
    log_op(user["username"], "盘点审核调整", bill["bill_no"], "调整明细 {} 条".format(adjusted))
    emit_event("StockChangeEvent", bill["bill_no"], {"adjusted": adjusted, "billNo": bill["bill_no"]})
    return {"ok": True, "adjusted": adjusted}


# ---------------------------------------------------------------- 出库与拣选
def outbound_list(user, params):
    rows = db.query("SELECT o.*, w.name AS warehouse_name FROM outbound_orders o "
                    "LEFT JOIN warehouses w ON w.id=o.warehouse_id ORDER BY o.id DESC")
    for r in rows:
        r["items"] = db.query("SELECT i.*, p.sku, p.name AS product_name, p.unit, l.code AS location_code "
                              "FROM outbound_items i LEFT JOIN products p ON p.id=i.product_id "
                              "LEFT JOIN locations l ON l.id=i.location_id WHERE i.order_id=?", (r["id"],))
        r["waybill"] = db.query_one("SELECT * FROM waybills WHERE outbound_id=?", (r["id"],))
    return rows


def outbound_create(user, body):
    ensure_not_empty(body, ["warehouse_id", "items"])
    wh = int(body["warehouse_id"])
    order_no = gen_no("OUT")
    items = body["items"]
    total = sum(int(i.get("plan_qty") or 0) for i in items)
    if total <= 0:
        raise ApiError("出库数量必须大于 0")
    # 库存校验
    for it in items:
        pid = int(it["product_id"])
        need = int(it["plan_qty"])
        avail = db.query("SELECT COALESCE(SUM(qty-locked_qty),0) q FROM stock WHERE product_id=? AND warehouse_id=?",
                         (pid, wh))[0]["q"]
        if avail < need:
            p = db.query_one("SELECT sku,name FROM products WHERE id=?", (pid,))
            raise ApiError("库存不足：{} 可用 {}，需求 {}".format(p["name"] if p else pid, avail, need))
    oid = db.execute_returning_id(
        "INSERT INTO outbound_orders(order_no,customer,warehouse_id,status,priority,total_qty,created_by,created_at,remark) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (order_no, body.get("customer") or "", wh, "待拣货", body.get("priority") or "普通",
         total, user["username"], now(), body.get("remark") or ""))
    for it in items:
        pid = int(it["product_id"])
        need = int(it["plan_qty"])
        # 分配库存（FIFO 按批次）
        remain = need
        picks = []
        for st in db.query("SELECT * FROM stock WHERE product_id=? AND warehouse_id=? AND qty>locked_qty "
                           "ORDER BY id", (pid, wh)):
            if remain <= 0:
                break
            take = min(int(st["qty"]) - int(st["locked_qty"]), remain)
            if take <= 0:
                continue
            db.execute("UPDATE stock SET locked_qty=locked_qty+? WHERE id=?", (take, st["id"]))
            picks.append((st["location_id"], take))
            remain -= take
        first_loc = picks[0][0] if picks else None
        db.execute("INSERT INTO outbound_items(order_id,product_id,plan_qty,location_id) VALUES(?,?,?,?)",
                   (oid, pid, need, first_loc))
        for loc_id, take in picks:
            db.execute("INSERT INTO pick_tasks(task_no,outbound_id,outbound_no,product_id,location_id,plan_qty,status,created_at) "
                       "VALUES(?,?,?,?,?,?,?,?)",
                       (gen_no("PK"), oid, order_no, pid, loc_id, take, "待拣货", now()))
    log_op(user["username"], "创建出库单", order_no, "总数量 {}".format(total))
    emit_event("OutboundOrderCreatedEvent", order_no, {"orderNo": order_no, "totalQty": total})
    return {"id": oid, "order_no": order_no}


def pick_list(user, params):
    cond, args = [], []
    if params.get("status"):
        cond.append("t.status=?")
        args.append(params["status"])
    sql = ("SELECT t.*, p.sku, p.name AS product_name, p.unit, l.code AS location_code, o.customer "
           "FROM pick_tasks t LEFT JOIN products p ON p.id=t.product_id "
           "LEFT JOIN locations l ON l.id=t.location_id LEFT JOIN outbound_orders o ON o.id=t.outbound_id ")
    sql += ("WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY t.id DESC"
    return db.query(sql, tuple(args))


def pick_confirm(user, tid_s, body):
    t = db.query_one("SELECT * FROM pick_tasks WHERE id=?", (int(tid_s),))
    if not t:
        raise ApiError("拣货任务不存在", 404)
    if t["status"] != "待拣货":
        raise ApiError("任务当前状态[{}]，无需重复确认".format(t["status"]))
    qty = int(body.get("picked_qty") if body.get("picked_qty") not in (None, "") else t["plan_qty"])
    if qty <= 0 or qty > t["plan_qty"]:
        raise ApiError("拣货数量需在 1 ~ {} 之间".format(t["plan_qty"]))
    db.execute("UPDATE pick_tasks SET picked_qty=?, status='已拣货', picker=?, finish_at=? WHERE id=?",
               (qty, body.get("picker") or user["name"], now(), t["id"]))
    ob = db.query_one("SELECT * FROM outbound_orders WHERE id=?", (t["outbound_id"],))
    db.execute("UPDATE outbound_items SET picked_qty=picked_qty+? WHERE order_id=? AND product_id=?",
               (qty, ob["id"], t["product_id"]))
    left = db.query("SELECT COUNT(*) c FROM pick_tasks WHERE outbound_id=? AND status='待拣货'", (ob["id"],))[0]["c"]
    db.execute("UPDATE outbound_orders SET status=? WHERE id=?", ("拣货中" if left else "待复核", ob["id"]))
    emit_event("PickFinishEvent", t["task_no"], {"taskNo": t["task_no"], "qty": qty})
    log_op(user["username"], "拣货确认", t["task_no"], "数量 {}".format(qty))
    return {"ok": True}


def outbound_review(user, oid_s, body):
    o = db.query_one("SELECT * FROM outbound_orders WHERE id=?", (int(oid_s),))
    if not o:
        raise ApiError("出库单不存在", 404)
    if o["status"] != "待复核":
        raise ApiError("当前状态[{}]不允许复核，请先完成拣货".format(o["status"]))
    db.execute("UPDATE outbound_orders SET status=? WHERE id=?", ("待出库", o["id"]))
    log_op(user["username"], "出库复核", o["order_no"], "复核通过")
    return {"ok": True}


def outbound_ship(user, oid_s, body):
    o = db.query_one("SELECT * FROM outbound_orders WHERE id=?", (int(oid_s),))
    if not o:
        raise ApiError("出库单不存在", 404)
    if o["status"] != "待出库":
        raise ApiError("当前状态[{}]不允许确认出库".format(o["status"]))
    carrier = body.get("carrier") or "顺丰速运"
    dest = body.get("dest") or (o["customer"] or "客户自提")
    # 扣减库存（先按任务锁定，再实际扣减）
    tasks = db.query("SELECT * FROM pick_tasks WHERE outbound_id=? AND status='已拣货'", (o["id"],))
    if not tasks:
        raise ApiError("没有已完成的拣货任务，无法出库")
    for t in tasks:
        st = db.query_one("SELECT * FROM stock WHERE location_id=? AND product_id=?", (t["location_id"], t["product_id"]))
        if not st:
            raise ApiError("库存记录缺失，无法出库")
        q = int(t["picked_qty"])
        if int(st["qty"]) < q:
            raise ApiError("库存不足，无法出库：{} 现有 {}".format(t["task_no"], st["qty"]))
        db.execute("UPDATE stock SET qty=qty-?, locked_qty=MAX(locked_qty-?,0), updated_at=? WHERE id=?",
                   (q, int(t["plan_qty"]), now(), st["id"]))
        db.execute("INSERT INTO stock_moves(move_type,product_id,location_id,qty,ref_no,operator,created_at) "
                   "VALUES(?,?,?,?,?,?,?)", ("出库下架", t["product_id"], t["location_id"], -q,
                                             o["order_no"], user["username"], now()))
    db.execute("UPDATE outbound_orders SET status=? WHERE id=?", ("已出库", o["id"]))
    waybill_no = gen_no("WB")
    wid = db.execute_returning_id(
        "INSERT INTO waybills(waybill_no,outbound_id,outbound_no,carrier,dest,status,created_at) "
        "VALUES(?,?,?,?,?,?,?)", (waybill_no, o["id"], o["order_no"], carrier, dest, "待推送", now()))
    db.execute("INSERT INTO logistics_traces(waybill_no,node,time,description) VALUES(?,?,?,?)",
               (waybill_no, "已出库", now(), "货物完成出库复核，交承运商 " + carrier))
    emit_event("OrderShipEvent", o["order_no"], {"orderNo": o["order_no"], "waybillNo": waybill_no})
    log_op(user["username"], "确认出库", o["order_no"], "运单 " + waybill_no)
    result = push_waybill(user, wid)
    return {"ok": True, "waybill_no": waybill_no, "push": result}


def push_waybill(user, wid):
    """调用（模拟的）承运平台 API 推送运单，失败写入失败状态供重试。"""
    w = db.query_one("SELECT * FROM waybills WHERE id=?", (wid,))
    if not w:
        raise ApiError("运单不存在", 404)
    db.execute("UPDATE waybills SET push_attempts=push_attempts+1 WHERE id=?", (wid,))
    simulate_fail = "异常" in (w["carrier"] or "")
    if simulate_fail:
        db.execute("UPDATE waybills SET status='推送失败' WHERE id=?", (wid,))
        emit_event("LogisticsPushFailedEvent", w["waybill_no"], {"waybill": w["waybill_no"], "retry": w["push_attempts"] + 1})
        log_op(user["username"], "运单推送失败", w["waybill_no"], "承运商接口异常，等待重试")
        return {"ok": False, "msg": "承运平台接口异常，运单已置为推送失败，可重试"}
    db.execute("UPDATE waybills SET status='已推送', pushed_at=? WHERE id=?", (now(), wid))
    db.execute("INSERT INTO logistics_traces(waybill_no,node,time,description) VALUES(?,?,?,?)",
               (w["waybill_no"], "已推送承运商", now(), "运单信息已推送至 {} 平台".format(w["carrier"])))
    emit_event("LogisticsPushEvent", w["waybill_no"], {"waybill": w["waybill_no"], "carrier": w["carrier"]})
    log_op(user["username"], "推送运单", w["waybill_no"], "承运商 " + (w["carrier"] or ""))
    return {"ok": True, "msg": "推送成功"}


def waybill_list(user, params):
    return db.query("SELECT w.*, o.customer FROM waybills w LEFT JOIN outbound_orders o ON o.id=w.outbound_id "
                    "ORDER BY w.id DESC")


def waybill_trace(user, wid_s):
    w = db.query_one("SELECT * FROM waybills WHERE id=?", (int(wid_s),))
    if not w:
        raise ApiError("运单不存在", 404)
    return {"waybill": w, "traces": db.query(
        "SELECT * FROM logistics_traces WHERE waybill_no=? ORDER BY id", (w["waybill_no"],))}


def waybill_sync_trace(user, wid_s):
    """模拟向承运平台查询轨迹，追加一条在途节点，并做异常预警。"""
    w = db.query_one("SELECT * FROM waybills WHERE id=?", (int(wid_s),))
    if not w:
        raise ApiError("运单不存在", 404)
    if w["status"] != "已推送":
        raise ApiError("运单尚未成功推送，无法同步轨迹")
    last = db.query_one("SELECT * FROM logistics_traces WHERE waybill_no=? ORDER BY id DESC", (w["waybill_no"],))
    nodes = ["已揽收", "运输中-天津分拨中心", "运输中-北京中转场", "派送中", "已签收"]
    idx = 0
    if last:
        base = last["node"]
        idx = nodes.index(base) + 1 if base in nodes else 0
    if idx >= len(nodes):
        return {"ok": True, "msg": "运单已签收，无新轨迹"}
    node = nodes[idx]
    desc = {"已揽收": "快递员已揽收，运单{}".format(w["waybill_no"]),
            "运输中-天津分拨中心": "货物到达天津分拨中心，预计次日发出",
            "运输中-北京中转场": "货物到达北京中转场，正在分拣",
            "派送中": "快件已到达目的地网点，安排派送",
            "已签收": "客户已签收，运单完成"}.get(node, node)
    db.execute("INSERT INTO logistics_traces(waybill_no,node,time,description) VALUES(?,?,?,?)",
               (w["waybill_no"], node, now(), desc))
    if node == "已签收":
        db.execute("UPDATE waybills SET status='已签收' WHERE id=?", (w["id"],))
    if node == "运输中-北京中转场" and w["dest"] and "北京" not in (w["dest"] or ""):
        emit_event("LogisticsAbnormalEvent", w["waybill_no"], {"waybill": w["waybill_no"], "reason": "路由偏离预警"})
        db.execute("INSERT INTO logistics_traces(waybill_no,node,time,description) VALUES(?,?,?,?)",
                   (w["waybill_no"], "异常预警", now(), "轨迹区域与目的地不一致，已触发异常预警流程"))
    log_op(user["username"], "同步物流轨迹", w["waybill_no"], node)
    return {"ok": True, "node": node}


# ---------------------------------------------------------------- 系统管理
def user_list(user, params):
    rows = db.query("SELECT u.id, u.username, u.name, u.role_id, u.phone, u.status, u.created_at, "
                    "r.name AS role_name, r.code AS role_code FROM users u "
                    "JOIN roles r ON r.id=u.role_id ORDER BY u.id")
    return rows


def user_create(user, body):
    ensure_not_empty(body, ["username", "password", "name", "role_id"])
    if db.query_one("SELECT 1 FROM users WHERE username=?", (body["username"],)):
        raise ApiError("用户名已存在")
    db.execute("INSERT INTO users(username,password,name,role_id,phone,status,created_at) VALUES(?,?,?,?,?,1,?)",
               (body["username"], body["password"], body["name"], int(body["role_id"]),
                body.get("phone") or "", now()))
    log_op(user["username"], "新增用户", body["username"], body["name"])
    return {"ok": True}


def user_update(user, uid_s, body):
    u = db.query_one("SELECT * FROM users WHERE id=?", (int(uid_s),))
    if not u:
        raise ApiError("用户不存在", 404)
    db.execute("UPDATE users SET name=?, role_id=?, phone=?, status=? WHERE id=?",
               (body.get("name") or u["name"], int(body.get("role_id") or u["role_id"]),
                body.get("phone") or u["phone"], int(body.get("status", u["status"])), u["id"]))
    if body.get("password"):
        db.execute("UPDATE users SET password=? WHERE id=?", (body["password"], u["id"]))
    log_op(user["username"], "修改用户", u["username"], "角色/状态更新")
    return {"ok": True}


def user_delete(user, uid_s):
    u = db.query_one("SELECT * FROM users WHERE id=?", (int(uid_s),))
    if not u:
        raise ApiError("用户不存在", 404)
    if u["username"] == "admin":
        raise ApiError("内置管理员账号不可删除")
    db.execute("DELETE FROM users WHERE id=?", (u["id"],))
    log_op(user["username"], "删除用户", u["username"], "")
    return {"ok": True}


def role_list(user, params):
    rows = db.query("SELECT * FROM roles ORDER BY id")
    for r in rows:
        r["permissions"] = json.loads(r["permissions"])
    return rows


def role_update(user, rid_s, body):
    r = db.query_one("SELECT * FROM roles WHERE id=?", (int(rid_s),))
    if not r:
        raise ApiError("角色不存在", 404)
    perms = body.get("permissions")
    if perms is not None:
        db.execute("UPDATE roles SET permissions=? WHERE id=?",
                   (json.dumps(perms, ensure_ascii=False), r["id"]))
    if body.get("name"):
        db.execute("UPDATE roles SET name=? WHERE id=?", (body["name"], r["id"]))
    log_op(user["username"], "修改角色权限", r["code"], json.dumps(perms, ensure_ascii=False) if perms else "")
    return {"ok": True}


def event_list(user, params):
    return db.query("SELECT * FROM business_events ORDER BY id DESC LIMIT 100")


def log_list(user, params):
    return db.query("SELECT * FROM operation_logs ORDER BY id DESC LIMIT 100")


# ---------------------------------------------------------------- 路由表
ROUTES = []


def route(method, pattern, perm=None):
    def deco(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn, perm))
        return fn
    return deco


# 认证
route("POST", r"/api/login", None)(lambda u, p, b, m: biz_login(b))
route("POST", r"/api/logout", None)(lambda u, p, b, m: {"ok": True})


@route("GET", r"/api/me")
def _me(u, p, b, m):
    return u


@route("GET", r"/api/dashboard")
def _dash(u, p, b, m):
    return biz_dashboard(u)


# 基础数据
@route("GET", r"/api/warehouses")
def _wh(u, p, b, m):
    return db.query("SELECT * FROM warehouses ORDER BY id")


@route("POST", r"/api/warehouses", "master")
def _wh_create(u, p, b, m):
    ensure_not_empty(b, ["code", "name"])
    db.execute("INSERT INTO warehouses(code,name,address,manager,status) VALUES(?,?,?,?,1)",
               (b["code"], b["name"], b.get("address") or "", b.get("manager") or ""))
    log_op(u["username"], "新增仓库", b["code"], b["name"])
    return {"ok": True}


@route("PUT", r"/api/warehouses/(\d+)", "master")
def _wh_update(u, p, b, m):
    wid = int(m.group(1))
    w = db.query_one("SELECT * FROM warehouses WHERE id=?", (wid,))
    if not w:
        raise ApiError("仓库不存在", 404)
    db.execute("UPDATE warehouses SET name=?, address=?, manager=?, status=? WHERE id=?",
               (b.get("name") or w["name"], b.get("address") if b.get("address") is not None else w["address"],
                b.get("manager") if b.get("manager") is not None else w["manager"],
                int(b.get("status", w["status"])), wid))
    return {"ok": True}


@route("DELETE", r"/api/warehouses/(\d+)", "master")
def _wh_delete(u, p, b, m):
    wid = int(m.group(1))
    if db.query_one("SELECT 1 FROM stock WHERE warehouse_id=? AND qty>0 LIMIT 1", (wid,)):
        raise ApiError("该仓库仍有库存，不能删除")
    db.execute("DELETE FROM warehouses WHERE id=?", (wid,))
    return {"ok": True}


@route("GET", r"/api/locations")
def _loc(u, p, b, m):
    sql = ("SELECT l.*, w.name AS warehouse_name FROM locations l JOIN warehouses w ON w.id=l.warehouse_id ")
    cond, args = [], []
    if p.get("warehouse_id"):
        cond.append("l.warehouse_id=?")
        args.append(int(p["warehouse_id"]))
    sql += ("WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY l.warehouse_id, l.code"
    return db.query(sql, tuple(args))


@route("POST", r"/api/locations", "master")
def _loc_create(u, p, b, m):
    ensure_not_empty(b, ["warehouse_id", "code"])
    db.execute("INSERT INTO locations(warehouse_id,code,zone,type,capacity,status) VALUES(?,?,?,?,?,1)",
               (int(b["warehouse_id"]), b["code"], b.get("zone") or "", b.get("type") or "存储位",
                int(b.get("capacity") or 100)))
    log_op(u["username"], "新增库位", b["code"], "")
    return {"ok": True}


@route("DELETE", r"/api/locations/(\d+)", "master")
def _loc_delete(u, p, b, m):
    lid = int(m.group(1))
    if db.query_one("SELECT 1 FROM stock WHERE location_id=? AND qty>0 LIMIT 1", (lid,)):
        raise ApiError("该库位仍有库存，不能删除")
    db.execute("DELETE FROM locations WHERE id=?", (lid,))
    return {"ok": True}


@route("GET", r"/api/products")
def _prod(u, p, b, m):
    return db.query("SELECT * FROM products ORDER BY id")


@route("POST", r"/api/products", "master")
def _prod_create(u, p, b, m):
    ensure_not_empty(b, ["sku", "name"])
    db.execute("INSERT INTO products(sku,name,category,unit,spec,price,warn_threshold,status) VALUES(?,?,?,?,?,?,?,1)",
               (b["sku"], b["name"], b.get("category") or "", b.get("unit") or "件", b.get("spec") or "",
                float(b.get("price") or 0), int(b.get("warn_threshold") or 10)))
    log_op(u["username"], "新增商品", b["sku"], b["name"])
    return {"ok": True}


@route("PUT", r"/api/products/(\d+)", "master")
def _prod_update(u, p, b, m):
    pid = int(m.group(1))
    pr = db.query_one("SELECT * FROM products WHERE id=?", (pid,))
    if not pr:
        raise ApiError("商品不存在", 404)
    db.execute("UPDATE products SET name=?, category=?, unit=?, spec=?, price=?, warn_threshold=?, status=? WHERE id=?",
               (b.get("name") or pr["name"], b.get("category") if b.get("category") is not None else pr["category"],
                b.get("unit") or pr["unit"], b.get("spec") if b.get("spec") is not None else pr["spec"],
                float(b.get("price") if b.get("price") not in (None, "") else pr["price"]),
                int(b.get("warn_threshold") if b.get("warn_threshold") not in (None, "") else pr["warn_threshold"]),
                int(b.get("status", pr["status"])), pid))
    return {"ok": True}


@route("DELETE", r"/api/products/(\d+)", "master")
def _prod_delete(u, p, b, m):
    pid = int(m.group(1))
    if db.query_one("SELECT 1 FROM stock WHERE product_id=? AND qty>0 LIMIT 1", (pid,)):
        raise ApiError("该商品仍有库存，不能删除")
    db.execute("DELETE FROM products WHERE id=?", (pid,))
    return {"ok": True}


@route("GET", r"/api/suppliers")
def _sup(u, p, b, m):
    return db.query("SELECT * FROM suppliers ORDER BY id")


@route("POST", r"/api/suppliers", "master")
def _sup_create(u, p, b, m):
    ensure_not_empty(b, ["code", "name"])
    db.execute("INSERT INTO suppliers(code,name,contact,phone,status) VALUES(?,?,?,?,1)",
               (b["code"], b["name"], b.get("contact") or "", b.get("phone") or ""))
    return {"ok": True}


# 入库
@route("GET", r"/api/inbound")
def _in_list(u, p, b, m):
    return inbound_list(u, p)


@route("POST", r"/api/inbound", "inbound")
def _in_create(u, p, b, m):
    return inbound_create(u, b)


@route("POST", r"/api/inbound/(\d+)/receive", "inbound")
def _in_receive(u, p, b, m):
    return inbound_receive(u, m.group(1), b)


@route("POST", r"/api/inbound/(\d+)/putaway", "inbound")
def _in_putaway(u, p, b, m):
    return inbound_putaway(u, m.group(1), b)


# 库存
@route("GET", r"/api/inventory")
def _inv(u, p, b, m):
    return inventory_list(u, p)


@route("GET", r"/api/inventory/warning")
def _inv_warn(u, p, b, m):
    return inventory_warning(u, p)


@route("GET", r"/api/stock-moves")
def _moves(u, p, b, m):
    return stock_move_list(u, p)


@route("GET", r"/api/checks")
def _check_list(u, p, b, m):
    return check_list(u, p)


@route("POST", r"/api/checks", "inventory")
def _check_create(u, p, b, m):
    return check_create(u, b)


@route("POST", r"/api/checks/(\d+)/input", "inventory")
def _check_input(u, p, b, m):
    return check_input(u, m.group(1), b)


@route("POST", r"/api/checks/(\d+)/approve", "inventory")
def _check_approve(u, p, b, m):
    return check_approve(u, m.group(1), b)


# 出库
@route("GET", r"/api/outbound")
def _out_list(u, p, b, m):
    return outbound_list(u, p)


@route("POST", r"/api/outbound", "outbound")
def _out_create(u, p, b, m):
    return outbound_create(u, b)


@route("POST", r"/api/outbound/(\d+)/review", "outbound")
def _out_review(u, p, b, m):
    return outbound_review(u, m.group(1), b)


@route("POST", r"/api/outbound/(\d+)/ship", "outbound")
def _out_ship(u, p, b, m):
    return outbound_ship(u, m.group(1), b)


@route("GET", r"/api/pick-tasks")
def _pick_list(u, p, b, m):
    return pick_list(u, p)


@route("POST", r"/api/pick-tasks/(\d+)/confirm", "picking")
def _pick_confirm(u, p, b, m):
    return pick_confirm(u, m.group(1), b)


@route("GET", r"/api/waybills")
def _wb_list(u, p, b, m):
    return waybill_list(u, p)


@route("GET", r"/api/waybills/(\d+)/trace")
def _wb_trace(u, p, b, m):
    return waybill_trace(u, m.group(1))


@route("POST", r"/api/waybills/(\d+)/push", "outbound")
def _wb_push(u, p, b, m):
    return push_waybill(u, int(m.group(1)))


@route("POST", r"/api/waybills/(\d+)/sync", "outbound")
def _wb_sync(u, p, b, m):
    return waybill_sync_trace(u, m.group(1))


# 系统
@route("GET", r"/api/users", "system")
def _users(u, p, b, m):
    return user_list(u, p)


@route("POST", r"/api/users", "system")
def _user_create(u, p, b, m):
    return user_create(u, b)


@route("PUT", r"/api/users/(\d+)", "system")
def _user_update(u, p, b, m):
    return user_update(u, m.group(1), b)


@route("DELETE", r"/api/users/(\d+)", "system")
def _user_delete(u, p, b, m):
    return user_delete(u, m.group(1))


@route("GET", r"/api/roles")
def _roles(u, p, b, m):
    return role_list(u, p)


@route("PUT", r"/api/roles/(\d+)", "system")
def _role_update(u, p, b, m):
    return role_update(u, m.group(1), b)


@route("GET", r"/api/events")
def _events(u, p, b, m):
    return event_list(u, p)


@route("GET", r"/api/logs")
def _logs(u, p, b, m):
    return log_list(u, p)


# ---------------------------------------------------------------- HTTP 服务
class Handler(BaseHTTPRequestHandler):
    server_version = "WMS/1.0"

    def log_message(self, fmt, *args):
        pass

    # ---- 静态文件
    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        fpath = os.path.normpath(os.path.join(WEB_DIR, path.lstrip("/")))
        if not fpath.startswith(os.path.abspath(WEB_DIR)):
            self._send_json({"ok": False, "msg": "非法路径"}, 403)
            return
        if not os.path.exists(fpath) or os.path.isdir(fpath):
            self._send_json({"ok": False, "msg": "Not Found"}, 404)
            return
        ctype = {"html": "text/html; charset=utf-8", "css": "text/css; charset=utf-8",
                 "js": "application/javascript; charset=utf-8", "svg": "image/svg+xml",
                 "png": "image/png", "ico": "image/x-icon", "json": "application/json; charset=utf-8"}.get(
            fpath.rsplit(".", 1)[-1].lower(), "application/octet-stream")
        with open(fpath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.end_headers()

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            raise ApiError("请求体不是合法的 JSON")

    def _auth(self):
        h = self.headers.get("Authorization") or ""
        token = h[7:] if h.startswith("Bearer ") else h
        if not token:
            qs = parse_qs(urlparse(self.path).query)
            token = (qs.get("token") or [""])[0]
        with TOKEN_LOCK:
            return TOKENS.get(token)

    def _handle(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            return self._serve_static(path)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        try:
            body = self._read_body() if method in ("POST", "PUT", "DELETE") else {}
            user = self._auth()
            if path == "/api/login":
                return self._send_json({"ok": True, "data": biz_login(body)})
            if path == "/api/logout":
                return self._send_json({"ok": True, "data": {"msg": "已退出"}})
            if not user:
                return self._send_json({"ok": False, "msg": "未登录或登录已失效，请重新登录"}, 401)
            for m_method, rx, fn, perm in ROUTES:
                if m_method != method:
                    continue
                match = rx.match(path)
                if not match:
                    continue
                if perm and perm not in user["permissions"]:
                    raise ApiError("当前角色[{}]无该操作权限".format(user["roleName"]), 403)
                result = fn(user, params, body, match)
                return self._send_json({"ok": True, "data": result})
            return self._send_json({"ok": False, "msg": "接口不存在: {} {}".format(method, path)}, 404)
        except ApiError as e:
            return self._send_json({"ok": False, "msg": e.message}, e.code)
        except Exception as e:
            traceback.print_exc()
            return self._send_json({"ok": False, "msg": "服务器内部错误: {}".format(e)}, 500)


def main():
    db.init_db()
    if not os.path.exists(WEB_DIR):
        print("警告：web 目录不存在")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("=" * 56)
    print("  智慧仓储物流协同系统 已启动")
    print("  访问地址：http://localhost:{}/".format(PORT))
    print("  默认账号：admin / admin123")
    print("  停止服务：Ctrl + C")
    print("=" * 56)
    if os.environ.get("WMS_NO_BROWSER") != "1":
        try:
            import webbrowser
            threading.Timer(1.2, lambda: webbrowser.open("http://localhost:{}/".format(PORT))).start()
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")


if __name__ == "__main__":
    main()
