import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import CommandStart
from datetime import datetime
import os
from environs import Env
import gspread
from google.oauth2.service_account import Credentials
import platform
import sqlite3
import psycopg2
from psycopg2 import sql, IntegrityError
import re

# Загрузка переменных окружения
env = Env()
env.read_env()
API_TOKEN = env.str('BOT_TOKEN')

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())

# --- Google Sheets настройки ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = '1luwtoyzIsnCTmpbY5L-POpTSh5hNWlX8zGMr1GPIlFY'
SHEET_NAME = 'Кирим Чиким'
CREDENTIALS_FILE = 'credentials.json'

# Состояния
class Form(StatesGroup):
    type = State()      # Kirim/Ciqim
    amount = State()    # Сумма
    category = State()  # Категория
    comment = State()   # Комментарий
    object = State()    # Объект

# Кнопки выбора Kirim/Chiqim
start_kb = InlineKeyboardMarkup(row_width=2)
start_kb.add(
    InlineKeyboardButton('🟢 Kirim', callback_data='type_kirim'),
    InlineKeyboardButton('🔴 Chiqim', callback_data='type_chiqim')
)

# Категории
categories = [
    ("🟥 Doimiy Xarajat", "cat_doimiy"),
    ("🟩 Oʻzgaruvchan Xarajat", "cat_ozgaruvchan"),
    ("🟪 Qarz", "cat_qarz"),
    ("⚪ Avtoprom", "cat_avtoprom"),
    ("🟩 Divident", "cat_divident"),
    ("🟪 Soliq", "cat_soliq"),
    ("🟦 Ish Xaqi", "cat_ishhaqi")
]

# Словарь соответствий: категория -> эмодзи
category_emojis = {
    "Qurilish materiallari": "🟩",
    "Doimiy Xarajat": "🟥",
    "Qarz": "🟪",
    "Divident": "🟩",
    "Soliq": "🟪",
    "Ish Xaqi": "🟦",
    # Добавьте другие категории и эмодзи по мере необходимости
}

def get_category_with_emoji(category_name):
    emoji = category_emojis.get(category_name, "")
    return f"{emoji} {category_name}".strip()

def get_categories_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for name in get_categories():
        cb = f"cat_{name}"
        # Показываем эмодзи в меню
        btn_text = get_category_with_emoji(name)
        kb.add(InlineKeyboardButton(btn_text, callback_data=cb))
    return kb

# Кнопка пропуска для Izoh
skip_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Пропустить", callback_data="skip_comment"))

# Кнопки подтверждения
confirm_kb = InlineKeyboardMarkup(row_width=2)
confirm_kb.add(
    InlineKeyboardButton('✅ Ha', callback_data='confirm_yes'),
    InlineKeyboardButton('❌ Yo\'q', callback_data='confirm_no')
)

def clean_emoji(text):
    # Удаляет только эмодзи/спецсимволы в начале строки, остальной текст не трогает
    return re.sub(r'^[^\w\s]*', '', text).strip()

def add_to_google_sheet(data):
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        
        # Пробуем получить лист по названию
        try:
            worksheet = sh.worksheet(SHEET_NAME)
        except Exception as e:
            # Если не можем найти лист, пробуем получить первый лист
            logging.error(f"Не удалось найти лист '{SHEET_NAME}': {e}")
            worksheet = sh.get_worksheet(0)  # Получаем первый лист
            logging.info(f"Используем первый лист: {worksheet.title}")
        
        # Получаем текущее время
        from datetime import datetime
        now = datetime.now()
        
        # Формат даты DD.MM.YYYY
        date_str = now.strftime('%d.%m.%Y')
        
        # Определяем значения для столбцов Кирим и Чиқим
        kirim = data.get('amount', '') if data.get('type') == 'Kirim' else ''
        chiqim = data.get('amount', '') if data.get('type') == 'Ciqim' else ''
        
        # Формируем строку для записи в таблицу
        # A: Сана, B: Кирим, C: Чиқим, E: Котегория, F: Изох, G: Объект номи
        row = [
            date_str,                    # A: Сана (дата)
            kirim,                       # B: Кирим (доход)
            chiqim,                      # C: Чиқим (расход)
            '',                          # D: остатка (пустой)
            data.get('category', ''),    # E: Котегория
            data.get('comment', ''),     # F: Изох
            data.get('loyiha', '')       # G: Объект номи
        ]
        
        worksheet.append_row(row)
        logging.info(f"Данные успешно добавлены в Google Sheets: {row}")
        
    except Exception as e:
        logging.error(f"Ошибка при добавлении в Google Sheets: {e}")
        raise e

