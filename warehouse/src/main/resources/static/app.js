const $=s=>document.querySelector(s);
const names={PENDING:'待出库',SHIPPED:'已出库',WAITING:'待揽收',TRANSIT:'运输中',DELIVERED:'已签收',STOCK_RECEIVED:'库存入库',STOCK_SHIPPED:'库存扣减',ORDER_CREATED:'订单创建',ORDER_SHIPPED:'订单出库'};
const titles={overview:'仓库工作台',catalog:'商品资料',inventory:'入库与库存',orders:'出库订单',logistics:'物流跟踪'};
const escapeHtml=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time=v=>v?new Date(v).toLocaleString('zh-CN',{hour12:false}):'';
let selectedShipment=null;
function notice(text,error=false){$('#notice').textContent=text;$('#notice').classList.toggle('error',error)}
async function api(path,body){const response=await fetch('/api'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(data.message||'请求失败');return data}
function tab(id){document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===id));document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('active',x.dataset.tab===id));$('#title').textContent=titles[id]}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>tab(b.dataset.go));
function table(id,headers,rows){$(id).innerHTML=rows.length?'<table><thead><tr>'+headers.map(x=>'<th>'+x+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(x=>'<td>'+x+'</td>').join('')+'</tr>').join('')+'</tbody></table>':'<p class="muted">暂无记录，完成相应操作后将在这里显示。</p>'}
const badge=s=>'<span class="badge '+(['PENDING','WAITING'].includes(s)?'pending':'')+'">'+escapeHtml(names[s]||s)+'</span>';
async function loadStocks(){const id=$('#filter').value;const rows=await api('/stocks'+(id?'?productId='+id:''));table('#stocks',['商品编号','商品名称','货位','库存数量','单位'],rows.map(r=>[r.CODE,r.NAME,r.LOCATION,r.QUANTITY,r.UNIT].map(escapeHtml)))}
async function refresh(){
 const [products,locations,stocks,inbounds,orders,shipments,events]=await Promise.all(['/products','/locations','/stocks','/inbounds','/orders','/shipments','/events'].map(p=>api(p)));
 document.querySelectorAll('.product-select').forEach(select=>{const old=select.value;select.innerHTML='<option value="">'+(select.id==='filter'?'全部商品':'请选择商品')+'</option>'+products.map(p=>'<option value="'+p.ID+'">'+escapeHtml(p.NAME+' · '+p.CODE)+'</option>').join('');select.value=old});
 document.querySelectorAll('.location-select').forEach(select=>{const old=select.value;select.innerHTML=locations.map(l=>'<option value="'+l.ID+'">'+escapeHtml(l.CODE)+'</option>').join('');if(old)select.value=old});
 table('#products',['编号','商品名称','单位'],products.map(p=>[p.CODE,p.NAME,p.UNIT].map(escapeHtml)));
 table('#inbounds',['入库单号','商品','货位','数量','时间'],inbounds.map(r=>[r.ID,r.NAME,r.LOCATION,r.QUANTITY,time(r.CREATED_AT)].map(escapeHtml)));
 table('#ordersList',['订单号','商品','货位','数量','状态','操作'],orders.map(o=>[o.ID,escapeHtml(o.NAME),escapeHtml(o.LOCATION),o.QUANTITY,badge(o.STATUS),o.STATUS==='PENDING'?'<button data-ship="'+o.ID+'">确认出库</button>':'已完成']));
 table('#shipments',['物流单号','订单号','商品','数量','状态','操作'],shipments.map(s=>[s.ID,s.ORDER_ID,escapeHtml(s.NAME),s.QUANTITY,badge(s.STATUS),'<button class="secondary" data-track="'+s.ID+'">查看轨迹</button>'+(s.STATUS==='DELIVERED'?'':'<button data-advance="'+s.ID+'" data-status="'+(s.STATUS==='WAITING'?'TRANSIT':'DELIVERED')+'">'+(s.STATUS==='WAITING'?'模拟运输中':'模拟已签收')+'</button>')]));
 table('#events',['事件','业务单号','时间'],events.slice(-6).reverse().map(e=>[escapeHtml(names[e.EVENT_TYPE]||e.EVENT_TYPE),e.AGGREGATE_ID,escapeHtml(time(e.CREATED_AT))]));
 $('#stats').innerHTML=[['商品种类',products.length],['库存总件数',stocks.reduce((n,s)=>n+s.QUANTITY,0)],['待出库订单',orders.filter(o=>o.STATUS==='PENDING').length],['运输中物流',shipments.filter(s=>s.STATUS==='TRANSIT').length]].map(([title,value])=>'<div class="stat"><span>'+title+'</span><strong>'+value+'</strong></div>').join('');
 await loadStocks();if(selectedShipment)await tracking(selectedShipment);
}
async function tracking(id){const rows=await api('/shipments/'+id+'/tracking');selectedShipment=id;$('#trackingTitle').textContent='物流单 #'+id+' 的轨迹';$('#tracking').innerHTML=rows.map(r=>'<div class="track"><strong>'+escapeHtml(names[r.STATUS])+'</strong>'+escapeHtml(time(r.CREATED_AT))+'</div>').join('')}
async function run(button,action,message){button.disabled=true;try{await action();notice(message);try{await refresh()}catch(e){notice(message+'；刷新失败，请点击刷新数据核对结果，勿重复提交。',true)}}catch(e){notice(e.message,true)}finally{button.disabled=false}}
for(const [form,path] of [['productForm','/products'],['inboundForm','/inbounds'],['orderForm','/orders']])$('#'+form).onsubmit=e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));if(form!=='productForm')for(const key of Object.keys(data))data[key]=Number(data[key]);run(e.target.querySelector('button'),()=>api(path,data),form==='orderForm'?'订单已创建，库存尚未扣减':'保存成功')};
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.ship)run(b,()=>api('/orders/'+b.dataset.ship+'/ship',{}),'出库成功，物流单已生成');if(b.dataset.advance)run(b,()=>api('/shipments/'+b.dataset.advance+'/advance',{status:b.dataset.status}),'物流状态更新成功');if(b.dataset.track)tracking(b.dataset.track).catch(e=>notice(e.message,true))});
$('#filter').onchange=()=>loadStocks().catch(e=>notice(e.message,true));$('#refresh').onclick=()=>refresh().then(()=>notice('已获取最新数据库记录')).catch(e=>notice(e.message,true));refresh().then(()=>notice('仓库已连接，可以开始作业。')).catch(e=>notice('连接失败：'+e.message,true));
