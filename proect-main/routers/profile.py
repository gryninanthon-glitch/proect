# routers/profile.py
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, User
from utils import ROLE_NAMES

router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    if not me:
        db.close()
        return RedirectResponse(url="/logout", status_code=303)

    my_id = me.id
    my_name = me.full_name
    my_role = me.role
    my_role_label = ROLE_NAMES.get(my_role, my_role)
    my_group = me.group_name or "—"
    my_room = me.room or ""
    my_code = me.access_code_plain or ""          # ← пустая строка, не "—"
    can_edit_room = (my_role in ('admin', 'support', 'vospitatel'))
    db.close()

    # --- Комната ---
    if can_edit_room:
        room_form = f"""
            <form action="/profile/room" method="POST" style="display: flex; gap: 10px; justify-content: center; margin-top: 10px;">
                <input type="text" name="new_room" value="{my_room}" placeholder="—" style="padding: 8px; width: 150px; font-size: 16px;">
                <button type="submit" style="padding: 8px 20px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer;">💾 Сохранить</button>
            </form>
        """
    else:
        room_form = f"<p style='color: #7f8c8d;'>{my_room or '—'} <small>(изменить может только воспитатель)</small></p>"

    # --- Блок с кодом: три случая ---
    if my_code:
        hidden = "•" * len(my_code)
        # json.dumps гарантирует, что спецсимволы в коде не сломают JS
        import json as _json
        code_block = f"""
            <p><b>Код доступа:</b>
                <span id="code_display" style="font-family: monospace; color: #d35400; font-weight: bold;">{hidden}</span>
                <button type="button" onclick="toggleCode()" style="margin-left: 8px; padding: 4px 10px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 12px;">👁 Показать</button>
            </p>
            <script>
                const realCode = {_json.dumps(my_code)};
                function toggleCode() {{
                    const el = document.getElementById('code_display');
                    el.textContent = (el.textContent === realCode) ? "•".repeat(realCode.length) : realCode;
                }}
            </script>
        """
    else:
        code_block = """
            <p><b>Код доступа:</b>
                <span style="color: #999;">— не задан (обратитесь к администрации)</span>
            </p>
        """

    # --- Кнопка удаления (только support) ---
    delete_block = ""
    if my_role == 'support':
        delete_block = """
            <hr style="margin-top: 25px;">
            <form action="/profile/delete_self" method="POST" onsubmit="return confirm('УДАЛИТЬ ВАШ АККАУНТ? Это необратимо. Вы выйдете из системы.');">
                <button type="submit" style="padding: 10px 25px; background: #e74c3c; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 15px;">🗑️ Удалить мой аккаунт</button>
            </form>
        """

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>👤 Мой профиль</h1>
        <div style="max-width: 500px; margin: 20px auto; background: white; border-radius: 10px; padding: 25px; border: 1px solid #ccc; text-align: left;">
            <p><b>ФИО:</b> {my_name}</p>
            <p><b>Роль:</b> {my_role_label}</p>
            <p><b>Группа:</b> {my_group}</p>
            {code_block}
            <hr>
            <p><b>Комната:</b></p>
            {room_form}
            {delete_block}
        </div>
        <a href="/dashboard">← Назад в кабинет</a>
    </body></html>
    """


@router.post("/profile/room")
async def profile_change_room(request: Request, new_room: str = Form("")):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    if not me:
        db.close()
        return RedirectResponse(url="/logout", status_code=303)

    # kid — нельзя
    if me.role == 'kid':
        db.close()
        return RedirectResponse(url="/profile", status_code=303)

    me.room = (new_room or "").strip()
    db.commit()
    db.close()
    return RedirectResponse(url="/profile", status_code=303)

#-----------------------------------------------------------------------------------------------------

@router.post("/profile/delete_self")
async def delete_self(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    # Только support может удалить себя
    if request.session.get('user_role') != 'support':
        return RedirectResponse(url="/profile", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    if not me:
        db.close()
        return RedirectResponse(url="/logout", status_code=303)

    # Защита: если это последний support — не даём удалить
    support_count = db.query(User).filter(User.role == 'support').count()
    if support_count <= 1:
        db.close()
        return HTMLResponse(f"""
        <html><body style="font-family: Arial; text-align: center; margin-top: 100px;">
            <div style="background: white; max-width: 500px; margin: 0 auto; padding: 40px; border-radius: 15px; border: 2px solid #e74c3c;">
                <h1 style="color: #e74c3c; font-size: 50px; margin: 0;">⛔</h1>
                <h2>Нельзя удалить последнюю техподдержку</h2>
                <p>В системе должен остаться хотя бы один аккаунт support.</p>
                <a href="/profile" style="padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">Назад в профиль</a>
            </div>
        </body></html>
        """)

    db.delete(me)
    db.commit()
    db.close()

    # Стираем сессию
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

