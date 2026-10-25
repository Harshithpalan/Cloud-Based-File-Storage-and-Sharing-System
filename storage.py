import os
import io
import logging
from abc import ABC, abstractmethod
from flask import send_from_directory, send_file, Response

logger = logging.getLogger(__name__)

class BaseStorageProvider(ABC):
    """Abstract storage interface for file operations."""
    
    @abstractmethod
    def save(self, file_storage, stored_filename):
        """Save an uploaded file object. Returns internal storage path/key."""
        pass

    @abstractmethod
    def delete(self, stored_filename):
        """Delete file from storage. Returns True on success, False otherwise."""
        pass

    @abstractmethod
    def exists(self, stored_filename):
        """Check if file exists in storage."""
        pass

    @abstractmethod
    def serve_file(self, stored_filename, original_filename, as_attachment=False, mimetype=None):
        """Return a Flask response to stream or download the file."""
        pass

    @abstractmethod
    def get_content_bytes(self, stored_filename):
        """Return raw content bytes for previewing or hashing."""
        pass


class LocalStorageProvider(BaseStorageProvider):
    """Local filesystem storage provider for development and testing."""

    def __init__(self, upload_folder):
        self.upload_folder = os.path.abspath(upload_folder)
        os.makedirs(self.upload_folder, exist_ok=True)

    def _get_full_path(self, stored_filename):
        return os.path.join(self.upload_folder, stored_filename)

    def save(self, file_storage, stored_filename):
        dest_path = self._get_full_path(stored_filename)
        file_storage.save(dest_path)
        return dest_path

    def delete(self, stored_filename):
        dest_path = self._get_full_path(stored_filename)
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
                return True
            except OSError as e:
                logger.error(f"Error deleting local file {dest_path}: {e}")
                return False
        return False

    def exists(self, stored_filename):
        return os.path.exists(self._get_full_path(stored_filename))

    def serve_file(self, stored_filename, original_filename, as_attachment=False, mimetype=None):
        return send_from_directory(
            self.upload_folder,
            stored_filename,
            as_attachment=as_attachment,
            download_name=original_filename,
            mimetype=mimetype
        )

    def get_content_bytes(self, stored_filename):
        dest_path = self._get_full_path(stored_filename)
        if os.path.exists(dest_path):
            with open(dest_path, 'rb') as f:
                return f.read()
        return None


class GCSStorageProvider(BaseStorageProvider):
    """Google Cloud Storage provider for production deployment on App Engine / Cloud Run."""

    def __init__(self, bucket_name, credentials_path=None):
        self.bucket_name = bucket_name
        self.client = None
        self.bucket = None
        
        try:
            from google.cloud import storage
            if credentials_path and os.path.exists(credentials_path):
                self.client = storage.Client.from_service_account_json(credentials_path)
            else:
                # Uses Application Default Credentials (ADC) on Google App Engine / Cloud Run
                self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(f"Initialized Google Cloud Storage provider with bucket '{bucket_name}'.")
        except Exception as e:
            logger.error(f"Failed to initialize GCS client for bucket '{bucket_name}': {e}")
            raise

    def save(self, file_storage, stored_filename):
        blob = self.bucket.blob(stored_filename)
        file_storage.seek(0)
        blob.upload_from_file(file_storage, content_type=file_storage.mimetype)
        return f"gs://{self.bucket_name}/{stored_filename}"

    def delete(self, stored_filename):
        try:
            blob = self.bucket.blob(stored_filename)
            if blob.exists():
                blob.delete()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete blob '{stored_filename}' from GCS: {e}")
            return False

    def exists(self, stored_filename):
        blob = self.bucket.blob(stored_filename)
        return blob.exists()

    def serve_file(self, stored_filename, original_filename, as_attachment=False, mimetype=None):
        blob = self.bucket.blob(stored_filename)
        if not blob.exists():
            return Response("File not found in cloud storage", status=404)
        
        # Download bytes to in-memory buffer
        file_bytes = blob.download_as_bytes()
        buffer = io.BytesIO(file_bytes)
        
        return send_file(
            buffer,
            as_attachment=as_attachment,
            download_name=original_filename,
            mimetype=mimetype or blob.content_type
        )

    def get_content_bytes(self, stored_filename):
        blob = self.bucket.blob(stored_filename)
        if blob.exists():
            return blob.download_as_bytes()
        return None


def get_storage_provider(app_config):
    """
    Factory to return the appropriate storage provider based on configuration.
    Falls back gracefully to LocalStorageProvider if GCS configuration is incomplete.
    """
    backend = app_config.get('STORAGE_BACKEND', 'local').lower()
    
    if backend == 'gcs':
        bucket_name = app_config.get('GCS_BUCKET_NAME')
        creds_path = app_config.get('GOOGLE_APPLICATION_CREDENTIALS')
        if bucket_name:
            try:
                return GCSStorageProvider(bucket_name, creds_path)
            except Exception as e:
                logger.warning(f"GCS initialization failed: {e}. Falling back to LocalStorageProvider.")
        else:
            logger.warning("STORAGE_BACKEND is set to 'gcs' but GCS_BUCKET_NAME is not configured. Falling back to LocalStorageProvider.")
            
    # Default to local storage provider
    upload_folder = app_config.get('UPLOAD_FOLDER', 'uploads')
    return LocalStorageProvider(upload_folder)
