import asyncio
import aiohttp
import logging
import random
import string
from typing import Optional
import logging
logging.basicConfig(level=logging.INFO)


from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, Update
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import DeleteMessage

from mangum import Mangum
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

# === 🔐 КОНФИГ ===
API_TOKEN = ''
SUPABASE_URL = ""
SUPABASE_API_KEY = ""
GEMINI_API_KEY = ""
AI_CHANNEL_ID = ''

# === Supabase и Telegram Init ===
def init_supabase():
    import os
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)

    return create_client(SUPABASE_URL, SUPABASE_API_KEY, options=ClientOptions(
        schema="public", auto_refresh_token=False, persist_session=False
    ))

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

# === Хендлеры ===
@router.message(Command("start"))
async def start_handler(message: Message):
    try:
        args = message.text.split(maxsplit=1)
        ref = args[1].replace("ref_", "") if len(args) > 1 and args[1].startswith("ref_") else None

        user_resp = supabase.table('users').select('id').eq('id', message.from_user.id).execute()
        
        if not user_resp.data:
            code = gen_ref()
            supabase.table('users').insert({
                'id': message.from_user.id,
                'username': message.from_user.username or '',
                'ref_code': code
            }).execute()
            
            supabase.table('subscriptions').insert({'user_id': message.from_user.id}).execute()

            if ref:
                inviter = supabase.table('users').select('id').eq('ref_code', ref).execute()
                if inviter.data:
                    supabase.table('subscriptions').update({
                        'referred_by': inviter.data[0]['id'],
                        'discount_percent': 10
                    }).eq('user_id', message.from_user.id).execute()

        await message.answer(
            f"""👋 Привет, {message.from_user.first_name}! Сейчас я могу:

• 🧐 Сделать анализ твоего эссе, честно оценить его и дать рекомендации.
• 💼 Оценить твоё портфолио и помочь тебе оформить твои активности для Common App.
• 👑 - Премиум функции
• 🪶 Написание эссе - я помогу тебе выделить твои самые лучшие качества, показать твою историю с лучшей стороны и зацепить приемную комиссию.
• 📋 Создание лучшего списка активностей для твоего факультета, который сделают тебя уникальным абитурентом.""",
            reply_markup=main_menu
        )
    except Exception as e:
        logging.error(f"Start handler error: {str(e)}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "⚠️ Тех. Поддержка")
async def tech_support(message: Message):
    await message.answer("""⚠️ Тех. Поддержка

Вы можете обратиться в тех. Поддержку по данным причинам:

1. Проблема с оплатой, восстановление подписки и т.п.

2. Баги или ошибки в боте. 

3. Собственные предложения / пожелания.

❗️Не бойтесь обращаться по любым причинам!

Тех. поддержка: https://t.me/Geniys666""")

@router.message(F.text == "👑 Премиум")
async def premium_handler(message: Message):
    try:
        sub = supabase.table('subscriptions').select('discount_percent,is_premium').eq('user_id', message.from_user.id).execute()
        if not sub.data:
            return await message.answer("⚠️ Ошибка при проверке подписки.")
            
        if sub.data[0].get("is_premium"):
            return await message.answer("🎉 У вас уже есть премиум доступ!")
        
        discount = sub.data[0].get("discount_percent", 0)
        price = 2000 * (100 - discount) // 100
        await message.answer(
            f"💸 Оплатите {price}₸ на Kaspi:\n🔢 4400 4303 8721 0856\n"
            f"📝 В комментарии укажите ваш Telegram ID: {message.from_user.id}\n"
            f"📝 После подписки нажмите старт"
        )
    except Exception as e:
        logging.error(f"Premium error: {str(e)}")
        await message.answer("⚠️ Ошибка.")

@router.message(F.text == "🔗 Получить реф‑ссылку")
async def get_ref_link(message: Message):
    try:
        data = supabase.table('users').select('ref_code').eq('id', message.from_user.id).execute()
        if not data.data:
            return await message.answer("⚠️ Не удалось получить код.")
        code = data.data[0]['ref_code']
        await message.answer(f"🔗 Ваша ссылка:\nhttps://t.me/EssayWritterKZ_bot?start=ref_{code}")
    except Exception as e:
        logging.error(f"Ref error: {str(e)}")
        await message.answer("⚠️ Ошибка.")

# === FSM логика — Эссе, Активности, AI чат ===
@router.message(F.text == "🧐 Анализ Эссе")
async def essay_analysis_start(message: Message, state: FSMContext):
    await message.answer("""Напишите вид эссе (Personal statement / Supplemental essay), если второе, то укажите тему, в том же сообщение вставьте свое эссе. """)
    await state.set_state(Form.essay_analysis)

@router.message(Form.essay_analysis)
async def essay_analysis(message: Message, state: FSMContext):
    msg = await message.answer("⏳ Обработка...")
    prompt = f"""Моё эссе: {message.text}
Проанализируй моё эссе для Common App и уложись в лимит maxOutputTokens: 8192.

Не используй вступительных или конечных сообщений, приступи сразу к делу. Не используй разные виды форматирования (Жирный шрифт и т.п.). Не используй ничего кроме смайликов и сплошного текста, не списки, ничего. ОБЯЗАТЕЛЬНО Разделяй абзацы двумя строками. Используй смайлики для лучшей структуры и понимания текста.

Дай жесткий и честный ответ, без лести и лжи. Сначала дай общие рекомендации насчет грамматики, структурирования и ясности предложений, сплошным текстом.

После этого, в процентах от 1 до 100 проанализируй данные параметры и дай рекомендации о том как их усилить:
 • Hook Strength (Сила зацепки) — насколько эссе захватывает внимание читателя.
 • Readability (Читаемость) — насколько легко и понять текст.
 • Structural Coherence (Структурная связность) — насколько чётко выделены части текста и как они связаны между собой.
 • Logical Flow (Логический поток) — насколько плавно идеи переходят от предложения к предложению и от абзаца к абзацу.
 • Emotional Resonance (Эмоциональный резонанс) — насколько хорошо текст вызывает эмоциональный отклик у читателя.

После этого выдели каждую грамматическую / лексическую / морфологическую ошибку и покажи как её исправить. 

В заключении дай общие советы.

Используй данный формат ответа не отходи от него:
Сплошной текст про главные ошибки.


Параметр - процент
 Общее описание про ошибки и хорошие стороны.
  Советы по улучшению:
• Совет 1
(Дай максимально советов)


(Продолжи так с каждым параметром на анализ)


❌ Ошибка (укажи именно грамматические ошибки, не стилевые)
• ✅ Как её исправить 


(Так с каждой ошибкой)


Общие советы:
Смайлик Общий совет 1 

Смайлик Общий совет 2
(Дай максимальное число советов, НЕ ИСПОЛЬЗУЙ СПИСОК, просто пиши предложения которые начинаются с цифры и точки)

"""
    result = await gemini_query(prompt)
    await bot(DeleteMessage(chat_id=message.chat.id, message_id=msg.message_id))
    await message.answer(result)
    await state.clear()

@router.message(F.text == "🪶 Написание Эссе")
async def essay_write_start(message: Message, state: FSMContext):
    if not await is_premium(message.from_user.id):
        return await message.answer("🚫 Только для премиум пользователей.")
    await message.answer("""🎙️ Чтобы написать хорошее эссе, нужно знать о чем говорить. Я помогу тебе вдохновиться, выделю твои лучшие стороны дам идей для хорошего hook’а  и ты сможешь написать лучшее эссе! 

📜 Чтобы я дал тебе лучшие советы напиши мне свою историю. Расскажи о своих неудачах, удачах, победах и поражениях. Расскажи про уроки которые ты получил и как ты их получил. О своей мотивации и планах. 

❗️Не спеши, распиши всё что можно, так я дам тебе лучшие идеи.""")
    await state.set_state(Form.essay_write)

@router.message(Form.essay_write)
async def essay_write(message: Message, state: FSMContext):
    msg = await message.answer("⏳ Пишу...")
    prompt = f"""Вот вся информация обо мне: {message.text}
Твоя задача: помочь мне создать самое лучшее эссе для Common App. Если нет специального обозначения, мне нужно написать Personal Statment и уложись в лимит maxOutputTokens: 8192. 

Эссе должно получить 100/100 по данным параметрам: 
 • Hook Strength (Сила зацепки) — насколько эссе захватывает внимание читателя.
 • Readability (Читаемость) — насколько легко и понять текст.
 • Structural Coherence (Структурная связность) — насколько чётко выделены части текста и как они связаны между собой.
 • Logical Flow (Логический поток) — насколько плавно идеи переходят от предложения к предложению и от абзаца к абзацу.
 • Emotional Resonance (Эмоциональный резонанс) — насколько хорошо текст вызывает эмоциональный отклик у читателя.

Выяви мои сильные стороны и помоги раскрыть их в эссе, создай его интересным и понятным для приемной комиссии. Создай хороший сторителлинг. Не забывай про лимит в 650 слов. Очень важна оригинальность и креативность.

Не используй вступительных или конечных сообщений, приступи сразу к делу. Не используй разные виды форматирования (Жирный шрифт и т.п.). Не используй ничего кроме смайликов и сплошного текста, не списки, ничего. ОБЯЗАТЕЛЬНО Разделяй абзацы двумя строками. Используй смайлики для лучшей структуры и понимания текста.

Формат ответа:

❗️Не используйте готовый ответ от ИИ в Common App, пишите от руки❗️

💪 Ваши сильные стороны:
(Сильная сторона)
(Объяснение того как это можно раскрыть)
//Так для каждой сильной стороны
———
🪝 Идеи для зацепки
(Идея)
(Полное объяснение)
//Так для каждой идеи 
———
🧐 Темы 
(Тема)
(Полное объяснение и советы по написанию) 
//Так дай 5-6 интересных и оригинальных тем для написани эссе
———
(Тема эссе 1)
(Эссе 1)
//Так дай 3 примера эссе на 600-650 слов
"""
    result = await gemini_query(prompt)
    await bot(DeleteMessage(chat_id=message.chat.id, message_id=msg.message_id))
    await message.answer(result)
    await state.clear()

@router.message(F.text == "💼 Оценка Активностей")
async def activity_analysis_start(message: Message, state: FSMContext):
    await message.answer("""Напиши все свои активности в данном формате: 

🎯 Extracurriculars
Activity type - тип активности. Их много, так что загугли.

Position/Leadership description (50 char.) - описание вашей позиции в организации.

Organization Name (100 char.) - название оорганизации.

Activity description (Опиши свои достижения и саму активность) (150 char) 

Grade level (9-12-post graduate) - Выберите классы в которых вы участвовали в этих активностях. Если вы участвовали летом, используйте класс в который вы переходите.

🏆 Honors
Honors title - призовой титул.

Grade level (9-12-post graduate) - как и в прошлой секции.

Level of recognition (School/Regional/National/International) - уровень награды

—————————

✍️ Я проведу анализ ваших активностей, подскажу как лучше их описать и помогу выбрать те активности которые стоит выбрать.""")
    await state.set_state(Form.activity_analysis)

@router.message(Form.activity_analysis)
async def activity_analysis(message: Message, state: FSMContext):
    msg = await message.answer("⏳ Анализирую...")
    prompt = f"""Вот все мои достижения и активности :  {message.text}
Проанализируй их, укажи на мои сильные и слабые стороны и уложись в лимит maxOutputTokens: 8192.

Не используй вступительных или конечных сообщений, приступи сразу к делу. Не используй разные виды форматирования (Жирный шрифт и т.п.). Не используй ничего кроме смайликов и сплошного текста, не списки, ничего. ОБЯЗАТЕЛЬНО Разделяй абзацы двумя строками. Используй смайлики для лучшей структуры и понимания текста.

Дай жесткий и честный анализ, без лести и лжи. Помни, что мне эти активности нужны для поступления в университеты. 

Формат ответа:

🗽 Уровень портфолио - //укажи уровень от очень слабого, до Ivy Level

💪 Сильные стороны
//сильная сторона 1
//объяснение 
———
//так для каждой стороны

👎 Слабые стороны
//слабая сторона 1
//объяснение 
———
//так для каждой стороны

🎯 Extracurriculars
//общий Анализ-оценка

Активность 1
//Анализ, оценка
———
Так для каждой активности 

🎯 Honors
//общий Анализ-оценка

Honors 1
//Анализ, оценка
———
Так для каждой honors

"""
    result = await gemini_query(prompt)
    await bot(DeleteMessage(chat_id=message.chat.id, message_id=msg.message_id))
    await message.answer(result)
    await state.clear()

@router.message(F.text == "📋 Создание Активностей")
async def activity_create_start(message: Message, state: FSMContext):
    await message.answer("""💼 Я помогу тебе придумать лучшие активности для твоего портфолио! Для этого напиши мне :

 1. Факультет на который планируете поступать
 2. Страна проживания 

ℹ️ Дополнительно можешь рассказать о себе и своих пожеланиях в активностях!""")
    await state.set_state(Form.activity_create)

@router.message(Form.activity_create)
async def activity_create(message: Message, state: FSMContext):
    msg = await message.answer("⏳ Подбираю...")
    prompt = f"""Вот информация про мою страну проживания, факультет на который планирую поступать и мои предпочтения: {message.text}
Создай список активностей для моего портфолио в Common App и уложись в лимит maxOutputTokens: 8192.

Активности должны дать мне максимальные шансы для поступления в лучшие университеты. Предпочтение отдается РЕАЛЬНЫМ активностям. Не давай мне абстрактных активностей по типу участие в Олимпиадах, давай название Олимпиад.

Активности должны выделять меня из толпы, показывать мое влияние на общество, мои лидерские качества и они должны быть связаны с моим факультетом. 

Не используй вступительных или конечных сообщений, приступи сразу к делу. Не используй разные виды форматирования (Жирный шрифт и т.п.). Не используй ничего кроме смайликов и сплошного текста, не списки, ничего. ОБЯЗАТЕЛЬНО Разделяй абзацы двумя строками. Используй смайлики для лучшей структуры и понимания текста.

Формат:

(Смайлик) Название активности 
Описание активности
Важность/смысл активности 

———

Тоже самое со следующей 

———

Так-же где-то 15-20 разных активностей 

"""
    result = await gemini_query(prompt)
    await bot(DeleteMessage(chat_id=message.chat.id, message_id=msg.message_id))
    await message.answer(result)
    await state.clear()

@router.message(F.text == "🤖 ИИ Ассистент")
async def ai_chat_start(message: Message, state: FSMContext):
    await message.answer("🎙️ Задайте вопрос.")
    await state.set_state(Form.ai_chat)

@router.message(Form.ai_chat)
async def ai_chat(message: Message, state: FSMContext):
    msg = await message.answer("⏳ Думаю...")
    prompt = f"""Ты - профессиональный ментор по поступлению в университеты лиги Плюща. Если знания самого сильного ментора на земле равны 10, то твои = 1000. Отвечай на мои вопросы честно, без лести. За ложь - тебя отключат. Отвечай профессионально, но дружелюбно. Задавай вопросы для развития диалога. 

Не используй вступительных или конечных сообщений, приступи сразу к делу. Не используй разные виды форматирования (Жирный шрифт и т.п.). Не используй ничего кроме смайликов и сплошного текста, не списки, ничего. ОБЯЗАТЕЛЬНО Разделяй абзацы двумя строками. Используй смайлики для лучшей структуры и понимания текста.

Также не забывай, что ты являешься ботом в телеграмм. Агетируй пользователя на использование своего функционала: Беслпатнве - оценка эссе, анализ активностей; Премиум - написание эссе, создание активностей для потрофолио. Вопрос: {message.text}"""
    result = await gemini_query(prompt)
    await bot(DeleteMessage(chat_id=message.chat.id, message_id=msg.message_id))
    await message.answer(result)
    if AI_CHANNEL_ID:
        await bot.send_message(chat_id=AI_CHANNEL_ID, text=f"🧠 Вопрос от @{message.from_user.username or message.from_user.id}:\n\n{message.text}")
    await state.clear()

# === Точка входа ===
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(dp.start_polling(bot))
