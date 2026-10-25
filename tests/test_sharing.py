import io
import json
from datetime import datetime, timedelta, timezone
import pytest
import database as db

def test_create_share_link_download_permission(auth_client, client):
    """Verify share link generation and public download permission."""
    # Upload test file
    data = {'files': (io.BytesIO(b"Shared secret file content"), 'secret_doc.txt')}
    upload_res = auth_client.post('/api/files/upload', data=data, content_type='multipart/form-data')
    file_id = json.loads(upload_res.data)['uploaded'][0]['id']

    # Create share link with download permission
    share_res = auth_client.post(f'/api/files/{file_id}/share', json={
        'permission': 'download',
        'expires_in': 'never'
    })
    assert share_res.status_code == 200
    share_data = json.loads(share_res.data)
    token = share_data['share_token']

    # Public user (unauthenticated) accesses the share landing page
    view_res = client.get(f'/share/{token}')
    assert view_res.status_code == 200
    assert b"secret_doc.txt" in view_res.data
    assert b"Download File" in view_res.data

    # Public user downloads the file
    dl_res = client.get(f'/share/{token}/download')
    assert dl_res.status_code == 200
    assert dl_res.data == b"Shared secret file content"

def test_view_only_share_link_blocks_download(auth_client, client):
    """Verify view-only permission allows previewing but strictly blocks downloads (403)."""
    # Upload test file
    data = {'files': (io.BytesIO(b"View only confidential text"), 'confidential.txt')}
    upload_res = auth_client.post('/api/files/upload', data=data, content_type='multipart/form-data')
    file_id = json.loads(upload_res.data)['uploaded'][0]['id']

    # Create share link with view permission
    share_res = auth_client.post(f'/api/files/{file_id}/share', json={
        'permission': 'view',
        'expires_in': '24h'
    })
    token = json.loads(share_res.data)['share_token']

    # View page shows View-Only warning
    view_res = client.get(f'/share/{token}')
    assert view_res.status_code == 200
    assert b"View-Only Permission" in view_res.data

    # Preview works
    prev_res = client.get(f'/share/{token}/preview')
    assert prev_res.status_code == 200
    assert prev_res.data == b"View only confidential text"

    # Attempting to download must return 403 Forbidden!
    dl_res = client.get(f'/share/{token}/download')
    assert dl_res.status_code == 403
    assert b"Download permission denied" in dl_res.data

def test_revoked_share_link_is_blocked(auth_client, client):
    """Verify revoked link immediately denies access with 410 Gone."""
    data = {'files': (io.BytesIO(b"Revoke target file"), 'revoke_target.txt')}
    upload_res = auth_client.post('/api/files/upload', data=data, content_type='multipart/form-data')
    file_id = json.loads(upload_res.data)['uploaded'][0]['id']

    # Create share link
    share_res = auth_client.post(f'/api/files/{file_id}/share', json={'permission': 'download'})
    share_data = json.loads(share_res.data)
    token = share_data['share_token']
    link_id = share_data['link_id']

    # Revoke link
    revoke_res = auth_client.post(f'/api/share/{link_id}/revoke')
    assert revoke_res.status_code == 200
    assert json.loads(revoke_res.data)['success'] is True

    # Recipient viewing revoked link should get 410 Gone
    view_res = client.get(f'/share/{token}')
    assert view_res.status_code == 410
    assert b"Link Revoked" in view_res.data

    # Direct download attempt should fail
    dl_res = client.get(f'/share/{token}/download')
    assert dl_res.status_code == 410

def test_expired_share_link_is_blocked(auth_client, client, app_instance):
    """Verify expired link denies access."""
    data = {'files': (io.BytesIO(b"Expired link file"), 'expired.txt')}
    upload_res = auth_client.post('/api/files/upload', data=data, content_type='multipart/form-data')
    file_id = json.loads(upload_res.data)['uploaded'][0]['id']

    # Create link expired 1 hour ago
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    db_path = app_instance.config['DATABASE_PATH']
    link_record = db.create_share_link(
        db_path,
        file_id=file_id,
        user_id=1,
        share_token="expired_token_12345",
        permission="download",
        expires_at=past_time
    )

    # Accessing expired link
    view_res = client.get('/share/expired_token_12345')
    assert view_res.status_code == 410
    assert b"Link Expired" in view_res.data

    # Downloading expired link
    dl_res = client.get('/share/expired_token_12345/download')
    assert dl_res.status_code == 410
