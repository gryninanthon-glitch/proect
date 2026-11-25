# routers/lists.py
import json
import datetime
from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, User, AccessList, Notification, Group
from utils import is_admin_like, parse_kids_list_xlsx, parse_kids_list_pdf

router = APIRouter()


@router.get("/admin/issue_lists", response_class=HTMLResponse)
async def issue_lists_page(request: Request):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    groups = db.query(Group).order_by(Group.name).all()
    groups_with_counts = []
    for g in groups:
        count = db.query(User).filter(User.role == 'kid', User.group_name == g.name).count()
        groups_with_counts.append((g.name, count))
    db.close()

    if not groups_with_counts:
        return HTMLResponse("""
        <html><body style="font-family: Arial; text-align: center; margin-top: 100px;">
            <h1>⚠️ Нет детей ни в одном отряде</h1>
            <p>Сначала добавьте детей через управление пользователями.</p>
            <a href="/admin/upload_lists" style="display:inline-block;padding:10px 20px;background:#16a085;color:white;text-decoration:none;border-radius:5px;margin-right:10px;">📎 Отправить список файлом</a>
            <a href="/lists_hub" style="display:inline-block;padding:10px 20px;background:#95a5a6;color:white;text-decoration:none;border-radius:5px;">← Назад в меню «Списки»</a>
        </body></html>
        """)

    options = "".join(
        f'<option value="{g}">{g} — {count} детей</option>'
        for g, count in groups_with_counts
    )

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>📋 Выдать список воспитателям</h1>
        <form action="/admin/issue_lists" method="POST">
            <p>Отряд: <select name="group_name" required style="padding:10px;">{options}</select></p>
            <button type="submit" style="padding:10px 20px;background:#27ae60;color:white;border:none;border-radius:5px;cursor:pointer;">Сформировать пакет</button>
            <a href="/admin/upload_lists" style="display:inline-block;padding:10px 20px;background:#16a085;color:white;text-decoration:none;border-radius:5px;margin-left:10px;">📎 Отправить список файлом</a>
        </form>
        <br><a href="/lists_hub" style="color: #7f8c8d; text-decoration: none;">← Назад в меню «Списки»</a>
    </body></html>
    """


@router.post("/admin/issue_lists")
async def issue_lists(request: Request, group_name: str = Form(...)):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    kids = db.query(User).filter(User.role == 'kid', User.group_name == group_name).all()
    if not kids:
        db.close()
        return HTMLResponse(f"""
        <html><body style="font-family: Arial; text-align: center; margin-top: 100px;">
            <h1>⚠️ В отряде «{group_name}» нет детей</h1>
            <p>Пакет не создан. Добавьте детей в отряд через управление пользователями.</p>
            <a href="/admin/issue_lists" style="padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">Назад</a>
        </body></html>
        """)

    kids_count = len(kids)
    content = [
        {"name": k.full_name, "code": k.access_code_plain or "—", "room": k.room or "—"}
        for k in kids
    ]

    db.add(AccessList(
        group_name=group_name,
        created_at=stamp,
        content=json.dumps(content, ensure_ascii=False),
    ))

    teachers = db.query(User).filter(
        User.role == 'vospitatel',
        User.group_name == group_name
    ).all()
    for t in teachers:
        db.add(Notification(
            user_id=t.id,
            text=f"📋 Список выдан для отряда {group_name} от {stamp}",
            is_read="no"
        ))

    db.commit()       # ← один commit
    db.close()

    return HTMLResponse(f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 100px;">
        <div style="background: white; max-width: 500px; margin: 0 auto; padding: 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h1 style="color: #27ae60; font-size: 50px; margin: 0;">✅</h1>
            <h2>Пакет сформирован</h2>
            <p>Отряд: <b>{group_name}</b></p>
            <p>Записей в пакете: <b>{kids_count}</b></p>
            <p>Уведомлений отправлено: <b>{len(teachers)}</b> воспитателям</p>
            <br>
            <a href="/admin/issue_lists" style="padding: 12px 25px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px;">Ещё один</a>
            <a href="/lists_hub" style="padding: 12px 25px; background: #95a5a6; color: white; text-decoration: none; border-radius: 5px;">В меню «Списки»</a>
        </div>
    </body></html>
    """)

# --------------------------------------------------------------------------
# «Отправить файлом» — загрузка xlsx/pdf со списком детей
# --------------------------------------------------------------------------

