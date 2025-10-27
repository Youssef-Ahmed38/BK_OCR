import os
from datetime import timedelta
from pathlib import Path

# Small helpers
def getenv_bool(key, default=False):
    v = os.getenv(key)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")

def getenv_int(key, default):
    v = os.getenv(key)
    try:
        return int(v) if v is not None else default
    except Exception:
        return default

def getenv_float(key, default):
    v = os.getenv(key)
    try:
        return float(v) if v is not None else default
    except Exception:
        return default

def getenv_tuple(key, default):
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return tuple(default) if isinstance(default, (list, tuple)) else (default,)
    parts = [p.strip() for p in str(v).split(",") if p.strip() != ""]
    return tuple(parts) if parts else tuple(default)

def getenv_set(key, default):
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return set(default) if isinstance(default, (list, tuple, set)) else {default}
    parts = [p.strip() for p in str(v).split(",") if p.strip() != ""]
    return set(parts)

# MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "cdndev.eqardy.com")
ACCESS_KEY = os.getenv("ACCESS_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")
USE_SSL = getenv_bool("USE_SSL", True)
BUCKET_NAME = os.getenv("BUCKET_NAME", "bank-statments")
MINIO_PREFIX_DATA = os.getenv("MINIO_PREFIX_DATA", "Data/")
MINIO_PREFIX_CROPS = os.getenv("MINIO_PREFIX_CROPS", "BK_Crops/")

# Models & OCR
MODEL_PATH = os.getenv("MODEL_PATH", "FSA.pt")
D_MODEL_PATH = os.getenv("D_MODEL_PATH", "d3.pt")
OCR_CONF_THRESHOLD = getenv_int("OCR_CONF_THRESHOLD", 50)
OCR_MAX_RETRIES = getenv_int("OCR_MAX_RETRIES", 6)
OCR_PSMS_GENERAL = getenv_tuple("OCR_PSMS_GENERAL", ("7", "6", "11"))
OCR_PSMS_DATE = getenv_tuple("OCR_PSMS_DATE", ("7", "6"))
OCR_PSMS_AMOUNT = getenv_tuple("OCR_PSMS_AMOUNT", ("7", "6", "11"))
CROP_PAD = getenv_int("CROP_PAD", 4)
AMOUNT_WHITELIST = os.getenv("AMOUNT_WHITELIST", "0123456789.,$£€-()")
ROW_MERGE_TOL = getenv_int("ROW_MERGE_TOL", 12)
DATE_ASSIGN_TOLERANCE = getenv_int("DATE_ASSIGN_TOLERANCE", 120)
SAME_LABEL_MERGE_IOU = getenv_float("SAME_LABEL_MERGE_IOU", 0.3)
DIFF_LABEL_OVERLAP_IOU = getenv_float("DIFF_LABEL_OVERLAP_IOU", 0.6)
CONTAIN_PAD = getenv_int("CONTAIN_PAD", 4)
CONTAIN_MIN_IOU = getenv_float("CONTAIN_MIN_IOU", 0.18)
CONTAIN_MIN_OVERLAP = getenv_float("CONTAIN_MIN_OVERLAP", 0.55)
MIN_OVERLAP_FRAC_ROW = getenv_float("MIN_OVERLAP_FRAC_ROW", 0.30)
MIN_OVERLAP_FRAC_BOX = getenv_float("MIN_OVERLAP_FRAC_BOX", 0.50)
FALLBACK_MIN_CONF = getenv_int("FALLBACK_MIN_CONF", 10)
HORIZ_FALLBACK_TOL = getenv_int("HORIZ_FALLBACK_TOL", 220)
EXCLUDED_CLASSES = getenv_set("EXCLUDED_CLASSES", {"Table"})
RANDOM_SEED = getenv_int("RANDOM_SEED", 42)

# Runtime
PORT = int(os.getenv("PORT", 8000))
DEBUG = getenv_bool("DEBUG", False)
MINIO_PRESIGNED_EXPIRE = timedelta(hours=24)

# Expose env mapping var name
SINGLE_LETTER_MONTH_MAP = os.getenv("SINGLE_LETTER_MONTH_MAP", "")