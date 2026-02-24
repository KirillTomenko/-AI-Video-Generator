"""
request.py — клиент для видеогенерации через proxyapi.ru.

Поддерживает два провайдера:
  openai → Sora 2   → POST /openai/v1/videos
  google → Veo 3.x  → POST /google/v1beta/models/{model}:predictLongRunning
"""

import os
import time
import logging
import requests
from dotenv import load_dotenv
from config import VIDEO_MODELS, OPENAI_BASE_URL, GOOGLE_BASE_URL, TASK_STATUS

load_dotenv()
logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY", "")


def _openai_headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def _google_headers():
    return {"x-goog-api-key": API_KEY, "Content-Type": "application/json"}

def get_model_config(model_key):
    if model_key not in VIDEO_MODELS:
        raise KeyError(f"Неизвестная модель: {model_key}. Доступны: {list(VIDEO_MODELS)}")
    return VIDEO_MODELS[model_key]

def _nearest(wanted, available):
    return min(available, key=lambda x: abs(x - wanted))


# ────────────────────────────────────────────────────────────
# Создание задачи
# ────────────────────────────────────────────────────────────

def create_video_task(prompt, model_key, duration=5, resolution="720p",
                      image_url=None, negative_prompt="", aspect_ratio="16:9"):
    cfg = get_model_config(model_key)
    provider = cfg["provider"]

    if provider == "openai":
        return _create_sora_task(cfg, prompt, duration, aspect_ratio)
    else:
        return _create_veo_task(cfg, prompt, duration, resolution,
                                image_url, negative_prompt, aspect_ratio)


def _create_sora_task(cfg, prompt, duration, aspect_ratio):
    """OpenAI Sora 2 — POST /v1/videos"""
    duration = _nearest(duration, cfg["durations"])
    size = cfg["sizes"].get(aspect_ratio, "1280x720")

    payload = {
        "model": cfg["api_model_id"],
        "prompt": prompt,
        "size": size,
        "seconds": str(duration),
    }

    endpoint = f"{OPENAI_BASE_URL}/videos"
    logger.info(f"POST {endpoint} | sora-2 | {duration}s | {size}")

    try:
        resp = requests.post(endpoint, json=payload, headers=_openai_headers(), timeout=30)
        if not resp.ok:
            logger.error(f"Sora API {resp.status_code}: {resp.text}")
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as e:
        raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.text}") from e

    # Ответ: {"id": "video_xxx", "status": "queued", ...}
    task_id = data.get("id")
    if not task_id:
        raise ValueError(f"API не вернул id. Ответ: {data}")

    cost = cfg["price_per_sec"] * duration
    logger.info(f"Задача: {task_id} | ~{cost:.0f} ₽")

    return {"task_id": task_id, "model": cfg["name"],
            "duration": duration, "estimated_cost": cost}


def _create_veo_task(cfg, prompt, duration, resolution, image_url,
                     negative_prompt, aspect_ratio):
    """Google Veo — POST /google/v1beta/models/{model}:predictLongRunning"""
    duration = _nearest(duration, cfg["durations"])
    if resolution == "1080p" and (duration != 8 or aspect_ratio != "16:9"):
        resolution = "720p"

    instance = {
        "prompt": prompt,
        "durationSeconds": str(duration),
        "aspectRatio": aspect_ratio,
        "resolution": resolution,
        "personGeneration": "allow_all",
    }
    if negative_prompt:
        instance["negativePrompt"] = negative_prompt
    if image_url:
        import base64
        if image_url.startswith("data:"):
            header, data = image_url.split(",", 1)
            mime = header.split(":")[1].split(";")[0]
        else:
            r = requests.get(image_url, timeout=15); r.raise_for_status()
            data = base64.b64encode(r.content).decode()
            mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
        instance["image"] = {"bytesBase64Encoded": data, "mimeType": mime}
        instance["personGeneration"] = "allow_adult"

    endpoint = f"{GOOGLE_BASE_URL}/models/{cfg['api_model_id']}:predictLongRunning"
    logger.info(f"POST {endpoint} | {duration}s | {resolution}")

    try:
        resp = requests.post(endpoint, json={"instances": [instance]},
                             headers=_google_headers(), timeout=30)
        if not resp.ok:
            logger.error(f"Veo API {resp.status_code}: {resp.text}")
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as e:
        raise RuntimeError(f"HTTP {e.response.status_code}: {e.response.text}") from e

    operation_name = data.get("name")
    if not operation_name:
        raise ValueError(f"API не вернул operation name. Ответ: {data}")

    cost = cfg["price_per_sec"] * duration
    return {"task_id": operation_name, "model": cfg["name"],
            "duration": duration, "estimated_cost": cost}


