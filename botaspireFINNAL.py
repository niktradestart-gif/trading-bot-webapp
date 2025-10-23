# ===================== 🌐 СИСТЕМНЫЕ И ОСНОВНЫЕ =====================
import os
import sys
import json
import asyncio
import logging
import random
import pickle
import joblib
from datetime import datetime, timedelta, time
from functools import wraps
from typing import Optional, Dict, List, Tuple

# Настройка event loop для Windows
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ===================== 📊 БИБЛИОТЕКИ ДЛЯ АНАЛИТИКИ И МАТЕМАТИКИ =====================
import numpy as np
import pandas as pd

# ВАЖНО: до любого импорта pyplot/ mplfinance — выключаем GUI-бэкенд (TkAgg) для потоков/async
import matplotlib
matplotlib.use("Agg")  # ✅ безопасный headless-режим, никаких вызовов Tkinter

import matplotlib.pyplot as plt
import mplfinance as mpf
from scipy.signal import argrelextrema
from matplotlib.patches import Rectangle

# MetaTrader 5 API
import MetaTrader5 as mt5

# ===================== 📅 ПЛАНИРОВЩИК (APSCHEDULER) =====================
from apscheduler.events import EVENT_JOB_MISSED, EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

def job_listener(event):
    """Обработчик событий job queue"""
    if event.code == EVENT_JOB_MISSED:
        logging.warning(f"⏰ Job {event.job_id} был пропущен!")
    elif event.code == EVENT_JOB_ERROR:
        logging.error(f"❌ Job {event.job_id} завершился ошибкой: {event.exception}")
    elif event.code == EVENT_JOB_EXECUTED:
        logging.debug(f"✅ Job {event.job_id} выполнен успешно")

# ===================== 🤖 TELEGRAM BOT =====================
import telegram
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# ===================== 🧠 МАШИННОЕ ОБУЧЕНИЕ (ML) =====================
import talib as ta
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.cluster import DBSCAN

# ===================== 🧠 OPENAI API =====================
from openai import OpenAI

# ===================== 🌐 GLOBAL VARIABLES =====================
app = None

# ===================== FIXED BOT WORKING HOURS =====================
from datetime import datetime, time, timedelta

# 🕒 Рабочие часы по локальному времени (например, Молдова UTC+2)
TRADING_START = time(4, 0)    # Начало торговли: 04:00
TRADING_END   = time(22, 59)  # Конец торговли: 22:59

# 🗓️ Выходные (суббота и воскресенье)
WEEKEND_DAYS = {5, 6}  # 5 = суббота, 6 = воскресенье

def is_trading_time() -> bool:
    """⏰ Проверяет, находится ли текущее время в рабочих часах бота с уведомлениями"""
    global BOT_LAST_STATUS, BOT_STATUS_NOTIFIED
    
    try:
        now = datetime.now()
        current_time = now.time()
        current_weekday = now.weekday()
        
        # 🗓️ Проверяем выходные (суббота и воскресенье)
        if current_weekday in WEEKEND_DAYS:
            is_working_time = False
        else:
            # 🕒 Проверяем рабочие часы
            is_working_time = TRADING_START <= current_time <= TRADING_END
        
        # 🔔 ПРОВЕРЯЕМ ИЗМЕНЕНИЕ СТАТУСА ДЛЯ УВЕДОМЛЕНИЙ
        if BOT_LAST_STATUS is None:
            BOT_LAST_STATUS = is_working_time
            BOT_STATUS_NOTIFIED = True
        elif BOT_LAST_STATUS != is_working_time:
            # Статус изменился - сбрасываем флаг уведомления
            BOT_LAST_STATUS = is_working_time
            BOT_STATUS_NOTIFIED = False
        
        if not is_working_time:
            # Расчет времени до следующего открытия для уведомления
            if current_weekday in WEEKEND_DAYS:
                days_until_monday = (7 - current_weekday) % 7
                next_work_day = now + timedelta(days=days_until_monday)
                next_open = datetime.combine(next_work_day.date(), TRADING_START)
            elif current_time < TRADING_START:
                next_open = datetime.combine(now.date(), TRADING_START)
            else:
                next_open = datetime.combine(now.date() + timedelta(days=1), TRADING_START)
            
            time_until = next_open - now
            hours = time_until.seconds // 3600
            minutes = (time_until.seconds % 3600) // 60
            
            logging.info(f"⏰ Вне рабочего времени. До открытия: {hours}ч {minutes}мин")
            return False
        else:
            return True
            
    except Exception as e:
        logging.error(f"❌ Ошибка проверки времени: {e}")
        return False

# ==================== TIME FILTERS (TRADE HOURS) ====================
import json
from datetime import datetime

def load_time_filters():
    """Загружает файл time_filters.json"""
    try:
        with open("time_filters.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"✅ Загружено {len(data)} фильтров по парам.")
            return data
    except Exception as e:
        print(f"⚠️ Не удалось загрузить time_filters.json: {e}")
        return {}

TIME_FILTERS = load_time_filters()
TIME_FILTERS_LAST_UPDATE = datetime.now()

def auto_reload_filters():
    """Автоматически перезагружает фильтр при изменении файла (без рестарта)"""
    global TIME_FILTERS, TIME_FILTERS_LAST_UPDATE
    try:
        import os
        mtime = datetime.fromtimestamp(os.path.getmtime("time_filters.json"))
        if mtime > TIME_FILTERS_LAST_UPDATE:
            TIME_FILTERS = load_time_filters()
            TIME_FILTERS_LAST_UPDATE = datetime.now()
            print("♻️ Файл фильтров обновлён на лету.")
    except Exception:
        pass

def is_trade_allowed(pair: str, ts: datetime = None) -> bool:
    """Проверяет, можно ли торговать выбранную пару в данный момент"""
    ts = ts or datetime.utcnow()
    hour = ts.hour
    auto_reload_filters()  # 🔄 Проверяем актуальность фильтра
    allowed_hours = TIME_FILTERS.get(pair, TIME_FILTERS.get("DEFAULT", list(range(24))))
    return hour in allowed_hours

# ================== ML MODEL LOAD ==================
import joblib
import json
import logging
import os

def load_latest_ml_info():
    """Загружает последний объект из ml_info.json (поддерживает список и dict)"""
    try:
        if not os.path.exists("ml_info.json"):
            logging.warning("⚠️ Файл ml_info.json не найден")
            return {}

        with open("ml_info.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            if data:
                latest = data[-1]
                logging.info(f"📚 Найдено {len(data)} записей обучения, используем последнюю ({latest.get('trained_at', 'N/A')})")
                return latest
            else:
                logging.warning("⚠️ ml_info.json пуст (список без записей)")
                return {}
        elif isinstance(data, dict):
            return data
        else:
            logging.warning(f"⚠️ Неподдерживаемый формат ml_info.json: {type(data)}")
            return {}

    except Exception as e:
        logging.error(f"Ошибка чтения ml_info.json: {e}", exc_info=True)
        return {}

# Загрузка модели, скейлера и информации
try:
    ml_model = joblib.load("ml_model.pkl")
    ml_scaler = joblib.load("ml_scaler.pkl")  # обязательная строка для нормализации входных данных
    model_info = load_latest_ml_info()

    if model_info:
        logging.info(f"✅ ML модель загружена ({model_info.get('trained_at', 'N/A')})")
    else:
        logging.warning("⚠️ ML модель загружена, но информация о ней отсутствует или повреждена")

except Exception as e:
    logging.warning(f"Не удалось загрузить ML модель: {e}")
    ml_model, ml_scaler, model_info = None, None, {}

# ================== ML MODEL INITIALIZATION ==================
def initialize_ml_model():
    """Инициализация ML модели с обработкой ошибок"""
    global ml_model, ml_scaler, model_info
    try:
        if os.path.exists("ml_model.pkl") and os.path.exists("ml_scaler.pkl"):
            ml_model = joblib.load("ml_model.pkl")
            ml_scaler = joblib.load("ml_scaler.pkl")
            if os.path.exists("ml_info.json"):
                with open("ml_info.json", "r", encoding="utf-8") as f:
                    model_info = json.load(f)
            logging.info("✅ ML модель загружена успешно")
        else:
            logging.warning("⚠ ML модель не найдена, будет создана при первом обучении")
            ml_model, ml_scaler, model_info = None, None, {}
    except Exception as e:
        logging.error(f"❌ Ошибка загрузки ML модели: {e}")
        ml_model, ml_scaler, model_info = None, None, {}

# Вызов инициализации
initialize_ml_model()

# ===================== CONFIG =====================
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    print("⚠ Ошибка: Проверьте .env файл и убедитесь что указаны TELEGRAM_TOKEN и OPENAI_API_KEY")
    sys.exit(1)

print("✅ Конфигурация загружена успешно")

# MT5
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_PATH = os.getenv("MT5_PATH", r"C:\Program Files\Po Trade MetaTrader 5\terminal64.exe")

# Пары
PAIRS: List[str] = [
    "EURUSD","AUDCAD","AUDCHF","AUDJPY","AUDUSD",
    "CADCHF","CADJPY","CHFJPY","EURAUD","EURCAD",
    "EURCHF","EURGBP","EURJPY","GBPAUD","GBPCAD",
    "GBPCHF","GBPJPY","GBPUSD","USDCAD","USDCHF","USDJPY"
]


# ===================== BOT STATUS TRACKING =====================
BOT_LAST_STATUS = None  # Последний статус бота (True - работает, False - остановлен)
BOT_STATUS_NOTIFIED = False  # Флаг чтобы не спамить уведомлениями


# ===================== POCKET OPTION WHITELIST SYSTEM =====================
import json
import os
from datetime import datetime

# Основной белый список
WHITELIST_FILE = "pocket_users.json"
BACKUP_FILE = "whitelist_ids.json"
REFERRAL_LINK = "https://pocket-friends.com/r/0qrjewbjlf"

# Дефолтные пользователи (админ + демо)
DEFAULT_USERS = {
    '69662105': {
        'name': 'Admin', 
        'role': 'admin',
        'telegram_id': 5129282647,
        'registered_at': '2024-01-15T10:30:00',
        'status': 'active'
    }
}

def load_whitelist():
    """Загружает белый список из файла"""
    try:
        if os.path.exists(WHITELIST_FILE):
            with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # Создаем файл с дефолтными пользователями
            save_whitelist(DEFAULT_USERS)
            return DEFAULT_USERS.copy()
    except Exception as e:
        logging.error(f"❌ Ошибка загрузки whitelist: {e}")
        return DEFAULT_USERS.copy()

def save_whitelist(whitelist_data):
    """Сохраняет белый список в файл"""
    try:
        # Основной файл
        with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
            json.dump(whitelist_data, f, ensure_ascii=False, indent=2)
        
        # Бэкап только ID
        backup_data = list(whitelist_data.keys())
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
        logging.info(f"💾 Whitelist сохранен: {len(whitelist_data)} пользователей")
    except Exception as e:
        logging.error(f"❌ Ошибка сохранения whitelist: {e}")

def is_valid_pocket_id(pocket_id: str) -> bool:
    """Проверяет валидность Pocket Option ID"""
    whitelist = load_whitelist()
    return pocket_id in whitelist

def get_pocket_user_info(pocket_id: str) -> dict:
    """Возвращает информацию о пользователе по Pocket ID"""
    whitelist = load_whitelist()
    return whitelist.get(pocket_id)

def add_user_to_whitelist(pocket_id: str, name: str, telegram_id: int = None, role: str = "user"):
    """Добавляет нового пользователя в белый список"""
    whitelist = load_whitelist()
    
    if pocket_id in whitelist:
        return False, "Пользователь уже существует"
    
    whitelist[pocket_id] = {
        'name': name,
        'role': role,
        'telegram_id': telegram_id,
        'registered_at': datetime.now().isoformat(),
        'status': 'active'
    }
    
    save_whitelist(whitelist)
    return True, "Пользователь добавлен"

def remove_user_from_whitelist(pocket_id: str):
    """Удаляет пользователя из белого списка"""
    whitelist = load_whitelist()
    
    if pocket_id in whitelist:
        del whitelist[pocket_id]
        save_whitelist(whitelist)
        return True, "Пользователь удален"
    
    return False, "Пользователь не найден"

def get_whitelist_stats():
    """Возвращает статистику белого списка"""
    whitelist = load_whitelist()
    total = len(whitelist)
    admins = sum(1 for user in whitelist.values() if user.get('role') == 'admin')
    active = sum(1 for user in whitelist.values() if user.get('status') == 'active')
    
    return {
        'total_users': total,
        'admins': admins,
        'active_users': active,
        'users': total - admins
    }

# Загружаем белый список при старте
WHITELIST = load_whitelist()


# ===================== SETTINGS =====================
USE_GPT = True
openai_client = OpenAI(api_key=OPENAI_API_KEY)

ML_ENABLED = True
ML_PROBABILITY_THRESHOLD = 0.65

# НОВАЯ ГИБКАЯ СИСТЕМА - поддержка двух режимов
MULTI_USER_MODE = True  # Переключатель режима
ADMIN_USER_ID = 5129282647
AUTO_TRADING = True  # Автоматическая торговля по умолчанию включена

# Мультипользовательские данные
users: Dict[int, Dict] = {}

# Однопользовательские данные (для совместимости)
single_user_data = {
    'virtual_balance': 100.0,
    'trade_counter': 0,
    'trade_history': [],
    'current_trade': None
}

# Глобальные флаги
IS_RUNNING = True
VIRTUAL_TRADING = True

# Настройки ставок
STAKE_AMOUNT = 10  
WIN_PROBABILITY = 0.6  
WIN_PROFIT = 18  
LOSS_AMOUNT = 10  



# ===================== ENHANCED LOGGING =====================
def setup_logging():
    """Настройка расширенного логирования"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Форматтер с подробной информацией
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Файловый обработчик
    file_handler = logging.FileHandler("bot_ai.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Очистка старых обработчиков и добавление новых
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Логирование запуска
    logging.info("=" * 50)
    logging.info("🚀 BOT ASPIRE TRADE STARTED")
    logging.info("=" * 50)

# Инициализация логирования
setup_logging()

# ===================== UNIFIED USER MANAGEMENT =====================
def get_user_data(user_id: int = None) -> Dict:
    """Универсальная функция получения данных пользователя БЕЗ БАЛАНСА"""
    if MULTI_USER_MODE and user_id is not None:
        if user_id not in users:
            users[user_id] = {
                'trade_counter': 0,
                'trade_history': [],
                'current_trade': None,
                'first_name': '',
                'username': '',
                'language': 'ru',
                'created_at': datetime.now().isoformat(),
                'auto_trading': True,
                'ml_enabled': ML_ENABLED,
                'gpt_enabled': USE_GPT,
                'smc_enabled': True
            }
        return users[user_id]
    else:
        return single_user_data

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом"""
    return user_id == ADMIN_USER_ID  # Используем существующий ADMIN_USER_ID

def check_and_restore_pocket_users():
    """Проверяет и восстанавливает пользователей в pocket_users.json после перезапуска"""
    try:
        whitelist = load_whitelist()
        updated = False
        
        # Проверяем всех пользователей из users_data.json
        if MULTI_USER_MODE and users:
            for user_id, user_data in users.items():
                pocket_id = str(user_id)
                
                # Если пользователя нет в pocket_users.json, добавляем
                if pocket_id not in whitelist:
                    user_name = user_data.get('first_name', f"User_{user_id}")
                    whitelist[pocket_id] = {
                        'name': user_name,
                        'role': "user",
                        'telegram_id': user_id,
                        'registered_at': user_data.get('created_at', datetime.now().isoformat()),
                        'status': 'active'
                    }
                    updated = True
                    logging.info(f"✅ Восстановлен пользователь в pocket_users.json: {user_id}")
        
        if updated:
            save_whitelist(whitelist)
            logging.info(f"♻️ Восстановление pocket_users.json завершено")
            
    except Exception as e:
        logging.error(f"❌ Ошибка восстановления pocket_users.json: {e}")


# ===================== УНИВЕРСАЛЬНЫЙ ФЛЕТТЕР ML ФИЧЕЙ =====================
def flatten_ml_features(features_dict, parent_key='', sep='_'):
    """Рекурсивно расплющивает вложенные словари ML фичей в плоские ключи"""
    items = {}
    for k, v in features_dict.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_ml_features(v, new_key, sep=sep))
        else:
            if isinstance(v, (bool, np.bool_)):
                items[new_key] = bool(v)
            elif isinstance(v, (np.float32, np.float64, float)):
                items[new_key] = float(v)
            elif isinstance(v, (np.int32, np.int64, int)):
                items[new_key] = int(v)
            elif isinstance(v, np.ndarray):
                items[new_key] = v.tolist()
            else:
                try:
                    items[new_key] = float(v)
                except Exception:
                    items[new_key] = str(v)
    return items


# ===================== СОХРАНЕНИЕ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ =====================
def save_users_data():
    """💾 Сохраняет пользователей с полной поддержкой 42 ML-фичей и надёжными бэкапами"""
    try:
        if MULTI_USER_MODE:
            users_to_save = {}
            for uid, data in users.items():
                trade_history_clean = []
                for trade in data.get('trade_history', []):
                    clean_trade = {
                        'id': int(trade.get('id', 0)),
                        'pair': str(trade.get('pair', '')),
                        'direction': str(trade.get('direction', '')),
                        'entry_price': float(trade.get('entry_price', 0)),
                        'exit_price': float(trade.get('exit_price', 0)) if trade.get('exit_price') else None,
                        'stake': float(trade.get('stake', STAKE_AMOUNT)),
                        'timestamp': str(trade.get('timestamp', datetime.now().isoformat())),
                        'result': str(trade.get('result', '')) if trade.get('result') else None,
                        'profit': float(trade.get('profit', 0)),
                        'expiry_minutes': int(trade.get('expiry_minutes', 1)),
                        'source': str(trade.get('source', '')),
                        'confidence': int(trade.get('confidence', 0)),
                        'completed_at': str(trade.get('completed_at', '')) if trade.get('completed_at') else None,
                        'stake_used': float(trade.get('stake_used', STAKE_AMOUNT))
                    }

                    # 🧠 Сохраняем 42 ML-фичи полностью, включая вложенные структуры
                    ml_features = trade.get('ml_features')
                    if ml_features and isinstance(ml_features, dict):
                        clean_ml_features = {}
                        for key, value in ml_features.items():
                            if isinstance(value, (bool, np.bool_)):
                                clean_ml_features[key] = bool(value)
                            elif isinstance(value, (np.float32, np.float64, float)):
                                clean_ml_features[key] = float(value)
                            elif isinstance(value, (np.int32, np.int64, int)):
                                clean_ml_features[key] = int(value)
                            elif isinstance(value, np.ndarray):
                                clean_ml_features[key] = value.tolist()
                            elif isinstance(value, dict):
                                clean_ml_features[key] = {
                                    k: (
                                        float(v) if isinstance(v, (np.float32, np.float64, float)) else
                                        int(v) if isinstance(v, (np.int32, np.int64, int)) else
                                        bool(v) if isinstance(v, (bool, np.bool_)) else v
                                    )
                                    for k, v in value.items()
                                }
                            else:
                                clean_ml_features[key] = str(value)
                        clean_trade['ml_features'] = clean_ml_features

                    trade_history_clean.append(clean_trade)

                trade_history_clean.sort(key=lambda x: x.get('id', 0))

                users_to_save[str(uid)] = {
                    'trade_counter': int(data.get('trade_counter', 0)),
                    'trade_history': trade_history_clean,
                    'current_trade': data.get('current_trade'),
                    'first_name': str(data.get('first_name', '')),
                    'username': str(data.get('username', '')),
                    'language': str(data.get('language', 'ru')),
                    'created_at': str(data.get('created_at', datetime.now().isoformat())),
                    'auto_trading': bool(data.get('auto_trading', True)),
                    'ml_enabled': bool(data.get('ml_enabled', ML_ENABLED)),
                    'gpt_enabled': bool(data.get('gpt_enabled', USE_GPT)),
                    'smc_enabled': bool(data.get('smc_enabled', True)),
                    'last_save': datetime.now().isoformat()
                }

            # 📁 Сохраняем с резервными копиями (не чаще 1 раза в час)
            os.makedirs("backups", exist_ok=True)
            temp_filename = "users_data.json.tmp"
            final_filename = "users_data.json"

            # 🕒 Формируем имя бэкапа по часу, чтобы не плодить лишние файлы
            hour_stamp = datetime.now().strftime('%Y%m%d_%H')
            backup_filename = f"backups/users_data_backup_{hour_stamp}.json"

            try:
                # 📝 Сохраняем во временный файл
                with open(temp_filename, "w", encoding="utf-8") as f:
                    json.dump(users_to_save, f, ensure_ascii=False, indent=2, default=str)

                # ✅ Проверка целостности временного файла
                with open(temp_filename, "r", encoding="utf-8") as f:
                    json.load(f)

                # 📦 Если уже есть основной файл — делаем резервную копию, но не чаще 1 раза в час
                import shutil
                if os.path.exists(final_filename):
                    if not os.path.exists(backup_filename):
                        shutil.copy2(final_filename, backup_filename)
                        logging.info(f"💾 Часовой бэкап создан: {backup_filename}")

                        # 🧹 Удаляем старые бэкапы, если их больше 4
                        backups = sorted(
                            [f for f in os.listdir("backups") if f.startswith("users_data_backup_")],
                            key=lambda x: os.path.getmtime(os.path.join("backups", x)),
                            reverse=True
                        )
                        if len(backups) > 4:
                            for old_backup in backups[4:]:
                                try:
                                    os.remove(os.path.join("backups", old_backup))
                                    logging.info(f"🗑 Удалён старый бэкап: {old_backup}")
                                except Exception as del_err:
                                    logging.warning(f"⚠ Не удалось удалить {old_backup}: {del_err}")
                    
                os.remove(final_filename)
  
                # 🔄 Атомарная замена временного файла на основной
                os.rename(temp_filename, final_filename)

                # 🧠 ML-бэкап (используется моделью при обучении)
                with open("ml_training_data.json", "w", encoding="utf-8") as f:
                    json.dump(users_to_save, f, ensure_ascii=False, indent=2, default=str)

                # 🟢 Лог успешного сохранения
                total_trades = sum(len(u['trade_history']) for u in users_to_save.values())
                logging.info(f"💾 Сохранены данные {len(users)} пользователей, {total_trades} сделок")

            except Exception as e:
                logging.error(f"❌ Ошибка сохранения данных: {e}")
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                raise e


        else:
            # 🧍 Однопользовательский режим
            trade_history_clean = []
            for trade in single_user_data.get('trade_history', []):
                clean_trade = {
                    'id': int(trade.get('id', 0)),
                    'pair': str(trade.get('pair', '')),
                    'direction': str(trade.get('direction', '')),
                    'entry_price': float(trade.get('entry_price', 0)),
                    'exit_price': float(trade.get('exit_price', 0)) if trade.get('exit_price') else None,
                    'stake': float(trade.get('stake', STAKE_AMOUNT)),
                    'timestamp': str(trade.get('timestamp', datetime.now().isoformat())),
                    'result': str(trade.get('result', '')) if trade.get('result') else None,
                    'profit': float(trade.get('profit', 0)),
                    'expiry_minutes': int(trade.get('expiry_minutes', 1)),
                    'source': str(trade.get('source', '')),
                    'confidence': int(trade.get('confidence', 0)),
                    'completed_at': str(trade.get('completed_at', '')) if trade.get('completed_at') else None,
                    'stake_used': float(trade.get('stake_used', STAKE_AMOUNT))
                }

                ml_features = trade.get('ml_features')
                if ml_features and isinstance(ml_features, dict):
                    clean_ml_features = {}
                    for key, value in ml_features.items():
                        if isinstance(value, (bool, np.bool_)):
                            clean_ml_features[key] = bool(value)
                        elif isinstance(value, (np.float32, np.float64, float)):
                            clean_ml_features[key] = float(value)
                        elif isinstance(value, (np.int32, np.int64, int)):
                            clean_ml_features[key] = int(value)
                        elif isinstance(value, np.ndarray):
                            clean_ml_features[key] = value.tolist()
                        elif isinstance(value, dict):
                            clean_ml_features[key] = {k: (float(v) if isinstance(v, (int,float)) else str(v)) for k,v in value.items()}
                        else:
                            clean_ml_features[key] = str(value)
                    clean_trade['ml_features'] = clean_ml_features

                trade_history_clean.append(clean_trade)

            trade_history_clean.sort(key=lambda x: x.get('id', 0))

            single_to_save = {
                'trade_counter': int(single_user_data.get('trade_counter', 0)),
                'trade_history': trade_history_clean,
                'current_trade': single_user_data.get('current_trade'),
                'last_save': datetime.now().isoformat()
            }

            os.makedirs("backups", exist_ok=True)
            temp_filename = "single_user_data.json.tmp"
            final_filename = "single_user_data.json"
            backup_filename = f"backups/single_user_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            try:
                with open(temp_filename, "w", encoding="utf-8") as f:
                    json.dump(single_to_save, f, ensure_ascii=False, indent=2, default=str)

                with open(temp_filename, "r", encoding="utf-8") as f:
                    json.load(f)

                if os.path.exists(final_filename):
                    import shutil
                    shutil.copy2(final_filename, backup_filename)
                    os.remove(final_filename)

                os.rename(temp_filename, final_filename)

                with open("ml_training_data_single.json", "w", encoding="utf-8") as f:
                    json.dump(single_to_save, f, ensure_ascii=False, indent=2, default=str)

                logging.info(f"💾 Сохранены данные одного пользователя, {len(trade_history_clean)} сделок")

            except Exception as e:
                logging.error(f"❌ Ошибка сохранения single: {e}")
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                raise e

    except Exception as e:
        logging.error(f"💥 Критическая ошибка save_users_data: {e}")

# ===================== ⚙️ SAFE MESSAGE SENDER (ASYNC) =====================
async def safe_send_message(bot, chat_id, text, **kwargs):
    """Отправка сообщения с автоочисткой при блокировке и безопасным сохранением"""
    try:
        await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        return True

    except telegram.error.Forbidden:
        logging.warning(f"🚫 Пользователь {chat_id} заблокировал бота — удаляем из базы.")
        if chat_id in users:
            del users[chat_id]
            await async_save_users_data()   # 🔄 Асинхронное сохранение
            logging.info(f"🧹 Пользователь {chat_id} успешно удалён (бот заблокирован).")
        return False

    except telegram.error.TimedOut:
        logging.warning(f"⏳ Таймаут при отправке пользователю {chat_id}, повторная попытка...")
        try:
            await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except Exception as retry_err:
            logging.error(f"⚠ Ошибка при повторной отправке пользователю {chat_id}: {retry_err}")
        return False

    except Exception as e:
        logging.error(f"⚠ Ошибка при отправке сообщения пользователю {chat_id}: {e}")
        return False


# ===================== ⚙️ USER DATA MANAGEMENT (ASYNC-SAFE) =====================
import aiofiles
import asyncio

save_lock = asyncio.Lock()  # 🔒 глобальный замок для асинхронной записи

async def async_save_users_data():
    """💾 Асинхронное сохранение users_data с блокировкой"""
    global users
    async with save_lock:
        try:
            filename = "users_data.json" if MULTI_USER_MODE else "single_user_data.json"
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)

            # Создаём бэкап
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{os.path.splitext(filename)[0]}_backup_{timestamp}.json")
            async with aiofiles.open(backup_path, "w", encoding="utf-8") as backup_file:
                await backup_file.write(json.dumps(users, ensure_ascii=False, indent=2))

            # Основное сохранение
            async with aiofiles.open(filename, "w", encoding="utf-8") as f:
                await f.write(json.dumps(users, ensure_ascii=False, indent=2))

            logging.info(f"💾 Данные успешно сохранены ({len(users)} пользователей)")

        except Exception as e:
            logging.error(f"❌ Ошибка сохранения данных: {e}")

