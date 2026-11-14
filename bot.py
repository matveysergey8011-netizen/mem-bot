import asyncio
import base64
import os
import urllib.parse
import aiohttp
from aiohttp import web
from io import BytesIO
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from pptx import Presentation
from docx import Document

TG_TOKEN = os.getenv("TG_TOKEN")

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

SYSTEM_PROMPT = (
    "Ты — сверхинтеллектуальный ИИ-помощник и мастер юмора в Telegram. "
    "Отвечай глубоко, точно и остроумно на русском языке. Если просят придумать мем, делай его смешным и актуальным."
)

# Безопасное кодирование текста (убирает сломанные символы и эмодзи)
def safe_encode(text: str) -> str:
    clean_text = text.encode("utf-8", "ignore").decode("utf-8")
    return urllib.parse.quote(clean_text, safe="")

async def ask_ai(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    full_prompt = f"{system}\n\nЗапрос пользователя: {prompt}"
    encoded = safe_encode(full_prompt)
    url = f"https://pollinations.ai{encoded}?model=openai"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=45) as resp:
                if resp.status == 200:
                    return await resp.text()
                return f"Сервер ответил кодом {resp.status}. Попробуй еще раз через 10 секунд."
    except Exception as e:
        return f"Не успел дождаться ответа от сервера: {type(e).__name__}"

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я твой личный ИИ-комбайн. Что я умею:\n"
        "🧠 Отвечать на любые сложные вопросы и придумывать мемы\n"
        "👁 Анализировать фото (просто отправь мне картинку с вопросом)\n"
        "🎨 Рисовать картинки: напиши /img описание\n"
        "📊 Делать презентации: напиши /pptx тема\n"
        "📄 Делать документы Word: напиши /docx тема"
    )

@dp.message(Command("img"))
async def cmd_img(message: Message):
    prompt = message.text.replace("/img", "").strip()
    if not prompt:
        return await message.answer("Напиши запрос после команды. Пример: /img кот программист в киберпанке")
    
    wait_msg = await message.answer("🎨 Рисую картинку (10–20 секунд)...")
    try:
        encoded = safe_encode(prompt)
        url = f"https://pollinations.ai{encoded}?width=1024&height=1024&model=flux&nologo=true"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=50) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    photo = BufferedInputFile(img_data, filename="art.jpg")
                    await message.answer_photo(photo, caption=f"✨ Готово по запросу: {prompt}")
                else:
                    await message.answer(f"Сервер рисования занят (код {resp.status}). Попробуй через минуту.")
    except Exception as e:
        await message.answer(f"Ошибка при рисовании: {type(e).__name__}. Попробуй еще раз!")
    finally:
        await wait_msg.delete()

@dp.message(Command("pptx"))
async def cmd_pptx(message: Message):
    topic = message.text.replace("/pptx", "").strip()
    if not topic:
        return await message.answer("Укажи тему. Пример: /pptx История мемов")
    
    wait_msg = await message.answer("📊 Собираю презентацию...")
    try:
        prompt = (
            f"Составь структуру презентации на 5 слайдов по теме: '{topic}'. "
            "Формат строго такой (разделяй слайды символом ===):\n"
            "Заголовок слайда | Текст слайда (3-4 коротких пункта)\n===\n"
        )
        text = await ask_ai(prompt, system="Ты генератор презентаций.")

        prs = Presentation()
        for slide_raw in text.split("==="):
            if "|" in slide_raw:
                title, body = slide_raw.split("|", 1)
                slide = prs.slides.add_slide(prs.slide_layouts[1])
                slide.shapes.title.text = title.strip()
                slide.placeholders[1].text = body.strip()

        buf = BytesIO()
        prs.save(buf)
        buf.seek(0)
        doc_file = BufferedInputFile(buf.read(), filename="presentation.pptx")
        await message.answer_document(doc_file, caption=f"📊 Презентация на тему «{topic}» готова!")
    except Exception:
        await message.answer("Не получилось собрать слайды, попробуй еще раз.")
    finally:
        await wait_msg.delete()

@dp.message(Command("docx"))
async def cmd_docx(message: Message):
    topic = message.text.replace("/docx", "").strip()
    if not topic:
        return await message.answer("Укажи тему. Пример: /docx План запуска стартапа")
    
    wait_msg = await message.answer("📄 Пишу документ...")
    try:
        text = await ask_ai(
            f"Напиши подробный, хорошо структурированный документ на тему: {topic}. Без markdown-звездочек.",
            system="Ты профессиональный автор документов."
        )

        doc = Document()
        doc.add_heading(topic, 0)
        for para in text.split("\n"):
            if para.strip():
                doc.add_paragraph(para.strip())

        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        doc_file = BufferedInputFile(buf.read(), filename="document.docx")
        await message.answer_document(doc_file, caption=f"📄 Документ «{topic}» готов!")
    except Exception:
        await message.answer("Ошибка при создании файла, попробуй еще раз.")
    finally:
        await wait_msg.delete()

@dp.message(F.photo)
async def handle_photo(message: Message):
    wait_msg = await message.answer("👁 Изучаю изображение...")
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        b64_img = base64.b64encode(file_bytes.read()).decode("utf-8")
        
        caption = message.caption or "Подробно опиши, что на этом фото, и придумай смешную подпись для мема."
        payload = {
            "model": "openai",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": caption},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                ]
            }]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post("https://pollinations.aiopenai", json=payload, timeout=45) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    await message.answer(data["choices"][0]["message"]["content"])
                else:
                    await message.answer(f"Сервер анализа фото вернул код {resp.status}.")
    except Exception:
        await message.answer("Не удалось изучить картинку, попробуй отправить её еще раз.")
    finally:
        await wait_msg.delete()

@dp.message(F.text)
async def handle_text(message: Message):
    answer = await ask_ai(message.text)
    await message.answer(answer)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", lambda request: web.Response(text="Bot is running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())