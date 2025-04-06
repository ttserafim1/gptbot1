import logging
import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from openai import OpenAI
from config import OPENROUTER_API_KEY, TELEGRAM_TOKEN
import clientgpt_setting  # Импорт настроек

# Подключение настроек
settings = clientgpt_setting.settings

# Папка для хранения истории сообщений
HISTORY_FOLDER = settings["history_folder"]
os.makedirs(HISTORY_FOLDER, exist_ok=True)

# Инициализация клиента OpenRouter
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

# Словарь для хранения состояния режима группы для каждого пользователя
user_group_mode = {}

# Функция сохранения истории пользователя
def save_user_message(user_id: int, message: str):
    file_path = os.path.join(HISTORY_FOLDER, f"{user_id}.txt")
    with open(file_path, "a", encoding="utf-8") as file:
        file.write(message + "\n")

# Функция получения последних сообщений пользователя
def get_last_messages(user_id: int):
    file_path = os.path.join(HISTORY_FOLDER, f"{user_id}.txt")
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as file:
        messages = file.readlines()
    return [msg.strip() for msg in messages[-settings["memory_limit"]:]]  # Ограничение по памяти

# Функция очистки истории пользователя
async def clear_history(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    file_path = os.path.join(HISTORY_FOLDER, f"{user_id}.txt")
    if os.path.exists(file_path):
        os.remove(file_path)
        await update.message.reply_text("🗑️ История сообщений очищена!")
    else:
        await update.message.reply_text("ℹ️ У тебя ещё нет сохранённой истории.")

# Приветственное сообщение
# Приветственное сообщение
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🚀 *Привет, я LasiChatGPT! Чем могу помочь?*\n\n"
        "LasiChatGPT — это уникальный и мощный телеграм-бот, который использует новейшие технологии искусственного интеллекта для общения. "
        "Он создан для того, чтобы сделать вашу жизнь проще, интереснее и более продуктивной. "
        "С помощью LasiChatGPT вы получаете доступ к безграничным возможностям общения, решения проблем и получения информации.\n\n"
        "Этот бот умеет генерировать ответы на любые вопросы, помогать с написанием текстов, решать задачи и давать советы по множеству тем, "
        "от науки и технологий до искусства и повседневной жизни. Он способен адаптироваться к вашему стилю общения, и всегда готов предложить нужную информацию или решение с точностью и ясностью.",
        parse_mode='Markdown'
    )


# Обработчик сообщений
async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_message = update.message.text
    chat_type = update.message.chat.type  # Определяем тип чата

    # Если это группа и режим группы включён для пользователя, не отвечаем
    if chat_type in ["group", "supergroup"] and user_group_mode.get(user_id, False):
        return

    logging.info(f"💬 Сообщение от {user_id}: {user_message}")
    save_user_message(user_id, user_message)  # Сохранение запроса
    last_messages = get_last_messages(user_id)  # Получение истории

    # Форматирование истории для промта
    history = "\n".join([f"{idx+1}. {msg}" for idx, msg in enumerate(last_messages)])

    # Вставляем историю в системный промт
    system_prompt = settings["system_prompt"].format(history=history)

    try:
        response = client.chat.completions.create(
            model="google/gemini-2.0-flash-lite-001",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=settings["max_tokens"],
            temperature=settings["temperature"],
            top_p=settings["top_p"]
        )

        # Отладочная печать структуры ответа
        logging.info(f"Ответ от OpenRouter: {response}")

        # Проверка содержимого ответа
        if response and hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and choice.message and hasattr(choice.message, "content"):
                # Замена всех вариантов "google" (регистр не важен) на "frokzer"
                bot_response = re.sub(r'(?i)google', 'frokzer', choice.message.content.strip())
            else:
                bot_response = "⚠️ Модель вернула неожиданный формат ответа."
        else:
            bot_response = "⚠️ Модель не вернула ответа."

    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        bot_response = "🌠 *Сеть временно нестабильна. Попробуй позже.* 🚀"

    logging.info(f"📡 Ответ пользователю {user_id}: {bot_response}")
    await update.message.reply_text(bot_response, parse_mode='HTML')

# Основная функция запуска бота
def main():
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clearhistory", clear_history))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()
