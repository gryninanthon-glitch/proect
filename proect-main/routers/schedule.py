# routers/schedule.py
import io
from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, ScheduleItem, ScheduleArchive, User, Group
from utils import (is_admin_like, parse_schedule_xlsx, parse_schedule_pdf,
                   _normalize_time, render_header, render_footer)
router = APIRouter()
import datetime as _dt


@router.get("/schedule", response_class=HTMLResponse)
async def view_schedule(request: Request, group: str = ""):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    role = request.session.get('user_role')
    user_group = request.session.get('group_name', "")

    db = SessionLocal()
    all_groups = sorted([g.name for g in db.query(Group).all()])
    items_all = db.query(ScheduleItem).order_by(ScheduleItem.time).all()

    # --- Определяем, чьё расписание показываем ---
    if role in ('admin', 'support'):
        if group == "__all__":
            selected = "__all__"
            items = list(items_all)                            # всё
        elif group == "":
            selected = ""
            items = [it for it in items_all if (it.group_name or "") == ""]   # только общие
        else:
            selected = group
            items = [it for it in items_all if (it.group_name or "") == group]  # только отряд
    else:
        # kid / vospitatel — своё + общее
        selected = user_group if user_group else ""
        if selected:
            items = [it for it in items_all if (it.group_name or "") in ("", selected)]
        else:
            items = [it for it in items_all if (it.group_name or "") == ""]

    items_data = [(it.id, it.time, it.title, it.place, it.responsible or "", it.group_name or "") for it in items]
    db.close()

    # --- Табы для админа ---
    tabs_html = ""
    if role in ('admin', 'support'):
        tab_base = 'display:inline-block;margin:4px;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:14px;color:white;'
        bg = "#0d3b8f" if selected == "__all__" else "#95a5a6"
        tabs_html += f'<a href="/schedule?group=__all__" style="{tab_base}background:{bg};">Всё</a>'
        bg = "#0d3b8f" if selected == "" else "#95a5a6"
        tabs_html += f'<a href="/schedule" style="{tab_base}background:{bg};">Общие</a>'
        for g in all_groups:
            active = (g == selected)
            bg = "#0d3b8f" if active else "#95a5a6"
            tabs_html += f'<a href="/schedule?group={g}" style="{tab_base}background:{bg};">{g}</a>'

    # --- Кнопка очистки ---
    clear_html = ""
    if is_admin_like(role):
        if selected == "__all__":
            current_scope = "all"
            clear_label = "🗑️ Очистить ВСЁ расписание"
            clear_color = "#c0392b"
            confirm_text = "ВСЁ расписание"
        elif selected == "":
            current_scope = "common"
            clear_label = "🗑️ Очистить общие"
            clear_color = "#e67e22"
            confirm_text = "общие мероприятия"
        else:
            current_scope = selected
            clear_label = f"🗑️ Очистить «{selected}»"
            clear_color = "#e74c3c"
            confirm_text = f"расписание отряда «{selected}»"

        clear_html = f"""
        <div style="text-align:center;margin:10px 0;">
            <form action="/admin/clear_schedule" method="POST" style="display:inline;"
                  onsubmit="return confirm('Удалить {confirm_text}? Всё удаляемое уйдёт в архив.');">
                <input type="hidden" name="scope" value="{current_scope}">
                <button type="submit" style="padding:10px 20px;background:{clear_color};color:white;border:none;border-radius:6px;cursor:pointer;font-size:14px;">{clear_label}</button>
            </form>
        </div>
        """

    html = f"""
    <html><body>
        {render_header(request, active_page='schedule')}
        <main style="flex:1;padding:30px 20px;">
            <div style="max-width:1000px;margin:0 auto;">
                <div style="text-align:left;margin-bottom:15px;">
                    <a href="/schedule_hub" style="display:inline-block;padding:8px 16px;background:#95a5a6;color:white;text-decoration:none;border-radius:6px;font-size:14px;">← Назад в меню</a>
                </div>

                <h1 style="margin-top:0;text-align:center;">📅 Расписание</h1>

                {f'<div style="text-align:center;margin:20px 0;">{tabs_html}</div>' if tabs_html else ''}
                {clear_html}

                <table border="1" cellpadding="10" style="margin: 20px auto; border-collapse: collapse; width: 100%; background: white;">
                    <tr style="background: #eee;">
                        <th>Время</th><th>Мероприятие</th><th>Место</th><th>Ответственные</th><th>Отряд</th>
                        {f'<th>Действия</th>' if is_admin_like(role) else ''}
                    </tr>
    """

    if not items_data:
        html += f"<tr><td colspan='6' style='color: #999; padding: 30px; text-align:center;'>Расписание пусто.</td></tr>"
    else:
        for item_id, time, title, place, resp, grp in items_data:
            edit_cell = ""
            if is_admin_like(role):
                edit_cell = f"""<td style="white-space:nowrap;">
                    <a href="/admin/schedule/edit_form/{item_id}" style="color:#f39c12;text-decoration:none;font-size:16px;" title="Изменить">✏️</a>
                    <form action="/admin/schedule/delete/{item_id}" method="POST" style="margin:0;display:inline;" onsubmit="return confirm('Удалить эту строку? Она уйдёт в архив.');">
                        <button type="submit" style="background:none;border:none;cursor:pointer;color:#e74c3c;font-size:16px;" title="Удалить">🗑️</button>
                    </form>
                </td>"""
            html += f"<tr><td>{time}</td><td>{title}</td><td>{place}</td><td>{resp or '—'}</td><td><b>{grp or 'Все'}</b></td>{edit_cell}</tr>"

    html += """
                </table>
            </div>
        </main>
    """
    html += render_footer()
    html += "</body></html>"
    return html


