# run.py
import logging
import os
import importlib
from dotenv import load_dotenv
from flask import Flask

# load .env right away
load_dotenv()

# Configure logging early so modules imported later inherit this config
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# You can control these via .env or fallback defaults:
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "false").strip().lower() in ("1", "true", "yes", "y", "on")


def create_app():
    """
    Application factory. Creates Flask app and registers the API blueprint.
    This file allows you to remove app/__init__.py and keep a single runner.
    """
    app = Flask(__name__)

    # Dynamically import app.api and register the blueprint there.
    # This expects a module at app/api.py that exposes "api" (a Blueprint).
    try:
        api_module = importlib.import_module("app.api")
    except Exception as exc:
        # Helpful error message if imports fail
        logger.exception("Failed to import app.api. Check that 'app' folder is on PYTHONPATH and app/api.py exists.")
        raise

    if not hasattr(api_module, "api"):
        raise RuntimeError("app.api module does not expose a Blueprint named 'api' (expected attribute 'api').")

    app.register_blueprint(api_module.api)
    logger.info("Registered blueprint: app.api.api")

    # Optional: register health endpoint directly if not present in blueprint
    # from flask import jsonify
    # @app.route("/health")
    # def health():
    #     return jsonify({"status": "ok"})

    return app


# create app instance for WSGI servers (gunicorn etc)
app = create_app()


if __name__ == "__main__":
    logger.info("Starting Flask app on 0.0.0.0:%s (debug=%s)", PORT, DEBUG)
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
