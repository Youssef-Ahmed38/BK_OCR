import os
import re
import tempfile
import shutil
import time
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from .processor import process_image_file
from .models import load_models
from .minio_client import create_minio_client
from .config import MINIO_PREFIX_DATA, MINIO_PREFIX_CROPS, MINIO_PRESIGNED_EXPIRE, BUCKET_NAME
from .pdf_utils import convert_pdf_to_images

logger = logging.getLogger(__name__)
api = Blueprint('api', __name__)

# Load models & MinIO client once per process
MODEL, D_MODEL = load_models()
MINIO_CLIENT = create_minio_client()

@api.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@api.route('/process', methods=['POST'])
def process_endpoint():
    if 'file' not in request.files:
        return jsonify({"error": "no file provided. upload as 'file'"}), 400

    file = request.files['file']
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    working_dir = tempfile.mkdtemp(prefix="ocrproc_")
    try:
        original_name = os.path.splitext(file.filename)[0]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename = re.sub(r'[^A-Za-z0-9_\-]', '_', original_name)
        input_filename = f"{basename}{os.path.splitext(file.filename)[1]}"
        input_path = os.path.join(working_dir, input_filename)
        file.save(input_path)

        if MODEL is None or D_MODEL is None:
            return jsonify({"error": "models not loaded on server. check server logs."}), 500

        start = time.time()

        if input_path.lower().endswith('.pdf'):
            try:
                pdf_images_dir = os.path.join(working_dir, "pdf_images")
                image_paths = convert_pdf_to_images(input_path, pdf_images_dir, dpi=300)
                if not image_paths:
                    return jsonify({"error": "PDF conversion failed - no pages generated"}), 500
                image_path = image_paths[0]
                result_info = process_image_file(image_path, working_dir, MODEL, D_MODEL, basename, ts)
            except RuntimeError as e:
                logger.error("PDF conversion failed (runtime): %s", e)
                # provide actionable message to caller
                return jsonify({"error": "PDF conversion failed", "detail": str(e)}), 500
            except Exception as e:
                logger.exception("PDF conversion failed")
                return jsonify({"error": "PDF conversion failed", "detail": str(e)}), 500
        else:
            result_info = process_image_file(input_path, working_dir, MODEL, D_MODEL, basename, ts)

        elapsed = time.time() - start
        uploads = {}

        for local_path, prefix in [
            (result_info["json_path"], MINIO_PREFIX_DATA),
            (result_info["excel_path"], MINIO_PREFIX_DATA)
        ]:
            obj_name = f"{prefix}{os.path.basename(local_path)}"
            try:
                MINIO_CLIENT.fput_object(BUCKET_NAME, obj_name, local_path)
            except Exception as e:
                logger.exception("MinIO upload failed")
                return jsonify({"error": "MinIO upload failed", "detail": str(e)}), 500

            try:
                presigned = MINIO_CLIENT.get_presigned_url("GET", BUCKET_NAME, obj_name, expires=MINIO_PRESIGNED_EXPIRE)
            except Exception:
                presigned = None

            uploads[os.path.basename(local_path)] = {
                "object_name": obj_name,
                "presigned_url": presigned
            }

        zip_local = result_info.get("cropped_zip")
        if zip_local and os.path.exists(zip_local):
            zip_name = os.path.basename(zip_local)
            obj_name = f"{MINIO_PREFIX_CROPS}{zip_name}"
            try:
                MINIO_CLIENT.fput_object(BUCKET_NAME, obj_name, zip_local)
            except Exception as e:
                logger.exception("MinIO upload failed (crops)")
                return jsonify({"error": "MinIO upload failed (crops)", "detail": str(e)}), 500

            try:
                presigned = MINIO_CLIENT.get_presigned_url("GET", BUCKET_NAME, obj_name, expires=MINIO_PRESIGNED_EXPIRE)
            except Exception:
                presigned = None

            uploads[zip_name] = {
                "object_name": obj_name,
                "presigned_url": presigned
            }

        response = {
            "status": "success",
            "uploaded": uploads,
            "rows_kept": result_info.get("rows_kept"),
            "elapsed_seconds": elapsed
        }
        return jsonify(response)

    except Exception as e:
        logger.exception("Processing failed")
        return jsonify({"error": "Processing failed", "detail": str(e)}), 500

    finally:
        try:
            shutil.rmtree(working_dir)
        except Exception:
            pass