# Вход, выход, главная страница
# routers/auth.py

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, User, Notification
from utils import render_header, render_footer
from main import limiter
import logging


logger = logging.getLogger("sozvezdie")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    is_logged_in = request.session.get('user_role') is not None

    if is_logged_in:
        button_html = '<a href="/dashboard" style="padding: 15px 30px; background: #27ae60; color: white; text-decoration: none; border-radius: 5px; font-size: 18px;">Перейти в личный кабинет</a>'
    else:
        button_html = '<a href="/login" style="padding: 15px 30px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; font-size: 18px;">Войти в аккаунт</a>'

    return f"""
    <html>
        <head>
            <title>Созвездие</title>
            <style>
                body {{ font-family: Arial; text-align: center; margin-top: 100px; background-color: #f0f8ff; }}
                h1 {{ color: #2c3e50; font-size: 40px; }}
                p {{ color: #34495e; font-size: 20px; margin-bottom: 40px; }}
            </style>
        </head>
        <body>
            <h1>Добро пожаловать в систему "Созвездие"!</h1>
            <p>Внутренняя цифровая платформа лагеря.</p>
            {button_html}
        </body>
    </html>
    """


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get('user_role'):
        return RedirectResponse(url="/dashboard", status_code=303)

    return """
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>Вход в систему "Созвездие"</h1>
        <p>Введите ваш код доступа:</p>
        <form action="/login" method="POST">
            <input type="text" name="code" placeholder="Например: a7b-9f2" required style="padding: 10px; font-size: 16px; text-align: center;">
            <br><br>
            <button type="submit" style="padding: 10px 30px; font-size: 16px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer;">Войти</button>
        </form>
        <br><a href="/">На главную</a>
    </body></html>
    """


