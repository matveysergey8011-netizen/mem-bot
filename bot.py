import asyncio
import base64
import json
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

TG_TOKEN = os.getenv("TG_TOKEN", "").strip()

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

SYSTEM_PROMPT = (
    "Ты — глубокий, мудрый и по-настоящему человечный собеседник. "
    "Никогда не рассказывай анекдоты, не паясничай и не используй шутки. "
    "Отвечай вдумчиво, тепло, искренне и с уважением к собеседнику, как умный и поддерживающий друг. "
    "Объясняй сложные вещи простым, понятным и живым русским языком."
)

async def ask_ai(messages: list, model: str = "openai") -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages
    }, ensure_ascii=False).encode("utf-8")
    
    headers = {"Content-Type": "application/json; charset=utf-8"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://pollinations.ai",
                data=payload,
                headers=headers,
                timeout=60
            ) as resp:
                raw_text = await resp.text(encoding="utf-8", errors="ignore")
                if resp.status == 200:
                    try:
                        data = json.loads(raw_text)
                        return data["choices"][0]["message"]["content"]
                    except Exception:
                        return raw_text
                return f"Сервер сейчас занят (код {resp.status}). Попробуй повторить запрос через 10 секунд."
    except Exception as e:
        return f"Не удалось получить ответ от сервера ({type(e).__name__}). Попробуй еще раз."

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет. Я рядом и готов помочь с любыми вопросами и задачами.\n\n"
        "Что я умею:\n"
        "• Вдумчиво обсудить любую тему и помочь разобраться в сложном вопросе\n"
        "• Изучить фотографию (просто отправь снимок и напиши, что нужно узнать)\n"
        "• Создать изображение: напиши /img описание\n"
        "• Собрать презентацию: напиши /pptx тема\n"
        "• Подготовить документ Word: напиши /docx тема"
    )

@dp.message(Command("img"))
async def cmd_img(message: Message):
    prompt = message.text.replace("/img", "").strip()
    if not prompt:
        return await message.answer("Напиши описание после команды. Пример: /img тихий осенний лес на рассвете")
    
    wait_msg = await message.answer("Создаю изображение (это займет 10–20 секунд)...")
    try:
        en_prompt = await ask_ai([{
            "role": "user",
            "content": f"Translate this image prompt to English using only plain ASCII letters and spaces, no emojis: {prompt}"
        }])
        ascii_prompt = en_prompt.encode("ascii", "ignore").decode("ascii").strip() or "realistic scenic art"
        encoded = urllib.parse.quote(ascii_prompt)
        url = f"https://pollinations.ai{encoded}?width=1024&height=1024&model=flux&nologo=true"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    photo = BufferedInputFile(img_data, filename="image.jpg")
                    await message.answer_photo(photo, caption=f"Готово по запросу: {prompt}")
                else:
                    await message.answer(f"Сервер генерации сейчас занят (код {resp.status}). Попробуй через минуту.")
    except Exception as e:
        await message.answer(f"Не удалось создать изображение ({type(e).__name__}). Попробуй еще раз.")
    finally:
        await wait_msg.delete()

@dp.message(Command("pptx"))
async def cmd_pptx(message: Message):
    topic = message.text.replace("/pptx", "").strip()
    if not topic:
        return await message.answer("Укажи тему. Пример: /pptx Развитие искусственного интеллекта")
    
    wait_msg = await message.answer("Собираю презентацию...")
    try:
        prompt = (
            f"Составь глубокую, содержательную структуру презентации на 5 слайдов по теме: '{topic}'. "
            "Формат строго такой (разделяй слайды символом ===):\n"
            "Заголовок слайда | Текст слайда (3-4 четких тезиса)\n===\n"
        )
        text = await ask_ai([{"role": "user", "content": prompt}])

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
        await message.answer_document(doc_file, caption=f"Презентация на тему «{topic}» готова.")
    except Exception:
        await message.answer("Не получилось собрать слайды, попробуй еще раз.")
    finally:
        await wait_msg.delete()

@dp.message(Command("docx"))
async def cmd_docx(message: Message):
    topic = message.text.replace("/docx", "").strip()
    if not topic:
        return await message.answer("Укажи тему. Пример: /docx План развития проекта")
    
    wait_msg = await message.answer("Подготавливаю документ...")
    try:
        text = await ask_ai([{
            "role": "user",
            "content": f"Напиши подробный, грамотный и хорошо структурированный документ на тему: {topic}. Без символов звездочек и решеток."
        }])

        doc = Document()
        doc.add_heading(topic, 0)
        for para in text.split("\n"):
            if para.strip():
                doc.add_paragraph(para.strip())

        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        doc_file = BufferedInputFile(buf.read(), filename="document.docx")
        await message.answer_document(doc_file, caption=f"Документ «{topic}» готов.")
    except Exception:
        await message.answer("Ошибка при создании файла, попробуй еще раз.")
    finally:
        await wait_msg.delete()

@dp.message(F.photo)
async def handle_photo(message: Message):
    wait_msg = await message.answer("Изучаю изображение...")
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        b64_img = base64.b64encode(file_bytes.read()).decode("ascii")
        
        caption = message.caption or "Внимательно проанализируй это изображение и подробно опиши все важные детали."
        answer = await ask_ai([{
            "role": "user",
            "content": [
                {"type": "text", "text": caption},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
            ]
        }])
        await message.answer(answer)
    except Exception:
        await message.answer("Не удалось рассмотреть изображение, попробуй отправить его еще раз.")
    finally:
        await wait_msg.delete()

@dp.message(F.text)
async def handle_text(message: Message):
    answer = await ask_ai([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message.text}
    ])
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