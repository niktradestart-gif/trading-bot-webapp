import asyncio
import sys
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging
import os
import json
import random
from datetime import datetime, timedelta,  time
from typing import Optional, Dict, List
from functools import wraps

# Market & math
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import argrelextrema
import mplfinance as mpf
from matplotlib.patches import Rectangle
from apscheduler.events import EVENT_JOB_MISSED, EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

# ===================== JOB QUEUE LISTENER =====================
def job_listener(event):
    """Обработчик событий job queue"""
    if event.code == EVENT_JOB_MISSED:
        logging.warning(f"⏰ Job {event.job_id} был пропущен!")
    elif event.code == EVENT_JOB_ERROR:
        logging.error(f"❌ Job {event.job_id} завершился ошибкой: {event.exception}")
    elif event.code == EVENT_JOB_EXECUTED:
        logging.debug(f"✅ Job {event.job_id} выполнен успешно")

# ===================== FIXED BOT WORKING HOURS =====================
from datetime import datetime, time, timedelta

# Telegram
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)
# ML
import talib as ta
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
import joblib
import pickle

# OpenAI
from openai import OpenAI


# ===================== FIXED BOT WORKING HOURS =====================
from datetime import datetime, time, timedelta

# 🕒 Рабочие часы по локальному времени (например, Молдова UTC+2)
TRADING_START = time(4, 0)    # Начало торговли: 04:00
TRADING_END   = time(23, 59)  # Конец торговли: 23:59

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

# ===================== KEYBOARDS =====================
from telegram import ReplyKeyboardMarkup

# Главное меню
main_keyboard = [
    ["📊 Торговля", "⚙️ Управление"],
    ["📈 Статистика", "🧠 Модели"],
    ["📅 Расписание", "📋 Помощь"]
]
main_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)

