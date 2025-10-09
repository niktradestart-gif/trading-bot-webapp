// Новая логика для красивого дизайна
class ModernTradingApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupDemoCards();
        this.setupFormInteractions();
        this.setupAnimations();
    }

    setupDemoCards() {
        // Клик по демо карточкам
        const demoCards = document.querySelectorAll('.demo-card');
        demoCards.forEach(card => {
            card.addEventListener('click', () => {
                const badge = card.querySelector('.demo-badge');
                this.fillDemoCredentials(badge.textContent.toLowerCase());
            });
        });
    }

    setupFormInteractions() {
        // Интерактивность чекбоксов
        const inputs = document.querySelectorAll('.modern-input');
        inputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const check = e.target.nextElementSibling;
                if (e.target.value.length > 0) {
                    check.classList.add('checked');
                } else {
                    check.classList.remove('checked');
                }
            });
        });

        // Радио кнопки
        const radioOptions = document.querySelectorAll('.radio-option');
        radioOptions.forEach(option => {
            option.addEventListener('click', () => {
                radioOptions.forEach(opt => opt.classList.remove('selected'));
                option.classList.add('selected');
                option.querySelector('input').checked = true;
            });
        });

        // Кнопка входа
        const loginBtn = document.querySelector('.login-btn');
        if (loginBtn) {
            loginBtn.addEventListener('click', () => this.handleLogin());
        }
    }

    setupAnimations() {
        // Плавное появление элементов
        const elements = document.querySelectorAll('.input-group, .login-btn, .demo-card');
        elements.forEach((el, index) => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                el.style.transition = 'all 0.5s ease';
                el.style.opacity = '1';
                el.style.transform = 'translateY(0)';
            }, index * 100);
        });
    }

    fillDemoCredentials(type) {
        const credentials = {
            'пользователь': { id: 'D:\\user\\23', password: 'password', accountType: 'user' },
            'администратор': { id: 'D:\\admin', password: 'admin\\123', accountType: 'admin' },
            'тестирование': { id: 'B:\\cramm', password: '', accountType: 'user' }
        };

        const creds = credentials[type];
        if (creds) {
            // Заполняем поля
            const idInput = document.querySelector('input[placeholder="Введите ваш ID"]');
            const passwordInput = document.querySelector('input[type="password"]');
            
            if (idInput) idInput.value = creds.id;
            if (passwordInput) passwordInput.value = creds.password;

            // Обновляем чекбоксы
            const checks = document.querySelectorAll('.input-check');
            checks[0].classList.add('checked');
            if (creds.password) {
                checks[1].classList.add('checked');
            }

            // Выбираем тип аккаунта
            const radioOptions = document.querySelectorAll('.radio-option');
            radioOptions.forEach(option => {
                option.classList.remove('selected');
                if (option.textContent.toLowerCase().includes(creds.accountType)) {
                    option.classList.add('selected');
                    option.querySelector('input').checked = true;
                }
            });

            // Анимация успеха
            this.showSuccess('Демо данные заполнены!');
        }
    }

    handleLogin() {
        const idInput = document.querySelector('input[placeholder="Введите ваш ID"]');
        const passwordInput = document.querySelector('input[type="password"]');
        
        if (!idInput.value || !passwordInput.value) {
            this.showError('Заполните все поля');
            return;
        }

        this.showLoading();
        
        // Имитация входа
        setTimeout(() => {
            const isAdmin = document.querySelector('.radio-option.selected').textContent.includes('Администратор');
            localStorage.setItem('user_role', isAdmin ? 'admin' : 'user');
            localStorage.setItem('auth_token', 'demo_token');
            
            window.location.href = isAdmin ? 'admin.html' : 'trading.html';
        }, 1500);
    }

    showLoading() {
        const btn = document.querySelector('.login-btn');
        if (btn) {
            btn.innerHTML = '<div class="loading-spinner"></div>';
            btn.disabled = true;
        }
    }

    showSuccess(message) {
        // Можно добавить красивый toast
        console.log('Success:', message);
    }

    showError(message) {
        // Можно добавить красивый toast
        alert('Ошибка: ' + message);
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    new ModernTradingApp();
});

// Стили для спиннера загрузки
const style = document.createElement('style');
style.textContent = `
    .loading-spinner {
        width: 20px;
        height: 20px;
        border: 2px solid transparent;
        border-top: 2px solid #ffffff;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
