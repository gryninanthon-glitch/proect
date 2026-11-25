# routers/notifications.py

from utils import is_admin_like, groups_options_html, render_header, render_footer
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, User, Notification, Group

router = APIRouter()


@router.get("/notifications", response_class=HTMLResponse)
async def view_notifications(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    user_login = request.session.get('user_name')
    user = db.query(User).filter(User.full_name == user_login).first()

    if not user:
        db.close()
        return RedirectResponse(url="/dashboard", status_code=303)

    notes = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.id.desc()).all()
    db.close()

    html = f"""
    <html><body>
        {render_header(request, active_page='notifications')}
        <main style="flex:1;padding:30px 20px;">
            <div style="max-width:800px;margin:0 auto;">
                <div style="text-align:left;margin-bottom:15px;">
                    <a href="/dashboard" style="display:inline-block;padding:8px 16px;background:#95a5a6;color:white;text-decoration:none;border-radius:6px;font-size:14px;">← Назад в кабинет</a>
                </div>
                <div style="background:white;padding:30px;border-radius:15px;box-shadow:0 4px 15px rgba(0,0,0,0.08);">
                    <h1 style="margin-top:0;text-align:center;">🔔 Ваши уведомления</h1>
                    <div style="height:400px;overflow-y:auto;border:1px solid #eee;border-radius:10px;padding:10px;background:#f9fafc;">
                        <table border="1" cellpadding="15" style="width:100%;border-collapse:collapse;border:none;">
    """

    if not notes:
        html += "<tr><td style='color:#999;padding:50px;text-align:center;border:none;'>Уведомлений пока нет.</td></tr>"
    else:
        for n in notes:
            if n.is_read == "yes":
                status_html = "✅ Прочитано"
            else:
                status_html = f"""
                <form action="/notifications/mark_read/{n.id}" method="POST" style="margin:0;">
                    <button type="submit" style="padding:5px 10px;background:#3498db;color:white;border:none;border-radius:5px;cursor:pointer;">🔵 Отметить прочитанным</button>
                </form>
                """
            html += f"""
            <tr style="border-bottom:1px solid #eee;">
                <td style="text-align:left;padding:15px;">{n.text}</td>
                <td style="width:180px;text-align:center;">{status_html}</td>
                <td style="width:100px;text-align:center;">
                    <form action="/notifications/delete/{n.id}" method="POST" style="margin:0;" onsubmit="return confirm('Удалить это уведомление?');">
                        <button type="submit" style="padding:5px 10px;background:#e74c3c;color:white;border:none;border-radius:5px;cursor:pointer;">🗑️ Удалить</button>
                    </form>
                </td>
            </tr>
            """

    html += """
                        </table>
                    </div>

                    <div style="margin-top:20px;text-align:center;">
                        <a href="/notifications/read" style="padding:10px 20px;background:#3498db;color:white;text-decoration:none;border-radius:5px;display:inline-block;">Отметить все прочитанными</a>
    """

    if notes:
        html += """
                        <form action="/notifications/clear_all" method="POST" style="display:inline;margin-left:10px;" onsubmit="return confirm('Вы уверены, что хотите удалить ВСЕ уведомления?');">
                            <button type="submit" style="padding:10px 20px;background:#e74c3c;color:white;border:none;border-radius:5px;cursor:pointer;">🗑️ Очистить всё</button>
                        </form>
        """

    html += f"""
                    </div>
                </div>
            </div>
        </main>
        {render_footer()}
    </body></html>
    """
    return html


@router.get("/notifications/read")
async def read_notifications(request: Request):
    db = SessionLocal()
    user_login = request.session.get('user_name')
    user = db.query(User).filter(User.full_name == user_login).first()
    if user:
        db.query(Notification).filter(Notification.user_id == user.id).update({"is_read": "yes"})
        db.commit()
    db.close()
    return RedirectResponse(url="/notifications", status_code=303)


@router.post("/notifications/delete/{note_id}")
async def delete_notification(request: Request, note_id: int):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    note = db.query(Notification).filter(Notification.id == note_id).first()
    if note:
        db.delete(note)
        db.commit()
    db.close()
    return RedirectResponse(url="/notifications", status_code=303)


