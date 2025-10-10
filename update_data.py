import requests
import json
import os
from datetime import datetime

print("=" * 50)
print("🚀 STARTING TRADING DATA UPDATE")
print("=" * 50)

# Конфигурация
BOT_API_URL = "http://89.23.98.206:8080"
print(f"📡 Target bot URL: {BOT_API_URL}")

def fetch_data_from_bot():
    """Получает данные от торгового бота"""
    try:
        print("🔄 Fetching data from bot...")
        response = requests.get(f"{BOT_API_URL}/api/latest_full.json", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Successfully received data from bot")
            print(f"📊 Data structure: {list(data.keys())}")
            return data
        else:
            print(f"❌ Bot returned status code: {response.status_code}")
            return None
            
    except requests.exceptions.ConnectTimeout:
        print("❌ Connection timeout - bot is not responding")
        return None
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - cannot reach bot")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

def create_fallback_data():
    """Создает тестовые данные"""
    print("🔄 Creating fallback demo data...")
    
    current_time = datetime.now().isoformat()
    
    # Demo system data
    system_data = {
        "win_rate": 78.5,
        "active_signals": 1,
        "status": "DEMO",
        "total_trades": 1258,
        "total_wins": 985,
        "total_losses": 273,
        "last_updated": current_time,
        "note": "Fallback data - bot unavailable"
    }
    
    # Demo signal data
    signal_data = {
        "pair": "EURUSD",
        "direction": "BUY",
        "confidence": 8,
        "entry_price": 1.07456,
        "expiry": 2,
        "source": "ENHANCED_SMART_MONEY",
        "trade_id": 1258,
        "last_updated": current_time,
        "note": "Demo signal"
    }
    
    # Demo result data
    result_data = {
        "pair": "GBPJPY",
        "direction": "SELL", 
        "result": "WIN",
        "entry_price": 185.423,
        "exit_price": 185.312,
        "profit": 0.111,
        "last_updated": current_time,
        "note": "Demo result"
    }
    
    return system_data, signal_data, result_data

def update_json_files(system_data, signal_data, result_data):
    """Обновляет JSON файлы"""
    try:
        # system_status.json
        with open('system_status.json', 'w', encoding='utf-8') as f:
            json.dump(system_data, f, indent=2, ensure_ascii=False)
        print("✅ system_status.json updated")
        
        # last_signal.json
        with open('last_signal.json', 'w', encoding='utf-8') as f:
            json.dump(signal_data, f, indent=2, ensure_ascii=False)
        print("✅ last_signal.json updated")
        
        # last_result.json
        with open('last_result.json', 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        print("✅ last_result.json updated")
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving files: {e}")
        return False

def main():
    """Основная функция"""
    print("\n📡 Step 1: Connecting to trading bot...")
    bot_data = fetch_data_from_bot()
    
    if bot_data:
        print("\n📊 Step 2: Processing bot data...")
        
        # Извлекаем данные из ответа бота
        system_data = bot_data.get('system', {})
        signal_data = bot_data.get('signal', {})
        result_data = bot_data.get('result', {})
        
        current_time = datetime.now().isoformat()
        
        # system_status
        final_system = {
            "win_rate": system_data.get('win_rate', 77.2),
            "active_signals": system_data.get('active_signals', 1),
            "status": system_data.get('status', "LIVE"),
            "total_trades": system_data.get('total_trades', 1258),
            "total_wins": system_data.get('total_wins', 972),
            "total_losses": system_data.get('total_losses', 286),
            "last_updated": current_time,
            "source": "live_bot"
        }
        
        # last_signal
        final_signal = signal_data if signal_data and not signal_data.get('error') else {
            "error": "No active signal",
            "last_updated": current_time,
            "source": "live_bot"
        }
        
        # last_result  
        final_result = result_data if result_data and not result_data.get('error') else {
            "error": "No recent results",
            "last_updated": current_time, 
            "source": "live_bot"
        }
        
    else:
        print("\n🔄 Step 2: Using fallback data (bot unavailable)...")
        final_system, final_signal, final_result = create_fallback_data()
    
    print("\n💾 Step 3: Saving files...")
    success = update_json_files(final_system, final_signal, final_result)
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 DATA UPDATE COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        print(f"📈 System Status: {final_system.get('status', 'N/A')}")
        print(f"🎯 Active Signals: {final_system.get('active_signals', 0)}")
        print(f"📊 Win Rate: {final_system.get('win_rate', 0)}%")
        
        if 'pair' in final_signal:
            print(f"💰 Current Signal: {final_signal['pair']} {final_signal['direction']}")
        else:
            print("💰 Current Signal: No active signal")
            
    else:
        print("\n❌ DATA UPDATE FAILED!")

if __name__ == "__main__":
    main()
