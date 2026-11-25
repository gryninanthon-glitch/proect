# routers/hubs.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, User, Notification
from utils import is_admin_like, render_header, render_footer

router = APIRouter()


def _btn(href, text, color="#3498db"):
    return (
        f'<a href="{href}" style="display:inline-block;margin:8px;padding:14px 28px;'
        f'background:{color};color:white;text-decoration:none;border-radius:8px;'
        f'font-size:16px;min-width:220px;text-align:center;">{text}</a>'
    )


def _wrap(request, title, subtitle, inner_html, back_href=None, back_label="← Назад в кабинет"):
    """Общая обёртка для хабов: шапка + (опционально) кнопка «Назад» слева сверху + карточка + подвал."""
    back_html = ""
    if back_href:
        back_html = f'<div style="text-align:left;margin-bottom:15px;"><a href="{back_href}" style="display:inline-block;padding:8px 16px;background:#95a5a6;color:white;text-decoration:none;border-radius:6px;font-size:14px;">{back_label}</a></div>'

    return f"""
    <html><body>
        {render_header(request)}
        <main style="flex:1;padding:30px 20px;">
            <div style="max-width:700px;margin:0 auto;">
                {back_html}
                <div style="background:white;padding:35px;border-radius:15px;box-shadow:0 4px 15px rgba(0,0,0,0.08);text-align:center;">
                    <h1 style="margin-top:0;color:#1f2937;">{title}</h1>
                    <p style="color:#7f8c8d;">{subtitle}</p>
                    <div style="display:flex;flex-wrap:wrap;justify-content:center;margin-top:20px;">
                        {inner_html}
                    </div>
                </div>
            </div>
        </main>
        {render_footer()}
    </body></html>
    """


@router.get("/schedule_hub", response_class=HTMLResponse)
async def schedule_hub(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    role = request.session.get('user_role')
    buttons = _btn("/schedule", "📅 Просмотр расписания")

    if is_admin_like(role):
        buttons += _btn("/admin/upload_schedule", "📊 Загрузить из Excel", "#27ae60")
        buttons += _btn("/admin/schedule_archive", "📚 Архив расписаний", "#9b59b6")

    return _wrap(request, "📅 Расписание", "Все действия с расписанием — в одном месте.", buttons)

#@router.get("/notifications_hub", response_class=HTMLResponse)
#async def notifications_hub(request: Request):
#    if not request.session.get('user_role'):
#        return RedirectResponse(url="/login", status_code=303)
#
#    role = request.session.get('user_role')
#
#    db = SessionLocal()
#    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
#    unread = 0
#    if me:
#        unread = db.query(Notification).filter(
#            Notification.user_id == me.id,
#            Notification.is_read == "no"
#        ).count()
#    db.close()
#
#    bell_label = f"🔔 Мои уведомления ({unread})" if unread > 0 else "🔔 Мои уведомления"
#    buttons = _btn("/notifications", bell_label, "#f39c12")
#
#    if role == 'support':
#        buttons += _btn("/admin/notify_user", "✉️ Уведомить пользователя", "#e67e22")
#    elif role in ('admin', 'vospitatel'):
#        buttons += _btn("/send_notification", "📢 Отправить уведомление", "#e74c3c")
#
#    return _wrap(request, "🔔 Уведомления", "Просмотр и отправка уведомлений.", buttons, back_href="/dashboard")

@router.get("/lists_hub", response_class=HTMLResponse)
async def lists_hub(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    role = request.session.get('user_role')
    buttons = ""

    if is_admin_like(role):
        buttons += _btn("/admin/groups", "👥 Отряды (сформировать)", "#c0392b")
        buttons += _btn("/admin/users", "👥 Список пользователей", "#3498db")
        buttons += _btn("/admin/add_user", "➕ Добавить пользователя", "#27ae60")
        buttons += _btn("/admin/issue_lists", "📋 Выдать списки", "#9b59b6")

    if role == 'vospitatel':
        buttons += _btn("/lists", "📋 Полученные списки", "#3498db")
        buttons += _btn("/my_kids", "👦 Дети отряда (сейчас)", "#27ae60")

    if not buttons:
        return RedirectResponse(url="/dashboard", status_code=303)

    return _wrap(request, "👥 Списки и пользователи", "Управление списками и людьми.", buttons)
