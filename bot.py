"""
bot.py — Telegram бот для генерации видео через API-агрегатор.
Команды: /start, /help, /models, /generate, /status
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from config import VIDEO_MODELS, DEFAULT_MODEL
from request import create_video_task, wait_for_completion

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Состояния диалога
(
    STATE_CHOOSE_MODEL,
    STATE_CHOOSE_DURATION,
    STATE_ENTER_PROMPT,
    STATE_WAIT_IMAGE,
) = range(4)

# Временное хранилище сессий пользователей (in-memory)
user_sessions: dict = {}


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

def model_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора модели."""
    buttons = []
    for key, cfg in VIDEO_MODELS.items():
        cost_3sec = cfg["price_per_sec"] * 3
        label = f"{cfg['name']} (~${cost_3sec:.3f}/3сек)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"model:{key}")])
    return InlineKeyboardMarkup(buttons)


def duration_keyboard(model_key: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора длительности для модели."""
    cfg = VIDEO_MODELS[model_key]
    buttons = []
    row = []
    for d in cfg["durations"]:
        cost = cfg["price_per_sec"] * d
        row.append(InlineKeyboardButton(f"{d}с (~{cost:.0f}₽)", callback_data=f"dur:{d}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def format_models_text() -> str:
    lines = ["📊 *Доступные модели и цены:*\n"]
    for key, cfg in VIDEO_MODELS.items():
        cost_3 = cfg["price_per_sec"] * 3
        cost_5 = cfg["price_per_sec"] * 5
        i2v = "✅" if cfg["supports_i2v"] else "❌"
        lines.append(
            f"*{cfg['name']}*\n"
            f"  💰 3сек: ~${cost_3:.3f} | 5сек: ~${cost_5:.3f}\n"
            f"  ⏱ Длительности: {', '.join(str(d) for d in cfg['durations'])} сек\n"
            f"  🖼 Image-to-Video: {i2v}\n"
            f"  📝 {cfg['note']}\n"
        )
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────
# Handlers
# ────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 *Video Generator Bot*\n\n"
        "Генерирую короткие видео через AI-агрегатор.\n\n"
        "Команды:\n"
        "/generate — создать видео\n"
        "/models — список моделей и цен\n"
        "/help — справка"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Справка*\n\n"
        "1. Нажмите /generate\n"
        "2. Выберите модель (LTX Fast — дешевле всего)\n"
        "3. Выберите длительность (2-3 сек = дешевле)\n"
        "4. Введите текстовый промпт или отправьте фото\n"
        "5. Ждите результат (обычно 30-120 сек)\n\n"
        "💡 *Совет:* для 2-3 сек роликов "
        "Sora 2 — самая дешёвая: 27 ₽/сек."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_models_text(),
        parse_mode="Markdown"
    )


async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions[user_id] = {}
    await update.message.reply_text(
        "🎬 *Выберите модель:*\n\n"
        "_Sora 2 — самая дешёвая: 27 ₽/сек._",
        reply_markup=model_keyboard(),
        parse_mode="Markdown",
    )
    return STATE_CHOOSE_MODEL


async def cb_choose_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    model_key = query.data.split(":")[1]
    user_id = update.effective_user.id
    user_sessions[user_id]["model"] = model_key

    cfg = VIDEO_MODELS[model_key]
    await query.edit_message_text(
        f"✅ Модель: *{cfg['name']}*\n\n"
        f"⏱ Выберите длительность:\n"
        f"_(чем короче — тем дешевле)_",
        reply_markup=duration_keyboard(model_key),
        parse_mode="Markdown",
    )
    return STATE_CHOOSE_DURATION


async def cb_choose_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    duration = int(query.data.split(":")[1])
    user_id = update.effective_user.id
    user_sessions[user_id]["duration"] = duration

    cfg = VIDEO_MODELS[user_sessions[user_id]["model"]]
    cost = cfg["price_per_sec"] * duration

    if cfg["supports_i2v"]:
        prompt_text = (
            f"✅ Длительность: *{duration} сек* (~${cost:.4f})\n\n"
            "📝 Введите промпт или отправьте *фото* для Image-to-Video:"
        )
    else:
        prompt_text = (
            f"✅ Длительность: *{duration} сек* (~${cost:.4f})\n\n"
            "📝 Введите промпт:"
        )

    await query.edit_message_text(prompt_text, parse_mode="Markdown")
    return STATE_ENTER_PROMPT


async def handle_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {})

    if update.message.photo:
        # Image-to-Video: получаем URL фото
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        session["image_url"] = file.file_path
        prompt = update.message.caption or "animate this image smoothly"
    else:
        prompt = (update.message.text or "").strip()
        if not prompt:
            await update.message.reply_text("⚠️ Промпт не может быть пустым.")
            return STATE_ENTER_PROMPT

    session["prompt"] = prompt
    model_key = session.get("model", DEFAULT_MODEL)
    duration  = session.get("duration", VIDEO_MODELS[model_key]["durations"][0])
    image_url = session.get("image_url")

    cfg = VIDEO_MODELS[model_key]
    cost = cfg["price_per_sec"] * duration

    msg = await update.message.reply_text(
        f"⏳ Запускаю генерацию...\n"
        f"Модель: *{cfg['name']}*\n"
        f"Длительность: {duration} сек | Цена: ~${cost:.4f}",
        parse_mode="Markdown"
    )

    # Запускаем как asyncio task в том же event loop
    context.application.create_task(
        _do_generation(update, context, msg, model_key, duration, prompt, image_url)
    )

    return ConversationHandler.END


async def _do_generation(update, context, status_msg, model_key, duration, prompt, image_url):
    """Выполнить генерацию и отправить результат."""
    bot = context.bot
    chat_id = update.effective_chat.id
    msg_id  = status_msg.message_id

    try:
        task = create_video_task(
            prompt=prompt,
            model_key=model_key,
            duration=duration,
            image_url=image_url,
        )
        task_id = task["task_id"]

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=f"⏳ Задача #{task_id[:8]}... запущена. Ожидаю результат...",
        )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: wait_for_completion(task_id, timeout=300, poll_interval=5)
        )
        video_url = result.get("video_url")

        if video_url:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text="⬇️ Скачиваю видео...",
            )
            # Скачиваем видео сами — Telegram не может получить защищённый URL
            import io, requests as req
            download_url = result.get("video_download_url") or video_url
            api_key = os.getenv("API_KEY", "")
            video_resp = await loop.run_in_executor(
                None, lambda: req.get(
                    download_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=120
                )
            )
            video_resp.raise_for_status()
            video_bytes = io.BytesIO(video_resp.content)
            video_bytes.name = "video.mp4"

            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            await bot.send_video(
                chat_id=chat_id,
                video=video_bytes,
                caption=f"✅ Готово!\n🎬 Модель: {VIDEO_MODELS[model_key]['name']}\n📝 {prompt[:100]}",
                supports_streaming=True,
            )
        else:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text="⚠️ Видео готово, но URL не получен. Попробуйте ещё раз.",
            )

    except TimeoutError:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text="⏱ Превышено время ожидания (5 мин). Попробуйте позже.",
        )
    except Exception as e:
        logger.exception("Ошибка генерации в боте")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=f"❌ Ошибка: {str(e)[:200]}",
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END


# ────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("generate", cmd_generate)],
        states={
            STATE_CHOOSE_MODEL:    [CallbackQueryHandler(cb_choose_model, pattern="^model:")],
            STATE_CHOOSE_DURATION: [CallbackQueryHandler(cb_choose_duration, pattern="^dur:")],
            STATE_ENTER_PROMPT:    [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_prompt),
                MessageHandler(filters.PHOTO, handle_prompt),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("models",  cmd_models))
    app.add_handler(conv)

    logger.info("Бот запущен. Нажмите Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
