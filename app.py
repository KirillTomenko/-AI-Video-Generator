import os, logging, requests
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv
from config import VIDEO_MODELS, DEFAULT_MODEL, OPENAI_BASE_URL
from request import create_video_task, get_task_status

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change_me")
API_KEY = os.getenv("API_KEY", "")


@app.route("/")
def index():
    models = {k: {
        "name": v["name"], "price_per_sec": v["price_per_sec"],
        "durations": v["durations"], "supports_i2v": v["supports_i2v"],
        "note": v["note"],
    } for k, v in VIDEO_MODELS.items()}
    return render_template("index.html", models=models,
        default_model=os.getenv("DEFAULT_MODEL", DEFAULT_MODEL),
        default_duration=int(os.getenv("DEFAULT_DURATION", 5)))


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Промпт пустой"}), 400
    try:
        result = create_video_task(
            prompt=prompt,
            model_key=data.get("model", DEFAULT_MODEL),
            duration=int(data.get("duration", 5)),
            resolution=data.get("resolution", "720p"),
            image_url=data.get("image_url"),
            negative_prompt=data.get("negative_prompt", ""),
            aspect_ratio=data.get("aspect_ratio", "16:9"),
        )
        return jsonify(result)
    except KeyError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Ошибка генерации")
        return jsonify({"error": str(e)}), 500


@app.route("/status/<path:task_id>")
def status(task_id):
    try:
        return jsonify(get_task_status(task_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download/<video_id>")
def download(video_id):
    """Прокси для скачивания видео Sora — API-ключ не раскрывается браузеру."""
    url = f"{OPENAI_BASE_URL}/videos/{video_id}/content"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {API_KEY}"},
                         stream=True, timeout=60)
        r.raise_for_status()
        return Response(
            stream_with_context(r.iter_content(chunk_size=8192)),
            content_type=r.headers.get("Content-Type", "video/mp4"),
            headers={"Content-Disposition": f'attachment; filename="{video_id}.mp4"'},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/models")
def models_list():
    return jsonify({k: {"name": v["name"], "price_per_sec": v["price_per_sec"],
                        "durations": v["durations"]} for k, v in VIDEO_MODELS.items()})


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 5000))
    logger.info(f"Запуск на {host}:{port}")
    app.run(host=host, port=port, debug=os.getenv("FLASK_DEBUG","false").lower()=="true")
