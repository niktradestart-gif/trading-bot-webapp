const API = "http://89.23.98.206:8080/api";

function logout(){localStorage.clear();window.location.href="login.html";}

// --- Tabs ---
document.addEventListener("click", e=>{
  if(e.target.classList.contains("tab")){
    document.querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));
    e.target.classList.add("active");
    document.querySelectorAll(".tab-content").forEach(c=>c.classList.remove("active"));
    document.getElementById("tab-"+e.target.dataset.tab).classList.add("active");
  }
});

// --- User Panel ---
async function loadSignal(){
  const el=document.getElementById("signalData");
  try{
    const r=await fetch(`${API}/last_signal.json`);
    const d=await r.json();
    if(d.error){el.innerText="Нет активных сигналов";return;}
    el.innerHTML=`<b>${d.pair}</b> — ${d.direction}<br>💰 ${d.entry_price} | ⏱ ${d.expiry}<br>🎯 ${d.confidence}/10 | 🧠 ${d.source}`;
  }catch{el.innerText="Ошибка загрузки сигнала.";}
}

async function loadChart(){
  const img=document.getElementById("chartImg");
  if(img) img.src=`${API}/chart.png?${Date.now()}`;
}

async function loadStats(){
  const el=document.getElementById("statsBox");
  try{
    const r=await fetch(`${API}/system_status.json`);
    const d=await r.json();
    if(d.error){el.innerText="Ошибка";return;}
    el.innerHTML=`Сделок: ${d.total_trades}<br>WinRate: ${d.win_rate}%<br>Пользователей: ${d.active_users}<br>ML: ${d.ml_accuracy}%`;
  }catch{el.innerText="Ошибка";}
}

async function loadResult(){
  const el=document.getElementById("lastResult");
  try{
    const r=await fetch(`${API}/last_result.json`);
    const d=await r.json();
    if(d.error){el.innerText="—";return;}
    el.innerHTML=`${d.pair}: <b>${d.result}</b>`;
  }catch{el.innerText="Ошибка";}
}

async function loadHistory(){
  const tb=document.querySelector("#historyTable tbody");
  tb.innerHTML="<tr><td colspan='5'>Загрузка...</td></tr>";
  // Тестовый вывод — можно потом связать с API истории
  tb.innerHTML=`<tr><td>1</td><td>EURUSD</td><td>BUY</td><td>WIN</td><td>${new Date().toLocaleTimeString()}</td></tr>`;
}

// --- Admin Panel ---
async function loadWhitelist(){const r=await fetch("pocket_users.json");const d=await r.json();document.getElementById("whitelistBox").innerText=JSON.stringify(d,null,2);}
async function addUser(){const id=document.getElementById("newPocket").value.trim();const name=document.getElementById("newName").value.trim();const role=document.getElementById("newRole").value;const r=await fetch("pocket_users.json");const users=await r.json();users[id]={name,role,registered_at:new Date().toISOString(),status:"active"};const blob=new Blob([JSON.stringify(users,null,2)],{type:"application/json"});const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="pocket_users.json";link.click();loadWhitelist();}
async function loadML(){const r=await fetch(`${API}/system_status.json`);const d=await r.json();document.getElementById("mlInfo").innerText="ML Accuracy: "+d.ml_accuracy+"%";}
async function loadSystem(){const r=await fetch(`${API}/system_status.json`);const d=await r.json();document.getElementById("systemBox").innerText=JSON.stringify(d,null,2);}
async function loadSignals(){const r=await fetch(`${API}/last_signal.json`);const d=await r.json();document.getElementById("adminSignals").innerText=JSON.stringify(d,null,2);}
async function loadLogs(){document.getElementById("logBox").innerText="— (пока без логов)";}

setInterval(()=>{
  if(document.getElementById("signalData")){
    loadSignal();loadChart();loadStats();loadResult();loadHistory();
  }
  if(document.getElementById("whitelistBox")){
    loadWhitelist();loadML();loadSystem();loadSignals();loadLogs();
  }
},15000);

window.onload=()=>{
  if(document.getElementById("signalData")){
    loadSignal();loadChart();loadStats();loadResult();loadHistory();
  }
  if(document.getElementById("whitelistBox")){
    loadWhitelist();loadML();loadSystem();loadSignals();loadLogs();
  }
};
