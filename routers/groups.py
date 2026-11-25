# routers/groups.py
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, User, Group
from utils import is_admin_like

router = APIRouter()


@router.get("/admin/groups", response_class=HTMLResponse)
async def groups_page(request: Request):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    groups = db.query(Group).order_by(Group.name).all()
    groups_data = [(g.id, g.name, db.query(User).filter(User.group_name == g.name).count()) for g in groups]
    db.close()

    rows = ""
    for g_id, g_name, count in groups_data:
        can_delete = count == 0
        delete_btn = (
            f'<form action="/admin/groups/delete/{g_id}" method="POST" style="margin:0;display:inline;" '
            f'onsubmit="return confirm(\'Удалить отряд «{g_name}»?\');">'
            f'<button type="submit" style="padding:5px 10px;background:#e74c3c;color:white;'
            f'border:none;border-radius:5px;cursor:pointer;">🗑️</button></form>'
            if can_delete else
            f'<span style="color:#7f8c8d;font-size:13px;">нельзя: {count} чел.</span>'
        )
        rows += f"""
        <tr>
            <td style="padding:10px;font-weight:bold;">{g_name}</td>
            <td style="padding:10px;">{count}</td>
            <td style="padding:10px;">{delete_btn}</td>
        </tr>
        """

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>👥 Отряды</h1>
        <div style="max-width: 700px; margin: 20px auto;">
            <form action="/admin/groups/create" method="POST" style="margin-bottom: 25px; display: flex; gap: 10px; justify-content: center;">
                <input type="text" name="name" placeholder="Название отряда (например, А или Луна)" required style="padding:10px;width:300px;">
                <button type="submit" style="padding:10px 20px;background:#27ae60;color:white;border:none;border-radius:5px;cursor:pointer;">+ Сформировать отряд</button>
            </form>
            <table border="1" cellpadding="10" style="width:100%;border-collapse:collapse;">
                <tr style="background:#eee;"><th>Название</th><th>Участников</th><th>Действие</th></tr>
                {rows if rows else '<tr><td colspan="3" style="padding:20px;color:#999;">Отрядов пока нет</td></tr>'}
            </table>
        </div>
        <br><a href="/lists_hub">Назад в меню «Списки»</a>
    </body></html>
    """


@router.post("/admin/groups/create")
async def create_group(request: Request, name: str = Form(...)):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    name_clean = name.strip()
    if not name_clean:
        return RedirectResponse(url="/admin/groups", status_code=303)

    db = SessionLocal()
    existing = db.query(Group).filter(Group.name == name_clean).first()
    if not existing:
        db.add(Group(name=name_clean))
        db.commit()
    db.close()
    return RedirectResponse(url="/admin/groups", status_code=303)


@router.post("/admin/groups/delete/{group_id}")
async def delete_group(request: Request, group_id: int):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    g = db.query(Group).filter(Group.id == group_id).first()
    if g:
        # защита: не удаляем, если в отряде есть люди
        count = db.query(User).filter(User.group_name == g.name).count()
        if count == 0:
            db.delete(g)
            db.commit()
    db.close()
    return RedirectResponse(url="/admin/groups", status_code=303)