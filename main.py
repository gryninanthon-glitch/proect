#Запуск сервера
#cmd
#cd C:\Users\Ученик\Documents\tosha\d\sozvezdie_bot
#.venv\Scripts\activate
#Проверка кода
#python -m py_compile main.py routers/*.py utils.py
#.venv\Scripts\uvicorn.exe main:app --reload --ssl-keyfile key.pem --ssl-certfile cert.pem
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

app = FastAPI(max_body_size=50 * 1024 * 1024)  # максимум 50 МБ на запрос
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SessionMiddleware, secret_key="sozvezdie_super_secret_key")

init_db()
seed_db()

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