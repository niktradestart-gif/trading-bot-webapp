// Основная логика трейдинг интерфейса
class TradingApp {
    constructor() {
        this.currentUser = null;
        this.activeTrade = null;
        this.chart = null;
        this.init();
    }

    async init() {
        await this.checkAuth();
        await this.loadUserData();
        this.initCharts();
        this.setupEventListeners();
        this.loadActiveSignals();
        this.startTimers();
    }

    async checkAuth() {
        const userId = localStorage.getItem('pocket_user_id');
        if (!userId) {
            window.location.href = 'index.html';
            return;
        }
        this.currentUser = {
            id: userId,
            name: localStorage.getItem('pocket_user_name'),
            role: localStorage.getItem('pocket_user_role')
        };
        document.getElementById('userName').textContent = this.currentUser.name;
    }

    async loadUserData() {
        // Загрузка статистики
        await this.loadStatistics();
        // Загрузка истории
        await this.loadTradeHistory();
    }

    initCharts() {
        // Основной торговый график
        this.initTradingChart();
        // Графики для статистики
        this.initPerformanceChart();
        this.initPairsChart();
    }

    initTradingChart() {
        const ctx = document.getElementById('tradingChart').getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['10:20', '14:10', '12:10', '12:30', '13:10', '14:30'],
                datasets: [{
                    label: 'USDCHF',
                    data: [0.80125, 0.80075, 0.80050, 0.80025, 0.80000, 0.79975],
                    borderColor: '#ff4444',
                    backgroundColor: 'rgba(255, 68, 68, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.1)' } },
                    y: { grid: { color: 'rgba(255,255,255,0.1)' } }
                }
            }
        });
    }

    async loadActiveSignals() {
        try {
            // Запрос к боту для получения активных сигналов
            const payload = JSON.stringify({
                action: 'get_active_signals',
                user_id: this.currentUser.id
            });
            tg.sendData(payload);
            
            // Имитация получения сигнала
            this.updateActiveSignal({
                pair: 'USDCHF',
                direction: 'SELL',
                confidence: 6,
                entryPrice: 0.52550,
                expiration: 2
            });
            
        } catch (error) {
            console.error('Ошибка загрузки сигналов:', error);
        }
    }

    updateActiveSignal(signal) {
        this.activeTrade = signal;
        document.querySelector('.current-signal h3').textContent = 
            `${signal.pair} - Smart Money Analysis - ${signal.direction}`;
        document.querySelector('.signal-confidence span:first-child').textContent = 
            `${signal.confidence}/10`;
        document.querySelector('.detail-item .value').textContent = signal.entryPrice;
        this.startTradeTimer(signal.expiration);
    }

    startTradeTimer(minutes) {
        let timeLeft = minutes * 60;
        const timerElement = document.getElementById('tradeTimer');
        
        const timer = setInterval(() => {
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            timerElement.textContent = 
                `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            
            if (timeLeft <= 0) {
                clearInterval(timer);
                this.tradeExpired();
            }
            timeLeft--;
        }, 1000);
    }

    async executeTrade(direction) {
        if (!this.activeTrade) return;
        
        const tradeData = {
            action: 'execute_trade',
            user_id: this.currentUser.id,
            pair: this.activeTrade.pair,
            direction: direction,
            entry_price: this.activeTrade.entryPrice
        };
        
        tg.sendData(JSON.stringify(tradeData));
        
        // Показ результата
        this.showTradeResult(direction);
    }

    setupEventListeners() {
        // Навигация по вкладкам
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tabName = e.target.dataset.tab;
                this.switchTab(tabName);
            });
        });

        // Фильтры истории
        document.getElementById('timeFilter').addEventListener('change', () => {
            this.loadTradeHistory();
        });
    }

    switchTab(tabName) {
        // Скрыть все вкладки
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.remove('active');
        });
        // Убрать активный класс у кнопок
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        // Показать выбранную вкладку
        document.getElementById(`${tabName}-tab`).classList.add('active');
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    }

    logout() {
        localStorage.clear();
        window.location.href = 'index.html';
    }
}

// Запуск приложения
const tradingApp = new TradingApp();
