import os
import uuid
from fastapi import UploadFile, HTTPException, status
from google.cloud import storage
from google.api_core import exceptions as google_exceptions
from google.auth.exceptions import DefaultCredentialsError
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
try:
    GCS_BUCKET_NAME = os.environ["GCS_BUCKET_NAME"]
    # GOOGLE_APPLICATION_CREDENTIALS should be set in the environment
except KeyError:
    logger.error("GCS_BUCKET_NAME or GOOGLE_APPLICATION_CREDENTIALS not set.")
    # This is a critical configuration error. The application should not start.
    # In a real app, you might have a more robust configuration management system.
    raise ImportError("GCS environment variables not properly configured.") from None

# Initialize Google Cloud Storage client
try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
except DefaultCredentialsError:
    logger.error("GCS authentication failed. Check GOOGLE_APPLICATION_CREDENTIALS.")
    # This error is also critical.
    raise ImportError("Could not authenticate with Google Cloud Storage.") from None
except Exception as e:
    logger.exception(f"An unexpected error occurred during GCS client initialization: {e}")
    raise


async def upload_file_to_gcs(file: UploadFile, destination_path: str = "profile_images") -> str:
    """
    Uploads a file to a specified path within the GCS bucket.

    Args:
        file: The file to upload, coming from a FastAPI endpoint.
        destination_path: The folder/path within the bucket to upload to.

    Returns:
        The public URL of the uploaded file.
    
    Raises:
        HTTPException: If the upload fails for various reasons.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file name provided.")

    # Generate a unique filename to prevent overwrites and add security
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    blob_name = f"{destination_path}/{unique_filename}"
    
    blob = bucket.blob(blob_name)

    try:
        # Read the file content into memory
        contents = await file.read()
        
        # Upload the file
        blob.upload_from_string(
            contents,
            content_type=file.content_type
        )
        
    except google_exceptions.GoogleAPICallError as e:
        logger.exception(f"GCS API error during upload of {blob_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A cloud storage error occurred during upload."
        ) from e
    except Exception as e:
        logger.exception(f"An unexpected error occurred uploading file to GCS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the file."
        ) from e

    logger.info(f"File {file.filename} uploaded to {blob.public_url}")
    return blob.public_url 