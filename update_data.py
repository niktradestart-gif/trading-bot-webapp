#!/usr/bin/env python3
import requests
import json
from datetime import datetime

def main():
    print("🚀 STARTING TRADING DATA UPDATE")
    print("=" * 50)
    
    # Всегда создаем данные, даже если бот недоступен
    current_time = datetime.now().isoformat()
    
    try:
        # Пробуем получить данные от бота
        print("📡 Connecting to bot...")
        response = requests.get("http://89.23.98.206:8080/api/latest_full.json", timeout=5)
        
        if response.status_code == 200:
            bot_data = response.json()
            print("✅ Successfully received data from bot")
            
            # system_status.json
            system_data = bot_data.get('system', {})
            system_status = {
                "win_rate": system_data.get('win_rate', 77.5),
                "active_signals": system_data.get('active_signals', 1),
                "status": "LIVE",
                "total_trades": system_data.get('total_trades', 1270),
                "total_wins": system_data.get('total_wins', 985),
                "total_losses": system_data.get('total_losses', 285),
                "last_updated": current_time,
                "source": "live_bot"
            }
            
            # last_signal.json
            signal_data = bot_data.get('signal', {})
            if signal_data and not signal_data.get('error'):
                last_signal = signal_data
                last_signal['last_updated'] = current_time
                last_signal['source'] = 'live_bot'
            else:
                last_signal = {
                    "pair": "EURUSD",
                    "direction": "BUY",
                    "confidence": 8,
                    "entry_price": 1.07521,
                    "expiry": 2,
                    "source": "ENHANCED_SMART_MONEY",
                    "last_updated": current_time,
                    "note": "Demo signal - bot unavailable"
                }
            
            # last_result.json
            result_data = bot_data.get('result', {})
            if result_data and not result_data.get('error'):
                last_result = result_data
                last_result['last_updated'] = current_time
                last_result['source'] = 'live_bot'
            else:
                last_result = {
                    "pair": "GBPJPY",
                    "direction": "SELL",
                    "result": "WIN",
                    "entry_price": 185.634,
                    "exit_price": 185.521,
                    "last_updated": current_time,
                    "note": "Demo result - bot unavailable"
                }
                
        else:
            raise Exception(f"Bot returned status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Bot unavailable: {e}")
        print("🔄 Using demo data...")
        
        # Demo данные
        system_status = {
            "win_rate": 78.2,
            "active_signals": 1,
            "status": "DEMO",
            "total_trades": 1270,
            "total_wins": 992,
            "total_losses": 278,
            "last_updated": current_time,
            "source": "demo_data"
        }
        
        last_signal = {
            "pair": "EURUSD",
            "direction": "BUY",
            "confidence": 8,
            "entry_price": 1.07521,
            "expiry": 2,
            "source": "ENHANCED_SMART_MONEY",
            "last_updated": current_time,
            "note": "Demo signal"
        }
        
        last_result = {
            "pair": "GBPJPY", 
            "direction": "SELL",
            "result": "WIN",
            "entry_price": 185.634,
            "exit_price": 185.521,
            "last_updated": current_time,
            "note": "Demo result"
        }

    # Сохраняем файлы
    print("💾 Saving files...")
    
    try:
        with open('system_status.json', 'w') as f:
            json.dump(system_status, f, indent=2)
        print("✅ system_status.json saved")
        
        with open('last_signal.json', 'w') as f:
            json.dump(last_signal, f, indent=2)
        print("✅ last_signal.json saved")
        
        with open('last_result.json', 'w') as f:
            json.dump(last_result, f, indent=2)
        print("✅ last_result.json saved")
        
        print("=" * 50)
        print("🎉 UPDATE COMPLETED SUCCESSFULLY!")
        print(f"📊 Status: {system_status['status']}")
        print(f"🎯 Active Signals: {system_status['active_signals']}")
        print(f"💰 Current Pair: {last_signal.get('pair', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error saving files: {e}")

if __name__ == "__main__":
    main()
