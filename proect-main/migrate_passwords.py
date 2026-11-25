"""
Одноразовый скрипт: хэширует все открытые пароли в БД.
Запустить ОДИН РАЗ после внедрения хэширования.
"""
from database import SessionLocal, User
from utils import hash_password


def migrate():
    db = SessionLocal()
    users = db.query(User).all()
    updated = 0
    for u in users:
        # Если пароль уже похож на bcrypt-хэш — пропускаем
        # (bcrypt-хэши начинаются с $2a$, $2b$ или $2y$)
        if u.access_code.startswith(("$2a$", "$2b$", "$2y$")):
            continue
        u.access_code = hash_password(u.access_code)
        updated += 1
    db.commit()
    db.close()
    print(f"Готово! Захэшировано паролей: {updated}")


if __name__ == "__main__":
    migrate()