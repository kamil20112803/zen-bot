import asyncio
import os
import logging
import threading
import random
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ============================================================
#                     НАСТРОЙКИ
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_СВОЙ_ТОКЕН")
DATABASE_URL = os.getenv("DATABASE_URL", "ВСТАВЬ_ССЫЛКУ_НА_БАЗУ")
OWNER_USERNAME = "rt6y9n"

logging.basicConfig(level=logging.INFO)
db_pool = None

# ============================================================
#                     СТАТИЧНЫЕ ДАННЫЕ
# ============================================================
SERVERS = {
    "survival": {"title": "⚔️ 1. ПолитWorld | ВЫЖИВАНИЕ", "text": "👑 Оригинальный политический сервер MultiCraft.\n\n🏛️ Создавай государства, заключай союзы, веди войны и развивай экономику!\n\n🔗 Инвайт: <code>PFJQTM0C</code>"},
    "creative": {"title": "🏗️ 2. ПолитWorld | КРЕАТИВ", "text": "🏙️ Строй столицы, создавай города, возводи инфраструктуру и воплощай свои идеи в жизнь!\n\n🔗 Инвайт: <code>LI9QFVL4</code>"},
    "medieval": {"title": "🏰 3. ПолитWorld | СРЕДНЕВЕКОВЬЕ", "text": "🛡️ Эпоха королевств, замков и великих сражений. Создавай собственные владения, заключай союзы и пиши историю своего государства!\n\n🔗 Инвайт: <code>NOIMVNSB</code>"},
}

MAIN_SERVER_TEXT = (
    "🌍 <b>ПОЛИТWORLD — ГЛАВНЫЙ СЕРВЕР</b>\n\n"
    "ПолитWorld — оригинальный политический сервер MultiCraft, ставший основой нашего сообщества. Здесь игроки создают собственные государства, развивают экономику, строят города и столицы, заключают дипломатические соглашения и участвуют в международных конфликтах.\n\n"
    "На сервере каждый игрок может пройти собственный путь: от основания небольшого государства до создания влиятельной державы. Союзы, соперничество, переговоры и борьба за территории формируют уникальную историю игрового мира.\n\n"
    "ПолитWorld — это не просто строительство и выживание, а целая политическая система, в которой решения игроков влияют на развитие государств и отношения между ними.\n\n"
    "🔗 <b>ИНВАЙТ:</b> <code>PFJQTM0C</code>\n\n"
    "⚔️ Создай своё государство. Напиши собственную историю. Стань частью ПолитWorld!"
)

SOCIALS = {
    "youtube": {"title": "▶️ YouTube — Zen Community", "text": "▶️ <b>Наш YouTube-канал</b>\n\nЗдесь выходят обзоры серверов, хроники войн, интервью с правителями и репортажи о ключевых событиях мира ПолитWorld.\n\n🔗 <a href=\"https://youtube.com/@ЗАМЕНИ_ССЫЛКУ\">Перейти на канал</a>"},
    "tiktok": {"title": "🎵 TikTok — Zen Community", "text": "🎵 <b>Наш TikTok</b>\n\nКороткие ролики: яркие моменты, конфликты, союзы и жизнь сообщества в формате, который удобно смотреть на ходу.\n\n🔗 <a href=\"https://tiktok.com/@ЗАМЕНИ_ССЫЛКУ\">Перейти в профиль</a>"},
}

RIGHT_KEYS = ["can_edit_users", "can_view_stats", "can_publish_news", "can_read_mail", "can_reply_mail", "can_manage_admins", "can_send_codes"]
RIGHT_LABELS = {
    "can_edit_users": "менять ник/страну", "can_view_stats": "смотреть статистику",
    "can_publish_news": "публиковать новости", "can_read_mail": "читать почту",
    "can_reply_mail": "отвечать на почту", "can_manage_admins": "управлять админами",
    "can_send_codes": "отправлять коды",
}
RIGHT_SHORTCUTS = {
    "edit": "can_edit_users", "stats": "can_view_stats", "news": "can_publish_news",
    "read": "can_read_mail", "reply": "can_reply_mail", "admins": "can_manage_admins", "codes": "can_send_codes",
}