@router.post("/login", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def process_login(request: Request, code: str = Form(...)):
    from utils import verify_password

    db = SessionLocal()
    all_users = db.query(User).all()
    user = None
    for u in all_users:
        if verify_password(code, u.access_code):
            user = u
            break
    db.close()

    if user:
        logger.info(f"Успешный вход: {user.full_name} ({user.role})")
        request.session['user_role'] = user.role
        request.session['user_name'] = user.full_name
        request.session['group_name'] = user.group_name or ""
        return RedirectResponse(url="/dashboard", status_code=303)
    else:
        logger.warning(f"Неудачная попытка входа (код: {code[:4]}...)")

    return HTMLResponse("""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>⛔ Ошибка входа</h1>
        <p>Такого кода нет в базе данных. Спросите педагога.</p>
        <a href="/login" style="padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px;">← Вернуться назад</a>
    </body></html>
    """, status_code=401)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    role = request.session.get('user_role')
    if not role:
        return RedirectResponse(url="/login", status_code=303)

    # Счётчик непрочитанных
    db = SessionLocal()
    db_user = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    unread = 0
    if db_user:
        unread = db.query(Notification).filter(
            Notification.user_id == db_user.id,
            Notification.is_read == "no"
        ).count()
    db.close()

    # --- Структура меню по ролям ---
    # (иконка, заголовок, ссылка, цвет-акцент, бейдж)
    menu_items = []

    # Общие разделы для всех
    menu_items.append(("📊", "Опросы", "/polls", "#9b59b6"))
    menu_items.append(("📅", "Расписание", "/schedule_hub", "#2c3e50"))
    menu_items.append(("📖", "Информация", "/info", "#1abc9c"))

    # Списки — только admin / support / vospitatel
    if role in ('admin', 'support', 'vospitatel'):
        menu_items.append(("👥", "Списки", "/lists_hub", "#27ae60"))

    # --- Сетка карточек ---
    cards_html = ""
    for icon, title, href, color in menu_items:
        cards_html += f"""
        <a href="{href}" class="menu-card" style="--accent: {color};" onclick="loadPanel('{href}', '{title}', event)">
            <div class="menu-card-icon">{icon}</div>
            <div class="menu-card-title">{title}</div>
        </a>
        """

    titles = {
        'admin': "Панель Администратора",
        'support': "Панель Техподдержки",
        'vospitatel': "Панель Воспитателя",
        'kid': "Личный кабинет",
    }
    title = titles.get(role, "Личный кабинет")

    html = f"""
    <html><body>
        {render_header(request, active_page='dashboard')}

        <main class="dashboard-main">
            <div class="dashboard-left">
                <h1 class="dashboard-title">{title}</h1>
                <p class="dashboard-subtitle">Выберите раздел:</p>
                <div class="menu-grid">
                    {cards_html}
                </div>
            </div>
            <div class="dashboard-right" id="right-panel">
                <div class="empty-state">
                    👈 Выберите раздел слева,<br>чтобы увидеть его здесь
                </div>
            </div>
        </main>

        {render_footer()}

                <style>
            .dashboard-main {{
                display: grid;
                grid-template-columns: 400px 1fr;
                gap: 30px;
                /* Убираем max-width и центрирование */
                margin: 0;
                padding: 30px 30px 40px 30px;
                align-items: start;
                box-sizing: border-box;
                width: 100%;
            }}
            .dashboard-left {{
                text-align: left;
                min-width: 0; /* важно для grid */
            }}
            .dashboard-right {{
                background: white;
                border-radius: 16px;
                border: 1px solid #e5e7eb;
                box-shadow: 0 4px 15px rgba(13,59,143,0.05);
                /* Высота = экран минус шапка и отступы, чтобы не уезжать под подвал */
                height: calc(100vh - 180px);
                min-height: 400px;
                max-height: calc(100vh - 180px);
                overflow: hidden;
                position: sticky;
                top: 90px;
                display: flex;
                flex-direction: column;
            }}
            .dashboard-title {{
                font-size: 28px;
                margin: 0 0 8px;
                color: #1f2937;
            }}
            .dashboard-subtitle {{
                color: #6b7280;
                margin: 0 0 24px;
            }}
            .menu-grid {{
                display: flex;
                flex-direction: column;
                gap: 16px;
                width: 100%;
            }}
            .menu-card {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 22px 16px;
                background: white;
                text-decoration: none;
                color: #1f2937;
                box-shadow: 0 2px 10px rgba(13,59,143,0.08);
                border: 3px solid #60a5fa;
                border-radius: 12px;
                transition: transform 0.2s, box-shadow 0.2s, background 0.2s, border-color 0.2s;
                width: 100%;
                box-sizing: border-box; /* критично: рамка не расширяет карточку */
                opacity: 0;
                animation: slideInLeft 0.6s cubic-bezier(0.25, 1, 0.5, 1) forwards;
            }}
            .menu-card:hover {{
                transform: translateX(8px);
                box-shadow: 0 6px 20px rgba(96, 165, 250, 0.3);
                border-color: #0d3b8f;
                background: #f0f7ff;
            }}
            .menu-card-icon {{ font-size: 32px; margin-bottom: 6px; }}
            .menu-card-title {{ font-size: 15px; font-weight: 600; }}

            .menu-card:nth-child(1) {{ animation-delay: 0.1s; }}
            .menu-card:nth-child(2) {{ animation-delay: 0.2s; }}
            .menu-card:nth-child(3) {{ animation-delay: 0.3s; }}
            .menu-card:nth-child(4) {{ animation-delay: 0.4s; }}

            @keyframes slideInLeft {{
                0% {{ opacity: 0; transform: translateX(-100px); }}
                60% {{ opacity: 1; transform: translateX(10px); }}
                80% {{ transform: translateX(-3px); }}
                100% {{ opacity: 1; transform: translateX(0); }}
            }}

            /* Узкие экраны: одна колонка */
            @media (max-width: 900px) {{
                .dashboard-main {{
                    grid-template-columns: 1fr;
                }}
                .dashboard-right {{
                    position: static;
                    min-height: 400px;
                }}
            }}
            .dashboard-right iframe {{
                width: 100%;
                flex: 1;
                border: none;
                display: block;
            }}
            .dashboard-right .empty-state {{
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100%;
                color: #9ca3af;
                font-size: 16px;
                text-align: center;
                padding: 40px;
                box-sizing: border-box;
            }}            
        </style>
    </body></html>
    """

    # Скрипт выносим отдельно — так JS-скобки не конфликтуют с f-строкой
    script = """
    <script>
        function loadPanel(url, title, event) {
            event.preventDefault();
            const panel = document.getElementById('right-panel');
            panel.innerHTML = `
                <div style="padding: 15px 20px; border-bottom: 1px solid #e5e7eb; background: #f8faff; display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; font-size: 16px;">${title}</h3>
                </div>
                <iframe src="${url}" style="width: 100%; height: calc(100% - 54px); border: none; background: white;"></iframe>
            `;
        }
    </script>
    """
    return html.replace("</body>", script + "</body>")
@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

#----------------------------------------------------------------------------

@router.get("/my_kids", response_class=HTMLResponse)
async def my_kids(request: Request):
    if request.session.get('user_role') != 'vospitatel':
        return RedirectResponse(url="/dashboard", status_code=303)

    db = SessionLocal()
    me = db.query(User).filter(User.full_name == request.session.get('user_name')).first()
    if not me:
        db.close()
        return RedirectResponse(url="/dashboard", status_code=303)

    my_group = me.group_name
    kids = db.query(User).filter(
        User.role == 'kid',
        User.group_name == my_group
    ).order_by(User.full_name).all()

    kids_data = [(k.id, k.full_name, k.room or "") for k in kids]
    db.close()

    html = f"""
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>👦 Мои дети (отряд «{my_group}»)</h1>
        <div style="max-width: 700px; margin: 20px auto;">
    """

    if not kids_data:
        html += "<p>В вашем отряде пока нет детей.</p>"
    else:
        html += """
        <table border="1" cellpadding="10" style="width: 100%; border-collapse: collapse;">
            <tr style="background: #eee;"><th>ФИО</th><th>Комната</th></tr>
        """
        for k_id, k_name, k_room in kids_data:
            html += f"""
            <tr>
                <td>{k_name}</td>
                <td>
                    <form action="/admin/change_room/{k_id}" method="POST" style="margin:0;display:flex;gap:5px;justify-content:center;">
                        <input type="text" name="new_room" value="{k_room}" placeholder="—" style="padding:5px;width:100px;">
                        <button type="submit" style="padding:5px 10px;background:#3498db;color:white;border:none;border-radius:5px;cursor:pointer;">💾</button>
                    </form>
                </td>
            </tr>
            """
        html += "</table>"

    html += """
        </div>
        <br><a href="/lists_hub">← Назад в меню «Списки»</a>
    </body></html>
    """
    return html