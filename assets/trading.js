const API = "http://127.0.0.1:8080/api";

function logout(){localStorage.clear();window.location.href="login.html";}

// ---- Tabs ----
document.addEventListener("click", e=>{
  if(e.target.classList.contains("tab")){
    document.querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));
    e.target.classList.add("active");
    document.querySelectorAll(".tab-content").forEach(c=>c.classList.remove("active"));
    document.getElementById("tab-"+e.target.dataset.tab).classList.add("active");
  }
});

// ---- Trader ----
async function loadSignal(){
  try{
    const r=await fetch(`${API}/last_signal.json`);const d=await r.json();
    const el=document.getElementById("signalData");
    if(d.error) return el.innerHTML="Нет активных сигналов";
    el.innerHTML=`<b>${d.pair}</b> — ${d.direction}<br>💰 ${d.entry_price} | ⏱ ${d.expiry}<br>🎯 ${d.confidence}/10 | 🧠 ${d.source}`;
  }catch{document.getElementById("signalData").innerText="Ошибка";}
}
async function loadChart(){const img=document.getElementById("chartImg");if(img)img.src=`${API}/chart.png?${Date.now()}`;}
async function loadResult(){const r=await fetch(`${API}/last_result.json`);const d=await r.json();document.getElementById("lastResult").innerHTML=d.error?"—":`${d.pair}: <b>${d.result}</b>`;}
async function loadStats(){const r=await fetch(`${API}/system_status.json`);const d=await r.json();const el=document.getElementById("statsBox");if(!el)return;if(d.error)return el.innerText="—";el.innerHTML=`Сделок: ${d.total_trades}<br>WinRate: ${d.win_rate}%<br>Пользователей: ${d.active_users}<br>ML: ${d.ml_accuracy}%`; }
async function loadHistory(){try{const r=await fetch("trade_history.json");const d=await r.json();const tb=document.querySelector("#historyTable tbody");tb.innerHTML="";d.slice(-10).reverse().forEach((t,i)=>{tb.innerHTML+=`<tr><td>${i+1}</td><td>${t.pair}</td><td>${t.direction}</td><td>${t.result}</td><td>${t.time}</td></tr>`});}catch{}}

// ---- Admin ----
async function loadWhitelist(){const r=await fetch("pocket_users.json");const d=await r.json();document.getElementById("whitelistBox").innerText=JSON.stringify(d,null,2);}
async function addUser(){const id=document.getElementById("newPocket").value.trim();const name=document.getElementById("newName").value.trim();const role=document.getElementById("newRole").value;const r=await fetch("pocket_users.json");const users=await r.json();users[id]={name,role,registered_at:new Date().toISOString(),status:"active"};const blob=new Blob([JSON.stringify(users,null,2)],{type:"application/json"});const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="pocket_users.json";link.click();loadWhitelist();}
async function loadML(){const r=await fetch(`${API}/ml_info.json`);const d=await r.json();document.getElementById("mlInfo").innerText=JSON.stringify(d,null,2);}
async function loadSystem(){const r=await fetch(`${API}/system_status.json`);const d=await r.json();document.getElementById("systemBox").innerText=JSON.stringify(d,null,2);}
async function loadSignals(){const r=await fetch(`${API}/last_signal.json`);const d=await r.json();document.getElementById("adminSignals").innerText=JSON.stringify(d,null,2);}
async function loadLogs(){try{const r=await fetch("system_log.json");if(!r.ok)return;const t=await r.text();document.getElementById("logBox").innerText=t.slice(-3000);}catch{}}
function sendCommand(cmd){alert(`📡 Команда '${cmd}' отправлена боту (через Telegram)`);}

setInterval(()=>{if(document.getElementById("signalData")){loadSignal();loadChart();loadResult();loadStats();loadHistory();}
if(document.getElementById("whitelistBox")){loadWhitelist();loadML();loadSystem();loadSignals();loadLogs();}},15000);

window.onload=()=>{if(document.getElementById("signalData")){loadSignal();loadChart();loadResult();loadStats();loadHistory();}
if(document.getElementById("whitelistBox")){loadWhitelist();loadML();loadSystem();loadSignals();loadLogs();}};