def load_users_data():
    """📥 Надёжная загрузка данных с бэкапами и восстановлением счетчиков"""
    global users, single_user_data
    try:
        path = "users_data.json" if MULTI_USER_MODE else "single_user_data.json"
        if os.path.exists(path):
            success = load_from_file(path, "multi" if MULTI_USER_MODE else "single")
            if not success:
                backups = [f for f in os.listdir("backups") if f.startswith(os.path.splitext(os.path.basename(path))[0])]
                if backups:
                    backups.sort(reverse=True)
                    latest = os.path.join("backups", backups[0])
                    logging.warning(f"⚠ Повреждён файл, пробуем бэкап: {latest}")
                    load_from_file(latest, "multi" if MULTI_USER_MODE else "single")
                else:
                    users = {}
                    logging.warning("⚠ Нет бэкапов — создаётся пустая база")
        else:
            users = {}
            logging.info(f"📝 {path} не найден — создаётся новая база")

    except Exception as e:
        logging.error(f"💥 Ошибка загрузки данных: {e}")
        users = {}
        single_user_data = create_default_single_data()

def load_from_file(filename, mode):
    """📥 Загружает JSON и восстанавливает счётчики"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            logging.warning(f"⚠ Файл {filename} пуст")
            return False

        data = json.loads(content)
        if mode == "multi":
            users.clear()
            for uid_str, udata in data.items():
                uid = int(uid_str)
                users[uid] = udata
                hist_count = len(udata.get("trade_history", []))
                if udata.get("trade_counter", 0) != hist_count:
                    users[uid]["trade_counter"] = hist_count
            logging.info(f"✅ Загружено {len(users)} пользователей")
        else:
            single_user_data.update(data)
            hist_count = len(single_user_data.get("trade_history", []))
            if single_user_data.get("trade_counter", 0) != hist_count:
                single_user_data["trade_counter"] = hist_count
            logging.info(f"✅ Загружены данные single ({hist_count} сделок)")
        return True

    except Exception as e:
        logging.error(f"❌ Ошибка load_from_file {filename}: {e}")
        return False


def create_default_single_data():
    """Создаёт дефолтную структуру single пользователя"""
    return {
        'trade_counter': 0,
        'trade_history': [],
        'current_trade': None
    }
# ===================== SMART MONEY ANALYSIS =====================
def find_market_structure(df, lookback=25):
    """Улучшенное определение структуры рынка с фильтрацией шума"""
    try:
        highs = df['high'].values
        lows = df['low'].values
        structure_points = []
        
        # Фильтр минимального движения
        avg_range = (df['high'] - df['low']).tail(50).mean()
        min_move = avg_range * 0.3
        
        for i in range(lookback, len(df) - lookback):
            # Проверка значимости High
            if (highs[i] > max(highs[i-lookback:i]) and 
                highs[i] > max(highs[i+1:i+lookback+1])):
                
                # Фильтр по размеру движения от предыдущего HH/HL
                prev_highs = [p for p in structure_points if p['type'] in ['HH', 'HL']]
                if prev_highs:
                    last_high = prev_highs[-1]['price']
                    if highs[i] - last_high >= min_move:
                        structure_points.append({
                            'type': 'HH',
                            'price': highs[i],
                            'index': i,
                            'time': df.index[i]
                        })
                else:
                    structure_points.append({
                        'type': 'HH', 
                        'price': highs[i],
                        'index': i,
                        'time': df.index[i]
                    })
            
            # Проверка значимости Low
            if (lows[i] < min(lows[i-lookback:i]) and 
                lows[i] < min(lows[i+1:i+lookback+1])):
                
                prev_lows = [p for p in structure_points if p['type'] in ['LL', 'LH']]
                if prev_lows:
                    last_low = prev_lows[-1]['price']
                    if last_low - lows[i] >= min_move:
                        structure_points.append({
                            'type': 'LL',
                            'price': lows[i],
                            'index': i,
                            'time': df.index[i]
                        })
                else:
                    structure_points.append({
                        'type': 'LL',
                        'price': lows[i],
                        'index': i,
                        'time': df.index[i]
                    })
        
        return structure_points[-8:] if len(structure_points) > 8 else structure_points
        
    except Exception as e:
        logging.error(f"Ошибка find_market_structure: {e}")
        return []

def find_horizontal_levels(df, threshold_pips=0.0005):
    """Улучшенный поиск горизонтальных уровней с кластеризацией"""
    try:
        levels = []
        
        # Используем только значимые экстремумы
        high_peaks = argrelextrema(df['high'].values, np.greater, order=3)[0]
        low_peaks = argrelextrema(df['low'].values, np.less, order=3)[0]
        
        # Объединяем все значимые точки
        significant_points = []
        for idx in high_peaks:
            significant_points.append(df['high'].iloc[idx])
        for idx in low_peaks:
            significant_points.append(df['low'].iloc[idx])
        
        if not significant_points:
            return []
        
        # Кластеризация по цене
        points_array = np.array(significant_points).reshape(-1, 1)
        clustering = DBSCAN(eps=threshold_pips, min_samples=3).fit(points_array)
        
        levels = []
        unique_labels = set(clustering.labels_)
        
        for label in unique_labels:
            if label != -1:  # Игнорируем шум
                cluster_points = np.array(significant_points)[clustering.labels_ == label]
                if len(cluster_points) >= 3:  # Минимум 3 точки в кластере
                    level_price = np.mean(cluster_points)
                    
                    # Подсчет касаний
                    touches = 0
                    for i in range(len(df)):
                        high = df['high'].iloc[i]
                        low = df['low'].iloc[i]
                        if abs(high - level_price) <= threshold_pips or \
                           abs(low - level_price) <= threshold_pips:
                            touches += 1
                    
                    if touches >= 5:  # Минимум 5 касаний
                        # Определение типа уровня
                        recent_prices = df['close'].tail(20)
                        above = sum(recent_prices > level_price)
                        below = sum(recent_prices < level_price)
                        
                        level_type = "RESISTANCE" if above > below else "SUPPORT"
                        strength = "STRONG" if touches > 12 else "MEDIUM" if touches > 8 else "WEAK"
                        
                        levels.append({
                            'price': level_price,
                            'touches': touches,
                            'type': level_type,
                            'strength': strength,
                            'cluster_size': len(cluster_points)
                        })
        
        # Сортировка по силе и удаление дубликатов
        levels.sort(key=lambda x: (x['touches'], x['cluster_size']), reverse=True)
        
        # Удаление близких уровней
        final_levels = []
        for level in levels:
            if not any(abs(level['price'] - existing['price']) <= threshold_pips 
                      for existing in final_levels):
                final_levels.append(level)
        
        return final_levels[:10]  # Возвращаем до 10 сильнейших уровней
        
    except Exception as e:
        logging.error(f"Ошибка find_horizontal_levels: {e}")
        return []

def validate_zone_quality(zone, df):
    """Проверка качества зоны - был ли реальный отскок"""
    try:
        # Проверяем что zone это словарь, а не строка
        if not isinstance(zone, dict):
            logging.error(f"❌ Zone не является словарем: {type(zone)}")
            return False
            
        zone_index = zone.get('index')
        if zone_index is None:
            logging.error("❌ Zone не имеет индекса")
            return False
        
        # Проверяем что индекс в пределах данных
        if zone_index >= len(df) - 8:
            return False
            
        candles_after = df.iloc[zone_index+1:zone_index+8]
        
        if len(candles_after) < 3:
            return False
            
        zone_type = zone.get('type')
        zone_top = zone.get('top')
        zone_bottom = zone.get('bottom')
        
        if not all([zone_type, zone_top, zone_bottom]):
            logging.error("❌ Zone отсутствуют необходимые поля")
            return False
            
        if zone_type == 'DEMAND':
            # Для зоны спроса: должен быть отскок ВВЕРХ
            rebound = any(candle['close'] > zone_top for candle in candles_after)
            return rebound
        else:  # SUPPLY
            # Для зоны предложения: должен быть отскок ВНИЗ  
            rebound = any(candle['close'] < zone_bottom for candle in candles_after)
            return rebound
            
    except Exception as e:
        logging.error(f"❌ Ошибка validate_zone_quality: {e}")
        return False

def find_supply_demand_zones(df, strength=2, lookback=25):
    """Улучшенный поиск зон спроса/предложения"""
    try:
        highs = df['high'].values
        lows = df['low'].values
        volumes = df['tick_volume'].values
        zones = []
        
        # Базовые зоны из экстремумов
        high_peaks = argrelextrema(highs, np.greater, order=strength)[0]
        low_peaks = argrelextrema(lows, np.less, order=strength)[0]
        
        avg_volume = np.mean(volumes[-50:]) if len(volumes) > 50 else np.mean(volumes)
        avg_candle_size = (df['high'] - df['low']).tail(50).mean()
        
        # Анализ зон предложения (Supply)
        for peak in high_peaks[-10:]:
            if peak >= 20:
                peak_high = highs[peak]
                peak_volume = volumes[peak]
                
                left_highs = highs[max(0, peak-20):peak]
                right_highs = highs[peak+1:min(len(highs), peak+21)]
                
                if (len(left_highs) > 0 and len(right_highs) > 0 and
                    peak_high > np.max(left_highs) and 
                    peak_high > np.max(right_highs)):
                    
                    volume_ratio = peak_volume / avg_volume if avg_volume > 0 else 1
                    zone_score = 0
                    
                    if volume_ratio > 2.0: zone_score += 3
                    elif volume_ratio > 1.5: zone_score += 2
                    elif volume_ratio > 1.2: zone_score += 1
                    
                    prev_low = np.min(lows[max(0, peak-10):peak])
                    move_size = (peak_high - prev_low) / avg_candle_size if avg_candle_size > 0 else 0
                    if move_size > 3: zone_score += 2
                    elif move_size > 2: zone_score += 1
                    
                    if zone_score >= 2:
                        zones.append({
                            'type': 'SUPPLY',
                            'top': peak_high,
                            'bottom': peak_high * 0.998,
                            'strength': 'STRONG' if zone_score >= 4 else 'MEDIUM',
                            'score': zone_score,
                            'volume_ratio': volume_ratio,
                            'source': 'EXTREME',
                            'index': peak
                        })
        
        # Анализ зон спроса (Demand)
        for valley in low_peaks[-10:]:
            if valley >= 20:
                valley_low = lows[valley]
                valley_volume = volumes[valley]
                
                left_lows = lows[max(0, valley-20):valley]
                right_lows = lows[valley+1:min(len(lows), valley+21)]
                
                if (len(left_lows) > 0 and len(right_lows) > 0 and
                    valley_low < np.min(left_lows) and 
                    valley_low < np.min(right_lows)):
                    
                    volume_ratio = valley_volume / avg_volume if avg_volume > 0 else 1
                    zone_score = 0
                    
                    if volume_ratio > 2.0: zone_score += 3
                    elif volume_ratio > 1.5: zone_score += 2
                    elif volume_ratio > 1.2: zone_score += 1
                    
                    prev_high = np.max(highs[max(0, valley-10):valley])
                    move_size = (prev_high - valley_low) / avg_candle_size if avg_candle_size > 0 else 0
                    if move_size > 3: zone_score += 2
                    elif move_size > 2: zone_score += 1
                    
                    if zone_score >= 2:
                        zones.append({
                            'type': 'DEMAND',
                            'top': valley_low * 1.002,
                            'bottom': valley_low,
                            'strength': 'STRONG' if zone_score >= 4 else 'MEDIUM',
                            'score': zone_score,
                            'volume_ratio': volume_ratio,
                            'source': 'EXTREME',
                            'index': valley
                        })
        
        # Добавление горизонтальных уровней как зон
        horizontal_levels = find_horizontal_levels(df)
        for level in horizontal_levels:
            if level['strength'] in ['STRONG', 'MEDIUM']:
                zone_width = avg_candle_size * 0.3
                zones.append({
                    'type': 'SUPPLY' if level['type'] == 'RESISTANCE' else 'DEMAND',
                    'top': level['price'] + zone_width,
                    'bottom': level['price'] - zone_width,
                    'strength': level['strength'],
                    'score': 3 if level['strength'] == 'STRONG' else 2,
                    'volume_ratio': 1.5,
                    'source': 'HORIZONTAL',
                    'touches': level['touches'],
                    'index': len(df) - 1
                })
        
        # 🔥 ВРЕМЕННО ОТКЛЮЧЕНА ФИЛЬТРАЦИЯ - ИСПОЛЬЗУЕМ ВСЕ ЗОНЫ
        # Сортировка по score
        zones.sort(key=lambda x: (x['score'], x.get('touches', 0)), reverse=True)
        
        # Удаление пересекающихся зон
        final_zones = []
        for zone in zones:
            overlapping = False
            for existing in final_zones:
                if (zone['bottom'] <= existing['top'] and 
                    zone['top'] >= existing['bottom']):
                    overlapping = True
                    if zone['score'] > existing['score']:
                        final_zones.remove(existing)
                        final_zones.append(zone)
                    break
            
            if not overlapping:
                final_zones.append(zone)
        
        return final_zones[:6]
        
    except Exception as e:
        logging.error(f"Ошибка find_supply_demand_zones: {e}")
        return []
    
def calculate_order_blocks_advanced(df):
    """Улучшенный поиск ордер-блоков с системой подтверждения"""
    order_blocks = []
    
    try:
        avg_candle_size = df['high'].subtract(df['low']).rolling(50).mean().iloc[-1]
        if pd.isna(avg_candle_size) or avg_candle_size == 0:
            avg_candle_size = df['high'].subtract(df['low']).mean()
        
        # Минимальный размер для значимого OB
        min_ob_size = avg_candle_size * 1.5
        
        for i in range(20, len(df) - 15):
            current_candle = df.iloc[i]
            candle_body = abs(current_candle['close'] - current_candle['open'])
            candle_range = current_candle['high'] - current_candle['low']
            
            # Проверка значимости свечи
            is_significant = (candle_body > min_ob_size and 
                             candle_range > avg_candle_size * 2.0)
            
            if not is_significant:
                continue
            
            next_candles = df.iloc[i+1:i+12]  # Увеличили окно для подтверждения
            
            # Медвежий OB (красная свеча)
            if (current_candle['close'] < current_candle['open'] and
                candle_body > min_ob_size):
                
                # Проверка: цена возвращалась к OB и отскакивала
                touched = any(low <= current_candle['close'] for low in next_candles['low'])
                rejected = any(close > current_candle['close'] for close in next_candles['close'])
                
                if touched and rejected:
                    # Дополнительное подтверждение - объем
                    ob_volume = current_candle['tick_volume']
                    avg_vol = df['tick_volume'].iloc[max(0,i-20):i].mean()
                    
                    strength = "STRONG" if ob_volume > avg_vol * 1.5 else "MEDIUM"
                    
                    order_blocks.append({
                        'type': 'BEARISH_OB',
                        'high': current_candle['open'],
                        'low': current_candle['close'],
                        'index': i,
                        'strength': strength,
                        'volume_ratio': ob_volume / avg_vol if avg_vol > 0 else 1
                    })
            
            # Бычий OB (зеленая свеча)
            elif (current_candle['close'] > current_candle['open'] and
                  candle_body > min_ob_size):
                
                touched = any(high >= current_candle['close'] for high in next_candles['high'])
                rejected = any(close < current_candle['close'] for close in next_candles['close'])
                
                if touched and rejected:
                    ob_volume = current_candle['tick_volume']
                    avg_vol = df['tick_volume'].iloc[max(0,i-20):i].mean()
                    
                    strength = "STRONG" if ob_volume > avg_vol * 1.5 else "MEDIUM"
                    
                    order_blocks.append({
                        'type': 'BULLISH_OB',
                        'high': current_candle['close'],
                        'low': current_candle['open'],
                        'index': i,
                        'strength': strength,
                        'volume_ratio': ob_volume / avg_vol if avg_vol > 0 else 1
                    })
        
        # Фильтрация: оставляем только сильные OB
        strong_obs = [ob for ob in order_blocks if ob['strength'] == 'STRONG']
        medium_obs = [ob for ob in order_blocks if ob['strength'] == 'MEDIUM']
        
        # Возвращаем до 2 сильных или 3 средних OB
        return (strong_obs[:2] if strong_obs else medium_obs[:3])
        
    except Exception as e:
        logging.error(f"Ошибка calculate_order_blocks_advanced: {e}")
        return []

def calculate_fibonacci_levels(df):
    """Расчёт уровней Фибоначчи по последнему импульсу"""
    try:
        recent = df.tail(100)
        high = recent['high'].max()
        low = recent['low'].min()

        diff = high - low
        levels = []
        fib_ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]

        for r in fib_ratios:
            level = high - diff * r
            levels.append({"ratio": int(r*100), "level": level})

        return levels
    except Exception as e:
        logging.error(f"Ошибка в calculate_fibonacci_levels: {e}")
        return []

def enhanced_trend_analysis(df):
    """Улучшенный анализ тренда с определением импульсных движений"""
    try:
        # =============== СТАНДАРТНЫЕ ИНДИКАТОРЫ ===============
        ema_20 = ta.EMA(df['close'], 20).iloc[-1]
        ema_50 = ta.EMA(df['close'], 50).iloc[-1]
        ema_100 = ta.EMA(df['close'], 100).iloc[-1]
        
        adx = ta.ADX(df['high'], df['low'], df['close'], 14).iloc[-1]
        rsi = ta.RSI(df['close'], 14).iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # =============== НОВЫЕ МЕТРИКИ ИМПУЛЬСА ===============
        # 1. Сила последнего движения
        if len(df) >= 10:
            price_change_5 = (current_price - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100
            price_change_10 = (current_price - df['close'].iloc[-10]) / df['close'].iloc[-10] * 100
        else:
            price_change_5 = 0
            price_change_10 = 0
        
        # 2. Объем импульса
        current_volume = df['tick_volume'].iloc[-1]
        avg_volume_20 = df['tick_volume'].tail(20).mean()
        volume_ratio = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1
        
        # 3. Определение импульсного движения
        is_strong_impulse = (
            abs(price_change_5) > 0.15 or  # Сильное движение за 5 свечей
            abs(price_change_10) > 0.25    # Сильное движение за 10 свечей
        )
        
        # 4. Направление тренда по EMA
        if ema_20 > ema_50 > ema_100:
            trend_direction = "BULLISH"
        elif ema_20 < ema_50 < ema_100:
            trend_direction = "BEARISH"
        else:
            trend_direction = "NEUTRAL"
        
        # 5. Сила тренда с учетом импульса и ADX
        if adx > 30 and is_strong_impulse:
            trend_strength = "VERY_STRONG"
        elif adx > 25:
            trend_strength = "STRONG"
        elif adx < 15:
            trend_strength = "WEAK"
        else:
            trend_strength = "MODERATE"
        
        # 6. Состояние RSI
        if rsi > 70:
            rsi_state = "OVERBOUGHT"
        elif rsi < 30:
            rsi_state = "OVERSOLD"
        else:
            rsi_state = "NEUTRAL"
        
        return {
            'direction': trend_direction,
            'strength': trend_strength,
            'rsi_state': rsi_state,
            'adx_value': adx,
            'rsi_value': rsi,
            'above_ema20': current_price > ema_20,
            'above_ema50': current_price > ema_50,
            # 🔥 Новые поля импульса
            'price_change_5m': price_change_5,
            'price_change_10m': price_change_10,
            'volume_ratio': volume_ratio,
            'is_strong_impulse': is_strong_impulse,
            'impulse_direction': 'BULLISH' if price_change_5 > 0 else 'BEARISH'
        }
    except Exception as e:
        logging.error(f"Ошибка enhanced_trend_analysis: {e}")
        return {
            'direction': 'NEUTRAL',
            'strength': 'WEAK',
            'rsi_state': 'NEUTRAL',
            'is_strong_impulse': False
        }

def liquidity_analysis(df):
    """Анализ уровней ликвидности"""
    try:
        recent_high = df['high'].tail(50).max()
        recent_low = df['low'].tail(50).min()
        current_price = df['close'].iloc[-1]
        atr = ta.ATR(df['high'], df['low'], df['close'], 14).iloc[-1]
        
        # Уровни ликвидности (стоп-лоссы)
        buy_liquidity_below = recent_low - atr * 0.5
        sell_liquidity_above = recent_high + atr * 0.5
        
        # Расстояние до ликвидности
        distance_to_buy_liquidity = current_price - buy_liquidity_below
        distance_to_sell_liquidity = sell_liquidity_above - current_price
        
        return {
            'buy_liquidity': buy_liquidity_below,
            'sell_liquidity': sell_liquidity_above,
            'distance_to_buy_liquidity_pips': distance_to_buy_liquidity * 10000,
            'distance_to_sell_liquidity_pips': distance_to_sell_liquidity * 10000,
            'near_buy_liquidity': distance_to_buy_liquidity < atr,
            'near_sell_liquidity': distance_to_sell_liquidity < atr
        }
    except Exception as e:
        logging.error(f"Ошибка liquidity_analysis: {e}")
        return {}

def price_action_patterns(df):
    """Определение Price Action паттернов"""
    patterns = []
    
    try:
        if len(df) < 3:
            return patterns
            
        current = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]
        
        current_body = abs(current['close'] - current['open'])
        current_range = current['high'] - current['low']
        prev_body = abs(prev['close'] - prev['open'])
        
        # Pin Bar
        if current_body < current_range * 0.3:
            upper_wick = current['high'] - max(current['open'], current['close'])
            lower_wick = min(current['open'], current['close']) - current['low']
            
            if upper_wick > current_body * 2 and lower_wick < current_body:
                patterns.append({'type': 'BEARISH_PIN', 'strength': 'MEDIUM'})
            elif lower_wick > current_body * 2 and upper_wick < current_body:
                patterns.append({'type': 'BULLISH_PIN', 'strength': 'MEDIUM'})
        
        # Engulfing
        if (current['close'] > current['open'] and prev['close'] < prev['open'] and
            current['open'] < prev['close'] and current['close'] > prev['open']):
            patterns.append({'type': 'BULLISH_ENGULFING', 'strength': 'STRONG'})
        elif (current['close'] < current['open'] and prev['close'] > prev['open'] and
              current['open'] > prev['close'] and current['close'] < prev['open']):
            patterns.append({'type': 'BEARISH_ENGULFING', 'strength': 'STRONG'})
        
        # Inside Bar
        if (current['high'] < prev['high'] and current['low'] > prev['low']):
            patterns.append({'type': 'INSIDE_BAR', 'strength': 'WEAK'})
            
    except Exception as e:
        logging.error(f"Ошибка price_action_patterns: {e}")
    
    return patterns

def calculate_dynamic_expiry(df, confidence, signal_type=None):
    """
    🔁 Оптимизированный расчёт экспирации для бинарных сделок (1–3 мин)
    ⚡ Укороченные интервалы для быстрой реакции на сигнал
    """
    try:
        # ATR — средний истинный диапазон (волатильность)
        atr = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14).iloc[-1]
        current_price = df['close'].iloc[-1]
        volatility_percent = (atr / current_price) * 100 if current_price > 0 else 0

        # 1️⃣ БАЗОВАЯ ЭКСПИРАЦИЯ (укороченная шкала)
        if volatility_percent >= 0.04:         # Очень высокая волатильность
            base_expiry = 1
        elif volatility_percent >= 0.025:      # Средне-высокая
            base_expiry = 2
        else:                                  # Спокойный рынок
            base_expiry = 3

        # 2️⃣ КОРРЕКТИРОВКА ПО ТИПУ СИГНАЛА
        if signal_type == "BREAKOUT":
            base_expiry = max(1, base_expiry - 1)
        elif signal_type == "REVERSAL":
            base_expiry = min(base_expiry + 1, 3)
        # TREND_FOLLOWING — без изменений

        # 3️⃣ КОРРЕКТИРОВКА ПО УВЕРЕННОСТИ
        if confidence >= 9:
            final_expiry = 1
        elif confidence >= 7:
            final_expiry = max(1, base_expiry - 1)
        elif confidence >= 5:
            final_expiry = base_expiry
        else:
            final_expiry = min(base_expiry + 1, 3)

        # 4️⃣ ГРАНИЦЫ БЕЗОПАСНОСТИ
        final_expiry = max(1, min(final_expiry, 3))

        logging.info(
            f"📊 Волатильность: {volatility_percent:.4f}% | "
            f"Тип: {signal_type or 'N/A'} | Уверенность: {confidence} → "
            f"Экспирация: {final_expiry} мин"
        )
        return final_expiry

    except Exception as e:
        logging.error(f"❌ Ошибка расчёта динамической экспирации: {e}")
        return 2  # дефолт 2 минуты при ошибке


def get_candle_time_info():
    """Получает информацию о времени до закрытия текущей свечи"""
    now = datetime.now()
    seconds_passed = now.second
    seconds_remaining = 60 - seconds_passed
    
    completion_percent = (seconds_passed / 60) * 100
    
    return {
        'seconds_remaining': seconds_remaining,
        'seconds_passed': seconds_passed, 
        'completion_percent': completion_percent,
        'is_beginning': completion_percent < 25,
        'is_middle': 25 <= completion_percent <= 75,
        'is_ending': completion_percent > 75
    }

def early_entry_strategy(df, candle_time, trend_analysis):
    """Стратегия входа в начале свечи при сильном импульсе"""
    if candle_time['seconds_passed'] < 10:
        if len(df) < 2:
            return None, 0, None
            
        prev_candle = df.iloc[-2]
        current_candle = df.iloc[-1]
        
        if current_candle['open'] > prev_candle['close'] * 1.0005:
            return "BUY", 2, "EARLY_GAP_UP"
        elif current_candle['open'] < prev_candle['close'] * 0.9995:
            return "SELL", 2, "EARLY_GAP_DOWN"
    
    return None, 0, None

def calculate_average_candle_size(df, period=20):
    """Рассчитывает средний размер свечи"""
    if len(df) < period:
        return 0
    candle_sizes = df['high'].tail(period) - df['low'].tail(period)
    return candle_sizes.mean()

def closing_candle_strategy(df, candle_time, trend_analysis):
    """Стратегия входа перед закрытием свечи"""
    if candle_time['seconds_remaining'] < 15:
        current_candle = df.iloc[-1]
        avg_candle_size = calculate_average_candle_size(df)
        
        if avg_candle_size > 0 and (current_candle['high'] - current_candle['low']) < avg_candle_size * 0.5:
            if trend_analysis['direction'] == 'BULLISH':
                return "BUY", 1, "BREAKOUT_ENDING"
            elif trend_analysis['direction'] == 'BEARISH':
                return "SELL", 1, "BREAKOUT_ENDING"
    
    return None, 0, None

def check_level_breakouts(df, current_price, zones):
    try:
        breakouts = []
        lookback = 8
        
        for zone in zones:
            zone_middle = (zone['top'] + zone['bottom']) / 2
            
            if zone['type'] == 'DEMAND':
                recent_closes = df['close'].tail(lookback)
                recent_lows = df['low'].tail(lookback)
                
                if any(close < zone['bottom'] for close in recent_closes) or \
                   any(low < zone['bottom'] for low in recent_lows):
                    breakouts.append({
                        'type': 'BEARISH_BREAKOUT',
                        'zone': zone,
                        'strength': 'STRONG' if zone['source'] == 'HORIZONTAL' else 'MEDIUM'
                    })
            
            elif zone['type'] == 'SUPPLY':
                recent_closes = df['close'].tail(lookback)
                recent_highs = df['high'].tail(lookback)
                
                if any(close > zone['top'] for close in recent_closes) or \
                   any(high > zone['top'] for high in recent_highs):
                    breakouts.append({
                        'type': 'BULLISH_BREAKOUT', 
                        'zone': zone,
                        'strength': 'STRONG' if zone['source'] == 'HORIZONTAL' else 'MEDIUM'
                    })
        
        return breakouts
        
    except Exception as e:
        logging.error(f"Ошибка проверки пробоев: {e}")
        return []
def is_exhausted_move(df, trend_analysis):
    """Определяет истощение движения для фильтрации ложных сигналов"""
    try:
        if len(df) < 20:
            return False
            
        current_price = df['close'].iloc[-1]
        rsi = trend_analysis.get('rsi_value', 50)
        
        # 1. Проверка RSI в экстремумах
        if rsi < 25 or rsi > 75:
            # 2. Проверка резкого движения (более чувствительная)
            price_change_5m = (current_price - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100
            price_change_15m = (current_price - df['close'].iloc[-15]) / df['close'].iloc[-15] * 100
            
            # 3. Проверка объема (менее строгая)
            current_volume = df['tick_volume'].iloc[-1]
            avg_volume = df['tick_volume'].tail(20).mean()
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # 4. Проверка относительно нормальной волатильности
            atr = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14).iloc[-1]
            normal_move = (atr / current_price) * 100 * 3  # 3x от нормальной волатильности
            
            # 🔥 УЛУЧШЕННЫЕ КРИТЕРИИ ИСТОЩЕНИЯ:
            is_strong_move = abs(price_change_5m) > 0.15  # Более чувствительный порог
            is_extended_move = abs(price_change_5m) > normal_move  # Относительно ATR
            is_volume_declining = volume_ratio < 0.9  # Менее строгий объем
            
            # Критерии истощения:
            if (is_strong_move or is_extended_move) and is_volume_declining:
                logging.info(f"⚠️ Обнаружено истощение движения: RSI={rsi:.1f}, Δ5m={price_change_5m:.2f}%, Объем={volume_ratio:.2f}")
                return True
                
        return False
        
    except Exception as e:
        logging.error(f"Ошибка в is_exhausted_move: {e}")
        return False

def enhanced_smart_money_analysis(df):
    """УЛУЧШЕННАЯ ВЕРСИЯ - сохраняет структуру, но усиливает анализ"""
    if df is None or len(df) < 100:
        return None, None, 0, "NO_DATA"
    
    try:
        logging.info(f"🔧 ENHANCED SMC анализ запущен для {len(df)} свечей")
        
        # =============== ОСНОВНОЙ АНАЛИЗ (сохраняем структуру) ===============
        zones = find_supply_demand_zones(df)
        structure = find_market_structure(df)
        order_blocks = calculate_order_blocks_advanced(df)
        fibonacci = calculate_fibonacci_levels(df)
        trend_analysis = enhanced_trend_analysis(df)
        liquidity_levels = liquidity_analysis(df)
        pa_patterns = price_action_patterns(df)
        candle_time = get_candle_time_info()
        
        # =============== УЛУЧШЕННАЯ СИСТЕМА СКОРИНГА ===============
        current_price = df['close'].iloc[-1]
        buy_score = 0
        sell_score = 0
        signal_details = []
        
        # Базовые веса различных компонентов
        WEIGHTS = {
            'ZONE_STRONG': 3,
            'ZONE_MEDIUM': 2,
            'OB_STRONG': 3, 
            'OB_MEDIUM': 2,
            'TREND_ALIGNED': 2,
            'PATTERN_STRONG': 2,
            'PATTERN_MEDIUM': 1,
            'FIBONACCI': 1,
            'STRUCTURE': 2,
            'LIQUIDITY': 1
        }
        
        # =============== АНАЛИЗ ЗОН С НОВОЙ СИСТЕМОЙ ===============
        for zone in zones:
            zone_middle = (zone['top'] + zone['bottom']) / 2
            distance_pct = abs(current_price - zone_middle) / current_price
    
            if distance_pct <= 0.002:  # В пределах 0.2% от зоны
                zone_weight = WEIGHTS['ZONE_STRONG'] if zone['strength'] == 'STRONG' else WEIGHTS['ZONE_MEDIUM']
        
                # 🔥 ИСПРАВЛЕНИЕ: зоны должны работать только в свою сторону
                if zone['type'] == 'DEMAND' and current_price >= zone['bottom']:
                    # Зона спроса работает только для BUY сигналов
                    if trend_analysis['direction'] == 'BULLISH':
                        zone_weight += WEIGHTS['TREND_ALIGNED']
            
                    buy_score += zone_weight
                    signal_details.append(f"DEMAND_ZONE(+{zone_weight})")
            
            elif zone['type'] == 'SUPPLY' and current_price <= zone['top']:
                # Зона предложения работает только для SELL сигналов  
                if trend_analysis['direction'] == 'BEARISH':
                    zone_weight += WEIGHTS['TREND_ALIGNED']
            
                sell_score += zone_weight
                signal_details.append(f"SUPPLY_ZONE(+{zone_weight})")
        
        # =============== АНАЛИЗ ОРДЕР-БЛОКОВ ===============
        for ob in order_blocks:
            ob_range = ob['high'] - ob['low']
            in_ob_range = ob['low'] <= current_price <= ob['high']
            
            if in_ob_range:
                ob_weight = WEIGHTS['OB_STRONG'] if ob['strength'] == 'STRONG' else WEIGHTS['OB_MEDIUM']
                
                if ob['type'] == 'BULLISH_OB':
                    buy_score += ob_weight
                    signal_details.append(f"BULLISH_OB(+{ob_weight})")
                elif ob['type'] == 'BEARISH_OB':
                    sell_score += ob_weight  
                    signal_details.append(f"BEARISH_OB(+{ob_weight})")
        
        # =============== АНАЛИЗ СТРУКТУРЫ РЫНКА ===============
        if len(structure) >= 2:
            last_point = structure[-1]
            if last_point['type'] == 'HH' and trend_analysis['direction'] == 'BULLISH':
                buy_score += WEIGHTS['STRUCTURE']
                signal_details.append(f"HH_STRUCTURE(+{WEIGHTS['STRUCTURE']})")
            elif last_point['type'] == 'LL' and trend_analysis['direction'] == 'BEARISH':
                sell_score += WEIGHTS['STRUCTURE']
                signal_details.append(f"LL_STRUCTURE(+{WEIGHTS['STRUCTURE']})")
        
        # =============== PRICE ACTION ПАТТЕРНЫ ===============
        for pattern in pa_patterns:
            pattern_weight = WEIGHTS['PATTERN_STRONG'] if pattern['strength'] == 'STRONG' else WEIGHTS['PATTERN_MEDIUM']
            
            if 'BULLISH' in pattern['type']:
                buy_score += pattern_weight
                signal_details.append(f"{pattern['type']}(+{pattern_weight})")
            elif 'BEARISH' in pattern['type']:
                sell_score += pattern_weight
                signal_details.append(f"{pattern['type']}(+{pattern_weight})")
        
        # =============== ФИБОНАЧЧИ И ЛИКВИДНОСТЬ ===============
        for fib in fibonacci:
            if abs(current_price - fib["level"]) / current_price < 0.001:
                if fib["ratio"] in [38, 50, 61]:
                    # Фибо поддерживает текущий сигнал
                    if buy_score > sell_score:
                        buy_score += WEIGHTS['FIBONACCI']
                        signal_details.append(f"FIB_{fib['ratio']}(+{WEIGHTS['FIBONACCI']})")
                    elif sell_score > buy_score:
                        sell_score += WEIGHTS['FIBONACCI'] 
                        signal_details.append(f"FIB_{fib['ratio']}(+{WEIGHTS['FIBONACCI']})")
        
        # =============== ОПРЕДЕЛЕНИЕ СИГНАЛА ===============
        signal = None
        confidence = 0
        
        min_confidence_threshold = 3  # Минимальный порог для входа
        
        if buy_score > sell_score and buy_score >= min_confidence_threshold:
            signal = 'BUY'
            confidence = min(buy_score, 10)  # Ограничиваем максимум 10
        elif sell_score > buy_score and sell_score >= min_confidence_threshold:
            signal = 'SELL' 
            confidence = min(sell_score, 10)
        
        # =============== ФИНАЛЬНАЯ ПРОВЕРКА И ФИЛЬТРЫ ===============
        if signal:
            # Фильтр истощения (сохраняем ваш оригинальный)
            if is_exhausted_move(df, trend_analysis):
                logging.warning("⏸️ Движение истощено — пропускаем сигнал")
                return None, None, 0, "EXHAUSTED_MOVE"
            
            # Проверка качества тренда
            if (signal == 'BUY' and trend_analysis['direction'] == 'BEARISH' and 
                trend_analysis['strength'] == 'VERY_STRONG'):
                confidence = max(1, confidence - 2)  # Ослабляем сигнал против сильного тренда
                signal_details.append("AGAINST_STRONG_TREND(-2)")
            
            elif (signal == 'SELL' and trend_analysis['direction'] == 'BULLISH' and 
                  trend_analysis['strength'] == 'VERY_STRONG'):
                confidence = max(1, confidence - 2)
                signal_details.append("AGAINST_STRONG_TREND(-2)")
            
            # Временная корректировка (сохраняем вашу логику)
            if candle_time['is_beginning']:
                confidence = max(1, confidence - 1)
                signal_details.append("EARLY_CANDLE(-1)")
            elif candle_time['is_ending']:
                confidence = min(10, confidence + 1)
                signal_details.append("LATE_CANDLE(+1)")
            
            # Рассчет экспирации
            expiry = calculate_dynamic_expiry(df, confidence, "SMC_CONFLUENCE")
            
            logging.info(f"🎯 ENHANCED SMC СИГНАЛ: {signal} (conf:{confidence}, score:{buy_score}-{sell_score})")
            logging.info(f"📋 Детали: {', '.join(signal_details)}")
            
            return signal, expiry, confidence, "ENHANCED_SMART_MONEY"
        
        else:
            logging.info(f"❌ ENHANCED SMC: Нет сигнала (BUY:{buy_score}, SELL:{sell_score}, threshold:{min_confidence_threshold})")
            return None, None, 0, "NO_CONFIDENT_SIGNAL"
    
    except Exception as e:
        logging.error(f"💥 Ошибка ENHANCED SMC анализа: {e}")
        return None, None, 0, "SMC_ERROR"
    
# ===================== ML (SAFE + DYNAMIC FEATURES) =====================
import os
import json
import pickle
import numpy as np
import pandas as pd
import joblib
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import talib as ta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

# ---- Глобальные переменные из бота ----
ml_model = None
ml_scaler = None
model_info: Dict = {}

# Порог для перевода proba → сигнал (как было у тебя)
ML_PROBABILITY_THRESHOLD = float(os.getenv("ML_PROBA_THR", "0.55"))

# Пути артефактов
ML_MODEL_PATH = "ml_model.pkl"
ML_SCALER_PATH = "ml_scaler.pkl"
ML_INFO_PATH = "ml_info.json"       # история обучений (список)
ML_INFO_LAST = "ml_info_last.json"  # последняя запись
ML_FEATS_PKL = "ml_features_selected.pkl"

# Минимум данных
MIN_SAMPLES_TO_TRAIN = 100

# Если хочешь фиксировать top-K — поставь число; если 0 → возьмем длину из pkl/истории
TOP_K_FEATURES = 0  # 0 = использовать размер текущего списка фич из pkl/истории

# ===================== ВСПОМОГАТЕЛЬНОЕ =====================

def _safe_json_load(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _append_ml_info(entry: Dict):
    """История обучений как список."""
    try:
        data = _safe_json_load(ML_INFO_PATH)
        if isinstance(data, list):
            data.append(entry)
        elif isinstance(data, dict):
            data = [data, entry]
        else:
            data = [entry]
        with open(ML_INFO_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"⚠️ Не удалось обновить {ML_INFO_PATH}: {e}")

def _load_selected_features_fallback() -> List[str]:
    """Фоллбэк: читаем список признаков из pkl (если есть)."""
    try:
        if os.path.exists(ML_FEATS_PKL):
            with open(ML_FEATS_PKL, "rb") as f:
                obj = pickle.load(f)
            if isinstance(obj, dict):
                return list(obj.keys())
            return list(obj)
    except Exception as e:
        logging.warning(f"⚠️ Ошибка чтения {ML_FEATS_PKL}: {e}")
    return []

def _get_expected_feature_list() -> List[str]:
    """
    Главный источник правды: ml_info_last.json["feature_names"].
    Если нет — фоллбэк к ml_features_selected.pkl.
    """
    info = _safe_json_load(ML_INFO_LAST)
    if isinstance(info, dict) and isinstance(info.get("feature_names"), list):
        return info["feature_names"]
    return _load_selected_features_fallback()

def _vectorize_for_inference(ml_features: Dict[str, float], expected_features: List[str]) -> np.ndarray:
    """Собираем строку фич в точном порядке expected_features; отсутствующие → 0.0."""
    row = [float(ml_features.get(f, 0.0)) for f in expected_features]
    return np.asarray([row], dtype=float)

def load_ml_artifacts() -> bool:
    """Грузим модель, скейлер и последнюю запись model_info."""
    global ml_model, ml_scaler, model_info
    try:
        if os.path.exists(ML_MODEL_PATH) and os.path.exists(ML_SCALER_PATH):
            ml_model = joblib.load(ML_MODEL_PATH)
            ml_scaler = joblib.load(ML_SCALER_PATH)
        else:
            logging.warning("⚠️ ML артефакты не найдены. Обучите модель.")
            return False

        info = _safe_json_load(ML_INFO_LAST)
        if info is None:
            data = _safe_json_load(ML_INFO_PATH)
            if isinstance(data, list) and data:
                info = data[-1]
            elif isinstance(data, dict):
                info = data
        model_info = info or {}
        if not isinstance(model_info.get("feature_names", None), list):
            # всё равно дадим шанс инференсу через pkl-список
            model_info["feature_names"] = _load_selected_features_fallback()

        logging.info("✅ ML артефакты загружены")
        return True
    except Exception as e:
        logging.error(f"❌ Ошибка загрузки ML артефактов: {e}", exc_info=True)
        return False

# ===================== ПОДГОТОВКА ФИЧЕЙ (твоя расширенная версия) =====================
def prepare_ml_features(df):
    """Готовит полный словарь из 50+ ML-признаков для сделки и обучения (адаптировано)."""
    try:
        if df is None or len(df) < 100:
            return None

        close, high, low, volume = df['close'], df['high'], df['low'], df['tick_volume']
        features = {}

        # Базовые
        features['price'] = float(close.iloc[-1])
        features['volume'] = float(volume.iloc[-1]) if not volume.isna().all() else 0.0

        # RSI
        for period in [14, 21]:
            rsi = ta.RSI(close, timeperiod=period)
            features[f'rsi_{period}'] = float(rsi.iloc[-1]) if len(close) >= period and not rsi.isna().all() else 50.0

        # ATR + ratio
        atr = ta.ATR(high, low, close, timeperiod=14)
        if len(close) >= 14 and not atr.isna().all():
            features['atr'] = float(atr.iloc[-1])
            atr_50 = atr.rolling(50).mean()
            features['atr_ratio'] = float(atr.iloc[-1] / atr_50.iloc[-1]) if len(atr_50) > 0 and not pd.isna(atr_50.iloc[-1]) else 1.0
        else:
            features['atr'] = 0.0
            features['atr_ratio'] = 1.0

        # OBV + тренд
        try:
            obv = ta.OBV(close, volume)
            features['obv'] = float(obv.iloc[-1]) if not obv.isna().all() else 0.0
            features['obv_trend'] = float(obv.diff(5).iloc[-1]) if len(obv) > 5 and not pd.isna(obv.diff(5).iloc[-1]) else 0.0
        except Exception:
            features['obv'] = 0.0
            features['obv_trend'] = 0.0

        features['adx'] = float(ta.ADX(high, low, close, timeperiod=14).iloc[-1]) if len(close) >= 14 else 0.0

        # Изменения цены
        for period in [15, 30, 60]:
            if len(close) >= period:
                features[f'price_change_{period}m'] = float((close.iloc[-1] - close.iloc[-period]) / close.iloc[-period] * 100)
            else:
                features[f'price_change_{period}m'] = 0.0

        features['volatility'] = float(close.pct_change().std() * 100)

        # MACD
        try:
            macd, _, _ = ta.MACD(close, 12, 26, 9)
            features['macd'] = float(macd.iloc[-1]) if not macd.isna().all() else 0.0
        except Exception:
            features['macd'] = 0.0

        # Bollinger
        try:
            bb_u, _, bb_l = ta.BBANDS(close, timeperiod=20)
            if not bb_u.isna().all() and not bb_l.isna().all():
                bb_range = bb_u.iloc[-1] - bb_l.iloc[-1]
                features['bb_position'] = float((close.iloc[-1] - bb_l.iloc[-1]) / max(1e-9, bb_range))
            else:
                features['bb_position'] = 0.5
        except Exception:
            features['bb_position'] = 0.5

        # Свечные паттерны (упрощённо)
        try:
            co, ch, cl, cc = df['open'].iloc[-1], df['high'].iloc[-1], df['low'].iloc[-1], df['close'].iloc[-1]
            po, ph, pl, pc = df['open'].iloc[-2], df['high'].iloc[-2], df['low'].iloc[-2], df['close'].iloc[-2]
            features['bullish_engulfing'] = int(pc < po and cc > co and co < pc and cc > po)
            features['bearish_engulfing'] = int(pc > po and cc < co and co > pc and cc < po)
            if len(df) >= 4:
                soldiers = all([
                    df['close'].iloc[-3] > df['open'].iloc[-3],
                    df['close'].iloc[-2] > df['open'].iloc[-2],
                    df['close'].iloc[-1] > df['open'].iloc[-1],
                    df['close'].iloc[-1] > df['close'].iloc[-2],
                    df['close'].iloc[-2] > df['close'].iloc[-3]
                ])
                features['three_white_soldiers'] = int(soldiers)
            else:
                features['three_white_soldiers'] = 0
        except Exception:
            features['bullish_engulfing'] = 0
            features['bearish_engulfing'] = 0
            features['three_white_soldiers'] = 0

        # Расстояния до дневных экстремумов
        try:
            daily_high = high.tail(1440).max()
            daily_low = low.tail(1440).min()
            features['distance_to_daily_high'] = float((daily_high - close.iloc[-1]) / daily_high * 100) if daily_high > 0 else 50.0
            features['distance_to_daily_low'] = float((close.iloc[-1] - daily_low) / close.iloc[-1] * 100) if close.iloc[-1] > 0 else 50.0
            rng = daily_high - daily_low
            features['daily_range_position'] = float((close.iloc[-1] - daily_low) / rng) if rng > 0 else 0.5
        except Exception:
            features['distance_to_daily_high'] = 50.0
            features['distance_to_daily_low'] = 50.0
            features['daily_range_position'] = 0.5

        # --- SMC / уровни (требуют твоих функций; оставляем try/except, как у тебя)
        try:
            zones = find_supply_demand_zones(df)
            structure = find_market_structure(df)
            order_blocks = calculate_order_blocks_advanced(df)
            fibonacci = calculate_fibonacci_levels(df)
            pa_patterns = price_action_patterns(df)

            features['smc_zones_count'] = len(zones)
            features['smc_structure_count'] = len(structure)
            features['smc_ob_count'] = len(order_blocks)
            features['smc_fib_count'] = len(fibonacci)
            features['smc_patterns_count'] = len(pa_patterns)

            features['smc_has_demand_zone'] = int(any(z['type'] == 'DEMAND' for z in zones))
            features['smc_has_supply_zone'] = int(any(z['type'] == 'SUPPLY' for z in zones))
            features['smc_has_bullish_ob'] = int(any(ob['type'] == 'BULLISH_OB' for ob in order_blocks))
            features['smc_has_bearish_ob'] = int(any(ob['type'] == 'BEARISH_OB' for ob in order_blocks))
            features['smc_has_engulfing'] = int(any('ENGULFING' in p['type'] for p in pa_patterns))
            features['smc_has_pinbar'] = int(any('PIN' in p['type'] for p in pa_patterns))

            current_price = close.iloc[-1]
            round_info = detect_round_levels(current_price)
            features['smc_round_distance_pips'] = float(round_info['distance_pips'])
            features['smc_round_strength'] = {'WEAK': 0, 'MEDIUM': 1, 'STRONG': 2, 'VERY_STRONG': 3}.get(round_info['strength'], 0)
        except Exception:
            for key in [
                'smc_zones_count','smc_structure_count','smc_ob_count','smc_fib_count','smc_patterns_count',
                'smc_has_demand_zone','smc_has_supply_zone','smc_has_bullish_ob','smc_has_bearish_ob',
                'smc_has_engulfing','smc_has_pinbar','smc_round_distance_pips','smc_round_strength'
            ]:
                features[key] = 0

        # Горизонтальные уровни
        try:
            horizontal_levels = find_horizontal_levels(df)
            features['horizontal_levels_count'] = len(horizontal_levels)
            if horizontal_levels:
                closest_level = min(horizontal_levels, key=lambda x: abs(x['price'] - close.iloc[-1]))
                features['distance_to_horizontal_level'] = abs(closest_level['price'] - close.iloc[-1]) * 10000
                features['horizontal_level_strength'] = closest_level['touches']
                features['is_near_horizontal_level'] = int(features['distance_to_horizontal_level'] < 5)
            else:
                features['distance_to_horizontal_level'] = 100
                features['horizontal_level_strength'] = 0
                features['is_near_horizontal_level'] = 0
        except Exception:
            features['horizontal_levels_count'] = 0
            features['distance_to_horizontal_level'] = 100
            features['horizontal_level_strength'] = 0
            features['is_near_horizontal_level'] = 0

        # Время/свечи
        try:
            candle_time = get_candle_time_info()
            features['candle_seconds_remaining'] = candle_time['seconds_remaining']
            features['candle_seconds_passed'] = candle_time['seconds_passed']
            features['candle_completion_percent'] = candle_time['completion_percent']
            features['candle_is_beginning'] = int(candle_time['is_beginning'])
            features['candle_is_middle'] = int(candle_time['is_middle'])
            features['candle_is_ending'] = int(candle_time['is_ending'])

            current_candle = df.iloc[-1]
            features['candle_body_size'] = abs(current_candle['close'] - current_candle['open'])
            features['candle_range'] = current_candle['high'] - current_candle['low']
            features['candle_body_ratio'] = features['candle_body_size'] / max(1e-9, features['candle_range'])

            features['early_gap_signal'] = int(early_entry_strategy(df, candle_time, {'direction': 'NEUTRAL'})[0])
            features['closing_breakout_signal'] = int(closing_candle_strategy(df, candle_time, {'direction': 'NEUTRAL'})[0])
        except Exception:
            for key in [
                'candle_seconds_remaining','candle_seconds_passed','candle_completion_percent',
                'candle_is_beginning','candle_is_middle','candle_is_ending',
                'candle_body_size','candle_range','candle_body_ratio',
                'early_gap_signal','closing_breakout_signal'
            ]:
                features[key] = 0

        # Контекст
        features['exhaustion_rsi_extreme'] = int((features.get('rsi_14', 50) < 25) or (features.get('rsi_14', 50) > 75))

        # Импульс
        pc_key = 'price_change_15m' if 'price_change_15m' in features else 'price_change_60m'
        pc = features.get(pc_key, 0.0)
        if pc == 0 and len(df) >= 15:
            pc = float((close.iloc[-1] - close.iloc[-15]) / close.iloc[-15] * 100)
        features['strong_impulse'] = int(abs(pc) > 0.3)

        volume_avg_20 = df['tick_volume'].tail(20).mean() if 'tick_volume' in df.columns else 1
        current_volume = df['tick_volume'].iloc[-1] if 'tick_volume' in df.columns else 1
        features['volume_declining'] = int(current_volume < (volume_avg_20 * 0.8))

        features['signal_vs_trend_conflict'] = 0
        features['signal_vs_rsi_conflict'] = 0

        # Чистим NaN
        for k, v in list(features.items()):
            if pd.isna(v):
                features[k] = 0.0

        return features
    except Exception as e:
        logging.error(f"Ошибка ML features: {e}", exc_info=True)
        return None

# ===================== ИНФЕРЕНС (БЕЗОПАСНЫЙ) =====================
def ml_predict_proba_safe(ml_features: Dict[str, float]) -> Optional[float]:
    """Вероятность WIN (0..1). Никогда не падает из-за несовпадения признаков."""
    try:
        global ml_model, ml_scaler, model_info
        if ml_model is None or ml_scaler is None:
            if not load_ml_artifacts():
                return None

        expected = model_info.get("feature_names", []) or _get_expected_feature_list()
        if not expected:
            logging.warning("⚠️ feature_names отсутствуют — инференс пропущен")
            return None

        X_raw = _vectorize_for_inference(ml_features or {}, expected)
        X = ml_scaler.transform(X_raw)
        if hasattr(ml_model, "predict_proba"):
            return float(ml_model.predict_proba(X)[0, 1])
        return float(ml_model.predict(X)[0])
    except Exception as e:
        logging.error(f"❌ Ошибка ML инференса: {e}", exc_info=True)
        return None

def ml_predict_enhanced(features_dict: dict, pair: str, current_price: float):
    """
    Совместимая обёртка под старый интерфейс:
    возвращает dict {probability, confidence, signal, ...}
    """
    try:
        proba = ml_predict_proba_safe(features_dict)
        if proba is None:
            return {"probability": 0.5, "confidence": 0.0, "signal": None}

        # Уверенность как расстояние от 0.5 (0..1)
        confidence_score = float(abs(proba - 0.5) * 2.0)

        signal = None
        if proba >= ML_PROBABILITY_THRESHOLD:
            signal = "BUY"
        elif proba <= (1.0 - ML_PROBABILITY_THRESHOLD):
            signal = "SELL"

        logging.info(f"🤖 ML {pair}: proba={proba:.3f}, conf={confidence_score:.3f}, signal={signal}")
        return {
            "probability": proba,
            "confidence": confidence_score,
            "signal": signal,
            "price": current_price,
        }
    except Exception as e:
        logging.error(f"❌ Ошибка ml_predict_enhanced для {pair}: {e}", exc_info=True)
        return {"probability": 0.5, "confidence": 0.0, "signal": None}

# ===================== ВАЛИДАЦИЯ СИГНАЛА (оставлено совместимым) =====================
def validate_ml_signal_with_context(ml_result, trend_analysis, pair):
    """Валидирует ML-сигнал с учётом тренда/RSI/импульса."""
    if not ml_result or not ml_result.get('signal'):
        return ml_result

    signal = ml_result['signal']
    confidence = ml_result['confidence']

    # Против тренда
    if (signal == 'BUY' and trend_analysis['direction'] == 'BEARISH' and 
        trend_analysis['strength'] in ['STRONG', 'VERY_STRONG']):
        confidence *= 0.5
        logging.info(f"⚠️ ML: BUY против сильного медвежьего тренда ({pair})")
    elif (signal == 'SELL' and trend_analysis['direction'] == 'BULLISH' and 
          trend_analysis['strength'] in ['STRONG', 'VERY_STRONG']):
        confidence *= 0.5
        logging.info(f"⚠️ ML: SELL против сильного бычьего тренда ({pair})")

    # RSI экстремумы
    if signal == 'BUY' and trend_analysis['rsi_state'] == 'OVERBOUGHT':
        confidence *= 0.6
        logging.info(f"⚠️ ML: BUY в зоне перекупленности ({pair})")
    elif signal == 'SELL' and trend_analysis['rsi_state'] == 'OVERSOLD':
        confidence *= 0.6
        logging.info(f"⚠️ ML: SELL в зоне перепроданности ({pair})")

    # Импульс
    if trend_analysis.get('is_strong_impulse', False):
        impulse_dir = trend_analysis.get('impulse_direction')
        if impulse_dir and signal != impulse_dir:
            confidence *= 0.4
            logging.info(f"⚠️ ML: сигнал против сильного импульса ({pair})")

    ml_result['confidence'] = confidence
    ml_result['validated'] = confidence >= 0.3
    return ml_result

# ===================== ФИЛЬТР ВХОДА (оставлено совместимым) =====================
def should_take_trade(pair: str, smc_signal: dict, ml_result: dict, rsi_value: float, trends: dict) -> bool:
    """Комбинированный фильтр входа в сделку."""
    try:
        smc_conf = smc_signal.get('confidence', 0) if (smc_signal and smc_signal.get('signal')) else 0
        smc_dir = smc_signal.get('signal') if smc_signal else None

        ml_dir = ml_result.get('signal') if ml_result else None
        ml_conf = ml_result.get('confidence', 0) if ml_result else 0
        ml_valid = ml_result.get('validated', False) if ml_result else False

        rsi_overbought = rsi_value >= 70
        rsi_oversold = rsi_value <= 30

        major_trend = trends.get('M30', 'NEUTRAL')
        minor_trend = trends.get('M5', 'NEUTRAL')

        # Отсеиваем слабые
        if smc_conf < 4 and (ml_conf < 0.15 or not ml_valid):
            return False

        # Сильный SMC + ML не против
        if smc_dir and smc_conf >= 6:
            if ml_dir is None or ml_dir == smc_dir:
                return True

        # Уверенный ML + контекст
        if ml_valid and ml_conf >= 0.25:
            if ml_dir == 'BUY' and (minor_trend == 'BULLISH' or major_trend == 'BULLISH') and not rsi_overbought:
                return True
            if ml_dir == 'SELL' and (minor_trend == 'BEARISH' or major_trend == 'BEARISH') and not rsi_oversold:
                return True

        if ml_dir == 'BUY' and rsi_overbought:
            return False
        if ml_dir == 'SELL' and rsi_oversold:
            return False

        return False
    except Exception as e:
        logging.error(f"[FILTER] Ошибка фильтрации сигнала для {pair}: {e}")
        return False

# ===================== ⚙️ REPAIR ML FEATURES (ASYNC-SAFE) =====================
async def repair_ml_features():
    """Помечает сделки для пересчета ml_features, без фейковых значений (асинхронная версия)."""
    try:
        needs_repair_count = 0
        if MULTI_USER_MODE:
            for user_id, user_data in users.items():
                for trade in user_data.get('trade_history', []):
                    if not trade.get('ml_features') and trade.get('pair'):
                        trade['needs_ml_recalculation'] = True
                        needs_repair_count += 1
        else:
            for trade in single_user_data.get('trade_history', []):
                if not trade.get('ml_features') and trade.get('pair'):
                    trade['needs_ml_recalculation'] = True
                    needs_repair_count += 1

        if needs_repair_count > 0:
            await async_save_users_data()  # 🔄 теперь безопасно и не блокирует event loop
            logging.info(f"🔧 Помечено {needs_repair_count} сделок для пересчета ml_features")

        return needs_repair_count

    except Exception as e:
        logging.error(f"❌ Ошибка восстановления ml_features: {e}")
        return 0

# ===================== TELEGRAM COMMAND: /repairml =====================
from telegram import Update
from telegram.ext import ContextTypes

async def repair_ml_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда Telegram /repairml — восстанавливает отсутствующие ml_features для сделок"""
    user_id = update.effective_user.id

    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору.")
        return

    await update.message.reply_text("🔄 Запускаю восстановление ml_features для всех сделок...")

    repaired_count = repair_ml_features()

    if repaired_count > 0:
        await update.message.reply_text(
            f"✅ Обновлено ml_features для {repaired_count} сделок!\n"
            f"🚀 Теперь можно запустить /forcetrain для переобучения модели."
        )
    else:
        await update.message.reply_text("ℹ️ Все сделки уже содержат ml_features, восстановление не требуется.")


