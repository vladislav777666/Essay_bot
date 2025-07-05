import asyncio
import aiohttp
import logging
from aiohttp import web

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# === 🔐 КОНФИГ ===
API_TOKEN = '8101812893:AAEXynon2ogqCX7SCbpZUpld4nAz2GKxUhA'
SUPABASE_URL = "https://wmslejierapwdicnresb.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
GEMINI_API_KEY = "AIzaSyBeU-4qbh71GbLchWE3-sTGJ72oLJMs7e0"

# === 📚 ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

headers = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json"
}

# === FSM состояния ===
class Form(StatesGroup):
    essay_analysis = State()
    essay_write = State()
    activity_analysis = State()
    activity_create = State()

# === Кнопки ===
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧐 Анализ Эссе"), KeyboardButton(text="💼 Оценка Активностей")],
        [KeyboardButton(text="🪶 Написание Эссе"), KeyboardButton(text="📋 Создание Активностей")],
        [KeyboardButton(text="👑 Премиум"), KeyboardButton(text="⚠️ Тех. Поддержка")]
    ],
    resize_keyboard=True
)

# === Подключение Gemini ===
async def gemini_query(prompt: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
            params={"key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]}
        ) as resp:
            data = await resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

# === Обработчики ===
@router.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("👋 Привет! Я помогу тебе поступить в вуз мечты.", reply_markup=main_menu)

@router.message(F.text == "⚠️ Тех. Поддержка")
async def tech_support(message: Message):
    await message.answer("📞 Тех. поддержка: https://t.me/Geniys666")

@router.message(F.text == "👑 Премиум")
async def premium_handler(message: Message):
    await message.answer(f"💸 Оплатите 2000₸ на Kaspi:\n🔢 4400 4303 8721 0856\n📝 Комментарий: {message.from_user.id}")

@router.message(F.text == "🧐 Анализ Эссе")
async def essay_analysis_start(message: Message, state: FSMContext):
    await message.answer("✍️ Отправь тип и текст эссе.")
    await state.set_state(Form.essay_analysis)

@router.message(Form.essay_analysis)
async def essay_analysis_process(message: Message, state: FSMContext):
    await state.clear()
    prompt = f"""
Проанализируй моё эссе. Не используй вступления и форматирования.

Эссе:
{message.text}
"""
    result = await gemini_query(prompt)
    await message.answer(result[:4096])

@router.message(F.text == "🪶 Написание Эссе")
async def essay_write_start(message: Message, state: FSMContext):
    await message.answer("📜 Расскажи о себе: история, цели, увлечения")
    await state.set_state(Form.essay_write)

@router.message(Form.essay_write)
async def essay_write_process(message: Message, state: FSMContext):
    await state.clear()
    prompt = f"""
Вот информация обо мне: {message.text}

Создай лучшее эссе для Common App.
"""
    result = await gemini_query(prompt)
    await message.answer(result[:4096])

@router.message(F.text == "💼 Оценка Активностей")
async def activity_analysis_start(message: Message, state: FSMContext):
    await message.answer("📋 Отправь Extracurriculars и Honors")
    await state.set_state(Form.activity_analysis)

@router.message(Form.activity_analysis)
async def activity_analysis_process(message: Message, state: FSMContext):
    await state.clear()
    prompt = f"""
Проанализируй активности. Дай советы.

{message.text}
"""
    result = await gemini_query(prompt)
    await message.answer(result[:4096])

@router.message(F.text == "📋 Создание Активностей")
async def activity_create_start(message: Message, state: FSMContext):
    await message.answer("📝 Напиши: класс, год выпуска, факультет, страна и интересы")
    await state.set_state(Form.activity_create)

@router.message(Form.activity_create)
async def activity_create_process(message: Message, state: FSMContext):
    await state.clear()
    prompt = f"""
Создай 10 Extracurricular Activities.

Инфо:
{message.text}
"""
    result = await gemini_query(prompt)
    await message.answer(result[:4096])

# === HTTP-сервер ===
async def handle_healthz(request):
    return web.Response(text="OK")

async def start_web_app():
    app = web.Application()
    app.router.add_get("/healthz", handle_healthz)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("🌐 HTTP server started on http://0.0.0.0:8080")

# === ГЛАВНЫЙ ЗАПУСК ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        await asyncio.gather(
            dp.start_polling(bot),
            start_web_app()
        )

    asyncio.run(main())
