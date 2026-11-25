# Всё для админа (пользователи, расписание)
# routers/admin.py

from utils import is_admin_like, groups_options_html, ROLE_NAMES
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, User, Group
from utils import hash_password

# routers/admin.py (или отдельный routers/lists.py — как хочешь)

router = APIRouter()

#--------------------------------------------------------------------------------------------------------------------

@router.get("/admin/users", response_class=HTMLResponse)
async def list_users(request: Request):
    role = request.session.get('user_role')
    if role not in ('admin', 'support'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    all_users = db.query(User).all()

    # Список отрядов — только из таблицы Group
    all_groups = [g.name for g in db.query(Group).order_by(Group.name).all()]
    db.close()

    html = """
    <html><body style="font-family: Arial; margin: 50px;">
        <h1>Список пользователей</h1>
    """

    if role == 'support':
        html += """
        <form action="/admin/clear_users" method="POST" onsubmit="return confirm('Удалить ВСЕХ пользователей?');">
            <button type="submit" style="padding: 10px 20px; background: #e74c3c; color: white; border: none; border-radius: 5px; cursor: pointer; margin-bottom: 20px;">🗑️ Очистить весь список</button>
        </form>
        """

    html += """
        <table border="1" cellpadding="10" style="border-collapse: collapse; width: 100%;">
            <tr style="background: #eee;">
                <th>ФИО</th><th>Роль</th><th>Группа</th><th>Комната</th><th>Код доступа</th><th>Действие</th>
            </tr>
    """

    def _can_modify(target) -> bool:
        """Может ли текущий пользователь вообще что-то делать с target."""
        if role == 'support':
            return not (target.role == 'support' and target.id != me.id)
        # admin
        if target.role in ('admin', 'support') and target.id != me.id:
            return False
        return True

    for u in all_users:
        # --- Видимость кода ---
        if role == 'support':
            show_code = True
        elif role == 'admin':
            show_code = (u.role != 'admin' or u.id == me.id)
        else:
            show_code = False
        if show_code:
            code_display = u.access_code_plain or "—"
        else:
            code_display = "*** скрыт ***"

        can_mod = _can_modify(u)
        is_self = (u.id == me.id)

        # --- Группа: только если can_mod (для kid и vospitatel имеет смысл) ---
        if can_mod and u.role in ('kid', 'vospitatel'):
            options_html = "".join(
                f'<option value="{g}"{" selected" if g == u.group_name else ""}>{g}</option>'
                for g in all_groups
            )
            if u.group_name and u.group_name not in all_groups and u.group_name != "Нет группы":
                options_html = f'<option value="{u.group_name}" selected>{u.group_name}</option>' + options_html
            group_cell = f"""
                <form action="/admin/change_group/{u.id}" method="POST" style="margin:0;display:flex;gap:5px;">
                    <select name="new_group" style="padding:5px;font-size:14px;">{options_html}</select>
                    <button type="submit" style="padding:5px 10px;background:#3498db;color:white;border:none;border-radius:5px;cursor:pointer;">💾</button>
                </form>
            """
        else:
            group_cell = u.group_name or "—"

        # --- Комната: kid — не может, остальные — если can_mod ---
        if can_mod:
            room_cell = f"""
                <form action="/admin/change_room/{u.id}" method="POST" style="margin:0;display:flex;gap:5px;">
                    <input type="text" name="new_room" value="{u.room or ''}" placeholder="—" style="padding:5px;width:80px;font-size:14px;">
                    <button type="submit" style="padding:5px 10px;background:#3498db;color:white;border:none;border-radius:5px;cursor:pointer;">💾</button>
                </form>
            """
        else:
            room_cell = u.room or "—"

        # --- Кнопки ---
        edit_btn = (
            f'<a href="/admin/edit_user/{u.id}" '
            f'style="padding:5px 10px;background:#f39c12;color:white;text-decoration:none;border-radius:5px;font-size:14px;">✏️ Изменить</a>'
            if can_mod else ""
        )
        delete_btn = (
            f'<form action="/admin/delete_user/{u.id}" method="POST" style="margin:0;display:inline;" '
            f'onsubmit="return confirm(\'Удалить {u.full_name}?\');">'
            f'<button type="submit" style="padding:5px 10px;background:#e74c3c;color:white;border:none;border-radius:5px;cursor:pointer;font-size:14px;">🗑️ Удалить</button></form>'
            if can_mod and not is_self else ""
        )
        action_cell = f'<div style="display:flex;gap:5px;">{edit_btn}{delete_btn}</div>' if (edit_btn or delete_btn) else "—"

        role_label = ROLE_NAMES.get(u.role)
        name_display = f"{u.full_name}" + (f" ({role_label})" if role_label else "")

        html += f"""
        <tr>
            <td>{u.full_name}</td>
            <td>{ROLE_NAMES.get(u.role, u.role)}</td>
            <td>{group_cell}</td>
            <td>{room_cell}</td>
            <td style="font-family: monospace; font-size: 16px; font-weight: bold; color: #d35400;">{code_display}</td>
            <td>{action_cell}</td>
        </tr>
        """

    html += """
        </table>
        <br>
        <a href="/lists_hub" style="padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">← Назад в меню «Списки»</a>
        <a href="/admin/add_user" style="padding: 10px 20px; background: #27ae60; color: white; text-decoration: none; border-radius: 5px; margin-left: 10px;">+ Добавить пользователя</a>
    </body></html>
    """
    return html

#-------------------------------------------------------------------------------------------------------------------------

@router.get("/admin/add_user", response_class=HTMLResponse)
async def add_user_page(request: Request):
    creator = request.session.get('user_role')
    if creator not in ('admin', 'support'):
        return RedirectResponse(url="/login", status_code=303)

    if creator == 'support':
        role_options = """
            <option value="kid">Участник</option>
            <option value="vospitatel">Воспитатель</option>
            <option value="admin">Администратор</option>
            <option value="support">Техподдержка</option>
        """
    else:
        role_options = """
            <option value="kid">Участник</option>
            <option value="vospitatel">Воспитатель</option>
        """

    group_options = groups_options_html(selected="")

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>Добавить нового пользователя</h1>
        <form action="/admin/add_user" method="POST">
            <p><input type="text" name="full_name" placeholder="ФИО" required style="padding: 10px; margin: 5px;"></p>
            <p><input type="text" name="max_id" placeholder="Логин (или ID в MAX)" required style="padding: 10px; margin: 5px;"></p>

            <p>
                <input type="text" name="access_code" id="code_field" placeholder="Код доступа" required style="padding: 10px; margin: 5px;">
                <button type="button" onclick="generateCode()" style="padding: 10px; cursor: pointer; background: #f39c12; color: white; border: none; border-radius: 5px;">🎲 Сгенерировать</button>
            </p>

            <p>
                <select name="role" style="padding: 10px; margin: 5px;">{role_options}</select>
            </p>

            <p>
                <label>Отряд: </label>
                <select name="group_name" style="padding: 10px; margin: 5px;">
                    {group_options}
                </select>
            </p>

            <p><input type="text" name="room" placeholder="Комната (например, 204)" style="padding: 10px; margin: 5px;"></p>

            <button type="submit" style="padding: 10px 20px; font-size: 16px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer;">Создать пользователя</button>
        </form>
        <script>
            function generateCode() {{
                const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
                let result = '';
                for (let i = 0; i < 6; i++) result += chars.charAt(Math.floor(Math.random() * chars.length));
                document.getElementById('code_field').value = result;
            }}
        </script>
        <br>
        <a href="/lists_hub">Назад в меню</a>
    </body></html>
    """

#----------------------------------------------------------------------------------------

@router.post("/admin/add_user", response_class=HTMLResponse)
async def process_add_user(
        request: Request,
        full_name: str = Form(...),
        max_id: str = Form(...),
        access_code: str = Form(...),
        role: str = Form(...),
        group_name: str = Form(""),
        room: str = Form(""),
):
    if request.session.get('user_role') not in ('admin', 'support'):
        return RedirectResponse(url="/login", status_code=303)

    # Защита: admin не создаёт admin/support
    if role in ('admin', 'support') and request.session.get('user_role') != 'support':
        return HTMLResponse("<h1>⛔ Отказано</h1><p>Только техподдержка может создавать администраторов.</p><a href='/admin/add_user'>Назад</a>")

    group_name = group_name.strip()

    db = SessionLocal()

    # Валидация группы
    if group_name:
        exists = db.query(Group).filter(Group.name == group_name).first()
        if not exists:
            db.close()
            return HTMLResponse(f"<h1>Ошибка</h1><p>Отряда '{group_name}' не существует в системе.</p><a href='/admin/add_user'>Назад</a>")

    # Проверка уникальности логина
    existing_user = db.query(User).filter(User.max_id == max_id).first()
    if existing_user:
        db.close()
        return HTMLResponse(f"<h1>Ошибка</h1><p>Логин '{max_id}' уже занят.</p><a href='/admin/add_user'>Назад</a>")

    new_user = User(
        full_name=full_name.strip(),
        max_id=max_id.strip(),
        access_code=hash_password(access_code.strip()),  # хэш
        access_code_plain=access_code.strip(),  # открытый
        role=role,
        group_name=group_name,
        room=room.strip(),
    )
    db.add(new_user)
    db.commit()
    db.close()

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 100px;">
        <div style="background: white; max-width: 500px; margin: 0 auto; padding: 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h1 style="color: #27ae60; font-size: 50px; margin: 0;">✅</h1>
            <h2>Пользователь создан!</h2>
            <p>{full_name} · роль: <b>{role}</b> · отряд: <b>{group_name or '—'}</b></p>
            <p>Код: <b style="font-family: monospace; color: #d35400; font-size: 18px;">{access_code}</b></p>
            <br>
            <a href="/admin/users" style="padding: 12px 25px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px;">К списку</a>
            <a href="/admin/add_user" style="padding: 12px 25px; background: #27ae60; color: white; text-decoration: none; border-radius: 5px;">Ещё одного</a>
        </div>
    </body></html>
    """

#-----------------------------------------------------------------------------------------

@router.post("/admin/delete_user/{user_id}")
async def delete_user(request: Request, user_id: int):
    role = request.session.get('user_role')
    if role not in ('admin', 'support'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    target = db.query(User).filter(User.id == user_id).first()

    # Защита: себя не удаляем
    if target.id == me.id:
        db.close()
        return RedirectResponse(url="/admin/users", status_code=303)

    # Защита: обычный админ не трогает других админов/поддержку
    if role == 'admin' and target.role in ('admin', 'support'):
        db.close()
        return RedirectResponse(url="/admin/users", status_code=303)

    # Защита: support не трогает других support
    if role == 'support' and target.role == 'support' and target.id != me.id:
        db.close()
        return RedirectResponse(url="/admin/users", status_code=303)

    db.delete(target)
    db.commit()
    db.close()
    logger.warning(f"{role} удалил пользователя: {target.full_name} (id={target.id})")
    return RedirectResponse(url="/admin/users", status_code=303)

#------------------------------------------------------------------------------------

@router.post("/admin/clear_users")
async def clear_users(request: Request):
    if request.session.get('user_role') != 'support':
        return RedirectResponse(url="/login", status_code=303)
    db = SessionLocal()
    db.query(User).delete()
    db.commit()
    db.close()
    return RedirectResponse(url="/admin/users", status_code=303)

#------------------------------------------------------------------------------------

@router.post("/admin/change_group/{user_id}")
async def change_group(request: Request, user_id: int, new_group: str = Form(...)):
    role = request.session.get('user_role')
    if role not in ('admin', 'support'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    target = db.query(User).filter(User.id == user_id).first()

    if not target:
        db.close()
        return RedirectResponse(url="/admin/users", status_code=303)

    # Обычный админ НЕ может менять группу другому админу или поддержке
    if role == 'admin' and target.role in ('admin', 'support'):
        db.close()
        return RedirectResponse(url="/admin/users", status_code=303)

    new_group = new_group.strip()
    if new_group:
        exists = db.query(Group).filter(Group.name == new_group).first()
        if not exists:
            db.close()
            return RedirectResponse(url="/admin/users", status_code=303)
    # Себе менять группу можно (но она ему не нужна), а вот поддержке/админу — не имеет смысла.
    # Просто записываем, если поле передано.
    if new_group.strip():
        target.group_name = new_group
        db.commit()

        # Если пользователь — воспитатель или ребёнок, положим ему уведомление
        if target.role in ('kid', 'vospitatel'):
            from database import Notification
            db.add(Notification(
                user_id=target.id,
                text=f"📋 Вам назначена группа: {target.group_name}",
                is_read="no"
            ))
            db.commit()

    db.close()
    return RedirectResponse(url="/admin/users", status_code=303)

#------------------------------------------------------------------------------------------

@router.get("/admin/notify_user", response_class=HTMLResponse)
async def notify_user_page(request: Request):
    if request.session.get('user_role') != 'support':
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    users = db.query(User).order_by(User.role, User.full_name).all()
    db.close()

    options = "".join(
        f'<option value="{u.id}">{u.full_name} ({ROLE_NAMES.get(u.role, u.role)})</option>'
        for u in users
    )

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>✉️ Уведомить конкретного пользователя</h1>
        <form action="/admin/notify_user" method="POST">
            <p>
                <select name="user_id" required style="padding: 10px; min-width: 400px;">
                    {options}
                </select>
            </p>
            <p><textarea name="text" placeholder="Текст уведомления" required style="padding: 10px; width: 500px; height: 100px;"></textarea></p>
            <button type="submit" style="padding: 10px 20px; background: #f39c12; color: white; border: none; border-radius: 5px; cursor: pointer;">Отправить</button>
        </form>
        <br><a href="/notifications_hub" style="color: #7f8c8d; text-decoration: none;">← Назад в меню уведомлений</a>
    </body></html>
    """


@router.post("/admin/notify_user", response_class=HTMLResponse)
async def notify_user(request: Request, user_id: int = Form(...), text: str = Form(...)):
    if request.session.get('user_role') != 'support':
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        db.close()
        return HTMLResponse("<h1>Пользователь не найден</h1><a href='/admin/notify_user'>Назад</a>")

    from database import Notification
    db.add(Notification(user_id=target.id, text=f"✉️ {text}", is_read="no"))
    db.commit()
    db.close()

    return f"""
    <html><body style="text-align: center; margin-top: 50px; font-family: Arial;">
        <h1>✅ Отправлено</h1>
        <p>Пользователь {target.full_name} получил уведомление.</p>
        <a href="/admin/notify_user" style="padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">Ещё одно</a>
        <a href="/notifications_hub" style="padding: 10px 20px; background: #95a5a6; color: white; text-decoration: none; border-radius: 5px; margin-left: 10px;">В меню уведомлений</a>
    </body></html>
    """

#------------------------------------------------------------------------------------------------------------------

@router.post("/admin/change_room/{user_id}")
async def change_room(request: Request, user_id: int, new_room: str = Form("")):
    role = request.session.get('user_role')
    if role not in ('admin', 'support', 'vospitatel'):    # ← добавили vospitatel
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    target = db.query(User).filter(User.id == user_id).first()

    if not me or not target:
        db.close()
        return RedirectResponse(url="/dashboard", status_code=303)

    # --- Проверки доступа ---
    if role == 'vospitatel':
        # воспитатель — только дети своего отряда
        if target.role != 'kid' or target.group_name != me.group_name:
            db.close()
            return RedirectResponse(url="/dashboard", status_code=303)
    elif role == 'admin':
        if target.role in ('admin', 'support') and target.id != me.id:
            db.close()
            return RedirectResponse(url="/admin/users", status_code=303)
    elif role == 'support':
        if target.role == 'support' and target.id != me.id:
            db.close()
            return RedirectResponse(url="/admin/users", status_code=303)
    # kid — вообще не может

    target.room = (new_room or "").strip()
    db.commit()
    db.close()
    if role == 'vospitatel':
        return RedirectResponse(url="/my_kids", status_code=303)
    return RedirectResponse(url="/admin/users", status_code=303)

#-------------------------------------------------------------------------------------

@router.get("/admin/edit_user/{user_id}", response_class=HTMLResponse)
async def edit_user_page(request: Request, user_id: int):
    role = request.session.get('user_role')
    if role not in ('admin', 'support'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        db.close()
        return RedirectResponse(url="/admin/users", status_code=303)

    # --- Проверки доступа ---
    if role == 'admin':
        if u.role in ('admin', 'support') and u.id != me.id:
            db.close()
            return RedirectResponse(url="/admin/users", status_code=303)
    if role == 'support':
        if u.role == 'support' and u.id != me.id:
            db.close()
            return RedirectResponse(url="/admin/users", status_code=303)

    # --- Вытаскиваем данные в локальные переменные (до db.close()) ---
    u_id = u.id
    u_full_name = u.full_name
    u_max_id = u.max_id
    u_access_code = ""  # не показываем хэш в поле
    u_role = u.role
    u_group = u.group_name or ""
    u_room = u.room or ""

    db.close()

    # --- Список отрядов (ВАЖНО: из таблицы Group, не из User) ---
    group_options = groups_options_html(selected=u_group)

    # --- Роли: support видит все, admin — только kid/vospitatel ---
    if role == 'support':
        role_options = f"""
            <option value="kid"{" selected" if u_role == 'kid' else ""}>Участник</option>
            <option value="vospitatel"{" selected" if u_role == 'vospitatel' else ""}>Воспитатель</option>
            <option value="admin"{" selected" if u_role == 'admin' else ""}>Администратор</option>
            <option value="support"{" selected" if u_role == 'support' else ""}>Техподдержка</option>
        """
    else:
        role_options = f"""
            <option value="kid"{" selected" if u_role == 'kid' else ""}>Участник</option>
            <option value="vospitatel"{" selected" if u_role == 'vospitatel' else ""}>Воспитатель</option>
        """

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>✏️ Редактировать пользователя #{u_id}</h1>
        <form action="/admin/edit_user/{u_id}" method="POST">
            <p><input type="text" name="full_name" value="{u_full_name}" placeholder="ФИО" required style="padding: 10px; margin: 5px; width: 400px;"></p>
            <p><input type="text" name="max_id" value="{u_max_id}" placeholder="Логин" required style="padding: 10px; margin: 5px; width: 400px;"></p>
            <p><input type="text" name="access_code" value="" placeholder="Новый код (оставьте пустым, чтобы не менять)" style="padding: 10px; margin: 5px; width: 400px;"></p>

            <p>
                <label>Роль: </label>
                <select name="role" style="padding: 10px; margin: 5px;">{role_options}</select>
            </p>

            <p>
                <label>Отряд: </label>
                <select name="group_name" style="padding: 10px; margin: 5px;">
                    {group_options}
                </select>
            </p>

            <p><input type="text" name="room" value="{u_room}" placeholder="Комната (например, 204)" style="padding: 10px; margin: 5px; width: 400px;"></p>

            <button type="submit" style="padding: 10px 30px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">💾 Сохранить</button>
        </form>
        <br>
        <a href="/admin/users">← Назад к списку</a>
    </body></html>
    """

#--------------------------------------------------------------------------------------

@router.post("/admin/edit_user/{user_id}", response_class=HTMLResponse)
async def edit_user(
        request: Request,
        user_id: int,
        full_name: str = Form(...),
        max_id: str = Form(...),
        access_code: str = Form(...),
        role: str = Form(...),
        group_name: str = Form(""),
        room: str = Form(""),
):
    current_role = request.session.get('user_role')
    if current_role not in ('admin', 'support'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    u = db.query(User).filter(User.id == user_id).first()

    if not me:
        db.close()
        return RedirectResponse(url="/logout", status_code=303)

    if not u:
        db.close()
        return RedirectResponse(url="/admin/users", status_code=303)

    # --- Проверки доступа ---
    if current_role == 'admin':
        if u.role in ('admin', 'support') and u.id != me.id:
            db.close()
            return RedirectResponse(url="/admin/users", status_code=303)
        if role in ('admin', 'support') and u.id != me.id:
            db.close()
            return RedirectResponse(url="/admin/users", status_code=303)

    if current_role == 'support':
        if u.role == 'support' and u.id != me.id:
            db.close()
            return RedirectResponse(url="/admin/users", status_code=303)

    # --- Валидация группы ---
    group_name = group_name.strip()
    if group_name:
        exists = db.query(Group).filter(Group.name == group_name).first()
        if not exists:
            db.close()
            return HTMLResponse(f"""
            <html><body style="text-align: center; margin-top: 50px;">
                <h1>Ошибка!</h1>
                <p>Отряда '{group_name}' не существует.</p>
                <a href="/admin/edit_user/{user_id}">Назад</a>
            </body></html>
            """)

    # --- Проверка уникальности max_id ---
    other = db.query(User).filter(User.max_id == max_id, User.id != user_id).first()
    if other:
        db.close()
        return HTMLResponse(f"""
        <html><body style="text-align: center; margin-top: 50px;">
            <h1>Ошибка!</h1>
            <p>Логин '{max_id}' уже занят пользователем {other.full_name}.</p>
            <a href="/admin/edit_user/{user_id}">Назад</a>
        </body></html>
        """)

    # --- Сохраняем ---
    u.full_name = full_name.strip()
    u.max_id = max_id.strip()
    new_code = access_code.strip()
    if new_code:
        u.access_code = hash_password(new_code)
        u.access_code_plain = new_code
        # если пусто — не меняем ни хэш, ни открытый
    # если пусто — оставляем старый хэш как есть
    u.role = role
    u.group_name = group_name
    u.room = room.strip()
    db.commit()
    db.close()

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 100px;">
        <div style="background: white; max-width: 500px; margin: 0 auto; padding: 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h1 style="color: #27ae60; font-size: 50px; margin: 0;">✅</h1>
            <h2>Изменения сохранены</h2>
            <p>Пользователь: <b>{full_name}</b></p>
            <p>Отряд: <b>{group_name or '—'}</b></p>
            <br>
            <a href="/admin/users" style="padding: 12px 25px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px;">К списку</a>
            <a href="/admin/edit_user/{user_id}" style="padding: 12px 25px; background: #f39c12; color: white; text-decoration: none; border-radius: 5px;">Изменить ещё</a>
        </div>
    </body></html>
    """