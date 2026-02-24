"""
Модели видеогенерации на proxyapi.ru — отсортированы по цене (дешевле сначала).

Цены (с НДС):
  sora-2              — 27 ₽/сек   ← САМАЯ ДЕШЕВАЯ
  veo-3-fast          — 43 ₽/сек
  veo-3.1-fast        — 43 ₽/сек
  veo-3 / veo-3.1     — 95 ₽/сек

API:
  Sora-2  → OpenAI Video API  → https://api.proxyapi.ru/openai/v1
  Veo     → Google Gemini API → https://api.proxyapi.ru/google/v1beta
"""

# Base URL для каждого провайдера
OPENAI_BASE_URL = "https://api.proxyapi.ru/openai/v1"
GOOGLE_BASE_URL = "https://api.proxyapi.ru/google/v1beta"

VIDEO_MODELS = {
    # ── САМАЯ ДЕШЕВАЯ — 27 ₽/сек ─────────────────────────────────────────
    "sora-2": {
        "name": "Sora 2",
        "api_model_id": "sora-2",
        "provider": "openai",                  # использует OpenAI Video API
        "price_per_sec": 27,                   # ₽/сек
        "durations": [4, 8, 12],          # сек (OpenAI поддерживает 5-20)
        "supports_i2v": False,
        "sizes": {
            "16:9": "1280x720",
            "9:16": "720x1280",
            "1:1":  "720x720",
        },
        "note": "Самая дешевая — 27 ₽/сек. ~135 ₽ за 5 сек. Со звуком!",
    },
    # ── GOOGLE VEO — 43 ₽/сек ────────────────────────────────────────────
    "veo-3-fast": {
        "name": "Veo 3 Fast",
        "api_model_id": "veo-3-fast",
        "provider": "google",
        "price_per_sec": 43,                   # ₽/сек
        "durations": [4, 6, 8],
        "supports_i2v": True,
        "resolutions": ["720p", "1080p"],
        "aspect_ratios": ["16:9", "9:16"],
        "note": "Google Veo Fast. ~172 ₽ за 4 сек. I2V поддерживается.",
    },
    "veo-3.1-fast": {
        "name": "Veo 3.1 Fast",
        "api_model_id": "veo-3.1-fast-generate-preview",
        "provider": "google",
        "price_per_sec": 43,
        "durations": [4, 6, 8],
        "supports_i2v": True,
        "resolutions": ["720p", "1080p"],
        "aspect_ratios": ["16:9", "9:16"],
        "note": "Google Veo 3.1 Fast. ~172 ₽ за 4 сек. Лучше качество.",
    },
    # ── ВЫСОКОЕ КАЧЕСТВО — 95 ₽/сек ──────────────────────────────────────
    "veo-3.1": {
        "name": "Veo 3.1",
        "api_model_id": "veo-3.1-generate-preview",
        "provider": "google",
        "price_per_sec": 95,
        "durations": [4, 6, 8],
        "supports_i2v": True,
        "resolutions": ["720p", "1080p"],
        "aspect_ratios": ["16:9", "9:16"],
        "note": "Топ-качество + аудио. ~380 ₽ за 4 сек.",
    },
}

DEFAULT_MODEL = "sora-2"

TASK_STATUS = {
    "PENDING":    "pending",
    "PROCESSING": "processing",
    "COMPLETED":  "completed",
    "FAILED":     "failed",
}
