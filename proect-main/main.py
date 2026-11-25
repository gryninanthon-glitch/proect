#Запуск сервера
#cmd
#cd C:\Users\Admin\OneDrive\Изображения\хз\proect-main\proect-main
#cd C:\Users\Ученик\Documents\tosha\d\sozvezdie_bot
#.venv\Scripts\activate
#Проверка кода
#python -m py_compile main.py routers/*.py utils.py
#.venv\Scripts\uvicorn.exe main:app --reload --ssl-keyfile key.pem --ssl-certfile cert.pem
#.venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem
# main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from database import init_db
from utils import seed_db
from routers import (
    auth, schedule, admin, notifications, polls,
    messages, info, tickets, lists, profile, hubs, groups,
)
import logging
import logging.handlers
import asyncio
import sys

if sys.platform == "win32":
    def silence_win_error_10054(loop, context):
        exception = context.get("exception")
        # Проверяем, что это именно ConnectionResetError с кодом 10054
        if isinstance(exception, ConnectionResetError) and getattr(exception, "winerror", None) == 10054:
            return  # Просто выходим, не логируем
        # Все остальные ошибки передаём стандартному обработчику
        loop.default_exception_handler(context)

    # Получаем текущий event loop и устанавливаем обработчик
    # (FastAPI/uvicorn используют один и тот же loop)
    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(silence_win_error_10054)
    except Exception:
        pass  # Если не получилось — не страшно, просто будет шум в логах

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(
            "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        ),
        logging.StreamHandler(),   # и в консоль
    ],
)
logger = logging.getLogger("sozvezdie")

app = FastAPI(max_body_size=50 * 1024 * 1024)  # максимум 50 МБ на запрос
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SessionMiddleware, secret_key="sozvezdie_super_secret_key")

logger.info("Приложение 'Созвездие' запущено")

init_db()
seed_db()

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "sozvezdie"}

app.include_router(groups.router)
app.include_router(hubs.router)
app.include_router(profile.router)
app.include_router(auth.router)
app.include_router(schedule.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(polls.router)
app.include_router(messages.router)
app.include_router(info.router)
app.include_router(tickets.router)
app.include_router(lists.router)