# ===================== 🧠 ОБНОВЛЁННЫЙ БЛОК ОБУЧЕНИЯ ML (RandomForest + MLPClassifier + Oversampling) =====================
def train_ml_model():
    """
    Устойчивое обучение:
    - time-based split
    - RandomForest и MLPClassifier (сравнение)
    - oversampling для балансировки классов WIN/LOSS
    - выбор фич: из pkl/истории или по важности (top-K)
    - сохраняем победившую модель + метаинформацию
    """
    global ml_model, ml_scaler, model_info

    try:
        # ========== 1️⃣ СБОР ДАННЫХ ==========
        all_trades = []
        if MULTI_USER_MODE:
            for user_data in users.values():
                all_trades.extend(user_data.get('trade_history', []))
            logging.info(f"📊 ML: собрано {len(all_trades)} сделок из {len(users)} пользователей")
        else:
            all_trades.extend(single_user_data.get('trade_history', []))
            logging.info(f"📊 ML: собрано {len(all_trades)} сделок из одного пользователя")

        completed = [
            t for t in all_trades
            if t.get('result') in ('WIN', 'LOSS')
            and isinstance(t.get('ml_features'), dict)
        ]
        if len(completed) < MIN_SAMPLES_TO_TRAIN:
            logging.warning(f"⚠ Недостаточно данных для обучения: {len(completed)} < {MIN_SAMPLES_TO_TRAIN}")
            return

        # ========== 2️⃣ ФОРМИРОВАНИЕ ФИЧ ==========
        base_feature_names = None
        for t in reversed(completed[-400:]):
            feats = t.get('ml_features')
            if isinstance(feats, dict) and len(feats) >= 10:
                base_feature_names = list(feats.keys())
                break
        if not base_feature_names:
            logging.warning("❌ Нет сделок с ml_features — обучение невозможно")
            return

        X, y, ts = [], [], []
        for tr in completed:
            feats = tr.get('ml_features', {})
            X.append([float(feats.get(f, 0.0)) for f in base_feature_names])
            y.append(1 if tr.get('result') == 'WIN' else 0)
            ts.append(tr.get('timestamp', None))

        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=int)
        ts = pd.to_datetime(pd.Series(ts), errors='coerce').astype('int64').fillna(0).to_numpy()

        # ========== ⚖️ 3️⃣ БАЛАНСИРОВКА КЛАССОВ (oversampling) ==========
        from sklearn.utils import resample
        X_df = pd.DataFrame(X, columns=base_feature_names)
        y_df = pd.Series(y, name='target')
        df_balanced = pd.concat([X_df, y_df], axis=1)

        minority = df_balanced[df_balanced.target == 1]
        majority = df_balanced[df_balanced.target == 0]

        # oversampling только если WIN сильно меньше
        if len(minority) / len(majority) < 0.8:
            minority_upsampled = resample(
                minority,
                replace=True,
                n_samples=len(majority),
                random_state=42
            )
            df_balanced = pd.concat([majority, minority_upsampled])
            logging.info(f"⚖️ Балансировка классов: WIN {len(minority)} → {len(minority_upsampled)}")
        else:
            logging.info("⚖️ Балансировка не требуется — классы сбалансированы")

        # обновляем X и y после балансировки
        X = df_balanced[base_feature_names].values
        y = df_balanced["target"].values

        # ========== 4️⃣ TIME-BASED SPLIT ==========
        order = np.argsort(ts[:len(X)])  # сортируем по времени
        X, y = X[order], y[order]
        split_idx = int(len(X) * 0.75)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        logging.info(f"🕒 Time-based split: train={len(X_train)}, test={len(X_test)}")

        # ========== 5️⃣ МАСШТАБИРОВАНИЕ ==========
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        # ========== 6️⃣ RANDOM FOREST ==========
        params = {
            'n_estimators': 250,
            'max_depth': 7,
            'min_samples_split': 15,
            'min_samples_leaf': 6,
            'max_features': 0.6,
            'max_samples': 0.85,
            'min_weight_fraction_leaf': 0.00,
            'random_state': 42,
            'class_weight': 'balanced_subsample',
            'n_jobs': -1,
        }
        base_model = RandomForestClassifier(**params)
        base_model.fit(X_train_s, y_train)

        # оценка
        train_acc = accuracy_score(y_train, base_model.predict(X_train_s))
        test_acc = accuracy_score(y_test, base_model.predict(X_test_s))
        overfit_ratio = train_acc / max(test_acc, 1e-6)

        # ========== 7️⃣ ВЫБОР ПРИЗНАКОВ ==========
        preserved = _get_expected_feature_list()
        if preserved:
            selected_features = [f for f in preserved if f in base_feature_names]
            logging.info(f"📝 Используем сохранённый список признаков: {len(selected_features)} шт.")
        else:
            importances = base_model.feature_importances_
            pairs = list(zip(base_feature_names, importances))
            pairs.sort(key=lambda x: x[1], reverse=True)
            k = min(TOP_K_FEATURES or len(pairs), len(pairs))
            selected_features = [f for f, _ in pairs[:k]]
            logging.info(f"🏆 Выбраны top-{len(selected_features)} признаков по важности")

        idx = {f: i for i, f in enumerate(base_feature_names)}
        cols = [idx[f] for f in selected_features if f in idx]
        X_train_top = X_train[:, cols]
        X_test_top = X_test[:, cols]

        scaler2 = StandardScaler()
        X_train_top_s = scaler2.fit_transform(X_train_top)
        X_test_top_s = scaler2.transform(X_test_top)

        model_rf = RandomForestClassifier(**params)
        model_rf.fit(X_train_top_s, y_train)

        y_tr2 = model_rf.predict(X_train_top_s)
        y_te2 = model_rf.predict(X_test_top_s)
        train_acc2 = accuracy_score(y_train, y_tr2)
        test_acc2 = accuracy_score(y_test, y_te2)
        f12 = f1_score(y_test, y_te2, zero_division=0)
        overfit_ratio2 = train_acc2 / max(test_acc2, 1e-6)

        folds = min(5, max(2, len(X_train_top_s)//400))
        try:
            cv_scores = cross_val_score(model_rf, X_train_top_s, y_train, cv=folds, scoring='accuracy')
            cv_mean, cv_std = float(np.mean(cv_scores)), float(np.std(cv_scores))
        except Exception as e:
            logging.warning(f"CV пропущен: {e}")
            cv_mean, cv_std = float('nan'), float('nan')

        logging.info(f"✅ RandomForest: Test={test_acc2:.3f} | Train={train_acc2:.3f} | Overfit={overfit_ratio2:.2f}")

        # ========== 8️⃣ MLP CLASSIFIER ==========
        from sklearn.neural_network import MLPClassifier
        try:
            mlp = MLPClassifier(
                hidden_layer_sizes=(64, 32),
                activation='tanh',
                solver='adam',
                learning_rate_init=0.001,
                max_iter=400,
                random_state=42,
                early_stopping=True,
                n_iter_no_change=10,
                validation_fraction=0.15,
            )
            mlp.fit(X_train_top_s, y_train)

            y_pred_mlp_train = mlp.predict(X_train_top_s)
            y_pred_mlp_test = mlp.predict(X_test_top_s)

            train_acc_mlp = accuracy_score(y_train, y_pred_mlp_train)
            test_acc_mlp = accuracy_score(y_test, y_pred_mlp_test)
            overfit_mlp = train_acc_mlp / max(test_acc_mlp, 1e-6)

            folds_mlp = min(5, max(2, len(X_train_top_s)//400))
            try:
                cv_scores_mlp = cross_val_score(mlp, X_train_top_s, y_train, cv=folds_mlp, scoring='accuracy')
                cv_mean_mlp, cv_std_mlp = float(np.mean(cv_scores_mlp)), float(np.std(cv_scores_mlp))
            except Exception as e:
                logging.warning(f"CV (MLP) пропущен: {e}")
                cv_mean_mlp, cv_std_mlp = float('nan'), float('nan')

            logging.info(f"🤖 MLPClassifier: Test={test_acc_mlp:.3f} | Train={train_acc_mlp:.3f} | Overfit={overfit_mlp:.2f}")

            # ========== 9️⃣ СРАВНЕНИЕ ==========
            if test_acc_mlp > test_acc2:
                best_model = mlp
                best_scaler = scaler2
                best_type = "MLPClassifier"
                best_test_acc = test_acc_mlp
                best_train_acc = train_acc_mlp
                best_cv = cv_mean_mlp
                best_overfit = overfit_mlp
                logging.info(f"🏆 Выбрана модель: MLPClassifier (Test={best_test_acc:.3f}) > RandomForest (Test={test_acc2:.3f})")
            else:
                best_model = model_rf
                best_scaler = scaler2
                best_type = "RandomForestClassifier"
                best_test_acc = test_acc2
                best_train_acc = train_acc2
                best_cv = cv_mean
                best_overfit = overfit_ratio2
                logging.info(f"🏆 Выбрана модель: RandomForestClassifier (Test={test_acc2:.3f}) ≥ MLP (Test={test_acc_mlp:.3f})")

        except Exception as e:
            logging.error(f"❌ Ошибка при обучении MLPClassifier: {e}", exc_info=True)
            best_model = model_rf
            best_scaler = scaler2
            best_type = "RandomForestClassifier"
            best_test_acc = test_acc2
            best_train_acc = train_acc2
            best_cv = cv_mean
            best_overfit = overfit_ratio2

        # ========== 🔟 СОХРАНЕНИЕ ==========
        joblib.dump(best_model, ML_MODEL_PATH)
        joblib.dump(best_scaler, ML_SCALER_PATH)

        win_rate_overall = float(np.mean(y)) * 100.0

        model_info = {
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "n_features": len(selected_features),
            "trades_used": int(len(X)),
            "train_accuracy": round(best_train_acc * 100, 2),
            "test_accuracy": round(best_test_acc * 100, 2),
            "cv_accuracy": round(best_cv * 100, 2) if not np.isnan(best_cv) else None,
            "overfitting_ratio": round(best_overfit, 2),
            "feature_names": selected_features,
            "train_samples": int(len(y_train)),
            "test_samples": int(len(y_test)),
            "win_rate": round(win_rate_overall, 2),
            "model_type": best_type
        }

        with open(ML_INFO_LAST, "w", encoding="utf-8") as f:
            json.dump(model_info, f, ensure_ascii=False, indent=2)
        _append_ml_info(model_info)

        ml_model, ml_scaler = best_model, best_scaler
        logging.info(f"✅ Финальная модель: {best_type} | Test={best_test_acc:.3f} | Train={best_train_acc:.3f}")

        return model_info

    except Exception as e:
        logging.error(f"❌ Ошибка обучения ML: {e}", exc_info=True)

# ===================== (опционально) МЯГКИЙ БУСТ УВЕРЕННОСТИ =====================
# Если пользуешься комплексной шкалой уверенности SMC/GPT, можно вызывать это место:
ML_CONF_THRESHOLDS = {"boost2": 0.62, "boost1": 0.58, "cut1": 0.45, "cut2": 0.40}
ML_CONF_MAX_ABS_DELTA = 2
ML_CONF_MIN_BASE = 4
ML_CONF_MAX_BASE = 9

def apply_ml_confidence_boost(base_conf: int, ml_features: Dict[str, float]) -> Tuple[int, Optional[float], str]:
    """Мягко корректирует уверенность на основе ML proba (не ломая SMC/GPT)."""
    proba = ml_predict_proba_safe(ml_features)
    if proba is None:
        return base_conf, None, "ML:skip"

    conf = int(base_conf)
    delta = 0
    if proba >= ML_CONF_THRESHOLDS["boost2"] and conf >= ML_CONF_MIN_BASE and conf < ML_CONF_MAX_BASE:
        delta = min(2, ML_CONF_MAX_ABS_DELTA)
    elif proba >= ML_CONF_THRESHOLDS["boost1"]:
        delta = min(1, ML_CONF_MAX_ABS_DELTA)
    elif proba <= ML_CONF_THRESHOLDS["cut2"]:
        delta = -min(2, ML_CONF_MAX_ABS_DELTA)
    elif proba <= ML_CONF_THRESHOLDS["cut1"]:
        delta = -min(1, ML_CONF_MAX_ABS_DELTA)

    new_conf = max(0, min(10, conf + delta))
    expl = f"ML:{proba:.2f}"
    if delta != 0:
        expl += f" Δ{delta:+d}"
    return new_conf, proba, expl

# ===================== GPT ANALYSIS =====================
def gpt_full_market_read(pair: str, df_m1: pd.DataFrame, df_m5: pd.DataFrame):
    """GPT-анализ с улучшенной логикой времени экспирации (1-4 минуты)"""
    try:
        if df_m1 is None or len(df_m1) < 100:
            return None, None
            
        # Берем 400 свечей M1 для анализа
        candles = df_m1.tail(400)[['open','high','low','close','tick_volume']].round(5)
        candles = candles.to_dict(orient='records')
        
        # Анализируем волатильность для определения времени экспирации
        current_price = df_m1['close'].iloc[-1]
        atr = ta.ATR(df_m1['high'], df_m1['low'], df_m1['close'], timeperiod=14).iloc[-1]
        volatility_percent = (atr / current_price) * 100 if current_price > 0 else 0
        
        # Определяем базовое время экспирации по волатильности (как в SMC)
        if volatility_percent >= 0.035:
            base_expiry = 1
        elif volatility_percent >= 0.02:
            base_expiry = 2
        elif volatility_percent >= 0.01:
            base_expiry = 3
        else:
            base_expiry = 4
            
        # Ограничиваем 1-4 минутами как в SMC
        base_expiry = max(1, min(base_expiry, 4))

        prompt = f"""
Ты профессиональный трейдер бинарных опционов. Проанализируй последние 400 свечей M1 (6.5 часа данных) для пары {pair}.

КРИТЕРИИ АНАЛИЗА:
1. Определи общий тренд (бычий/медвежий/флэт)
2. Найди ключевые уровни поддержки/сопротивления  
3. Проанализируй объемы на ключевых движениях
4. Оцени силу текущего движения
5. Определи потенциальные точки входа

ВАЖНО: Время экспирации должно быть от 1 до 4 минут. Текущая волатильность: {volatility_percent:.4f}% - рекомендуется {base_expiry} мин.

Ответ строго в формате JSON: {{"decision":"BUY/SELL/WAIT","expiry":1-4,"confidence":1-10,"reason":"краткое обоснование"}}

Данные свечей (первые 50 из 400): {json.dumps(candles[:50], ensure_ascii=False)}
"""
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"Ты профессиональный трейдер. Отвечай только JSON."},
                      {"role":"user","content":prompt}],
            temperature=0.1,
            timeout=45
        )
        
        text = resp.choices[0].message.content.strip()
        if "```" in text:
            text = text.replace("```json","").replace("```","").strip()
            
        if "{" in text and "}" in text:
            json_str = text[text.find("{"):text.rfind("}")+1]
            try:
                data = json.loads(json_str)
                decision = data.get("decision")
                expiry = data.get("expiry", base_expiry)
                confidence = data.get("confidence", 5)
                
                # Ограничиваем экспирацию 1-4 минутами как в SMC
                expiry = max(1, min(expiry, 4))
                
                if decision in ["BUY","SELL"] and confidence >= 6:
                    return decision, expiry
                return None, None
            except:
                return None, None
        return None, None
        
    except Exception as e:
        logging.warning(f"GPT error: {e}")
        return None, None
# ===================== ROUND LEVELS DETECTION =====================
def detect_round_levels(price: float, pip_distance: float = 0.0050) -> dict:
    """УЛУЧШЕННОЕ определение круглых уровней"""
    # Определяем разряд цены для поиска круглых уровней
    if price >= 100:
        # Для JPY пар
        round_levels = [
            round(price / 5) * 5 - 10,  # Ближайшие уровни
            round(price / 5) * 5 - 5,
            round(price / 5) * 5,
            round(price / 5) * 5 + 5,
            round(price / 5) * 5 + 10
        ]
        threshold = 1.0  # 100 пипсов для JPY
    elif price >= 1.0:
        # Для основных пар
        base = int(price)
        round_levels = []
        for i in range(base - 2, base + 3):
            round_levels.extend([
                i + 0.0000,
                i + 0.1000,
                i + 0.2000, 
                i + 0.3000,
                i + 0.4000,
                i + 0.5000,
                i + 0.6000,
                i + 0.7000,
                i + 0.8000,
                i + 0.9000
            ])
        threshold = 0.0020  # 20 пипсов
    else:
        # Для экзотических пар
        round_levels = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        threshold = 0.0020
    
    # Находим ближайший круглый уровень
    closest_level = min(round_levels, key=lambda x: abs(x - price))
    distance = abs(price - closest_level)
    distance_pips = distance * 10000
    
    # УЛУЧШЕННАЯ логика силы
    if distance <= threshold * 0.1:
        strength = "VERY_STRONG"
        confidence_boost = 3
    elif distance <= threshold * 0.3:
        strength = "STRONG" 
        confidence_boost = 2
    elif distance <= threshold * 0.6:
        strength = "MEDIUM"
        confidence_boost = 1
    else:
        strength = "WEAK"
        confidence_boost = 0
    
    return {
        "closest_level": closest_level,
        "distance": distance,
        "distance_pips": distance_pips,
        "strength": strength,
        "confidence_boost": confidence_boost,
        "is_near_round": distance <= threshold
    }


def log_trade_to_file(trade: dict, result: str = None):
    """
    Записывает каждую сделку в отдельный лог-файл для анализа
    """
    try:
        log_entry = {
            "timestamp": trade.get('timestamp', datetime.now().isoformat()),
            "pair": trade.get('pair'),
            "direction": trade.get('direction'),
            "entry_price": trade.get('entry_price'),
            "exit_price": trade.get('exit_price'),
            "stake": trade.get('stake'),
            "result": result or trade.get('result'),
            "profit": trade.get('profit'),
            "source": trade.get('source'),
            "confidence": trade.get('confidence'),
            "ml_probability": trade.get('ml_features', {}).get('ml_probability') if isinstance(trade.get('ml_features'), dict) else None,
            "ml_confidence": trade.get('ml_features', {}).get('ml_confidence') if isinstance(trade.get('ml_features'), dict) else None,
            "round_level": trade.get('ml_features', {}).get('round_level_info', {}).get('closest_level') if isinstance(trade.get('ml_features'), dict) else None,
            "round_distance": trade.get('ml_features', {}).get('round_level_info', {}).get('distance_pips') if isinstance(trade.get('ml_features'), dict) else None,
            "expiry_minutes": trade.get('expiry_minutes')
        }
        
        # Записываем в CSV
        log_file = "trades_log.csv"
        file_exists = os.path.exists(log_file)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            if not file_exists:
                headers = ",".join(log_entry.keys())
                f.write(headers + "\n")
            
            values = ",".join(str(v) if v is not None else "" for v in log_entry.values())
            f.write(values + "\n")
            
        logging.info(f"✅ Сделка залогирована в {log_file}")
        
    except Exception as e:
        logging.error(f"Ошибка логирования сделки: {e}")
        
# ===================== ANALYZE PAIR =====================
def get_mt5_data(symbol: str, n: int, timeframe) -> Optional[pd.DataFrame]:
    """Получает исторические котировки из MT5"""
    try:
        if not mt5.terminal_info():
            logging.error("MT5 терминал не подключен")
            return None

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
        if rates is None or len(rates) == 0:
            logging.warning(f"Нет данных для {symbol}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        return df

    except Exception as e:
        logging.error(f"Ошибка получения данных MT5: {e}")
        return None

def analyze_trend(df, timeframe_name="M1"):
    """Определяет тренд на заданном таймфрейме"""
    if df is None or len(df) < 50:
        return "NEUTRAL"
    
    try:
        # Анализ по EMA для лучшего определения тренда
        ema_10 = ta.EMA(df['close'], timeperiod=10).iloc[-1]
        ema_20 = ta.EMA(df['close'], timeperiod=20).iloc[-1]
        ema_50 = ta.EMA(df['close'], timeperiod=50).iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # Многопараметрический анализ тренда
        bullish_signals = 0
        bearish_signals = 0
        
        # Цена относительно EMA
        if current_price > ema_10 > ema_20 > ema_50:
            bullish_signals += 2
        elif current_price < ema_10 < ema_20 < ema_50:
            bearish_signals += 2
        
        # Наклон EMA
        ema_10_prev = ta.EMA(df['close'], timeperiod=10).iloc[-2] if len(df) > 10 else ema_10
        if ema_10 > ema_10_prev:
            bullish_signals += 1
        else:
            bearish_signals += 1
        
        # Определение тренда
        if bullish_signals - bearish_signals >= 2:
            trend = "BULLISH"
        elif bearish_signals - bullish_signals >= 2:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"
            
        logging.debug(f"📈 {timeframe_name} тренд: {trend} (bullish:{bullish_signals}, bearish:{bearish_signals})")
        return trend
        
    except Exception as e:
        logging.warning(f"Ошибка анализа тренда на {timeframe_name}: {e}")
        return "NEUTRAL"

def is_against_strong_trend(signal, trend_analysis):
    """Проверка сигнала против сильного тренда"""
    if trend_analysis['strength'] in ['VERY_STRONG', 'STRONG']:
        if (signal == 'BUY' and trend_analysis['direction'] == 'BEARISH') or \
           (signal == 'SELL' and trend_analysis['direction'] == 'BULLISH'):
            return True
    return False

def analyze_pair(pair: str):
    try:

        global ml_model, ml_scaler, ml_features_count
        # 🕒 ПРОВЕРЯЕМ ФИКСИРОВАННЫЙ ГРАФИК РАБОТЫ БОТА
        if not is_trading_time():
            logging.info(f"⏸ Вне рабочего времени бота — пропускаем анализ {pair}")
            return None, None, 0, "OUT_OF_SCHEDULE", None
        
        logging.info(f"🔍 Начало анализа пары: {pair}")

        # 1️⃣ Получаем данные
        df_m1 = get_mt5_data(pair, 400, mt5.TIMEFRAME_M1)
        df_m5 = get_mt5_data(pair, 200, mt5.TIMEFRAME_M5)
        df_m15 = get_mt5_data(pair, 100, mt5.TIMEFRAME_M15)
        df_m30 = get_mt5_data(pair, 80, mt5.TIMEFRAME_M30)
        if df_m1 is None or df_m5 is None:
            logging.warning(f"⚠ Нет данных для {pair}")
            return None, None, 0, "NO_DATA", None

        current_price = df_m1['close'].iloc[-1]
        logging.info(f"💰 {pair}: текущая цена = {current_price:.5f}")

        # 2️⃣ Тренды и уровни
        trend_analysis = enhanced_trend_analysis(df_m1)
        m5_trend = analyze_trend(df_m5, "M5")
        m15_trend = analyze_trend(df_m15, "M15")
        m30_trend = analyze_trend(df_m30, "M30")
        round_info = detect_round_levels(current_price)
        logging.info(f"📊 Тренды M5={m5_trend}, M15={m15_trend}, M30={m30_trend}")
        logging.info(f"🎯 Круглый уровень: {round_info['closest_level']} сила={round_info['strength']}")

        # 3️⃣ Подготовка ML фичей (42 признака)
        ml_enabled_for_this_pair = ML_ENABLED
        if ML_ENABLED and (ml_model is None or ml_scaler is None):
            initialize_ml_model()
            if ml_model is None or ml_scaler is None:
                ml_enabled_for_this_pair = False
                logging.warning(f"⏭ {pair}: ML анализ пропущен - модель недоступна")

        ml_features_dict = prepare_ml_features(df_m1)
        ml_features_data = None
        feats_array = None

        if ml_features_dict is not None:
            # 🧠 Сохраняем словарь для истории сделки
            ml_features_data = ml_features_dict.copy()

            # ➡️ Преобразуем dict → array для подачи в ML модель
            feature_names = list(ml_features_dict.keys())
            feats_array = np.array([ml_features_dict[f] for f in feature_names]).reshape(1, -1)
            ml_features_data['round_level_info'] = round_info

            logging.info(f"📊 {pair}: подготовлены {len(feature_names)} ML фичей")

        # 4️⃣ Анализ источников сигналов
        smc_result = {
            "signal": None,
            "confidence": 0,
            "expiry": None,
            "source": "SMC"
        }
        ml_result = None
        gpt_result = None

        # --- SMC ---
        smc_signal, smc_expiry, smc_conf, smc_source = enhanced_smart_money_analysis(df_m1)
        if smc_signal and smc_conf >= 4:
            smc_result.update({"signal": smc_signal, "confidence": smc_conf, "expiry": smc_expiry})
            logging.info(f"✅ {pair}: SMC сигнал = {smc_signal} (conf={smc_conf})")

        # --- ML ---
        if ml_enabled_for_this_pair and feats_array is not None:
            try:
                # 🔧 ДОБАВЬ ЭТОТ БЛОК ДЛЯ ИСПРАВЛЕНИЯ SCALER
                current_feature_count = feats_array.shape[1]
                if (ml_scaler is not None and 
                    hasattr(ml_scaler, 'n_features_in_') and 
                    ml_scaler.n_features_in_ != current_feature_count):
            
                    logging.warning(f"🔄 Размерность не совпадает: scaler={ml_scaler.n_features_in_}, данные={current_feature_count}")
                    logging.info("🔄 Пересоздаю scaler с правильной размерностью...")
            
                    # ПЕРЕСОЗДАЕМ SCALER С ПРАВИЛЬНОЙ РАЗМЕРНОСТЬЮ
                    ml_scaler = StandardScaler()
                    ml_scaler.fit(feats_array)  # Обучаем на текущих данных
        
                # ✅ ТЕПЕРЬ ЭТА СТРОКА БУДЕТ РАБОТАТЬ БЕЗ ОШИБОК
                feats_scaled = ml_scaler.transform(feats_array)
        
                ml_pred = ml_model.predict_proba(feats_scaled)[0][1]
                ml_confidence = round(ml_pred * 100, 1)
                ml_signal = "BUY" if ml_pred >= 0.5 else "SELL"

                ml_result = {
                    "signal": ml_signal,
                    "confidence": ml_pred,
                    "validated": True
                }

                ml_result = validate_ml_signal_with_context(ml_result, trend_analysis, pair)
                logging.info(f"🤖 {pair}: ML сигнал={ml_result['signal']} conf={ml_result['confidence']:.2f} valid={ml_result['validated']}")

            except Exception as e:
                logging.error(f"❌ Ошибка ML для {pair}: {e}")

        # --- GPT ---
        if USE_GPT:
            gpt_signal, gpt_expiry = gpt_full_market_read(pair, df_m1, df_m5)
            if gpt_signal:
                gpt_result = {"signal": gpt_signal, "confidence": 6, "expiry": gpt_expiry, "source": "GPT"}
                logging.info(f"💬 {pair}: GPT сигнал={gpt_signal}")

        # 5️⃣ ✅ Комбинированное решение
        final_signal = None
        final_expiry = None
        final_confidence = 0
        final_source = None

        # 📌 1. ВЫСОКИЙ ПРИОРИТЕТ: SMC с уверенностью >= 5
        if smc_result['signal'] and smc_result['confidence'] >= 5:
            final_signal = smc_result['signal']
            final_confidence = smc_result['confidence']
            final_expiry = smc_result['expiry']
            final_source = "ENHANCED_SMART_MONEY"
            logging.info(f"🎯 SMC ПРИОРИТЕТ: {final_signal} (conf={final_confidence})")

        # 📌 2. СРЕДНИЙ ПРИОРИТЕТ: ML если валидирован и SMC слабый/отсутствует
        elif ml_result and ml_result['signal'] and ml_result['validated'] and ml_result['confidence'] >= 0.6:
            # Дополнительная проверка контекста
            rsi_val = ml_features_dict.get('rsi', 50)
            if (ml_result['signal'] == 'BUY' and rsi_val < 65) or \
               (ml_result['signal'] == 'SELL' and rsi_val > 35):
                final_signal = ml_result['signal']
                final_confidence = int(ml_result['confidence'] * 10)
                final_expiry = 2
                final_source = "ML_VALIDATED"
                logging.info(f"🤖 ML ПРИОРИТЕТ: {final_signal} (conf={final_confidence})")

        # 📌 3. 🔥 ОСТОРОЖНЫЙ ПРИОРИТЕТ: GPT с дополнительными фильтрами
        elif (gpt_result and gpt_result['signal'] and 
              smc_result['confidence'] >= 2 and  # SMC хотя бы слабо подтверждает
              ml_result and ml_result['confidence'] >= 0.4 and  # ML не сильно против
              not is_against_strong_trend(gpt_result['signal'], trend_analysis)):  # 🔥 НЕ против сильного тренда
    
            final_signal = gpt_result['signal']
            final_confidence = gpt_result['confidence'] - 1  # Понижаем уверенность
            final_expiry = gpt_result['expiry']
            final_source = "GPT_CAREFUL"
            logging.info(f"⚠️ ОСТОРОЖНЫЙ GPT: {final_signal} (conf={final_confidence})")
 
        # 6️⃣ 🔥 ФИНАЛЬНАЯ ПРОВЕРКА: запрет сигналов против сильного тренда
        if final_signal and is_against_strong_trend(final_signal, trend_analysis):
            logging.warning(f"⛔ ОТМЕНА: сигнал {final_signal} против сильного тренда")
            return None, None, 0, "AGAINST_STRONG_TREND", ml_features_data

        # 7️⃣ Возврат
        if final_signal:
            logging.info(f"🚀 {pair}: Окончательный сигнал = {final_signal} ({final_source}, conf={final_confidence})")
    
            return final_signal, final_expiry, final_confidence, final_source, ml_features_data
        
        logging.info(f"❌ {pair}: сигналов нет или они отфильтрованы")
        return None, None, 0, "NO_SIGNAL", ml_features_data

    except Exception as e:
        logging.error(f"💥 Ошибка анализа пары {pair}: {e}", exc_info=True)
        return None, None, 0, "ERROR", None
    
# ===================== FAST CHART (MATPLOTLIB) =====================
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import pandas as pd
import logging
from datetime import datetime

# 🔥 ГЛОБАЛЬНЫЙ КЭШ ГРАФИКОВ В ПАМЯТИ
CHART_CACHE = {}
CACHE_EXPIRY = 300  # 5 минут

def enhanced_plot_chart(df, pair, entry_price, direction):
    """СУПЕР-БЫСТРЫЙ TradingView-стиль график со свечами (1-2 секунды)"""
    
    try:
        if df is None or len(df) < 100:
            return None

        # 🔥 ПРОВЕРКА КЭША В ПАМЯТИ
        cache_key = f"{pair}_{direction}_{entry_price:.5f}"
        current_time = datetime.now()
        
        if cache_key in CHART_CACHE:
            cached_time, chart_bytes = CHART_CACHE[cache_key]
            if (current_time - cached_time).total_seconds() < CACHE_EXPIRY:
                logging.info(f"📊 Используем кэшированный график из памяти для {pair}")
                chart_stream = BytesIO(chart_bytes)
                chart_stream.name = f"chart_{pair}.png"
                return chart_stream

        # Используем только последние 80 свечей для скорости и читаемости
        df_plot = df.tail(80).copy()
        
        # Создаем график
        plt.style.use('dark_background')
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), 
                                      gridspec_kw={'height_ratios': [3, 1]})
        fig.patch.set_facecolor('#0a1120')
        
        # ======== СВЕЧНОЙ ГРАФИК ========
        # Цвета TradingView
        green_color = '#00ff88'  # Бычий
        red_color = '#ff4444'    # Медвежий
        
        # Рисуем свечи вручную
        for i in range(len(df_plot)):
            open_price = df_plot['open'].iloc[i]
            close_price = df_plot['close'].iloc[i]
            high_price = df_plot['high'].iloc[i]
            low_price = df_plot['low'].iloc[i]
            
            # Определяем цвет свечи
            color = green_color if close_price >= open_price else red_color
            alpha = 0.8
            
            # Тело свечи
            body_bottom = min(open_price, close_price)
            body_top = max(open_price, close_price)
            body_height = body_top - body_bottom
            
            if body_height > 0:
                ax1.bar(i, body_height, bottom=body_bottom, color=color, alpha=alpha, width=0.8)
            
            # Тени свечи
            ax1.plot([i, i], [low_price, body_bottom], color=color, linewidth=1, alpha=alpha)
            ax1.plot([i, i], [body_top, high_price], color=color, linewidth=1, alpha=alpha)
        
        # SMA20
        sma20 = df_plot['close'].rolling(20).mean()
        ax1.plot(range(len(sma20)), sma20, color='#ffaa00', linewidth=2, label='SMA 20', alpha=0.9)
        
        # ======== КЛЮЧЕВЫЕ ЛИНИИ ========
        # Линия входа (белая пунктирная)
        ax1.axhline(y=entry_price, color='white', linestyle='--', 
                   linewidth=2, label=f'Entry: {entry_price:.5f}')
        
        # Текущая цена (голубая точечная)
        current_price = df_plot['close'].iloc[-1]
        ax1.axhline(y=current_price, color='#00ffff', linestyle=':', 
                   linewidth=1.5, label=f'Current: {current_price:.5f}')
        
        # ======== ОФОРМЛЕНИЕ ========
        # 🔥 ИСПРАВЛЕНИЕ ШРИФТОВ - убираем эмодзи из заголовка
        title_text = f"{pair} - SMART MONEY - {direction}"
        ax1.set_title(title_text, color='white', fontsize=16, fontweight='bold', pad=20)
        
        ax1.legend(loc='upper left', facecolor='#1e2a3a')
        ax1.grid(True, alpha=0.3, color='#1e2a3a')
        ax1.set_facecolor('#0a1120')
        ax1.tick_params(colors='white')
        
        # ======== ОБЪЕМЫ ========
        if 'volume' in df_plot.columns or 'tick_volume' in df_plot.columns:
            volumes = df_plot['volume'] if 'volume' in df_plot.columns else df_plot['tick_volume']
            
            # Цвета объемов как в TradingView (зеленый/красный)
            volume_colors = []
            for i in range(len(df_plot)):
                if df_plot['close'].iloc[i] >= df_plot['open'].iloc[i]:
                    volume_colors.append(green_color)
                else:
                    volume_colors.append(red_color)
            
            ax2.bar(range(len(volumes)), volumes, color=volume_colors, alpha=0.7)
        
        ax2.set_ylabel('Volume', color='white')
        ax2.grid(True, alpha=0.3, color='#1e2a3a')
        ax2.set_facecolor('#0a1120')
        ax2.tick_params(colors='white')
        
        # ======== ИНФО-ПАНЕЛЬ ========
        trend_analysis = enhanced_trend_analysis(df)
        info_bg = '#00cc66' if direction == 'BUY' else '#ff4444'
        
        # 🔥 ИСПРАВЛЕНИЕ ШРИФТОВ - простой текст без спецсимволов
        info_text = (f"PRICE: {current_price:.5f}\n"
                    f"TREND: {trend_analysis['direction']}\n"
                    f"STRENGTH: {trend_analysis['strength']}\n"
                    f"SIGNAL: {direction}")
        
        ax1.text(0.02, 0.98, info_text, transform=ax1.transAxes, 
                fontsize=10, verticalalignment='top', color='white',
                bbox=dict(boxstyle='round', facecolor=info_bg, alpha=0.9, edgecolor='white'))

        plt.tight_layout()
        
        # ======== СОХРАНЕНИЕ В ПАМЯТЬ ========
        chart_stream = BytesIO()
        
        # 🔥 ИСПРАВЛЕНИЕ ШРИФТОВ - убираем эмодзи из настроек сохранения
        plt.savefig(chart_stream, format='png', dpi=100, bbox_inches='tight', 
                   facecolor='#0a1120', edgecolor='none')
        plt.close()
        
        chart_bytes = chart_stream.getvalue()
        
        # 🔥 СОХРАНЯЕМ В КЭШ ПАМЯТИ
        CHART_CACHE[cache_key] = (current_time, chart_bytes)
        
        # 🔥 СОЗДАЕМ НОВЫЙ BytesIO для отправки
        chart_stream = BytesIO(chart_bytes)
        chart_stream.name = f"chart_{pair}.png"
        
        logging.info(f"⚡ БЫСТРЫЙ график создан в памяти: {pair} (1-2 сек)")
        return chart_stream
        
    except Exception as e:
        logging.error(f"❌ Ошибка создания быстрого графика: {e}")
        return None

