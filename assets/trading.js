// Minimal front-end runtime for ASPIRE WebApp
const Aspire = (() => {
const state = {
whitelist: [],
whitelistMap: {},
pocketId: null,
isAdmin: false,
polling: null,
};
const paths = {
whitelist: 'pocket_users.json',
10
lastSignal: 'last_signal.json', // создаётся ботом при новом
сигнале
lastResult: 'last_result.json', // создаётся ботом при закрытии
сделки
mlInfo: 'ml_info.json', // бот обновляет после /retrain
system: 'system_status.json', // бот обновляет по /status
chartPng: 'assets/images/latest_chart.png', // бот экспортирует PNG из
enhanced_plot_chart()
};
// ---------- helpers ----------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
function toast(msg, type='info'){ const t=$('#toast'); if(!t) return;
t.textContent=msg; t.className='toast';
setTimeout(()=>t.classList.add('hidden'), 3000); }
async function fetchJSON(url){
try{ const r = await fetch(url + '?_=' + Date.now()); if(!r.ok) return {
ok:false, data:null }; const d = await r.json(); return { ok:true, data:d } }
catch{ return { ok:false, data:null } }
}
// ---------- whitelist ----------
async function fetchWhitelist(){
const res = await fetchJSON(paths.whitelist);
if(!res.ok){ return { ok:false, list:[], map:{} } }
// file is in object form { id: {name, role, ...}, ... }
const map = res.data || {};
const list = Object.entries(map).map(([id, obj])=>({ id, ...obj }));
state.whitelist = list; state.whitelistMap = map;
return { ok:true, list, map };
}
function requireAuth(){
const id = localStorage.getItem('pocketId');
if(!id){ location.href = 'login.html'; return }
state.pocketId = id;
}
async function requireAdmin(){
const id = localStorage.getItem('pocketId');
if(!id) return location.href='login.html';
state.pocketId = id;
const wl = await fetchWhitelist();
const u = wl.map[id];
state.isAdmin = !!u && (u.role === 'admin');
if(!state.isAdmin){ toast('Требуются права администратора'); return
location.href='trading.html' }
}
11
// ---------- trading page ----------
function renderSignal(sig, target){
if(!sig){ target.innerHTML = '<div class="muted">Нет активных сигналов</
div>'; return; }
const badge = sig.direction === 'SELL' ? 'badge badge-sell' : 'badge
badge-buy';
target.innerHTML = `
 <div class="pair">${sig.pair}</div>
 <div><span class="${badge}">${sig.direction}</span></div>
 <div><span class="badge badge-conf">${sig.confidence ?? '-'} / 10</
span></div>
 <div><div class="muted">ID</div>#${sig.id ?? '—'}</div>
 <div><div class="muted">ВХОД</div>${sig.entry_price ?? '—'}</div>
 <div><div class="muted">Экспирация</div>${sig.expiry ?? '—'}</div>
 `;
}
let countdownInt = null;
function startTimer(seconds){
const el = $('#signalTimer'); if(!el) return;
clearInterval(countdownInt);
let t = Number(seconds)||0;
const tick = ()=>{ const m=String(Math.floor(t/60)).padStart(2,'0');
const s=String(t%60).padStart(2,'0'); el.textContent=`${m}:${s}`; if(t>0)
t--; else clearInterval(countdownInt); };
tick(); countdownInt = setInterval(tick,1000);
}
async function loadKPIs(){
const sR = await fetchJSON(paths.system);
if(sR.ok){
$('#botStatus')?.classList.add('pill-online');
$('#kpi-servertime').textContent = sR.data.server_time ?? '—';
$('#kpi-accuracy').textContent = sR.data.accuracy_today ?? '—';
$('#kpi-active').textContent = sR.data.active_signals ?? '—';
$('#kpi-botstate').className = sR.data.bot_online ? 'dot dot-green' :
'dot';
}
}
async function loadHistory(){
const r = await fetchJSON('last_history.json'); // опционально, если бот
пишет историй
if(!r.ok || !Array.isArray(r.data)) return;
const box = $('#history');
box.innerHTML = r.data.slice(-6).reverse().map(item=>{
const cls = item.result === 'WIN' ? 'win' : 'loss';
return `<div class="hist-item"><div class="muted">#${item.id} • $
{item.pair}</div><div class="result ${cls}">${item.result}</div><div
class="muted">${item.timestamp ?? ''}</div></div>`
12
}).join('');
}
async function pollSignal(){
const res = await fetchJSON(paths.lastSignal);
const wrap = $('#signalWrap');
if(res.ok){
const sig = res.data; renderSignal(sig, wrap);
const ttl = Number(sig.time_left_sec ?? 0); if(ttl>0) startTimer(ttl);
$('#chartImg')?.setAttribute('src', paths.chartPng + '?_=' +
Date.now());
}
const rr = await fetchJSON(paths.lastResult);
if(rr.ok && rr.data?.result){ toast(`Сделка #${rr.data.id} завершена: $
{rr.data.result}`); loadHistory(); }
}
function initTrading(){
$('#btnLogout')?.addEventListener('click', ()=>{
localStorage.removeItem('pocketId'); location.href='login.html'; });
loadKPIs(); pollSignal(); loadHistory();
state.polling = setInterval(()=>{ pollSignal(); loadKPIs(); }, 15000);
}
// ---------- admin page ----------
function wireTabs(){
$$('.tab').forEach(t=>t.addEventListener('click',()=>{
$$('.tab').forEach(x=>x.classList.remove('active'));
t.classList.add('active');
const id = t.getAttribute('data-tab');
$$('.tab-page').forEach(p=>p.classList.remove('active'));
$('#tab-' + id).classList.add('active');
}));
$$('.feature.card').forEach(f=>f.addEventListener('click',()=>{
const act = f.getAttribute('data-action');
const mapping = { users:'users', ml:'ml', analytics:'analytics',
system:'system' };
const tab = mapping[act] || 'overview';
$$(`.tabs .tab`).forEach(x=> x.classList.toggle('active',
x.dataset.tab===tab));
$$('.tab-page').forEach(p=>p.classList.remove('active'));
$('#tab-'+tab).classList.add('active');
}));
}
function renderUsers(){
const box = $('#users-list');
if(!box) return;
box.innerHTML = state.whitelist.map(u=>`
 <div class="user-row">
13
 <div>
 <div><strong>${u.name ?? 'User'}</strong> <span class="meta">• $
{u.role ?? 'user'}</span></div>
 <div class="meta">ID: ${u.id} • ${u.status ?? 'active'}</div>
 </div>
 <div>
 <button class="btn" data-del="${u.id}">Удалить</button>
 </div>
 </div>
 `).join('');
box.querySelectorAll('button[data-del]').forEach(b=>
b.addEventListener('click', ()=>{
const id = b.getAttribute('data-del');
delete state.whitelistMap[id];
state.whitelist =
Object.entries(state.whitelistMap).map(([id,obj])=>({ id, ...obj }));
renderUsers();
toast('Удалено из списка');
}));
}
function exportWhitelist(){
const data = JSON.stringify(state.whitelistMap, null, 2);
const blob = new Blob([data], { type:'application/json' });
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url; a.download = 'pocket_users.json'; a.click();
setTimeout(()=> URL.revokeObjectURL(url), 2000);
}
async function loadAdminBlocks(){
// KPIs
const wl = await fetchWhitelist();
$('#ovr-users').textContent = wl.list.length;
const sys = await fetchJSON(paths.system);
if(sys.ok){ $('#ovr-acc').textContent = sys.data.accuracy_all ?? '—'; $
('#ovr-sig').textContent = sys.data.active_signals ?? '—'; }
// ML
const ml = await fetchJSON(paths.mlInfo);
if(ml.ok){ $('#ml-info').innerHTML = `
 <div><strong>Обучена:</strong> ${ml.data.trained_at ?? '—'}</div>
 <div><strong>Сделок:</strong> ${ml.data.trades ?? '—'}</div>
 <div><strong>Точность (тест):</strong> ${ml.data.test_accuracy ?? '—'}
</div>
 <div><strong>Win rate:</strong> ${ml.data.win_rate ?? '—'}</div>`; }
// Signals
const sig = await fetchJSON(paths.lastSignal);
14
if(sig.ok){ renderSignal(sig.data, $('#adm-signal')); }
// Users
renderUsers();
// Logs (заглушка)
$('#ovr-log').innerHTML = [
'<span class="info">[INFO]</span> ML модель переобучена с точностью
61.5%\n',
'<span class="succ">[SUCCESS]</span> Сделка #392 завершена в
прибыль\n',
'<span class="warn">[WARNING]</span> Высокая волатильность AUDCHF\n',
'<span class="err">[ERROR]</span> Ошибка подключения к бирже, повторная
попытка...\n'
].join('');
}
function initAdmin(){
$('#btnLogout')?.addEventListener('click', ()=>{
localStorage.removeItem('pocketId'); location.href='login.html'; });
wireTabs();
fetchWhitelist().then(loadAdminBlocks);
$('#btn-add')?.addEventListener('click', ()=>{
const id = $('#u-id').value.trim();
const name = $('#u-name').value.trim() || 'User';
const role = $('#u-role').value || 'user';
if(!id){ return toast('Укажите Pocket ID','error') }
if(state.whitelistMap[id]){ return toast('Такой ID уже есть','error') }
state.whitelistMap[id] = { name, role, telegram_id:null,
registered_at:new Date().toISOString(), status:'active' };
state.whitelist =
Object.entries(state.whitelistMap).map(([id,obj])=>({ id, ...obj }));
renderUsers();
toast('Пользователь добавлен');
});
$('#btn-export')?.addEventListener('click', exportWhitelist);
// fake command buttons (визуальные): замените на реальные HTTP вызовы
вашего бота
$$('[data-cmd]').forEach(btn=> btn.addEventListener('click', ()=>{
toast('Команда отправлена: ' + btn.dataset.cmd);
}));
}
return {
fetchWhitelist, requireAuth, requireAdmin, initTrading, initAdmin, toast
};
})();
