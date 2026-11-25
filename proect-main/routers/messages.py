# Чат и уведомления
# routers/messages.py

from utils import is_admin_like
import datetime
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, User, Message, Notification
from utils import ROLE_NAMES, count_unread_notifications

router = APIRouter()


@router.get("/messages", response_class=HTMLResponse)
async def messages_list(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    user_name = request.session.get('user_name')
    user = db.query(User).filter(User.full_name == user_name).first()
    role = user.role

    if user.role == 'kid':
        # Детям разрешено писать только воспитателям и администрации
        contacts = db.query(User).filter(
            User.id != user.id,
            User.role.in_(['vospitatel', 'admin'])
        ).all()
    else:
        contacts = db.query(User).filter(User.id != user.id, User.role != 'support').all()

    # Считаем непрочитанные входящие по каждому контакту
    # берём из Notification: "💬 Новое сообщение от {full_name}" с is_read='no'
    from database import Notification
    unread_notes = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == "no",
        Notification.text.like("💬 Новое сообщение от %")
    ).all()
    unread_senders = set()
    for n in unread_notes:
        # вытаскиваем ФИО из текста: "💬 Новое сообщение от ФИО: ..."
        try:
            after = n.text.split("от ", 1)[1]      # "ФИО: превью..."
            name = after.split(":", 1)[0].strip()
            unread_senders.add(name)
        except IndexError:
            pass

    html = """
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>💬 Выберите, кому написать</h1>
        <div style="display: flex; flex-wrap: wrap; justify-content: center;">
    """

    for c in contacts:
        has_new = c.full_name in unread_senders
        badge = '<span style="background: #e74c3c; color: white; font-size: 12px; padding: 2px 8px; border-radius: 10px; margin-left: 5px;">🔵 новое</span>' if has_new else ""
        border_color = "#e74c3c" if has_new else "#ccc"
        html += f"""
        <div style="border: 2px solid {border_color}; border-radius: 10px; padding: 15px; margin: 10px; width: 200px;">
            <h4>{c.full_name}{badge}</h4>
            <p style="color: #7f8c8d; font-size: 14px;">{ROLE_NAMES.get(c.role, c.role)}</p>
            <a href="/messages/{c.id}" style="padding: 5px 15px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">Написать</a>
        </div>
        """

    if not contacts:
        html += "<p>Собеседников пока нет.</p>"

    html += """
        </div>
        <br><a href="/dashboard">Назад в кабинет</a>
    </body></html>
    """
    db.close()
    return html

@router.get("/messages/{contact_id}", response_class=HTMLResponse)
async def chat_with_contact(request: Request, contact_id: int):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    user_name = request.session.get('user_name')
    user = db.query(User).filter(User.full_name == user_name).first()
    contact = db.query(User).filter(User.id == contact_id).first()

    if not contact:
        db.close()
        return RedirectResponse(url="/messages", status_code=303)

    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == "no",
        Notification.text.like(f"💬 Новое сообщение от {contact.full_name}%")
    ).update({"is_read": "yes"})
    db.commit()

    messages = db.query(Message).filter(
        ((Message.sender_id == user.id) & (Message.receiver_id == contact.id)) |
        ((Message.sender_id == contact.id) & (Message.receiver_id == user.id))
    ).order_by(Message.id).all()

    html = f"""
    <html><body style="font-family: Arial; margin: 0; padding: 0; background: #e5e5e5;">
        <div style="background: #3498db; color: white; padding: 15px; text-align: center;">
            <h2 style="margin: 0;">Чат с {contact.full_name}</h2>
            <a href="/messages" style="color: #d1ecf1; text-decoration: none; font-size: 14px;">← Назад к контактам</a>
        </div>

        <div style="max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; padding: 20px; height: 400px; overflow-y: scroll; display: flex; flex-direction: column;">
    """

    if not messages:
        html += "<p style='text-align: center; color: #999;'>История сообщений пуста. Напишите первым!</p>"
    else:
        for msg in messages:
            is_mine = (msg.sender_id == user.id)
            align = "align-items: flex-end;" if is_mine else "align-items: flex-start;"
            bg_color = "#dcf8c6" if is_mine else "#f1f0f0"
            html += f"""
            <div style="display: flex; flex-direction: column; {align} margin-bottom: 10px;">
                <div style="background: {bg_color}; padding: 10px 15px; border-radius: 15px; max-width: 70%; text-align: left;">
                    <p style="margin: 0;">{msg.text}</p>
                    <span style="font-size: 10px; color: #999; display: block; text-align: right; margin-top: 5px;">{msg.timestamp}</span>
                </div>
            </div>
            """

    html += f"""
        </div>

        <div style="max-width: 600px; margin: 0 auto; text-align: center;">
            <form action="/messages/{contact.id}/send" method="POST" style="display: flex; gap: 10px;">
                <input type="text" name="text" placeholder="Введите сообщение..." required style="flex-grow: 1; padding: 15px; border-radius: 20px; border: 1px solid #ccc; font-size: 16px;">
                <button type="submit" style="padding: 15px 30px; background: #3498db; color: white; border: none; border-radius: 20px; cursor: pointer;">Отправить</button>
            </form>
        </div>
    </body></html>
    """
    db.close()
    return html


@router.post("/messages/{contact_id}/send")
async def send_message(request: Request, contact_id: int, text: str = Form(...)):
    db = SessionLocal()
    user_name = request.session.get('user_name')
    user = db.query(User).filter(User.full_name == user_name).first()

    if user:
        # Проверка: kid может писать только воспитателям и админам
        if user.role == 'kid':
            receiver = db.query(User).filter(User.id == contact_id).first()
            if not receiver or receiver.role not in ('vospitatel', 'admin'):
                db.close()
                return RedirectResponse(url="/messages", status_code=303)

        now = datetime.datetime.now().strftime("%H:%M")
        db.add(Message(sender_id=user.id, receiver_id=contact_id, text=text, timestamp=now))
        db.add(Notification(
            user_id=contact_id,
            text=f"💬 Новое сообщение от {user.full_name}: {text[:20]}..."
        ))
        db.commit()
    db.close()
    return RedirectResponse(url=f"/messages/{contact_id}", status_code=303)