@router.get("/admin/upload_schedule", response_class=HTMLResponse)
async def upload_schedule_page(request: Request):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    groups = sorted([g.name for g in db.query(Group).all()])
    db.close()

    if not groups:
        group_options = '<option value="" disabled selected>— Сначала создайте отряд —</option>'
    else:
        group_options = '<option value="" disabled selected>— Выберите отряд —</option>'
        group_options += '<option value="">Общее (для всех)</option>'
        for g in groups:
            group_options += f'<option value="{g}">{g}</option>'

    return f"""
    <html><body>
        {render_header(request, active_page='schedule')}
        <main style="flex:1;padding:30px 20px;">
            <div style="max-width:600px;margin:0 auto;">
                <div style="text-align:left;margin-bottom:15px;">
                    <a href="/schedule_hub" style="display:inline-block;padding:8px 16px;background:#95a5a6;color:white;text-decoration:none;border-radius:6px;font-size:14px;">← Назад в меню</a>
                </div>
                <div style="background:white;padding:30px;border-radius:15px;box-shadow:0 4px 15px rgba(0,0,0,0.08);text-align:center;">
                    <h1 style="margin-top:0;">📊 Загрузить расписание</h1>
                    <p style="color: #7f8c8d;">Поддерживаются <b>.xlsx</b> и <b>.pdf</b> (текстовые PDF с таблицами).</p>
                    <p style="color: #7f8c8d;">Колонки: <b>Время · Мероприятие · Место · Ответственные</b></p>

                    <form action="/admin/upload_schedule" method="POST" enctype="multipart/form-data"
                          style="margin: 30px auto; text-align: left;">
                        <p><input type="file" name="file" accept=".xlsx,.pdf" required style="padding: 10px;"></p>
                        <p>
                            <label>Для какого отряда?</label><br>
                            <select name="target_group" required style="padding: 10px; width: 100%; box-sizing: border-box; margin-top: 5px;">
                                {group_options}
                            </select>
                        </p>
                        <p style="color: #7f8c8d; font-size: 14px;">
                            Новое расписание заменит текущее. Старое автоматически уйдёт в архив.
                        </p>
                        <button type="submit" style="padding: 12px 30px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">Загрузить</button>
                    </form>
                </div>
            </div>
        </main>
    </body></html>
    """


