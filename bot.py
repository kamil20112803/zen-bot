
import asyncio
import os
import logging
from datetime import datetime

import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)

# ============================================================
#                     НАСТРОЙКИ
# ============================================================
# ВАЖНО: Токен и базу мы берем из настроек Render (Environment Variables)
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_СВОЙ_ТОКЕН_СЮДА_ЕСЛИ_ТЕСТИРУЕШЬ_ЛОКАЛЬНО")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://zen_db_ayih_user:xgEI5NGNmWrFWXdDeoh86jUjnaxZv30h@dpg-dbb22pbbc2fs73d8gokg-a/zen_db_ayih")

OWNER_USERNAME = "rt6y9n"

logging.basicConfig(level=logging.INFO)

# Пул соединений с БД
db_pool = None

# ============================================================
#                     СТАТИЧНЫЕ ДАННЫЕ
# ============================================================

SERVERS = {
    "survival": {
        "title": "⚔️ 1. ПолитWorld | ВЫЖИВАНИЕ",
        "text": "👑 Оригинальный политический сервер MultiCraft.\n\n🏛️ Создавай государства, заключай союзы, веди войны и развивай экономику!\n\n🔗 Инвайт: <code>PFJQTM0C</code>",
    },
    "creative": {
        "title": "🏗️ 2. ПолитWorld | КРЕАТИВ",
        "text": "🏙️ Строй столицы, создавай города, возводи инфраструктуру и воплощай свои идеи в жизнь!\n\n🔗 Инвайт: <code>LI9QFVL4</code>",
    },
    "medieval": {
        "title": "🏰 3. ПолитWorld | СРЕДНЕВЕКОВЬЕ",
        "text": "🛡️ Эпоха королевств, замков и великих сражений. Создавай собственные владения, заключай союзы и пиши историю своего государства!\n\n🔗 Инвайт: <code>NOIMVNSB</code>",
    },
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
    "youtube": {
        "title": "▶️ YouTube — Zen Community",
        "text": "▶️ <b>Наш YouTube-канал</b>\n\nЗдесь выходят обзоры серверов, хроники войн, интервью с правителями и репортажи о ключевых событиях мира ПолитWorld.\n\n🔗 <a href=\"https://youtube.com/@ЗАМЕНИ_ССЫЛКУ\">Перейти на канал</a>",
    },
    "tiktok": {
        "title": "🎵 TikTok — Zen Community",
        "text": "🎵 <b>Наш TikTok</b>\n\nКороткие ролики: яркие моменты, конфликты, союзы и жизнь сообщества в формате, который удобно смотреть на ходу.\n\n🔗 <a href=\"https://tiktok.com/@ЗАМЕНИ_ССЫЛКУ\">Перейти в профиль</a>",
    },
}

HISTORICAL_EVENTS = {
    "01.05.2024": "🏛️ <b>Основание Zen Community.</b>\nСообщество официально заявило о себе и открыло первый политический сервер.",
    "12.06.2024": "⚔️ <b>Первая крупная война.</b>\nКоалиция государств выступила против усиливающейся державы — мир ПолитWorld изменился навсегда.",
    "23.09.2024": "🕊️ <b>Подписание Великого союза.</b>\nТри крупнейшие державы заключили долгосрочное соглашение о ненападении.",
}