@router.post("/notifications/clear_all")
async def clear_all_notifications(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    user_login = request.session.get('user_name')
    user = db.query(User).filter(User.full_name == user_login).first()

    if user:
        db.query(Notification).filter(Notification.user_id == user.id).delete()
        db.commit()
    db.close()
    return RedirectResponse(url="/notifications", status_code=303)


@router.get("/send_notification", response_class=HTMLResponse)
async def send_notification_page(request: Request):
    role = request.session.get('user_role')
    if role not in ('admin', 'vospitatel'):
        return RedirectResponse(url="/dashboard", status_code=303)

    group_options = '<option value="Все">— Всем —</option>' + groups_options_html(allow_empty=False)

    return f"""
    <html><body>
        {render_header(request, active_page='notifications')}
        <main style="flex:1;padding:30px 20px;">
            <div style="max-width:600px;margin:0 auto;">
                <div style="text-align:left;margin-bottom:15px;">
                    <a href="/dashboard" style="display:inline-block;padding:8px 16px;background:#95a5a6;color:white;text-decoration:none;border-radius:6px;font-size:14px;">← Назад в кабинет</a>
                </div>
                <div style="background:white;padding:30px;border-radius:15px;box-shadow:0 4px 15px rgba(0,0,0,0.08);text-align:center;">
                    <h1 style="margin-top:0;">📢 Отправить уведомление</h1>
                    <form action="/send_notification" method="POST">
                    <p><input type="text" name="text" placeholder="Текст уведомления" required style="padding: 10px; width: 100%; box-sizing: border-box;"></p>
                    <p style="text-align:left;">
                        <label>Кому: </label>
                        <select name="target_group" style="padding: 10px;">
                            {group_options}
                        </select>
                    <button type="submit" style="padding: 10px 20px; background: #f39c12; color: white; border: none; border-radius: 5px; cursor: pointer;">Отправить</button>
                </form>
                </div>
            </div>
        </main>
        {render_footer()}
    </body></html>
    """


@router.post("/send_notification", response_class=HTMLResponse)
async def process_send_notification(request: Request, text: str = Form(...), target_group: str = Form("Все")):
    role = request.session.get('user_role')
    if not (is_admin_like(role) or role == 'vospitatel'):
        return RedirectResponse(url="/dashboard", status_code=303)

    # Валидация отряда
    if target_group != "Все":
        check_db = SessionLocal()
        exists = check_db.query(Group).filter(Group.name == target_group).first()
        check_db.close()
        if not exists:
            return HTMLResponse(f"<h1>Отряда '{target_group}' нет</h1><a href='/send_notification'>Назад</a>")

    db = SessionLocal()

    count = 0
    try:
        users = db.query(User).all()
        new_notes = []
        for u in users:
            if target_group == "Все" or u.group_name == target_group:
                new_notes.append(Notification(user_id=u.id, text=f"📢 {text}", is_read="no"))
                count += 1
        db.add_all(new_notes)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Ошибка при отправке уведомлений: {e}")
        return "<h1>Произошла ошибка при отправке</h1>"
    finally:
        db.close()

    return f"""
    <html><body>
        {render_header(request, active_page='notifications')}
        <main style="flex:1;padding:30px 20px;">
            <div style="max-width:500px;margin:0 auto;background:white;padding:40px;border-radius:15px;box-shadow:0 4px 15px rgba(0,0,0,0.08);text-align:center;">
                <h1 style="color:#27ae60;font-size:50px;margin:0;">✅</h1>
                <h2>Успешно!</h2>
                <p>Уведомление отправлено <b>{count}</b> пользователям.</p>
                <a href="/dashboard" style="padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">← В кабинет</a>
            </div>
        </main>
        {render_footer()}
    </body></html>
    """

@router.post("/notifications/mark_read/{note_id}")
async def mark_notification_read(request: Request, note_id: int):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    note = db.query(Notification).filter(Notification.id == note_id).first()
    if note:
        note.is_read = "yes"
        db.commit()
    db.close()
    return RedirectResponse(url="/notifications", status_code=303)