import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'cloud-file-share-dev-secret-key-2026')
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Database
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'cloud_file_share.db'))
    
    # Upload & Storage
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads'))
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_FILE_SIZE', 50 * 1024 * 1024))  # 50 MB max upload
    DEFAULT_USER_QUOTA = int(os.environ.get('USER_STORAGE_QUOTA', 100 * 1024 * 1024))  # 100 MB free tier
    
    # Storage Backend ('local' or 'gcs')
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'local').lower()
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', '')
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
    
    # Allowed Extensions for Upload Security
    ALLOWED_EXTENSIONS = {
        'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg',
        'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'json',
        'zip', 'tar', 'gz', '7z', 'rar',
        'mp3', 'wav', 'ogg', 'm4a', 'aac',
        'mp4', 'webm', 'mov', 'mkv', 'avi',
        'py', 'js', 'html', 'css', 'sql', 'md', 'sh', 'java', 'cpp', 'c'
    }

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    DATABASE_PATH = ':memory:'
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'test_uploads')
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # In production on Google Cloud, use environment variables
    SECRET_KEY = os.environ.get('SECRET_KEY')
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'gcs')

config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