COUNTRIES = {
    "zen": {"name": "🌍 Zen Community", "people": [("admin", "Администрация Zen Community"), ("rt6y9n", "@rt6y9n — Глава сообщества")]},
    "north": {"name": "🏔️ Северная Держава", "people": [("leader_north", "Глава Северной Державы"), ("diplomat_north", "Дипломат Северной Державы")]},
    "south": {"name": "🌊 Южная Федерация", "people": [("leader_south", "Президент Южной Федерации")]},
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
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                game_nick TEXT,
                game_country TEXT,
                game_position TEXT,
                verified INTEGER DEFAULT 0,
                verify_code TEXT
            );
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                can_edit_users INTEGER DEFAULT 0,
                can_view_stats INTEGER DEFAULT 0,
                can_publish_news INTEGER DEFAULT 0,
                can_read_mail INTEGER DEFAULT 0,
                can_reply_mail INTEGER DEFAULT 0,
                can_manage_admins INTEGER DEFAULT 0,
                can_send_codes INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS news (
                id SERIAL PRIMARY KEY,
                text TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS mail (
                id SERIAL PRIMARY KEY,
                from_user_id BIGINT,
                from_country TEXT,
                to_country TEXT,
                to_recipient TEXT,
                text TEXT,
                answer TEXT,
                answered_by BIGINT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                target_nick TEXT,
                target_country TEXT,
                target_position TEXT,
                status TEXT DEFAULT 'open',
                code_sent TEXT,
                sent_by BIGINT,
                created_at TEXT,
                sent_at TEXT
            );
        """)

async def get_user(user_id: int):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

async def upsert_user(user_id: int, username: str):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username",
            user_id, username
        )

async def is_owner(user_id: int) -> bool:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT username FROM users WHERE user_id = $1", user_id)
        if not row or not row['username']: return False
        return row['username'].lstrip("@").lower() == OWNER_USERNAME.lower()

async def is_admin(user_id: int) -> bool:
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

async def remove_admin(user_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM admins WHERE user_id = $1", user_id)

# ============================================================
#                     КЛАВИАТУРЫ
# ============================================================

def main_menu_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="ℹ️ Информация"), KeyboardButton(text="📰 Новости")], [KeyboardButton(text="🤝 Коммуникация")]], resize_keyboard=True)

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

def countries_kb(prefix: str):
    rows = [[InlineKeyboardButton(text=v["name"], callback_data=f"{prefix}:{k}")] for k, v in COUNTRIES.items()]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def people_kb(country_key: str):
    rows = [[InlineKeyboardButton(text=label, callback_data=f"mailto:{country_key}:{rid}")] for rid, label in COUNTRIES[country_key]["people"]]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="comm:mail")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Тикеты на верификацию", callback_data="adm:tickets")],
        [InlineKeyboardButton(text="✏️ Изменить ник/страну", callback_data="adm:edit_user")],
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

# ============================================================
#                     FSM
# ============================================================

class ProfileForm(StatesGroup):
    nick = State(); country = State(); position = State(); verify = State()

class MailForm(StatesGroup):
    text = State()

class AdminForms(StatesGroup):
    edit_user_id = State(); edit_user_nick = State(); edit_user_country = State()
    stats_user_id = State(); news_text = State()
    reply_mail_id = State(); reply_mail_text = State()
    add_admin_id = State(); add_admin_rights = State()
    ticket_send_code = State(); ticket_send_nick = State()

dp = Dispatcher()

# ============================================================
#                     ХЭНДЛЕРЫ
# ============================================================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await upsert_user(message.from_user.id, message.from_user.username or "")
    if (message.from_user.username or "").lstrip("@").lower() == OWNER_USERNAME.lower():
        await add_admin(message.from_user.id, {k: 1 for k in RIGHT_KEYS})
        await message.answer("👑 <b>Добро пожаловать, владелец!</b>\nТебе выданы полные права администратора.\nАдмин-панель: /admin", reply_markup=main_menu_kb())
        return
    await message.answer("🌍 <b>ZEN COMMUNITY</b>\n\nДобро пожаловать в официальный бот сообщества.\nВыбери раздел в меню ниже.", reply_markup=main_menu_kb())

@dp.message(F.text == "ℹ️ Информация")
async def info_menu(message: Message):
    await message.answer("ℹ️ <b>Раздел «Информация»</b>\nВыбери подраздел:", reply_markup=info_menu_kb())

@dp.callback_query(F.data == "info:back")
async def info_back(call: CallbackQuery):
    await call.message.edit_text("ℹ️ <b>Раздел «Информация»</b>\nВыбери подраздел:", reply_markup=info_menu_kb())
    await call.answer()

@dp.callback_query(F.data == "info:servers")
async def info_servers(call: CallbackQuery):
    await call.message.edit_text("╔══════ 🌍 ══════╗\n<b>ZEN COMMUNITY</b>\n<b>НАШИ СЕРВЕРЫ</b>\n╚═══════════════╝\n\nВыбери сервер:", reply_markup=servers_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("srv:"))
async def info_server_detail(call: CallbackQuery):
    key = call.data.split(":", 1)[1]
    srv = SERVERS.get(key)
    if not srv: return await call.answer("Не найдено", show_alert=True)
    await call.message.edit_text(f"<b>{srv['title']}</b>\n\n{srv['text']}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ К списку серверов", callback_data="info:servers")]]))
    await call.answer()

@dp.callback_query(F.data == "info:main")
async def info_main(call: CallbackQuery):
    await call.message.edit_text(MAIN_SERVER_TEXT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="info:back")]]), disable_web_page_preview=True)
    await call.answer()

@dp.callback_query(F.data == "info:events")
async def info_events(call: CallbackQuery):
    await call.message.edit_text("📜 <b>Исторические ивенты</b>\n\nВведи дату в формате <code>ДД.ММ.ГГГГ</code> (например, <code>01.05.2024</code>), и я расскажу, что произошло в этот день.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="info:back")]]))
    await call.answer()

@dp.callback_query(F.data == "info:socials")
async def info_socials(call: CallbackQuery):
    await call.message.edit_text("📱 <b>Наши соцсети</b>\nВыбери платформу:", reply_markup=socials_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("soc:"))
async def info_social_detail(call: CallbackQuery):
    key = call.data.split(":", 1)[1]
    soc = SOCIALS.get(key)
    if not soc: return await call.answer("Не найдено", show_alert=True)
    await call.message.edit_text(soc["text"], reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ К соцсетям", callback_data="info:socials")]]), disable_web_page_preview=True)
    await call.answer()

@dp.message(F.text.regexp(r"^\d{2}\.\d{2}\.\d{4}$"))
async def handle_event_date(message: Message):
    date_str = message.text.strip()
    try: datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError: return await message.answer("❌ Неверная дата. Формат: ДД.ММ.ГГГГ")
    event = HISTORICAL_EVENTS.get(date_str)
    if event: await message.answer(f"📜 <b>{date_str}</b>\n\n{event}")
    else: await message.answer(f"📜 <b>{date_str}</b>\n\nВ этот день в архивах Zen Community событий не зафиксировано.")

@dp.message(F.text == "📰 Новости")
async def news_menu(message: Message):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM news ORDER BY id DESC LIMIT 20")
    if not rows: return await message.answer("📰 Пока новостей нет.")
    for r in rows: await message.answer(f"📰 <b>Новость #{r['id']}</b>\n<i>{r['created_at']}</i>\n\n{r['text']}")

@dp.message(F.text == "🤝 Коммуникация")
async def comm_menu(message: Message):
    await message.answer("🤝 <b>Раздел «Коммуникация»</b>\nВыбери действие:", reply_markup=comm_menu_kb())

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
        await conn.execute("INSERT INTO tickets (user_id, target_nick, target_country, target_position, status, created_at) VALUES ($1, $2, $3, $4, 'open', $5)", message.from_user.id, data["nick"], data["country"], data["position"], datetime.now().strftime("%d.%m.%Y %H:%M"))
        code_admins = await conn.fetch("SELECT user_id FROM admins WHERE can_send_codes=1")

    for r in code_admins:
        try: await message.bot.send_message(r["user_id"], f"🎫 <b>Новый тикет на верификацию</b>\n\nНик: <code>{data['nick']}</code>\nСтрана: {data['country']}\nДолжность: {data['position']}\n\nОткрой админ-панель (/admin) → «Тикеты на верификацию» и отправь код.")
        except Exception: pass

    await message.answer("✅ Данные профиля сохранены.\n\n📬 Создан тикет на верификацию. Администрация отправит тебе 4-значный код по серверной почте на сервере.\n\nКак только получишь код в игре — введи его в разделе «Дипломатический профиль» → «Ввести код».")

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

@dp.callback_query(F.data == "comm:mail")
async def comm_mail(call: CallbackQuery):
    u = await get_user(call.from_user.id)
    if not (u and u["verified"]):
        await call.message.edit_text("✉️ <b>Дипломатическая почта</b>\n\n⚠️ Ты не верифицирован. Пока можешь писать только администрации.\n\nНажми «Написать администрации».", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✉️ Написать администрации", callback_data="mailto:zen:admin")], [InlineKeyboardButton(text="⬅️ Назад", callback_data="comm:back")]]))
        return await call.answer()
    await call.message.edit_text("✉️ <b>Дипломатическая почта</b>\n\nВыбери страну:", reply_markup=countries_kb("mailc"))
    await call.answer()

@dp.callback_query(F.data == "comm:back")
async def comm_back(call: CallbackQuery):
    await call.message.edit_text("🤝 <b>Раздел «Коммуникация»</b>\nВыбери действие:", reply_markup=comm_menu_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("mailc:"))
async def comm_mail_country(call: CallbackQuery):
    country_key = call.data.split(":", 1)[1]
    if country_key not in COUNTRIES: return await call.answer("Не найдено", show_alert=True)
    await call.message.edit_text(f"✉️ <b>{COUNTRIES[country_key]['name']}</b>\n\nКому направить сообщение?", reply_markup=people_kb(country_key))
    await call.answer()

@dp.callback_query(F.data.startswith("mailto:"))
async def comm_mail_recipient(call: CallbackQuery, state: FSMContext):
    _, country_key, recipient = call.data.split(":", 2)
    await state.update_data(mail_country=country_key, mail_recipient=recipient)
    await state.set_state(MailForm.text)
    await call.message.edit_text("✍️ Введи текст дипломатического сообщения:")
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

@dp.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    if not await is_admin(message.from_user.id): return await message.answer("⛔ У тебя нет доступа.")
    await message.answer("🛠 <b>Админ-панель</b>\nВыбери действие:", reply_markup=admin_menu_kb())

@dp.callback_query(F.data == "adm:back")
async def adm_back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🛠 <b>Админ-панель</b>\nВыбери действие:", reply_markup=admin_menu_kb())
    await call.answer()

# ТИКЕТЫ
@dp.callback_query(F.data == "adm:tickets")
async def adm_tickets(call: CallbackQuery):
    if not await has_right(call.from_user.id, "can_send_codes"): return await call.answer("Нет прав", show_alert=True)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM tickets WHERE status='open' ORDER BY id ASC LIMIT 20")
    if not rows:
        await call.message.edit_text("🎫 <b>Тикеты на верификацию</b>\n\nОткрытых тикетов нет.", reply_markup=back_to_admin_kb())
        return await call.answer()
    text = "🎫 <b>Открытые тикеты:</b>\n\n"
    buttons = []
    for r in rows:
        text += f"<b>#{r['id']}</b> — ник <code>{r['target_nick']}</code> ({r['target_country']})\nuser_id: <code>{r['user_id']}</code> • {r['created_at']}\n\n"
        buttons.append([InlineKeyboardButton(text=f"📨 Отправить код по тикету #{r['id']}", callback_data=f"ticket:send:{r['id']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data.startswith("ticket:send:"))
async def adm_ticket_send_start(call: CallbackQuery, state: FSMContext):
    if not await has_right(call.from_user.id, "can_send_codes"): return await call.answer("Нет прав", show_alert=True)
    ticket_id = int(call.data.split(":")[-1])
    await state.update_data(ticket_id=ticket_id)
    await state.set_state(AdminForms.ticket_send_code)
    await call.message.edit_text(f"🎫 Тикет #{ticket_id}\n\nВведи 4-значный код, который ты отправишь по серверной почте игроку:")
    await call.answer()

@dp.message(AdminForms.ticket_send_code)
async def adm_ticket_send_code(message: Message, state: FSMContext):
    code = message.text.strip()
    if not (code.isdigit() and len(code) == 4): return await message.answer("Код должен быть из 4 цифр. Попробуй ещё раз:")
    await state.update_data(ticket_code=code)
    await state.set_state(AdminForms.ticket_send_nick)
    await message.answer("Теперь подтверди ник игрока на сервере
