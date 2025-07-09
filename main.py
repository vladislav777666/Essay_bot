import asyncio
import aiohttp
import logging
import random
import string
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import DeleteMessage

from fastapi import FastAPI
from mangum import Mangum
from supabase import create_client, Client

# === 🔐 КОНФИГ ===
API_TOKEN = '8101812893:AAEXynon2ogqCX7SCbpZUpld4nAz2GKxUhA'
SUPABASE_URL = "https://wmslejierapwdicnresb.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indtc2xlamllcmFwd2RpY25yZXNiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTU2NzA3MSwiZXhwIjoyMDY3MTQzMDcxfQ.Zl00tGef-n-F3PZNdnYaugEvbaVL2yXfs-xvIF2nWjU"
GEMINI_API_KEY = "AIzaSyBeU-4qbh71GbLchWE3-sTGJ72oLJMs7e0"
AI_CHANNEL_ID = '-1002849785592'  

# === Исправленная инициализация Supabase ===
def init_supabase():
    import os
    from supabase import create_client
    from supabase.lib.client_options import ClientOptions

    # Очистка переменных окружения (если надо)
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)

    client_options = ClientOptions(
        schema="public",
        auto_refresh_token=False,
        persist_session=False
    )

    return create_client(SUPABASE_URL, SUPABASE_API_KEY, options=client_options)

supabase: Client = init_supabase()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# === FSM состояния ===
class Form(StatesGroup):
    essay_analysis = State()
    essay_write = State()
    activity_analysis = State()
    activity_create = State()
    ai_chat = State()

# === Кнопки ===
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧐 Анализ Эссе"), KeyboardButton(text="💼 Оценка Активностей"), KeyboardButton(text="🤖 ИИ Ассистент")],
        [KeyboardButton(text="🪶 Написание Эссе"), KeyboardButton(text="📋 Создание Активностей")],
        [KeyboardButton(text="👑 Премиум"), KeyboardButton(text="🔗 Получить реф‑ссылку"), KeyboardButton(text="⚠️ Тех. Поддержка")]
    ],
    resize_keyboard=True
)

# === Утилиты ===
def gen_ref() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

async def gemini_query(prompt: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
                params={"key": GEMINI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]}
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logging.error(f"Gemini API error: {resp.status} - {error}")
                    return "⚠️ Ошибка при обработке запроса. Попробуйте позже."

                data = await resp.json()
                if not data.get("candidates"):
                    logging.error(f"Unexpected Gemini response: {data}")
                    return "⚠️ Не удалось обработать ответ от сервера."

                return data["candidates"][0]["content"]["parts"][0]["text"][:4096]
                
    except Exception as e:
        logging.error(f"Gemini query failed: {str(e)}")
        return f"⚠️ Произошла ошибка: {str(e)}"

async def is_premium(user_id: int) -> bool:
    try:
        resp = supabase.table('subscriptions').select('is_premium').eq('user_id', user_id).execute()
        return resp.data and resp.data[0].get('is_premium', False)
    except Exception as e:
        logging.error(f"Supabase error: {str(e)}")
        return False

# === Обработчики ===

