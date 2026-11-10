import json,urllib.request,urllib.error,datetime
from pathlib import Path
base='http://127.0.0.1:8080/api'; results=[]
def call(path,data=None,expect=200):
 req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req) as r:code=r.status;body=json.load(r)
 except urllib.error.HTTPError as e:code=e.code;body=json.load(e)
 assert code==expect,(path,code,body)
 results.append({'path':path,'input':data,'expected':expect,'actual':code,'response':body})
 return body
p=call('/products',{'code':'HTTP-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'),'name':'HTTP验证键盘','unit':'个'})['id']
call('/inbounds',{'productId':p,'locationId':1,'quantity':100})
o=call('/orders',{'productId':p,'locationId':1,'quantity':20})['id']
assert call('/stocks?productId='+str(p))[0]['QUANTITY']==100
call(f'/orders/{o}/ship',{})
assert call('/stocks?productId='+str(p))[0]['QUANTITY']==80
call(f'/orders/{o}/ship',{},409)
large=call('/orders',{'productId':p,'locationId':1,'quantity':81})['id'];call(f'/orders/{large}/ship',{},409)
for q in [0,-1,1.5,None,1000001]:call('/inbounds',{'productId':p,'locationId':1,'quantity':q},400)
s=next(s for s in call('/shipments') if s['ORDER_ID']==o)['ID']
call(f'/shipments/{s}/advance',{'status':'DELIVERED'},409)
call(f'/shipments/{s}/advance',{'status':'TRANSIT'})
call(f'/shipments/{s}/advance',{'status':'DELIVERED'})
tracks=call(f'/shipments/{s}/tracking');assert [t['STATUS'] for t in tracks]==['WAITING','TRANSIT','DELIVERED']
Path('docs/evidence/persist-ids.json').write_text(json.dumps({'product':p,'order':o,'shipment':s}))
Path('docs/evidence/http-results.json').write_text(json.dumps({'time':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'executor':'Codex automated HTTP verification','results':results},ensure_ascii=False,indent=2),encoding='utf8')
print('PASS HTTP: stock 100 -> 80, invalid operations rejected, three tracking records')
