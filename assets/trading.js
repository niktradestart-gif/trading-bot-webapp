// =============================
// 🌐 ASPIRE TRADE WebApp Logic
// =============================

// --- Конфигурация API (VPS IP)
const API = "http://89.23.98.206:8080/api";

// --- Logout
function logout() {
  localStorage.clear();
  window.location.href = "login.html";
}

// =============================
// 🧭 Навигация по вкладкам
// =============================
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("tab")) {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    e.target.classList.add("active");

    document.querySelectorAll(".tab-content").forEach((c) =>
      c.classList.remove("active")
    );
    const tab = e.target.dataset.tab;
    const target = document.getElementById("tab-" + tab);
    if (target) target.classList.add("active");
  }
});

// =============================
// 📈 TRADER PANEL
// =============================
async function loadSignal() {
  const el = document.getElementById("signalData");
  if (!el) return;
  try {
    const r = await fetch(`${API}/last_signal.json`);
    const d = await r.json();

    if (d.error) {
      el.innerHTML = "⚠️ Нет активных сигналов";
      return;
    }

    el.innerHTML = `
      <b>${d.pair || "-"}</b> — ${d.direction || "-"}<br>
      💰 <b>${d.entry_price || "-"}</b> | ⏱ ${d.expiry || "-"}<br>
      🎯 Уверенность: ${d.confidence || "?"}/10<br>
      🧠 Источник: ${d.source || "N/A"}
    `;
  } catch (e) {
    el.innerText = "Ошибка загрузки сигнала.";
  }
}

async function loadChart() {
  const img = document.getElementById("chartImg");
  if (!img) return;
  img.src = `${API}/chart.png?${Date.now()}`;
}

async function loadResult() {
  const el = document.getElementById("lastResult");
  if (!el) return;
  try {
    const r = await fetch(`${API}/last_result.json`);
    const d = await r.json();
    el.innerHTML = d.error ? "—" : `${d.pair}: <b>${d.result}</b>`;
  } catch {
    el.innerText = "Ошибка";
  }
}

async function loadStats() {
  const el = document.getElementById("statsBox");
  if (!el) return;
  try {
    const r = await fetch(`${API}/system_status.json`);
    const d = await r.json();

    if (d.error) {
      el.innerText = "Нет данных";
      return;
    }

    el.innerHTML = `
      📊 Сделок: <b>${d.total_trades || 0}</b><br>
      🎯 WinRate: <b>${d.win_rate || 0}%</b><br>
      👥 Пользователей: <b>${d.active_users || 0}</b><br>
      🤖 ML точность: <b>${d.ml_accuracy || 0}%</b>
    `;
  } catch {
    el.innerText = "Ошибка";
  }
}

async function loadHistory() {
  const table = document.querySelector("#historyTable tbody");
  if (!table) return;
  try {
    const r = await fetch("trade_history.json");
    const d = await r.json();
    table.innerHTML = "";
    d.slice(-10).reverse().forEach((t, i) => {
      table.innerHTML += `
        <tr>
          <td>${i + 1}</td>
          <td>${t.pair}</td>
          <td>${t.direction}</td>
          <td>${t.result}</td>
          <td>${t.time}</td>
        </tr>
      `;
    });
  } catch {
    table.innerHTML = "<tr><td colspan='5'>Нет истории</td></tr>";
  }
}

// =============================
// 🧑‍💼 ADMIN PANEL
// =============================
async function loadWhitelist() {
  const el = document.getElementById("whitelistBox");
  if (!el) return;
  try {
    const r = await fetch("pocket_users.json");
    const d = await r.json();
    el.innerText = JSON.stringify(d, null, 2);
  } catch {
    el.innerText = "Ошибка загрузки списка пользователей.";
  }
}

async function addUser() {
  const id = document.getElementById("newPocket").value.trim();
  const name = document.getElementById("newName").value.trim();
  const role = document.getElementById("newRole").value;

  if (!id || !name) return alert("Заполните все поля!");

  try {
    const r = await fetch("pocket_users.json");
    const users = await r.json();

    users[id] = {
      name,
      role,
      registered_at: new Date().toISOString(),
      status: "active",
    };

    const blob = new Blob([JSON.stringify(users, null, 2)], {
      type: "application/json",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "pocket_users.json";
    link.click();

    loadWhitelist();
  } catch (e) {
    alert("Ошибка при добавлении пользователя.");
  }
}

async function loadML() {
  const el = document.getElementById("mlInfo");
  if (!el) return;
  try {
    const r = await fetch(`${API}/ml_info.json`);
    const d = await r.json();
    el.innerText = JSON.stringify(d, null, 2);
  } catch {
    el.innerText = "Ошибка загрузки ML данных.";
  }
}

async function loadSystem() {
  const el = document.getElementById("systemBox");
  if (!el) return;
  try {
    const r = await fetch(`${API}/system_status.json`);
    const d = await r.json();
    el.innerText = JSON.stringify(d, null, 2);
  } catch {
    el.innerText = "Ошибка загрузки статуса.";
  }
}

async function loadSignals() {
  const el = document.getElementById("adminSignals");
  if (!el) return;
  try {
    const r = await fetch(`${API}/last_signal.json`);
    const d = await r.json();
    el.innerText = JSON.stringify(d, null, 2);
  } catch {
    el.innerText = "Ошибка загрузки сигналов.";
  }
}

async function loadLogs() {
  const el = document.getElementById("logBox");
  if (!el) return;
  try {
    const r = await fetch("system_log.json");
    if (!r.ok) return;
    const text = await r.text();
    el.innerText = text.slice(-3000);
  } catch {
    el.innerText = "Ошибка загрузки логов.";
  }
}

function sendCommand(cmd) {
  alert(`📡 Команда '${cmd}' отправлена боту (через Telegram)`);
}

// =============================
// ⏱️ Автообновление интерфейса
// =============================
setInterval(() => {
  if (document.getElementById("signalData")) {
    loadSignal();
    loadChart();
    loadResult();
    loadStats();
    loadHistory();
  }
  if (document.getElementById("whitelistBox")) {
    loadWhitelist();
    loadML();
    loadSystem();
    loadSignals();
    loadLogs();
  }
}, 15000);

// Первичная загрузка
window.onload = () => {
  if (document.getElementById("signalData")) {
    loadSignal();
    loadChart();
    loadResult();
    loadStats();
    loadHistory();
  }
  if (document.getElementById("whitelistBox")) {
    loadWhitelist();
    loadML();
    loadSystem();
    loadSignals();
    loadLogs();
  }
};