# ============================================================
#                     БАЗА ДАННЫХ (POSTGRES)
# ============================================================
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY, username TEXT, game_nick TEXT,
                game_country TEXT, game_position TEXT, verified INTEGER DEFAULT 0, verify_code TEXT
            );
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY, can_edit_users INTEGER DEFAULT 0, can_view_stats INTEGER DEFAULT 0,
                can_publish_news INTEGER DEFAULT 0, can_read_mail INTEGER DEFAULT 0, can_reply_mail INTEGER DEFAULT 0,
                can_manage_admins INTEGER DEFAULT 0, can_send_codes INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS news (
                id SERIAL PRIMARY KEY, text TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS mail (
                id SERIAL PRIMARY KEY, from_user_id BIGINT, from_country TEXT, to_country TEXT,
                to_recipient TEXT, text TEXT, answer TEXT, answered_by BIGINT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id SERIAL PRIMARY KEY, user_id BIGINT, target_nick TEXT, target_country TEXT,
                target_position TEXT, status TEXT DEFAULT 'open', code_sent TEXT, sent_by BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, sent_at TEXT
            );
        """)

async def get_user(user_id: int):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

async def upsert_user(user_id: int, username: str):
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username", user_id, username)

async def is_owner(user_id: int) -> bool:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT username FROM users WHERE user_id = $1", user_id)
        if not row or not row['username']: return False
        return row['username'].lstrip("@").lower() == OWNER_USERNAME.lower()

async def is_admin(user_id: int) -> bool:
    if await is_owner(user_id): return True
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM admins WHERE user_id = $1", user_id)
        return row is not None

async def has_right(user_id: int, right: str) -> bool:
    if await is_owner(user_id): return True
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM admins WHERE user_id = $1", user_id)
        if not row: return False
        return bool(row[right])

async def add_admin(user_id: int, rights: dict):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO admins (user_id, can_edit_users, can_view_stats, can_publish_news, can_read_mail, can_reply_mail, can_manage_admins, can_send_codes)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (user_id) DO UPDATE SET
                can_edit_users = EXCLUDED.can_edit_users, can_view_stats = EXCLUDED.can_view_stats,
                can_publish_news = EXCLUDED.can_publish_news, can_read_mail = EXCLUDED.can_read_mail,
                can_reply_mail = EXCLUDED.can_reply_mail, can_manage_admins = EXCLUDED.can_manage_admins,
                can_send_codes = EXCLUDED.can_send_codes
        """, user_id, *[int(rights.get(k, 0)) for k in RIGHT_KEYS])

# ============================================================
#                     КЛАВИАТУРЫ
# ============================================================
def main_menu_kb(is_admin_user=False):
    buttons = [
        [KeyboardButton(text="ℹ️ Информация"), KeyboardButton(text="📰 Новости")],
        [KeyboardButton(text="🤝 Коммуникация")]
    ]
    if is_admin_user:
        buttons.append([KeyboardButton(text="🛠 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def info_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🖥 Сервера Zen", callback_data="info:servers")], [InlineKeyboardButton(text="🌍 ПолитWorld — главный проект", callback_data="info:main")], [InlineKeyboardButton(text="📜 Исторические ивенты", callback_data="info:events")], [InlineKeyboardButton(text="📱 Соцсети", callback_data="info:socials")]])

def servers_kb():
    rows = [[InlineKeyboardButton(text=v["title"], callback_data=f"srv:{k}")] for k, v in SERVERS.items()]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="info:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def socials_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=SOCIALS["youtube"]["title"], callback_data="soc:youtube")], [InlineKeyboardButton(text=SOCIALS["tiktok"]["title"], callback_data="soc:tiktok")], [InlineKeyboardButton(text="⬅️ Назад", callback_data="info:back")]])

def comm_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎖 Дипломатический профиль", callback_data="comm:profile")], [InlineKeyboardButton(text="✉️ Дипломатическая почта", callback_data="comm:mail")]])

def profile_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Заполнить / изменить данные", callback_data="prof:fill")], [InlineKeyboardButton(text="🔐 Ввести верификационный код", callback_data="prof:verify")], [InlineKeyboardButton(text="👤 Мой профиль", callback_data="prof:view")]])

def admin_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Тикеты на верификацию", callback_data="adm:tickets")],
        [InlineKeyboardButton(text="✏️ Изменить ник/страну", callback_data="adm:edit_user")],
        [InlineKeyboardButton(text="🗑 Удалить страну", callback_data="adm:del_country")],
        [InlineKeyboardButton(text="📊 Статистика пользователя", callback_data="adm:stats_user")],
        [InlineKeyboardButton(text="📰 Опубликовать новость", callback_data="adm:news")],
        [InlineKeyboardButton(text="📬 Дипломатическая почта", callback_data="adm:mail")],
        [InlineKeyboardButton(text="📈 Статистика по кодам", callback_data="adm:code_stats")],
        [InlineKeyboardButton(text="👥 Управление администраторами", callback_data="adm:admins")],
    ])

def admin_manage_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Добавить администратора", callback_data="admadm:add")], [InlineKeyboardButton(text="📋 Список администраторов", callback_data="admadm:list")], [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")]])

def back_to_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")]])