# 📊 Торговля
def get_trading_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Динамическая клавиатура торговли"""
    user_data = get_user_data(user_id)
    auto_status = "🟢 Авто-торговля: ВКЛ" if user_data.get('auto_trading', False) else "🔴 Авто-торговля: ВЫКЛ"
    
    keyboard = [
        ["🔄 Следующий сигнал", "📈 История"],
        [auto_status],
        ["◀️ Главное меню"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ⚙️ Управление
management_keyboard = [
    ["🎯 Изменить ставку", "📊 Статус системы"],
    ["🛑 Остановить бота"],
    ["◀️ Главное меню"]
]
management_markup = ReplyKeyboardMarkup(management_keyboard, resize_keyboard=True)

# 🧠 Модели
def get_models_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Динамическая клавиатура для моделей с текущим состоянием"""
    user_data = get_user_data(user_id)
    
    ml_status = "🟢 ML: ВКЛ" if user_data.get('ml_enabled', ML_ENABLED) else "🔴 ML: ВЫКЛ"
    gpt_status = "🟢 GPT: ВКЛ" if user_data.get('gpt_enabled', USE_GPT) else "🔴 GPT: ВЫКЛ"
    smc_status = "🟢 SMC: ВКЛ" if user_data.get('smc_enabled', True) else "🔴 SMC: ВЫКЛ"
    
    keyboard = [
        ["📊 ML Статистика", "🔄 Обучить ML"],
        [ml_status, gpt_status],
        [smc_status],
        ["◀️ Главное меню"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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
    return user_id == ADMIN_USER_ID


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


def load_users_data():
    """📥 Надёжная загрузка данных с бэкапами и восстановлением счетчиков"""
    global users, single_user_data
    try:
        if MULTI_USER_MODE:
            if os.path.exists("users_data.json"):
                success = load_from_file("users_data.json", "multi")
                if not success:
                    backups = [f for f in os.listdir("backups") if f.startswith("users_data_backup")]
                    if backups:
                        backups.sort(reverse=True)
                        latest = os.path.join("backups", backups[0])
                        logging.warning(f"⚠ Повреждён файл, пробуем бэкап: {latest}")
                        load_from_file(latest, "multi")
                    else:
                        users = {}
                        logging.warning("⚠ Нет бэкапов — пустая база")
            else:
                users = {}
                logging.info("📝 users_data.json не найден — создаём новую базу")
        else:
            if os.path.exists("single_user_data.json"):
                success = load_from_file("single_user_data.json", "single")
                if not success:
                    backups = [f for f in os.listdir("backups") if f.startswith("single_user_backup")]
                    if backups:
                        backups.sort(reverse=True)
                        latest = os.path.join("backups", backups[0])
                        logging.warning(f"⚠ Повреждён single файл, пробуем бэкап: {latest}")
                        load_from_file(latest, "single")
                    else:
                        single_user_data = create_default_single_data()
            else:
                single_user_data = create_default_single_data()
                logging.info("📝 single_user_data.json не найден — создаём новую базу")
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
                hist_count = len(udata.get('trade_history', []))
                if udata.get('trade_counter', 0) != hist_count:
                    users[uid]['trade_counter'] = hist_count
            logging.info(f"✅ Загружено {len(users)} пользователей")
        else:
            single_user_data.update(data)
            hist_count = len(single_user_data.get('trade_history', []))
            if single_user_data.get('trade_counter', 0) != hist_count:
                single_user_data['trade_counter'] = hist_count
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
    """Определяет структуру рынка - HH, HL, LH, LL"""
    highs = df['high'].values
    lows = df['low'].values
    structure_points = []
    
    for i in range(lookback, len(df) - lookback):
        if (highs[i] > max(highs[i-lookback:i]) and 
            highs[i] > max(highs[i+1:i+lookback+1])):
            structure_points.append({
                'type': 'HH',
                'price': highs[i],
                'index': i,
                'time': df.index[i]
            })
        if (lows[i] < min(lows[i-lookback:i]) and 
            lows[i] < min(lows[i+1:i+lookback+1])):
            structure_points.append({
                'type': 'LL',
                'price': lows[i],
                'index': i,
                'time': df.index[i]
            })
    
    return structure_points[-8:]

def find_horizontal_levels(df, threshold_pips=0.0005):
    try:
        levels = []
        prices = pd.concat([df['high'], df['low'], df['close']]).sort_values()
        price_values = prices.values
        clusters = []
        
        i = 0
        while i < len(price_values):
            current_price = price_values[i]
            cluster = [current_price]
            
            j = i + 1
            while j < len(price_values) and abs(price_values[j] - current_price) <= threshold_pips:
                cluster.append(price_values[j])
                j += 1
            
            if len(cluster) >= 5:
                cluster_mean = np.mean(cluster)
                
                touches = 0
                for idx in range(len(df)):
                    high = df['high'].iloc[idx]
                    low = df['low'].iloc[idx]
                    if (low <= cluster_mean <= high) or \
                       (abs(high - cluster_mean) <= threshold_pips) or \
                       (abs(low - cluster_mean) <= threshold_pips):
                        touches += 1
                
                if touches >= 6:
                    recent_prices = df['close'].tail(20)
                    above_level = sum(recent_prices > cluster_mean)
                    below_level = sum(recent_prices < cluster_mean)
                    
                    level_type = "RESISTANCE" if above_level > below_level else "SUPPORT"
                    
                    levels.append({
                        'price': cluster_mean,
                        'touches': touches,
                        'type': level_type,
                        'strength': 'STRONG' if touches > 10 else 'MEDIUM',
                        'cluster_size': len(cluster)
                    })
            
            i = j
        
        unique_levels = []
        for level in levels:
            is_duplicate = False
            for existing in unique_levels:
                if abs(level['price'] - existing['price']) <= threshold_pips:
                    is_duplicate = True
                    if level['touches'] > existing['touches']:
                        unique_levels.remove(existing)
                        unique_levels.append(level)
                    break
            
            if not is_duplicate:
                unique_levels.append(level)
        
        return sorted(unique_levels, key=lambda x: x['touches'], reverse=True)[:8]
        
    except Exception as e:
        logging.error(f"Ошибка поиска горизонтальных уровней: {e}")
        return []

def find_supply_demand_zones(df, strength=2, lookback=25):
    try:
        highs = df['high'].values
        lows = df['low'].values
        volumes = df['tick_volume'].values
        zones = []
        
        high_peaks = argrelextrema(highs, np.greater, order=strength)[0]
        low_peaks = argrelextrema(lows, np.less, order=strength)[0]
        
        avg_volume = np.mean(volumes[-50:]) if len(volumes) > 50 else np.mean(volumes)
        
        for peak in high_peaks[-8:]:
            if peak > 15:
                peak_high = highs[peak]
                if (peak_high > np.max(highs[max(0, peak-15):peak]) and 
                    peak_high > np.max(highs[peak+1:min(len(highs), peak+16)])):
                    
                    volume_ratio = volumes[peak] / avg_volume if avg_volume > 0 else 1
                    
                    if volume_ratio > 1.3:
                        zones.append({
                            'type': 'SUPPLY',
                            'top': peak_high,
                            'bottom': peak_high * 0.999,
                            'strength': 'STRONG' if volume_ratio > 2.0 else 'MEDIUM',
                            'index': peak,
                            'volume_ratio': volume_ratio,
                            'source': 'EXTREME'
                        })
        
        for valley in low_peaks[-8:]:
            if valley > 15:
                valley_low = lows[valley]
                if (valley_low < np.min(lows[max(0, valley-15):valley]) and 
                    valley_low < np.min(lows[valley+1:min(len(lows), valley+16)])):
                    
                    volume_ratio = volumes[valley] / avg_volume if avg_volume > 0 else 1
                    
                    if volume_ratio > 1.3:
                        zones.append({
                            'type': 'DEMAND',
                            'top': valley_low * 1.001,
                            'bottom': valley_low,
                            'strength': 'STRONG' if volume_ratio > 2.0 else 'MEDIUM',
                            'index': valley,
                            'volume_ratio': volume_ratio,
                            'source': 'EXTREME'
                        })
        
        horizontal_levels = find_horizontal_levels(df)
        for level in horizontal_levels:
            zone_width = 0.0003
            zones.append({
                'type': 'SUPPLY' if level['type'] == 'RESISTANCE' else 'DEMAND',
                'top': level['price'] + zone_width,
                'bottom': level['price'] - zone_width,
                'strength': level['strength'],
                'index': len(df) - 1,
                'volume_ratio': 1.5,
                'source': 'HORIZONTAL',
                'touches': level['touches']
            })
        
        zones.sort(key=lambda x: (
            3 if x['strength'] == 'STRONG' else 2 if x['strength'] == 'MEDIUM' else 1,
            x.get('touches', 0),
            x['volume_ratio']
        ), reverse=True)
        
        return zones[:5]
        
    except Exception as e:
        logging.error(f"Ошибка поиска зон: {e}")
        return []
    
def calculate_order_blocks_advanced(df):
    """Улучшенный поиск ордер-блоков с лучшим обнаружением"""
    order_blocks = []
    avg_candle_size = df['high'].subtract(df['low']).rolling(50).mean().iloc[-1]
    
    if pd.isna(avg_candle_size) or avg_candle_size == 0:
        avg_candle_size = df['high'].subtract(df['low']).mean()
    
    for i in range(20, len(df) - 10):
        current_candle = df.iloc[i]
        candle_body = abs(current_candle['close'] - current_candle['open'])
        candle_range = current_candle['high'] - current_candle['low']
        
        is_significant = (candle_body > avg_candle_size * 2.0 or 
                         candle_range > avg_candle_size * 2.5)
        
        if not is_significant:
            continue
            
        # Медвежий OB
        if (current_candle['close'] < current_candle['open'] and
            candle_body > avg_candle_size * 1.8):
            
            next_candles = df.iloc[i+1:i+8]
            if len(next_candles) >= 3:
                touched_ob = any(low < current_candle['close'] for low in next_candles['low'])
                rebounded = any(close > current_candle['close'] for close in next_candles['close'])
                
                if touched_ob and rebounded:
                    order_blocks.append({
                        'type': 'BEARISH_OB',
                        'high': current_candle['open'],
                        'low': current_candle['close'],
                        'index': i,
                        'strength': 'STRONG'
                    })
        
        # Бычий OB
        elif (current_candle['close'] > current_candle['open'] and
              candle_body > avg_candle_size * 1.8):
            
            next_candles = df.iloc[i+1:i+8]
            if len(next_candles) >= 3:
                touched_ob = any(high > current_candle['close'] for high in next_candles['high'])
                rebounded = any(close < current_candle['close'] for close in next_candles['close'])
                
                if touched_ob and rebounded:
                    order_blocks.append({
                        'type': 'BULLISH_OB',
                        'high': current_candle['close'],
                        'low': current_candle['open'],
                        'index': i,
                        'strength': 'STRONG'
                    })
    
    return order_blocks[-3:]

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
    Улучшенный расчёт экспирации для бинарных сделок (1–4 мин)
    ⚡ Приоритет 1 минуты на импульсах и сильных сигналах
    """
    try:
        atr = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14).iloc[-1]
        current_price = df['close'].iloc[-1]
        volatility_percent = (atr / current_price) * 100 if current_price > 0 else 0

        # 📊 1. Базовая экспирация по волатильности
        if volatility_percent >= 0.035:         # импульсное движение — часто нужен короткий вход
            base_expiry = 1
        elif volatility_percent >= 0.02:       # нормальная волатильность
            base_expiry = 2
        elif volatility_percent >= 0.01:       # спокойный рынок
            base_expiry = 3
        else:                                  # флет, слабое движение
            base_expiry = 4

        # 📌 2. Корректировка по типу сигнала
        if signal_type == "BREAKOUT":
            # На пробоях чаще лучше быстрая экспирация
            base_expiry = max(1, base_expiry - 1)
        elif signal_type == "REVERSAL":
            # Развороты часто требуют чуть больше времени
            base_expiry = min(base_expiry + 1, 4)

        # 📌 3. Корректировка по уверенности сигнала
        if confidence >= 9:
            # Очень сильный сигнал — часто лучше короткая экспирация (1 минута)
            final_expiry = 1
        elif confidence >= 6:
            # Средняя уверенность — экспирация не более 2 минут
            final_expiry = min(base_expiry, 2)
        else:
            # Слабый сигнал — используем базовое значение
            final_expiry = base_expiry

        # 🧠 4. Границы безопасности
        final_expiry = max(1, min(final_expiry, 4))

        logging.info(
            f"📊 Волатильность: {volatility_percent:.4f}% | тип={signal_type} | conf={confidence} → экспирация: {final_expiry} мин"
        )
        return final_expiry

    except Exception as e:
        logging.error(f"Ошибка расчёта динамической экспирации: {e}")
        return 2

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
# ===================== EXHAUSTION FILTER =====================
def is_exhausted_move(df, trend_analysis):
    """Определяет истощение движения для фильтрации ложных сигналов"""
    try:
        if len(df) < 20:
            return False
            
        current_price = df['close'].iloc[-1]
        rsi = trend_analysis.get('rsi_value', 50)
        
        # 1. Проверка RSI в экстремумах
        if rsi < 25 or rsi > 75:
            # 2. Проверка резкого движения
            price_change_5m = (current_price - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100
            price_change_15m = (current_price - df['close'].iloc[-15]) / df['close'].iloc[-15] * 100
            
            # 3. Проверка объема
            current_volume = df['tick_volume'].iloc[-1]
            avg_volume = df['tick_volume'].tail(20).mean()
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Критерии истощения:
            # - Резкое движение (>0.3% за 5 минут)
            # - RSI в экстремуме
            # - Объем снижается после пика
            if abs(price_change_5m) > 0.3 and volume_ratio < 0.8:
                logging.info(f"⚠️ Обнаружено истощение движения: RSI={rsi:.1f}, Δ5m={price_change_5m:.2f}%, Δ15m={price_change_15m:.2f}%")
                return True
                
        return False
        
    except Exception as e:
        logging.error(f"Ошибка в is_exhausted_move: {e}")
        return False

def enhanced_smart_money_analysis(df):
    if df is None or len(df) < 100:
        return None, None, 0, "NO_DATA"
    
    try:
        logging.info(f"🔧 SMC анализ запущен для {len(df)} свечей")
        
        # =============== АНАЛИТИЧЕСКИЕ БЛОКИ ===============
        zones = find_supply_demand_zones(df)
        structure = find_market_structure(df)
        order_blocks = calculate_order_blocks_advanced(df)
        fibonacci = calculate_fibonacci_levels(df)
        trend_analysis = enhanced_trend_analysis(df)
        liquidity_levels = liquidity_analysis(df)
        pa_patterns = price_action_patterns(df)
        candle_time = get_candle_time_info()
        
        # =============== НОВЫЙ ФИЛЬТР ИСТОЩЕНИЯ ===============
        if is_exhausted_move(df, trend_analysis):
            logging.warning("⏸️ Движение истощено — пропускаем сигналы против импульса")
            # В случае истощения можно рассматривать сигналы на отскок
            if trend_analysis['rsi_state'] == 'OVERSOLD':
                return "BUY", 2, 4, "EXHAUSTION_BOUNCE"
            elif trend_analysis['rsi_state'] == 'OVERBOUGHT':
                return "SELL", 2, 4, "EXHAUSTION_BOUNCE"
            return None, None, 0, "EXHAUSTED_MOVE"

        # =============== ОСНОВНОЙ АНАЛИЗ ===============
        breakouts = check_level_breakouts(df, df['close'].iloc[-1], zones)
        logging.info(f"📊 SMC найдено: зон={len(zones)}, пробоев={len(breakouts)}")

        current_price = df['close'].iloc[-1]
        signal, confidence, signal_type = None, 0, None
        
        buy_signals = 0
        sell_signals = 0
        buy_confidence = 0
        sell_confidence = 0

        bearish_breakouts = [b for b in breakouts if b['type'] == 'BEARISH_BREAKOUT']
        bullish_breakouts = [b for b in breakouts if b['type'] == 'BULLISH_BREAKOUT']
        
        if bearish_breakouts:
            logging.info(f"📉 Обнаружены медвежьи пробои: {len(bearish_breakouts)}")
            sell_confidence += len(bearish_breakouts) * 3
            
        if bullish_breakouts:
            logging.info(f"📈 Обнаружены бычьи пробои: {len(bullish_breakouts)}")
            buy_confidence += len(bullish_breakouts) * 3

        # 🟡 Ранний вход
        early_signal, early_conf, early_source = early_entry_strategy(df, candle_time, trend_analysis)
        if early_signal:
            return early_signal, 1, early_conf + 2, f"EARLY_{early_source}"

        # 🟠 Вход в конце свечи
        closing_signal, closing_conf, closing_source = closing_candle_strategy(df, candle_time, trend_analysis)
        if closing_signal:
            return closing_signal, 1, closing_conf + 2, f"CLOSING_{closing_source}"

        # =============== АНАЛИЗ ЗОН ===============
        for zone in zones:
            if zone['strength'] in ['STRONG', 'MEDIUM']:
                zone_middle = (zone['top'] + zone['bottom']) / 2
                distance_to_zone = min(abs(current_price - zone['top']), abs(current_price - zone['bottom']))
                
                if distance_to_zone <= (zone['top'] - zone['bottom']) * 2:
                    
                    if (zone['type'] == 'DEMAND' and 
                        current_price >= zone['bottom'] and 
                        not any(b['type'] == 'BEARISH_BREAKOUT' and b['zone'] == zone for b in breakouts)):
                        
                        base_confidence = 3
                        if zone['source'] == 'HORIZONTAL':
                            base_confidence += 1
                        if trend_analysis['direction'] == 'BULLISH':
                            base_confidence += 1
                        
                        bull_patterns = [p for p in pa_patterns if 'BULLISH' in p['type']]
                        if bull_patterns:
                            base_confidence += 1
                        
                        buy_signals += 1
                        buy_confidence += base_confidence
                        logging.info(f"✅ SMC зона спроса: BUY +{base_confidence}")
                        
                    elif (zone['type'] == 'SUPPLY' and 
                          current_price <= zone['top'] and
                          not any(b['type'] == 'BULLISH_BREAKOUT' and b['zone'] == zone for b in breakouts)):
                        
                        base_confidence = 3
                        if zone['source'] == 'HORIZONTAL':
                            base_confidence += 1
                        if trend_analysis['direction'] == 'BEARISH':
                            base_confidence += 1
                        
                        bear_patterns = [p for p in pa_patterns if 'BEARISH' in p['type']]
                        if bear_patterns:
                            base_confidence += 1
                        
                        sell_signals += 1
                        sell_confidence += base_confidence
                        logging.info(f"✅ SMC зона предложения: SELL +{base_confidence}")

        # =============== ОРДЕР-БЛОКИ ===============
        for ob in order_blocks:
            ob_middle = (ob['high'] + ob['low']) / 2
            if (ob['type'] == 'BULLISH_OB' and 
                current_price <= ob_middle and
                ob['low'] <= current_price <= ob['high']):
                
                conf_boost = 2
                if liquidity_levels.get('near_sell_liquidity'):
                    conf_boost += 1
                
                buy_signals += 1
                buy_confidence += conf_boost
                logging.info(f"✅ SMC бычий OB: BUY +{conf_boost}")
                
            elif (ob['type'] == 'BEARISH_OB' and 
                  current_price >= ob_middle and
                  ob['low'] <= current_price <= ob['high']):
                
                conf_boost = 2
                if liquidity_levels.get('near_buy_liquidity'):
                    conf_boost += 1
                
                sell_signals += 1
                sell_confidence += conf_boost
                logging.info(f"✅ SMC медвежий OB: SELL +{conf_boost}")

        # =============== РАЗРЕШЕНИЕ КОНФЛИКТОВ ===============
        if buy_signals > 0 and sell_signals > 0:
            logging.info(f"⚖️ Конфликт сигналов: BUY={buy_signals}(conf:{buy_confidence}) vs SELL={sell_signals}(conf:{sell_confidence})")
            
            if buy_confidence > sell_confidence:
                signal, confidence = 'BUY', buy_confidence
                logging.info(f"✅ Разрешен конфликт в пользу BUY")
            elif sell_confidence > buy_confidence:
                signal, confidence = 'SELL', sell_confidence
                logging.info(f"✅ Разрешен конфликт в пользу SELL")
            else:
                logging.info(f"❌ Конфликт не разрешен — равные confidence")
                return None, None, 0, "CONFLICT_SIGNAL"
        elif buy_signals > 0:
            signal, confidence = 'BUY', buy_confidence
        elif sell_signals > 0:
            signal, confidence = 'SELL', sell_confidence

        # =============== ДОПОЛНИТЕЛЬНЫЕ БОНУСЫ ===============
        for fib in fibonacci:
            if abs(current_price - fib["level"]) / current_price < 0.0015:
                if fib["ratio"] in [38, 50, 61]:
                    confidence += 1
                    logging.info(f"✅ SMC фибо уровень: +1")

        if len(structure) >= 2 and signal:
            last_structure = structure[-1]['type']
            if last_structure == 'HH' and signal == 'BUY':
                confidence += 2
                logging.info(f"✅ SMC структура HH: +2")
            elif last_structure == 'LL' and signal == 'SELL':
                confidence += 2
                logging.info(f"✅ SMC структура LL: +2")

        for pattern in pa_patterns:
            if pattern['type'] == 'BULLISH_ENGULFING' and signal == 'BUY':
                confidence += 2
                logging.info(f"✅ SMC бычий engulfing: +2")
            elif pattern['type'] == 'BEARISH_ENGULFING' and signal == 'SELL':
                confidence += 2
                logging.info(f"✅ SMC медвежий engulfing: +2")
            elif 'PIN' in pattern['type'] and signal:
                confidence += 1
                logging.info(f"✅ SMC pin bar: +1")

        # =============== ВРЕМЕННОЙ БОНУС ===============
        if signal:
            if candle_time['is_beginning']:
                confidence -= 1
                logging.info(f"⚠️ Начало свечи — понижаем уверенность: -1")
            elif candle_time['is_ending']:
                confidence += 1
                logging.info(f"✅ Конец свечи — усиливаем уверенность: +1")

        confidence = max(0, min(confidence, 10))

        if confidence >= 2:
            logging.info(f"🎯 SMC СИГНАЛ: {signal} (conf:{confidence})")
            expiry = calculate_dynamic_expiry(df, confidence, signal_type)
            return signal, expiry, confidence, "ENHANCED_SMART_MONEY"

        logging.info(f"❌ SMC не нашел сигналов (conf:{confidence})")
        return None, None, 0, "NO_SMC_SIGNAL"
    
    except Exception as e:
        logging.error(f"💥 Ошибка SMC анализа: {e}")
        return None, None, 0, "SMC_ERROR"


ml_model = None
ml_scaler = None
model_info = {}
ML_PROBABILITY_THRESHOLD = 0.6  # Порог для принятия торгового решения

def prepare_ml_features(df):
    """Готовит полный словарь из 50+ ML-признаков для сделки и обучения"""
    try:
        if df is None or len(df) < 100:
            return None

        close, high, low, volume = df['close'], df['high'], df['low'], df['tick_volume']
        features = {}

        # ===================== 📌 БАЗОВЫЕ ПРИЗНАКИ (УЛУЧШЕННЫЕ) =====================
        features['price'] = float(close.iloc[-1])
        features['volume'] = float(volume.iloc[-1]) if not volume.isna().all() else 0.0
        
        # 📈 RSI с несколькими периодами
        for period in [14, 21]:
            rsi = ta.RSI(close, timeperiod=period)
            features[f'rsi_{period}'] = float(rsi.iloc[-1]) if len(close) >= period and not rsi.isna().all() else 50.0
        
        # 📊 ATR с ratio (новый признак)
        atr = ta.ATR(high, low, close, timeperiod=14)
        if len(close) >= 14 and not atr.isna().all():
            features['atr'] = float(atr.iloc[-1])
            # ATR Ratio - отношение текущего ATR к среднему за 50 периодов
            atr_50 = atr.rolling(50).mean()
            features['atr_ratio'] = float(atr.iloc[-1] / atr_50.iloc[-1]) if len(atr_50) > 0 and not pd.isna(atr_50.iloc[-1]) else 1.0
        else:
            features['atr'] = 0.0
            features['atr_ratio'] = 1.0
        
        # 📈 OBV (On-Balance Volume) - новый признак
        try:
            obv = ta.OBV(close, volume)
            features['obv'] = float(obv.iloc[-1]) if not obv.isna().all() else 0.0
            # OBV тренд (производная)
            if len(obv) > 5:
                obv_trend = obv.diff(5).iloc[-1]
                features['obv_trend'] = float(obv_trend) if not pd.isna(obv_trend) else 0.0
            else:
                features['obv_trend'] = 0.0
        except Exception:
            features['obv'] = 0.0
            features['obv_trend'] = 0.0
        
        features['adx'] = float(ta.ADX(high, low, close, timeperiod=14).iloc[-1]) if len(close) >= 14 else 0.0
        
        # 📊 Ценовые изменения с разными периодами
        for period in [15, 30, 60]:  # M1, M2, M4
            if len(close) >= period:
                price_change = (close.iloc[-1] - close.iloc[-period]) / close.iloc[-period] * 100
                features[f'price_change_{period}m'] = float(price_change)
            else:
                features[f'price_change_{period}m'] = 0.0
        
        features['volatility'] = float(close.pct_change().std() * 100)

        # ===================== 📈 MACD =====================
        try:
            macd, _, _ = ta.MACD(close, 12, 26, 9)
            features['macd'] = float(macd.iloc[-1]) if not macd.isna().all() else 0.0
        except Exception:
            features['macd'] = 0.0

        # ===================== 📊 Bollinger Bands =====================
        try:
            bb_u, _, bb_l = ta.BBANDS(close, timeperiod=20)
            if not bb_u.isna().all() and not bb_l.isna().all():
                bb_range = bb_u.iloc[-1] - bb_l.iloc[-1]
                features['bb_position'] = float((close.iloc[-1] - bb_l.iloc[-1]) / max(1e-9, bb_range))
            else:
                features['bb_position'] = 0.5
        except Exception:
            features['bb_position'] = 0.5

        # ===================== 🕯️ СВЕЧНЫЕ ПАТТЕРНЫ (УЛУЧШЕННЫЕ) =====================
        try:
            # Определяем свечные паттерны более надежно
            current_open = df['open'].iloc[-1]
            current_high = df['high'].iloc[-1] 
            current_low = df['low'].iloc[-1]
            current_close = df['close'].iloc[-1]
            
            prev_open = df['open'].iloc[-2] if len(df) > 1 else current_open
            prev_high = df['high'].iloc[-2] if len(df) > 1 else current_high
            prev_low = df['low'].iloc[-2] if len(df) > 1 else current_low
            prev_close = df['close'].iloc[-2] if len(df) > 1 else current_close
            
            # Bullish Engulfing
            features['bullish_engulfing'] = 1 if (
                prev_close < prev_open and  # предыдущая медвежья
                current_close > current_open and  # текущая бычья
                current_open < prev_close and  # открытие ниже закрытия предыдущей
                current_close > prev_open  # закрытие выше открытия предыдущей
            ) else 0
            
            # Bearish Engulfing  
            features['bearish_engulfing'] = 1 if (
                prev_close > prev_open and  # предыдущая бычья
                current_close < current_open and  # текущая медвежья
                current_open > prev_close and  # открытие выше закрытия предыдущей
                current_close < prev_open  # закрытие ниже открытия предыдущей
            ) else 0
            
            # Three White Soldiers (упрощенная версия)
            if len(df) >= 4:
                soldiers = all([
                    df['close'].iloc[-3] > df['open'].iloc[-3],  # 3 свечи назад бычья
                    df['close'].iloc[-2] > df['open'].iloc[-2],  # 2 свечи назад бычья  
                    df['close'].iloc[-1] > df['open'].iloc[-1],  # текущая бычья
                    df['close'].iloc[-1] > df['close'].iloc[-2],  # каждая следующая выше
                    df['close'].iloc[-2] > df['close'].iloc[-3]
                ])
                features['three_white_soldiers'] = 1 if soldiers else 0
            else:
                features['three_white_soldiers'] = 0
                
        except Exception:
            features['bullish_engulfing'] = 0
            features['bearish_engulfing'] = 0  
            features['three_white_soldiers'] = 0

        # ===================== 📏 РАССТОЯНИЕ ДО HIGH/LOW (НОВОЕ) =====================
        try:
            # Расстояние до дневного high/low в %
            daily_high = high.tail(1440).max()  # 24 часа
            daily_low = low.tail(1440).min()
            
            features['distance_to_daily_high'] = float((daily_high - close.iloc[-1]) / daily_high * 100) if daily_high > 0 else 50.0
            features['distance_to_daily_low'] = float((close.iloc[-1] - daily_low) / close.iloc[-1] * 100) if close.iloc[-1] > 0 else 50.0
            
            # Позиция в дневном диапазоне (0-1)
            daily_range = daily_high - daily_low
            if daily_range > 0:
                features['daily_range_position'] = float((close.iloc[-1] - daily_low) / daily_range)
            else:
                features['daily_range_position'] = 0.5
                
        except Exception:
            features['distance_to_daily_high'] = 50.0
            features['distance_to_daily_low'] = 50.0
            features['daily_range_position'] = 0.5

        # ===================== 🧠 SMC ПРИЗНАКИ =====================
        try:
            # Импортируем функции SMC анализа (должны быть определены в вашем коде)
            from your_smc_module import (
                find_supply_demand_zones, find_market_structure, 
                calculate_order_blocks_advanced, calculate_fibonacci_levels,
                price_action_patterns, detect_round_levels
            )
            
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

            features['smc_has_demand_zone'] = 1 if any(z.get('type') == 'DEMAND' for z in zones) else 0
            features['smc_has_supply_zone'] = 1 if any(z.get('type') == 'SUPPLY' for z in zones) else 0
            features['smc_has_bullish_ob'] = 1 if any(ob.get('type') == 'BULLISH_OB' for ob in order_blocks) else 0
            features['smc_has_bearish_ob'] = 1 if any(ob.get('type') == 'BEARISH_OB' for ob in order_blocks) else 0
            features['smc_has_engulfing'] = 1 if any('ENGULFING' in p.get('type', '') for p in pa_patterns) else 0
            features['smc_has_pinbar'] = 1 if any('PIN' in p.get('type', '') for p in pa_patterns) else 0

            current_price = close.iloc[-1]
            round_info = detect_round_levels(current_price)
            features['smc_round_distance_pips'] = float(round_info.get('distance_pips', 100))
            features['smc_round_strength'] = {'WEAK': 0, 'MEDIUM': 1, 'STRONG': 2, 'VERY_STRONG': 3}.get(round_info.get('strength', 'WEAK'), 0)

        except Exception as e:
            logging.warning(f"SMC features error: {e}")
            for key in [
                'smc_zones_count','smc_structure_count','smc_ob_count','smc_fib_count','smc_patterns_count',
                'smc_has_demand_zone','smc_has_supply_zone','smc_has_bullish_ob','smc_has_bearish_ob',
                'smc_has_engulfing','smc_has_pinbar','smc_round_distance_pips','smc_round_strength'
            ]:
                features[key] = 0

        # ===================== 📐 ГОРИЗОНТАЛЬНЫЕ УРОВНИ =====================
        try:
            from your_technical_module import find_horizontal_levels
            
            horizontal_levels = find_horizontal_levels(df)
            features['horizontal_levels_count'] = len(horizontal_levels)
            if horizontal_levels:
                closest_level = min(horizontal_levels, key=lambda x: abs(x['price'] - close.iloc[-1]))
                features['distance_to_horizontal_level'] = abs(closest_level['price'] - close.iloc[-1]) * 10000
                features['horizontal_level_strength'] = closest_level['touches']
                features['is_near_horizontal_level'] = 1 if features['distance_to_horizontal_level'] < 5 else 0
            else:
                features['distance_to_horizontal_level'] = 100
                features['horizontal_level_strength'] = 0
                features['is_near_horizontal_level'] = 0
        except Exception as e:
            logging.warning(f"Horizontal levels error: {e}")
            features['horizontal_levels_count'] = 0
            features['distance_to_horizontal_level'] = 100
            features['horizontal_level_strength'] = 0
            features['is_near_horizontal_level'] = 0

        # ===================== 🕒 ВРЕМЯ И СВЕЧИ =====================
        try:
            from your_time_module import get_candle_time_info, early_entry_strategy, closing_candle_strategy
            
            candle_time = get_candle_time_info()

            features['candle_seconds_remaining'] = candle_time.get('seconds_remaining', 0)
            features['candle_seconds_passed'] = candle_time.get('seconds_passed', 0)
            features['candle_completion_percent'] = candle_time.get('completion_percent', 0)
            features['candle_is_beginning'] = 1 if candle_time.get('is_beginning', False) else 0
            features['candle_is_middle'] = 1 if candle_time.get('is_middle', False) else 0
            features['candle_is_ending'] = 1 if candle_time.get('is_ending', False) else 0

            current_candle = df.iloc[-1]
            features['candle_body_size'] = abs(current_candle['close'] - current_candle['open'])
            features['candle_range'] = current_candle['high'] - current_candle['low']
            features['candle_body_ratio'] = features['candle_body_size'] / max(1e-9, features['candle_range'])

            features['early_gap_signal'] = 1 if early_entry_strategy(df, candle_time, {'direction': 'NEUTRAL'})[0] else 0
            features['closing_breakout_signal'] = 1 if closing_candle_strategy(df, candle_time, {'direction': 'NEUTRAL'})[0] else 0
        except Exception as e:
            logging.warning(f"Candle time features error: {e}")
            for key in [
                'candle_seconds_remaining','candle_seconds_passed','candle_completion_percent',
                'candle_is_beginning','candle_is_middle','candle_is_ending',
                'candle_body_size','candle_range','candle_body_ratio',
                'early_gap_signal','closing_breakout_signal'
            ]:
                features[key] = 0

        # ===================== 🧮 КОНТЕКСТНЫЕ (УЛУЧШЕННЫЕ) =====================
        features['exhaustion_rsi_extreme'] = 1 if (features.get('rsi_14', 50) < 25 or features.get('rsi_14', 50) > 75) else 0

        # Используем самый короткий доступный период для импульса
        price_change_key = 'price_change_15m' if 'price_change_15m' in features else 'price_change_1h'
        price_change_1h = features.get(price_change_key, 0)
        features['strong_impulse'] = 1 if abs(price_change_1h) > 0.3 else 0

        volume_avg_20 = df['tick_volume'].tail(20).mean() if 'tick_volume' in df.columns else 1
        current_volume = df['tick_volume'].iloc[-1] if 'tick_volume' in df.columns else 1
        features['volume_declining'] = 1 if current_volume < (volume_avg_20 * 0.8) else 0

        features['signal_vs_trend_conflict'] = 0
        features['signal_vs_rsi_conflict'] = 0

        # ===================== 🧹 ОЧИСТКА NaN =====================
        for k, v in features.items():
            if pd.isna(v):
                features[k] = 0

        logging.debug(f"✅ Подготовлено {len(features)} ML признаков")
        return features

    except Exception as e:
        logging.error(f"❌ Ошибка ML features: {e}", exc_info=True)
        return None

def ml_predict_enhanced(features_dict: dict, pair: str, current_price: float):
    """
    ML прогноз с учетом отобранных признаков
    """
    global ml_model, ml_scaler
    try:
        if ml_model is None or ml_scaler is None:
            logging.warning(f"⚠ ML модель не загружена — предикт {pair} невозможен")
            return {"probability": 0.5, "confidence": 0, "signal": None}

        # 🔧 Загружаем список отобранных признаков
        selected_features = []
        try:
            with open("ml_features_selected.pkl", "rb") as f:
                selected_features = pickle.load(f)
        except:
            # Если файла нет, используем все признаки
            selected_features = list(features_dict.keys())
            logging.info(f"📝 Используем все {len(selected_features)} признаков (файл отбора не найден)")

        # ✅ Используем только отобранные признаки в правильном порядке
        features_array = np.array([features_dict.get(f, 0.0) for f in selected_features]).reshape(1, -1)

        features_scaled = ml_scaler.transform(features_array)
        probabilities = ml_model.predict_proba(features_scaled)[0]
        win_probability = float(probabilities[1])
        confidence_score = abs(win_probability - 0.5) * 2

        signal = None
        if win_probability >= ML_PROBABILITY_THRESHOLD:
            signal = "BUY"
        elif win_probability <= (1 - ML_PROBABILITY_THRESHOLD):
            signal = "SELL"

        logging.info(
            f"🤖 ML прогноз {pair}: WIN={win_probability:.3f}, "
            f"уверенность={confidence_score:.3f}, сигнал={signal}, "
            f"признаков={len(selected_features)}"
        )

        return {
            "probability": win_probability,
            "confidence": confidence_score,
            "signal": signal,
            "price": current_price,
            "features_used": len(selected_features)
        }

    except Exception as e:
        logging.error(f"❌ Ошибка ml_predict_enhanced для {pair}: {e}", exc_info=True)
        return {"probability": 0.5, "confidence": 0, "signal": None}

def validate_ml_signal_with_context(ml_result, trend_analysis, pair):
    """Валидирует ML сигнал с учетом рыночного контекста (тренд, RSI, импульсы)"""
    if not ml_result or not ml_result.get('signal'):
        return ml_result

    signal = ml_result['signal']
    confidence = ml_result['confidence']

    # 1️⃣ Фильтр против тренда
    if (signal == 'BUY' and trend_analysis.get('direction') == 'BEARISH' and 
        trend_analysis.get('strength') in ['STRONG', 'VERY_STRONG']):
        confidence *= 0.5
        logging.info(f"⚠️ ML валидация: BUY против сильного медвежьего тренда ({pair})")

    elif (signal == 'SELL' and trend_analysis.get('direction') == 'BULLISH' and 
          trend_analysis.get('strength') in ['STRONG', 'VERY_STRONG']):
        confidence *= 0.5
        logging.info(f"⚠️ ML валидация: SELL против сильного бычьего тренда ({pair})")

    # 2️⃣ Фильтр RSI экстремумов
    if signal == 'BUY' and trend_analysis.get('rsi_state') == 'OVERBOUGHT':
        confidence *= 0.6
        logging.info(f"⚠️ ML валидация: BUY в зоне перекупленности ({pair})")

    elif signal == 'SELL' and trend_analysis.get('rsi_state') == 'OVERSOLD':
        confidence *= 0.6
        logging.info(f"⚠️ ML валидация: SELL в зоне перепроданности ({pair})")

    # 3️⃣ Фильтр импульсных движений
    if trend_analysis.get('is_strong_impulse', False):
        impulse_dir = trend_analysis.get('impulse_direction')
        if impulse_dir and signal != impulse_dir:
            confidence *= 0.4  # Сильное наказание за торговлю против импульса
            logging.info(f"⚠️ ML валидация: сигнал против сильного импульса ({pair})")

    ml_result['confidence'] = min(confidence, 1.0)  # Ограничиваем сверху 1.0
    ml_result['validated'] = confidence >= 0.3  # минимальный порог после фильтров

    return ml_result

def should_take_trade(pair: str, smc_signal: dict, ml_result: dict, rsi_value: float, trends: dict) -> bool:
    """
    Комбинированный фильтр для сигналов перед входом в сделку.
    Возвращает True если сигнал достаточно силён для входа.
    """
    try:
        # 1️⃣ Проверяем SMC
        if smc_signal and smc_signal.get('signal'):
            smc_conf = smc_signal.get('confidence', 0)
            smc_dir = smc_signal.get('signal')
        else:
            smc_conf = 0
            smc_dir = None

        # 2️⃣ Проверяем ML
        if ml_result:
            ml_dir = ml_result.get('signal')
            ml_conf = ml_result.get('confidence', 0)
            ml_valid = ml_result.get('validated', False)
        else:
            ml_dir = None
            ml_conf = 0
            ml_valid = False

        # 3️⃣ Проверяем RSI
        rsi_overbought = rsi_value >= 70
        rsi_oversold = rsi_value <= 30

        # 4️⃣ Проверяем тренды
        major_trend = trends.get('M30', 'NEUTRAL')
        minor_trend = trends.get('M5', 'NEUTRAL')

        # ========== ЛОГИКА ФИЛЬТРА ==========
        # 🚫 Отсеиваем слабые сигналы
        if smc_conf < 4 and (ml_conf < 0.15 or not ml_valid):
            return False

        # ✅ Если SMC сильный и ML не противоречит — вход
        if smc_dir and smc_conf >= 6:
            if ml_dir is None or ml_dir == smc_dir:
                return True

        # ✅ Если ML уверен и подтверждён контекстом — можно входить даже без SMC
        if ml_valid and ml_conf >= 0.25:
            # Подтверждение трендом
            if ml_dir == 'BUY' and (minor_trend == 'BULLISH' or major_trend == 'BULLISH') and not rsi_overbought:
                return True
            if ml_dir == 'SELL' and (minor_trend == 'BEARISH' or major_trend == 'BEARISH') and not rsi_oversold:
                return True

        # 🚫 RSI против тренда
        if ml_dir == 'BUY' and rsi_overbought:
            return False
        if ml_dir == 'SELL' and rsi_oversold:
            return False

        return False

    except Exception as e:
        logging.error(f"[FILTER] Ошибка фильтрации сигнала для {pair}: {e}")
        return False

def train_ml_model_enhanced():
    """Улучшенная версия обучения с ансамблированием и отбором признаков"""
    global ml_model, ml_scaler, model_info
    
    # 🔧 Инициализация лучшего результата
    if not hasattr(train_ml_model_enhanced, 'best_test_score'):
        train_ml_model_enhanced.best_test_score = 0
    
    try:
        # 🧠 Сбор сделок (замените на ваши глобальные переменные)
        all_trades = []
        
        # 🔧 ЗАМЕНИТЕ ЭТИ ПЕРЕМЕННЫЕ НА ВАШИ РЕАЛЬНЫЕ
        MULTI_USER_MODE = False  # Измените на True если используете multi-user
        users = {}  # Ваш словарь пользователей
        single_user_data = {'trade_history': []}  # Ваши данные пользователя
        
        if MULTI_USER_MODE:
            for user_data in users.values():
                all_trades.extend(user_data.get('trade_history', []))
            logging.info(f"📊 ML: собрано {len(all_trades)} сделок из {len(users)} пользователей")
        else:
            all_trades.extend(single_user_data.get('trade_history', []))
            logging.info(f"📊 ML: собрано {len(all_trades)} сделок из одного пользователя")

        # 📌 Фильтр завершённых сделок с ML фичами
        completed_trades = [
            t for t in all_trades 
            if t.get('result') in ['WIN', 'LOSS'] 
            and t.get('ml_features') 
            and isinstance(t.get('ml_features'), dict)
        ]
        
        logging.info(f"📊 ML: завершённых сделок с ML фичами: {len(completed_trades)}")
        
        if len(completed_trades) < 30:
            logging.warning(f"⚠ Недостаточно данных для обучения: {len(completed_trades)} < 30")
            if not isinstance(model_info, dict):
                model_info = {}
            model_info["error"] = f"Недостаточно данных: {len(completed_trades)} сделок"
            return None

        # 🧭 Определяем признаки
        feature_names = None
        for t in completed_trades[-100:]:
            feats = t.get('ml_features')
            if isinstance(feats, dict) and len(feats) >= 30:
                feature_names = list(feats.keys())
                break

        if not feature_names:
            logging.warning("❌ Нет сделок с ml_features — обучение невозможно")
            return None

        # 📊 Формируем X и y
        X, y = [], []
        for trade in completed_trades:
            feats = trade.get('ml_features')
            if isinstance(feats, dict):
                row = [feats.get(f, 0.0) for f in feature_names]
                if len(row) == len(feature_names) and all(isinstance(x, (int, float)) for x in row):
                    X.append(row)
                    # 🔧 Target Smoothing: взвешенный таргет для уверенных сделок
                    result = trade.get('result')
                    if result == "WIN":
                        # Если сделка с высоким профитом - считаем более уверенной
                        profit = trade.get('profit_pips', 0)
                        if profit > 20:  # сильная сделка
                            y.append(1.0)
                        else:  # слабая сделка
                            y.append(0.7)
                    else:  # LOSS
                        loss = abs(trade.get('profit_pips', 0))
                        if loss > 20:  # сильный убыток
                            y.append(0.0)
                        else:  # небольшой убыток
                            y.append(0.3)

        if len(X) < 30:
            logging.warning(f"⚠ Недостаточно данных для обучения ML: {len(X)}")
            return None

        X = np.array(X, dtype=float)
        y = np.array(y, dtype=float)
        logging.info(f"🤖 ML: подготовлено {len(X)} образцов с {X.shape[1]} фичами")
        logging.info(f"📊 Target distribution: mean={np.mean(y):.3f}, std={np.std(y):.3f}")

        # 🎯 Time Decay - веса для последних сделок
        sample_weights = np.ones(len(X))
        if len(X) > 50:
            # Последние 25% сделок получают больший вес (примерно 7 дней при 100 сделках)
            recent_count = max(7, len(X) // 4)
            sample_weights[-recent_count:] = 1.4
            logging.info(f"⏰ Time decay: {recent_count} последних сделок с весом 1.4x")

        # 🧪 Масштабирование
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # 🌲 Feature Selection - отбираем топ-25 признаков
        if X_scaled.shape[1] > 25:
            selector = SelectKBest(score_func=f_classif, k=min(25, X_scaled.shape[1]))
            X_selected = selector.fit_transform(X_scaled, (y > 0.5).astype(int))
            selected_features = [feature_names[i] for i in selector.get_support(indices=True)]
            logging.info(f"🔍 Feature selection: выбрано {len(selected_features)} из {len(feature_names)} признаков")
        else:
            X_selected = X_scaled
            selected_features = feature_names

        # 🎯 Model Stacking: RandomForest + LogisticRegression
        if len(X) > 100:  # Используем stacking только при достаточном количестве данных
            base_models = [
                ('rf', RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    min_samples_split=10,
                    random_state=42,
                    class_weight='balanced'
                )),
                ('lr', LogisticRegression(
                    C=0.1,
                    random_state=42,
                    class_weight='balanced',
                    max_iter=1000
                ))
            ]
            
            model = VotingClassifier(
                estimators=base_models,
                voting='soft',  # Используем вероятности
                weights=[2, 1]  # Больший вес для RandomForest
            )
            logging.info("🤖 Используем Model Stacking (RF + LR)")
        else:
            # Для малого количества данных используем только RandomForest
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                min_samples_split=15,
                random_state=42,
                class_weight='balanced'
            )
            logging.info("🤖 Используем RandomForest (мало данных)")

        # 📊 Разделение на train/test
        X_train, X_test, y_train, y_test, weights_train, weights_test = train_test_split(
            X_selected, y, sample_weights, test_size=0.25, stratify=(y > 0.5).astype(int), random_state=42
        )

        # 🏋️ Обучение с весами
        model.fit(X_train, y_train > 0.5, sample_weight=weights_train)

        # 📈 Предсказания
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        y_pred = (y_pred_proba > 0.5).astype(int)
        y_test_binary = (y_test > 0.5).astype(int)

        train_score = accuracy_score(y_train > 0.5, model.predict(X_train))
        test_score = accuracy_score(y_test_binary, y_pred)

        # 🔍 Дополнительные метрики
        f1 = f1_score(y_test_binary, y_pred, zero_division=0)
        precision = precision_score(y_test_binary, y_pred, zero_division=0)
        recall = recall_score(y_test_binary, y_pred, zero_division=0)

        logging.info(f"📊 ML метрики: Train={train_score:.3f} | Test={test_score:.3f}")
        logging.info(f"🎯 F1={f1:.3f} | Precision={precision:.3f} | Recall={recall:.3f}")

        # 💾 AutoSave Quality Gate - сохраняем только если улучшилась точность
        current_best = train_ml_model_enhanced.best_test_score
        improvement = test_score - current_best
        
        if test_score > current_best or current_best == 0:
            # Сохраняем модель только если точность улучшилась
            ml_model = model
            ml_scaler = scaler
            
            joblib.dump(ml_model, "ml_model.pkl")
            joblib.dump(ml_scaler, "ml_scaler.pkl")
            
            # Сохраняем информацию о выбранных фичах
            with open("ml_features_selected.pkl", "wb") as f:
                pickle.dump(selected_features, f)
            
            train_ml_model_enhanced.best_test_score = test_score
            logging.info(f"💾 Модель сохранена (новый лучший результат: {test_score:.3f}, улучшение: {improvement:.3f})")
            model_saved = True
        else:
            logging.warning(f"🚫 Модель НЕ сохранена (текущий {test_score:.3f} <= лучший {current_best:.3f})")
            model_saved = False

        # 📊 Сохраняем статистику
        if not isinstance(model_info, dict):
            model_info = {}

        model_info.update({
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "n_features_original": len(feature_names),
            "n_features_selected": len(selected_features),
            "trades_used": len(X),
            "train_accuracy": round(train_score * 100, 2),
            "test_accuracy": round(test_score * 100, 2),
            "f1_score": round(f1 * 100, 2),
            "precision": round(precision * 100, 2),
            "recall": round(recall * 100, 2),
            "selected_features": selected_features,
            "win_rate": round(float(np.mean(y > 0.5)) * 100, 2),
            "model_type": "Stacking" if len(X) > 100 else "RandomForest",
            "model_saved": model_saved,
            "improvement": round(improvement * 100, 2) if improvement > 0 else 0
        })

        # 💾 Сохраняем историю
        try:
            old_data = []
            if os.path.exists("ml_info.json"):
                with open("ml_info.json", "r", encoding="utf-8") as f:
                    try:
                        old_data = json.load(f)
                        if isinstance(old_data, dict):
                            old_data = [old_data]
                    except json.JSONDecodeError:
                        old_data = []

            old_data.append(model_info)
            with open("ml_info.json", "w", encoding="utf-8") as f:
                json.dump(old_data, f, ensure_ascii=False, indent=2)

            logging.info(f"💾 ML история обновлена: всего записей {len(old_data)}")
            logging.info(f"✅ ML модель успешно обучена на {len(selected_features)} признаках")

        except Exception as e:
            logging.error(f"❌ Ошибка сохранения истории ML: {e}", exc_info=True)

        return model_info

    except Exception as e:
        logging.error(f"❌ Ошибка обучения ML: {e}", exc_info=True)
        if not isinstance(model_info, dict):
            model_info = {}
        model_info["error"] = str(e)
        return model_info

def load_ml_model():
    """Загружает ML модель и scaler при запуске"""
    global ml_model, ml_scaler
    try:
        if os.path.exists("ml_model.pkl") and os.path.exists("ml_scaler.pkl"):
            ml_model = joblib.load("ml_model.pkl")
            ml_scaler = joblib.load("ml_scaler.pkl")
            logging.info("✅ ML модель и scaler загружены")
            return True
        else:
            logging.warning("⚠ ML модель или scaler не найдены")
            return False
    except Exception as e:
        logging.error(f"❌ Ошибка загрузки ML модели: {e}")
        return False

def repair_ml_features():
    """Помечает сделки для пересчета ml_features, но НЕ создает случайные данные"""
    try:
        needs_repair_count = 0
        
        # 🔧 ЗАМЕНИТЕ НА ВАШИ ПЕРЕМЕННЫЕ
        MULTI_USER_MODE = False
        users = {}
        single_user_data = {'trade_history': []}
        
        if MULTI_USER_MODE:
            for user_id, user_data in users.items():
                for trade in user_data.get('trade_history', []):
                    if not trade.get('ml_features') and trade.get('pair'):
                        # 🔧 ТОЛЬКО помечаем, что нужны реальные данные
                        trade['needs_ml_recalculation'] = True
                        needs_repair_count += 1
        else:
            for trade in single_user_data.get('trade_history', []):
                if not trade.get('ml_features') and trade.get('pair'):
                    trade['needs_ml_recalculation'] = True
                    needs_repair_count += 1
        
        if needs_repair_count > 0:
            # save_users_data()  # Раскомментируйте если у вас есть эта функция
            logging.info(f"🔧 Помечено {needs_repair_count} сделок для пересчета ml_features")
        
        return needs_repair_count
        
    except Exception as e:
        logging.error(f"❌ Ошибка восстановления ml_features: {e}")
        return 0
    
# 🔧 Инициализация при импорте
def init_ml_module():
    """Инициализация ML модуля при запуске"""
    load_ml_model()
    logging.info("🤖 ML модуль инициализирован")

# Автоматическая инициализация при импорте
init_ml_module()

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

def analyze_pair(pair: str):
    try:
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
                # Масштабируем признаки и получаем вероятность WIN
                feats_scaled = ml_scaler.transform(feats_array)
                ml_pred = ml_model.predict_proba(feats_scaled)[0][1]
                ml_confidence = round(ml_pred * 100, 1)
                ml_signal = "BUY" if ml_pred >= 0.5 else "SELL"

                ml_result = {
                    "signal": ml_signal,
                    "confidence": ml_pred,
                    "validated": True  # позже проверяется трендом
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

        # 📌 1. SMC если сильный, а ML не против → берём
        if smc_result['signal'] and smc_result['confidence'] >= 7:
            if not ml_result or ml_result['signal'] == smc_result['signal']:
                final_signal = smc_result['signal']
                final_confidence = smc_result['confidence']
                final_expiry = smc_result['expiry']
                final_source = "ENHANCED_SMART_MONEY"

        # 📌 2. ML если валидирован и не конфликтует с RSI и трендом
        elif ml_result and ml_result['signal'] and ml_result['validated'] and ml_result['confidence'] >= 0.25:
            rsi_val = ml_features_dict.get('rsi', 50)
            if (ml_result['signal'] == 'BUY' and rsi_val < 70 and m15_trend == 'BULLISH') or \
               (ml_result['signal'] == 'SELL' and rsi_val > 30 and m15_trend == 'BEARISH'):
                final_signal = ml_result['signal']
                final_confidence = int(ml_result['confidence'] * 20)
                final_expiry = 2
                final_source = "ML_VALIDATED"

        # 📌 3. GPT если ничего другого нет
        elif gpt_result:
            final_signal = gpt_result['signal']
            final_confidence = gpt_result['confidence']
            final_expiry = gpt_result['expiry']
            final_source = gpt_result['source']

        # 6️⃣ Возврат
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

# ===================== AUTO TRADING LOOP - ФИНАЛ =====================
async def auto_trading_loop(context: ContextTypes.DEFAULT_TYPE):
    """Финальная версия торгового цикла с ПАРАЛЛЕЛЬНОЙ проверкой фиксированного рабочего времени бота"""
    start_time = datetime.now()  # ⏱️ ОБЯЗАТЕЛЬНО ДОБАВИТЬ ЭТУ СТРОКУ В НАЧАЛО ФУНКЦИИ
    
    try:
        logging.info("🔄 ===== ЗАПУСК АВТО-ТРЕЙДИНГ ЦИКЛА =====")

        # 🕒 Проверяем фиксированный график работы бота
        if not is_trading_time():
            logging.info("⏸ Вне рабочего времени бота — цикл пропущен")
            return

        # 📥 Загружаем / обновляем данные пользователей
        logging.info(f"👥 Загружено пользователей: {len(users)}")

        if not users or len(users) == 0:
            logging.warning("⚠ База пользователей пуста")
            return

        # 🚀 ПАРАЛЛЕЛЬНАЯ обработка всех пользователей
        tasks = []
        user_tasks = []

        for user_id, user_data in users.copy().items():
            try:
                uid = int(user_id)
                auto_trading = user_data.get('auto_trading', False)
                
                if not auto_trading:
                    logging.info(f"⏸ Пользователь {uid}: авто-трейдинг отключён")
                    continue
                    
                logging.info(f"🚀 Пользователь {uid}: добавляем в параллельную обработку...")
                # Создаем задачу для каждого пользователя
                task = asyncio.create_task(
                    process_auto_trade_for_user(uid, user_data, context),
                    name=f"user_{uid}"
                )
                tasks.append(task)
                user_tasks.append(uid)

            except Exception as user_err:
                logging.error(f"❌ Ошибка подготовки пользователя {user_id}: {user_err}", exc_info=True)

        # 🔥 ЗАПУСК ВСЕХ ЗАДАЧ ПАРАЛЛЕЛЬНО
        processed_users = 0
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logging.error(f"❌ Ошибка у пользователя {user_tasks[i]}: {result}")
                else:
                    processed_users += 1

        logging.info(f"✅ АВТО-ТРЕЙДИНГ ЦИКЛ ЗАВЕРШЕН. Обработано пользователей: {processed_users}/{len(users)}")

    except Exception as e:
        logging.error(f"💥 Критическая ошибка авто-трейдинга: {e}", exc_info=True)
    
    finally:
        execution_time = (datetime.now() - start_time).total_seconds()
        logging.info(f"⏱️ Авто-трейдинг выполнен за {execution_time:.1f} сек")

# ===================== TRADE RESULT CHECKER =====================
async def check_trade_result(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет результат сделки и закрывает её с обновлением истории и статистики"""
    try:
        job_data = context.job.data
        user_id = job_data['user_id']
        pair = job_data['pair']
        trade_id = job_data['trade_id']

        logging.info(f"🔍 Проверка сделки #{trade_id} для пользователя {user_id}, пара: {pair}")

        user_data = get_user_data(user_id)
        if not user_data:
            logging.error(f"❌ Пользователь {user_id} не найден")
            return

        current_trade = user_data.get('current_trade')
        if not current_trade:
            logging.warning(f"⚠️ У пользователя {user_id} нет активной сделки")
            return

        if current_trade.get('id') != trade_id:
            logging.warning(f"⚠️ ID сделки не совпадает: ожидали {trade_id}, получили {current_trade.get('id')}")
            return

        # Получаем текущую цену
        df = get_mt5_data(pair, 2, mt5.TIMEFRAME_M1)
        if df is None or len(df) < 1:
            logging.error(f"❌ Не удалось получить данные для {pair}")
            return

        current_price = df['close'].iloc[-1]
        entry_price = current_trade['entry_price']
        direction = current_trade['direction']

        # Определяем результат сделки
        if direction == 'BUY':
            result = 'WIN' if current_price > entry_price else 'LOSS'
        else:  # SELL
            result = 'WIN' if current_price < entry_price else 'LOSS'

        # Сумма ставки
        stake = current_trade.get('stake', STAKE_AMOUNT)
        profit = WIN_PROFIT if result == 'WIN' else -stake

        # ✅ Формируем финальную запись сделки
        closed_trade = {
            'id': trade_id,
            'pair': pair,
            'direction': direction,
            'entry_price': entry_price,
            'exit_price': current_price,
            'stake': stake,
            'stake_used': stake,
            'timestamp': current_trade.get('timestamp', datetime.now().isoformat()),
            'completed_at': datetime.now().isoformat(),
            'result': result,
            'profit': profit,
            'confidence': current_trade.get('confidence', 0),
            'source': current_trade.get('source', 'UNKNOWN'),
            'expiry_minutes': current_trade.get('expiry_minutes', 1),
            'ml_features': current_trade.get('ml_features', None)
        }

        # ✅ Добавляем сделку в историю пользователя
        if 'trade_history' not in user_data:
            user_data['trade_history'] = []

        user_data['trade_history'].append(closed_trade)
        user_data['trade_counter'] = len(user_data['trade_history'])

        # ✅ Очищаем текущую активную сделку
        user_data['current_trade'] = None

        # ✅ Сохраняем обновлённые данные пользователя
        save_users_data()

        # ✅ Логируем сделку в файл истории (если функция есть)
        try:
            log_trade_to_file(closed_trade, result)
        except Exception as e:
            logging.error(f"⚠️ Ошибка логирования сделки в файл: {e}")

        # 📝 Подсчёт текущей статистики для отображения в сообщении
        total = len(user_data['trade_history'])
        wins = sum(1 for t in user_data['trade_history'] if t.get('result') == 'WIN')
        losses = sum(1 for t in user_data['trade_history'] if t.get('result') == 'LOSS')
        win_rate = round(wins / total * 100, 1) if total > 0 else 0

        # 📢 Уведомление пользователя
        result_emoji = "🟢" if result == "WIN" else "🔴"
        result_text = (
            f"{result_emoji} СДЕЛКА #{trade_id} ЗАВЕРШЕНА\n\n"
            f"💼 Пара: {pair}\n"
            f"📊 Направление: {direction}\n"
            f"💰 Вход: {entry_price:.5f}\n"
            f"💰 Выход: {current_price:.5f}\n"
            f"🎯 Результат: {result}\n\n"
            f"📊 Общая статистика:\n"
            f"• Всего: {total}\n"
            f"• 🟢 Выигрыши: {wins}\n"
            f"• 🔴 Проигрыши: {losses}\n"
            f"• 🎯 Win Rate: {win_rate}%"
        )

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=result_text,
                reply_markup=get_trading_keyboard(user_id)
            )
            logging.info(f"✅ Сделка #{trade_id} закрыта: {result}")
        except Exception as e:
            logging.error(f"❌ Ошибка отправки уведомления: {e}")

    except Exception as e:
        logging.error(f"💥 Критическая ошибка в check_trade_result: {e}", exc_info=True)
# ===================== 🤖 PROCESS AUTO TRADE =====================
async def process_auto_trade_for_user(user_id: int, user_data: Dict, context: ContextTypes.DEFAULT_TYPE):
    """Авто-трейдинг: анализ, открытие сделки и отложенная запись после закрытия"""
    try:
        # ⏸ Проверка фиксированного рабочего времени бота
        if not is_trading_time():
            logging.info(f"⏸ Вне рабочего времени — пользователь {user_id}, цикл пропущен")
            return

        # ⏸ Проверка на уже открытую сделку
        if user_data.get('current_trade'):
            logging.info(f"⏸ Пользователь {user_id} уже имеет открытую сделку — пропуск")
            return

        logging.info(f"🚀 [AUTO] Старт автоанализа для user_id={user_id}")
        random.shuffle(PAIRS)

        for pair in PAIRS:
            start_time = datetime.now()
            result = analyze_pair(pair)
            if not result or len(result) < 4:
                continue

            signal, expiry, conf, source = result[:4]

            # 🎯 Фильтрация слабых сигналов
            if not signal or conf < 6:
                continue

            # 📊 Получаем данные с MT5
            df = get_mt5_data(pair, 300, mt5.TIMEFRAME_M1)
            if df is None or len(df) < 50:
                continue

            entry_price = df['close'].iloc[-1]
            trade_number = user_data['trade_counter'] + 1
            ml_features_dict = prepare_ml_features(df) or {}

            # 📝 Текст сигнала
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

            # 📈 Отправка графика ИЗ ПАМЯТИ (BytesIO)
            chart_stream = enhanced_plot_chart(df, pair, entry_price, signal)
            user_markup = get_trading_keyboard(user_id)
            try:
                if chart_stream:
                    # 🔥 ПРАВИЛЬНАЯ ОТПРАВКА BytesIO ИЗ ПАМЯТИ
                    await context.bot.send_photo(
                        chat_id=user_id, 
                        photo=chart_stream,  # Отправляем BytesIO напрямую
                        caption=signal_text, 
                        reply_markup=user_markup
                    )
                    # 🔥 НЕ НУЖНО УДАЛЯТЬ ФАЙЛ - его нет!
                    logging.info(f"✅ График отправлен из памяти пользователю {user_id}")
                else:
                    await context.bot.send_message(chat_id=user_id, text=signal_text, reply_markup=user_markup)
            except Exception as tg_err:
                logging.error(f"⚠ Ошибка отправки сигнала пользователю {user_id}: {tg_err}")

            # 📌 Сделка сохраняется ТОЛЬКО как текущая
            trade = {
                'id': trade_number,
                'pair': pair,
                'direction': signal,
                'entry_price': float(entry_price),
                'expiry_minutes': int(expiry),
                'stake': float(STAKE_AMOUNT),
                'timestamp': datetime.now().isoformat(),
                'ml_features': ml_features_dict,
                'source': source,
                'confidence': int(conf)
            }

            user_data['current_trade'] = trade
            user_data['trade_counter'] += 1
            save_users_data()
            logging.info(f"📌 Текущая сделка #{trade_number} сохранена (история — после закрытия)")

            # ⏱ Планируем проверку результата сделки
            check_delay = (expiry * 60) + 5
            context.job_queue.run_once(
                check_trade_result,
                check_delay,
                data={'user_id': user_id, 'pair': pair, 'trade_id': trade_number}
            )

            logging.info(f"🕒 План проверки сделки #{trade_number} через {check_delay} сек")
            elapsed = (datetime.now() - start_time).total_seconds()
            logging.info(f"✅ Сделка #{trade_number} ({pair} {signal}) открыта за {elapsed:.2f} сек")

            # 🛑 Одна сделка за цикл
            return

        logging.info(f"🏁 [AUTO] Анализ для user_id={user_id} завершён без открытия сделок")

    except Exception as e:
        logging.error(f"❌ Ошибка process_auto_trade_for_user: {e}", exc_info=True)
        
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
                        reply_markup=main_markup
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
                            reply_markup=get_trading_keyboard(user_id)
                        )
                        
            except Exception as e:
                logging.error(f"❌ Ошибка уведомления пользователя {user_id}: {e}")
        
        BOT_STATUS_NOTIFIED = True
        logging.info(f"🔔 Уведомления о статусе отправлены {notified_users} пользователям")
        
    except Exception as e:
        logging.error(f"❌ Ошибка отправки уведомлений о статусе: {e}")

