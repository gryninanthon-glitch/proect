# Опросы
# routers/polls.py

from utils import is_admin_like, groups_options_html, ROLE_NAMES
import datetime
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, User, Poll, PollAnswer, Group

router = APIRouter()

@router.get("/create_poll", response_class=HTMLResponse)
async def create_poll_page(request: Request):
    role = request.session.get('user_role')
    if role not in ('admin', 'support', 'vospitatel'):
        return RedirectResponse(url="/dashboard", status_code=303)

    group_options = '<option value="Все">— Всем —</option>' + groups_options_html(allow_empty=False)

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>Создать новый опрос</h1>
        <form action="/create_poll" method="POST">
            <p><input type="text" name="question" placeholder="Вопрос" required style="padding: 10px; width: 400px;"></p>
            <p><input type="text" name="options" placeholder="Варианты через запятую (Да,Нет)" required style="padding: 10px; width: 400px;"></p>

            <p>
                <label>Кому: </label>
                <select name="group_name" style="padding: 10px;">
                    {group_options}
                </select>
            </p>

            <p style="margin-top: 15px;"><b>Режим:</b></p>
            <p>
                <label style="display: block; margin: 8px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; cursor: pointer;">
                    <input type="radio" name="mode" value="timed" checked onchange="toggleMode()">
                    <b>По часам</b> — закроется автоматически через указанное время
                </label>
                <label style="display: block; margin: 8px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; cursor: pointer;">
                    <input type="radio" name="mode" value="forever" onchange="toggleMode()">
                    <b>Бессрочный</b> — закрывается вручную кнопкой «Закрыть»
                </label>
            </p>

            <p id="duration_field">
                <label>Срок (в часах): </label>
                <input type="number" name="duration_hours" value="24" min="1" max="720" style="padding: 10px; width: 80px;">
            </p>

            <button type="submit" style="padding: 10px 20px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer;">Создать опрос</button>
        </form>

        <script>
            function toggleMode() {{
                const mode = document.querySelector('input[name="mode"]:checked').value;
                document.getElementById('duration_field').style.display = (mode === 'timed') ? 'block' : 'none';
            }}
            toggleMode();
        </script>

        <br><a href="/polls">Назад к опросам</a>
    </body></html>
    """


@router.post("/create_poll", response_class=HTMLResponse)
async def process_create_poll(
        request: Request,
        question: str = Form(...),
        options: str = Form(...),
        group_name: str = Form("Все"),
        mode: str = Form("timed"),           # "timed" | "forever"
        duration_hours: int = Form(24),
):
    role = request.session.get('user_role')
    if role not in ('admin', 'support', 'vospitatel'):
        return RedirectResponse(url="/dashboard", status_code=303)

    # Валидация группы
    if group_name != "Все":
        db = SessionLocal()
        exists = db.query(Group).filter(Group.name == group_name).first()
        db.close()
        if not exists:
            return HTMLResponse(f"<h1>Отряда '{group_name}' нет</h1><a href='/create_poll'>Назад</a>")

    # Считаем время
    if mode == "forever":
        expires_str = "Без срока"
    else:
        expire_time = datetime.datetime.now() + datetime.timedelta(hours=duration_hours)
        expires_str = expire_time.strftime("%Y-%m-%d %H:%M")

    db = SessionLocal()
    new_poll = Poll(
        question=question,
        options=options,
        group_name=group_name,
        expires_at=expires_str,
        is_closed="no",
    )
    db.add(new_poll)
    db.commit()
    db.close()

    mode_label = "бессрочный (закрывается вручную)" if mode == "forever" else f"закроется {expires_str}"

    return f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 100px; background: #f4f7f6;">
        <div style="background: white; max-width: 500px; margin: 0 auto; padding: 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h1 style="color: #27ae60; font-size: 50px; margin: 0;">✅</h1>
            <h2>Опрос создан!</h2>
            <p>Вопрос: <b>{question}</b></p>
            <p>Режим: <b>{mode_label}</b></p>
            <br>
            <a href="/polls" style="padding: 12px 25px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">К опросам</a>
        </div>
    </body></html>
    """


