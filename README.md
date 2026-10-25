# Cloud File Share — Cloud-Based File Storage and Sharing System

A production-ready cloud storage and secure file-sharing web application built with **Python Flask**, **SQLite**, and **Google Cloud Platform (GCP)** support. 

This project directly aligns with the **Cloud Computing Lab Manual** practicals:
1. **Web Application Development on Google App Engine**
2. **File Transfer and Storage between Virtual Machines and Cloud Services**

---

## 🌟 MVP Feature Overview

### 1. Modern Glassmorphic Dashboard
- **Storage Consumption Meter**: Real-time progress bar showing consumed storage vs. quota (100 MB free tier) with dynamic color thresholds (normal, warning, danger).
- **File Statistics**: Total files count, breakdown by category (Documents, Images, Audio, Video, Archives, Code).
- **Backend Environment Badge**: Visual indicator showing whether the active storage backend is `LOCAL` or `GOOGLE CLOUD STORAGE (GCS)`.

### 2. Full-Featured File Management
- **Multi-File Uploads**: Modern drag-and-drop zone + file browser supporting multiple concurrent uploads with real-time percentage progress bar.
- **Search & Filter**: Real-time keyword search by filename, category filter pills (All, Documents, Images, Videos, Audio, Code, Archives), and 6-way sorting (Newest, Oldest, Name A-Z, Name Z-A, Size Largest, Size Smallest).
- **Inline Previews**: Built-in modal previewer supporting images, PDFs, videos, audio players, and source code / text viewer.
- **Download & Deletion**: Direct file downloads with automatic download counter tracking and deletion modal with confirmation safeguards.

### 3. Secure File Sharing
- **Cryptographic Share Tokens**: URL-safe random tokens generated via `secrets.token_urlsafe(16)`.
- **Granular Permissions**:
  - `Allow Download & View`: Recipients can preview and download the file.
  - `View Only`: Recipients can only preview inside the browser. Direct downloads are strictly blocked with `HTTP 403 Forbidden`.
- **Link Expiration**: Configurable lifetime (1 Hour, 24 Hours, 7 Days, 30 Days, or Never).
- **Instant Revocation**: Owners can revoke any link with 1 click; revoked links immediately return `HTTP 410 Gone`.
- **Access Tracking**: Tracks visitation counts on shared links.

### 4. Authentication & Security
- User registration and login with secure password hashing (`scrypt` / `pbkdf2:sha256` via Werkzeug).
- Session management with protected routes and auto-redirects.
- Defense against directory traversal using `werkzeug.utils.secure_filename` and UUID-prefixed file naming.
- Enforced file size limits and file extension whitelisting.

---

## 🏗️ Technology Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript | Responsive glassmorphic UI, Lucide icons, drag-and-drop uploader |
| **Backend** | Python Flask (3.0.0+) | RESTful APIs, routing, and business logic |
| **Database** | SQLite3 (WAL mode) | Users, file metadata, share tokens, and access logs |
| **Local Storage** | Local filesystem (`uploads/`) | Development and local testing storage provider |
| **Cloud Storage** | Google Cloud Storage (GCS) | Production object storage on GCP |
| **Deployment** | Google App Engine / Cloud Run | Scalable serverless cloud web hosting (`app.yaml` & `Dockerfile`) |
| **Testing** | Pytest | Automated test suite verifying all 8 MVP requirements |

---

## 🚀 Quickstart Guide (Local Development)

### Step 1: Clone or Open the Workspace
```powershell
cd "Cloud-Based File Storage and Sharing System"
```

### Step 2: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Run the Application
```powershell
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

### Step 4: Run Automated Tests
```powershell
python -m pytest -v
```
All 19 test cases will run against isolated temporary databases and temporary upload directories:
```
tests/test_auth.py: 9 passed
tests/test_files.py: 6 passed
tests/test_sharing.py: 4 passed
Total: 19 passed
```

---

## ☁️ Google Cloud Deployment Guide

### Option A: Deploying to Google App Engine (GAE)
1. **Install Google Cloud SDK** and log in:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_GCP_PROJECT_ID
   ```
2. **Create a Google Cloud Storage Bucket**:
   ```bash
   gcloud storage buckets create gs://your-cloud-file-share-bucket --location=us-central1
   ```
3. **Configure `app.yaml`**:
   Update `GCS_BUCKET_NAME` with your bucket name:
   ```yaml
   env_variables:
     STORAGE_BACKEND: "gcs"
     GCS_BUCKET_NAME: "your-cloud-file-share-bucket"
     SECRET_KEY: "your-cryptographically-secure-key"
   ```
4. **Deploy**:
   ```bash
   gcloud app deploy app.yaml
   ```
5. **Open deployed app**:
   ```bash
   gcloud app browse
   ```

### Option B: Deploying to Google Cloud Run (Containerized)
1. **Build and deploy via Cloud Build**:
   ```bash
   gcloud run deploy cloud-file-share \
     --source . \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars STORAGE_BACKEND=gcs,GCS_BUCKET_NAME=your-cloud-file-share-bucket
   ```

---

## ✅ MVP Completion Verification Checklist

- [x] **Registration and login work** (verified with password hashing, session cookies, and validation)
- [x] **File upload and download work** (single & multi-file batch uploads, content integrity preserved)
- [x] **Search, sorting, and file deletion work** (name search, category filters, 6 sort modes, cascading delete)
- [x] **Dashboard shows real storage usage** (progress bar with color thresholds, quota calculations)
- [x] **Share links enforce permissions** (view-only permits browser preview while blocking downloads with 403)
- [x] **Expired and revoked links are blocked** (returns HTTP 410 Gone with clean user feedback)
- [x] **Automated tests pass** (19 comprehensive pytest tests passing with 100% success rate)
- [x] **Google Cloud deployment is configured** (`app.yaml`, `Dockerfile`, `.gcloudignore`, `requirements.txt`)

---

## 📂 Project Directory Structure

```
Cloud-Based File Storage and Sharing System/
│
├── app.py                      # Core Flask application factory & endpoints
├── config.py                   # Environment configuration (Local, Testing, Production)
├── database.py                 # SQLite database schema, connection & query methods
├── storage.py                  # Storage provider abstraction (Local & Google Cloud Storage)
├── requirements.txt            # Python dependencies
├── app.yaml                    # Google App Engine deployment configuration
├── Dockerfile                  # Container build file for Cloud Run / Docker
├── .gcloudignore               # Deployment exclusions for GCP
├── .gitignore                  # Git exclusions
├── .env.example                # Sample environment variables
├── README.md                   # Full documentation & lab practical reference
│
├── static/
│   ├── css/
│   │   └── style.css           # Glassmorphic responsive dark theme design system
│   └── js/
│       └── main.js             # Client uploader, drag-drop, previews, share modals, toast alerts
│
├── templates/
│   ├── base.html               # Main layout wrapper with navigation & toasts
│   ├── dashboard.html          # Interactive dashboard with stats, dropzone, table & modals
│   ├── share_view.html         # Public shared link viewing & download portal
│   ├── 404.html                # Error page
│   └── auth/
│       ├── login.html          # Login card
│       └── register.html       # User registration card
│
├── uploads/                    # Local storage directory for uploads (auto-created)
│
└── tests/
    ├── conftest.py             # Pytest fixtures with isolated temporary databases & storage
    ├── test_auth.py            # Registration, login, password hashing, session tests
    ├── test_files.py           # Upload, multi-file, download, search, filter, quota tests
    └── test_sharing.py         # Share links, permissions, expiration, revocation tests
```