# -------- START & STATUS --------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение и показ главного меню"""
    user = update.effective_user
    user_id = user.id

    user_data = get_user_data(user_id)
    user_data['first_name'] = user.first_name or ""
    user_data['username'] = user.username or ""

    # Получаем актуальную статистику
    history = user_data.get('trade_history', [])
    finished_trades = [t for t in history if t.get('result') in ("WIN", "LOSS")]
    total = len(finished_trades)
    wins = len([t for t in finished_trades if t.get('result') == "WIN"])
    winrate = round(wins / total * 100, 1) if total > 0 else 0

    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        f"🤖 Я — AI Trading Bot с технологией Smart Money Concepts.\n\n"
        f"📊 Мои возможности:\n"
        f"• Smart Money анализ (SMC)\n"
        f"• Машинное обучение (ML)\n"
        f"• GPT-анализ рынка\n"
        f"• Автоматическая торговля\n"
        f"• Подробные графики\n\n"
        f"📈 Сделок: {total}\n"
        f"🎯 Win Rate: {winrate}%\n\n"
        f"📋 Используй кнопки меню ниже 👇"
    )

    await update.message.reply_text(welcome_text, reply_markup=main_markup)
    save_users_data()
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

    await update.message.reply_text(status_text, reply_markup=main_markup)

