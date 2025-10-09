// Текущая выбранная роль
let currentRole = 'user';

// Выбор роли
function selectRole(role) {
    currentRole = role;
    
    // Обновить UI
    document.querySelectorAll('.role-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-role="${role}"]`).classList.add('active');
}

// Заполнить демо данные
function fillDemo(type) {
    const demoData = {
        'user': { id: 'D:\\user\\23', password: 'password' },
        'admin': { id: 'D:\\admin', password: 'admin\\123' },
        'test': { id: 'B:\\cramm', password: '' }
    };
    
    const data = demoData[type];
    document.getElementById('userId').value = data.id;
    document.getElementById('password').value = data.password;
    
    // Выбрать соответствующую роль
    if (type === 'admin') {
        selectRole('admin');
    } else {
        selectRole('user');
    }
    
    showNotification('Демо данные заполнены!', 'success');
}

// Вход через Telegram
function connectTelegram() {
    showNotification('Интеграция с Telegram будет настроена при подключении к боту', 'success');
}

// Обработка формы входа
document.getElementById('loginForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const userId = document.getElementById('userId').value;
    const password = document.getElementById('password').value;
    
    if (!userId || !password) {
        showNotification('Заполните все поля', 'error');
        return;
    }
    
    // Имитация процесса входа
    simulateLogin(userId, password, currentRole);
});

// Имитация входа в систему
function simulateLogin(userId, password, role) {
    // Показать состояние загрузки
    const submitBtn = document.querySelector('.btn-primary');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<div class="spinner"></div> Авторизация...';
    submitBtn.disabled = true;
    
    // Имитация задержки сети
    setTimeout(() => {
        // Простая проверка демо данных
        const validUsers = {
            'user': { id: 'D:\\user\\23', password: 'password' },
            'admin': { id: 'D:\\admin', password: 'admin\\123' },
            'test': { id: 'B:\\cramm', password: '' }
        };
        
        let isValid = false;
        Object.values(validUsers).forEach(user => {
            if (userId === user.id && password === user.password) {
                isValid = true;
            }
        });
        
        if (isValid) {
            showNotification('Успешный вход! Перенаправление...', 'success');
            
            // Сохраняем данные авторизации
            localStorage.setItem('auth_token', 'demo_token');
            localStorage.setItem('user_role', role);
            localStorage.setItem('user_id', userId);
            
            // Перенаправление на соответствующую панель
            setTimeout(() => {
                if (role === 'admin') {
                    window.location.href = 'admin.html';
                } else {
                    window.location.href = 'trading.html';
                }
            }, 1500);
            
        } else {
            showNotification('Неверный ID пользователя или пароль', 'error');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    }, 2000);
}

// Показать уведомление
function showNotification(message, type) {
    // Создать элемент уведомления
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    
    notification.innerHTML = `
        <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-triangle'}"></i>
        ${message}
    `;
    
    document.body.appendChild(notification);
    
    // Удалить уведомление через 4 секунды
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => {
            if (document.body.contains(notification)) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 4000);
}

// Автофокус на поле userId при загрузке
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('userId').focus();
});

// Функция выхода
function logout() {
    if (confirm('Вы уверены что хотите выйти?')) {
        localStorage.clear();
        window.location.href = 'login.html';
    }
}
