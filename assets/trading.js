const API = "http://127.0.0.1:8080/api";

async function loadSignal() {
  try {
    const res = await fetch(`${API}/last_signal.json`);
    const data = await res.json();
    const div = document.getElementById("signalData");
    if (data.error) return (div.innerHTML = "Нет активных сигналов");
    div.innerHTML = `
      💼 <b>${data.pair}</b> — ${data.direction}<br>
      💰 Вход: ${data.entry_price}<br>
      ⏱ Экспирация: ${data.expiry}<br>
      🎯 Уверенность: ${data.confidence}/10<br>
      🧠 Источник: ${data.source}
    `;
  } catch {
    document.getElementById("signalData").innerText = "Ошибка загрузки";
  }
}

async function loadChart() {
  const chart = document.getElementById("chartImg");
  if (chart) chart.src = `${API}/chart.png?${Date.now()}`;
}

async function loadResult() {
  const r = await fetch(`${API}/last_result.json`);
  const d = await r.json();
  const div = document.getElementById("lastResult");
  if (d.error) return (div.innerText = "Нет данных");
  div.innerHTML = `Пара: ${d.pair}<br>Результат: <b>${d.result}</b>`;
}

async function loadStats() {
  const s = await fetch(`${API}/system_status.json`);
  const d = await s.json();
  const div = document.getElementById("statsBox");
  if (d.error) return (div.innerText = "—");
  div.innerHTML = `
    Всего сделок: ${d.total_trades}<br>
    WinRate: ${d.win_rate}%<br>
    Активные пользователи: ${d.active_users}<br>
    ML: ${d.ml_accuracy}%
  `;
}

async function loadHistory() {
  const r = await fetch("trade_history.json");
  const data = await r.json();
  const tbody = document.querySelector("#historyTable tbody");
  tbody.innerHTML = "";
  data.slice(-10).reverse().forEach((t, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${i + 1}</td><td>${t.pair}</td><td>${t.direction}</td><td>${t.result}</td><td>${t.time}</td>`;
    tbody.appendChild(tr);
  });
}

async function loadWhitelist() {
  const res = await fetch("pocket_users.json");
  const data = await res.json();
  document.getElementById("whitelistBox").innerText = JSON.stringify(data, null, 2);
}

async function addUser() {
  const id = document.getElementById("newPocket").value.trim();
  const name = document.getElementById("newName").value.trim();
  const role = document.getElementById("newRole").value;
  const res = await fetch("pocket_users.json");
  const users = await res.json();
  users[id] = { name, role, registered_at: new Date().toISOString(), status: "active" };
  const blob = new Blob([JSON.stringify(users, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "pocket_users.json";
  link.click();
  document.getElementById("adminMsg").innerText = "✅ Файл обновлён и скачан. Загрузите его на сервер.";
  loadWhitelist();
}

async function loadML() {
  const r = await fetch(`${API}/ml_info.json`);
  const d = await r.json();
  document.getElementById("mlInfo").innerText = JSON.stringify(d, null, 2);
}

async function loadAdminSignals() {
  const s = await fetch(`${API}/last_signal.json`);
  const d = await s.json();
  document.getElementById("adminSignals").innerText = JSON.stringify(d, null, 2);
}

async function loadLogs() {
  const res = await fetch("system_log.json");
  if (!res.ok) return;
  const text = await res.text();
  document.getElementById("logBox").innerText = text.slice(-3000);
}

function logout() {
  localStorage.clear();
  window.location.href = "login.html";
}

function sendCommand(cmd) {
  alert(`📡 Команда '${cmd}' отправлена через Telegram бот`);
}

setInterval(() => {
  if (document.getElementById("signalData")) {
    loadSignal(); loadChart(); loadResult(); loadStats(); loadHistory();
  }
  if (document.getElementById("whitelistBox")) {
    loadWhitelist(); loadML(); loadAdminSignals(); loadLogs();
  }
}, 15000);

window.onload = () => {
  if (document.getElementById("signalData")) {
    loadSignal(); loadChart(); loadResult(); loadStats(); loadHistory();
  }
  if (document.getElementById("whitelistBox")) {
    loadWhitelist(); loadML(); loadAdminSignals(); loadLogs();
  }
};
