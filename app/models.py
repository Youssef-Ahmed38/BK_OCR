import logging
from ultralytics import YOLO
from .config import MODEL_PATH, D_MODEL_PATH

logger = logging.getLogger(__name__)

def load_models():
    """
    Try to load two YOLO models; return (model, d_model) or (None, None) on failure.
    """
    try:
        model = YOLO(MODEL_PATH)
        d_model = YOLO(D_MODEL_PATH)
        logger.info("YOLO models loaded: %s , %s", MODEL_PATH, D_MODEL_PATH)
        return model, d_model
    except Exception as e:
        logger.exception("Failed to load YOLO models: %s", e)
        return None, None