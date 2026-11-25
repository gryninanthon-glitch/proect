from database import engine
from sqlalchemy import text

with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE polls ADD COLUMN is_closed VARCHAR DEFAULT 'no'"))
        print("OK: добавлена колонка is_closed")
    except Exception as e:
        print("Уже есть или ошибка:", e)