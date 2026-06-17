"""Точка входа FastAPI: CORS, middleware безопасности, подключение роутеров, обработка ошибок."""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routers import academy, auth, users

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Digital Academy API",
    version="1.0.0",
    description="Платформа образовательного учреждения: авторизация, RBAC, учебная часть.",
)

ALLOWED_ORIGINS = [
    settings.FRONTEND_URL,
    "https://msdig.kz",
    "https://www.msdig.kz",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(ALLOWED_ORIGINS)),  # без дублей
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-CSRF-Token"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(academy.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logging.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера"})
