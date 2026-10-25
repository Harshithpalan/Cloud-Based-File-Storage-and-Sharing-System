import pytest
import database as db

def test_registration_success(client, app_instance):
    """Verify user can register successfully and password is encrypted."""
    response = client.post('/register', data={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'Password123',
        'confirm_password': 'Password123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Welcome to Cloud File Share" in response.data or b"Dashboard" in response.data

    # Check user in db and verify password hashing
    user = db.get_user_by_username(app_instance.config['DATABASE_PATH'], 'newuser')
    assert user is not None
    assert user['email'] == 'newuser@example.com'
    assert user['password_hash'] != 'Password123'
    assert user['password_hash'].startswith('scrypt:') or user['password_hash'].startswith('pbkdf2:')

def test_registration_duplicate_username(client, registered_user):
    """Verify duplicate username is rejected with error."""
    response = client.post('/register', data={
        'username': registered_user['username'],
        'email': 'different@example.com',
        'password': 'Password123',
        'confirm_password': 'Password123'
    }, follow_redirects=True)
    assert b"Username already registered" in response.data

def test_registration_duplicate_email(client, registered_user):
    """Verify duplicate email is rejected with error."""
    response = client.post('/register', data={
        'username': 'anotheruser',
        'email': registered_user['email'],
        'password': 'Password123',
        'confirm_password': 'Password123'
    }, follow_redirects=True)
    assert b"Email already registered" in response.data

def test_registration_password_mismatch(client):
    """Verify password mismatch generates warning."""
    response = client.post('/register', data={
        'username': 'testmismatch',
        'email': 'mismatch@example.com',
        'password': 'Password123',
        'confirm_password': 'Password456'
    }, follow_redirects=True)
    assert b"Passwords do not match" in response.data

def test_login_success_with_username(client, registered_user):
    """Verify successful login using username."""
    response = client.post('/login', data={
        'identifier': registered_user['username'],
        'password': registered_user['password']
    }, follow_redirects=True)
    assert response.status_code == 200
    assert registered_user['username'].encode() in response.data

def test_login_success_with_email(client, registered_user):
    """Verify successful login using email address."""
    response = client.post('/login', data={
        'identifier': registered_user['email'],
        'password': registered_user['password']
    }, follow_redirects=True)
    assert response.status_code == 200
    assert registered_user['username'].encode() in response.data

def test_login_invalid_password(client, registered_user):
    """Verify invalid password fails authentication."""
    response = client.post('/login', data={
        'identifier': registered_user['username'],
        'password': 'WrongPassword!'
    }, follow_redirects=True)
    assert b"Invalid username/email or password" in response.data

def test_protected_routes_require_login(client):
    """Verify unauthenticated requests redirect to login."""
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_logout(auth_client):
    """Verify logout clears session and prevents access to dashboard."""
    response = auth_client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b"logged out securely" in response.data

    # Now dashboard should redirect
    dash_response = auth_client.get('/dashboard', follow_redirects=False)
    assert dash_response.status_code == 302
