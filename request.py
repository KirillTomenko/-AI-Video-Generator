"""
request.py — обёртка над API видеогенерации.
Поддерживает piapi.ai, gen-api.ru и любой совместимый агрегатор.
"""

import os
import time
import logging
import requests
from typing import Optional
from dotenv import load_dotenv
from config import VIDEO_MODELS, TASK_STATUS

load_dotenv()
logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY", "")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.piapi.ai").rstrip("/")


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_model_config(model_key: str) -> dict:
    """Вернуть конфиг модели или выбросить KeyError."""
    if model_key not in VIDEO_MODELS:
        raise KeyError(f"Неизвестная модель: {model_key}. Доступны: {list(VIDEO_MODELS)}")
    return VIDEO_MODELS[model_key]


# ────────────────────────────────────────────────────────────
# Создание задачи
# ────────────────────────────────────────────────────────────

def create_video_task(
    prompt: str,
    model_key: str,
    duration: Optional[int] = None,
    resolution: str = "720p",
    image_url: Optional[str] = None,
    negative_prompt: str = "",
    aspect_ratio: str = "16:9",
) -> dict:
    """
    Отправить задачу на генерацию видео.

    Возвращает dict с полями:
        task_id (str), model (str), estimated_cost (float)
    """
    cfg = get_model_config(model_key)
    api_model = cfg["api_model_id"]

    # Проверяем длительность
    if duration is None:
        duration = cfg["min_duration"]
    duration = max(cfg["min_duration"], min(duration, cfg["max_duration"]))

    # Базовая структура запроса (piapi / gen-api совместимая)
    payload: dict = {
        "model": api_model,
        "task_type": "img2video" if image_url else "txt2video",
        "input": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
        },
        "config": {
            "webhook_config": {
                "endpoint": "",   # оставьте пустым для polling
            }
        }
    }

    if image_url:
        if not cfg["supports_i2v"]:
            raise ValueError(f"Модель {cfg['name']} не поддерживает Image-to-Video")
        payload["input"]["image_url"] = image_url

    # Некоторые провайдеры ожидают чуть иной формат — адаптируем
    endpoint = f"{API_BASE_URL}/api/v1/task"
    if "gen-api.ru" in API_BASE_URL:
        endpoint = f"{API_BASE_URL}/v1/video/generate"
        payload = _adapt_for_genapi(payload, cfg)

    logger.info(f"POST {endpoint} | model={api_model} | duration={duration}s")

    try:
        resp = requests.post(endpoint, json=payload, headers=_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"Ошибка запроса к API: {e}")
        raise

    task_id = (
        data.get("task_id")
        or data.get("id")
        or data.get("data", {}).get("task_id")
    )
    if not task_id:
        raise ValueError(f"API не вернул task_id. Ответ: {data}")

    estimated_cost = cfg["price_per_sec"] * duration
    logger.info(f"Задача создана: {task_id} | ~${estimated_cost:.4f}")

    return {
        "task_id": task_id,
        "model": cfg["name"],
        "duration": duration,
        "estimated_cost": estimated_cost,
    }


def _adapt_for_genapi(payload: dict, cfg: dict) -> dict:
    """Адаптировать payload под формат gen-api.ru."""
    inp = payload["input"]
    return {
        "model": cfg["api_model_id"],
        "prompt": inp.get("prompt", ""),
        "negative_prompt": inp.get("negative_prompt", ""),
        "duration": inp.get("duration", 5),
        "resolution": inp.get("resolution", "720p"),
        "image_url": inp.get("image_url"),
    }


# ────────────────────────────────────────────────────────────
# Проверка статуса
# ────────────────────────────────────────────────────────────

def get_task_status(task_id: str) -> dict:
    """
    Получить текущий статус задачи.

    Возвращает dict:
        status (str), video_url (str|None), error (str|None)
    """
    endpoint = f"{API_BASE_URL}/api/v1/task/{task_id}"
    if "gen-api.ru" in API_BASE_URL:
        endpoint = f"{API_BASE_URL}/v1/task/{task_id}"

    try:
        resp = requests.get(endpoint, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning(f"Ошибка получения статуса {task_id}: {e}")
        return {"status": "error", "video_url": None, "error": str(e)}

    # Нормализуем ответ от разных провайдеров
    raw = data.get("data") or data
    status_raw = (
        raw.get("status")
        or raw.get("task_status")
        or ""
    ).lower()

    # Маппинг статусов
    if status_raw in ("completed", "succeed", "success", "done"):
        status = TASK_STATUS["COMPLETED"]
    elif status_raw in ("failed", "error", "cancelled"):
        status = TASK_STATUS["FAILED"]
    elif status_raw in ("processing", "running", "in_progress", "generating"):
        status = TASK_STATUS["PROCESSING"]
    else:
        status = TASK_STATUS["PENDING"]

    video_url = (
        raw.get("video_url")
        or raw.get("output", {}).get("video_url")
        or (raw.get("output") if isinstance(raw.get("output"), str) else None)
    )
    error_msg = raw.get("error") or raw.get("error_message")

    return {
        "status": status,
        "video_url": video_url,
        "error": error_msg,
        "raw": data,
    }


# ────────────────────────────────────────────────────────────
# Polling — ждать завершения задачи
# ────────────────────────────────────────────────────────────

def wait_for_completion(
    task_id: str,
    timeout: int = 300,
    poll_interval: int = 5,
    progress_callback=None,
) -> dict:
    """
    Ждать завершения задачи с polling.

    Args:
        task_id: ID задачи
        timeout: максимальное время ожидания в секундах
        poll_interval: интервал опроса в секундах
        progress_callback: функция(status_str) — вызывается при каждом опросе

    Returns:
        dict с video_url при успехе или error при ошибке.
    """
    start = time.time()
    attempts = 0

    while time.time() - start < timeout:
        attempts += 1
        result = get_task_status(task_id)
        status = result["status"]

        logger.debug(f"[{task_id}] Попытка {attempts}: {status}")
        if progress_callback:
            progress_callback(status)

        if status == TASK_STATUS["COMPLETED"]:
            return result

        if status == TASK_STATUS["FAILED"]:
            raise RuntimeError(f"Генерация завершилась с ошибкой: {result.get('error')}")

        time.sleep(poll_interval)

    raise TimeoutError(f"Задача {task_id} не завершилась за {timeout} сек.")
