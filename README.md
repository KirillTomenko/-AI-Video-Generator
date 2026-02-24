# 🎬 AI Video Generator

Генерация коротких видео через API-агрегатор (piapi.ai, gen-api.ru и совместимые).  
Проект включает Flask веб-интерфейс и Telegram бот.

## Структура

```
video_generate/
├── app.py          # Flask веб-приложение
├── bot.py          # Telegram бот
├── request.py      # API клиент (polling, создание задач)
├── config.py       # Модели и цены
├── templates/
│   └── index.html  # Веб-интерфейс
├── .env.example    # Шаблон переменных окружения
└── requirements.txt
```

## Быстрый старт

### 1. Установка
```bash
pip install -r requirements.txt
```

### 2. Настройка .env
```bash
cp .env.example .env
# Откройте .env и заполните:
#   API_KEY       — ключ от вашего API-агрегатора
#   API_BASE_URL  — базовый URL провайдера
#   TELEGRAM_BOT_TOKEN — токен бота (для bot.py)
```

### 3. Запуск веб-приложения
```bash
python app.py
# → http://localhost:5000
```

### 4. Запуск Telegram бота
```bash
python bot.py
```

---

## Выбор модели по стоимости

| Модель | ~$/ 3 сек | ~$/ 5 сек | I2V | Мин. длит. |
|--------|-----------|-----------|-----|-----------|
| **LTX Video Fast** | **$0.015** | $0.025 | ✅ | 2 сек |
| Wan 2.1 Turbo | $0.24 | $0.40 | ❌ | 3 сек |
| Wan 2.1 I2V Turbo | $0.24 | $0.40 | ✅ | 3 сек |
| PixVerse v4 Fast | — | $0.20 | ✅ | 4 сек |
| Kling 1.0 Standard | — | $0.14 | ✅ | 5 сек |

> **Совет:** Для 2-3 сек роликов → `ltx-video-fast` (дешевле всего).  
> Для 5 сек высокого качества → `kling-v1-standard` или `wan-2.1-turbo`.

---

## Поддерживаемые провайдеры

| Провайдер | API_BASE_URL |
|-----------|-------------|
| piapi.ai | `https://api.piapi.ai` |
| gen-api.ru | `https://api.gen-api.ru` |
| proxyapi | укажите свой URL |

> Если провайдер использует другой формат запросов — расширьте `request.py`,  
> добавив адаптер в `_adapt_for_genapi()` по аналогии.

---

## API эндпоинты (Flask)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/` | Веб-интерфейс |
| POST | `/generate` | Создать задачу генерации |
| GET | `/status/<task_id>` | Статус задачи |
| GET | `/models` | Список моделей с ценами |

### Пример запроса
```bash
curl -X POST http://localhost:5000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A cat walking on a beach at sunset",
    "model": "ltx-video-fast",
    "duration": 3,
    "resolution": "720p"
  }'
```

### Ответ
```json
{
  "task_id": "abc123...",
  "model": "LTX Video Fast",
  "duration": 3,
  "estimated_cost": 0.015
}
```