@router.get("/admin/upload_lists", response_class=HTMLResponse)
async def upload_lists_page(request: Request):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    groups = db.query(Group).order_by(Group.name).all()
    group_names = [g.name for g in groups]
    db.close()
    if not group_names:
        options = '<option value="" disabled selected>— Сначала создайте отряд —</option>'
    else:
        options = "".join(f'<option value="{g}">{g}</option>' for g in group_names)
    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>📎 Отправить список файлом</h1>
        <p style="color: #7f8c8d;">
            Загрузите Excel или PDF со списком детей.<br>
            Колонки: <b>ФИО · Код · Комната · Группа</b>
        </p>
        <form action="/admin/upload_lists" method="POST" enctype="multipart/form-data"
              style="max-width: 600px; margin: 30px auto; background: white; padding: 25px; border-radius: 10px; border: 1px solid #ccc;">
            <p><input type="file" name="file" accept=".xlsx,.pdf" required style="padding: 10px;"></p>
            <p>
                <label>Отряд: </label>
                <select name="group_name" required style="padding: 10px;">
                    {options}
                </select>
            </p>
            <button type="submit" style="padding: 12px 30px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">Загрузить и отправить</button>
            <br><br>
        <br><a href="/admin/issue_lists">← Назад к выдаче списков</a>
    </body></html>
    """


@router.post("/admin/upload_lists", response_class=HTMLResponse)
async def upload_lists(request: Request, file: UploadFile = File(...), group_name: str = Form(...)):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    filename = (file.filename or "").lower()
    contents = await file.read()

    if filename.endswith(".xlsx"):
        rows, warnings = parse_kids_list_xlsx(contents)
    elif filename.endswith(".pdf"):
        rows, warnings = parse_kids_list_pdf(contents)
    else:
        return HTMLResponse("<h1>Нужен .xlsx или .pdf</h1><a href='/admin/upload_lists'>Назад</a>")

    if not rows:
        warn_html = "".join(f"<li>{w}</li>" for w in warnings)
        return HTMLResponse(f"""
        <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h1>⚠️ Не удалось извлечь строки</h1>
            <p>Файл пуст или таблица не распознана.</p>
            <ul style="text-align: left; display: inline-block;">{warn_html}</ul>
            <p><a href="/admin/upload_lists">Назад</a></p>
        </body></html>
        """)

    db = SessionLocal()
    exists = db.query(Group).filter(Group.name == group_name).first()
    if not exists:
        db.close()
        return HTMLResponse(f"<h1>Отряда '{group_name}' нет</h1><a href='/admin/upload_lists'>Назад</a>")

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    content = [
        {"name": k.full_name, "code": k.access_code_plain or "—", "room": k.room or "—"}
        for k in kids
    ]

    db.add(AccessList(
        group_name=group_name,
        created_at=stamp,
        content=json.dumps(content, ensure_ascii=False),
    ))

    teachers = db.query(User).filter(
        User.role == 'vospitatel',
        User.group_name == group_name,
    ).all()
    teacher_count = len(teachers)
    for t in teachers:
        db.add(Notification(
            user_id=t.id,
            text=f"📋 Список выдан для отряда {group_name} от {stamp}",
            is_read="no",
        ))
    db.commit()
    db.close()

    warn_html = "".join(f"<li style='color:#e67e22;'>{w}</li>" for w in warnings)

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 100px;">
        <div style="background: white; max-width: 500px; margin: 0 auto; padding: 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h1 style="color: #27ae60; font-size: 50px; margin: 0;">✅</h1>
            <h2>Список отправлен</h2>
            <p>Отряд: <b>{group_name}</b></p>
            <p>Детей: <b>{len(content)}</b></p>
            <p>Уведомлений: <b>{teacher_count}</b> воспитателям</p>
            {f'<ul style="text-align:left;display:inline-block;">{warn_html}</ul>' if warnings else ''}
            <br>
            <a href="/admin/upload_lists" style="padding: 12px 25px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px;">Ещё файл</a>
            <a href="/admin/issue_lists" style="padding: 12px 25px; background: #95a5a6; color: white; text-decoration: none; border-radius: 5px;">К выдаче</a>
        </div>
    </body></html>
    """

#----------------------------------------------------------------------------------------------------------------