@router.get("/polls", response_class=HTMLResponse)
async def view_polls(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    user_name = request.session.get('user_name')
    user = db.query(User).filter(User.full_name == user_name).first()
    if not user:
        db.close()
        return RedirectResponse(url="/dashboard", status_code=303)

    role = user.role

    # Получаем все опросы по фильтру
    if role in ('admin', 'support'):
        all_polls = db.query(Poll).order_by(Poll.id.desc()).all()
    elif role == 'vospitatel':
        all_polls = db.query(Poll).filter(
            (Poll.group_name == user.group_name) | (Poll.group_name == "Все")
        ).order_by(Poll.id.desc()).all()
    else:  # kid
        all_polls = db.query(Poll).filter(
            (Poll.group_name == user.group_name) | (Poll.group_name == "Все")
        ).order_by(Poll.id.desc()).all()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    def _is_expired(p):
        return p.expires_at != "Без срока" and p.expires_at < now_str

    def _is_closed(p):
        return p.is_closed == "yes" or _is_expired(p)

    html = """
    <html><body style="font-family: Arial; text-align: center; margin-top: 20px;">
    """

    if role in ('admin', 'support', 'vospitatel'):
        html += '<p><a href="/create_poll" style="padding: 10px 20px; background: #27ae60; color: white; text-decoration: none; border-radius: 5px;">+ Создать опрос</a></p>'

    if not all_polls:
        html += "<p>Опросов пока нет.</p>"
    else:
        for poll in all_polls:
            answer_count = db.query(PollAnswer).filter(PollAnswer.poll_id == poll.id).count()
            closed = _is_closed(poll)

            if closed:
                if poll.is_closed == "yes":
                    status_badge = "<span style='color: #e74c3c;'>🔴 Закрыт вручную</span>"
                else:
                    status_badge = "<span style='color: #e74c3c;'>🔴 Закрыт по времени</span>"
            else:
                if poll.expires_at == "Без срока":
                    status_badge = "<span style='color: #27ae60;'>🟢 Активен (бессрочный)</span>"
                else:
                    status_badge = f"<span style='color: #27ae60;'>🟢 Активен до {poll.expires_at}</span>"

            # Уже ответил?
            already_answered = db.query(PollAnswer).filter(
                PollAnswer.poll_id == poll.id,
                PollAnswer.user_id == user.id
            ).first()

            html += f"""
            <div style="border: 1px solid #ccc; padding: 20px; margin: 10px auto; width: 550px; border-radius: 10px; background: white; text-align: left;">
                <h3 style="margin-top: 0;">{poll.question}</h3>
                <p style="color: #7f8c8d;">Группа: {poll.group_name} | Ответов: <b>{answer_count}</b></p>
                <p>{status_badge}</p>
            """

            # --- kid: форма ответа ---
            if role == 'kid' and not closed and not already_answered:
                options_list = [o.strip() for o in poll.options.split(',')]
                html += f'<form action="/polls/{poll.id}/answer" method="POST" style="margin-top: 12px;">'
                for opt in options_list:
                    html += f"""
                    <label style="display: block; margin: 5px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; cursor: pointer;">
                        <input type="radio" name="answer" value="{opt}" required> {opt}
                    </label>
                    """
                html += '<button type="submit" style="margin-top: 10px; padding: 10px 20px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer;">Ответить</button></form>'
            elif role == 'kid' and already_answered:
                html += f"<p style='background:#eafaf1;padding:10px;border-radius:5px;color:#27ae60;'>✅ Вы ответили: <b>{already_answered.answer}</b></p>"

            # --- admin/support/vospitatel: кнопки ---
            if role in ('admin', 'support', 'vospitatel'):
                html += '<div style="display:flex;gap:10px;margin-top:12px;justify-content:center;">'
                html += f'<a href="/polls/{poll.id}/stats" style="padding:8px 20px;background:#9b59b6;color:white;text-decoration:none;border-radius:5px;">Детали</a>'
                if not closed:
                    html += f'''
                    <form action="/polls/{poll.id}/close" method="POST" style="margin:0;" onsubmit="return confirm('Закрыть опрос? Новые ответы станут невозможны.');">
                        <button type="submit" style="padding:8px 20px;background:#e67e22;color:white;border:none;border-radius:5px;cursor:pointer;">🔒 Закрыть</button>
                    </form>
                    '''
                html += f'''
                <form action="/admin/delete_poll/{poll.id}" method="POST" style="margin:0;" onsubmit="return confirm('Удалить опрос со всеми ответами?');">
                    <button type="submit" style="padding:8px 20px;background:#e74c3c;color:white;border:none;border-radius:5px;cursor:pointer;">🗑️ Удалить</button>
                </form>
                '''
                html += '</div>'

            html += "</div>"

    html += '</body></html>'
    db.close()
    return html


@router.post("/polls/{poll_id}/answer")
async def answer_poll(request: Request, poll_id: int, answer: str = Form(...)):
    db = SessionLocal()
    user_name = request.session.get('user_name')
    user = db.query(User).filter(User.full_name == user_name).first()
    poll = db.query(Poll).filter(Poll.id == poll_id).first()

    if not user or not poll:
        db.close()
        return RedirectResponse(url="/polls", status_code=303)

    # Проверка «закрыт»
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    is_expired = poll.expires_at != "Без срока" and poll.expires_at < now_str
    if poll.is_closed == "yes" or is_expired:
        db.close()
        return RedirectResponse(url="/polls", status_code=303)

    # Защита: нельзя ответить дважды
    already = db.query(PollAnswer).filter(
        PollAnswer.poll_id == poll_id,
        PollAnswer.user_id == user.id
    ).first()
    if already:
        db.close()
        return RedirectResponse(url="/polls", status_code=303)

    db.add(PollAnswer(poll_id=poll_id, user_id=user.id, answer=answer))
    db.commit()
    db.close()
    return RedirectResponse(url="/polls", status_code=303)


@router.get("/polls/{poll_id}/stats", response_class=HTMLResponse)
async def poll_stats(request: Request, poll_id: int):
    role = request.session.get('user_role')
    if not (is_admin_like(role) or role == 'vospitatel'):
        return RedirectResponse(url="/dashboard", status_code=303)

    db = SessionLocal()
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        db.close()
        return "<h1>Опрос не найден</h1>"

    if poll.group_name == "Все":
        target_users = db.query(User).all()
    else:
        target_users = db.query(User).filter(User.group_name == poll.group_name).all()

    answers = db.query(PollAnswer).filter(PollAnswer.poll_id == poll_id).all()
    answers_dict = {a.user_id: a.answer for a in answers}

    stats = {}
    for opt in poll.options.split(','):
        stats[opt.strip()] = 0
    for a in answers:
        if a.answer in stats:
            stats[a.answer] += 1

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    is_expired = poll.expires_at != "Без срока" and poll.expires_at < now_str
    if poll.is_closed == "yes":
        status = "🔴 Закрыт вручную"
    elif is_expired:
        status = "🔴 Закрыт по времени"
    elif poll.expires_at == "Без срока":
        status = "🟢 Активен (бессрочный)"
    else:
        status = f"🟢 Активен до {poll.expires_at}"

    html = f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px; background: #f4f7f6;">
        <h1>📊 Результаты опроса</h1>
        <h2 style="color: #2c3e50;">{poll.question}</h2>
        <p>Группа: <b>{poll.group_name}</b></p>
        <p style="font-weight:bold;">{status}</p>

        <div style="display: flex; justify-content: center; gap: 30px; margin-bottom: 30px;">
    """

    for option, count in stats.items():
        html += f"""
        <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); min-width: 150px;">
            <h3 style="margin: 0; color: #3498db; font-size: 30px;">{count}</h3>
            <p style="margin: 5px 0 0 0; color: #7f8c8d;">{option}</p>
        </div>
        """

    html += """
        </div>

        <h3>Детально по участникам:</h3>
        <div style="max-width: 600px; margin: 0 auto; height: 400px; overflow-y: auto; background: white; border-radius: 10px; border: 1px solid #ccc;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #ecf0f1; position: sticky; top: 0;">
                    <th style="padding: 15px; text-align: left;">Участник</th>
                    <th style="padding: 15px; text-align: left;">Ответ</th>
                </tr>
    """

    for u in target_users:
        user_answer = answers_dict.get(u.id)
        if ROLE_NAMES[u.role] != "Участник":
            continue
        if user_answer:
            answer_html = f"<span style='color: #27ae60; font-weight: bold;'>{user_answer}</span>"
        else:
            answer_html = "<span style='color: #e74c3c;'>Не ответил</span>"

        html += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 15px; text-align: left;">{u.full_name} ({ROLE_NAMES.get(u.role, u.role)})</td>
                    <td style="padding: 15px; text-align: left;">{answer_html}</td>
                </tr>
        """

    html += """
            </table>
        </div>
        <br>
        <a href="/polls" style="padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">← Назад к опросам</a>
    </body></html>
    """
    db.close()
    return html

@router.post("/polls/{poll_id}/close")
async def close_poll(request: Request, poll_id: int):
    role = request.session.get('user_role')
    if role not in ('admin', 'support', 'vospitatel'):
        return RedirectResponse(url="/dashboard", status_code=303)

    db = SessionLocal()
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if poll:
        poll.is_closed = "yes"
        db.commit()
    db.close()
    return RedirectResponse(url="/polls", status_code=303)

@router.post("/admin/delete_poll/{poll_id}")
async def delete_poll(request: Request, poll_id: int):
    role = request.session.get('user_role')
    if not (is_admin_like(role) or role == 'vospitatel'):
        return RedirectResponse(url="/dashboard", status_code=303)

    db = SessionLocal()
    db.query(PollAnswer).filter(PollAnswer.poll_id == poll_id).delete()
    db.query(Poll).filter(Poll.id == poll_id).delete()
    db.commit()
    db.close()

    return RedirectResponse(url="/polls", status_code=303)