import sys,json,datetime
from pathlib import Path
# Install playwright into your own Python environment before running this optional check.
from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8080');expect(page.locator('#notice')).to_have_text('仓库已连接，可以开始作业。')
 page.get_by_role('button',name='商品资料',exact=True).click()
 code='UI-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f');page.locator('#productForm [name=code]').fill(code);page.locator('#productForm [name=name]').fill('键盘');page.get_by_role('button',name='保存商品',exact=True).click();expect(page.locator('#products')).to_contain_text(code)
 product=next(x for x in page.request.get('http://127.0.0.1:8080/api/products').json() if x['CODE']==code)['ID']
 page.get_by_role('button',name='入库与库存',exact=True).click();page.locator('#inboundForm [name=productId]').select_option(str(product));page.locator('#inboundForm [name=quantity]').fill('100');page.get_by_role('button',name='确认入库',exact=True).click();expect(page.locator('#inbounds')).to_contain_text('键盘')
 page.locator('#filter').select_option(str(product));expect(page.locator('#stocks')).to_contain_text('100');page.screenshot(path='docs/evidence/01-inventory.png',full_page=True)
 page.get_by_role('button',name='出库订单',exact=True).click();page.locator('#orderForm [name=productId]').select_option(str(product));page.locator('#orderForm [name=quantity]').fill('20');page.get_by_role('button',name='创建订单',exact=True).click();expect(page.locator('#ordersList')).to_contain_text('键盘')
 order=next(x for x in page.request.get('http://127.0.0.1:8080/api/orders').json() if x['PRODUCT_ID']==product)['ID']
 stocks=page.request.get(f'http://127.0.0.1:8080/api/stocks?productId={product}').json();assert stocks[0]['QUANTITY']==100
 page.locator(f'[data-ship="{order}"]').click();expect(page.locator(f'[data-ship="{order}"]')).to_have_count(0)
 stocks=page.request.get(f'http://127.0.0.1:8080/api/stocks?productId={product}').json();assert stocks[0]['QUANTITY']==80
 page.screenshot(path='docs/evidence/02-orders.png',full_page=True)
 page.get_by_role('button',name='物流跟踪',exact=True).click()
 ship=next(x for x in page.request.get('http://127.0.0.1:8080/api/shipments').json() if x['ORDER_ID']==order)['ID']
 page.locator(f'[data-track="{ship}"]').click();expect(page.locator('#tracking')).to_contain_text('待揽收')
 page.locator(f'[data-advance="{ship}"]').click();expect(page.locator(f'[data-advance="{ship}"]')).to_have_text('模拟已签收');page.locator(f'[data-advance="{ship}"]').click();expect(page.locator('#tracking .track')).to_have_count(3);expect(page.locator('#tracking')).to_contain_text('已签收');page.screenshot(path='docs/evidence/03-logistics.png',full_page=True)
 page.get_by_role('button',name='工作台',exact=True).click();page.screenshot(path='docs/evidence/04-overview.png',full_page=True)
 page.set_viewport_size({'width':390,'height':844});page.screenshot(path='docs/evidence/05-mobile.png',full_page=True)
 assert not errors,errors
 Path('docs/evidence/browser-results.json').write_text(json.dumps({'time':datetime.datetime.now().isoformat(),'browser':'Microsoft Edge headless Playwright','flow':'商品KB001/键盘 -> 入库100 -> 下单20(仍100) -> 出库(80) -> 运输 -> 签收','product':product,'order':order,'shipment':ship,'pageErrors':errors,'result':'PASS'},ensure_ascii=False,indent=2),encoding='utf8')
 print('PASS browser full flow, screenshots saved, no JS errors');browser.close()
