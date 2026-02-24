"""
app.py — Flask веб-приложение для генерации видео.
"""

import os
import logging
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from config import VIDEO_MODELS, CHEAPEST_FOR_SHORT, CHEAPEST_FOR_5SEC
from request import create_video_task, get_task_status, wait_for_completion

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change_me_in_env")


# ────────────────────────────────────────────────────────────
# Routes
# ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    models = {
        k: {
            "name": v["name"],
            "price_per_sec": v["price_per_sec"],
            "min_duration": v["min_duration"],
            "max_duration": v["max_duration"],
            "supports_i2v": v["supports_i2v"],
            "resolutions": v["resolutions"],
            "note": v["note"],
        }
        for k, v in VIDEO_MODELS.items()
    }
    return render_template(
        "index.html",
        models=models,
        default_model=os.getenv("DEFAULT_MODEL", CHEAPEST_FOR_SHORT),
        default_duration=int(os.getenv("DEFAULT_DURATION", 3)),
    )


@app.route("/generate", methods=["POST"])
def generate():
    """Запустить генерацию видео → вернуть task_id."""
    data = request.get_json(force=True)
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Промпт не может быть пустым"}), 400

    model_key  = data.get("model", os.getenv("DEFAULT_MODEL", CHEAPEST_FOR_SHORT))
    duration   = int(data.get("duration", os.getenv("DEFAULT_DURATION", 3)))
    resolution = data.get("resolution", "720p")
    image_url  = data.get("image_url") or None
    neg_prompt = data.get("negative_prompt", "")
    aspect     = data.get("aspect_ratio", "16:9")

    try:
        result = create_video_task(
            prompt=prompt,
            model_key=model_key,
            duration=duration,
            resolution=resolution,
            image_url=image_url,
            negative_prompt=neg_prompt,
            aspect_ratio=aspect,
        )
        return jsonify(result)
    except KeyError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Ошибка при создании задачи")
        return jsonify({"error": str(e)}), 500


@app.route("/status/<task_id>")
def status(task_id: str):
    """Получить статус задачи."""
    try:
        result = get_task_status(task_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/models")
def models_list():
    """Список доступных моделей с ценами."""
    return jsonify({
        k: {
            "name": v["name"],
            "price_per_sec": v["price_per_sec"],
            "min_duration": v["min_duration"],
            "max_duration": v["max_duration"],
            "supports_i2v": v["supports_i2v"],
            "note": v["note"],
        }
        for k, v in VIDEO_MODELS.items()
    })


# ────────────────────────────────────────────────────────────
# Run
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    host  = os.getenv("FLASK_HOST", "0.0.0.0")
    port  = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info(f"Запуск Flask на {host}:{port}")
    app.run(host=host, port=port, debug=debug)
