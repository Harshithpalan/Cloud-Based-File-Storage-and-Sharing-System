import os
import shutil
import tempfile
import pytest
from app import create_app
import database as db

@pytest.fixture
def app_instance():
    """Create and configure a Flask application for automated testing."""
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, 'test_cloud_file_share.db')
    temp_uploads = os.path.join(temp_dir, 'uploads')
    os.makedirs(temp_uploads, exist_ok=True)

    app = create_app('testing')
    app.config.update({
        'TESTING': True,
        'DATABASE_PATH': temp_db,
        'UPLOAD_FOLDER': temp_uploads,
        'STORAGE_BACKEND': 'local',
        'SECRET_KEY': 'test-secret-key-antigravity',
        'DEFAULT_USER_QUOTA': 10 * 1024 * 1024  # 10 MB for testing
    })

    # Re-initialize test db & storage provider for this temporary instance
    with app.app_context():
        db.init_db(temp_db)
        from storage import LocalStorageProvider
        app.storage_provider = LocalStorageProvider(temp_uploads)

    yield app

    # Cleanup temporary folder
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def client(app_instance):
    """Test HTTP client."""
    return app_instance.test_client()

@pytest.fixture
def registered_user(app_instance):
    """Create a test user and return user credentials."""
    username = 'cloud_tester'
    email = 'tester@cloud.edu'
    password = 'SecurePassword123!'
    db_path = app_instance.config['DATABASE_PATH']
    user = db.create_user(db_path, username, email, password, storage_quota=app_instance.config['DEFAULT_USER_QUOTA'])
    return {
        'id': user['id'],
        'username': username,
        'email': email,
        'password': password
    }

@pytest.fixture
def auth_client(client, registered_user):
    """Test client logged in as registered_user."""
    client.post('/login', data={
        'identifier': registered_user['username'],
        'password': registered_user['password']
    }, follow_redirects=True)
    return client
