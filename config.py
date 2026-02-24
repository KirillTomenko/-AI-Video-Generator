"""
Конфигурация моделей видеогенерации.
Выбраны самые экономичные варианты для коротких роликов (2-5 сек).
Цены указаны ориентировочно — проверяйте актуальные у провайдера.
"""

# Поддерживаемые провайдеры и их базовые URL
PROVIDERS = {
    "piapi":   "https://api.piapi.ai",
    "genapi":  "https://api.gen-api.ru",
    "proxyapi":"https://api.proxyapi.ru",  # укажите свой
}

# Модели: name → конфиг
# price_per_sec — ориентировочная цена в $ за секунду видео
# min_duration  — минимальная длительность в секундах
# max_duration  — максимальная длительность
# supports_i2v  — поддержка Image-to-Video
# api_model_id  — идентификатор модели в API
VIDEO_MODELS = {
    # ── САМЫЕ ДЕШЁВЫЕ ──────────────────────────────────────────────────────
    "ltx-video-fast": {
        "name": "LTX Video Fast",
        "api_model_id": "ltx-video-fast",        # piapi / gen-api
        "price_per_sec": 0.005,                   # ~$0.015 за 3 сек
        "min_duration": 2,
        "max_duration": 5,
        "supports_i2v": True,
        "resolutions": ["480p", "720p"],
        "note": "Самая дешёвая. Быстрая генерация. Качество базовое."
    },
    "wan-2.1-turbo": {
        "name": "Wan 2.1 Turbo (720p)",
        "api_model_id": "Wanx2.1-T2V-Turbo",     # piapi
        "price_per_sec": 0.08,                    # ~$0.24 за 3 сек
        "min_duration": 3,
        "max_duration": 5,
        "supports_i2v": False,
        "resolutions": ["480p", "720p"],
        "note": "Хорошее качество, быстро, недорого. Только T2V."
    },
    "wan-2.1-i2v-turbo": {
        "name": "Wan 2.1 I2V Turbo (720p)",
        "api_model_id": "Wanx2.1-I2V-Turbo-14B",  # piapi
        "price_per_sec": 0.08,
        "min_duration": 3,
        "max_duration": 5,
        "supports_i2v": True,
        "resolutions": ["480p", "720p"],
        "note": "Image-to-Video вариант Wan Turbo."
    },
    # ── СРЕДНИЙ ЦЕНОВОЙ СЕГМЕНТ ─────────────────────────────────────────────
    "kling-v1-standard": {
        "name": "Kling 1.0 Standard",
        "api_model_id": "kling-video-v1",
        "price_per_sec": 0.028,                   # ~$0.14 за 5 сек (минимум)
        "min_duration": 5,
        "max_duration": 10,
        "supports_i2v": True,
        "resolutions": ["720p", "1080p"],
        "note": "Стабильное качество. Минимум 5 сек — не подходит для 2-3 сек."
    },
    "pixverse-fast": {
        "name": "PixVerse v4 Fast",
        "api_model_id": "pixverse-v4-fast",
        "price_per_sec": 0.04,
        "min_duration": 4,
        "max_duration": 8,
        "supports_i2v": True,
        "resolutions": ["540p", "720p", "1080p"],
        "note": "Быстрая генерация, хорошее качество для соцсетей."
    },
}

# Рекомендации по экономии:
# 1. Для 2-3 сек → ltx-video-fast (~$0.01-0.02 за ролик)
# 2. Для 3-5 сек T2V → wan-2.1-turbo (~$0.24-0.40 за ролик)
# 3. Для 3-5 сек I2V → wan-2.1-i2v-turbo (~$0.24-0.40 за ролик)
# 4. Если нужно качество 5+ сек → kling-v1-standard

CHEAPEST_FOR_SHORT = "ltx-video-fast"  # для 2-3 сек
CHEAPEST_FOR_5SEC  = "wan-2.1-turbo"   # для 5 сек T2V

# Статусы задач API (стандартные)
TASK_STATUS = {
    "PENDING":    "pending",
    "PROCESSING": "processing",
    "COMPLETED":  "completed",
    "FAILED":     "failed",
}
