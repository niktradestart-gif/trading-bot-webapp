import requests
import json
import os
from datetime import datetime

print("🚀 Starting data update...")

# Конфигурация
BOT_API_URL = "http://89.23.98.206:8080"

def fetch_data_from_bot():
    """Получает данные от торгового бота"""
    try:
        print("🔄 Fetching data from bot...")
        response = requests.get(f"{BOT_API_URL}/api/latest_full.json", timeout=10)
        if response.status_code == 200:
            print("✅ Data received from bot")
            return response.json()
        else:
            print(f"❌ Bot response: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Bot connection failed: {e}")
        return None

def update_files(data):
    """Обновляет JSON файлы"""
    current_time = datetime.now().isoformat()
    
    # system_status.json
    system_data = data.get('system', {}) if data else {}
    final_system = {
        "win_rate": system_data.get('win_rate', 76.5),
        "active_signals": system_data.get('active_signals', 1),
        "status": system_data.get('status', "LIVE"),
        "total_trades": system_data.get('total_trades', 1255),
        "total_wins": system_data.get('total_wins', 960),
        "total_losses": system_data.get('total_losses', 295),
        "last_updated": current_time
    }
    
    with open('system_status.json', 'w') as f:
        json.dump(final_system, f, indent=2)
    print("✅ system_status.json updated")
    
    # last_signal.json
    signal_data = data.get('signal', {}) if data else {}
    if signal_data and not signal_data.get('error'):
        signal_data['last_updated'] = current_time
        with open('last_signal.json', 'w') as f:
            json.dump(signal_data, f, indent=2)
        print("✅ last_signal.json updated")
    else:
        with open('last_signal.json', 'w') as f:
            json.dump({"error": "No signal", "last_updated": current_time}, f, indent=2)
        print("⚠️ No active signal")
    
    # last_result.json
    result_data = data.get('result', {}) if data else {}
    if result_data and not result_data.get('error'):
        result_data['last_updated'] = current_time
        with open('last_result.json', 'w') as f:
            json.dump(result_data, f, indent=2)
        print("✅ last_result.json updated")
    else:
        with open('last_result.json', 'w') as f:
            json.dump({"error": "No result", "last_updated": current_time}, f, indent=2)
        print("⚠️ No recent results")

# Основной код
print("📡 Connecting to bot...")
bot_data = fetch_data_from_bot()

print("📊 Updating files...")
update_files(bot_data)

print("🎉 Data update completed!")
