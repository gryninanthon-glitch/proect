# routers/tickets.py
import datetime
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, User, Ticket
from utils import ROLE_NAMES, render_header, render_footer

router = APIRouter()


@router.get("/tickets", response_class=HTMLResponse)
async def list_tickets(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    user = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    if not user:
        db.close()
        return RedirectResponse(url="/dashboard", status_code=303)

    role = user.role

    if role == 'support':
        tickets = db.query(Ticket).order_by(Ticket.id.desc()).all()
        title = "🎫 Все тикеты (техподдержка)"
        show_create = False
    elif role == 'admin':
        tickets = db.query(Ticket).filter(Ticket.author_id == user.id).order_by(Ticket.id.desc()).all()
        title = "🎫 Мои обращения в техподдержку"
        show_create = True
    else:
        tickets = db.query(Ticket).filter(Ticket.author_id == user.id).order_by(Ticket.id.desc()).all()
        title = "🎫 Мои обращения"
        show_create = True

    # --- Начало HTML ---
    html = f"""
    <html><body>
        {render_header(request, active_page='feedback')}
        <main style="flex:1;padding:30px 20px;">
            <div style="max-width:800px;margin:0 auto;">
                <div style="text-align: left; margin-bottom: 15px;">
                    <a href="/dashboard" style="display: inline-block; padding: 8px 16px; background: #95a5a6; color: white; text-decoration: none; border-radius: 6px; font-size: 14px;">← Назад в кабинет</a>
                </div>
                <h1 style="text-align:center;margin-top:0;">{title}</h1>
    """

    if show_create:
        html += '<p style="text-align:center;"><a href="/tickets/create" style="padding: 10px 20px; background: #27ae60; color: white; text-decoration: none; border-radius: 5px;">+ Создать обращение</a></p>'

    html += '<div style="max-width: 800px; margin: 20px auto;">'

    if not tickets:
        html += "<p style='color: #999; text-align:center;'>Обращений нет.</p>"
    else:
        for t in tickets:
            author = db.query(User).filter(User.id == t.author_id).first()
            author_name = author.full_name if author else "?"
            status_color = "#e74c3c" if t.status == "open" else "#27ae60"
            status_text = "🔴 Открыт" if t.status == "open" else "✅ Закрыт"
            html += f"""
            <div style="border: 1px solid #ccc; border-radius: 10px; padding: 20px; margin: 10px 0; background: white; text-align: left;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0;">#{t.id} — {t.subject}</h3>
                    <span style="color: {status_color}; font-weight: bold;">{status_text}</span>
                </div>
                <p style="color: #7f8c8d; font-size: 14px;">Автор: {author_name} · {t.created_at}</p>
                <p>{t.text}</p>
            """
            if t.answer:
                html += f'<div style="background: #eafaf1; padding: 10px; border-radius: 5px; margin-top: 10px;"><b>Ответ:</b> {t.answer}</div>'

            if role == 'support' and t.status == 'open':
                html += f"""
                <form action="/tickets/{t.id}/close" method="POST" style="margin-top: 10px;">
                    <input type="text" name="answer" placeholder="Ответ (необязательно)" style="padding: 8px; width: 60%;">
                    <button type="submit" style="padding: 8px 20px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer;">Закрыть</button>
                </form>
                """
            html += "</div>"

    # --- Конец HTML: подвал + кнопка поддержки ---
    html += """
            </div>
        </main>
    """
    html += render_footer()
    html += "</body></html>"

    db.close()
    return html


@router.get("/tickets/create", response_class=HTMLResponse)
async def create_ticket_page(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)
    if request.session.get('user_role') == 'support':
        return RedirectResponse(url="/tickets", status_code=303)

    return f"""
    <html><body>
        {render_header(request, active_page='feedback')}
        <main style="flex:1;padding:30px 20px;">
            <div style="max-width:600px;margin:0 auto;background:white;padding:30px;border-radius:15px;box-shadow:0 4px 15px rgba(0,0,0,0.08);text-align:center;">
                <div style="text-align:left;margin-bottom:15px;">
                    <a href="/tickets" style="display:inline-block;padding:8px 16px;background:#95a5a6;color:white;text-decoration:none;border-radius:6px;font-size:14px;">← Назад к обращениям</a>
                </div>
                <h1 style="margin-top:0;">🎫 Новое обращение</h1>
                <form action="/tickets/create" method="POST">
                    <p><input type="text" name="subject" placeholder="Тема (например, Проблема со входом)" required style="padding: 10px; width: 100%; box-sizing: border-box;"></p>
                    <p><textarea name="text" placeholder="Подробно опишите проблему..." required style="padding: 10px; width: 100%; height: 120px; box-sizing: border-box;"></textarea></p>
                    <button type="submit" style="padding: 10px 20px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer;">Отправить</button>
                </form>
            </div>
        </main>
        {render_footer()}
    </body></html>
    """


@router.post("/tickets/create")
async def create_ticket(
        request: Request,
        subject: str = Form(...),
        text: str = Form(...),
):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)
    if request.session.get('user_role') == 'support':
        return RedirectResponse(url="/tickets", status_code=303)

    db = SessionLocal()
    user = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    if not user:
        db.close()
        return HTMLResponse(
            "<h1>Сессия устарела</h1><a href='/logout'>Войти заново</a>",
            status_code=400
        )

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    db.add(Ticket(
        author_id=user.id,
        subject=subject,
        text=text,
        status="open",
        created_at=now
    ))
    db.commit()
    db.close()
    return RedirectResponse(url="/tickets", status_code=303)


@router.post("/tickets/{ticket_id}/close")
async def close_ticket(request: Request, ticket_id: int, answer: str = Form("")):
    if request.session.get('user_role') != 'support':
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    t = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if t:
        t.status = "closed"
        t.answer = answer or ""
        db.commit()
    db.close()
    return RedirectResponse(url="/tickets", status_code=303)