# -------- НОВАЯ КОМАНДА РАСПИСАНИЯ --------
async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущий статус расписания работы бота"""
    now = datetime.now()
    current_time = now.time()
    current_weekday = now.weekday()
    weekday_name = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'][current_weekday]
    
    is_working_time = is_trading_time()
    status = "🟢 РАБОТАЕТ" if is_working_time else "🔴 ОТКЛЮЧЕН"
    
    # Расчет времени до следующего открытия
    if not is_working_time:
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
        until_text = f"⏰ До открытия: {hours}ч {minutes}мин"
    else:
        time_until_close = datetime.combine(now.date(), TRADING_END) - now
        hours = time_until_close.seconds // 3600
        minutes = (time_until_close.seconds % 3600) // 60
        until_text = f"⏰ До закрытия: {hours}ч {minutes}мин"
    
    schedule_text = (
        f"📅 РАСПИСАНИЕ РАБОТЫ БОТА\n\n"
        f"🕐 Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📅 День недели: {weekday_name}\n"
        f"📊 Статус: {status}\n"
        f"{until_text}\n\n"
        f"🕒 Рабочие часы:\n"
        f"• Ежедневно: {TRADING_START.strftime('%H:%M')} - {TRADING_END.strftime('%H:%M')}\n"
        f"• Выходные: Суббота, Воскресенье\n\n"
        f"🌐 Часовой пояс: Локальное время системы"
    )
    
    await update.message.reply_text(schedule_text)

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
            reply_markup=get_trading_keyboard(user_id)
        )
        return
    if user_data.get('current_trade'):
        await update.message.reply_text(
            "⏳ У вас уже есть активная сделка! Дождитесь её завершения.",
            reply_markup=get_trading_keyboard(user_id)
        )
        return

    await update.message.reply_text("🔍 Ищу лучшие торговые сигналы...", reply_markup=get_trading_keyboard(user_id))

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
                        await update.message.reply_photo(photo=photo, caption=signal_text, reply_markup=get_trading_keyboard(user_id))
                    try:
                        os.remove(chart_path)
                    except:
                        pass
                else:
                    await update.message.reply_text(signal_text, reply_markup=get_trading_keyboard(user_id))

                context.user_data['last_signal'] = {
                    'pair': pair,
                    'signal': signal,
                    'entry_price': entry_price,
                    'expiry': expiry,
                    'ml_features': ml_features_data,
                    'source': source
                }
                return

    await update.message.reply_text("⚠ Сигналы не найдены. Попробуйте позже.", reply_markup=get_trading_keyboard(user_id))


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
            reply_markup=get_models_keyboard(update.effective_user.id)
        )
    except Exception as e:
        logging.error(f"Ошибка model_stats_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ошибка получения статистики модели",
            reply_markup=get_models_keyboard(update.effective_user.id)
        )


async def retrain_model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переобучает ML модель (только админ)"""
    user_id = update.effective_user.id

    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text(
            "❌ Эта команда доступна только администратору",
            reply_markup=get_models_keyboard(user_id)
        )
        return

    await update.message.reply_text(
        "🔄 Запускаю переобучение ML модели... Это может занять несколько минут.",
        reply_markup=get_models_keyboard(user_id)
    )

    try:
        # Запускаем обучение и получаем результат
        result = train_ml_model()

        # 🔧 ИСПРАВЛЕНИЕ: проверяем результат обучения
        if result and not result.get("error"):
            test_acc = result.get("test_accuracy", 0)
            if test_acc > 1:
                test_acc = test_acc / 100
            trades_used = result.get("trades_used", 0)
            cv_accuracy = result.get("cv_accuracy", 0)
            
            await update.message.reply_text(
                f"✅ ML модель успешно переобучена!\n"
                f"📊 Точность (тест): {test_acc:.2f}%\n"
                f"🎯 Кросс-валидация: {cv_accuracy:.2f}%\n"
                f"📈 Сделок использовано: {trades_used}",
                reply_markup=get_models_keyboard(user_id)
            )
        else:
            # 🔧 ИСПРАВЛЕНИЕ: получаем ошибку из результата
            error_msg = result.get("error", "Неизвестная ошибка") if result else "Неизвестная ошибка"
            await update.message.reply_text(
                f"❌ Ошибка переобучения: {error_msg}",
                reply_markup=get_models_keyboard(user_id)
            )
            
    except Exception as e:
        logging.error(f"Ошибка retrain_model_command: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Произошла ошибка при переобучении модели: {str(e)}",
            reply_markup=get_models_keyboard(user_id)
        )
