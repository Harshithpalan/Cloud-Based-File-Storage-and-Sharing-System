import io
import json
import pytest
import database as db

def test_file_upload_single(auth_client, app_instance, registered_user):
    """Verify single file upload saves file to disk and records metadata."""
    data = {
        'files': (io.BytesIO(b"Hello Cloud File Share World!"), 'notes.txt')
    }
    response = auth_client.post(
        '/api/files/upload',
        data=data,
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 200
    res_data = json.loads(response.data)
    assert res_data['success'] is True
    assert len(res_data['uploaded']) == 1
    assert res_data['uploaded'][0]['original_filename'] == 'notes.txt'
    assert res_data['uploaded'][0]['category'] == 'document'

    # Verify database state
    user_files = db.get_user_files(app_instance.config['DATABASE_PATH'], registered_user['id'])
    assert len(user_files) == 1
    assert user_files[0]['original_filename'] == 'notes.txt'
    assert user_files[0]['file_size'] == len(b"Hello Cloud File Share World!")

def test_file_upload_multiple(auth_client, app_instance, registered_user):
    """Verify multiple files can be uploaded simultaneously."""
    data = {
        'files': [
            (io.BytesIO(b"File One Content"), 'doc1.pdf'),
            (io.BytesIO(b"File Two Content"), 'picture.png')
        ]
    }
    response = auth_client.post(
        '/api/files/upload',
        data=data,
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 200
    res_data = json.loads(response.data)
    assert res_data['success'] is True
    assert len(res_data['uploaded']) == 2

    # Check categories
    cats = {f['original_filename']: f['category'] for f in res_data['uploaded']}
    assert cats['doc1.pdf'] == 'document'
    assert cats['picture.png'] == 'image'

def test_file_download(auth_client, app_instance, registered_user):
    """Verify user can download their uploaded file with full content."""
    file_content = b"Lab Manual Cloud App Engine Practical Data"
    data = {'files': (io.BytesIO(file_content), 'cloud_lab.txt')}
    upload_res = auth_client.post('/api/files/upload', data=data, content_type='multipart/form-data')
    file_id = json.loads(upload_res.data)['uploaded'][0]['id']

    # Download file
    download_res = auth_client.get(f'/api/files/{file_id}/download')
    assert download_res.status_code == 200
    assert download_res.data == file_content
    assert 'attachment' in download_res.headers.get('Content-Disposition', '')
    assert 'cloud_lab.txt' in download_res.headers.get('Content-Disposition', '')

    # Verify download count incremented
    file_meta = db.get_file_by_id(app_instance.config['DATABASE_PATH'], file_id)
    assert file_meta['download_count'] == 1

def test_file_search_and_filter(auth_client, app_instance):
    """Verify search query and category filtering."""
    files_to_upload = [
        (io.BytesIO(b"report content"), 'annual_report.pdf'),
        (io.BytesIO(b"invoice content"), 'march_invoice.pdf'),
        (io.BytesIO(b"profile photo"), 'avatar.jpg'),
        (io.BytesIO(b"script code"), 'backup.py')
    ]
    for stream, fname in files_to_upload:
        auth_client.post('/api/files/upload', data={'files': (stream, fname)}, content_type='multipart/form-data')

    # Search for 'invoice'
    res_search = auth_client.get('/dashboard?q=invoice')
    assert res_search.status_code == 200
    assert b"march_invoice.pdf" in res_search.data
    assert b"annual_report.pdf" not in res_search.data

    # Filter by category 'image'
    res_cat = auth_client.get('/dashboard?category=image')
    assert res_cat.status_code == 200
    assert b"avatar.jpg" in res_cat.data
    assert b"annual_report.pdf" not in res_cat.data

def test_storage_quota_calculation_and_enforcement(auth_client, app_instance, registered_user):
    """Verify storage used tracking and rejection when quota exceeded."""
    # Check initial stats
    stats_res = auth_client.get('/api/files/stats')
    initial_stats = json.loads(stats_res.data)
    assert initial_stats['storage_used'] == 0

    # Upload 1 KB file
    kb_data = b"x" * 1024
    auth_client.post('/api/files/upload', data={'files': (io.BytesIO(kb_data), 'small.txt')}, content_type='multipart/form-data')

    # Verify updated stats
    stats_res2 = auth_client.get('/api/files/stats')
    updated_stats = json.loads(stats_res2.data)
    assert updated_stats['storage_used'] == 1024
    assert updated_stats['total_files'] == 1

    # Attempt to upload 20 MB file when test quota is 10 MB
    big_data = b"x" * (20 * 1024 * 1024)
    big_res = auth_client.post('/api/files/upload', data={'files': (io.BytesIO(big_data), 'huge.zip')}, content_type='multipart/form-data')
    assert big_res.status_code == 400
    assert b"exceed" in big_res.data

def test_file_deletion(auth_client, app_instance, registered_user):
    """Verify file deletion cleans up database and physical storage."""
    data = {'files': (io.BytesIO(b"Delete me please"), 'temp_file.txt')}
    upload_res = auth_client.post('/api/files/upload', data=data, content_type='multipart/form-data')
    file_id = json.loads(upload_res.data)['uploaded'][0]['id']

    # Delete file
    del_res = auth_client.post(
        f'/api/files/{file_id}/delete',
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert del_res.status_code == 200
    assert json.loads(del_res.data)['success'] is True

    # Check database: record should no longer exist
    assert db.get_file_by_id(app_instance.config['DATABASE_PATH'], file_id) is None

    # Check storage: total storage should now be 0
    assert db.get_user_storage_used(app_instance.config['DATABASE_PATH'], registered_user['id']) == 0
