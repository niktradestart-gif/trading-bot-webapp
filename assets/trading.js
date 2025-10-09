// Логика торговой панели
class TradingPanel {
    constructor() {
        this.currentTimer = 89; // 1:29 в секундах
        this.timerInterval = null;
        this.init();
    }

    init() {
        this.checkAuth();
        this.setupWebApp();
        this.startTimer();
        this.setupEventListeners();
    }

    checkAuth() {
        const token = localStorage.getItem('auth_token');
        if (!token) {
            window.location.href = 'login.html';
            return;
        }
    }

    setupWebApp() {
        if (window.Telegram && window.Telegram.WebApp) {
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();
            
            // Устанавливаем цветовую схему
            Telegram.WebApp.setHeaderColor('#1a1a2e');
            Telegram.WebApp.setBackgroundColor('#1a1a2e');
        }
    }

    startTimer() {
        this.timerInterval = setInterval(() => {
            this.currentTimer--;
            
            if (this.currentTimer <= 0) {
                this.timerComplete();
                return;
            }
            
            this.updateTimerDisplay();
        }, 1000);
    }

    updateTimerDisplay() {
        const minutes = Math.floor(this.currentTimer / 60);
        const seconds = this.currentTimer % 60;
        const timerText = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        
        // Обновляем все таймеры на странице
        const timerElements = document.querySelectorAll('.timer');
        timerElements.forEach(element => {
            element.textContent = timerText;
        });
    }

    timerComplete() {
        clearInterval(this.timerInterval);
        
        // Показываем результат сделки
        this.showTradeResult();
    }

    async showTradeResult() {
        // Запрашиваем результат у бота
        try {
            const result = await this.getTradeResult();
            this.displayResult(result);
        } catch (error) {
            console.error('Ошибка получения результата:', error);
        }
    }

    async getTradeResult() {
        // В реальном приложении бот сам пришлет результат
        // Здесь имитируем ответ
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve({
                    success: Math.random() > 0.5,
                    profit: 18,
                    pair: 'AUDCHF',
                    exitPrice: 0.52480
                });
            }, 2000);
        });
    }

    displayResult(result) {
        const statusElement = document.querySelector('.status-message');
        if (statusElement) {
            if (result.success) {
                statusElement.innerHTML = '<span class="icon">🟢</span> СДЕЛКА ВЫИГРАНА +' + result.profit + '$';
                statusElement.style.color = '#00ff88';
            } else {
                statusElement.innerHTML = '<span class="icon">🔴</span> СДЕЛКА ПРОИГРАНА';
                statusElement.style.color = '#ff4444';
            }
        }

        // Через 5 секунд обновляем данные
        setTimeout(() => {
            this.refreshData();
        }, 5000);
    }

    async refreshData() {
        // Обновляем данные через бота
        if (window.Telegram && window.Telegram.WebApp) {
            Telegram.WebApp.sendData(JSON.stringify({
                action: 'get_signal'
            }));
        }
        
        // Сбрасываем таймер для нового сигнала
        this.resetTimer();
    }

    resetTimer() {
        this.currentTimer = 120; // 2 минуты
        const statusElement = document.querySelector('.status-message');
        if (statusElement) {
            statusElement.innerHTML = '<span class="icon">☒</span> ОЖИДАНИЕ РЕЗУЛЬТАТА';
            statusElement.style.color = '#ffffff';
        }
        this.startTimer();
    }

    setupEventListeners() {
        // Обработчики для будущих интерактивных элементов
    }

    // Получение новых данных от бота
    handleBotMessage(data) {
        switch (data.type) {
            case 'new_signal':
                this.updateSignal(data.signal);
                break;
            case 'trade_result':
                this.displayResult(data.result);
                break;
            case 'update_stats':
                this.updateStats(data.stats);
                break;
        }
    }

    updateSignal(signal) {
        // Обновляем данные сигнала на странице
        const pairElement = document.querySelector('.pair');
        const directionElement = document.querySelector('.direction');
        const confidenceElement = document.querySelector('.confidence');
        const priceElement = document.querySelector('.detail-item:nth-child(2) .value');

        if (pairElement) pairElement.textContent = signal.pair;
        if (directionElement) {
            directionElement.textContent = signal.direction;
            directionElement.className = `direction ${signal.direction.toLowerCase()}`;
        }
        if (confidenceElement) confidenceElement.textContent = signal.confidence;
        if (priceElement) priceElement.textContent = signal.entry_price;

        // Сбрасываем таймер
        this.resetTimer();
    }

    updateStats(stats) {
        // Обновляем статистику
        const statValues = document.querySelectorAll('.stat-value');
        if (statValues[0]) statValues[0].textContent = stats.accuracy + '%';
        if (statValues[1]) statValues[1].textContent = stats.active_signals;
        // и т.д.
    }
}

// Инициализация торговой панели
document.addEventListener('DOMContentLoaded', () => {
    window.tradingPanel = new TradingPanel();
});

// Глобальная функция для получения сообщений от бота
window.handleTelegramUpdate = function(data) {
    if (window.tradingPanel) {
        window.tradingPanel.handleBotMessage(data);
    }
};