# ===================== GLOBAL SIGNAL VARIABLES =====================
CURRENT_SIGNAL = None
CURRENT_SIGNAL_TIMESTAMP = None
SIGNAL_EXPIRY_MINUTES = 2  # Сигнал действителен 2 минуты

from datetime import datetime  # Убедитесь что этот импорт есть в начале файла

# ===================== 🧩 АНТИ-ЗАВИСАНИЕ СДЕЛОК (ASYNC-SAFE) =====================
async def auto_close_stuck_trades():
    """Асинхронно закрывает зависшие сделки, не блокируя event loop"""
    global users
    now = datetime.utcnow()
    closed_count = 0

    try:
        for uid, udata in list(users.items()):
            current_trade = udata.get("current_trade")
            if not current_trade:
                continue

            start_time_str = current_trade.get("timestamp")
            expiry_minutes = current_trade.get("expiry_minutes", 1)

            try:
                start_time = datetime.fromisoformat(start_time_str)
            except Exception:
                continue

            elapsed = (now - start_time).total_seconds() / 60

            # Если прошло больше, чем expiry + 2 минуты — считаем зависшей
            if elapsed > expiry_minutes + 2:
                current_trade["result"] = "LOSS"
                current_trade["completed_at"] = now.isoformat()

                udata.setdefault("trade_history", []).append(current_trade)
                udata["current_trade"] = None
                closed_count += 1

                logging.warning(f"⚠️ Автоматически закрыта зависшая сделка у пользователя {uid}")

        if closed_count > 0:
            await async_save_users_data()  # 🔄 не блокирует event loop
            logging.info(f"♻️ Автоматически закрыто зависших сделок: {closed_count}")

    except Exception as e:
        logging.error(f"💥 Ошибка в auto_close_stuck_trades: {e}")



