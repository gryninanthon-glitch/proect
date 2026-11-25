from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

# Создаем файл базы данных (он появится в папке как sozvezdie.db)
SQLALCHEMY_DATABASE_URL = "sqlite:///./sozvezdie.db"

# Движок для подключения (check_same_thread=False нужен для SQLite)
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# Фабрика сессий (через нее мы будем общаться с базой)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для наших таблиц
Base = declarative_base()

# --- ОПИСЫВАЕМ ТАБЛИЦУ ПОЛЬЗОВАТЕЛЕЙ ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    max_id = Column(String, unique=True, index=True) # Логин (или ID в MAX)
    full_name = Column(String)                       # ФИО
    role = Column(String)                            # admin, vospitatel, kid
    group_name = Column(String, default="Нет группы") # Название отряда
    access_code = Column(String)                     # Код доступа (пароль)
    room = Column(String, default="")

# Функция, которая создаст файл базы и все таблицы
def init_db():
    Base.metadata.create_all(bind=engine)

# --- ТАБЛИЦА РАСПИСАНИЯ ---

class ScheduleItem(Base):
    __tablename__ = "schedule"
    id = Column(Integer, primary_key=True, index=True)
    time = Column(String)
    title = Column(String)
    place = Column(String)
    responsible = Column(String, default="")
    group_name = Column(String, default="")  # ← пусто = для всех отрядов


class ScheduleArchive(Base):
    __tablename__ = "schedule_archive"
    id = Column(Integer, primary_key=True, index=True)
    uploaded_at = Column(String)
    time = Column(String)
    title = Column(String)
    place = Column(String)
    responsible = Column(String, default="")     # ← вместо group_name

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)   # Кому отправлено
    text = Column(String)       # Текст уведомления
    is_read = Column(String, default="no") # "no" или "yes"

#---------------------------------------------------------------------

class Poll(Base):
    __tablename__ = "polls"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(String)
    group_name = Column(String)
    options = Column(String)
    expires_at = Column(String, default="Без срока")   # было
    is_closed = Column(String, default="no")            # ← НОВОЕ: "no" | "yes"

class PollAnswer(Base):
    __tablename__ = "poll_answers"
    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer)          # ID опроса
    user_id = Column(Integer)          # Кто ответил
    answer = Column(String)            # Что выбрал

#--------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer)
    receiver_id = Column(Integer)
    text = Column(String)
    timestamp = Column(String)


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(String)

#----------------------------------------------------------------------------

# в конец database.py
class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer)       # кто создал
    subject = Column(String)          # тема
    text = Column(String)             # описание
    status = Column(String, default="open")  # open / closed
    created_at = Column(String)       # когда создан (строка, как у Message)
    answer = Column(String, default="")      # ответ администратора

#----------------------------------------------------------------------------------

class AccessList(Base):
    __tablename__ = "access_lists"
    id = Column(Integer, primary_key=True, index=True)
    group_name = Column(String)        # для какого отряда
    created_at = Column(String)
    # содержимое — JSON-строка вида [{"name":..., "code":..., "room":...}, ...]
    content = Column(String)

#--------------------------------------------------------------------------------

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)   # "А", "Б", "В" — без "Отряд"

# --------------------------------------------------------------------------------



