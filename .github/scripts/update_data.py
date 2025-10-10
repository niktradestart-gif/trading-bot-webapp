import requests
import json
import os
from datetime import datetime

# Конфигурация
BOT_API_URL = os.getenv('BOT_API_URL', 'http://89.23.98.206:8080')
FILES_TO_UPDATE = [
    'system_status.json',
    'last_signal.json', 
    'last_result.json'
]

def fetch_data_from_bot():
    """Получает данные от торгового бота"""
    try:
        print("🔄 Запрос данных от бота...")
        
        # Вариант 1: Если бот имеет единый endpoint
        response = requests.get(f"{BOT_API_URL}/api/latest_full.json", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"❌ Ошибка запроса: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка подключения к боту: {e}")
        return None

def update_json_files(data):
    """Обновляет JSON файлы на основе данных от бота"""
    if not data:
        print("❌ Нет данных для обновления")
        return False
        
    try:
        # system_status.json
        system_data = {
            "win_rate": data.get('system', {}).get('win_rate', 75.5),
            "active_signals": data.get('system', {}).get('active_signals', 1),
            "status": data.get('system', {}).get('status', "LIVE"),
            "total_trades": data.get('system', {}).get('total_trades', 1250),
            "total_wins": data.get('system', {}).get('total_wins', 945),
            "total_losses": data.get('system', {}).get('total_losses', 305),
            "last_updated": datetime.now().isoformat()
        }
        
        with open('system_status.json', 'w', encoding='utf-8') as f:
            json.dump(system_data, f, indent=2, ensure_ascii=False)
        print("✅ system_status.json обновлен")
        
        # last_signal.json
        signal_data = data.get('signal', {})
        if signal_data and not signal_data.get('error'):
            signal_data['last_updated'] = datetime.now().isoformat()
            with open('last_signal.json', 'w', encoding='utf-8') as f:
                json.dump(signal_data, f, indent=2, ensure_ascii=False)
            print("✅ last_signal.json обновлен")
        else:
            print("⚠️ Нет активного сигнала")
            
        # last_result.json  
        result_data = data.get('result', {})
        if result_data and not result_data.get('error'):
            result_data['last_updated'] = datetime.now().isoformat()
            with open('last_result.json', 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
            print("✅ last_result.json обновлен")
        else:
            print("⚠️ Нет данных о результате")
            
        return True
        
    except Exception as e:
        print(f"❌ Ошибка обновления файлов: {e}")
        return False

def create_fallback_data():
    """Создает тестовые данные если бот недоступен"""
    print("🔄 Создание тестовых данных...")
    
    current_time = datetime.now().isoformat()
    
    # Тестовые данные
    fallback_system = {
        "win_rate": 78.2,
        "active_signals": 1,
        "status": "DEMO",
        "total_trades": 1251,
        "total_wins": 978,
        "total_losses": 273,
        "last_updated": current_time
    }
    
    fallback_signal = {
        "pair": "EURUSD",
        "direction": "BUY", 
        "confidence": 8,
        "entry_price": 1.07423,
        "expiry": 2,
        "source": "ENHANCED_SMART_MONEY",
        "trade_id": 1251,
        "last_updated": current_time
    }
    
    fallback_result = {
        "pair": "GBPJPY",
        "direction": "SELL",
        "result": "WIN", 
        "entry_price": 185.567,
        "exit_price": 185.423,
        "last_updated": current_time
    }
    
    # Сохраняем fallback данные
    with open('system_status.json', 'w') as f:
        json.dump(fallback_system, f, indent=2)
    with open('last_signal.json', 'w') as f:
        json.dump(fallback_signal, f, indent=2) 
    with open('last_result.json', 'w') as f:
        json.dump(fallback_result, f, indent=2)
        
    print("✅ Fallback данные созданы")

if __name__ == "__main__":
    print("🚀 Запуск обновления торговых данных...")
    
    # Пробуем получить данные от бота
    bot_data = fetch_data_from_bot()
    
    if bot_data:
        success = update_json_files(bot_data)
        if not success:
            create_fallback_data()
    else:
        # Если бот недоступен - создаем тестовые данные
        create_fallback_data()
        
    print("✅ Процесс обновления завершен")