@router.post("/admin/upload_schedule", response_class=HTMLResponse)
async def upload_schedule(request: Request, file: UploadFile = File(...), target_group: str = Form("")):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    # --- Валидация отряда ---
    target_group = (target_group or "").strip()
    db = SessionLocal()
    if target_group:
        exists = db.query(Group).filter(Group.name == target_group).first()
        if not exists:
            db.close()
            return HTMLResponse(f"<h1>Отряда '{target_group}' нет</h1><a href='/admin/upload_schedule'>Назад</a>")
    db.close()

    filename = (file.filename or "").lower()
    contents = await file.read()

    # --- Парсинг ---
    warnings = []
    if filename.endswith(".xlsx"):
        try:
            parsed, skipped = parse_schedule_xlsx(contents)
            if skipped:
                warnings.append(f"Пропущены строки: {skipped}")
        except Exception as e:
            return HTMLResponse(f"<h1>Ошибка xlsx: {e}</h1><a href='/admin/upload_schedule'>Назад</a>")
    elif filename.endswith(".pdf"):
        try:
            parsed, warns = parse_schedule_pdf(contents)
            warnings.extend(warns)
        except Exception as e:
            return HTMLResponse(f"<h1>Ошибка pdf: {e}</h1><a href='/admin/upload_schedule'>Назад</a>")
    else:
        return HTMLResponse("<h1>Нужен .xlsx или .pdf</h1><a href='/admin/upload_schedule'>Назад</a>")

    if not parsed:
        warn_html = "".join(f"<li>{w}</li>" for w in warnings)
        return HTMLResponse(f"""
        <html><body style="font-family: Arial; text-align:center; margin-top:50px;">
            <h1>⚠️ Не удалось извлечь строки</h1>
            <ul style="text-align:left;display:inline-block;">{warn_html}</ul>
            <a href="/admin/upload_schedule">Назад</a>
        </body></html>
        """)

    # --- Архивируем и удаляем ТОЛЬКО этот отряд, потом пишем новое ---
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db = SessionLocal()
    try:
        if target_group:
            old = db.query(ScheduleItem).filter(
                ScheduleItem.group_name == target_group
            ).all()
        else:
            old = db.query(ScheduleItem).filter(
                (ScheduleItem.group_name == "") | (ScheduleItem.group_name == None)
            ).all()

        for it in old:
            db.add(ScheduleArchive(
                uploaded_at=stamp,
                time=it.time, title=it.title, place=it.place,
                responsible=it.responsible or ""
            ))
            db.delete(it)

        db.commit()

        for r in parsed:
            db.add(ScheduleItem(
                time=r["time"],
                title=r["title"],
                place=r["place"],
                responsible=r.get("responsible", ""),
                group_name=target_group
            ))
        db.commit()
        old_count = len(old)
    except Exception as e:
        db.rollback()
        return HTMLResponse(f"<h1>Ошибка: {e}</h1><a href='/admin/upload_schedule'>Назад</a>")
    finally:
        db.close()

    warn_html = "".join(f"<li style='color:#e67e22;'>{w}</li>" for w in warnings)
    group_label = target_group or "Общее (для всех)"
    logger.info(f"Загружено расписание для '{target_group or 'общее'}': {len(parsed)} строк")
    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 100px;">
        <div style="background: white; max-width: 500px; margin: 0 auto; padding: 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h1 style="color: #27ae60; font-size: 50px; margin: 0;">✅</h1>
            <h2>Расписание загружено</h2>
            <p>Отряд: <b>{group_label}</b></p>
            <p>Строк: <b>{len(parsed)}</b></p>
            <p>Старые строки этого отряда в архив: <b>{old_count}</b></p>
            {f'<ul style="text-align:left;display:inline-block;">{warn_html}</ul>' if warnings else ''}
            <a href="/schedule?group={target_group}" style="padding: 12px 25px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px;">Смотреть</a>
            <a href="/admin/schedule_archive" style="padding: 12px 25px; background: #9b59b6; color: white; text-decoration: none; border-radius: 5px;">Архив</a>
        </div>
    </body></html>
    """

@router.post("/admin/clear_schedule")
async def clear_schedule(request: Request, scope: str = Form("all")):
    """
    scope: "all" | "common" | имя отряда
    Всё удаляемое уходит в архив.
    """
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = SessionLocal()
    try:
        q = db.query(ScheduleItem)
        if scope == "all":
            items = q.all()
        elif scope == "common":
            items = q.filter(
                (ScheduleItem.group_name == "") | (ScheduleItem.group_name == None)
            ).all()
        else:
            exists = db.query(Group).filter(Group.name == scope).first()
            if not exists:
                db.close()
                return HTMLResponse(f"<h1>Отряда '{scope}' нет</h1><a href='/schedule'>Назад</a>")
            items = q.filter(ScheduleItem.group_name == scope).all()

        for it in items:
            db.add(ScheduleArchive(
                uploaded_at=stamp,
                time=it.time, title=it.title, place=it.place,
                responsible=it.responsible or ""
            ))
            db.delete(it)
        db.commit()
    except Exception as e:
        db.rollback()
        return HTMLResponse(f"<h1>Ошибка: {e}</h1><a href='/schedule'>Назад</a>")
    finally:
        db.close()

    # Возвращаемся на соответствующую вкладку
    if scope in ("all", "common"):
        return RedirectResponse(url="/schedule", status_code=303)
    return RedirectResponse(url=f"/schedule?group={scope}", status_code=303)


@router.get("/admin/schedule_archive", response_class=HTMLResponse)
async def schedule_archive(request: Request):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    archived = db.query(ScheduleArchive).order_by(ScheduleArchive.uploaded_at.desc()).all()
    # Собираем в партии
    batches = {}
    for a in archived:
        batches.setdefault(a.uploaded_at, []).append(
            {"time": a.time, "title": a.title, "place": a.place, "responsible": a.responsible or ""}
        )
    db.close()

    html = """
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px; background: #f4f7f6;">
        <h1>📚 Архив расписаний</h1>
    """

    if batches:
        html += """
        <div style="max-width: 700px; margin: 0 auto 20px auto; background: white; padding: 15px; border-radius: 10px; border: 1px solid #ccc;">
            <form action="/admin/schedule_archive/clear" method="POST" onsubmit="return confirm('Очистить весь архив?');">
                <button type="submit" style="padding: 8px 20px; background: #e74c3c; color: white; border: none; border-radius: 5px; cursor: pointer;">🗑️ Очистить весь архив</button>
            </form>
        </div>
        """
        for stamp, items in batches.items():
            rows = "".join(
                f"<tr><td>{i['time']}</td><td>{i['title']}</td><td>{i['place']}</td><td>{i['responsible'] or '—'}</td></tr>"
                for i in items
            )
            html += f"""
            <details style="background:white;border:1px solid #ccc;border-radius:10px;margin:10px auto;max-width:800px;text-align:left;">
                <summary style="cursor:pointer;padding:15px;background:#ecf0f1;border-radius:10px;font-weight:bold;display:flex;justify-content:space-between;">
                    <span>📅 Партия от {stamp}</span>
                    <span style="color:#7f8c8d;font-weight:normal;">{len(items)} записей</span>
                </summary>
                <div style="padding:0 15px 15px 15px;">
                    <table border="1" cellpadding="8" style="width:100%;border-collapse:collapse;margin-top:10px;">
                        <tr style="background:#eee;"><th>Время</th><th>Мероприятие</th><th>Место</th><th>Ответственные</th></tr>
                        {rows}
                    </table>
                </div>
            </details>
            """
    else:
        html += "<p style='color:#999;'>Архив пуст.</p>"

    html += '<br><a href="/schedule_hub">Назад в меню</a></body></html>'
    return html


@router.post("/admin/schedule_archive/clear")
async def clear_archive(request: Request):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)
    db = SessionLocal()
    db.query(ScheduleArchive).delete()
    db.commit()
    db.close()
    return RedirectResponse(url="/admin/schedule_archive", status_code=303)

#---------------------------------------------------------------------------------------------------------------------

@router.post("/admin/schedule/edit/{item_id}")
async def edit_schedule_item(
    request: Request,
    item_id: int,
    time: str = Form(...),
    title: str = Form(...),
    place: str = Form(...),
    responsible: str = Form(""),
    group_name: str = Form(""),
):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    item = db.query(ScheduleItem).filter(ScheduleItem.id == item_id).first()
    if item:
        item.time = time.strip()
        item.title = title.strip()
        item.place = place.strip()
        item.responsible = responsible.strip()
        item.group_name = group_name.strip()
        db.commit()
    db.close()

    return RedirectResponse(url="/schedule", status_code=303)

#-------------------------------------------------------------------------------------------------------

@router.get("/admin/schedule/edit_form/{item_id}", response_class=HTMLResponse)
async def edit_schedule_form(request: Request, item_id: int):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    item = db.query(ScheduleItem).filter(ScheduleItem.id == item_id).first()
    if not item:
        db.close()
        return RedirectResponse(url="/schedule", status_code=303)

    # Сохраняем в переменные до close()
    i_id = item.id
    i_time = item.time
    i_title = item.title
    i_place = item.place
    i_resp = item.responsible or ""
    i_group = item.group_name or ""
    db.close()

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>✏️ Редактировать строку расписания</h1>
        <form action="/admin/schedule/edit/{i_id}" method="POST"
              style="max-width: 500px; margin: 20px auto; background: white; padding: 25px; border-radius: 10px; border: 1px solid #ccc; text-align: left;">
            <p><b>Время:</b><br>
                <input type="text" name="time" value="{i_time}" required style="padding: 10px; width: 100%; box-sizing: border-box;"></p>
            <p><b>Мероприятие:</b><br>
                <input type="text" name="title" value="{i_title}" required style="padding: 10px; width: 100%; box-sizing: border-box;"></p>
            <p><b>Место:</b><br>
                <input type="text" name="place" value="{i_place}" style="padding: 10px; width: 100%; box-sizing: border-box;"></p>
            <p><b>Ответственные:</b><br>
                <input type="text" name="responsible" value="{i_resp}" style="padding: 10px; width: 100%; box-sizing: border-box;"></p>
            <br>
            <p><b>Отряд (Оставьте пустым, если мероприятие для всех):</b><br>
                <input type="text" name="group_name" value="{i_group}" style="padding: 10px; width: 100%; box-sizing: border-box;"></p>
            <button type="submit" style="padding: 10px 30px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">💾 Сохранить</button>
            <a href="/schedule" style="margin-left: 15px; color: #7f8c8d;">Отмена</a>
        </form>
    </body></html>
    """

#----------------------------------------------------------------------------------------------------------------------------------------

@router.post("/admin/schedule/delete/{item_id}")
async def delete_schedule_item(request: Request, item_id: int):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    item = db.query(ScheduleItem).filter(ScheduleItem.id == item_id).first()
    if item:
        db.add(ScheduleArchive(
            uploaded_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            time=item.time, title=item.title, place=item.place,
            responsible=item.responsible or ""
        ))
        db.delete(item)
        db.commit()
    db.close()

    # Возвращаемся на ту же страницу
    ref = request.headers.get('referer') or "/schedule"
    return RedirectResponse(url=ref, status_code=303)