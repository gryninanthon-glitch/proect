"""Одноразовый скрипт: добавляет колонку group_name в таблицу schedule."""
from database import engine
from sqlalchemy import text

with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE schedule ADD COLUMN group_name VARCHAR DEFAULT ''"))
        print("OK: добавлена колонка group_name")
    except Exception as e:
        print("Уже есть или ошибка:", e)