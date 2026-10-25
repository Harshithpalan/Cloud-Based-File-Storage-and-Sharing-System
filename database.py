import sqlite3
import os
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

def get_db_connection(db_path):
    """Establish connection to SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path):
    """Initialize database tables with indexes."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        storage_quota INTEGER NOT NULL DEFAULT 104857600, -- 100 MB default
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Files Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        original_filename TEXT NOT NULL,
        stored_filename TEXT NOT NULL UNIQUE,
        file_size INTEGER NOT NULL,
        file_type TEXT NOT NULL,
        category TEXT NOT NULL,
        storage_path TEXT NOT NULL,
        download_count INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Share Links Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS share_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        share_token TEXT NOT NULL UNIQUE,
        permission TEXT NOT NULL DEFAULT 'download', -- 'view' or 'download'
        expires_at TIMESTAMP NULL,
        is_revoked INTEGER NOT NULL DEFAULT 0,
        access_count INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Performance Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_user ON files(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_category ON files(category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_share_token ON share_links(share_token);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_share_file ON share_links(file_id);")

    conn.commit()
    conn.close()

# User Management Functions
def create_user(db_path, username, email, password, storage_quota=104857600):
    """Create a new user with hashed password."""
    password_hash = generate_password_hash(password)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, storage_quota) VALUES (?, ?, ?, ?)",
            (username.strip(), email.strip().lower(), password_hash, storage_quota)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return get_user_by_id(db_path, user_id)
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_id(db_path, user_id):
    """Retrieve user by ID."""
    conn = get_db_connection(db_path)
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_username(db_path, username):
    """Retrieve user by username."""
    conn = get_db_connection(db_path)
    user = conn.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_email(db_path, email):
    """Retrieve user by email."""
    conn = get_db_connection(db_path)
    user = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
    conn.close()
    return dict(user) if user else None

def verify_user(db_path, identifier, password):
    """Authenticate user with username or email and password."""
    conn = get_db_connection(db_path)
    user = conn.execute(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
        (identifier.strip(), identifier.strip())
    ).fetchone()
    conn.close()
    if user and check_password_hash(user['password_hash'], password):
        return dict(user)
    return None

# File Management Functions
def add_file(db_path, user_id, original_filename, stored_filename, file_size, file_type, category, storage_path):
    """Record a newly uploaded file in the database."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO files (user_id, original_filename, stored_filename, file_size, file_type, category, storage_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, original_filename, stored_filename, file_size, file_type, category, storage_path))
    conn.commit()
    file_id = cursor.lastrowid
    conn.close()
    return get_file_by_id(db_path, file_id)

def get_file_by_id(db_path, file_id):
    """Retrieve file metadata by file ID."""
    conn = get_db_connection(db_path)
    f = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    conn.close()
    return dict(f) if f else None

def get_file_by_stored_name(db_path, stored_filename):
    """Retrieve file metadata by stored unique filename."""
    conn = get_db_connection(db_path)
    f = conn.execute("SELECT * FROM files WHERE stored_filename = ?", (stored_filename,)).fetchone()
    conn.close()
    return dict(f) if f else None

def get_user_files(db_path, user_id, search_query=None, category=None, sort_by='date_desc'):
    """Fetch files for a user with search, filtering, and sorting."""
    conn = get_db_connection(db_path)
    query = "SELECT * FROM files WHERE user_id = ?"
    params = [user_id]

    if search_query:
        query += " AND original_filename LIKE ?"
        params.append(f"%{search_query.strip()}%")

    if category and category.lower() != 'all':
        query += " AND category = ?"
        params.append(category.lower())

    sort_options = {
        'date_desc': 'created_at DESC',
        'date_asc': 'created_at ASC',
        'name_asc': 'original_filename ASC',
        'name_desc': 'original_filename DESC',
        'size_desc': 'file_size DESC',
        'size_asc': 'file_size ASC'
    }
    order_clause = sort_options.get(sort_by, 'created_at DESC')
    query += f" ORDER BY {order_clause}"

    files = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in files]

def get_user_storage_used(db_path, user_id):
    """Calculate total storage consumed by user in bytes."""
    conn = get_db_connection(db_path)
    res = conn.execute("SELECT COALESCE(SUM(file_size), 0) AS total_bytes FROM files WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return res['total_bytes'] if res else 0

def get_user_file_count(db_path, user_id):
    """Calculate total files owned by user."""
    conn = get_db_connection(db_path)
    res = conn.execute("SELECT COUNT(*) AS total_count FROM files WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return res['total_count'] if res else 0

def get_user_category_breakdown(db_path, user_id):
    """Get count and storage size grouped by file category."""
    conn = get_db_connection(db_path)
    rows = conn.execute("""
        SELECT category, COUNT(*) as count, COALESCE(SUM(file_size), 0) as total_size
        FROM files
        WHERE user_id = ?
        GROUP BY category
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_file(db_path, file_id, user_id):
    """Delete a file belonging to a specific user."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    f = conn.execute("SELECT * FROM files WHERE id = ? AND user_id = ?", (file_id, user_id)).fetchone()
    if not f:
        conn.close()
        return None
    cursor.execute("DELETE FROM files WHERE id = ? AND user_id = ?", (file_id, user_id))
    conn.commit()
    conn.close()
    return dict(f)

def increment_file_downloads(db_path, file_id):
    """Increment the download count for a file."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE files SET download_count = download_count + 1 WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()

# Share Links Management Functions
def create_share_link(db_path, file_id, user_id, share_token, permission='download', expires_at=None):
    """Generate a share link for a user's file."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO share_links (file_id, user_id, share_token, permission, expires_at)
        VALUES (?, ?, ?, ?, ?)
    """, (file_id, user_id, share_token, permission, expires_at))
    conn.commit()
    link_id = cursor.lastrowid
    conn.close()
    return get_share_link_by_id(db_path, link_id)

