// ==================== ASPIRE TRADE FRONTEND ====================
const apiUrl = "http://89.23.98.206:8080/api/latest_full.json";
const refreshInterval = 5000; // автообновление каждые 5 секунд

async function loadData() {
  try {
    const res = await fetch(apiUrl + "?t=" + Date.now()); // чтобы не кэшировалось
    const data = await res.json();

    if (!data) {
      console.error("❌ Нет данных от API");
      return;
    }

    // === СИГНАЛ ===
    const signalBox = document.getElementById("signal-box");
    if (data.signal && !data.signal.error) {
      signalBox.innerHTML = `
        <h3>📊 Текущий сигнал</h3>
        <p><b>Пара:</b> ${data.signal.pair || "?"}</p>
        <p><b>Направление:</b> <span class="${data.signal.direction === "BUY" ? "buy" : "sell"}">${data.signal.direction}</span></p>
        <p><b>Уверенность:</b> ${data.signal.confidence || "?"}/10</p>
        <p><b>Источник:</b> ${data.signal.source || "?"}</p>
      `;
    } else {
      signalBox.innerHTML = `<h3>📊 Текущий сигнал</h3><p>Нет активного сигнала</p>`;
    }

    // === РЕЗУЛЬТАТ ===
    const resultBox = document.getElementById("result-box");
    if (data.result && !data.result.error) {
      resultBox.innerHTML = `
        <h3>📈 Последний результат</h3>
        <p><b>Пара:</b> ${data.result.pair || "?"}</p>
        <p><b>Результат:</b> <span class="${data.result.result === "WIN" ? "win" : "loss"}">${data.result.result}</span></p>
        <p><b>Вход:</b> ${data.result.entry_price?.toFixed?.(5) || "?"}</p>
        <p><b>Выход:</b> ${data.result.exit_price?.toFixed?.(5) || "?"}</p>
      `;
    } else {
      resultBox.innerHTML = `<h3>📈 Последний результат</h3><p>Нет завершённых сделок</p>`;
    }

    // === СТАТИСТИКА ===
    const systemBox = document.getElementById("system-box");
    if (data.system) {
      systemBox.innerHTML = `
        <h3>⚙️ Состояние системы</h3>
        <p><b>Активных пользователей:</b> ${data.system.active_users}</p>
        <p><b>Сделок:</b> ${data.system.total_trades}</p>
        <p><b>Win Rate:</b> ${data.system.win_rate}%</p>
        <p><b>ML Точность:</b> ${data.system.ml_accuracy}%</p>
      `;
    }

    // === ГРАФИК ===
    const chartBox = document.getElementById("chart-box");
    if (data.chart_base64) {
      chartBox.innerHTML = `<img src="${data.chart_base64}" alt="Chart" class="chart-img" />`;
    } else {
      chartBox.innerHTML = `<p>График пока недоступен</p>`;
    }

  } catch (err) {
    console.error("Ошибка загрузки API:", err);
  }
}

// === АВТО-ОБНОВЛЕНИЕ ===
setInterval(loadData, refreshInterval);
window.addEventListener("load", loadData);
