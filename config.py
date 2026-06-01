import os
from dotenv import load_dotenv

# Load .env file for local development
load_dotenv()

class Config:
    # ── Core ──────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-only-change-in-production-NOW'
    BASE_DIR   = os.path.abspath(os.path.dirname(__file__))

    # ── Database ──────────────────────────────────────────────
    # Supports PostgreSQL in production via DATABASE_URL env var
    # Falls back to local SQLite for development
    _db_url = os.environ.get('DATABASE_URL', '')
    if _db_url.startswith('postgres://'):
        # Heroku/Railway give postgres://, SQLAlchemy needs postgresql://
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url or 'sqlite:///' + os.path.join(BASE_DIR, 'invitely.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── File uploads ──────────────────────────────────────────
    UPLOAD_FOLDER      = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    S3_ENDPOINT_URL    = os.environ.get('S3_ENDPOINT_URL', '')
    S3_ACCESS_KEY_ID   = os.environ.get('S3_ACCESS_KEY_ID', '')
    S3_SECRET_ACCESS_KEY = os.environ.get('S3_SECRET_ACCESS_KEY', '')
    S3_BUCKET_NAME     = os.environ.get('S3_BUCKET_NAME', '')
    S3_REGION          = os.environ.get('S3_REGION', 'auto')
    S3_PUBLIC_URL      = os.environ.get('S3_PUBLIC_URL', '').rstrip('/')

    # ── Mail ──────────────────────────────────────────────────
    MAIL_SERVER        = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT          = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS       = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME      = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD      = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = ('Invitisimemo', os.environ.get('MAIL_USERNAME', 'noreply@invitisimemo.co.za'))
    CONTACT_EMAIL      = os.environ.get('CONTACT_EMAIL', os.environ.get('MAIL_USERNAME', 'inviteisimemo@gmail.com'))

    # ── CSRF (Flask-WTF) ──────────────────────────────────────
    WTF_CSRF_ENABLED     = True
    WTF_CSRF_TIME_LIMIT  = 3600  # 1 hour token lifetime

    # ── Session cookies ───────────────────────────────────────
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Set to True in production (requires HTTPS)
    SESSION_COOKIE_SECURE   = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14  # 14 days

    # ── Admin ─────────────────────────────────────────────────
    # Email of the first admin account — this user gets is_admin=True on first login
    FIRST_ADMIN_EMAIL = os.environ.get('FIRST_ADMIN_EMAIL', '')
    # Legacy token for old admin access (kept for transition, removed later)
    ADMIN_TOKEN       = os.environ.get('ADMIN_TOKEN', '')

    # ── Rate limiting ─────────────────────────────────────────
    # Use Redis in production: RATELIMIT_STORAGE_URL=redis://localhost:6379/0
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    RATELIMIT_HEADERS_ENABLED = True

    # ── Data retention ────────────────────────────────────────
    # Auto-archive events older than this many days (0 = disabled)
    ARCHIVE_AFTER_DAYS = int(os.environ.get('ARCHIVE_AFTER_DAYS', 365))

    # ── PayFast payments ──────────────────────────────────────
    PAYFAST_MERCHANT_ID  = os.environ.get('PAYFAST_MERCHANT_ID', '')
    PAYFAST_MERCHANT_KEY = os.environ.get('PAYFAST_MERCHANT_KEY', '')
    PAYFAST_PASSPHRASE   = os.environ.get('PAYFAST_PASSPHRASE', '')
    PAYFAST_SANDBOX      = os.environ.get('PAYFAST_SANDBOX', 'true').lower() == 'true'
    SUBSCRIPTION_PRICE_ZAR = float(os.environ.get('SUBSCRIPTION_PRICE_ZAR', '99'))
    # Pay-per-invite: one-off unlock for a single invitation (no subscription)
    SINGLE_INVITE_PRICE_ZAR = float(os.environ.get('SINGLE_INVITE_PRICE_ZAR', '15'))
    APP_BASE_URL         = os.environ.get('APP_BASE_URL', '')
