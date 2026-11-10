# -*- coding: utf-8 -*-
"""接口自动化自测脚本：模拟一次完整的“入库—库存—盘点—出库—物流”业务闭环。
用法：先启动 app.py，再执行  python 自测脚本.py
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
TOKEN = ""
PASS = 0
FAIL = 0


def call(path, method="GET", body=None, token=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    tk = token if token is not None else TOKEN
    if tk:
        req.add_header("Authorization", "Bearer " + tk)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] {}".format(name))
    else:
        FAIL += 1
        print("  [FAIL] {} {}".format(name, extra))


def main():
    global TOKEN
    print("=== 1. 登录与鉴权 ===")
    r = call("/api/login", "POST", {"username": "admin", "password": "admin123"})
    check("管理员登录成功", r.get("ok"), r.get("msg"))
    TOKEN = (r.get("data") or {}).get("token", "")
    r = call("/api/login", "POST", {"username": "admin", "password": "wrong"})
    check("错误密码被拒绝(401)", not r.get("ok") and r.get("msg"), r)
    r = call("/api/users", token="")
    check("未登录访问被拒绝", not r.get("ok"), r.get("msg"))
    r = call("/api/login", "POST", {"username": "operator", "password": "123456"})
    op_token = (r.get("data") or {}).get("token", "")
    r = call("/api/users", token=op_token)
    check("作业员无系统管理权限(403)", not r.get("ok") and "权限" in (r.get("msg") or ""), r)

    print("=== 2. 基础数据 ===")
    whs = call("/api/warehouses")["data"]
    check("仓库列表非空", len(whs) > 0)
    prods = call("/api/products")["data"]
    check("商品列表非空", len(prods) > 0)
    locs = call("/api/locations?warehouse_id={}".format(whs[0]["id"]))["data"]
    check("库位列表非空", len(locs) > 0)

    print("=== 3. 入库全流程 ===")
    wh = whs[0]["id"]
    supplier = call("/api/suppliers")["data"][0]["id"]
    prod = prods[0]["id"]
    r = call("/api/inbound", "POST", {"supplier_id": supplier, "warehouse_id": wh,
                                      "remark": "自测入库", "items": [{"product_id": prod, "plan_qty": 50}]})
    check("创建入库单", r.get("ok"), r.get("msg"))
    ino = r["data"]["order_no"]
    oid = r["data"]["id"]
    items = call("/api/inbound")["data"]
    order = [x for x in items if x["id"] == oid][0]
    item_id = order["items"][0]["id"]
    r = call("/api/inbound/{}/putaway".format(oid), "POST", {"items": []})
    check("未验货直接上架被拦截", not r.get("ok"), r.get("msg"))
    r = call("/api/inbound/{}/receive".format(oid), "POST",
             {"items": [{"id": item_id, "recv_qty": 50, "qualified_qty": 48}]})
    check("收货验货(合格48)", r.get("ok") and r["data"]["qualified"] == 48, r)
    r = call("/api/inbound/{}/putaway".format(oid), "POST",
             {"items": [{"id": item_id, "location_id": locs[0]["id"], "batch_no": "B20261110"}]})
    check("上架入库(48件)", r.get("ok") and r["data"]["putaway"] == 48, r)
    order = [x for x in call("/api/inbound")["data"] if x["id"] == oid][0]
    check("入库单已完成", order["status"] == "已完成", order["status"])
    stock = call("/api/inventory?keyword=SKU10001")["data"]
    check("库存已增加至对应库位", any(s["qty"] == 48 for s in stock), stock)

    print("=== 4. 库存与盘点 ===")
    r = call("/api/checks", "POST", {"warehouse_id": wh})
    check("生成盘点单", r.get("ok"), r.get("msg"))
    cid = r["data"]["id"]
    tasks = call("/api/checks")["data"]
    bill = [x for x in tasks if x["id"] == cid][0]
    check("盘点明细带出账面数", len(bill["items"]) > 0)
    ci = bill["items"][0]
    r = call("/api/checks/{}/input".format(cid), "POST",
             {"items": [{"id": ci["id"], "real_qty": ci["book_qty"] - 3, "diff_reason": "破损报废"}]})
    check("录入实盘数(差异1条)", r.get("ok") and r["data"]["diff"] == 1, r)
    r = call("/api/checks/{}/approve".format(cid), "POST", {})
    check("审核调整库存", r.get("ok") and r["data"]["adjusted"] == 1, r)
    bill = [x for x in call("/api/checks")["data"] if x["id"] == cid][0]
    check("盘点单已完成", bill["status"] == "已完成", bill["status"])

    print("=== 5. 出库、拣货与物流协同 ===")
    r = call("/api/outbound", "POST", {"warehouse_id": wh, "customer": "北京华联商贸",
                                       "priority": "加急", "items": [{"product_id": prod, "plan_qty": 5}]})
    check("创建出库单并锁定库存", r.get("ok"), r.get("msg"))
    if not r.get("ok"):
        print(r)
        return report()
    oid2 = r["data"]["id"]
    r = call("/api/outbound", "POST", {"warehouse_id": wh, "customer": "库存不足测试",
                                       "items": [{"product_id": prod, "plan_qty": 99999}]})
    check("库存不足被拦截", not r.get("ok") and "库存不足" in (r.get("msg") or ""), r)
    r = call("/api/outbound/{}/review".format(oid2), "POST", {})
    check("未拣货不能复核", not r.get("ok"), r.get("msg"))
    picks = [x for x in call("/api/pick-tasks")["data"] if x["outbound_id"] == oid2]
    check("系统按库位生成拣货任务", len(picks) > 0)
    for p in picks:
        call("/api/pick-tasks/{}/confirm".format(p["id"]), "POST", {"picked_qty": p["plan_qty"], "picker": "王芳"})
    r = call("/api/outbound/{}/review".format(oid2), "POST", {})
    check("拣货完成可复核", r.get("ok"), r.get("msg"))
    r = call("/api/outbound/{}/ship".format(oid2), "POST", {"carrier": "德邦物流(模拟异常)", "dest": "北京市朝阳区"})
    check("确认出库并生成运单", r.get("ok"), r.get("msg"))
    check("模拟承运接口异常时推送失败", r["data"]["push"]["ok"] is False, r["data"]["push"])
    wbs = call("/api/waybills")["data"]
    wb = wbs[0]
    check("运单状态为推送失败", wb["status"] == "推送失败", wb["status"])
    # 换成正常承运商重新创建一单测试推送成功与轨迹
    r = call("/api/outbound", "POST", {"warehouse_id": wh, "customer": "北京朝阳门店",
                                       "items": [{"product_id": prod, "plan_qty": 2}]})
    oid3 = r["data"]["id"]
    for p in [x for x in call("/api/pick-tasks")["data"] if x["outbound_id"] == oid3]:
        call("/api/pick-tasks/{}/confirm".format(p["id"]), "POST", {"picked_qty": p["plan_qty"]})
    call("/api/outbound/{}/review".format(oid3), "POST", {})
    r = call("/api/outbound/{}/ship".format(oid3), "POST", {"carrier": "顺丰速运", "dest": "北京市朝阳区"})
    check("正常承运商推送成功", r.get("ok") and r["data"]["push"]["ok"], r.get("msg"))
    wbs = call("/api/waybills")["data"]
    wid = wbs[0]["id"]
    r = call("/api/waybills/{}/sync".format(wid), "POST", {})
    check("同步物流轨迹(已揽收)", r.get("ok") and r["data"].get("node") == "已揽收", r)
    r = call("/api/waybills/{}/trace".format(wid))
    check("轨迹查询返回节点", r.get("ok") and len(r["data"]["traces"]) >= 2, r)

    print("=== 6. 事件与日志 ===")
    evs = call("/api/events")["data"]
    types = {e["event_type"] for e in evs}
    for t in ["GoodsInEvent", "OrderShipEvent", "PickFinishEvent", "StockChangeEvent"]:
        check("事件已发布: " + t, t in types)
    logs = call("/api/logs")["data"]
    check("操作日志已记录", len(logs) > 5)
    r = call("/api/dashboard")
    check("工作台统计可读取", r.get("ok") and r["data"]["cards"]["stockTotal"] > 0, r.get("msg"))
    report()


def report():
    print("\n" + "=" * 46)
    print("自测完成：通过 {} 项，失败 {} 项".format(PASS, FAIL))
    print("=" * 46)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