def get_share_link_by_id(db_path, link_id):
    """Get share link record by ID with joined file info."""
    conn = get_db_connection(db_path)
    row = conn.execute("""
        SELECT s.*, f.original_filename, f.file_size, f.file_type, f.category, f.stored_filename, u.username as owner_username
        FROM share_links s
        JOIN files f ON s.file_id = f.id
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
    """, (link_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_share_link_by_token(db_path, share_token):
    """Retrieve full share link details by token."""
    conn = get_db_connection(db_path)
    row = conn.execute("""
        SELECT s.*, f.original_filename, f.file_size, f.file_type, f.category, f.stored_filename, f.storage_path, u.username as owner_username
        FROM share_links s
        JOIN files f ON s.file_id = f.id
        JOIN users u ON s.user_id = u.id
        WHERE s.share_token = ?
    """, (share_token,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_file_share_links(db_path, file_id, user_id):
    """Get all share links generated for a specific file."""
    conn = get_db_connection(db_path)
    rows = conn.execute("""
        SELECT * FROM share_links
        WHERE file_id = ? AND user_id = ?
        ORDER BY created_at DESC
    """, (file_id, user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_all_share_links(db_path, user_id):
    """Get all active and revoked share links created by the user."""
    conn = get_db_connection(db_path)
    rows = conn.execute("""
        SELECT s.*, f.original_filename, f.file_size, f.category
        FROM share_links s
        JOIN files f ON s.file_id = f.id
        WHERE s.user_id = ?
        ORDER BY s.created_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def revoke_share_link(db_path, link_id, user_id):
    """Revoke a share link so it can no longer be accessed."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE share_links
        SET is_revoked = 1
        WHERE id = ? AND user_id = ?
    """, (link_id, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def increment_share_access(db_path, share_token):
    """Increment access counter on a share link."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE share_links SET access_count = access_count + 1 WHERE share_token = ?", (share_token,))
    conn.commit()
    conn.close()
