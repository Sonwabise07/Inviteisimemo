# Invitely Setup Guide

These commands are for PowerShell on Windows. Run them from the project folder:

```powershell
cd C:\Users\CC\Videos\invitely_secure
```

## First-time Setup

1. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

2. Create your local environment file if it does not exist yet:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and fill in your real values. At minimum, set `SECRET_KEY` and `FIRST_ADMIN_EMAIL`.

To generate a secure secret key:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

3. Initialize the database. Only run `db init` once for a fresh project:

```powershell
python -m flask db init
python -m flask db migrate -m "initial"
python -m flask db upgrade
```

If the `migrations` folder already exists, skip `python -m flask db init` and run only:

```powershell
python -m flask db migrate -m "your migration message"
python -m flask db upgrade
```

4. Create your admin account:

```powershell
python -m flask create-admin
```

Follow the prompts for email, name, and password.

5. Run the app:

```powershell
python app.py
```

Open the local URL shown in the terminal, usually `http://127.0.0.1:5000`.

## Quick Checks

Check that Python can see Flask:

```powershell
python -c "import importlib.metadata; print(importlib.metadata.version('flask'))"
```

Check that Flask can load this app:

```powershell
python -m flask --help
```

Check the database migration status:

```powershell
python -m flask db current
```

## Common Fixes

If you get `No module named flask`, install the dependencies again with the same Python command:

```powershell
python -m pip install -r requirements.txt
```

If `python -m flask db init` says the migrations directory already exists, that is okay. Skip `db init` and run:

```powershell
python -m flask db upgrade
```

If PowerShell says `flask` is not recognized, use:

```powershell
python -m flask ...
```

instead of:

```powershell
flask ...
```

## Production Notes

For PostgreSQL, install the driver:

```powershell
python -m pip install psycopg2-binary
```

Then set `DATABASE_URL` in `.env`, for example:

```env
DATABASE_URL=postgresql://user:password@host:5432/invitely_db
```

Apply migrations:

```powershell
python -m flask db upgrade
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | yes | Random 32+ character secret. |
| `DATABASE_URL` | production | PostgreSQL URL. Leave blank for local SQLite. |
| `MAIL_USERNAME` | email | Sender email address. |
| `MAIL_PASSWORD` | email | Email app password. |
| `MAIL_SERVER` | email | SMTP server, usually `smtp.gmail.com`. |
| `MAIL_PORT` | email | SMTP port, usually `587`. |
| `MAIL_USE_TLS` | email | Use `true` for TLS. |
| `FIRST_ADMIN_EMAIL` | yes | Email that should become the first admin. |
| `ADMIN_TOKEN` | optional | Legacy admin token, if needed. |
| `SESSION_COOKIE_SECURE` | production | Set `true` when serving over HTTPS. |
| `RATELIMIT_STORAGE_URL` | production | Redis URL for distributed rate limiting. |
| `ARCHIVE_AFTER_DAYS` | optional | Days before events are auto-archived. Default: `365`. |
