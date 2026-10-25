import os
import secrets
import mimetypes
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort, make_response
)
from werkzeug.utils import secure_filename

from config import config_by_name, Config
import database as db
from storage import get_storage_provider

def determine_category(ext):
    """Categorize file based on extension."""
    ext = ext.lower().lstrip('.')
    image_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico'}
    doc_exts = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'txt', 'rtf', 'odt'}
    audio_exts = {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac'}
    video_exts = {'mp4', 'webm', 'mov', 'mkv', 'avi'}
    archive_exts = {'zip', 'tar', 'gz', '7z', 'rar'}
    code_exts = {'py', 'js', 'html', 'css', 'json', 'xml', 'sql', 'md', 'sh', 'java', 'cpp', 'c', 'ts', 'jsx', 'tsx'}
    
    if ext in image_exts:
        return 'image'
    elif ext in doc_exts:
        return 'document'
    elif ext in audio_exts:
        return 'audio'
    elif ext in video_exts:
        return 'video'
    elif ext in archive_exts:
        return 'archive'
    elif ext in code_exts:
        return 'code'
    return 'other'

def format_bytes(size):
    """Format bytes into readable units."""
    if size is None or size == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    s = float(size)
    while s >= 1024.0 and unit_idx < len(units) - 1:
        s /= 1024.0
        unit_idx += 1
    return f"{s:.1f} {units[unit_idx]}" if unit_idx > 0 else f"{int(s)} B"

def login_required(f):
    """Decorator to require login for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def create_app(config_name=None):
    """Application factory for Cloud File Share."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    app_config = config_by_name.get(config_name, Config)
    app.config.from_object(app_config)

    # Initialize Database & Storage
    db.init_db(app.config['DATABASE_PATH'])
    storage_provider = get_storage_provider(app.config)
    app.storage_provider = storage_provider

    # Template Jinja filters
    @app.template_filter('format_bytes')
    def filter_format_bytes(s):
        return format_bytes(s)

    @app.template_filter('format_datetime')
    def filter_format_datetime(val):
        if not val:
            return "N/A"
        try:
            if isinstance(val, str):
                dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            else:
                dt = val
            return dt.strftime("%b %d, %Y %I:%M %p")
        except Exception:
            return str(val)

    # Context processor for templates
    @app.context_processor
    def inject_user():
        current_user = None
        if 'user_id' in session:
            current_user = db.get_user_by_id(app.config['DATABASE_PATH'], session['user_id'])
        return dict(current_user=current_user)

    # ----------------- Auth Routes -----------------

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')

            # Validation
            if not username or len(username) < 3:
                flash('Username must be at least 3 characters long.', 'danger')
                return render_template('auth/register.html', username=username, email=email)
            if not email or '@' not in email:
                flash('Please enter a valid email address.', 'danger')
                return render_template('auth/register.html', username=username, email=email)
            if not password or len(password) < 6:
                flash('Password must be at least 6 characters long.', 'danger')
                return render_template('auth/register.html', username=username, email=email)
            if password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return render_template('auth/register.html', username=username, email=email)

            # Check existing
            if db.get_user_by_username(app.config['DATABASE_PATH'], username):
                flash('Username already registered. Please choose another.', 'danger')
                return render_template('auth/register.html', username=username, email=email)
            if db.get_user_by_email(app.config['DATABASE_PATH'], email):
                flash('Email already registered. Please login.', 'danger')
                return render_template('auth/register.html', username=username, email=email)

            # Create User
            user = db.create_user(
                app.config['DATABASE_PATH'],
                username=username,
                email=email,
                password=password,
                storage_quota=app.config['DEFAULT_USER_QUOTA']
            )
            if user:
                session.permanent = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash('Registration successful! Welcome to Cloud File Share.', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('An error occurred during registration. Please try again.', 'danger')

        return render_template('auth/register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            identifier = request.form.get('identifier', '').strip()
            password = request.form.get('password', '')

            if not identifier or not password:
                flash('Please enter both username/email and password.', 'danger')
                return render_template('auth/login.html', identifier=identifier)

            user = db.verify_user(app.config['DATABASE_PATH'], identifier, password)
            if user:
                session.permanent = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash(f"Welcome back, {user['username']}!", 'success')
                next_url = request.args.get('next')
                return redirect(next_url or url_for('dashboard'))
            else:
                flash('Invalid username/email or password.', 'danger')

        return render_template('auth/login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out securely.', 'info')
        return redirect(url_for('login'))

    # ----------------- Dashboard & File Routes -----------------

    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        user_id = session['user_id']
        db_path = app.config['DATABASE_PATH']
        
        # User details & Quotas
        user = db.get_user_by_id(db_path, user_id)
        storage_used = db.get_user_storage_used(db_path, user_id)
        storage_quota = user.get('storage_quota', app.config['DEFAULT_USER_QUOTA'])
        storage_percent = min(100.0, (storage_used / storage_quota * 100)) if storage_quota > 0 else 0
        total_files = db.get_user_file_count(db_path, user_id)
        category_breakdown = db.get_user_category_breakdown(db_path, user_id)

        # Filters & Sorting
        search_query = request.args.get('q', '').strip()
        category_filter = request.args.get('category', 'all')
        sort_by = request.args.get('sort', 'date_desc')

        files = db.get_user_files(
            db_path,
            user_id=user_id,
            search_query=search_query,
            category=category_filter,
            sort_by=sort_by
        )

        # Recent uploads (top 5 latest)
        recent_files = db.get_user_files(db_path, user_id, sort_by='date_desc')[:5]

        # All share links created by user
        share_links = db.get_user_all_share_links(db_path, user_id)

        return render_template(
            'dashboard.html',
            user=user,
            files=files,
            recent_files=recent_files,
            share_links=share_links,
            storage_used=storage_used,
            storage_quota=storage_quota,
            storage_percent=round(storage_percent, 1),
            total_files=total_files,
            category_breakdown=category_breakdown,
            search_query=search_query,
            category_filter=category_filter,
            sort_by=sort_by,
            storage_backend=app.config.get('STORAGE_BACKEND', 'local').upper()
        )

    @app.route('/api/files/upload', methods=['POST'])
    @login_required
    def upload_files():
        """Upload one or multiple files."""
        user_id = session['user_id']
        db_path = app.config['DATABASE_PATH']
        
        if 'files' not in request.files and 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded.'}), 400

        uploaded_items = request.files.getlist('files')
        if not uploaded_items or (len(uploaded_items) == 1 and uploaded_items[0].filename == ''):
            # check single 'file' parameter
            single_file = request.files.get('file')
            if single_file and single_file.filename != '':
                uploaded_items = [single_file]
            else:
                return jsonify({'success': False, 'error': 'No file selected.'}), 400

        user = db.get_user_by_id(db_path, user_id)
        storage_quota = user.get('storage_quota', app.config['DEFAULT_USER_QUOTA'])
        current_used = db.get_user_storage_used(db_path, user_id)

        saved_files = []
        errors = []

        for f in uploaded_items:
            if not f or f.filename == '':
                continue
            
            orig_name = secure_filename(f.filename)
            if not orig_name:
                orig_name = f"file_{secrets.token_hex(4)}"

            # Extension check
            ext = orig_name.rsplit('.', 1)[-1].lower() if '.' in orig_name else ''
            if app.config['ALLOWED_EXTENSIONS'] and ext not in app.config['ALLOWED_EXTENSIONS']:
                errors.append(f"File '{orig_name}' has an unsupported file type.")
                continue

            # Read content / calculate size
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(0)

            if size > app.config['MAX_CONTENT_LENGTH']:
                errors.append(f"File '{orig_name}' ({format_bytes(size)}) exceeds maximum limit of {format_bytes(app.config['MAX_CONTENT_LENGTH'])}.")
                continue

            if current_used + size > storage_quota:
                errors.append(f"Uploading '{orig_name}' would exceed your storage quota ({format_bytes(storage_quota)}).")
                continue

            # Detect MIME and Category
            category = determine_category(ext)
            mime_type, _ = mimetypes.guess_type(orig_name)
            if not mime_type:
                mime_type = 'application/octet-stream'

            # Unique stored filename with UUID
            unique_prefix = secrets.token_hex(16)
            stored_name = f"{unique_prefix}_{orig_name}"

            # Save via storage provider
            try:
                storage_path = app.storage_provider.save(f, stored_name)
                saved_record = db.add_file(
                    db_path=db_path,
                    user_id=user_id,
                    original_filename=orig_name,
                    stored_filename=stored_name,
                    file_size=size,
                    file_type=mime_type,
                    category=category,
                    storage_path=storage_path
                )
                current_used += size
                saved_files.append(saved_record)
            except Exception as e:
                errors.append(f"Failed to store '{orig_name}': {str(e)}")

        if not saved_files and errors:
            return jsonify({'success': False, 'errors': errors}), 400

        return jsonify({
            'success': True,
            'uploaded': [
                {
                    'id': f['id'],
                    'original_filename': f['original_filename'],
                    'file_size': f['file_size'],
                    'formatted_size': format_bytes(f['file_size']),
                    'category': f['category'],
                    'created_at': f['created_at']
                } for f in saved_files
            ],
            'errors': errors
        })

    @app.route('/api/files/<int:file_id>/download')
    @login_required
    def download_file(file_id):
        """Download user's own file."""
        user_id = session['user_id']
        db_path = app.config['DATABASE_PATH']
        file_record = db.get_file_by_id(db_path, file_id)

        if not file_record or file_record['user_id'] != user_id:
            abort(404)

        db.increment_file_downloads(db_path, file_id)
        return app.storage_provider.serve_file(
            file_record['stored_filename'],
            file_record['original_filename'],
            as_attachment=True,
            mimetype=file_record['file_type']
        )

    @app.route('/api/files/<int:file_id>/preview')
    @login_required
    def preview_file(file_id):
        """Preview inline (images, pdfs, text)."""
        user_id = session['user_id']
        db_path = app.config['DATABASE_PATH']
        file_record = db.get_file_by_id(db_path, file_id)

        if not file_record or file_record['user_id'] != user_id:
            abort(404)

        return app.storage_provider.serve_file(
            file_record['stored_filename'],
            file_record['original_filename'],
            as_attachment=False,
            mimetype=file_record['file_type']
        )

    @app.route('/api/files/<int:file_id>/delete', methods=['POST', 'DELETE'])
    @login_required
    def delete_file_endpoint(file_id):
        """Delete user's file and remove from storage."""
        user_id = session['user_id']
        db_path = app.config['DATABASE_PATH']

        file_record = db.delete_file(db_path, file_id, user_id)
        if not file_record:
            return jsonify({'success': False, 'error': 'File not found or permission denied.'}), 404

        # Delete physical object
        app.storage_provider.delete(file_record['stored_filename'])

        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'File deleted successfully.'})
        flash(f"File '{file_record['original_filename']}' deleted successfully.", 'success')
        return redirect(url_for('dashboard'))

    @app.route('/api/files/stats')
    @login_required
    def file_stats():
        """Return storage usage and count stats."""
        user_id = session['user_id']
        db_path = app.config['DATABASE_PATH']
        user = db.get_user_by_id(db_path, user_id)
        storage_used = db.get_user_storage_used(db_path, user_id)
        storage_quota = user.get('storage_quota', app.config['DEFAULT_USER_QUOTA'])
        total_files = db.get_user_file_count(db_path, user_id)
        breakdown = db.get_user_category_breakdown(db_path, user_id)

        return jsonify({
            'storage_used': storage_used,
            'storage_used_formatted': format_bytes(storage_used),
            'storage_quota': storage_quota,
            'storage_quota_formatted': format_bytes(storage_quota),
            'storage_percent': round(min(100.0, (storage_used / storage_quota * 100)), 1) if storage_quota > 0 else 0,
            'total_files': total_files,
            'category_breakdown': breakdown
        })

    # ----------------- Secure Share Routes -----------------

    @app.route('/api/files/<int:file_id>/share', methods=['POST'])
    @login_required
    def create_file_share(file_id):
        """Generate a secure sharing link."""
        user_id = session['user_id']
        db_path = app.config['DATABASE_PATH']
        file_record = db.get_file_by_id(db_path, file_id)

        if not file_record or file_record['user_id'] != user_id:
            return jsonify({'success': False, 'error': 'File not found or unauthorized.'}), 404

        data = request.get_json(silent=True) or request.form
        permission = data.get('permission', 'download').lower()
        if permission not in ('view', 'download'):
            permission = 'download'

        expiry_option = data.get('expires_in', 'never')
        expires_at = None
        now = datetime.now(timezone.utc)
        
        if expiry_option == '1h':
            expires_at = (now + timedelta(hours=1)).isoformat()
        elif expiry_option == '24h':
            expires_at = (now + timedelta(hours=24)).isoformat()
        elif expiry_option == '7d':
            expires_at = (now + timedelta(days=7)).isoformat()
        elif expiry_option == '30d':
            expires_at = (now + timedelta(days=30)).isoformat()

        share_token = secrets.token_urlsafe(16)
        share_record = db.create_share_link(
            db_path=db_path,
            file_id=file_id,
            user_id=user_id,
            share_token=share_token,
            permission=permission,
            expires_at=expires_at
        )

        share_url = url_for('view_shared_file', token=share_token, _external=True)

        return jsonify({
            'success': True,
            'share_token': share_token,
            'share_url': share_url,
            'permission': permission,
            'expires_at': expires_at,
            'link_id': share_record['id']
        })

    @app.route('/api/share/<int:link_id>/revoke', methods=['POST'])
    @login_required
    def revoke_share(link_id):
        """Revoke a shared link."""
        user_id = session['user_id']
        db_path = app.config['DATABASE_PATH']
        success = db.revoke_share_link(db_path, link_id, user_id)
        if success:
            return jsonify({'success': True, 'message': 'Share link revoked successfully.'})
        return jsonify({'success': False, 'error': 'Link not found or unauthorized.'}), 404

    @app.route('/share/<token>')
    def view_shared_file(token):
        """Public recipient view for a shared file."""
        db_path = app.config['DATABASE_PATH']
        link = db.get_share_link_by_token(db_path, token)

        if not link:
            return render_template('share_view.html', error_title="Link Not Found",
                                   error_message="This share link does not exist or may have been deleted.", status="not_found"), 404

        if link['is_revoked']:
            return render_template('share_view.html', error_title="Link Revoked",
                                   error_message="The owner has revoked access to this file link.", status="revoked"), 410

        # Check expiration
        is_expired = False
        if link['expires_at']:
            try:
                exp_dt = datetime.fromisoformat(link['expires_at'].replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if now > exp_dt:
                    is_expired = True
            except (ValueError, TypeError):
                pass

        if is_expired:
            return render_template('share_view.html', error_title="Link Expired",
                                   error_message="This share link has expired and is no longer accessible.", status="expired"), 410

        # Increment access count
        db.increment_share_access(db_path, token)

        return render_template(
            'share_view.html',
            link=link,
            status="active",
            download_url=url_for('download_shared_file', token=token) if link['permission'] == 'download' else None,
            preview_url=url_for('preview_shared_file', token=token)
        )

    @app.route('/share/<token>/download')
    def download_shared_file(token):
        """Public endpoint to download a shared file."""
        db_path = app.config['DATABASE_PATH']
        link = db.get_share_link_by_token(db_path, token)

        if not link:
            abort(404)
        if link['is_revoked']:
            abort(410)

        # Check expiration
        if link['expires_at']:
            try:
                exp_dt = datetime.fromisoformat(link['expires_at'].replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if now > exp_dt:
                    abort(410)
            except (ValueError, TypeError):
                pass

        # Check permission enforcement
        if link['permission'] != 'download':
            return make_response(jsonify({'error': 'Download permission denied. This link is view-only.'}), 403)

        db.increment_file_downloads(db_path, link['file_id'])

        return app.storage_provider.serve_file(
            link['stored_filename'],
            link['original_filename'],
            as_attachment=True,
            mimetype=link['file_type']
        )

    @app.route('/share/<token>/preview')
    def preview_shared_file(token):
        """Public endpoint to stream file inline for preview."""
        db_path = app.config['DATABASE_PATH']
        link = db.get_share_link_by_token(db_path, token)

        if not link or link['is_revoked']:
            abort(404)

        if link['expires_at']:
            try:
                exp_dt = datetime.fromisoformat(link['expires_at'].replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if now > exp_dt:
                    abort(410)
            except (ValueError, TypeError):
                pass

        return app.storage_provider.serve_file(
            link['stored_filename'],
            link['original_filename'],
            as_attachment=False,
            mimetype=link['file_type']
        )

    # ----------------- Error Handlers -----------------

    @app.errorhandler(404)
    def not_found_error(error):
        if request.is_json:
            return jsonify({'error': 'Resource not found'}), 404
        return render_template('404.html'), 404

    @app.errorhandler(410)
    def gone_error(error):
        if request.is_json:
            return jsonify({'error': 'Resource has expired or was revoked'}), 410
        return render_template('share_view.html', error_title="Link Expired or Revoked",
                               error_message="The requested link has either expired or been revoked.", status="expired"), 410

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({'error': f'File exceeds maximum upload limit of {format_bytes(app.config["MAX_CONTENT_LENGTH"])}'}), 413

    return app

if __name__ == '__main__':
    # Local development runner
    app = create_app('development')
    port = int(os.environ.get('PORT', 5000))
    print(f"[*] Cloud File Share starting on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
