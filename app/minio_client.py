import logging
from minio import Minio
from minio.error import S3Error
from .config import MINIO_ENDPOINT, ACCESS_KEY, SECRET_KEY, USE_SSL, BUCKET_NAME

logger = logging.getLogger(__name__)

def create_minio_client():
    client = Minio(
        MINIO_ENDPOINT,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        secure=USE_SSL
    )

    try:
        if not client.bucket_exists(BUCKET_NAME):
            client.make_bucket(BUCKET_NAME)
            logger.info("Created bucket: %s", BUCKET_NAME)
        else:
            logger.info("Bucket exists: %s", BUCKET_NAME)
    except S3Error as err:
        logger.exception("MinIO bucket check/create error: %s", err)

    return client