# ===================== 🧠 AUTO TRADING LOOP - АСИНХРОННЫЙ =====================
async def auto_trading_loop(context: ContextTypes.DEFAULT_TYPE):
    """
    Асинхронный торговый цикл с параллельной обработкой пользователей
    ✅ Защита от зависаний, таймаутов и блокировок
    """
    from datetime import datetime
    start_time = datetime.now()
    semaphore = asyncio.Semaphore(10)  # ограничение одновременных задач

    await auto_close_stuck_trades()

    try:
        if not is_trading_time():
            logging.info("⏸ Вне рабочего времени бота — цикл пропущен")
            return

        if not users or len(users) == 0:
            logging.warning("⚠ База пользователей пуста")
            return

        logging.info(f"🔄 Запуск авто-трейдинг цикла для {len(users)} пользователей...")

        async def process_user(uid: int, udata: dict):
            """Асинхронная обработка одного пользователя с таймаутом и ограничением"""
            async with semaphore:
                try:
                    if not udata.get("auto_trading", True):
                        logging.debug(f"⏸ {uid}: авто-трейдинг выключен")
                        return

                    # ограничение выполнения для одного пользователя
                    await asyncio.wait_for(process_auto_trade_for_user(uid, udata, context), timeout=20)

                except asyncio.TimeoutError:
                    logging.warning(f"⏳ Таймаут обработки пользователя {uid}")
                except Exception as err:
                    logging.error(f"❌ Ошибка при обработке пользователя {uid}: {err}", exc_info=True)

        # создаём задачи для всех пользователей
        tasks = [asyncio.create_task(process_user(uid, udata)) for uid, udata in users.copy().items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success = sum(1 for r in results if not isinstance(r, Exception))
        logging.info(f"✅ Завершено пользователей: {success}/{len(users)}")

        # безопасное сохранение данных без блокировки event loop
        await asyncio.to_thread(save_users_data)

    except Exception as e:
        logging.error(f"💥 Ошибка авто-трейдинга: {e}", exc_info=True)

    finally:
        duration = (datetime.now() - start_time).total_seconds()
        logging.info(f"⏱️ Цикл завершён за {duration:.1f} сек")


# ===================== ⚙️ TRADE RESULT CHECKER (ASYNC VERSION) =====================
async def check_trade_result(context: ContextTypes.DEFAULT_TYPE):
    """Асинхронная проверка результата сделки с таймаутами, повторными попытками и защитой от зависаний"""
    try:
        job_data = context.job.data
        user_id = job_data["user_id"]
        pair = job_data["pair"]
        trade_id = job_data["trade_id"]
        attempt = job_data.get("attempt", 1)
        max_attempts = job_data.get("max_attempts", 3)

        logging.info(f"🔍 Проверка сделки #{trade_id} для пользователя {user_id} ({pair}), попытка {attempt}/{max_attempts}")

        # Получаем данные пользователя
        user_data = get_user_data(user_id)
        if not user_data:
            logging.error(f"❌ Пользователь {user_id} не найден")
            return

        current_trade = user_data.get("current_trade")
        if not current_trade:
            # возможно, сделка уже закрыта
            await check_if_trade_already_closed(user_id, trade_id, context)
            return

        if current_trade.get("id") != trade_id:
            logging.warning(f"⚠️ Несоответствие ID: ожидалось {trade_id}, получено {current_trade.get('id')}")
            await check_if_trade_already_closed(user_id, trade_id, context)
            return

        # Получаем текущую цену с таймаутом и повторными попытками
        try:
            current_price = await asyncio.wait_for(
                get_current_price_with_retry(pair, max_retries=3),
                timeout=10
            )
        except asyncio.TimeoutError:
            logging.warning(f"⏳ Таймаут получения цены для {pair}")
            current_price = None

        if current_price is None:
            await schedule_retry_check(context.job, attempt, max_attempts, user_id, pair, trade_id)
            return

        entry_price = current_trade["entry_price"]
        direction = current_trade["direction"]

        # Определяем результат
        result = "WIN" if (
            (direction == "BUY" and current_price > entry_price) or
            (direction == "SELL" and current_price < entry_price)
        ) else "LOSS"

        stake = current_trade.get("stake", STAKE_AMOUNT)
        profit = WIN_PROFIT if result == "WIN" else -stake

        closed_trade = {
            "id": trade_id,
            "pair": pair,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": current_price,
            "stake": stake,
            "timestamp": current_trade.get("timestamp", datetime.now().isoformat()),
            "completed_at": datetime.now().isoformat(),
            "result": result,
            "profit": profit,
            "confidence": current_trade.get("confidence", 0),
            "source": current_trade.get("source", "UNKNOWN"),
            "expiry_minutes": current_trade.get("expiry_minutes", 1),
            "ml_features": current_trade.get("ml_features"),
            "check_attempts": attempt,
            "closed_successfully": True
        }

        # ✅ Добавляем в историю и очищаем активную сделку
        user_data.setdefault("trade_history", []).append(closed_trade)
        user_data["current_trade"] = None
        user_data["trade_counter"] = len(user_data["trade_history"])

        # 💾 Сохраняем безопасно
        await asyncio.to_thread(save_users_data)

        # 📑 Логируем
        try:
            await asyncio.to_thread(log_trade_to_file, closed_trade, result)
        except Exception as e:
            logging.error(f"⚠️ Ошибка логирования сделки: {e}")

        # 📢 Отправляем уведомление пользователю
        await send_trade_result_notification(context, user_id, closed_trade, user_data)

        logging.info(f"✅ Сделка #{trade_id} ({pair}) успешно закрыта — {result}")

    except Exception as e:
        logging.error(f"💥 Ошибка в check_trade_result: {e}", exc_info=True)
        try:
            await schedule_retry_check(context.job, attempt, max_attempts, user_id, pair, trade_id)
        except Exception as err:
            logging.error(f"⚠️ Ошибка при планировании повторной проверки: {err}")


# ===================== ⚡ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

async def get_current_price_with_retry(pair, max_retries=3):
    """Получение текущей цены с повторными попытками"""
    for attempt in range(1, max_retries + 1):
        try:
            df = await asyncio.to_thread(get_mt5_data, pair, 2, mt5.TIMEFRAME_M1)
            if df is not None and len(df) > 0:
                return df["close"].iloc[-1]
        except Exception as e:
            logging.error(f"❌ Ошибка при получении цены {pair} (попытка {attempt}): {e}")
        if attempt < max_retries:
            await asyncio.sleep(2)
    return None


async def schedule_retry_check(job, current_attempt, max_attempts, user_id, pair, trade_id):
    """Планирует повторную проверку сделки"""
    if current_attempt >= max_attempts:
        await force_close_trade_on_failure(user_id, trade_id, pair, current_attempt)
        return

    retry_delay = 30
    job_data = {
        "user_id": user_id,
        "pair": pair,
        "trade_id": trade_id,
        "attempt": current_attempt + 1,
        "max_attempts": max_attempts
    }

    job.job_queue.run_once(
        check_trade_result,
        when=retry_delay,
        data=job_data,
        name=f"retry_check_{trade_id}_{current_attempt + 1}"
    )
    logging.info(f"🔁 Повторная проверка сделки #{trade_id} через {retry_delay} сек (попытка {current_attempt + 1})")


async def force_close_trade_on_failure(user_id, trade_id, pair, attempt):
    """Принудительное закрытие сделки при превышении попыток"""
    try:
        user_data = get_user_data(user_id)
        if not user_data or not user_data.get("current_trade"):
            return

        current_trade = user_data["current_trade"]

        closed_trade = {
            "id": trade_id,
            "pair": pair,
            "direction": current_trade["direction"],
            "entry_price": current_trade["entry_price"],
            "exit_price": current_trade["entry_price"],
            "stake": current_trade.get("stake", STAKE_AMOUNT),
            "timestamp": current_trade.get("timestamp", datetime.now().isoformat()),
            "completed_at": datetime.now().isoformat(),
            "result": "LOSS",
            "profit": -current_trade.get("stake", STAKE_AMOUNT),
            "force_closed": True,
            "close_reason": "MAX_RETRIES_EXCEEDED",
            "check_attempts": attempt
        }

        user_data.setdefault("trade_history", []).append(closed_trade)
        user_data["current_trade"] = None

        await asyncio.to_thread(save_users_data)
        logging.warning(f"🔒 Сделка #{trade_id} принудительно закрыта (превышено {attempt} попыток)")

        await send_force_close_notification(user_id, trade_id)

    except Exception as e:
        logging.error(f"💥 Ошибка принудительного закрытия сделки #{trade_id}: {e}")


async def send_force_close_notification(user_id, trade_id):
    """Отправка уведомления о принудительном закрытии"""
    try:
        await app.bot.send_message(
            chat_id=user_id,
            text=(f"⚠️ Сделка #{trade_id} была автоматически закрыта из-за проблем с проверкой.\n"
                  f"Результат: LOSS\n"
                  f"Средства возвращены."),
            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
        )
    except Exception as e:
        logging.error(f"❌ Ошибка уведомления о принудительном закрытии сделки #{trade_id}: {e}")


async def check_if_trade_already_closed(user_id, trade_id, context):
    """Проверяет, не закрыта ли уже сделка"""
    try:
        user_data = get_user_data(user_id)
        if not user_data:
            return False

        for trade in user_data.get("trade_history", []):
            if trade.get("id") == trade_id:
                logging.info(f"ℹ️ Сделка #{trade_id} уже закрыта ранее")
                return True
        return False
    except Exception as e:
        logging.error(f"❌ Ошибка проверки истории: {e}")
        return False


async def send_trade_result_notification(context, user_id, closed_trade, user_data):
    """Отправка уведомления пользователю о результате сделки"""
    try:
        trade_id = closed_trade["id"]
        pair = closed_trade["pair"]
        direction = closed_trade["direction"]
        entry = closed_trade["entry_price"]
        exit_ = closed_trade["exit_price"]
        result = closed_trade["result"]
        profit = closed_trade["profit"]

        total = len(user_data["trade_history"])
        wins = sum(1 for t in user_data["trade_history"] if t["result"] == "WIN")
        losses = total - wins
        win_rate = round(wins / total * 100, 1) if total else 0

        emoji = "🟢" if result == "WIN" else "🔴"
        text = (
            f"{emoji} СДЕЛКА #{trade_id} ЗАВЕРШЕНА\n\n"
            f"💼 Пара: {pair}\n"
            f"📊 Направление: {direction}\n"
            f"💰 Вход: {entry:.5f}\n"
            f"💰 Выход: {exit_:.5f}\n"
            f"🎯 Результат: {result}\n"
            f"💸 Прибыль: {profit:.2f}\n\n"
            f"📊 Ваша статистика:\n"
            f"• Всего: {total}\n"
            f"• 🟢 Победы: {wins}\n"
            f"• 🔴 Поражения: {losses}\n"
            f"• 🎯 Win Rate: {win_rate}%"
        )

        if closed_trade.get("force_closed"):
            text += "\n\n⚠️ Сделка закрыта автоматически (техническая ошибка)"

        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
        )

    except Exception as e:
        logging.error(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}")

        
