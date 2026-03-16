# ARFM — Autonomous Right to be Forgotten Manager

A zero-knowledge privacy tool that scans your Gmail for account sign-ups and sends legally-compliant data deletion requests (GDPR/CCPA) on your behalf.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![License](https://img.shields.io/badge/License-MIT-green)

## Architecture

```
ARFM/
├── Frontend (HTML/JS/CSS)     ← Static cybertech UI
│   ├── index.html             ← Landing page
│   ├── dashboard.html         ← Main dashboard
│   ├── connect.html           ← Google account connection
│   ├── scan.html              ← Scan results
│   ├── requests.html          ← Deletion request management
│   └── tracker.html           ← Request tracking
│
└── backend/                   ← FastAPI (Python)
    ├── auth/                  ← Google OAuth + encrypted cookies
    ├── api/                   ← REST endpoints
    ├── services/              ← Scanner, legal templates, email sender
    └── tests/                 ← 59 tests across 3 phases
```

## Key Features

- **Zero-Knowledge** — No database. Sessions are encrypted cookies via `itsdangerous`.
- **Gmail Scanning** — Regex-based detection of account creation emails (5,000 headers).
- **Legal Compliance** — Auto-generated GDPR Article 17 & CCPA Section 1798.105 emails.
- **Gmail Dispatch** — Sends deletion requests directly from the user's Gmail via the API.
- **Modular Design** — `BaseScanner` ABC allows swapping regex for AI inference.

## Quick Start

### Backend

```bash
cd backend
cp .env.example .env
# Fill in: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Swagger UI → [http://localhost:8000/docs](http://localhost:8000/docs)

### Docker

```bash
cd backend
docker-compose up --build
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/login` | Google OAuth authorization URL |
| `GET` | `/auth/callback` | Token exchange → encrypted cookie |
| `GET` | `/auth/status` | Check authentication state |
| `GET` | `/api/scan` | Scan Gmail for sign-up emails |
| `POST` | `/api/send-request` | Send GDPR/CCPA deletion email |

## Tests

```bash
cd backend
python -m pytest tests/ -v
# 59 passed ✅
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Google OAuth 2.0 client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 2.0 client secret |
| `FRONTEND_URL` | Frontend origin for CORS (default: `http://localhost:5173`) |
| `SECRET_KEY` | Secret key for signing encrypted cookies |

## Built By

**Krish Sarkar** — © 2026 ARFM
