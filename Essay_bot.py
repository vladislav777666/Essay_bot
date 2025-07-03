import asyncio
import aiohttp
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command

API_TOKEN = '8101812893:AAEXynon2ogqCX7SCbpZUpld4nAz2GKxUhA'
DA_ACCESS_TOKEN = '9dX94XworRBHUXgvHJbL'

# 📦 Инициализация
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# 🔐 Подключение к базе
conn = sqlite3.connect("premium_users.db")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS premium (user_id INTEGER PRIMARY KEY)")
conn.commit()

# ✅ Проверка в БД
def is_premium(user_id: int) -> bool:
    cursor.execute("SELECT 1 FROM premium WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

# ➕ Добавить в БД
def add_premium(user_id: int):
    try:
        cursor.execute("INSERT INTO premium VALUES (?)", (user_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Уже добавлен

# 🧭 Главное меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👑 Премиум")]
    ],
    resize_keyboard=True
)

# 🚀 /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Привет! Я бот, который пишет эссе.\n\n"
        f"1️⃣ Оплати: https://www.donationalerts.com/r/essay_bot\n"
        f"2️⃣ В комментарии укажи Telegram ID: {message.from_user.id}\n"
        f"3️⃣ Нажми /check после оплаты.",
        reply_markup=main_menu
    )

# 🔍 /check — проверка доната
@dp.message(Command("check"))
async def cmd_check(message: Message):
    tg_id = str(message.from_user.id)

    async with aiohttp.ClientSession() as session:
        headers = {'Authorization': f'Bearer {DA_ACCESS_TOKEN}'}
        async with session.get('https://www.donationalerts.com/api/v1/donations', headers=headers) as resp:
            if resp.status != 200:
                await message.answer(f"❌ Ошибка API: статус {resp.status}")
                return

            data = await resp.json()

            for donation in data.get('data', []):
                comment = donation.get('message', '')
                if tg_id in comment:
                    if donation['id'] not in checked_donors:
                        checked_donors.add(donation['id'])
                        add_premium(message.from_user.id)
                        await message.answer("✅ Донат найден! Вы получили Премиум-доступ 🎉")
                        return

            await message.answer("❌ Донат не найден. Убедись, что указал ID в комментарии.")

# 🔘 Кнопка "Премиум"
@dp.message(F.text == "👑 Премиум")
async def check_premium(message: Message):
    if is_premium(message.from_user.id):
        await message.answer("✅ У вас уже есть Премиум-доступ.")
    else:
        await message.answer(
            f"🔒 У вас пока нет доступа.\n\n"
            f"1️⃣ Сделайте донат: https://www.donationalerts.com/r/essay_bot\n"
            f"2️⃣ Укажите Telegram ID: {message.from_user.id}\n"
            f"3️⃣ Затем нажмите /check"
        )

# 📦 Список уже проверенных донатов
checked_donors = set()

# 🏁 Запуск
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    dp.run_polling(bot)