# ===================== TRADE MONITORING & EXPIRED TRADES =====================
async def check_expired_trades_job(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка зависших и просроченных сделок"""
    try:
        logging.info("🔍 Проверка просроченных сделок...")
        expired_count = 0

        # ✅ используем глобальный словарь пользователей
        global users

        for user_id, user_info in users.items():
            current_trade = user_info.get('current_trade')
            if not current_trade:
                continue

            trade_start_str = current_trade.get('timestamp')
            if not trade_start_str:
                continue

            try:
                # корректно парсим время
                trade_start = datetime.fromisoformat(trade_start_str.replace('Z', '+00:00'))
                trade_age = datetime.utcnow() - trade_start

                # если сделка висит более 15 минут — закрываем
                if trade_age.total_seconds() > 15 * 60:
                    await force_close_expired_trade(context, user_id, current_trade)
                    expired_count += 1

            except Exception as e:
                logging.error(f"❌ Ошибка проверки времени сделки пользователя {user_id}: {e}")

        if expired_count > 0:
            logging.warning(f"🕒 Автоматически закрыто просроченных сделок: {expired_count}")
        else:
            logging.info("✅ Активных зависших сделок не найдено")

    except Exception as e:
        logging.error(f"❌ Ошибка в check_expired_trades_job: {e}", exc_info=True)


# ===================== 🧩 FORCE CLOSE EXPIRED TRADE (ASYNC-SAFE) =====================
async def force_close_expired_trade(context, user_id, trade):
    """Принудительное закрытие просроченной сделки без блокировки event loop"""
    try:
        user_info = users.get(user_id)
        if not user_info:
            logging.error(f"❌ Пользователь {user_id} не найден при закрытии сделки")
            return

        trade_id = trade.get("id")
        pair = trade.get("pair")
        direction = trade.get("direction")

        # 🕐 Получаем текущую цену (с защитой от зависания)
        try:
            current_price = await asyncio.wait_for(
                get_current_price_with_retry(pair, max_retries=2),
                timeout=8
            )
        except asyncio.TimeoutError:
            current_price = None

        if current_price is None:
            current_price = trade.get("entry_price", 0.0)

        # 🧾 Формируем запись о закрытии
        closed_trade = {
            "id": trade_id,
            "pair": pair,
            "direction": direction,
            "entry_price": trade.get("entry_price", 0.0),
            "exit_price": current_price,
            "stake": trade.get("stake", STAKE_AMOUNT),
            "stake_used": trade.get("stake", STAKE_AMOUNT),
            "timestamp": trade.get("timestamp", datetime.now().isoformat()),
            "completed_at": datetime.now().isoformat(),
            "result": "LOSS",
            "profit": -trade.get("stake", STAKE_AMOUNT),
            "confidence": trade.get("confidence", 0),
            "source": trade.get("source", "UNKNOWN"),
            "expiry_minutes": trade.get("expiry_minutes", 1),
            "ml_features": trade.get("ml_features", None),
            "closed_successfully": False,
            "force_closed": True,
            "close_reason": "EXPIRED_TIMEOUT"
        }

        # 💾 Сохраняем данные пользователя
        user_info.setdefault("trade_history", []).append(closed_trade)
        user_info["current_trade"] = None
        await async_save_users_data()  # 🔄 безопасная асинхронная запись

        logging.warning(f"🔒 Просроченная сделка #{trade_id} у пользователя {user_id} закрыта (таймаут)")

        # 📢 Уведомление пользователя
        try:
            msg = (
                f"⚠️ СДЕЛКА #{trade_id} ЗАКРЫТА ПО ТАЙМАУТУ\n\n"
                f"Сделка висела более 15 минут без завершения.\n"
                f"Результат: LOSS (принудительное закрытие)\n"
                f"Пара: {pair} — {direction}"
            )

            await context.bot.send_message(
                chat_id=user_id,
                text=msg,
                reply_markup=ReplyKeyboardMarkup(
                    [["❓ Помощь", "🕒 Расписание"]],
                    resize_keyboard=True
                )
            )

        except telegram.error.Forbidden:
            logging.warning(f"🚫 Пользователь {user_id} заблокировал бота (не удалось уведомить)")
            if user_id in users:
                del users[user_id]
                await async_save_users_data()

        except Exception as e:
            logging.error(f"⚠ Ошибка уведомления о принудительном закрытии сделки {trade_id}: {e}")

    except Exception as e:
        logging.error(f"💥 Ошибка в force_close_expired_trade для пользователя {user_id}: {e}")

# ===================== COMMAND HANDLERS FOR TRADE MANAGEMENT =====================

async def check_active_trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все активные сделки (только для администратора)"""
    try:
        user_id = str(update.effective_user.id)
        
        # Проверяем права администратора
        if user_id != "5129282647":  # ID администратора
            await update.message.reply_text("❌ Эта команда только для администратора")
            return
        
        active_trades = []
        total_active = 0
        
        for uid, user_info in user_data.items():
            current_trade = user_info.get('current_trade')
            if current_trade:
                total_active += 1
                trade_age = "N/A"
                if current_trade.get('timestamp'):
                    try:
                        trade_start = datetime.fromisoformat(current_trade['timestamp'].replace('Z', '+00:00'))
                        trade_age_minutes = (datetime.now() - trade_start).total_seconds() / 60
                        trade_age = f"{trade_age_minutes:.1f} мин"
                    except:
                        trade_age = "N/A"
                
                active_trades.append(
                    f"👤 {user_info.get('first_name', 'Unknown')} (ID: {uid})\n"
                    f"   📈 {current_trade['pair']} {current_trade['direction']}\n"
                    f"   🆔 #{current_trade.get('id', 'N/A')}\n"
                    f"   ⏰ Возраст: {trade_age}\n"
                    f"   🎯 Источник: {current_trade.get('source', 'UNKNOWN')}\n"
                    f"   💰 Ставка: ${current_trade.get('stake', 0):.2f}"
                )
        
        if active_trades:
            message = f"🔍 АКТИВНЫЕ СДЕЛКИ ({total_active}):\n\n" + "\n\n".join(active_trades)
        else:
            message = "✅ Нет активных сделок"
            
        await update.message.reply_text(message)
        
    except Exception as e:
        logging.error(f"❌ Ошибка команды check_active_trades: {e}")
        await update.message.reply_text("❌ Ошибка получения информации о сделках")

async def force_close_trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительно закрыть все активные сделки (только для администратора)"""
    try:
        user_id = str(update.effective_user.id)
        
        # Проверяем права администратора
        if user_id != "5129282647":
            await update.message.reply_text("❌ Эта команда только для администратора")
            return
        
        closed_count = 0
        for uid, user_info in user_data.items():
            current_trade = user_info.get('current_trade')
            if current_trade:
                # Используем существующую функцию принудительного закрытия
                await force_close_expired_trade(context, uid, current_trade)
                closed_count += 1
        
        if closed_count > 0:
            await update.message.reply_text(f"✅ Принудительно закрыто {closed_count} сделок")
        else:
            await update.message.reply_text("✅ Нет активных сделок для закрытия")
            
    except Exception as e:
        logging.error(f"❌ Ошибка команды force_close_trade: {e}")
        await update.message.reply_text("❌ Ошибка принудительного закрытия сделок")

# ===================== ⚡ PROCESS AUTO TRADE FOR USER (ASYNC VERSION) =====================
async def process_auto_trade_for_user(user_id: int, user_data: Dict, context: ContextTypes.DEFAULT_TYPE):
    """
    Асинхронная версия авто-трейдинга с таймаутами, безопасной обработкой и отсутствием блокировок
    """
    try:
        # 🕒 Проверяем, разрешено ли сейчас торговать
        if not is_trading_time():
            logging.debug(f"⏸ Вне рабочего времени — пользователь {user_id}")
            return

        # 🧩 Пропускаем, если есть открытая сделка
        if user_data.get('current_trade'):
            logging.debug(f"⏸ Пользователь {user_id} уже имеет открытую сделку")
            return

        logging.info(f"🚀 [AUTO] Старт анализа для пользователя {user_id}")
        random.shuffle(PAIRS)

        for pair in PAIRS:
            start_time = datetime.now()

            # 🧠 Анализ пары в отдельном потоке (чтобы не блокировать event loop)
            try:
                result = await asyncio.to_thread(analyze_pair, pair)
            except Exception as e:
                logging.warning(f"⚠ Ошибка анализа {pair} для {user_id}: {e}")
                continue

            if not result or len(result) < 4:
                continue

            signal, expiry, conf, source = result[:4]

            # 🎯 Фильтрация слабых сигналов
            if not signal or conf < 6:
                continue

            # 📊 Получаем данные с MT5 асинхронно
            df = await asyncio.to_thread(get_mt5_data, pair, 300, mt5.TIMEFRAME_M1)
            if df is None or len(df) < 50:
                continue

            entry_price = df['close'].iloc[-1]
            trade_number = user_data['trade_counter'] + 1

            # 🧠 Подготовка ML-признаков
            ml_features_dict = await asyncio.to_thread(prepare_ml_features, df)

            # 📝 Формируем сообщение
            signal_text = (
                f"🎯 СДЕЛКА #{trade_number}\n"
                f"🤖 АВТО-ТРЕЙДИНГ СИГНАЛ\n"
                f"💼 Пара: `{pair}`\n"
                f"📊 Сигнал: {signal}\n"
                f"💰 Цена входа: {entry_price:.5f}\n"
                f"⏰ Экспирация: {expiry} мин\n"
                f"🎯 Уверенность: {conf}/10\n"
                f"🔍 Источник: {source}\n\n"
                f"Сделка открыта! Результат через {expiry} минут..."
            )

            # 📈 Генерация графика (в фоне)
            chart_stream = await asyncio.to_thread(enhanced_plot_chart, df, pair, entry_price, signal)
            markup = ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)

            # 📤 Отправка сигнала пользователю
            try:
                if chart_stream:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=chart_stream,
                        caption=signal_text,
                        reply_markup=markup
                    )
                else:
                    await context.bot.send_message(chat_id=user_id, text=signal_text, reply_markup=markup)

                logging.info(f"✅ Сигнал отправлен пользователю {user_id} ({pair} {signal})")

            except telegram.error.Forbidden:
                logging.warning(f"🚫 Пользователь {user_id} заблокировал бота — удаляем из базы")
                users.pop(user_id, None)
                await asyncio.to_thread(save_users_data)
                return

            except telegram.error.TimedOut:
                logging.warning(f"⏳ Таймаут Telegram API для {user_id}, повторная попытка...")
                await asyncio.sleep(2)
                try:
                    await context.bot.send_message(chat_id=user_id, text=signal_text, reply_markup=markup)
                except Exception as retry_err:
                    logging.error(f"⚠ Ошибка повторной отправки {user_id}: {retry_err}")
                return

            except Exception as send_err:
                logging.error(f"⚠ Ошибка отправки сигнала {user_id}: {send_err}")
                return

            # 💾 Сохраняем текущую сделку
            trade = {
                'id': trade_number,
                'pair': pair,
                'direction': signal,
                'entry_price': float(entry_price),
                'expiry_minutes': int(expiry),
                'stake': float(STAKE_AMOUNT),
                'timestamp': datetime.now().isoformat(),
                'ml_features': ml_features_dict or {},
                'source': source,
                'confidence': int(conf)
            }

            user_data['current_trade'] = trade
            user_data['trade_counter'] += 1

            await asyncio.to_thread(save_users_data)
            logging.info(f"📌 Сделка #{trade_number} сохранена (история добавится после закрытия)")

            # 🕒 Планируем проверку результата
            check_delay = (expiry * 60) + 5
            context.job_queue.run_once(
                check_trade_result,
                check_delay,
                data={'user_id': user_id, 'pair': pair, 'trade_id': trade_number}
            )

            logging.info(f"🕒 Проверка сделки #{trade_number} через {check_delay} сек")

            elapsed = (datetime.now() - start_time).total_seconds()
            logging.info(f"✅ Сделка #{trade_number} ({pair} {signal}) открыта за {elapsed:.2f} сек")

            # 🛑 Одно срабатывание за цикл
            return

        logging.info(f"🏁 [AUTO] Анализ для {user_id} завершён без открытия сделок")

    except Exception as e:
        logging.error(f"❌ Ошибка process_auto_trade_for_user({user_id}): {e}", exc_info=True)


        
# ===================== TELEGRAM COMMANDS =====================
# -------- WHITELIST MANAGEMENT COMMANDS --------
async def whitelist_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет пользователя в белый список (только админ)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для администраторов")
        return
        
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📝 Использование:\n"
            "/whitelist_add <pocket_id> <имя> [role=user]\n\n"
            "Пример:\n"
            "/whitelist_add 12345678 \"Иван Петров\"\n"
            "/whitelist_add 87654321 \"Мария\" admin"
        )
        return
        
    pocket_id = context.args[0]
    name = context.args[1]
    role = context.args[2] if len(context.args) > 2 else "user"
    
    success, message = add_user_to_whitelist(pocket_id, name, role=role)
    
    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")

async def whitelist_remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет пользователя из белого списка (только админ)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для администраторов")
        return
        
    if not context.args:
        await update.message.reply_text(
            "📝 Использование:\n"
            "/whitelist_remove <pocket_id>\n\n"
            "Пример:\n"
            "/whitelist_remove 12345678"
        )
        return
        
    pocket_id = context.args[0]
    success, message = remove_user_from_whitelist(pocket_id)
    
    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")

async def whitelist_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику белого списка"""
    stats = get_whitelist_stats()
    
    await update.message.reply_text(
        f"📊 **Статистика белого списка**\n\n"
        f"👥 Всего пользователей: `{stats['total_users']}`\n"
        f"🛡️ Администраторов: `{stats['admins']}`\n"
        f"👤 Пользователей: `{stats['users']}`\n"
        f"🟢 Активных: `{stats['active_users']}`",
        parse_mode='Markdown'
    )

async def whitelist_show_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает всех пользователей в белом списке (только админ)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для администраторов")
        return
        
    whitelist = load_whitelist()
    
    if not whitelist:
        await update.message.reply_text("📝 Белый список пуст")
        return
        
    message = "📋 **Белый список пользователей:**\n\n"
    
    for pocket_id, user_data in whitelist.items():
        role_icon = "🛡️" if user_data.get('role') == 'admin' else "👤"
        message += f"{role_icon} `{pocket_id}` - {user_data['name']}\n"
        
        if user_data.get('telegram_id'):
            message += f"   📱 TG: {user_data['telegram_id']}\n"
            
        message += f"   📅 {user_data.get('registered_at', 'Unknown')[:10]}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

# -------- BOT STATUS NOTIFICATIONS --------
async def send_bot_status_notification(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет уведомления о изменении статуса бота всем пользователям"""
    global BOT_LAST_STATUS, BOT_STATUS_NOTIFIED
    
    try:
        if BOT_STATUS_NOTIFIED:
            return  # Уже уведомили
            
        now = datetime.now()
        current_time = now.time()
        current_weekday = now.weekday()
        weekday_name = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'][current_weekday]
        
        if BOT_LAST_STATUS:  # Бот начал работу
            message = (
                "🚀 **БОТ НАЧАЛ РАБОТУ!**\n\n"
                f"🕐 Время: {now.strftime('%H:%M:%S')}\n"
                f"📅 День: {weekday_name}\n\n"
                "🤖 Авто-трейдинг активирован\n"
                "📊 Поиск сигналов запущен\n"
                "🎯 Готов к торговле!"
            )
            
        else:  # Бот остановился
            # Расчет времени до следующего открытия
            if current_weekday in WEEKEND_DAYS:
                days_until_monday = (7 - current_weekday) % 7
                next_work_day = now + timedelta(days=days_until_monday)
                next_open = datetime.combine(next_work_day.date(), TRADING_START)
                reason = "выходной день"
            else:
                next_open = datetime.combine(now.date() + timedelta(days=1), TRADING_START)
                reason = "окончание рабочего дня"
            
            time_until = next_open - now
            hours = time_until.seconds // 3600
            minutes = (time_until.seconds % 3600) // 60
            
            message = (
                "⏸ **БОТ ОСТАНОВЛЕН**\n\n"
                f"🕐 Время: {now.strftime('%H:%M:%S')}\n"
                f"📅 День: {weekday_name}\n"
                f"📋 Причина: {reason}\n\n"
                f"🔄 **Возобновление работы:**\n"
                f"⏰ {next_open.strftime('%d.%m.%Y в %H:%M')}\n"
                f"⏳ Через: {hours}ч {minutes}мин\n\n"
                "📊 Торговля приостановлена до утра"
            )
        
        # Отправляем уведомление всем пользователям с авто-трейдингом
        notified_users = 0
        for user_id, user_data in users.items():
            try:
                if user_data.get('auto_trading', False):
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='Markdown',
                        reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
                    )
                    notified_users += 1
                    
                    # При старте дополнительно отправляем приветственное сообщение
                    if BOT_LAST_STATUS:
                        welcome_text = (
                            f"👋 С возвращением! Рабочий день начался.\n\n"
                            f"📊 Статус: 🟢 АКТИВЕН\n"
                            f"🤖 Авто-трейдинг: {'🟢 ВКЛ' if user_data.get('auto_trading', False) else '🔴 ВЫКЛ'}\n"
                            f"🎯 Режим: Поиск сигналов"
                        )
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=welcome_text,
                            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
                        )
                        
            except Exception as e:
                logging.error(f"❌ Ошибка уведомления пользователя {user_id}: {e}")
        
        BOT_STATUS_NOTIFIED = True
        logging.info(f"🔔 Уведомления о статусе отправлены {notified_users} пользователям")
        
    except Exception as e:
        logging.error(f"❌ Ошибка отправки уведомлений о статусе: {e}")

# -------- START & STATUS (ASYNC-SAFE) --------
async def register_or_update_user(user_id: int, username: str, update: Update):
    """Регистрирует нового пользователя или обновляет данные существующего (асинхронно и безопасно)"""
    try:
        # Получаем данные пользователя
        user_data = get_user_data(user_id)

        # 🔥 Правильное получение имени пользователя
        first_name = update.effective_user.first_name if update.effective_user else ''
        
        # Обновляем информацию
        user_data['first_name'] = first_name
        user_data['username'] = username
        user_data['language'] = 'ru'

        # Если пользователь новый
        if 'created_at' not in user_data:
            user_data['created_at'] = datetime.now().isoformat()
            user_data['auto_trading'] = True
            user_data['ml_enabled'] = ML_ENABLED
            user_data['gpt_enabled'] = USE_GPT
            user_data['smc_enabled'] = True

            logging.info(f"✅ Зарегистрирован новый пользователь: {user_id} ({username})")

            # 🔥 Автоматическое добавление в pocket_users.json
            try:
                # Загружаем whitelist асинхронно
                whitelist = await asyncio.to_thread(load_whitelist)

                pocket_id = str(user_id)
                user_name = first_name or f"User_{user_id}"

                if pocket_id not in whitelist:
                    whitelist[pocket_id] = {
                        "name": user_name,
                        "role": "user",
                        "telegram_id": user_id,
                        "registered_at": datetime.now().isoformat(),
                        "status": "active"
                    }
                    await asyncio.to_thread(save_whitelist, whitelist)
                    logging.info(f"✅ Пользователь {user_id} добавлен в pocket_users.json")
                else:
                    logging.info(f"ℹ️ Пользователь {user_id} уже есть в pocket_users.json")

            except Exception as e:
                logging.error(f"❌ Ошибка добавления пользователя в pocket_users.json: {e}")

        else:
            logging.info(f"✅ Обновлены данные пользователя: {user_id}")

        # 💾 Асинхронное сохранение базы
        await async_save_users_data()

    except Exception as e:
        logging.error(f"❌ Ошибка регистрации пользователя {user_id}: {e}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start - ОДИНАКОВЫЕ КНОПКИ ДЛЯ ВСЕХ"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        logging.info(f"👋 Команда /start от {user_id} ({username})")
        
        # 🔥 ОДИНАКОВАЯ КЛАВИАТУРА ДЛЯ ВСЕХ (только 2 кнопки)
        keyboard = [
            ["❓ Помощь", "🕒 Расписание"]
        ]
        
        # Разный текст приветствия для админа и пользователей
        if is_admin(user_id):  # 🔥 ИСПРАВЛЕНИЕ: используем is_admin вместо ADMIN_IDS
            welcome_text = (
                "🛠️ **Панель администратора**\n\n"
                "📋 **Доступные команды:**\n"
                "• /stats - статистика\n"
                "• /settings - настройки\n" 
                "• /next - следующий сигнал\n"
                "• /retrain - переобучить ML\n"
                "• /stop - остановить бота\n"
                "• /start - запустить бота\n"
                "• /logs - просмотр логов\n"
                "• /cleartrade - очистить сделки\n\n"
                "📱 **Кнопки меню:**\n"
                "• ❓ Помощь - справка\n"
                "• 🕒 Расписание - график работы"
            )
        else:
            welcome_text = (
                "🎯 **Добро пожаловать в ASPIRE TRADE!**\n\n"
                "🤖 **О боте:**\n"
                "• Автоматический торговый бот\n" 
                "• Анализ рынка в реальном времени\n"
                "• Умные сигналы на основе SMC анализа\n"
                "• Работает 24/7 в установленные часы\n\n"
                "📱 **Доступные функции:**\n"
                "• ❓ Помощь - инструкция и поддержка\n"
                "• 🕒 Расписание - график работы бота\n\n"
                "⚡ **Бот работает автоматически** - вы будете получать сигналы согласно расписанию!"
            )
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, selective=True)
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
        
        # Регистрация/обновление пользователя
        await register_or_update_user(user_id, username, update)  # 🔥 ИСПРАВЛЕНИЕ: передаем update вместо context
        
    except Exception as e:
        logging.error(f"❌ Ошибка в start_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при запуске бота")
    
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global users
    """Показывает системный статус"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    if ml_model and model_info and not model_info.get("error"):
        acc = model_info.get("accuracy")
        if isinstance(acc, (int, float)):
            ml_status = f"✅ Обучена ({model_info.get('trades_used', '?')} сделок, {acc*100:.1f}%)"
        else:
            ml_status = f"✅ Обучена ({model_info.get('trades_used', '?')} сделок)"
    else:
        error_msg = model_info.get("error", "Не обучена") if model_info else "Не обучена"
        ml_status = f"⚠ {error_msg}"

    personal_stake = user_data.get('personal_stake', STAKE_AMOUNT)
    personal_profit = round(personal_stake * 0.8)

    status_text = (
         f"📊 СТАТУС СИСТЕМЫ\n\n"
         f"👤 Пользователь: {user_data['first_name']}\n"
         f"📈 Сделок: {user_data['trade_counter']}\n"
         f"🤖 Авто-трейдинг: {'✅ ВКЛ' if user_data.get('auto_trading', False) else '⚠ ВЫКЛ'}\n\n"
         f"🌐 Режим: {'Мультипользовательский' if MULTI_USER_MODE else 'Однопользовательский'}\n"
         f"📡 MT5: {'✅ Подключен' if mt5.terminal_info() else '⚠ Отключен'}\n"
         f"🧠 ML: {ml_status}\n"
         f"🤖 GPT: {'✅ Активен' if USE_GPT else '⚠ Выключен'}"
    )

    await update.message.reply_text(status_text, reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True))

# -------- НОВАЯ КОМАНДА РАСПИСАНИЯ --------
async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда показа расписания работы бота"""
    try:
        schedule_text = (
            "🕒 РАСПИСАНИЕ РАБОТЫ БОТА\n\n"
            
            "⏰ Рабочие часы:\n"
            "• Начало: 04:00 (по вашему времени)\n"
            "• Окончание: 23:59 (по вашему времени)\n"
            "• Ежедневно, кроме выходных\n\n"
            
            "🗓️ Выходные дни:\n"
            "• Суббота - не работает\n" 
            "• Воскресенье - не работает\n\n"
            
            "📈 Когда бот активен:\n"
            "• Анализирует валютные пары\n"
            "• Ищет торговые сигналы\n"
            "• Автоматически открывает сделки\n"
            "• Отправляет уведомления\n\n"
            
            "💤 Когда бот неактивен:\n"
            "• Вне рабочих часов\n"
            "• В выходные дни\n"
            "• При техническом обслуживании\n\n"
            
            "🔔 Статус работы:\n"
            f"• Сейчас бот {'🟢 АКТИВЕН' if is_trading_time() else '🔴 НЕАКТИВЕН'}\n"
            f"• Текущее время: {datetime.now().strftime('%H:%M:%S')}\n\n"
            
            "⚡ Бот автоматически возобновит работу согласно расписанию!"
        )
        
        await update.message.reply_text(schedule_text)  # ✅ Убрал parse_mode='Markdown'
        
    except Exception as e:
        logging.error(f"❌ Ошибка в schedule_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при показе расписания")

# -------- ИСТОРИЯ & СИГНАЛЫ --------
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает последние 10 завершённых сделок пользователя"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    history = user_data.get('trade_history', [])
    if not history:
        await update.message.reply_text("📭 У вас пока нет истории сделок.")
        return

    # ✅ Берём только завершённые сделки
    finished_trades = [t for t in history if t.get('result') in ("WIN", "LOSS")]
    if not finished_trades:
        await update.message.reply_text("⏳ У вас пока нет завершённых сделок.")
        return

    # Последние 10 — новые сверху
    last_trades = finished_trades[-10:]
    lines = ["📈 *Последние 10 сделок:*", ""]
    for trade in reversed(last_trades):
        trade_id = trade.get('id', '?')
        date = trade.get('timestamp', '').replace("T", " ")[:16]
        pair = trade.get('pair', '?')
        direction = trade.get('direction', '?')
        result = trade.get('result', '')
        icon = "🟢" if result == "WIN" else "🔴"
        lines.append(f"#{trade_id} {date} {icon} {pair} {direction} | {result}")

    text = "\n".join(lines)
    await update.message.reply_text(text, parse_mode="Markdown")
    
async def next_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск следующего сигнала"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    # 🕒 ПРОВЕРКА РАБОЧЕГО ВРЕМЕНИ ДЛЯ РУЧНЫХ СИГНАЛОВ
    if not is_trading_time():
        now = datetime.now()
        current_weekday = now.weekday()
        
        # Расчет времени до следующего открытия
        if current_weekday in WEEKEND_DAYS:
            days_until_monday = (7 - current_weekday) % 7
            next_work_day = now + timedelta(days=days_until_monday)
            next_open = datetime.combine(next_work_day.date(), TRADING_START)
            reason = "выходной день"
        else:
            next_open = datetime.combine(now.date() + timedelta(days=1), TRADING_START)
            reason = "окончание рабочего дня"
        
        time_until = next_open - now
        hours = time_until.seconds // 3600
        minutes = (time_until.seconds % 3600) // 60
        
        await update.message.reply_text(
            f"⏸ **Сейчас нерабочее время бота**\n\n"
            f"📋 Причина: {reason}\n"
            f"🔄 **Бот начнет работу:**\n"
            f"⏰ {next_open.strftime('%d.%m.%Y в %H:%M')}\n"
            f"⏳ Через: {hours}ч {minutes}мин\n\n"
            f"🕒 Рабочие часы:\n"
            f"• {TRADING_START.strftime('%H:%M')}-{TRADING_END.strftime('%H:%M')}\n"
            f"• Без выходных (кроме субботы, воскресенья)",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
        )
        return
    if user_data.get('current_trade'):
        await update.message.reply_text(
            "⏳ У вас уже есть активная сделка! ождитесь её завершения.",
            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
        )
        return

    await update.message.reply_text("🔍 Ищу лучшие торговые сигналы...", reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True))

    random.shuffle(PAIRS)

    for pair in PAIRS:

        # ⏰ Проверяем фильтр по разрешённым часам из time_filters.json
        if not is_trade_allowed(pair):
            logging.info(f"⏰ Пропуск {pair} — неразрешённое время торговли (ручной поиск сигнала).")
            continue
        
        # ИСПРАВЛЕНИЕ: убрали user_id из вызова
        result = analyze_pair(pair)
        if len(result) >= 4:
            signal, expiry, conf, source = result[:4]
            ml_features_data = result[4] if len(result) > 4 else None

            if signal and conf >= 6:
                df = get_mt5_data(pair, 2, mt5.TIMEFRAME_M1)
                if df is None:
                    continue

                entry_price = df['close'].iloc[-1]
                chart_df = get_mt5_data(pair, 300, mt5.TIMEFRAME_M1)
                chart_path = enhanced_plot_chart(chart_df, pair, entry_price, signal)

                signal_text = (
                    f"🎯 ТОРГОВЫЙ СИГНАЛ\n\n"
                    f"💼 Пара: `{pair}`\n"
                    f"📊 Сигнал: {signal}\n"
                    f"💰 Цена входа: {entry_price:.5f}\n"
                    f"⏰ Экспирация: {expiry} мин\n"
                    f"🎯 Уверенность: {conf}/10\n"
                    f"🔍 Источник: {source}"
                )

                if chart_path:
                    with open(chart_path, 'rb') as photo:
                        await update.message.reply_photo(
                            photo=photo, 
                            caption=signal_text,
                            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
                        )
                    try:
                        os.remove(chart_path)
                    except:
                        pass
                    
                else:
                    await update.message.reply_text(signal_text, reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True))

                context.user_data['last_signal'] = {
                    'pair': pair,
                    'signal': signal,
                    'entry_price': entry_price,
                    'expiry': expiry,
                    'ml_features': ml_features_data,
                    'source': source
                }
                return

    await update.message.reply_text(
        "⚠ Сигналы не найдены. Попробуйте позже.",
        reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
)


# -------- СТАТИСТИКА & МОДЕЛИ --------
async def statistics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику пользователя на основе актуальных данных"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    # Используем trade_history из user_data, а не из глобальной переменной
    history = user_data.get('trade_history', [])

    # ✅ берём только завершённые сделки (WIN/LOSS)
    finished_trades = [t for t in history if t.get('result') in ("WIN", "LOSS")]

    total = len(finished_trades)
    wins = len([t for t in finished_trades if t.get('result') == "WIN"])
    losses = len([t for t in finished_trades if t.get('result') == "LOSS"])
    winrate = round(wins / total * 100, 1) if total > 0 else 0

    text = (
        "📊 СТАТИСТИКА ТОРГОВЛИ\n\n"
        f"📈 Всего сделок: {total}\n"
        f"🟢 Выигрыши: {wins}\n"
        f"🔴 Проигрыши: {losses}\n"
        f"🎯 Win Rate: {winrate}%"
    )

    await update.message.reply_text(text)
    
async def model_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает актуальную статистику ML модели, корректно читая ml_info.json"""
    try:
        # Пробуем подгрузить актуальные данные из ml_info.json
        info = {}
        if os.path.exists("ml_info.json"):
            with open("ml_info.json", "r", encoding="utf-8") as f:
                info = json.load(f)

            # ✅ Исправление: если это список (история переобучений), берём последнюю запись
            if isinstance(info, list):
                info = info[-1] if info else {}
        else:
            info = model_info  # fallback на глобальную переменную

        if not info or info.get("error"):
            stats_text = "❌ ML модель не обучена или произошла ошибка"
            if info and "error" in info:
                stats_text += f"\nОшибка: {info['error']}"
        else:
            # 🧮 Аккуратно обрабатываем метрики
            trades_used = info.get("trades_used", 0)
            n_features = info.get("n_features", 0)
            trained_at = info.get("trained_at", "N/A")

            train_acc = info.get("train_accuracy", 0)
            test_acc = info.get("test_accuracy", 0)
            cv_acc = info.get("cv_accuracy", 0)
            cv_std = info.get("cv_std", 0)

            # Если вдруг проценты >1, не умножаем ещё раз
            if train_acc > 1:
                train_acc = train_acc / 100
            if test_acc > 1:
                test_acc = test_acc / 100
            if cv_acc > 1:
                cv_acc = cv_acc / 100
            if cv_std > 1:
                cv_std = cv_std / 100

            win_rate = info.get("win_rate", 0)
            if win_rate > 1:
                win_rate = win_rate / 100

            overfit_ratio = 1.0
            if test_acc > 0:
                overfit_ratio = train_acc / test_acc

            train_samples = info.get("train_samples", 0)
            test_samples = info.get("test_samples", 0)

            stats_text = (
                f"📊 СТАТИСТИКА ML МОДЕЛИ\n\n"
                f"🕐 Обучена: {trained_at}\n"
                f"📈 Сделок: {trades_used}\n"
                f"🧠 Признаков: {n_features}\n"
                f"🎯 Точность (тест): {test_acc*100:.2f}%\n"
                f"🎯 Точность (train): {train_acc*100:.2f}%\n"
                f"📊 Win rate: {win_rate*100:.2f}%\n"
                f"🔍 Коэф. переобучения: {overfit_ratio:.2f}\n"
                f"📋 Тестовых: {test_samples}\n"
                f"📚 Обучающих: {train_samples}\n"
                f"🎯 Кросс-валидация: {cv_acc*100:.2f}% ± {cv_std*100:.2f}%"
            )

        await update.message.reply_text(
            stats_text,
            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True) 
        )
    except Exception as e:
        logging.error(f"Ошибка model_stats_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ошибка получения статистики модели",
            reply_markup=get_models_keyboard(update.effective_user.id)
        )


