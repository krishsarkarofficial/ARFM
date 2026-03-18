"""
ARFM Backend — FastAPI Application Entry Point
Autonomous Right to be Forgotten Manager
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from auth.router import router as auth_router
from api.router import router as api_router

# ── App Initialization ──────────────────────────────────────────
app = FastAPI(
    title="ARFM — Autonomous Right to be Forgotten Manager",
    description="Zero-knowledge privacy tool for managing data deletion requests.",
    version="1.0.0",
)

# ── CORS Middleware ─────────────────────────────────────────────
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(api_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "ARFM Backend",
        "version": "1.0.0",
        "status": "operational",
    }


@app.get("/health", tags=["Root"])
async def health():
    return {"status": "healthy"}
