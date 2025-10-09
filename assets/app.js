// Основная логика приложения
class PocketOptionAuth {
    constructor() {
        this.whitelist = {};
        this.init();
    }

    async init() {
        await this.loadWhitelist();
        this.setupEventListeners();
    }

    // Загружаем белый список из файла
    async loadWhitelist() {
        try {
            const response = await fetch('pocket_users.json');
            this.whitelist = await response.json();
            console.log('Whitelist loaded:', this.whitelist);
        } catch (error) {
            console.error('Error loading whitelist:', error);
            // Fallback на дефолтные данные
            this.whitelist = {
                "69662105": {
                    "name": "Admin",
                    "role": "admin",
                    "telegram_id": 5129282647,
                    "registered_at": "2024-01-15T10:30:00",
                    "status": "active"
                },
                "12345678": {
                    "name": "Тестовый пользователь", 
                    "role": "user",
                    "telegram_id": null,
                    "registered_at": "2024-01-15T11:00:00",
                    "status": "active"
                }
            };
        }
    }

    setupEventListeners() {
        // Обработка формы
        document.getElementById('loginForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        // Автоподтверждение при вводе ID
        document.getElementById('pocketId').addEventListener('input', (e) => {
            const checkbox = document.getElementById('confirmId');
            if (e.target.value.length >= 8) {
                checkbox.checked = true;
            } else {
                checkbox.checked = false;
            }
        });

        // Демо доступы
        document.querySelectorAll('input[name="demoAccount"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.fillDemo(e.target.id.replace('demo', '').toLowerCase());
                }
            });
        });
    }

    // Проверка Pocket ID
    async handleLogin() {
        const pocketId = document.getElementById('pocketId').value.trim();
        const isConfirmed = document.getElementById('confirmId').checked;

        if (!pocketId) {
            this.showNotification('Введите ваш Pocket ID', 'error');
            return;
        }

        if (!isConfirmed) {
            this.showNotification('Подтвердите ваш ID', 'error');
            return;
        }

        this.showLoading();

        // Проверяем ID в белом списке
        const userInfo = this.whitelist[pocketId];
        
        if (userInfo && userInfo.status === 'active') {
            this.showNotification(`✅ ID подтвержден! Добро пожаловать, ${userInfo.name}`, 'success');
            
            // Сохраняем данные пользователя
            localStorage.setItem('auth_token', 'pocket_auth');
            localStorage.setItem('user_role', userInfo.role);
            localStorage.setItem('user_name', userInfo.name);
            localStorage.setItem('pocket_id', pocketId);
            
            // Перенаправляем
            setTimeout(() => {
                if (userInfo.role === 'admin') {
                    window.location.href = 'admin.html';
                } else {
                    window.location.href = 'trading.html';
                }
            }, 1500);
            
        } else {
            this.showNotification(
                `❌ Pocket ID ${pocketId} не найден в системе. Зарегистрируйтесь по реферальной ссылке.`,
                'error'
            );
            this.hideLoading();
        }
    }

    // Заполнение демо данных
    fillDemo(type) {
        const demoIds = {
            'user': '12345678',
            'admin': '69662105',
            'test': '87654321'
        };
        
        const pocketId = demoIds[type];
        document.getElementById('pocketId').value = pocketId;
        document.getElementById('confirmId').checked = true;
        
        this.showNotification(`Демо ID ${pocketId} заполнен`, 'success');
    }

    // Показать загрузку
    showLoading() {
        const btn = document.querySelector('.btn-primary');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<div class="spinner"></div> Проверка ID...';
        btn.disabled = true;
    }

    // Скрыть загрузку
    hideLoading() {
        const btn = document.querySelector('.btn-primary');
        btn.innerHTML = 'Перейти в трейдинг';
        btn.disabled = false;
    }

    // Показать уведомление
    showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => {
                if (document.body.contains(notification)) {
                    document.body.removeChild(notification);
                }
            }, 300);
        }, 4000);
    }
}

// Глобальные функции для кнопок
function fillDemo(type) {
    if (window.authApp) {
        window.authApp.fillDemo(type);
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    window.authApp = new PocketOptionAuth();
});

// Функция выхода
function logout() {
    if (confirm('Вы уверены что хотите выйти?')) {
        localStorage.clear();
        window.location.href = 'login.html';
    }
}