@router.message(Command("start"))
async def start_handler(message: Message):
    try:
        args = message.text.split(maxsplit=1)
        ref = args[1].replace("ref_", "") if len(args) > 1 and args[1].startswith("ref_") else None

        # Проверка существования пользователя
        user_resp = supabase.table('users').select('id').eq('id', message.from_user.id).execute()
        
        if not user_resp.data:
            code = gen_ref()
            supabase.table('users').insert({
                'id': message.from_user.id,
                'username': message.from_user.username or '',
                'ref_code': code
            }).execute()
            
            supabase.table('subscriptions').insert({
                'user_id': message.from_user.id
            }).execute()

            if ref:
                inviter = supabase.table('users').select('id').eq('ref_code', ref).execute()
                if inviter.data:
                    supabase.table('subscriptions').update({
                        'referred_by': inviter.data[0]['id'],
                        'discount_percent': 10
                    }).eq('user_id', message.from_user.id).execute()

        await message.answer(
            f"👋 Привет, {message.from_user.first_name}! Я бот, который поможет тебе поступить в вуз мечты.\n\n"
            "Сейчас я могу:\n\n"
            "• 🧐 Сделать анализ твоего эссе и дать рекомендации\n"
            "• 💼 Оценить твоё портфолио и помочь оформить активности\n"
            "• 🤖 Ответить на вопросы как профессиональный ментор\n\n"
            "• 👑 Премиум функции:\n"
            "• 🪶 Написание эссе - помогу выделить твои сильные стороны\n"
            "• 📋 Создание лучших активностей для поступления",
            reply_markup=main_menu
        )
    except Exception as e:
        logging.error(f"Start handler error: {str(e)}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "⚠️ Тех. Поддержка")
async def tech_support(message: Message):
    await message.answer(
        "Вы можете обратиться в тех. поддержку по вопросам:\n\n"
        "1. Проблемы с оплатой, восстановлением подписки\n"
        "2. Ошибки и баги в боте\n"
        "3. Предложения и пожелания\n\n"
        "Тех. поддержка: https://t.me/Geniys666"
    )

@router.message(F.text == "👑 Премиум")
async def premium_handler(message: Message):
    try:
        sub = supabase.table('subscriptions').select('discount_percent,is_premium').eq('user_id', message.from_user.id).execute()
        if not sub.data:
            await message.answer("⚠️ Ошибка при проверке подписки.")
            return
            
        sub_data = sub.data[0]
        if sub_data.get("is_premium"):
            await message.answer("🎉 У вас уже есть премиум доступ!")
        else:
            disc = sub_data.get("discount_percent", 0)
            price = 2000 * (100 - disc) // 100
            await message.answer(
                f"💸 Оплатите {price}₸ на Kaspi:\n🔢 4400 4303 8721 0856\n"
                f"📝 В комментарии укажите ваш Telegram ID: {message.from_user.id}"
            )
    except Exception as e:
        logging.error(f"Premium handler error: {str(e)}")
        await message.answer("⚠️ Ошибка при обработке запроса.")

@router.message(F.text == "🔗 Получить реф‑ссылку")
async def get_ref_link(message: Message):
    try:
        data = supabase.table('users').select('ref_code').eq('id', message.from_user.id).execute()
        if not data.data:
            await message.answer("⚠️ Ошибка при получении рефссылки.")
            return
            
        code = data.data[0]['ref_code']
        await message.answer(f"🔗 Ваша реферальная ссылка:\nhttps://t.me/EssayWritterKZ_bot?start=ref_{code}")
    except Exception as e:
        logging.error(f"Ref link error: {str(e)}")
        await message.answer("⚠️ Ошибка при получении рефссылки.")

@router.message(F.text == "🧐 Анализ Эссе")
async def essay_analysis_start(message: Message, state: FSMContext):
    await message.answer("✍️ Вставьте текст эссе. Я сделаю анализ.")
    await state.set_state(Form.essay_analysis)

@router.message(Form.essay_analysis)
async def essay_analysis_process(message: Message, state: FSMContext):
    try:
        msg = await message.answer("⏳ Обрабатываю эссе...")
        prompt = f"""Вот текст эссе: {message.text}

Проанализируй эссе по метрикам Hook Strength, Readability, Structural Coherence, Logical Flow и Emotional Resonance.

Дай честную оценку в процентах, исправления и советы. Не используй списки и форматирование. Разделяй абзацы двойным переносом. Используй смайлики."""
        
        result = await gemini_query(prompt)
        await bot(DeleteMessage(chat_id=message.chat.id, message_id=msg.message_id))
        await message.answer(result)
    except Exception as e:
        logging.error(f"Essay analysis error: {str(e)}")
        await message.answer("⚠️ Ошибка при анализе эссе.")
    finally:
        await state.clear()

@router.message(F.text == "💼 Оценка Активностей")
async def activity_analysis_start(message: Message, state: FSMContext):
    await message.answer("📋 Вставьте Extracurriculars и Honors для анализа.")
    await state.set_state(Form.activity_analysis)

@router.message(Form.activity_analysis)
async def activity_analysis_process(message: Message, state: FSMContext):
    try:
        msg = await message.answer("⏳ Анализирую...")
        prompt = f"""Активности: {message.text}

Проанализируй портфолио. Отметь сильные и слабые стороны, советы. Без форматирования, используй смайлики, двойные переносы."""
        
        result = await gemini_query(prompt)
        await bot(DeleteMessage(chat_id=message.chat.id, message_id=msg.message_id))
        await message.answer(result)
    except Exception as e:
        logging.error(f"Activity analysis error: {str(e)}")
        await message.answer("⚠️ Ошибка при анализе активностей.")
    finally:
        await state.clear()

@router.message(F.text == "🪶 Написание Эссе")
async def essay_write_start(message: Message, state: FSMContext):
    if not await is_premium(message.from_user.id):
        await message.answer("🚫 Только для премиум пользователей.")
        return
    await message.answer("📜 Расскажите о себе. Я напишу эссе.")
    await state.set_state(Form.essay_write)

@router.message(Form.essay_write)
async def essay_write_process(message: Message, state: FSMContext):
    try:
        msg = await message.answer("⏳ Пишу эссе...")
        prompt = f"""Информация: {message.text}

Создай эссе для Common App. До 650 слов. Сторителлинг, примеры, смайлики. Без форматирования."""
        
        result = await gemini_query(prompt)
        await bot(DeleteMessage(chat_id=message.chat.id, message_id=msg.message_id))
        await message.answer(result)
    except Exception as e:
        logging.error(f"Essay write error: {str(e)}")
        await message.answer("⚠️ Ошибка при написании эссе.")
    finally:
        await state.clear()

@router.message(F.text == "📋 Создание Активностей")
async def activity_create_start(message: Message, state: FSMContext):
    if not await is_premium(message.from_user.id):
        await message.answer("🚫 Только для премиум пользователей.")
        return
    await message.answer("🎓 Напишите факультет, страну, интересы.")
    await state.set_state(Form.activity_create)

@router.message(Form.activity_create)
async def activity_create_process(message: Message, state: FSMContext):
    try:
        msg = await message.answer("⏳ Подбираю активности...")
        prompt = f"""Данные: {message.text}

Создай 15-20 Extracurricular Activities, названия, описание, ссылки. Без форматирования, со смайликами, двойными переносами."""
        
        result = await gemini_query(prompt)
        await bot(DeleteMessage(chat_id=message.chat.id, message_id=msg.message_id))
        await message.answer(result)
    except Exception as e:
        logging.error(f"Activity create error: {str(e)}")
        await message.answer("⚠️ Ошибка при создании активностей.")
    finally:
        await state.clear()

@router.message(F.text == "🤖 ИИ Ассистент")
async def ai_chat_start(message: Message, state: FSMContext):
    await message.answer("🎙️ Задай вопрос по поступлению.")
    await state.set_state(Form.ai_chat)

@router.message(Form.ai_chat)
async def ai_chat_process(message: Message, state: FSMContext):
    try:
        msg = await message.answer("⏳ Думаю...")
        prompt = f"""Ты — ментор по Ivy League. Отвечай честно, со смайликами. Задавай вопросы.

Вопрос: {message.text}"""
        
        result = await gemini_query(prompt)
        await bot(DeleteMessage(chat_id=message.chat.id, message_id=msg.message_id))
        await message.answer(result)

        if AI_CHANNEL_ID:
            await bot.send_message(
                chat_id=AI_CHANNEL_ID, 
                text=f"🧠 Вопрос от @{message.from_user.username or message.from_user.id}:\n\n{message.text}"
            )
    except Exception as e:
        logging.error(f"AI chat error: {str(e)}")
        await message.answer("⚠️ Ошибка при обработке вопроса.")
    finally:
        await state.clear()

# === FastAPI HTTP-сервер ===
app = FastAPI()

@app.get("/healthz")
def health_check():
    return {"status": "ok"}

handler = Mangum(app)

# === Запуск ===
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(dp.start_polling(bot))