@router.get("/lists", response_class=HTMLResponse)
async def lists_page(request: Request):
    if request.session.get('user_role') != 'vospitatel':
        return RedirectResponse(url="/dashboard", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    if not me:
        db.close()
        return RedirectResponse(url="/dashboard", status_code=303)

    my_group = me.group_name
    lists = db.query(AccessList).filter(
        AccessList.group_name == my_group
    ).order_by(AccessList.id.desc()).all()

    # Считаем суммарное число детей во всех пакетах
    total_kids = 0
    lists_data = []
    for L in lists:
        try:
            kids = json.loads(L.content) if L.content else []
        except (json.JSONDecodeError, TypeError):
            kids = []
        total_kids += len(kids)
        lists_data.append((L.id, L.created_at, L.group_name, len(kids)))
    db.close()

    # --- Toast: показываем «Получено: N списков, M детей» один раз за сессию просмотра ---
    # Используем session-флаг, чтобы не всплывало при каждом обновлении.
    show_toast = False
    if request.session.get('lists_toast_shown_for') != my_group:
        show_toast = True
        request.session['lists_toast_shown_for'] = my_group

    toast_html = ""
    if show_toast and lists_data:
        toast_html = f"""
        <div id="toast" style="
            position: fixed; top: 20px; right: 20px;
            background: #27ae60; color: white;
            padding: 15px 25px; border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            font-size: 16px; z-index: 1000;
            opacity: 0; transition: opacity 0.5s ease;
        ">
            📋 Получено списков: <b>{len(lists_data)}</b> · Детей: <b>{total_kids}</b>
        </div>
        <script>
            window.addEventListener('load', () => {{
                const t = document.getElementById('toast');
                if (!t) return;
                setTimeout(() => t.style.opacity = '1', 100);
                setTimeout(() => {{
                    t.style.opacity = '0';
                    setTimeout(() => t.remove(), 600);
                }}, 4000);
            }});
        </script>
        """

    html = f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        {toast_html}
        <h1>📋 Полученные списки</h1>
        <p style="color: #7f8c8d;">
            Всего пакетов: <b>{len(lists_data)}</b> · Детей в них: <b>{total_kids}</b>
        </p>
    """

    if not lists_data:
        html += "<p>Пока списков нет.</p>"
    else:
        for L_id, L_created, L_group, kids_count in lists_data:
            html += f"""
            <div style="border: 1px solid #ccc; border-radius: 10px; padding: 15px; margin: 10px auto; max-width: 600px; background: white;">
                <h3 style="margin-top: 0;">Пакет от {L_created}</h3>
                <p>Отряд: {L_group} · Детей: <b>{kids_count}</b></p>
                <a href="/lists/{L_id}" style="padding: 8px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">Открыть</a>
                <a href="/lists/{L_id}/export" style="padding: 8px 20px; background: #27ae60; color: white; text-decoration: none; border-radius: 5px; margin-left: 8px;">📥 Скачать в Excel</a>
            </div>
            """

    html += """
            </div>
            <br><a href="/lists_hub">← Назад в меню «Списки»</a>
        </body></html>
        """
    return html


@router.get("/lists/{list_id}", response_class=HTMLResponse)
async def list_detail(request: Request, list_id: int):
    if request.session.get('user_role') != 'vospitatel':
        return RedirectResponse(url="/dashboard", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    L = db.query(AccessList).filter(AccessList.id == list_id).first()

    if not L or not me or L.group_name != me.group_name:
        db.close()
        return RedirectResponse(url="/lists", status_code=303)

    # Вытаскиваем всё нужное ДО закрытия сессии
    L_group = L.group_name
    L_created = L.created_at
    raw_content = L.content
    my_id = me.id

    try:
        data = json.loads(raw_content) if raw_content else []
    except (json.JSONDecodeError, TypeError):
        db.close()
        return f"""
        <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h1>⚠️ Ошибка данных</h1>
            <p>Пакет №{list_id} содержит некорректные данные.</p>
            <a href="/lists">Назад</a>
        </body></html>
        """

    db.query(Notification).filter(
        Notification.user_id == my_id,
        Notification.text == f"📋 Список выдан для отряда {L_group} от {L_created}",
        Notification.is_read == "no",
    ).update({"is_read": "yes"})
    db.commit()
    db.close()

    html = f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>📋 Список отряда «{L_group}» от {L_created}</h1>
        <table border="1" cellpadding="10" style="margin: 0 auto; border-collapse: collapse;">
            <tr style="background: #eee;"><th>ФИО</th><th>Код доступа</th><th>Комната</th></tr>
    """
    for p in data:
        html += f"<tr><td>{p.get('name','—')}</td><td style='font-family:monospace;'>{p.get('code','—')}</td><td>{p.get('room','—')}</td></tr>"
    html += f"""
        </table>
                <br>
        <a href="/lists/{list_id}/export" style="padding: 10px 20px; background: #27ae60; color: white; text-decoration: none; border-radius: 5px;">📥 Скачать в Excel</a>
        <a href="/lists" style="padding: 10px 20px; background: #95a5a6; color: white; text-decoration: none; border-radius: 5px; margin-left: 8px;">← Назад к спискам</a>
    </body></html>
    """
    return html

#------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Скачать список в Excel
# --------------------------------------------------------------------------

@router.get("/lists/{list_id}/export")
async def export_list(list_id: int, request: Request):
    role = request.session.get('user_role')
    if role not in ('vospitatel', 'admin', 'support'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    L = db.query(AccessList).filter(AccessList.id == list_id).first()

    if not L or not me:
        db.close()
        return RedirectResponse(url="/lists", status_code=303)

    # Воспитатель — только свой отряд
    if role == 'vospitatel' and L.group_name != me.group_name:
        db.close()
        return RedirectResponse(url="/lists", status_code=303)

    group_name = L.group_name
    created_at = L.created_at
    raw_content = L.content
    db.close()

    try:
        data = json.loads(raw_content) if raw_content else []
    except (json.JSONDecodeError, TypeError):
        data = []

    rows = [
        {
            "name": p.get("name", ""),
            "code": p.get("code", ""),
            "room": p.get("room", ""),
            "group": group_name,
        }
        for p in data
    ]

    from utils import make_kids_list_xlsx
    from fastapi.responses import Response

    xlsx_bytes = make_kids_list_xlsx(rows, title=f"Список {group_name}")

    safe_stamp = created_at.replace(":", "-").replace(" ", "_")
    filename = f"spisok_{group_name}_{safe_stamp}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )