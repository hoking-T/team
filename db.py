# -*- coding: utf-8 -*-
"""数据库层：建表、初始化种子数据、通用查询封装。纯标准库 sqlite3 实现。"""
import os
import sqlite3
import json
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "wms.db")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    """执行写语句，返回 lastrowid"""
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def executemany(sql, seq):
    conn = get_conn()
    try:
        conn.executemany(sql, seq)
        conn.commit()
    finally:
        conn.close()


def execute_returning_id(sql, params=()):
    return execute(sql, params)


SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    permissions TEXT NOT NULL DEFAULT '[]',
    remark TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT NOT NULL,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    phone TEXT,
    status INTEGER NOT NULL DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS warehouses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    address TEXT,
    manager TEXT,
    status INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
    code TEXT NOT NULL,
    zone TEXT,
    type TEXT DEFAULT '存储位',
    capacity INTEGER DEFAULT 100,
    status INTEGER NOT NULL DEFAULT 1,
    UNIQUE(warehouse_id, code)
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    contact TEXT,
    phone TEXT,
    status INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    unit TEXT DEFAULT '件',
    spec TEXT,
    price REAL DEFAULT 0,
    warn_threshold INTEGER DEFAULT 10,
    status INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL DEFAULT 0,
    locked_qty INTEGER NOT NULL DEFAULT 0,
    batch_no TEXT,
    updated_at TEXT,
    UNIQUE(location_id, product_id, batch_no)
);

CREATE TABLE IF NOT EXISTS inbound_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT UNIQUE NOT NULL,
    supplier_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT '待收货',
    total_qty INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TEXT,
    finish_at TEXT,
    remark TEXT
);

CREATE TABLE IF NOT EXISTS inbound_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES inbound_orders(id),
    product_id INTEGER NOT NULL,
    plan_qty INTEGER NOT NULL,
    recv_qty INTEGER NOT NULL DEFAULT 0,
    qualified_qty INTEGER NOT NULL DEFAULT 0,
    location_id INTEGER,
    status TEXT NOT NULL DEFAULT '待收货'
);

CREATE TABLE IF NOT EXISTS outbound_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT UNIQUE NOT NULL,
    customer TEXT,
    warehouse_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT '待拣货',
    priority TEXT DEFAULT '普通',
    total_qty INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TEXT,
    remark TEXT
);

CREATE TABLE IF NOT EXISTS outbound_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES outbound_orders(id),
    product_id INTEGER NOT NULL,
    plan_qty INTEGER NOT NULL,
    picked_qty INTEGER NOT NULL DEFAULT 0,
    location_id INTEGER
);

CREATE TABLE IF NOT EXISTS pick_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_no TEXT UNIQUE NOT NULL,
    outbound_id INTEGER NOT NULL,
    outbound_no TEXT,
    product_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    plan_qty INTEGER NOT NULL,
    picked_qty INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT '待拣货',
    picker TEXT,
    created_at TEXT,
    finish_at TEXT
);

CREATE TABLE IF NOT EXISTS check_bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_no TEXT UNIQUE NOT NULL,
    warehouse_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT '待录入',
    diff_count INTEGER DEFAULT 0,
    created_by TEXT,
    created_at TEXT,
    finish_at TEXT
);

CREATE TABLE IF NOT EXISTS check_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES check_bills(id),
    product_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    book_qty INTEGER NOT NULL DEFAULT 0,
    real_qty INTEGER,
    diff_reason TEXT
);

CREATE TABLE IF NOT EXISTS waybills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    waybill_no TEXT UNIQUE NOT NULL,
    outbound_id INTEGER NOT NULL,
    outbound_no TEXT,
    carrier TEXT,
    dest TEXT,
    status TEXT NOT NULL DEFAULT '待推送',
    push_attempts INTEGER DEFAULT 0,
    pushed_at TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS logistics_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    waybill_no TEXT NOT NULL,
    node TEXT NOT NULL,
    time TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS business_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    aggregate_id TEXT,
    payload TEXT,
    status TEXT DEFAULT '已消费',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    action TEXT,
    target TEXT,
    detail TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS stock_moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    move_type TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    ref_no TEXT,
    operator TEXT,
    created_at TEXT
);
"""


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
    if not query("SELECT 1 FROM users LIMIT 1"):
        _seed()


def _seed():
    now_s = now()
    roles = [
        ("admin", "系统管理员", ["dashboard", "master", "inbound", "inventory", "picking", "outbound", "system"]),
        ("keeper", "仓库管理员", ["dashboard", "master", "inbound", "inventory", "picking", "outbound"]),
        ("operator", "仓储作业员", ["dashboard", "inventory", "picking", "outbound"]),
        ("logistics", "物流操作员", ["dashboard", "outbound"]),
    ]
    for code, name, perms in roles:
        execute("INSERT INTO roles(code,name,permissions) VALUES(?,?,?)",
                (code, name, json.dumps(perms, ensure_ascii=False)))

    users = [
        ("admin", "admin123", "张明", "admin", "13800000001"),
        ("keeper", "123456", "李强", "keeper", "13800000002"),
        ("operator", "123456", "王芳", "operator", "13800000003"),
        ("logistics", "123456", "赵磊", "logistics", "13800000004"),
    ]
    for u, p, n, r, phone in users:
        rid = query_one("SELECT id FROM roles WHERE code=?", (r,))["id"]
        execute("INSERT INTO users(username,password,name,role_id,phone,status,created_at) VALUES(?,?,?,?,?,1,?)",
                (u, p, n, rid, phone, now_s))

    wh1 = execute_returning_id(
        "INSERT INTO warehouses(code,name,address,manager,status) VALUES(?,?,?,?,1)",
        ("WH01", "天津中心仓", "天津市西青区赛达工业园 A 区", "李强"))
    wh2 = execute_returning_id(
        "INSERT INTO warehouses(code,name,address,manager,status) VALUES(?,?,?,?,1)",
        ("WH02", "北京备货仓", "北京市大兴区物流园 B 栋", "王芳"))

    locs = []
    for wh, prefix in ((wh1, "A"), (wh2, "B")):
        for zone in ("01", "02"):
            for n in range(1, 5):
                code = "{}-{}-{:02d}".format(prefix, zone, n)
                locs.append((wh, code, "{}区".format(zone), "存储位" if n < 4 else "拣货位",
                             200 if n < 4 else 50, 1))
    for wh, code, zone, typ, cap, st in locs:
        execute("INSERT INTO locations(warehouse_id,code,zone,type,capacity,status) VALUES(?,?,?,?,?,?)",
                (wh, code, zone, typ, cap, st))

    suppliers = [
        ("SUP01", "天津联创电子有限公司", "刘经理", "022-88880001"),
        ("SUP02", "苏州精工机械制造厂", "陈经理", "0512-66660002"),
        ("SUP03", "广州华美日用品公司", "周经理", "020-77770003"),
    ]
    for c, n, p, ph in suppliers:
        execute("INSERT INTO suppliers(code,name,contact,phone,status) VALUES(?,?,?,?,1)", (c, n, p, ph))

    products = [
        ("SKU10001", "无线蓝牙耳机", "数码配件", "件", "白色/标准版", 189.00, 30),
        ("SKU10002", "便携充电宝 10000mAh", "数码配件", "件", "黑色", 129.00, 30),
        ("SKU10003", "机械键盘 87 键", "电脑外设", "把", "青轴", 329.00, 20),
        ("SKU10004", "不锈钢保温杯 500ml", "生活用品", "个", "银色", 79.00, 50),
        ("SKU10005", "A4 复印纸 500 张", "办公用品", "包", "80g", 25.00, 100),
        ("SKU10006", "人体工学办公椅", "办公家具", "张", "黑色网布", 599.00, 10),
    ]
    for sku, n, cat, unit, spec, price, warn in products:
        execute("INSERT INTO products(sku,name,category,unit,spec,price,warn_threshold,status) VALUES(?,?,?,?,?,?,?,1)",
                (sku, n, cat, unit, spec, price, warn))

    # 初始库存
    init_stock = [
        (wh1, "A-01-01", "SKU10001", 120, "B20261001"),
        (wh1, "A-01-02", "SKU10002", 45, "B20261002"),
        (wh1, "A-01-03", "SKU10003", 18, "B20261003"),
        (wh1, "A-02-01", "SKU10004", 260, "B20261004"),
        (wh1, "A-02-02", "SKU10005", 380, "B20261005"),
        (wh1, "A-02-03", "SKU10006", 8, "B20261006"),
        (wh2, "B-01-01", "SKU10001", 60, "B20261011"),
        (wh2, "B-01-02", "SKU10005", 90, "B20261012"),
    ]
    for wh, loc_code, sku, qty, batch in init_stock:
        loc = query_one("SELECT id FROM locations WHERE warehouse_id=? AND code=?", (wh, loc_code))["id"]
        p = query_one("SELECT id FROM products WHERE sku=?", (sku,))["id"]
        execute("INSERT INTO stock(warehouse_id,location_id,product_id,qty,locked_qty,batch_no,updated_at) "
                "VALUES(?,?,?,?,0,?,?)", (wh, loc, p, qty, batch, now_s))
        execute("INSERT INTO stock_moves(move_type,product_id,location_id,qty,ref_no,operator,created_at) "
                "VALUES(?,?,?,?,?,?,?)", ("初始化", p, loc, qty, "SEED", "system", now_s))

    execute("INSERT INTO business_events(event_type,aggregate_id,payload,status,created_at) VALUES(?,?,?,?,?)",
            ("SystemInitEvent", "SYSTEM", json.dumps({"msg": "系统初始化完成，种子数据已加载"}, ensure_ascii=False),
             "已消费", now_s))


if __name__ == "__main__":
    init_db()
    print("数据库初始化完成:", DB_PATH)