def format_summary(data):
    tur_emoji = '🟢' if data.get('type') == 'Kirim' else '🔴'
    dt = data.get('dt', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    # Показываем категорию с эмодзи
    category_with_emoji = get_category_with_emoji(data.get('category', '-'))
    return (
        f"<b>Natija:</b>\n"
        f"<b>Tur:</b> {tur_emoji} {data.get('type', '-')}\n"
        f"<b>Summa:</b> {data.get('amount', '-')}\n"
        f"<b>Kotegoriya:</b> {category_with_emoji}\n"
        f"<b>Izoh:</b> {data.get('comment', '-')}\n"
        f"<b>Объект номи:</b> {data.get('loyiha', '-')}\n"
        f"<b>Vaqt:</b> {dt}"
    )

# --- Админы ---
ADMINS = [5657091547, 5048593195]  # Здесь можно добавить id других админов через запятую

# --- Инициализация БД ---
def get_db_conn():
    return psycopg2.connect(
        dbname=env.str('POSTGRES_DB', 'kapital'),
        user=env.str('POSTGRES_USER', 'postgres'),
        password=env.str('POSTGRES_PASSWORD', 'postgres'),
        host=env.str('POSTGRES_HOST', 'localhost'),
        port=env.str('POSTGRES_PORT', '5432')
    )

def init_db():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        user_id BIGINT UNIQUE,
        name TEXT,
        phone TEXT,
        status TEXT,
        reg_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE
    )''')
    # Заполняем дефолтные значения, если таблицы пусты
    c.execute('SELECT COUNT(*) FROM categories')
    if c.fetchone()[0] == 0:
        for name in ["🟥 Doimiy Xarajat", "🟩 Oʻzgaruvchan Xarajat", "🟪 Qarz", "⚪ Avtoprom", "🟩 Divident", "🟪 Soliq", "🟦 Ish Xaqi"]:
            c.execute('INSERT INTO categories (name) VALUES (%s)', (name,))
    conn.commit()
    conn.close()

init_db()

# --- Проверка статуса пользователя ---
def get_user_status(user_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT status FROM users WHERE user_id=%s', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def register_user(user_id, name, phone):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('INSERT INTO users (user_id, name, phone, status, reg_date) VALUES (%s, %s, %s, %s, %s)',
              (user_id, name, phone, 'pending', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

def update_user_status(user_id, status):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('UPDATE users SET status=%s WHERE user_id=%s', (status, user_id))
    conn.commit()
    conn.close()

def get_user_name(user_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT name FROM users WHERE user_id=%s', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# --- Получение актуальных списков ---
def get_categories():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT name FROM categories')
    result = [row[0] for row in c.fetchall()]
    conn.close()
    return result

# --- Основные команды ---
@dp.message_handler(commands=['start'])
async def start(msg: types.Message, state: FSMContext):
    await state.finish()
    text = "<b>Qaysi turdagi operatsiya?</b>"
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton('🟢 Kirim', callback_data='type_kirim'),
        InlineKeyboardButton('🔴 Chiqim', callback_data='type_chiqim')
    )
    await msg.answer(text, reply_markup=kb)
    await Form.type.set()

# Kirim/Ciqim выбор
@dp.callback_query_handler(lambda c: c.data.startswith('type_'), state=Form.type)
async def process_type(call: types.CallbackQuery, state: FSMContext):
    t = 'Kirim' if call.data == 'type_kirim' else 'Ciqim'
    await state.update_data(type=t)
    await call.message.edit_text("<b>Summani kiriting:</b>")
    await Form.amount.set()
    await call.answer()

# Сумма
@dp.message_handler(lambda m: m.text.replace('.', '', 1).isdigit(), state=Form.amount)
async def process_amount(msg: types.Message, state: FSMContext):
    await state.update_data(amount=msg.text)
    await msg.answer("<b>Kotegoriyani tanlang:</b>", reply_markup=get_categories_kb())
    await Form.category.set()

# Категория
@dp.callback_query_handler(lambda c: c.data.startswith('cat_'), state=Form.category)
async def process_category(call: types.CallbackQuery, state: FSMContext):
    cat = call.data[4:]
    await state.update_data(category=cat)
    await call.message.edit_text("<b>Izoh kiriting (yoki пропустите):</b>", reply_markup=skip_kb)
    await Form.comment.set()
    await call.answer()

# Кнопка пропуска комментария
@dp.callback_query_handler(lambda c: c.data == 'skip_comment', state=Form.comment)
async def skip_comment_btn(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(comment='-')
    await call.message.edit_text("<b>Объект номини киритинг:</b>")
    await Form.object.set()
    await call.answer()

# Комментарий (или пропуск)
@dp.message_handler(state=Form.comment, content_types=types.ContentTypes.TEXT)
async def process_comment(msg: types.Message, state: FSMContext):
    await state.update_data(comment=msg.text)
    await msg.answer("<b>Объект номини киритинг:</b>")
    await Form.object.set()

# Объект
@dp.message_handler(state=Form.object, content_types=types.ContentTypes.TEXT)
async def process_object(msg: types.Message, state: FSMContext):
    await state.update_data(loyiha=msg.text)
    data = await state.get_data()
    
    # Показываем итоговую информацию для подтверждения
    text = format_summary(data)
    await msg.answer(text, reply_markup=confirm_kb)
    await state.set_state('confirm')

# Обработка кнопок Да/Нет
@dp.callback_query_handler(lambda c: c.data in ['confirm_yes', 'confirm_no'], state='confirm')
async def process_confirm(call: types.CallbackQuery, state: FSMContext):
    if call.data == 'confirm_yes':
        data = await state.get_data()
        from datetime import datetime
        dt = datetime.now()
        import platform
        if platform.system() == 'Windows':
            date_str = dt.strftime('%m/%d/%Y')
        else:
            date_str = dt.strftime('%-m/%-d/%Y')
        time_str = dt.strftime('%H:%M')
        data['dt_for_sheet'] = date_str
        data['vaqt'] = time_str
        # Гарантируем, что user_id всегда есть
        data['user_id'] = call.from_user.id
        try:
            add_to_google_sheet(data)
            await call.message.answer('✅ Данные успешно отправлены в Google Sheets!')

            # Уведомление для админов
            user_name = get_user_name(call.from_user.id) or call.from_user.full_name
            summary_text = format_summary(data)
            admin_notification_text = f"Foydalanuvchi <b>{user_name}</b> tomonidan kiritilgan yangi ma'lumot:\n\n{summary_text}"
            
            for admin_id in ADMINS:
                try:
                    await bot.send_message(admin_id, admin_notification_text)
                except Exception as e:
                    logging.error(f"Could not send notification to admin {admin_id}: {e}")

        except Exception as e:
            await call.message.answer(f'⚠️ Ошибка при отправке в Google Sheets: {e}')
        await state.finish()
    else:
        await call.message.answer('❌ Операция отменена.')
        await state.finish()
    # Возврат к стартовому шагу
    text = "<b>Qaysi turdagi operatsiya?</b>"
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton('🟢 Kirim', callback_data='type_kirim'),
        InlineKeyboardButton('🔴 Chiqim', callback_data='type_chiqim')
    )
    await call.message.answer(text, reply_markup=kb)
    await Form.type.set()
    await call.answer()

# --- Команды для админа ---
@dp.message_handler(commands=['test_sheets'], state='*')
async def test_sheets_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    
    await state.finish()
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        
        # Получаем список всех листов
        worksheets = sh.worksheets()
        sheet_names = [ws.title for ws in worksheets]
        
        await msg.answer(f'✅ Google Sheets подключен успешно!\n\n'
                        f'📊 Доступные листы:\n' + 
                        '\n'.join([f'• {name}' for name in sheet_names]) +
                        f'\n\n🎯 Используемый лист: {SHEET_NAME}')
        
    except Exception as e:
        await msg.answer(f'❌ Ошибка подключения к Google Sheets:\n{str(e)}')

@dp.message_handler(commands=['add_category'], state='*')
async def add_category_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    await msg.answer('Yangi kategoriya nomini yuboring:')
    await state.set_state('add_category')

@dp.message_handler(state='add_category', content_types=types.ContentTypes.TEXT)
async def add_category_save(msg: types.Message, state: FSMContext):
    # Удаляем эмодзи из названия категории
    name = clean_emoji(msg.text.strip())
    conn = get_db_conn()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO categories (name) VALUES (%s)', (name,))
        conn.commit()
        await msg.answer(f'✅ Yangi kategoriya qo\'shildi: {name}')
    except IntegrityError:
        await msg.answer('❗️ Bu nom allaqachon mavjud.')
        conn.rollback()
    conn.close()
    await state.finish()

# --- Удаление и изменение Kotegoriyalar ---
@dp.message_handler(commands=['del_category'], state='*')
async def del_category_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    kb = InlineKeyboardMarkup(row_width=1)
    for name in get_categories():
        kb.add(InlineKeyboardButton(f'❌ {name}', callback_data=f'del_category_{name}'))
    await msg.answer('O\'chirish uchun kategoriyani tanlang:', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('del_category_'))
async def del_category_cb(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    name = call.data[len('del_category_'):]
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('DELETE FROM categories WHERE name=%s', (name,))
    conn.commit()
    conn.close()
    await call.message.edit_text(f'❌ Kategoriya o\'chirildi: {name}')
    await call.answer()

@dp.message_handler(commands=['edit_category'], state='*')
async def edit_category_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    kb = InlineKeyboardMarkup(row_width=1)
    for name in get_categories():
        kb.add(InlineKeyboardButton(f'✏️ {name}', callback_data=f'edit_category_{name}'))
    await msg.answer('Tahrirlash uchun kategoriyani tanlang:', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('edit_category_'))
async def edit_category_cb(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    old_name = call.data[len('edit_category_'):]
    await state.update_data(edit_category_old=old_name)
    await call.message.answer(f'Yangi nomini yuboring (eski: {old_name}):')
    await state.set_state('edit_category_new')
    await call.answer()

@dp.message_handler(state='edit_category_new', content_types=types.ContentTypes.TEXT)
async def edit_category_save(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    old_name = data.get('edit_category_old')
    new_name = clean_emoji(msg.text.strip())
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('UPDATE categories SET name=%s WHERE name=%s', (new_name, old_name))
    conn.commit()
    conn.close()
    await msg.answer(f'✏️ Kategoriya o\'zgartirildi: {old_name} → {new_name}')
    await state.finish()

# --- Управление пользователями ---
@dp.message_handler(commands=['userslist'], state='*')
async def users_list_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT user_id, name, phone, status, reg_date FROM users ORDER BY reg_date DESC')
    users = c.fetchall()
    conn.close()
    
    if not users:
        await msg.answer('Foydalanuvchilar mavjud emas.')
        return
    
    text = '<b>Foydalanuvchilar ro\'yxati:</b>\n\n'
    for user in users:
        user_id, name, phone, status, reg_date = user
        status_emoji = '✅' if status == 'approved' else '⏳' if status == 'pending' else '❌'
        text += f'{status_emoji} <b>{name}</b> (ID: {user_id})\n'
        text += f'📱 {phone}\n'
        text += f'📅 {reg_date}\n\n'
    
    await msg.answer(text)

@dp.message_handler(commands=['block_user'], state='*')
async def block_user_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT user_id, name, status FROM users WHERE status != \'blocked\' ORDER BY reg_date DESC')
    users = c.fetchall()
    conn.close()
    
    if not users:
        await msg.answer('Bloklash uchun foydalanuvchilar mavjud emas.')
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    for user_id, name, status in users:
        status_text = '✅ Tasdiqlangan' if status == 'approved' else '⏳ Kutilmoqda'
        kb.add(InlineKeyboardButton(f'{status_text} - {name}', callback_data=f'blockuser_{user_id}'))
    
    await msg.answer('Bloklash uchun foydalanuvchini tanlang:', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('blockuser_'))
async def block_user_cb(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    user_id = int(call.data[len('blockuser_'):])
    update_user_status(user_id, 'blocked')
    await call.message.edit_text(f'❌ Foydalanuvchi bloklandi (ID: {user_id})')
    await call.answer()

@dp.message_handler(commands=['approve_user'], state='*')
async def approve_user_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT user_id, name, status FROM users WHERE status = \'pending\' ORDER BY reg_date DESC')
    users = c.fetchall()
    conn.close()
    
    if not users:
        await msg.answer('Tasdiqlash uchun foydalanuvchilar mavjud emas.')
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    for user_id, name, status in users:
        kb.add(InlineKeyboardButton(f'⏳ {name}', callback_data=f'approveuser_{user_id}'))
    
    await msg.answer('Tasdiqlash uchun foydalanuvchini tanlang:', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('approveuser_'))
async def approve_user_cb(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    user_id = int(call.data[len('approveuser_'):])
    update_user_status(user_id, 'approved')
    await call.message.edit_text(f'✅ Foydalanuvchi tasdiqlandi (ID: {user_id})')
    await call.answer()

# --- Регистрация новых пользователей ---
class Register(StatesGroup):
    name = State()
    phone = State()

@dp.message_handler(commands=['register'], state='*')
async def register_cmd(msg: types.Message, state: FSMContext):
    await state.finish()
    await msg.answer('Ismingizni kiriting:')
    await Register.name.set()

@dp.message_handler(state=Register.name, content_types=types.ContentTypes.TEXT)
async def process_register_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await msg.answer('Telefon raqamingizni yuboring:', reply_markup=types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton('📱 Telefon raqamini yuborish', request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    ))
    await Register.phone.set()

@dp.message_handler(state=Register.phone, content_types=types.ContentTypes.CONTACT)
async def process_register_phone(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data.get('name')
    phone = msg.contact.phone_number
    
    register_user(msg.from_user.id, name, phone)
    await msg.answer('✅ Ro\'yxatdan o\'tish muvaffaqiyatli! Admin tasdiqlashini kuting.', 
                    reply_markup=types.ReplyKeyboardRemove())
    await state.finish()

# --- Обработка одобрения/отклонения пользователей ---
@dp.callback_query_handler(lambda c: c.data.startswith('approve_') or c.data.startswith('deny_'), state='*')
async def process_admin_approve(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    
    user_id = int(call.data.split('_')[1])
    action = call.data.split('_')[0]
    
    if action == 'approve':
        update_user_status(user_id, 'approved')
        await call.message.edit_text(f'✅ Foydalanuvchi tasdiqlandi (ID: {user_id})')
        # Уведомляем пользователя
        try:
            await bot.send_message(user_id, '🎉 Sizning ro\'yxatdan o\'tishingiz tasdiqlandi! Endi botdan foydalanishingiz mumkin.')
        except Exception as e:
            logging.error(f"Could not notify user {user_id}: {e}")
    else:
        update_user_status(user_id, 'denied')
        await call.message.edit_text(f'❌ Foydalanuvchi rad etildi (ID: {user_id})')
    
    await call.answer()

# --- Блокировка неодобренных пользователей ---
@dp.message_handler(lambda msg: get_user_status(msg.from_user.id) != 'approved', state='*')
async def block_unapproved(msg: types.Message, state: FSMContext):
    if msg.text == '/register':
        return  # Пропускаем команду регистрации
    await msg.answer('❌ Sizning ro\'yxatdan o\'tishingiz hali tasdiqlanmagan. Iltimos, kuting yoki /register buyrug\'ini ishlatib qaytadan ro\'yxatdan o\'ting.')

# --- Настройка команд бота ---
async def set_user_commands(dp):
    await dp.bot.set_my_commands([
        types.BotCommand("start", "Boshlash"),
        types.BotCommand("register", "Ro'yxatdan o'tish")
    ])

# --- Уведомления для всех пользователей ---
async def notify_all_users(bot):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT user_id FROM users WHERE status = \'approved\'')
    users = c.fetchall()
    conn.close()
    
    for user in users:
        try:
            await bot.send_message(user[0], '🔔 Yangi xabar!')
        except Exception as e:
            logging.error(f"Could not send notification to user {user[0]}: {e}")

# --- Запуск бота ---
if __name__ == '__main__':
    async def on_startup(dp):
        await set_user_commands(dp)
        logging.info('Bot started!')
    
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