# ===================== 🔁 ОБНОВЛЁННАЯ КОМАНДА /retrain_model =====================
async def retrain_model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переобучает ML модель (доступно только администратору, с сравнением RF и MLP)"""
    user_id = update.effective_user.id

    # 🧩 Проверка прав доступа
    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text(
            "❌ Эта команда доступна только администратору.",
            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
        )
        return

    # 🔄 Уведомление о старте
    await update.message.reply_text(
        "🔄 Запускаю переобучение ML модели... Это может занять несколько минут.",
        reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
    )

    try:
        # 🚀 Запуск обучения
        result = train_ml_model()

        # ✅ Успех
        if result and not result.get("error"):
            test_acc = result.get("test_accuracy", 0)
            cv_accuracy = result.get("cv_accuracy", 0)
            trades_used = result.get("trades_used", 0)
            overfit = result.get("overfitting_ratio", 0)
            f1 = result.get("f1_score", 0)
            model_type = result.get("model_type", "N/A")
            win_rate = result.get("win_rate", 0)
            n_features = result.get("n_features", 0)
            train_acc = result.get("train_accuracy", 0)
            test_samples = result.get("test_samples", 0)
            train_samples = result.get("train_samples", 0)

            # Корректировка процентов
            if test_acc <= 1:
                test_acc *= 100
            if cv_accuracy <= 1:
                cv_accuracy *= 100

            # 🏆 Финальное сообщение
            msg = (
                f"✅ ML модель успешно переобучена!\n"
                f"📊 Точность (тест): {test_acc:.2f}%\n"
                f"🎯 Кросс-валидация: {cv_accuracy:.2f}%\n"
                f"📈 Сделок использовано: {trades_used}\n"
                f"🧠 Тип модели: {model_type}\n"
                f"📋 Признаков: {n_features} | Train={train_samples} | Test={test_samples}\n"
                f"📊 Win rate: {win_rate:.2f}%\n"
                f"📊 F1 Score: {f1:.2f}% | Overfit: {overfit:.2f}\n"
            )

            # Отправляем основное сообщение
            await update.message.reply_text(
                msg,
                reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
            )

            # 🏁 Лог в консоль
            logging.info(
                f"[ML] ✅ Модель переобучена ({model_type}): Test={test_acc:.2f}% | CV={cv_accuracy:.2f}% | Overfit={overfit:.2f}"
            )

            # 💡 Дополнительное уведомление о сравнении моделей
            if model_type == "MLPClassifier":
                await update.message.reply_text(
                    "🤖 Нейросеть (MLPClassifier) показала лучшие результаты и выбрана как основная модель 🏆",
                    reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
                )
            elif model_type == "RandomForestClassifier":
                await update.message.reply_text(
                    "🌲 RandomForestClassifier сохранил лидерство — стабильная точность и надёжность ✅",
                    reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
                )

        # ⚠️ Ошибка в обучении
        else:
            error_msg = result.get("error", "Неизвестная ошибка") if result else "Неизвестная ошибка"
            await update.message.reply_text(
                f"❌ Ошибка переобучения: {error_msg}",
                reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
            )
            logging.error(f"[ML] ❌ Ошибка переобучения: {error_msg}")

    except Exception as e:
        # 🧨 Критическая ошибка
        logging.exception(f"[ML] Ошибка при переобучении модели: {e}")
        await update.message.reply_text(
            f"❌ Критическая ошибка при переобучении: {e}",
            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
        )
# -------- TOGGLE FUNCTIONS (ML / GPT / SMC) --------
async def toggle_ml(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['ml_enabled'] = not user_data.get('ml_enabled', ML_ENABLED)
    status = "🟢 ML: ВКЛ" if user_data['ml_enabled'] else "🔴 ML: ВЫКЛ"
    await update.message.reply_text(f"⚙️ ML режим переключен: {status}", reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True))


async def toggle_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['gpt_enabled'] = not user_data.get('gpt_enabled', USE_GPT)
    status = "🟢 GPT: ВКЛ" if user_data['gpt_enabled'] else "🔴 GPT: ВЫКЛ"
    await update.message.reply_text(f"⚙️ GPT режим переключен: {status}", reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True))


async def toggle_smc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['smc_enabled'] = not user_data.get('smc_enabled', True)
    status = "🟢 SMC: ВКЛ" if user_data['smc_enabled'] else "🔴 SMC: ВЫКЛ"
    await update.message.reply_text(f"⚙️ SMC анализ переключен: {status}", reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True))


# -------- НОВЫЕ КОМАНДЫ (ДОБАВЬТЕ ЭТОТ БЛОК) --------
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает настройки бота"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    personal_stake = user_data.get('personal_stake', STAKE_AMOUNT)
    auto_trading = user_data.get('auto_trading', AUTO_TRADING)
    ml_enabled = user_data.get('ml_enabled', ML_ENABLED)
    gpt_enabled = user_data.get('gpt_enabled', USE_GPT)
    
    settings_text = (
        f"⚙️ НАСТРОЙКИ БОТА\n\n"
        f"💰 Ставка: {personal_stake}\n"
        f"🤖 Авто-торговля: {'✅ ВКЛ' if auto_trading else '❌ ВЫКЛ'}\n"
        f"🧠 ML: {'✅ ВКЛ' if ml_enabled else '❌ ВЫКЛ'}\n"
        f"💬 GPT: {'✅ ВКЛ' if gpt_enabled else '❌ ВЫКЛ'}\n\n"
        f"Используйте меню для изменения настроек."
    )
    
    await update.message.reply_text(settings_text, reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True))

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Останавливает бота (только для админа)"""
    user_id = update.effective_user.id
    
    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return
        
    global IS_RUNNING
    IS_RUNNING = False
    
    await update.message.reply_text("🛑 Бот остановлен. Для перезапуска перезапустите скрипт.")
    logging.info("Бот остановлен пользователем")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи с обновленной информацией"""
    try:
        help_text = (
            "🆘 ПОМОЩЬ И ПОДДЕРЖКА\n\n"
            
            "🎯 Как работает бот:\n"
            "• Автоматически анализирует рынок 24/7\n"
            "• Использует Smart Money Concepts (SMC)\n" 
            "• Ищет зоны спроса/предложения\n"
            "• Определяет ордер-блоки и уровни\n"
            "• Генерирует сигналы с уверенностью\n\n"
            
            "📊 Типы сигналов:\n"
            "• 🎯 ENHANCED_SMART_MONEY - основные сигналы\n"
            "• 🤖 ML_VALIDATED - машинное обучение\n"
            "• 💬 GPT - анализ искусственного интеллекта\n\n"
            
            "⏰ График работы:\n"
            "• Бот работает по установленному расписанию\n"
            "• Используйте кнопку '🕒 Расписание' для деталей\n"
            "• Вне рабочего времени анализ приостанавливается\n\n"
            
            "⚠️ Важно:\n"
            "• Всегда используйте управление рисками\n"
            "• Не инвестируйте больше, чем можете потерять\n"
            "• Сигналы не являются финансовой рекомендацией\n\n"
            
            "📞 Поддержка:\n"
            "По вопросам работы бота обращайтесь в группу поддержки:\n"
            "👉 https://t.me/+hKC6n9WrE6pkMzEy"
        )
        
        await update.message.reply_text(help_text)  # ✅ Убрал parse_mode='Markdown'
        
    except Exception as e:
        logging.error(f"❌ Ошибка в help_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при показе помощи")
        
# ===================== ⚙️ USER COMMANDS (ASYNC-SAFE) =====================

async def toggle_auto_trading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключает авто-трейдинг для пользователя (без блокировки event loop)"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    user_data['auto_trading'] = not user_data.get('auto_trading', False)
    status = "🟢 ВКЛ" if user_data['auto_trading'] else "🔴 ВЫКЛ"

    await update.message.reply_text(
        f"🤖 Авто-трейдинг: {status}",
        reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
    )

    # 💾 Асинхронное сохранение
    await async_save_users_data()


async def clear_active_trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очищает активную сделку (для отладки)"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    if user_data.get('current_trade'):
        trade_info = user_data['current_trade']
        user_data['current_trade'] = None
        await async_save_users_data()

        await update.message.reply_text(
            f"🔄 Активная сделка очищена:\n"
            f"Пара: {trade_info.get('pair')}\n"
            f"Направление: {trade_info.get('direction')}\n"
            f"Цена: {trade_info.get('entry_price')}\n\n"
            f"Теперь можно получить новый сигнал.",
            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            "✅ Активных сделок нет",
            reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
        )


async def restore_counter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстанавливает правильный счётчик сделок (без блокировки event loop)"""
    user_id = update.effective_user.id

    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return

    await update.message.reply_text("🔄 Восстановление счётчика сделок...")

    try:
        if MULTI_USER_MODE:
            for uid, user_data in users.items():
                actual_trades = len(user_data.get('trade_history', []))
                current_counter = user_data.get('trade_counter', 0)

                if actual_trades > current_counter:
                    user_data['trade_counter'] = actual_trades
                    await update.message.reply_text(
                        f"✅ Восстановлен счётчик для пользователя {uid}:\n"
                        f"Было: {current_counter}\n"
                        f"Стало: {actual_trades}"
                    )
                else:
                    await update.message.reply_text(
                        f"ℹ️ Счётчик для пользователя {uid} корректен: {current_counter}"
                    )
        else:
            actual_trades = len(single_user_data.get('trade_history', []))
            current_counter = single_user_data.get('trade_counter', 0)

            if actual_trades > current_counter:
                single_user_data['trade_counter'] = actual_trades
                await update.message.reply_text(
                    f"✅ Восстановлен счётчик:\n"
                    f"Было: {current_counter}\n"
                    f"Стало: {actual_trades}"
                )
            else:
                await update.message.reply_text(
                    f"ℹ️ Счётчик корректен: {current_counter}"
                )

        # 💾 Асинхронное сохранение базы
        await async_save_users_data()

    except Exception as e:
        logging.error(f"Ошибка восстановления счётчика: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def check_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет целостность данных"""
    user_id = update.effective_user.id
    
    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return
        
    try:
        message = "📊 ПРОВЕРКА ДАННЫХ:\n\n"
        
        if MULTI_USER_MODE:
            if os.path.exists("users_data.json"):
                with open("users_data.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                message += f"✅ users_data.json: {len(data)} пользователей\n"
                
                for uid, user_data in data.items():
                    trades = len(user_data.get('trade_history', []))
                    counter = user_data.get('trade_counter', 0)
                    message += f"👤 {uid}: сделок={trades}, счетчик={counter}\n"
            else:
                message += "❌ users_data.json не существует\n"
                
            message += f"\n📈 ТЕКУЩАЯ ПАМЯТЬ: {len(users)} пользователей\n"
            for uid, user_data in users.items():
                trades = len(user_data.get('trade_history', []))
                counter = user_data.get('trade_counter', 0)
                message += f"👤 {uid}: сделок={trades}, счетчик={counter}\n"
                
        else:
            if os.path.exists("single_user_data.json"):
                with open("single_user_data.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                trades = len(data.get('trade_history', []))
                counter = data.get('trade_counter', 0)
                message += f"✅ single_user_data.json: сделок={trades}, счетчик={counter}\n"
            else:
                message += "❌ single_user_data.json не существует\n"
                
            message += f"\n📈 ТЕКУЩАЯ ПАМЯТЬ: сделок={len(single_user_data.get('trade_history', []))}, счетчик={single_user_data.get('trade_counter', 0)}"
        
        await update.message.reply_text(message)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка проверки: {e}")

# ===================== ⚙️ RESTORE FROM BACKUP (ASYNC-SAFE) =====================
async def restore_from_backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстанавливает данные из последнего бэкапа (асинхронно и безопасно)"""
    user_id = update.effective_user.id

    # 🔐 Только администраторы
    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return

    await update.message.reply_text("🔄 Поиск резервных копий данных...")

    try:
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            await update.message.reply_text("❌ Папка backups/ не найдена")
            return

        # 📂 Ищем файлы бэкапов
        backup_files = [f for f in os.listdir(backup_dir) if f.startswith("users_data_backup")]
        if not backup_files:
            await update.message.reply_text("❌ Резервные копии не найдены в папке backups/")
            return

        # 📅 Сортируем по дате (новейшие первыми)
        backup_files.sort(reverse=True)
        latest_backup = os.path.join(backup_dir, backup_files[0])

        await update.message.reply_text(f"📂 Найдена резервная копия: {backup_files[0]}")

        # 🧠 Загружаем данные из бэкапа асинхронно
        async with aiofiles.open(latest_backup, "r", encoding="utf-8") as f:
            content = await f.read()
        backup_data = json.loads(content)

        # 🔒 Блокируем сохранение, чтобы никто не записывал в этот момент
        async with save_lock:
            global users
            users.clear()
            for uid_str, user_data in backup_data.items():
                users[int(uid_str)] = user_data

            # 💾 Асинхронно сохраняем восстановленные данные как текущие
            await async_save_users_data()

            # ✅ Обновляем память из сохранённого файла
            await asyncio.to_thread(load_users_data)

        logging.info("♻️ Память пользователей успешно обновлена после восстановления бэкапа")

        # 📊 Статистика
        total_trades = sum(len(u.get('trade_history', [])) for u in users.values())
        await update.message.reply_text(
            f"✅ Данные восстановлены из последнего бэкапа!\n"
            f"📊 Пользователей: {len(users)}\n"
            f"📈 Сделок: {total_trades}\n"
            f"♻️ Память обновлена — перезапуск не требуется"
        )

    except Exception as e:
        logging.error(f"💥 Ошибка восстановления из бэкапа: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка восстановления: {e}")



# ===================== ⚙️ RECALCULATE REAL ML FEATURES (ASYNC-SAFE) =====================
async def recalculate_real_ml_features_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Асинхронно пересчитывает ML-фичи на реальных данных для всех сделок"""
    user_id = update.effective_user.id

    # 🔐 Только админ
    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return

    await update.message.reply_text("🔄 Пересчёт РЕАЛЬНЫХ ML-фичей для всех сделок...")

    try:
        recalculated_count = 0
        failed_count = 0
        total_trades = 0

        # 📊 Подсчёт общего количества сделок
        if MULTI_USER_MODE:
            total_trades = sum(len(u.get("trade_history", [])) for u in users.values())
        else:
            total_trades = len(all_trades)

        processed = 0

        # 🧠 Основной цикл
        if MULTI_USER_MODE:
            for uid, udata in users.items():
                for trade in udata.get("trade_history", []):
                    if not trade.get("pair"):
                        continue

                    pair = trade["pair"]

                    # Получаем данные с MT5 — без блокировки event loop
                    df_m1 = await asyncio.to_thread(get_mt5_data, pair, 400, mt5.TIMEFRAME_M1)
                    if df_m1 is not None and len(df_m1) > 100:
                        # Подготовка фичей — CPU-нагрузка
                        feats = await asyncio.to_thread(prepare_ml_features, df_m1)
                        if feats:
                            trade["ml_features"] = feats
                            recalculated_count += 1
                            logging.info(f"✅ Пересчитаны фичи для {pair} ({len(feats)})")
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1

                    processed += 1
                    if processed % 20 == 0:
                        await update.message.reply_text(f"📊 Обработано {processed}/{total_trades} сделок...")

        else:
            # Режим одного пользователя
            for trade in all_trades:
                if not trade.get("pair"):
                    continue

                pair = trade["pair"]
                df_m1 = await asyncio.to_thread(get_mt5_data, pair, 400, mt5.TIMEFRAME_M1)
                if df_m1 is not None and len(df_m1) > 100:
                    feats = await asyncio.to_thread(prepare_ml_features, df_m1)
                    if feats:
                        trade["ml_features"] = feats
                        recalculated_count += 1
                        logging.info(f"✅ Пересчитаны фичи для {pair} ({len(feats)})")
                    else:
                        failed_count += 1
                else:
                    failed_count += 1

                processed += 1
                if processed % 20 == 0:
                    await update.message.reply_text(f"📊 Обработано {processed}/{total_trades} сделок...")

        # 💾 Асинхронное сохранение результатов
        if recalculated_count > 0:
            await async_save_users_data()

            # Проверяем пример фичей
            sample_features_count = 0
            trades_iter = (
                (trade for u in users.values() for trade in u.get("trade_history", []))
                if MULTI_USER_MODE
                else all_trades
            )
            for trade in trades_iter:
                if trade.get("ml_features"):
                    sample_features_count = len(trade["ml_features"])
                    break

            await update.message.reply_text(
                f"✅ Пересчёт завершён!\n"
                f"• Успешно: {recalculated_count}\n"
                f"• Ошибок: {failed_count}\n"
                f"• Кол-во фич: {sample_features_count}\n"
                f"💡 Можно запустить /retrain"
            )
        else:
            await update.message.reply_text("❌ Не удалось пересчитать ни одной сделки")

    except Exception as e:
        logging.error(f"💥 Ошибка пересчёта ML-фичей: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")


# ===================== ⚙️ RECALCULATE ML FEATURES (ASYNC-SAFE) =====================
async def recalculate_ml_features_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Асинхронно пересчитывает ML-фичи для всех сделок"""
    await update.message.reply_text("🔄 Начинаю пересчёт ML-фичей для всех сделок...")

    recalculated = 0
    errors = 0
    total = len(all_trades)

    try:
        for i, trade in enumerate(all_trades):
            try:
                # Пропускаем сделки без пары
                if not trade.get("pair"):
                    continue

                pair = trade["pair"]

                # 🔄 Получаем исторические данные в отдельном потоке
                df = await asyncio.to_thread(get_historical_data, pair)
                if df is None or df.empty:
                    errors += 1
                    continue

                # 🧠 Пересчитываем фичи — CPU-тяжёлая операция, выносим в отдельный поток
                new_features = await asyncio.to_thread(prepare_ml_features, df)

                if new_features:
                    trade["ml_features"] = new_features
                    recalculated += 1

                # Прогресс каждые 10 сделок
                if (i + 1) % 10 == 0:
                    await update.message.reply_text(f"📊 Обработано {i + 1}/{total} сделок...")

                # Небольшая пауза для предотвращения перегрузки CPU
                if (i + 1) % 50 == 0:
                    await asyncio.sleep(0.1)

            except Exception as e:
                errors += 1
                logging.error(f"❌ Ошибка пересчёта фич для {trade.get('pair')}: {e}")

        # 💾 Асинхронное сохранение всех обновлений
        await async_save_users_data()

        # 🧩 Определяем количество фич в одной из сделок
        sample_features_count = 0
        for trade in all_trades:
            if trade.get("ml_features"):
                sample_features_count = len(trade["ml_features"])
                break

        # 📢 Итоговое сообщение
        message = (
            f"✅ Пересчёт ML-фичей завершён!\n"
            f"• Всего сделок: {total}\n"
            f"• Успешно пересчитано: {recalculated}\n"
            f"• Ошибок: {errors}\n"
            f"• Количество фич: {sample_features_count if recalculated > 0 else 'N/A'}"
        )
        await update.message.reply_text(message)

    except Exception as e:
        logging.error(f"💥 Критическая ошибка пересчёта ML-фичей: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ===================== ⚙️ RESET ML FEATURES (ASYNC-SAFE) =====================
async def reset_ml_features_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Асинхронно очищает старые ML-фичи и помечает сделки для пересчёта"""
    user_id = update.effective_user.id

    # Только администратор может использовать
    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return

    await update.message.reply_text("🔄 Сброс ML-фичей для пересчёта на реальных данных...")

    try:
        reset_count = 0

        async with save_lock:
            if MULTI_USER_MODE:
                for uid, udata in users.items():
                    for trade in udata.get("trade_history", []):
                        if trade.get("ml_features"):
                            trade["ml_features"] = None
                            trade["needs_ml_recalculation"] = True
                            reset_count += 1
            else:
                for trade in single_user_data.get("trade_history", []):
                    if trade.get("ml_features"):
                        trade["ml_features"] = None
                        trade["needs_ml_recalculation"] = True
                        reset_count += 1

            # 💾 Асинхронное сохранение
            await async_save_users_data()

        if reset_count > 0:
            await update.message.reply_text(
                f"✅ Сброшено ML-фичей: {reset_count} сделок\n"
                f"🧠 Теперь используйте /recalculateml для пересчёта на реальных данных"
            )
        else:
            await update.message.reply_text("ℹ️ Нет ML-фичей для сброса")

    except Exception as e:
        logging.error(f"💥 Ошибка сброса ML-фичей: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ===================== ⚙️ FORCE ENABLE ML (ASYNC-SAFE) =====================
async def force_enable_ml_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительно включает ML независимо от точности"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    user_data["ml_enabled"] = True

    async with save_lock:
        await async_save_users_data()

    await update.message.reply_text(
        "🟢 ML ПРИНУДИТЕЛЬНО ВКЛЮЧЕН!\n"
        "📊 Текущая точность: 50.0%\n"
        "⚠️ Модель будет использоваться даже с низкой точностью\n"
        "🔄 Она улучшится со временем при накоплении данных"
    )

# ===================== ⚙️ CLEAR ALL TRADES (ASYNC-SAFE) =====================
async def clear_all_trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительно очищает все открытые сделки у всех пользователей (только для админа)"""
    user_id = update.effective_user.id

    # Проверка прав через is_admin()
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды.")
        return

    cleared_count = 0

    try:
        async with save_lock:  # 🔒 Гарантируем, что никто другой не пишет users_data
            for uid, data in users.items():
                if data.get("current_trade"):
                    data["current_trade"] = None
                    cleared_count += 1
                    logging.info(f"🧹 Принудительно очищена сделка у пользователя {uid}")

            # 💾 Асинхронное сохранение данных
            await async_save_users_data()

        logging.info(f"✅ Админ {user_id} очистил {cleared_count} открытых сделок у всех пользователей")

        await update.message.reply_text(
            f"🧹 Принудительно очищено сделок: {cleared_count}\n"
            f"💾 Изменения сохранены успешно."
        )

    except Exception as e:
        logging.error(f"💥 Ошибка при очистке сделок: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка при очистке сделок: {e}")

async def restore_pocket_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительно восстанавливает всех пользователей в pocket_users.json"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return
        
    await update.message.reply_text("🔄 Принудительное восстановление pocket_users.json...")
    
    try:
        check_and_restore_pocket_users()
        whitelist = load_whitelist()
        
        await update.message.reply_text(
            f"✅ Восстановление завершено!\n"
            f"📊 Пользователей в pocket_users.json: {len(whitelist)}"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка восстановления: {e}")
  
# ===================== MARKET STATUS COMMAND =====================
async def market_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статус работы бота по фиксированному локальному графику"""
    now = datetime.now()
    status = "🟢 РАБОТАЕТ" if is_trading_time() else "🔴 ВНЕ ГРАФИКА"

    # Рассчитываем время до следующего открытия, если сейчас вне графика
    if not is_trading_time():
        today_open = datetime.combine(now.date(), TRADING_START)
        tomorrow_open = datetime.combine(now.date() + timedelta(days=1), TRADING_START)
        next_open = today_open if now.time() < TRADING_START else tomorrow_open
        time_until_open = next_open - now
        hours, remainder = divmod(int(time_until_open.total_seconds()), 3600)
        minutes = remainder // 60
        until_text = f"⏰ До открытия: {hours} ч {minutes} мин"
    else:
        until_text = "✅ Бот сейчас активно работает"

    status_text = (
        f"📊 СТАТУС РАБОТЫ БОТА\n\n"
        f"🕐 Текущее локальное время: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📈 Статус: {status}\n"
        f"{until_text}\n\n"
        f"🕒 График работы:\n"
        f"• Каждый день: {TRADING_START.strftime('%H:%M')} — {TRADING_END.strftime('%H:%M')}"
    )

    await update.message.reply_text(status_text)

# 🔧 ДОБАВЬТЕ ЭТУ ФУНКЦИЮ ПОСЛЕ market_status_command
async def debug_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает отладочную информацию о данных пользователя"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    # Данные из памяти
    memory_trades = len(user_data.get('trade_history', []))
    memory_counter = user_data.get('trade_counter', 0)
    
    # Данные из файла (если есть)
    file_trades = 0
    if MULTI_USER_MODE and os.path.exists("users_data.json"):
        with open("users_data.json", "r", encoding="utf-8") as f:
            file_data = json.load(f)
            if str(user_id) in file_data:
                file_trades = len(file_data[str(user_id)].get('trade_history', []))
    
    debug_text = (
        f"🔧 ОТЛАДКА ДАННЫХ\n\n"
        f"👤 User ID: {user_id}\n"
        f"💾 В памяти: {memory_trades} сделок, счетчик: {memory_counter}\n"
        f"📁 В файле: {file_trades} сделок\n"
        f"📊 Завершённых: {len([t for t in user_data.get('trade_history', []) if t.get('result') in ('WIN', 'LOSS')])}"
    )
    
    await update.message.reply_text(debug_text)

# ===================== HANDLE MESSAGE =====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений и кнопок - ОДИНАКОВО ДЛЯ ВСЕХ"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        logging.info(f"📨 Сообщение от {user_id}: {text}")
        
        # 🔥 АВТОМАТИЧЕСКАЯ РЕГИСТРАЦИЯ ПРИ ЛЮБОМ СООБЩЕНИИ
        user_data = get_user_data(user_id)
        if 'created_at' not in user_data:
            username = update.effective_user.username or "Unknown"
            await register_or_update_user(user_id, username, update)
            logging.info(f"✅ Автоматически зарегистрирован пользователь {user_id}")
            
            # Приветственное сообщение для новых пользователей
            welcome_text = (
                "🎯 **Добро пожаловать в ASPIRE TRADE!**\n\n"
                "🤖 **О боте:**\n"
                "• Автоматический торговый бот\n" 
                "• Анализ рынка в реальном времени\n"
                "• Умные сигналы на основе SMC анализа\n"
                "• Работает 24/7 в установленные часы\n\n"
                "📱 **Доступные функции:**\n"
                "• ❓ Помощь - инструкция и поддержка\n"
                "• 🕒 Расписание - график работы бота\n\n"
                "⚡ **Бот работает автоматически** - вы будете получать сигналы согласно расписанию!"
            )
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True),
                parse_mode='Markdown'
            )
        
        # 🔥 ОБРАБОТКА КНОПОК ДЛЯ ВСЕХ (только 2 кнопки)
        if text == "❓ Помощь":
            await help_command(update, context)
        elif text == "🕒 Расписание":
            await schedule_command(update, context)
        else:
            # Если нажата неизвестная кнопка
            await update.message.reply_text(
                "❓ Используйте кнопки меню:\n"
                "• ❓ Помощь - справка по боту\n" 
                "• 🕒 Расписание - график работы",
                reply_markup=ReplyKeyboardMarkup([["❓ Помощь", "🕒 Расписание"]], resize_keyboard=True)
            )
            
    except Exception as e:
        logging.error(f"❌ Ошибка в handle_message: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке сообщения")
# ===================== 🚀 ЗАГЛУШКИ ДЛЯ КОМАНД АДМИНА =====================

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Статистика - функция доступна только администратору")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ Настройки - функция доступна только администратору")

async def retrain_ml_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Переобучить ML - функция доступна только администратору")

async def stop_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 Стоп Бот - функция доступна только администратору")

async def start_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("▶️ Старт Бот - функция доступна только администратору")

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Логи - функция доступна только администратору")

async def clear_trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧹 Очистить сделки - функция доступна только администратору")

# ===================== 🔍 SETUP TRADE MONITORING =====================
def setup_trade_monitoring():
    """Инициализация мониторинга сделок и автоочистки устаревших job'ов"""
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
    global app

    try:
        if app is None or not hasattr(app, "job_queue") or app.job_queue is None:
            logging.warning("⚠ setup_trade_monitoring: JobQueue недоступен — мониторинг не запущен")
            return

        job_queue = app.job_queue

        async def cleanup_expired_trade_jobs(context: ContextTypes.DEFAULT_TYPE):
            """Очистка устаревших job'ов старше 24 часов"""
            try:
                jobs = job_queue.jobs()
                now = datetime.utcnow()
                expired = 0

                for job in jobs:
                    next_run = getattr(job, "next_t", None)
                    if not next_run:
                        continue

                    try:
                        job_time = datetime.fromtimestamp(next_run)
                    except Exception:
                        continue

                    if (now - job_time).total_seconds() > 86400:  # старше 24 часов
                        job.schedule_removal()
                        expired += 1

                if expired > 0:
                    logging.info(f"🧹 Удалено устаревших задач: {expired}")
            except Exception as e:
                logging.error(f"⚠ Ошибка очистки job'ов: {e}", exc_info=True)

        # ✅ Запускаем регулярную очистку каждые 6 часов
        job_queue.run_repeating(
            cleanup_expired_trade_jobs,
            interval=21600,  # 6 часов
            first=300,       # через 5 минут после старта
            name="cleanup_expired_trade_jobs"
        )

        # ✅ Подключаем listener для логирования статуса задач
        job_queue.scheduler.add_listener(
            job_listener,
            EVENT_JOB_ERROR | EVENT_JOB_EXECUTED
        )

        logging.info("🔧 Мониторинг сделок и автоочистка job'ов инициализированы успешно")

    except Exception as e:
        logging.error(f"❌ Ошибка инициализации мониторинга сделок: {e}", exc_info=True)



# ===================== MAIN =====================
def main():
    global app, save_lock

    # 🔒 Асинхронная блокировка для безопасного сохранения users_data.json
    import asyncio
    save_lock = asyncio.Lock()

    # ===================== 1. ПРОВЕРКА ЛОГОВ =====================
    try:
        with open("bot_ai.log", "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 50}\n")
            f.write(f"🔄 Перезапуск бота: {datetime.now()}\n")
            f.write(f"{'=' * 50}\n")
        logging.info("✅ Права доступа к лог-файлу проверены")
    except Exception as e:
        print(f"❌ Ошибка доступа к лог-файлу: {e}")
        return

    # ===================== 2. ВОССТАНОВЛЕНИЕ ПОЛЬЗОВАТЕЛЕЙ =====================
    try:
        check_and_restore_pocket_users()
    except Exception as e:
        logging.error(f"❌ Ошибка при восстановлении пользователей: {e}")

    # ===================== 3. СТАТУС БОТА =====================
    global BOT_LAST_STATUS, BOT_STATUS_NOTIFIED
    BOT_LAST_STATUS = is_trading_time()
    BOT_STATUS_NOTIFIED = False

    status_text = "🟢 РАБОТАЕТ" if BOT_LAST_STATUS else "🔴 ОСТАНОВЛЕН (вне рабочего времени)"
    logging.info(f"🤖 Статус бота при запуске: {status_text}")
    print(f"🤖 Статус бота при запуске: {status_text}")

    if not BOT_LAST_STATUS:
        now = datetime.now()
        logging.warning(f"⚠ Бот запущен в нерабочее время: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print("⚠ ВНИМАНИЕ: бот будет ждать начала торгового времени.")

    # ===================== 4. ПОДКЛЮЧЕНИЕ К MT5 =====================
    if not mt5.initialize(path=MT5_PATH, login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
        logging.error(f"❌ Ошибка инициализации MT5: {mt5.last_error()}")
        return
    logging.info("✅ MT5 подключен успешно")
    print("✅ MT5 подключен успешно")

    # ===================== 5. ИНИЦИАЛИЗАЦИЯ TELEGRAM APP =====================
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=20.0,
        write_timeout=20.0,
        pool_timeout=10.0,
    )
    app = Application.builder().token(TELEGRAM_TOKEN).request(request).build()

    # ===================== 6. МОНИТОРИНГ СДЕЛОК =====================
    try:
        setup_trade_monitoring()
        logging.info("🔧 Мониторинг сделок и автоочистка job'ов инициализированы")
    except Exception as e:
        logging.error(f"❌ Ошибка инициализации мониторинга сделок: {e}")

    # ===================== 7. РЕГИСТРАЦИЯ КОМАНД =====================
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("whitelist_add", whitelist_add_command))
    app.add_handler(CommandHandler("whitelist_remove", whitelist_remove_command))
    app.add_handler(CommandHandler("whitelist_stats", whitelist_stats_command))
    app.add_handler(CommandHandler("whitelist_show", whitelist_show_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("next", next_signal_command))
    app.add_handler(CommandHandler("stats", statistics_command))
    app.add_handler(CommandHandler("modelstats", model_stats_command))
    app.add_handler(CommandHandler("retrain", retrain_model_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cleartrade", clear_active_trade_command))
    app.add_handler(CommandHandler("repairml", repair_ml_command))
    app.add_handler(CommandHandler("restorecounter", restore_counter_command))
    app.add_handler(CommandHandler("checkdata", check_data_command))
    app.add_handler(CommandHandler("restorebackup", restore_from_backup_command))
    app.add_handler(CommandHandler("recalculateml", recalculate_real_ml_features_command))
    app.add_handler(CommandHandler("resetml", reset_ml_features_command))
    app.add_handler(CommandHandler("forceml", force_enable_ml_command))
    app.add_handler(CommandHandler("marketstatus", market_status_command))
    app.add_handler(CommandHandler("clearalltrades", clear_all_trades_command))
    app.add_handler(CommandHandler("restorepocket", restore_pocket_users_command))
    app.add_handler(CommandHandler("checktrades", check_active_trades_command))
    app.add_handler(CommandHandler("forcetradeclose", force_close_trade_command))
    app.add_handler(CommandHandler("debug", debug_user_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ===================== 8. JOB QUEUE =====================
    job_queue = app.job_queue
    if job_queue:
        # ----- Основной авто-трейдинг -----
        job_queue.run_repeating(
            auto_trading_loop,
            interval=90,
            first=10,
            name="auto_trading_loop",
            job_kwargs={"misfire_grace_time": 15},
        )

        # ----- Проверка зависших сделок -----
        job_queue.run_repeating(
            check_expired_trades_job,
            interval=300,
            first=30,
            name="expired_trades_check",
            job_kwargs={"misfire_grace_time": 30},
        )

        # ----- Автоматический бэкап -----
        async def auto_backup_job(context):
            try:
                await async_save_users_data()
                backup_name = f"backups/users_data_backup_auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                await asyncio.to_thread(shutil.copy, "users_data.json", backup_name)
                logging.info(f"💾 Автобэкап создан: {backup_name}")
            except Exception as e:
                logging.error(f"⚠ Ошибка авто-бэкапа: {e}")

        job_queue.run_repeating(
            auto_backup_job,
            interval=10800,  # каждые 3 часа
            first=120,
            name="auto_backup_job",
            job_kwargs={"misfire_grace_time": 60},
        )

        # ----- Listener для отслеживания задач -----
        from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

        def job_listener(event):
            if event.exception:
                logging.error(f"💥 Ошибка в задаче: {event.job_id} — {event.exception}")
            else:
                logging.info(f"✅ Задача {event.job_id} выполнена успешно")

        job_queue.scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)
        logging.info("📅 JobQueue инициализирован — автоцикл каждые 90 сек с защитой от сбоев")

    else:
        logging.error("❌ JobQueue не инициализирован — автоцикл не запущен")
        return

    # ===================== 9. СТАРТ БОТА =====================
    try:
        logging.info("🤖 Бот запущен и готов к работе!")
        app.run_polling(stop_signals=None)
    except (KeyboardInterrupt, SystemExit):
        logging.warning("🛑 Остановка бота вручную...")
    finally:
        # ===================== 10. КОРРЕКТНОЕ ЗАВЕРШЕНИЕ =====================
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(async_save_users_data())
            else:
                loop.run_until_complete(async_save_users_data())
        except Exception as e:
            logging.error(f"⚠ Ошибка сохранения данных при выходе: {e}")

        mt5.shutdown()
        logging.info("💾 Данные сохранены, MT5 отключен")
        print("💾 Данные сохранены, MT5 отключен")


# ===================== ASYNC SAVE USERS =====================
async def async_save_users_data():
    """Асинхронное безопасное сохранение users_data.json"""
    try:
        async with save_lock:
            await asyncio.to_thread(save_users_data)
            logging.info("💾 Данные пользователей сохранены (async-safe)")
    except Exception as e:
        logging.error(f"❌ Ошибка async_save_users_data: {e}", exc_info=True)


if __name__ == "__main__":
    main()