async def get_countries_kb():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT game_country FROM users WHERE verified = 1 AND game_country IS NOT NULL")
    buttons = [[InlineKeyboardButton(text="🌍 Администрация", callback_data="mailc:admins")]]
    for r in rows:
        c_name = r['game_country']
        if c_name.strip().lower() not in ["администрация", "zen community", "—"]:
            c_id = c_name.replace(" ", "_")
            buttons.append([InlineKeyboardButton(text=f"🏛 {c_name}", callback_data=f"mailc:{c_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="comm:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_people_kb(country_name: str):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT game_nick, game_position FROM users WHERE verified = 1 AND game_country = $1", country_name)
    buttons = []
    for r in rows:
        buttons.append([InlineKeyboardButton(text=f"{r['game_position']}: {r['game_nick']}", callback_data=f"mailto:{country_name}:{r['game_nick']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="comm:mail")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================================
#                     FSM
# ============================================================
class ProfileForm(StatesGroup):
    nick = State(); country = State(); position = State(); verify = State()

class MailForm(StatesGroup):
    text = State()

class AdminForms(StatesGroup):
    edit_user_id = State(); edit_user_nick = State(); edit_user_country = State()
    del_country_name = State()
    stats_user_id = State(); news_text = State()
    reply_mail_id = State(); reply_mail_text = State()
    add_admin_id = State(); add_admin_rights = State()

dp = Dispatcher()

# ============================================================
#                     ОБРАБОТЧИКИ
# ============================================================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await upsert_user(message.from_user.id, message.from_user.username or "")
    if (message.from_user.username or "").lstrip("@").lower() == OWNER_USERNAME.lower():
        await add_admin(message.from_user.id, {k: 1 for k in RIGHT_KEYS})
    
    admin_status = await is_admin(message.from_user.id)
    await message.answer("🌍 <b>ZEN COMMUNITY</b>\n\nДобро пожаловать в официальный бот сообщества.\nВыбери раздел в меню ниже.", reply_markup=main_menu_kb(admin_status))

@dp.message(Command("admin"))
async def admin_cmd(message: Message, state: FSMContext):
    await state.clear()
    if not await is_admin(message.from_user.id): return
    await message.answer("🛠 <b>Админ-панель</b>\nВыбери действие:", reply_markup=admin_menu_kb())

@dp.message(F.text == "🛠 Админ-панель")
async def admin_btn(message: Message, state: FSMContext):
    await admin_cmd(message, state)

@dp.message(F.text == "ℹ️ Информация")
async def info_menu(message: Message):
    await message.answer("ℹ️ <b>Раздел «Информация»</b>\nВыбери подраздел:", reply_markup=info_menu_kb())

@dp.callback_query(F.data == "info:back")
async def info_back(call: CallbackQuery):
    await call.message.edit_text("ℹ️ <b>Раздел «Информация»</b>\nВыбери подраздел:", reply_markup=info_menu_kb())
    await call.answer()

@dp.callback_query(F.data == "info:servers")
async def info_servers(call: CallbackQuery):
    await call.message.edit_text("╔══════ 🌍 ══════╗\n<b>ZEN COMMUNITY</b>\n<b>НАШИ СЕРВЕРА</b>\n╚═══════════════╝\n\nВыбери сервер:", reply_markup=servers_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("srv:"))
async def info_server_detail(call: CallbackQuery):
    srv = SERVERS.get(call.data.split(":", 1)[1])
    if not srv: return await call.answer("Не найдено", show_alert=True)
    await call.message.edit_text(f"<b>{srv['title']}</b>\n\n{srv['text']}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ К списку серверов", callback_data="info:servers")]]))
    await call.answer()

@dp.callback_query(F.data == "info:main")
async def info_main(call: CallbackQuery):
    await call.message.edit_text(MAIN_SERVER_TEXT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="info:back")]]), disable_web_page_preview=True)
    await call.answer()

