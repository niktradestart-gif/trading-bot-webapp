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
            radio.addEventListener('change', (e) => this.handleDemoAccount(e.target.id));
        });

        // Переключение типа учетной записи
        const accountTypes = document.querySelectorAll('input[name="accountType"]');
        accountTypes.forEach(radio => {
            radio.addEventListener('change', (e) => this.handleAccountTypeChange(e.target.id));
        });
    }

    checkAuthentication() {
        const token = localStorage.getItem('auth_token');
        if (token && window.location.pathname.includes('login.html')) {
            const role = localStorage.getItem('user_role');
            this.redirectToPanel(role);
        }
    }

    handleLogin() {
        const userId = document.getElementById('userId').value.trim();
        const password = document.getElementById('password').value;
        const isUserType = document.getElementById('userType').checked;
        const accountType = isUserType ? 'user' : 'admin';

        if (!userId) {
            this.showError('Введите ID пользователя');
            return;
        }

        if (!password) {
            this.showError('Введите пароль');
            return;
        }

        this.showLoading();

        // Проверка демо доступов
        if (this.checkDemoAccess(userId, password, accountType)) {
            setTimeout(() => {
                this.loginSuccess({
                    role: accountType,
                    name: 'Демо пользователь',
                    id: userId
                });
            }, 1000);
        } else {
            setTimeout(() => {
                this.showError('Неверные учетные данные');
                this.hideLoading();
            }, 1000);
        }
    }

    checkDemoAccess(userId, password, accountType) {
        const demoCredentials = {
            'D:\\user\\23': { password: 'password', role: 'user' },
            'D:\\admin': { password: 'admin\\123', role: 'admin' },
            'B:\\cramm': { password: '', role: 'user' }
        };

        const creds = demoCredentials[userId];
        return creds && creds.password === password && creds.role === accountType;
    }

    handleDemoAccount(demoId) {
        const demoData = {
            'demoUser': { id: 'D:\\user\\23', password: 'password', type: 'userType' },
            'demoAdmin': { id: 'D:\\admin', password: 'admin\\123', type: 'adminType' },
            'demoTest': { id: 'B:\\cramm', password: '', type: 'userType' }
        };

        const data = demoData[demoId];
        if (data) {
            document.getElementById('userId').value = data.id;
            document.getElementById('password').value = data.password;
            document.getElementById(data.type).checked = true;
        }
    }

    handleAccountTypeChange(typeId) {
        // Можно добавить дополнительную логику при смене типа аккаунта
        console.log('Тип аккаунта изменен на:', typeId);
    }

    loginSuccess(user) {
        localStorage.setItem('auth_token', 'demo_token');
        localStorage.setItem('user_role', user.role);
        localStorage.setItem('user_name', user.name);
        localStorage.setItem('user_id', user.id);

        this.redirectToPanel(user.role);
    }

    redirectToPanel(role) {
        if (role === 'admin') {
            window.location.href = 'admin.html';
        } else {
            window.location.href = 'trading.html';
        }
    }

    showError(message) {
        alert('Ошибка: ' + message);
    }

    showLoading() {
        const btn = document.getElementById('loginBtn');
        if (btn) {
            btn.innerHTML = 'Проверка...';
            btn.disabled = true;
        }
    }

    hideLoading() {
        const btn = document.getElementById('loginBtn');
        if (btn) {
            btn.innerHTML = 'Войти в систему';
            btn.disabled = false;
        }
    }
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    new TradingApp();
});

// Интеграция с Telegram Web App
if (window.Telegram && window.Telegram.WebApp) {
    Telegram.WebApp.ready();
    Telegram.WebApp.expand();
}