# -------- TOGGLE FUNCTIONS (ML / GPT / SMC) --------
async def toggle_ml(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['ml_enabled'] = not user_data.get('ml_enabled', ML_ENABLED)
    status = "🟢 ML: ВКЛ" if user_data['ml_enabled'] else "🔴 ML: ВЫКЛ"
    await update.message.reply_text(f"⚙️ ML режим переключен: {status}", reply_markup=get_models_keyboard(user_id))


async def toggle_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['gpt_enabled'] = not user_data.get('gpt_enabled', USE_GPT)
    status = "🟢 GPT: ВКЛ" if user_data['gpt_enabled'] else "🔴 GPT: ВЫКЛ"
    await update.message.reply_text(f"⚙️ GPT режим переключен: {status}", reply_markup=get_models_keyboard(user_id))


async def toggle_smc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    user_data['smc_enabled'] = not user_data.get('smc_enabled', True)
    status = "🟢 SMC: ВКЛ" if user_data['smc_enabled'] else "🔴 SMC: ВЫКЛ"
    await update.message.reply_text(f"⚙️ SMC анализ переключен: {status}", reply_markup=get_models_keyboard(user_id))


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
    
    await update.message.reply_text(settings_text, reply_markup=main_markup)

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
    """Показывает справку по командам"""
    help_text = (
        "📋 СПРАВКА ПО КОМАНДАМ\n\n"
        "Основные команды:\n"
        "• /start - Запуск бота\n"
        "• /status - Статус системы\n"
        "• /stats - Статистика торговли\n"
        "• /history - История сделок\n"
        "• /next - Следующий сигнал\n"
        "• /settings - Настройки\n\n"
        "Для ML модели:\n"
        "• /modelstats - Статистика ML\n"
        "• /retrain - Переобучить ML\n\n"
        "Управление:\n"
        "• /stake <сумма> - Изменить ставку\n"
        "• /resetbalance - Сбросить баланс\n"
        "• /stop - Остановить бота (админ)\n\n"
        "Используйте кнопки меню для удобства! 🎯"
    )
    
    await update.message.reply_text(help_text, reply_markup=main_markup)

async def toggle_auto_trading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключает авто-трейдинг для пользователя"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    user_data['auto_trading'] = not user_data.get('auto_trading', False)
    status = "🟢 ВКЛ" if user_data['auto_trading'] else "🔴 ВЫКЛ"
    
    await update.message.reply_text(
        f"🤖 Авто-трейдинг: {status}",
        reply_markup=get_trading_keyboard(user_id)
    )
    save_users_data()
    
async def clear_active_trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очищает активную сделку (для отладки)"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if user_data.get('current_trade'):
        trade_info = user_data['current_trade']
        user_data['current_trade'] = None
        save_users_data()
        
        await update.message.reply_text(
            f"🔄 Активная сделка очищена:\n"
            f"Пара: {trade_info.get('pair')}\n"
            f"Направление: {trade_info.get('direction')}\n"
            f"Цена: {trade_info.get('entry_price')}\n\n"
            f"Теперь можно получить новый сигнал.",
            reply_markup=get_trading_keyboard(user_id)
        )
    else:
        await update.message.reply_text(
            "✅ Активных сделок нет",
            reply_markup=get_trading_keyboard(user_id)
        )

async def restore_counter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстанавливает правильный счетчик сделок"""
    user_id = update.effective_user.id
    
    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return
        
    await update.message.reply_text("🔄 Восстановление счетчика сделок...")
    
    try:
        if MULTI_USER_MODE:
            for user_id, user_data in users.items():
                actual_trades = len(user_data.get('trade_history', []))
                current_counter = user_data.get('trade_counter', 0)
                
                if actual_trades > current_counter:
                    user_data['trade_counter'] = actual_trades
                    await update.message.reply_text(
                        f"✅ Восстановлен счетчик для пользователя {user_id}:\n"
                        f"Было: {current_counter}\n"
                        f"Стало: {actual_trades}"
                    )
                else:
                    await update.message.reply_text(
                        f"ℹ️ Счетчик для пользователя {user_id} корректен: {current_counter}"
                    )
        else:
            actual_trades = len(single_user_data.get('trade_history', []))
            current_counter = single_user_data.get('trade_counter', 0)
            
            if actual_trades > current_counter:
                single_user_data['trade_counter'] = actual_trades
                await update.message.reply_text(
                    f"✅ Восстановлен счетчик:\n"
                    f"Было: {current_counter}\n"
                    f"Стало: {actual_trades}"
                )
            else:
                await update.message.reply_text(
                    f"ℹ️ Счетчик корректен: {current_counter}"
                )
        
        save_users_data()
        
    except Exception as e:
        logging.error(f"Ошибка восстановления счетчика: {e}")
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

async def restore_from_backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстанавливает данные из последнего бэкапа"""
    user_id = update.effective_user.id

    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return

    await update.message.reply_text("🔄 Поиск резервных копий данных...")

    try:
        backup_files = []
        if os.path.exists("backups"):
            backup_files = [f for f in os.listdir("backups") if f.startswith("users_data_backup")]

        if not backup_files:
            await update.message.reply_text("❌ Резервные копии не найдены в папке backups/")
            return

        # Сортируем по дате (новейшие первыми)
        backup_files.sort(reverse=True)
        latest_backup = os.path.join("backups", backup_files[0])

        await update.message.reply_text(f"📂 Найдена резервная копия: {backup_files[0]}")

        # Загружаем из бэкапа
        with open(latest_backup, "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        # Восстанавливаем данные в память
        global users
        users.clear()

        for uid_str, user_data in backup_data.items():
            users[int(uid_str)] = user_data

        # Сохраняем как текущие данные
        save_users_data()

        # ✅ 📌 ВАЖНО: сразу обновляем память из восстановленного файла
        users.clear()
        load_users_data()
        logging.info("♻️ Память пользователей успешно обновлена после восстановления бэкапа")

        # Статистика
        total_trades = sum(len(user_data.get('trade_history', [])) for user_data in users.values())
        await update.message.reply_text(
            f"✅ Данные восстановлены из бэкапа!\n"
            f"📊 Пользователей: {len(users)}\n"
            f"📈 Сделок: {total_trades}\n"
            f"♻️ Память обновлена — перезапуск не требуется"
        )

    except Exception as e:
        logging.error(f"Ошибка восстановления из бэкапа: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка восстановления: {e}")


async def recalculate_real_ml_features_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересчитывает ML фичи на РЕАЛЬНЫХ данных для всех сделок"""
    user_id = update.effective_user.id
    
    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return
        
    await update.message.reply_text("🔄 Пересчет РЕАЛЬНЫХ ML фичей для всех сделок...")
    
    try:
        recalculated_count = 0
        failed_count = 0
        
        if MULTI_USER_MODE:
            for user_id, user_data in users.items():
                for trade in user_data.get('trade_history', []):
                    if trade.get('pair'):
                        pair = trade['pair']
                        # Получаем реальные данные для пересчета
                        df_m1 = get_mt5_data(pair, 400, mt5.TIMEFRAME_M1)
                        
                        if df_m1 is not None and len(df_m1) > 100:
                            feats = prepare_ml_features(df_m1)
                            if feats is not None:
                                feature_names = [
                                    'price', 'volume', 'rsi', 'atr', 'adx',
                                    'price_change_1h', 'volatility', 'macd', 'bb_position'
                                ]
                                trade['ml_features'] = dict(zip(feature_names, feats.flatten()))
                                recalculated_count += 1
                                logging.info(f"✅ Пересчитаны фичи для {pair}")
                            else:
                                failed_count += 1
                        else:
                            failed_count += 1
        
        if recalculated_count > 0:
            save_users_data()
            await update.message.reply_text(
                f"✅ Пересчитано РЕАЛЬНЫХ ML фичей: {recalculated_count} сделок\n"
                f"❌ Не удалось: {failed_count} сделок\n"
                f"🚀 Теперь пробуйте /forcetrain снова!"
            )
        else:
            await update.message.reply_text("❌ Не удалось пересчитать ни одной сделки")
            
    except Exception as e:
        logging.error(f"Ошибка пересчета ML фичей: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def reset_ml_features_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет случайные ML фичи и готовит для пересчета"""
    user_id = update.effective_user.id
    
    if MULTI_USER_MODE and not is_admin(user_id):
        await update.message.reply_text("❌ Эта команда доступна только администратору")
        return
        
    await update.message.reply_text("🔄 Сброс ML фичей для пересчета на реальных данных...")
    
    try:
        reset_count = 0
        
        if MULTI_USER_MODE:
            for user_id, user_data in users.items():
                for trade in user_data.get('trade_history', []):
                    # Удаляем старые случайные фичи
                    if trade.get('ml_features'):
                        trade['ml_features'] = None
                        trade['needs_ml_recalculation'] = True
                        reset_count += 1
        
        if reset_count > 0:
            save_users_data()
            await update.message.reply_text(
                f"✅ Сброшено ML фичей: {reset_count} сделок\n"
                f"📝 Теперь используйте /recalculateml для пересчета на реальных данных"
            )
        else:
            await update.message.reply_text("ℹ️ Нет ML фичей для сброса")
            
    except Exception as e:
        logging.error(f"Ошибка сброса ML фичей: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def force_enable_ml_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительно включает ML независимо от точности"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    user_data['ml_enabled'] = True
    save_users_data()
    
    await update.message.reply_text(
        "🟢 ML ПРИНУДИТЕЛЬНО ВКЛЮЧЕН!\n"
        "📊 Текущая точность: 50.0%\n"
        "⚠️ Модель будет использоваться даже с низкой точностью\n"
        "🔄 Модель улучшится со временем при накоплении данных"
    )

# ===================== CLEAR ALL TRADES (ADMIN) =====================
from telegram import Update
from telegram.ext import ContextTypes

ADMIN_IDS = [5129282647]  

async def clear_all_trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительно очищает все открытые сделки у всех пользователей (только для админа)"""
    user_id = update.effective_user.id

    # Проверка прав
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды.")
        return

    cleared_count = 0
    for uid, data in users.items():
        if "current_trade" in data:
            data.pop("current_trade", None)
            cleared_count += 1
            logging.info(f"🧹 Принудительно очищена сделка у пользователя {uid}")

    save_users_data()
    logging.info(f"✅ Админ {user_id} очистил {cleared_count} открытых сделок у всех пользователей")

    await update.message.reply_text(f"🧹 Принудительно очищено сделок: {cleared_count}")

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
    """Главный обработчик нажатий на кнопки меню"""
    text = update.message.text
    user_id = update.effective_user.id

    # ---------- 📌 ГЛАВНОЕ МЕНЮ ----------
    if text == "📊 Торговля":
        await trading_menu(update, context)

    elif text == "⚙️ Управление":
        await management_menu(update, context)

    elif text == "📈 Статистика":
        await statistics_command(update, context)

    elif text == "🧠 Модели":
        await models_menu(update, context)

    elif text == "📋 Помощь":
        await help_command(update, context)

    elif text == "📅 Расписание":  # ← ДОБАВЬТЕ ЭТОТ БЛОК
        await schedule_command(update, context)

    # ---------- ⬅️ ВОЗВРАТ В МЕНЮ ----------
    elif text in ["◀️ Главное меню", "◀️ Назад", "◀️ Назад в главное меню"]:
        await update.message.reply_text("🏠 Главное меню", reply_markup=main_markup)


    # ---------- 📊 МЕНЮ ТОРГОВЛИ ----------
    elif text == "🔄 Следующий сигнал":
        await next_signal_command(update, context)

    elif text == "📈 История":
        await history_command(update, context)

    elif "Авто-торговля" in text:
        await toggle_auto_trading(update, context)


    # ---------- 🧠 МЕНЮ МОДЕЛЕЙ ----------
    elif text == "📊 ML Статистика":
        await model_stats_command(update, context)

    elif text == "🔄 Обучить ML":
        await retrain_model_command(update, context)

    elif "ML:" in text:
        await toggle_ml(update, context)

    elif "GPT:" in text:
        await toggle_gpt(update, context)

    elif "SMC:" in text:
        await toggle_smc(update, context)


    # ---------- ❓ НЕИЗВЕСТНЫЙ ВВОД ----------
    else:
        await update.message.reply_text("❓ Используйте кнопки меню", reply_markup=main_markup)



# ===================== МЕНЮ ПОДРАЗДЕЛОВ =====================
async def trading_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📊 Меню торговли"""
    user_id = update.effective_user.id
    await update.message.reply_text(
        "📊 МЕНЮ ТОРГОВЛИ\n\nУправляйте сигналами и авто-торговлей 👇",
        reply_markup=get_trading_keyboard(user_id)
    )


async def models_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🧠 Меню моделей"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)

    ml_state = "включено" if user_data.get('ml_enabled', ML_ENABLED) else "отключено"
    gpt_state = "включено" if user_data.get('gpt_enabled', USE_GPT) else "отключено"
    smc_state = "включено" if user_data.get('smc_enabled', True) else "отключено"

    await update.message.reply_text(
        f"🧠 УПРАВЛЕНИЕ МОДЕЛЯМИ\n\n"
        f"🤖 ML: {ml_state}\n"
        f"💬 GPT: {gpt_state}\n"
        f"📊 SMC: {smc_state}\n\n"
        f"Включайте или отключайте нужные анализаторы 👇",
        reply_markup=get_models_keyboard(user_id)
    )

async def management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⚙️ Меню управления ботом"""
    await update.message.reply_text(
        "⚙️ УПРАВЛЕНИЕ СИСТЕМОЙ\n\nНастройки и контроль бота 👇",
        reply_markup=management_markup
    )

# ===================== MAIN =====================
def main():
    # Проверка прав доступа
    try:
        with open("bot_ai.log", "a", encoding="utf-8") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"🔄 Перезапуск бота: {datetime.now()}\n")
            f.write(f"{'='*50}\n")
        logging.info("✅ Права доступа к лог-файлу проверены")
    except Exception as e:
        print(f"❌ Ошибка доступа к лог-файлу: {e}")
        return
    
    # 🔧 6. ИНИЦИАЛИЗАЦИЯ СТАТУСА БОТА ПРИ ЗАПУСКЕ
    global BOT_LAST_STATUS, BOT_STATUS_NOTIFIED
    BOT_LAST_STATUS = is_trading_time()
    BOT_STATUS_NOTIFIED = False
    
    # Логируем начальный статус
    status_text = "🟢 РАБОТАЕТ" if BOT_LAST_STATUS else "🔴 ОСТАНОВЛЕН (вне рабочего времени)"
    logging.info(f"🤖 Статус бота при запуске: {status_text}")
    print(f"🤖 Статус бота при запуске: {status_text}")
    
    # Если бот запущен в нерабочее время - предупреждаем
    if not BOT_LAST_STATUS:
        now = datetime.now()
        logging.warning(f"⏸ Бот запущен в нерабочее время: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print("⚠ ВНИМАНИЕ: Бот запущен в нерабочее время и будет ожидать начала рабочего дня")
    
    # Подключение к MT5
    if not mt5.initialize(path=MT5_PATH, login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
        logging.error(f"❌ Ошибка инициализации MT5: {mt5.last_error()}")
        return
    logging.info("✅ MT5 подключен успешно")
    print("✅ MT5 подключен успешно")
    
    # Создание приложения Telegram
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Обработчики команд
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
    app.add_handler(CommandHandler("debug", debug_user_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # ===================== JOB QUEUE =====================
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(auto_trading_loop, interval=60, first=10)  # 60 секунд вместо 30
        job_queue.scheduler.add_listener(job_listener, 
                                   EVENT_JOB_MISSED | EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)
        logging.info("📅 JobQueue инициализирован — автоцикл каждые 60 сек с мониторингом")
        
    else:
        logging.error("❌ JobQueue не инициализирован — автоцикл не запущен")
        return

    # ===================== СТАРТ =====================
    IS_RUNNING = True   # ⚡ ВАЖНО: теперь цикл реально будет работать
    logging.info("🤖 Бот запущен и готов к работе!")
    app.run_polling()
    
    # ===================== ЗАВЕРШЕНИЕ =====================
    IS_RUNNING = False
    save_users_data()
    mt5.shutdown()
    logging.info("💾 Данные сохранены, MT5 отключен")
    print("💾 Данные сохранены, MT5 отключен")


if __name__ == "__main__":
    main()