# ────────────────────────────────────────────────────────────
# Статус
# ────────────────────────────────────────────────────────────

def get_task_status(task_id):
    # Определяем провайдера по формату task_id
    if task_id.startswith("video_"):
        return _get_sora_status(task_id)
    else:
        return _get_veo_status(task_id)


def _get_sora_status(video_id):
    """GET /v1/videos/{id}"""
    endpoint = f"{OPENAI_BASE_URL}/videos/{video_id}"
    try:
        resp = requests.get(endpoint, headers=_openai_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"status": "error", "video_url": None, "error": str(e)}

    status_raw = data.get("status", "")

    if status_raw == "completed":
        # Скачиваем видео через /v1/videos/{id}/content
        download_url = f"{OPENAI_BASE_URL}/videos/{video_id}/content"
        return {
            "status": TASK_STATUS["COMPLETED"],
            "video_url": download_url,
            "video_download_url": download_url,
            "video_id": video_id,
            "error": None,
        }
    elif status_raw in ("failed", "cancelled"):
        return {"status": TASK_STATUS["FAILED"], "video_url": None,
                "error": data.get("error", "Неизвестная ошибка")}
    else:
        # queued / in_progress
        progress = data.get("progress", 0)
        return {"status": TASK_STATUS["PROCESSING"], "video_url": None,
                "error": None, "progress": progress}


def _get_veo_status(task_id):
    """GET /google/v1beta/{operation_name}"""
    endpoint = f"{GOOGLE_BASE_URL}/{task_id}" if "/" in task_id \
               else f"{GOOGLE_BASE_URL}/operations/{task_id}"
    try:
        resp = requests.get(endpoint, headers=_google_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"status": "error", "video_url": None, "error": str(e)}

    if data.get("done"):
        if "error" in data:
            return {"status": TASK_STATUS["FAILED"], "video_url": None,
                    "error": str(data["error"])}
        try:
            uri = data["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
        except (KeyError, IndexError):
            uri = None
        dl = (f"{uri}?key={API_KEY}" if uri and "?" not in uri
              else f"{uri}&key={API_KEY}" if uri else None)
        return {"status": TASK_STATUS["COMPLETED"], "video_url": uri,
                "video_download_url": dl, "error": None}

    return {"status": TASK_STATUS["PROCESSING"], "video_url": None, "error": None}


# ────────────────────────────────────────────────────────────
# Polling
# ────────────────────────────────────────────────────────────

def wait_for_completion(task_id, timeout=300, poll_interval=5, progress_callback=None):
    start = time.time()
    i = 0
    while time.time() - start < timeout:
        i += 1
        result = get_task_status(task_id)
        if progress_callback:
            progress_callback(result["status"])
        if result["status"] == TASK_STATUS["COMPLETED"]:
            return result
        if result["status"] == TASK_STATUS["FAILED"]:
            raise RuntimeError(f"Ошибка генерации: {result.get('error')}")
        logger.debug(f"Попытка {i}: {result['status']}")
        time.sleep(poll_interval)
    raise TimeoutError(f"Не завершилась за {timeout} сек.")
