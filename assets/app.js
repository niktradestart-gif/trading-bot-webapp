// Базовая логика приложения
class TradingApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkAuthentication();
    }

    setupEventListeners() {
        // Логин форма
        const loginBtn = document.getElementById('loginBtn');
        if (loginBtn) {
            loginBtn.addEventListener('click', () => this.handleLogin());
        }

        // Демо доступы
        const demoAccounts = document.querySelectorAll('input[name="demoAccount"]');
        demoAccounts.forEach(radio => {
            radio.addEventListener('change', (e) => this.handleDemoAccount(e.target.value));
        });
    }

    checkAuthentication() {
        // Проверяем, авторизован ли пользователь
        const token = localStorage.getItem('auth_token');
        if (token && window.location.pathname.includes('login.html')) {
            // Если уже авторизован, перенаправляем на торговую панель
            this.redirectToTrading();
        }
    }

    async handleLogin() {
        const pocketId = document.getElementById('pocketId').value.trim();
        const isConfirmed = document.getElementById('confirmId').checked;

        if (!pocketId) {
            this.showError('Введите ваш Pocket ID');
            return;
        }

        if (!isConfirmed) {
            this.showError('Подтвердите ваш ID');
            return;
        }

        // Показываем загрузку
        this.showLoading();

        try {
            // Проверяем Pocket ID через Telegram Web App
            if (window.Telegram && window.Telegram.WebApp) {
                const result = await this.verifyPocketId(pocketId);
                
                if (result.success) {
                    this.loginSuccess(result.user);
                } else {
                    this.showError(result.message);
                }
            } else {
                // Режим тестирования (без Telegram)
                this.testLogin(pocketId);
            }
        } catch (error) {
            this.showError('Ошибка подключения: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    async verifyPocketId(pocketId) {
        // Отправляем данные в бота через Telegram Web App
        if (window.Telegram && window.Telegram.WebApp) {
            return new Promise((resolve) => {
                window.Telegram.WebApp.sendData(JSON.stringify({
                    action: 'check_pocket_id',
                    pocket_id: pocketId,
                    telegram_id: window.Telegram.WebApp.initDataUnsafe.user?.id
                }));
                
                // В реальном приложении бот ответит через callback
                setTimeout(() => {
                    resolve({ success: true, user: { role: 'user' } });
                }, 1000);
            });
        } else {
            // Тестовый режим
            return this.mockVerifyPocketId(pocketId);
        }
    }

    mockVerifyPocketId(pocketId) {
        // Тестовая проверка Pocket ID
        const testIds = ['69662105', '12345678', '87654321'];
        
        if (testIds.includes(pocketId) || pocketId.startsWith('demo')) {
            return {
                success: true,
                user: {
                    role: pocketId === '69662105' ? 'admin' : 'user',
                    name: 'Тестовый пользователь'
                }
            };
        } else {
            return {
                success: false,
                message: 'Pocket ID не найден в системе'
            };
        }
    }

    handleDemoAccount(accountType) {
        const demoCredentials = {
            user: { id: 'demo_user_23', password: 'password' },
            admin: { id: 'demo_admin', password: 'admin123' }
        };

        const creds = demoCredentials[accountType];
        if (creds) {
            document.getElementById('pocketId').value = creds.id;
            document.getElementById('confirmId').checked = true;
        }
    }

    loginSuccess(user) {
        // Сохраняем данные авторизации
        localStorage.setItem('auth_token', 'demo_token');
        localStorage.setItem('user_role', user.role);
        localStorage.setItem('user_name', user.name);

        // Перенаправляем в зависимости от роли
        if (user.role === 'admin') {
            window.location.href = 'admin.html';
        } else {
            this.redirectToTrading();
        }
    }

    redirectToTrading() {
        window.location.href = 'trading.html';
    }

    testLogin(pocketId) {
        // Тестовый логин для разработки
        const user = {
            role: pocketId === '69662105' ? 'admin' : 'user',
            name: 'Тестовый пользователь'
        };
        
        this.loginSuccess(user);
    }

    showError(message) {
        // Простое уведомление об ошибке
        alert('Ошибка: ' + message);
    }

    showLoading() {
        const btn = document.getElementById('loginBtn');
        if (btn) {
            btn.innerHTML = 'Проверка ID...';
            btn.disabled = true;
        }
    }

    hideLoading() {
        const btn = document.getElementById('loginBtn');
        if (btn) {
            btn.innerHTML = 'Перейти в трейдинг';
            btn.disabled = false;
        }
    }
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    new TradingApp();
});

// Функции для работы с Telegram Web App
if (window.Telegram && window.Telegram.WebApp) {
    Telegram.WebApp.ready();
    Telegram.WebApp.expand();
}