@dp.callback_query(F.data == "info:events")
async def info_events(call: CallbackQuery):
    await call.message.edit_text("📜 <b>Исторические ивенты</b>\n\nВведи дату в формате <code>ДД.ММ.ГГГГ</code> (например, <code>20.10.2026</code>), и я покажу все события за этот день.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="info:back")]]))
    await call.answer()

@dp.callback_query(F.data == "info:socials")
async def info_socials(call: CallbackQuery):
    await call.message.edit_text("📱 <b>Наши соцсети</b>\nВыбери платформу:", reply_markup=socials_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("soc:"))
async def info_social_detail(call: CallbackQuery):
    soc = SOCIALS.get(call.data.split(":", 1)[1])
    if not soc: return await call.answer("Не найдено", show_alert=True)
    await call.message.edit_text(soc["text"], reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ К соцсетям", callback_data="info:socials")]]), disable_web_page_preview=True)
    await call.answer()

@dp.message(F.text.regexp(r"^\d{2}\.\d{2}\.\d{4}$"))
async def handle_event_date(message: Message):
    date_str = message.text.strip()
    try:
        target_date = datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError: 
        return await message.answer("❌ Неверная дата. Формат: ДД.ММ.ГГГГ")
    
    async with db_pool.acquire() as conn:
        # Ищем новости за этот день
        rows = await conn.fetch("SELECT text FROM news WHERE DATE(created_at) = $1", target_date)
    
    if rows:
        resp = f"📜 <b>События за {date_str}:</b>\n\n"
        for r in rows: resp += f"• {r['text']}\n\n"
        await message.answer(resp)
    else: 
        await message.answer(f"📜 <b>{date_str}</b>\n\nВ этот день в архивах Zen Community событий не зафиксировано.")

@dp.message(F.text == "📰 Новости")
async def news_menu(message: Message):
    async with db_pool.acquire() as conn:
        # Берем новости только за последние 48 часов
        rows = await conn.fetch("SELECT * FROM news WHERE created_at >= NOW() - INTERVAL '48 hours' ORDER BY id DESC")
    if not rows: return await message.answer("📰 За последние 48 часов новостей нет.")
    for r in rows: 
        await message.answer(f"📰 <b>Новость</b>\n<i>{r['created_at'].strftime('%d.%m.%Y %H:%M')}</i>\n\n{r['text']}")

@dp.message(F.text == "🤝 Коммуникация")
async def comm_menu(message: Message):
    await message.answer("🤝 <b>Раздел «Коммуникация»</b>\nВыбери действие:", reply_markup=comm_menu_kb())

# --- ПРОФИЛЬ ---
@dp.callback_query(F.data == "comm:profile")
async def comm_profile(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🎖 <b>Дипломатический профиль</b>\n\nЗаполни данные: игровой ник, страна, должность.\nПосле заполнения администрация получит тикет и отправит тебе 4-значный код по серверной почте.\n\n⚠️ После верификации изменить данные нельзя.", reply_markup=profile_menu_kb())
    await call.answer()

@dp.callback_query(F.data == "prof:view")
async def prof_view(call: CallbackQuery):
    u = await get_user(call.from_user.id)
    if not u: return await call.answer("Профиль не найден", show_alert=True)
    status = "✅ подтверждён" if u["verified"] else "⚠️ не подтверждён"
    await call.message.edit_text(f"👤 <b>Твой дипломатический профиль</b>\n\nНик: <b>{u['game_nick'] or '—'}</b>\nСтрана: <b>{u['game_country'] or '—'}</b>\nДолжность: <b>{u['game_position'] or '—'}</b>\nСтатус: {status}", reply_markup=profile_menu_kb())
    await call.answer()

@dp.callback_query(F.data == "prof:fill")
async def prof_fill(call: CallbackQuery, state: FSMContext):
    u = await get_user(call.from_user.id)
    if u and u["verified"]: return await call.answer("Данные уже подтверждены кодом и не могут быть изменены.", show_alert=True)
    await state.set_state(ProfileForm.nick)
    await call.message.edit_text("Шаг 1/3. Введи свой игровой ник:")
    await call.answer()

@dp.message(ProfileForm.nick)
async def prof_nick(message: Message, state: FSMContext):
    await state.update_data(nick=message.text.strip())
    await state.set_state(ProfileForm.country)
    await message.answer("Шаг 2/3. Введи свою страну в игре:")

@dp.message(ProfileForm.country)
async def prof_country(message: Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await state.set_state(ProfileForm.position)
    await message.answer("Шаг 3/3. Введи свою должность в игре:")

@dp.message(ProfileForm.position)
async def prof_position(message: Message, state: FSMContext):
    await state.update_data(position=message.text.strip())
    data = await state.get_data()
    await state.clear()

    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET game_nick=$1, game_country=$2, game_position=$3, verified=0, verify_code=NULL WHERE user_id=$4", data["nick"], data["country"], data["position"], message.from_user.id)
        await conn.execute("INSERT INTO tickets (user_id, target_nick, target_country, target_position, status) VALUES ($1, $2, $3, $4, 'open')", message.from_user.id, data["nick"], data["country"], data["position"])
        code_admins = await conn.fetch("SELECT user_id FROM admins WHERE can_send_codes=1")

    for r in code_admins:
        try: await message.bot.send_message(r["user_id"], f"🎫 <b>Новый тикет на верификацию</b>\n\nНик: <code>{data['nick']}</code>\nСтрана: {data['country']}\nДолжность: {data['position']}\n\nОткрой админ-панель и отправь код.")
        except Exception: pass

    await message.answer("✅ Данные профиля сохранены.\n\n📬 Создан тикет. Ожидай код от администрации.")

@dp.callback_query(F.data == "prof:verify")
async def prof_verify(call: CallbackQuery, state: FSMContext):
    u = await get_user(call.from_user.id)
    if not u or not u["game_nick"]: return await call.answer("Сначала заполни данные профиля.", show_alert=True)
    if u["verified"]: return await call.answer("Профиль уже подтверждён.", show_alert=True)
    await state.set_state(ProfileForm.verify)
    await call.message.edit_text("🔐 Введи 4-значный код из серверной почты:")
    await call.answer()

@dp.message(ProfileForm.verify)
async def prof_verify_code(message: Message, state: FSMContext):
    code = message.text.strip()
    u = await get_user(message.from_user.id)
    if u and u["verify_code"] and code == u["verify_code"]:
        async with db_pool.acquire() as conn:
            await conn.execute("UPDATE users SET verified=1, verify_code=NULL WHERE user_id=$1", message.from_user.id)
        await state.clear()
        await message.answer("✅ Профиль подтверждён! Теперь данные нельзя изменить.")
    else: await message.answer("❌ Неверный код. Попробуй ещё раз.")

# --- ПОЧТА ---
@dp.callback_query(F.data == "comm:mail")
async def comm_mail(call: CallbackQuery):
    u = await get_user(call.from_user.id)
    if not (u and u["verified"]):
        await call.message.edit_text("✉️ <b>Дипломатическая почта</b>\n\n⚠️ Ты не верифицирован. Пока можешь писать только администрации.\n\nНажми «Написать администрации».", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✉️ Написать администрации", callback_data="mailto:admins:admin")], [InlineKeyboardButton(text="⬅️ Назад", callback_data="comm:back")]]))
        return await call.answer()
    
    await call.message.edit_text("✉️ <b>Дипломатическая почта</b>\n\nВыбери страну:", reply_markup=await get_countries_kb())
    await call.answer()

@dp.callback_query(F.data == "comm:back")
async def comm_back(call: CallbackQuery):
    await call.message.edit_text("🤝 <b>Раздел «Коммуникация»</b>\nВыбери действие:", reply_markup=comm_menu_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("mailc:"))
async def comm_mail_country(call: CallbackQuery):
    country_id = call.data.split(":", 1)[1]
    if country_id == "admins":
        # Показываем админов по их игровым никам
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, game_nick, username FROM admins LEFT JOIN users ON admins.user_id = users.user_id")
        buttons = []
        for r in rows:
            nick = r['game_nick'] or r['username'] or "Администратор"
            buttons.append([InlineKeyboardButton(text=f"👑 {nick}", callback_data=f"mailto:Администрация:{nick}")])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="comm:mail")])
        await call.message.edit_text("✉️ <b>Администрация</b>\n\nВыбери, кому направить сообщение:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    else:
        country_name = country_id.replace("_", " ")
        await call.message.edit_text(f"✉️ <b>{country_name}</b>\n\nВыбери, кому направить сообщение:", reply_markup=await get_people_kb(country_name))
    await call.answer()

@dp.callback_query(F.data.startswith("mailto:"))
async def comm_mail_recipient(call: CallbackQuery, state: FSMContext):
    _, country_name, recipient = call.data.split(":", 2)
    await state.update_data(mail_country=country_name, mail_recipient=recipient)
    await state.set_state(MailForm.text)
    await call.message.edit_text(f"✍️ Введи текст сообщения для <b>{country_name}</b> (получатель: <code>{recipient}</code>):")
    await call.answer()

@dp.message(MailForm.text)
async def comm_mail_send(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    u = await get_user(message.from_user.id)
    from_country = u["game_country"] if u and u["game_country"] else "—"
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO mail (from_user_id, from_country, to_country, to_recipient, text, created_at) VALUES ($1, $2, $3, $4, $5, $6)", message.from_user.id, from_country, data["mail_country"], data["mail_recipient"], message.text, datetime.now().strftime("%d.%m.%Y %H:%M"))
    await message.answer("✅ Сообщение отправлено по дипломатической почте.\nОтвет придёт сюда же.")

# ============================================================
#                     АДМИН-ПАНЕЛЬ
# ============================================================
@dp.callback_query(F.data == "adm:back")
async def adm_back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🛠 <b>Админ-панель</b>\nВыбери действие:", reply_markup=admin_menu_kb())
    await call.answer()

@dp.callback_query(F.data == "adm:tickets")
async def adm_tickets(call: CallbackQuery):
    if not await has_right(call.from_user.id, "can_send_codes"): return await call.answer("Нет прав", show_alert=True)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM tickets WHERE status='open' ORDER BY id ASC LIMIT 20")
    if not rows:
        await call.message.edit_text("🎫 <b>Тикеты</b>\n\nОткрытых тикетов нет.", reply_markup=back_to_admin_kb())
        return await call.answer()
    text = "🎫 <b>Открытые тикеты:</b>\n\n"
    buttons = []
    for r in rows:
        text += f"<b>#{r['id']}</b> — <code>{r['target_nick']}</code> ({r['target_country']})\n"
        buttons.append([InlineKeyboardButton(text=f"Открыть тикет #{r['id']}", callback_data=f"ticket:open:{r['id']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data.startswith("ticket:open:"))
async def adm_ticket_open(call: CallbackQuery):
    if not await has_right(call.from_user.id, "can_send_codes"): return await call.answer("Нет прав", show_alert=True)
    t_id = int(call.data.split(":")[-1])
    async with db_pool.acquire() as conn:
        t = await conn.fetchrow("SELECT * FROM tickets WHERE id=$1", t_id)
    if not t: return await call.answer("Тикет не найден", show_alert=True)
    
    code = str(random.randint(1000, 9999))
    copy_text = f"Код подтверждения для игрока {t['target_nick']}: {code}"
    
    await call.message.edit_text(
        f"🎫 <b>Тикет #{t_id}</b>\n\n"
        f"Ник: <code>{t['target_nick']}</code>\n"
        f"Страна: {t['target_country']}\n"
        f"Роль: {t['target_position']}\n\n"
        f"👇 <b>Текст для отправки (нажми, чтобы скопировать):</b>\n"
        f"<code>{copy_text}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я отправил код по серверной почте", callback_data=f"ticket:done:{t_id}:{code}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:tickets")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("ticket:done:"))
async def adm_ticket_done(call: CallbackQuery):
    _, _, t_id, code = call.data.split(":")
    t_id = int(t_id)
    async with db_pool.acquire() as conn:
        t = await conn.fetchrow("SELECT user_id FROM tickets WHERE id=$1", t_id)
        if t:
            await conn.execute("UPDATE tickets SET status='sent', code_sent=$1, sent_by=$2, sent_at=$3 WHERE id=$4", code, call.from_user.id, datetime.now().strftime("%d.%m.%Y %H:%M"), t_id)
            await conn.execute("UPDATE users SET verify_code=$1 WHERE user_id=$2", code, t['user_id'])
            try: await call.bot.send_message(t['user_id'], f"📬 <b>Дипломатическая почта</b>\n\nДля твоего профиля отправлен верификационный код.\nПроверь серверную почту в игре и введи код в разделе «Дипломатический профиль» → «Ввести код».")
            except Exception: pass
    await call.message.edit_text("✅ Код сохранен в БД, игроку отправлено уведомление.", reply_markup=back_to_admin_kb())
    await call.answer()

@dp.callback_query(F.data == "adm:del_country")
async def adm_del_country(call: CallbackQuery, state: FSMContext):
    if not await has_right(call.from_user.id, "can_edit_users"): return await call.answer("Нет прав", show_alert=True)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT game_country FROM users WHERE game_country IS NOT NULL")
    if not rows: return await call.answer("В базе нет стран.", show_alert=True)
    buttons = [[InlineKeyboardButton(text=f"🗑 {r['game_country']}", callback_data=f"adm:del_country_do:{r['game_country']}")] for r in rows]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")])
    await call.message.edit_text("Выбери страну для удаления (у всех игроков этой страны она обнулится):", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data.startswith("adm:del_country_do:"))
async def adm_del_country_do(call: CallbackQuery):
    if not await has_right(call.from_user.id, "can_edit_users"): return await call.answer("Нет прав", show_alert=True)
    c_name = call.data.split(":", 1)[1]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET game_country = NULL WHERE game_country = $1", c_name)
    await call.answer(f"Страна '{c_name}' удалена", show_alert=True)
    await call.message.edit_text("🛠 <b>Админ-панель</b>", reply_markup=admin_menu_kb())

@dp.callback_query(F.data == "adm:edit_user")
async def adm_edit_user(call: CallbackQuery, state: FSMContext):
    if not await has_right(call.from_user.id, "can_edit_users"): return await call.answer("Нет прав", show_alert=True)
    await state.set_state(AdminForms.edit_user_id)
    await call.message.edit_text("Введи <b>user_id</b> пользователя, чьи данные меняем:")
    await call.answer()

@dp.message(AdminForms.edit_user_id)
async def adm_edit_user_id(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Нужен числовой user_id.")
    u = await get_user(int(message.text))
    if not u: return await message.answer("Пользователь не найден.")
    await state.update_data(edit_uid=u['user_id'])
    await state.set_state(AdminForms.edit_user_nick)
    await message.answer(f"Текущий ник: <b>{u['game_nick'] or '—'}</b>\nВведи новый ник (или отправь <code>-</code>, чтобы оставить):")

@dp.message(AdminForms.edit_user_nick)
async def adm_edit_user_nick(message: Message, state: FSMContext):
    if message.text.strip() != "-": await state.update_data(new_nick=message.text.strip())
    await state.set_state(AdminForms.edit_user_country)
    await message.answer("Введи новую страну (или <code>-</code>, чтобы оставить):")

@dp.message(AdminForms.edit_user_country)
async def adm_edit_user_country(message: Message, state: FSMContext):
    data = await state.get_data()
    async with db_pool.acquire() as conn:
        if message.text.strip() != "-": await conn.execute("UPDATE users SET game_country=$1 WHERE user_id=$2", message.text.strip(), data["edit_uid"])
        if "new_nick" in data: await conn.execute("UPDATE users SET game_nick=$1 WHERE user_id=$2", data["new_nick"], data["edit_uid"])
    await state.clear()
    await message.answer("✅ Данные обновлены.", reply_markup=main_menu_kb(await is_admin(message.from_user.id)))

@dp.callback_query(F.data == "adm:stats_user")
async def adm_stats_user(call: CallbackQuery, state: FSMContext):
    if not await has_right(call.from_user.id, "can_view_stats"): return await call.answer("Нет прав", show_alert=True)
    await state.set_state(AdminForms.stats_user_id)
    await call.message.edit_text("Введи <b>user_id</b> для просмотра статистики:")
    await call.answer()

@dp.message(AdminForms.stats_user_id)
async def adm_stats_result(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Нужен числовой user_id.")
    u = await get_user(int(message.text))
    if not u: return await message.answer("Пользователь не найден.")
    async with db_pool.acquire() as conn:
        sent = await conn.fetchval("SELECT COUNT(*) FROM mail WHERE from_user_id=$1", u['user_id'])
        answered = await conn.fetchval("SELECT COUNT(*) FROM mail WHERE answered_by=$1", u['user_id'])
    await state.clear()
    await message.answer(f"📊 <b>Статистика {u['user_id']}</b>\n\nUsername: @{u['username'] or '—'}\nНик: {u['game_nick'] or '—'}\nСтрана: {u['game_country'] or '—'}\nРоль: {u['game_position'] or '—'}\nВерифицирован: {'да' if u['verified'] else 'нет'}\nПисем отправлено: {sent}\nОтвечено: {answered}")

@dp.callback_query(F.data == "adm:news")
async def adm_news(call: CallbackQuery, state: FSMContext):
    if not await has_right(call.from_user.id, "can_publish_news"): return await call.answer("Нет прав", show_alert=True)
    await state.set_state(AdminForms.news_text)
    await call.message.edit_text("Введи текст новости для рассылки (она также сохранится в архиве):")
    await call.answer()

@dp.message(AdminForms.news_text)
async def adm_news_send(message: Message, state: FSMContext):
    text = message.text.strip()
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO news (text, created_at) VALUES ($1, NOW())", text)
        users = await conn.fetch("SELECT user_id FROM users")
    await state.clear()
    sent = 0
    for r in users:
        try: await message.bot.send_message(r["user_id"], f"📰 <b>Новость</b>\n\n{text}"); sent += 1
        except: pass
    await message.answer(f"✅ Новость опубликована и добавлена в архив. Доставлено: {sent}.", reply_markup=main_menu_kb(await is_admin(message.from_user.id)))

@dp.callback_query(F.data == "adm:mail")
async def adm_mail(call: CallbackQuery):
    if not await has_right(call.from_user.id, "can_read_mail"): return await call.answer("Нет прав", show_alert=True)
    await call.message.edit_text("📬 <b>Дипломатическая почта</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 Входящие", callback_data="admmail:list")], [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")]]))
    await call.answer()

@dp.callback_query(F.data == "admmail:list")
async def adm_mail_list(call: CallbackQuery):
    if not await has_right(call.from_user.id, "can_read_mail"): return await call.answer("Нет прав", show_alert=True)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM mail ORDER BY id DESC LIMIT 20")
    if not rows:
        await call.message.edit_text("📭 Входящих нет.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:mail")]]))
        return await call.answer()
    text = "📥 <b>Последние сообщения:</b>\n\n"
    buttons = []
    for r in rows:
        status = "✅" if r["answer"] else "🕓"
        text += f"{status} <b>#{r['id']}</b> от {r['from_country']} → {r['to_country']}/{r['to_recipient']}\n{r['text'][:100]}...\n\n"
        if not r["answer"]: buttons.append([InlineKeyboardButton(text=f"Ответить на #{r['id']}", callback_data=f"admmail:reply:{r['id']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:mail")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data.startswith("admmail:reply:"))
async def adm_mail_reply(call: CallbackQuery, state: FSMContext):
    if not await has_right(call.from_user.id, "can_reply_mail"): return await call.answer("Нет прав", show_alert=True)
    mail_id = int(call.data.split(":")[-1])
    await state.update_data(reply_mail_id=mail_id)
    await state.set_state(AdminForms.reply_mail_text)
    await call.message.edit_text(f"✍️ Введи ответ на сообщение #{mail_id}:")
    await call.answer()

@dp.message(AdminForms.reply_mail_text)
async def adm_mail_reply_send(message: Message, state: FSMContext):
    data = await state.get_data()
    mail_id, text = data["reply_mail_id"], message.text.strip()
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM mail WHERE id=$1", mail_id)
        if not row: return await message.answer("Сообщение не найдено.")
        await conn.execute("UPDATE mail SET answer=$1, answered_by=$2 WHERE id=$3", text, message.from_user.id, mail_id)
    try: await message.bot.send_message(row["from_user_id"], f"📬 <b>Ответ по дипломатической почте</b>\nНа твоё сообщение #{mail_id}:\n\n{text}")
    except: pass
    await state.clear()
    await message.answer("✅ Ответ отправлен.", reply_markup=main_menu_kb(await is_admin(message.from_user.id)))

# Управление админами
@dp.callback_query(F.data == "adm:admins")
async def adm_admins(call: CallbackQuery):
    if not await has_right(call.from_user.id, "can_manage_admins"): return await call.answer("Нет прав", show_alert=True)
    await call.message.edit_text("👥 <b>Управление администраторами</b>", reply_markup=admin_manage_kb())
    await call.answer()

@dp.callback_query(F.data == "admadm:list")
async def adm_admins_list(call: CallbackQuery):
    if not await has_right(call.from_user.id, "can_manage_admins"): return await call.answer("Нет прав", show_alert=True)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM admins")
    if not rows: return await call.message.edit_text("Список пуст.", reply_markup=admin_manage_kb())
    text = "📋 <b>Администраторы:</b>\n\n"
    buttons = []
    for r in rows:
        granted = [RIGHT_LABELS[k] for k in RIGHT_KEYS if r[k]]
        text += f"• <code>{r['user_id']}</code>: {', '.join(granted) or '—'}\n"
        buttons.append([InlineKeyboardButton(text=f"🗑 Снять {r['user_id']}", callback_data=f"admadm:del:{r['user_id']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:admins")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data.startswith("admadm:del:"))
async def adm_admins_del(call: CallbackQuery):
    if not await has_right(call.from_user.id, "can_manage_admins"): return await call.answer("Нет прав", show_alert=True)
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM admins WHERE user_id = $1", int(call.data.split(":")[-1]))
    await call.answer("Права сняты.", show_alert=True)
    await call.message.edit_text("👥 <b>Управление администраторами</b>", reply_markup=admin_manage_kb())

@dp.callback_query(F.data == "admadm:add")
async def adm_admins_add(call: CallbackQuery, state: FSMContext):
    if not await has_right(call.from_user.id, "can_manage_admins"): return await call.answer("Нет прав", show_alert=True)
    await state.set_state(AdminForms.add_admin_id)
    await call.message.edit_text("Введи <b>user_id</b> нового администратора:")
    await call.answer()

@dp.message(AdminForms.add_admin_id)
async def adm_admins_add_id(message: Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Нужен числовой user_id.")
    await state.update_data(new_admin_id=int(message.text))
    await state.set_state(AdminForms.add_admin_rights)
    await message.answer("Введи права через запятую:\n\n<code>edit</code> — менять ник/страну\n<code>stats</code> — смотреть статистику\n<code>news</code> — публиковать новости\n<code>read</code> — читать почту\n<code>reply</code> — отвечать на почту\n<code>admins</code> — управлять админами\n<code>codes</code> — отправлять коды\n\nПример: <code>news,stats</code>")

@dp.message(AdminForms.add_admin_rights)
async def adm_admins_add_rights(message: Message, state: FSMContext):
    chosen = [p.strip().lower() for p in message.text.split(",") if p.strip()]
    rights = {v: 0 for v in RIGHT_KEYS}
    for c in chosen:
        if c in RIGHT_SHORTCUTS: rights[RIGHT_SHORTCUTS[c]] = 1
    data = await state.get_data()
    await add_admin(data["new_admin_id"], rights)
    await state.clear()
    await message.answer(f"✅ Пользователь <code>{data['new_admin_id']}</code> назначен администратором.", reply_markup=main_menu_kb(await is_admin(message.from_user.id)))

@dp.callback_query(F.data == "adm:code_stats")
async def adm_code_stats(call: CallbackQuery):
    if not await has_right(call.from_user.id, "can_manage_admins"): return await call.answer("Нет прав", show_alert=True)
    async with db_pool.acquire() as conn:
        by_admin = await conn.fetch("SELECT sent_by, COUNT(*) AS cnt FROM tickets WHERE status='sent' AND sent_by IS NOT NULL GROUP BY sent_by")
        by_status = await conn.fetch("SELECT status, COUNT(*) AS cnt FROM tickets GROUP BY status")
        code_admins = await conn.fetch("SELECT user_id FROM admins WHERE can_send_codes=1")
    text = "📈 <b>Статистика по кодам</b>\n\n<b>Всего тикетов по статусам:</b>\n"
    for s in by_status:
        emoji = {"open": "🕓", "sent": "✅", "rejected": "❌"}.get(s["status"], "•")
        text += f"{emoji} {s['status']}: {s['cnt']}\n"
    if not by_status: text += "— нет данных\n"
    text += "\n<b>Кто сколько кодов отправил:</b>\n"
    if by_admin:
        for r in by_admin: text += f"• <code>{r['sent_by']}</code> — {r['cnt']} шт.\n"
    else: text += "— пока никто\n"
    text += "\n<b>Кто имеет право отправлять коды:</b>\n"
    if code_admins:
        for r in code_admins: text += f"• <code>{r['user_id']}</code>\n"
    else: text += "— никого\n"
    await call.message.edit_text(text, reply_markup=back_to_admin_kb())
    await call.answer()

# ============================================================
#                     ЗАПУСК (Заглушка для Render)
# ============================================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

async def main():
    if not BOT_TOKEN or "ВСТАВЬ" in BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в Environment Variables!")
    
    threading.Thread(target=run_dummy_server, daemon=True).start()
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logging.info("Bot started successfully!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
