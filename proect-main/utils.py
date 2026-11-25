#общие функции (ROLE_NAMES, get_current_user, create_notification, seed_db)
# utils.py
from database import SessionLocal, User, Notification, Message

# Расшифровка ролей — нужна и в admin.py, и в polls.py, и в messages.py
# utils.py
import io
from passlib.context import CryptContext
import pdfplumber

ROLE_NAMES = {
    "admin": "Администрация",
    "vospitatel": "Воспитатель",
    "kid": "Участник",
    "support": "Техподдержка",
}


def get_current_user(request):
    """Достаёт объект User из сессии. Возвращает None, если не залогинен.
    Заменяет вот эту повторяющуюся конструкцию:
        user_name = request.session.get('user_name')
        user = db.query(User).filter(User.full_name == user_name).first()
    """
    user_name = request.session.get('user_name')
    if not user_name:
        return None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.full_name == user_name).first()
        return user
    finally:
        db.close()


def create_notification(user_id: int, text: str):
    """Создать одно уведомление пользователю."""
    db = SessionLocal()
    try:
        note = Notification(user_id=user_id, text=text)
        db.add(note)
        db.commit()
    finally:
        db.close()


def seed_db():
    """Заполняет базу тестовыми пользователями, если она пустая."""
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            codes = {
                "admin":   ("admin1",    "Админ: Макет",       "SOZV-ADM-9X4K",     ""),
                "vospitatel": ("vosp_1", "Воспитатель: Макет", "SOZV-VOS-7P2M",     "А"),
                "kid":     ("kid_1",     "Участник: Макет",    "SOZV-KID-3Q8F",     "А"),
                "support": ("support_1", "Техподдержка",       "SOZV-SUP-HELP-2024","АБВГД"),
            }
            for role, (max_id, full_name, code, group) in codes.items():
                db.add(User(
                    max_id=max_id,
                    full_name=full_name,
                    role=role,
                    access_code=hash_password(code),
                    access_code_plain=code,
                    group_name=group,
                ))
            db.commit()
    finally:
        db.close()

#------------------------------------------------------------------------------


def count_unread_notifications(user_id: int) -> int:
    """Сколько непрочитанных уведомлений у пользователя."""
    db = SessionLocal()
    try:
        return db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == "no"
        ).count()
    finally:
        db.close()


def has_unread_from(sender_id: int, receiver_id: int) -> bool:
    """Есть ли непрочитанное сообщение от sender к receiver.
    Считаем 'непрочитанным' любое сообщение, после которого у receiver
    не появилось уведомление с прочтённым is_read='yes'...
    Проще: пока проще считать, что если есть сообщение от X к Y
    и Y ещё ни разу не открывал чат с X — считаем непрочитанным.
    """
    # Простая реализация: есть ли сообщение, которое ещё не «открыли».
    # В нашей модели Message нет поля is_read, поэтому используем Notification.
    db = SessionLocal()
    try:
        # Ищем уведомления типа "💬 Новое сообщение от X" у получателя,
        # которые ещё не прочитаны (is_read='no')
        sender = db.query(User).filter(User.id == sender_id).first()
        if not sender:
            return False
        note = db.query(Notification).filter(
            Notification.user_id == receiver_id,
            Notification.is_read == "no",
            Notification.text.like(f"💬 Новое сообщение от {sender.full_name}%")
        ).first()
        return note is not None
    finally:
        db.close()

#----------------------------------------------------------------------------

def is_admin_like(role: str) -> bool:
    """Админ или техподдержка — у них одинаковые права на большинство действий."""
    return role in ('admin', 'support')


def is_admin(role: str) -> bool:
    """Только «чистый» админ (без поддержки) — для мест, где поддержке нельзя.
    Например: скрытие чужих админских кодов, удаление других админов."""
    return role == 'admin'

#----------------------------------------------------------------------------

def get_all_groups():
    """Возвращает отсортированный список названий отрядов из таблицы Group."""
    from database import SessionLocal, Group
    db = SessionLocal()
    try:
        return sorted([g.name for g in db.query(Group).all()])
    finally:
        db.close()

#----------------------------------------------------------------------------

def groups_options_html(selected: str = "", allow_empty: bool = True, empty_label: str = "— без отряда —"):
    """Возвращает HTML для <option> со всеми группами. selected — что выбрать по умолчанию."""
    from database import SessionLocal, Group
    db = SessionLocal()
    try:
        names = sorted([g.name for g in db.query(Group).all()])
    finally:
        db.close()
    html = ""
    if allow_empty:
        sel = ' selected' if not selected else ''
        html += f'<option value=""{sel}>{empty_label}</option>'
    for n in names:
        sel = ' selected' if n == selected else ''
        html += f'<option value="{n}"{sel}>{n}</option>'
    return html

#----------------------------------------------------------------------------

def parse_schedule_xlsx(file_bytes: bytes) -> list[dict]:
    """Парсит xlsx → список dict(time, title, place, responsible)."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True)
    ws = wb.active
    rows = []
    skipped = []
    for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if not row or all(c is None for c in row):
            continue
        if idx == 1 and isinstance(row[0], str) and row[0].strip().lower() == "time":
            continue

        time_val = _normalize_time(row[0])
        title = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        place = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
        responsible = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
        group_name = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""

        if not time_val or not title:
            skipped.append(idx)
            continue
        rows.append({"time": time_val, "title": title, "place": place,
                     "responsible": responsible, "group_name": group_name})
    return rows, skipped


def parse_schedule_pdf(file_bytes: bytes) -> tuple[list[dict], list[str]]:
    """
    Парсит PDF → список dict(time, title, place, responsible).
    Возвращает (rows, warnings).
    Работает для текстовых PDF с таблицами.
    """
    rows = []
    warnings = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                if not tables:
                    warnings.append(f"Стр. {page_num}: таблиц не найдено")
                    continue
                for table in tables:
                    for row_idx, row in enumerate(table):
                        if not row or all((c is None or str(c).strip() == "") for c in row):
                            continue
                        # Пропускаем заголовок таблицы
                        first = (row[0] or "").strip().lower() if row else ""
                        if first in ("время", "time"):
                            continue
                        # Ожидаем как минимум 2 колонки: время и мероприятие
                        if len(row) < 2:
                            warnings.append(f"Стр. {page_num}, стр. {row_idx+1}: слишком мало колонок")
                            continue

                        time_val = str(row[0] or "").strip()
                        title = str(row[1] or "").strip()
                        place = str(row[2] or "").strip() if len(row) > 2 and row[2] else ""
                        responsible = str(row[3] or "").strip() if len(row) > 3 and row[3] else ""
                        group_name = str(row[4] or "").strip() if len(row) > 4 and row[4] else ""

                        if not time_val or not title:
                            continue
                        rows.append({"time": time_val, "title": title, "place": place,
                                     "responsible": responsible, "group_name": group_name})
    except Exception as e:
        warnings.append(f"Ошибка чтения PDF: {e}")
    return rows, warnings


def _normalize_time(raw) -> str:
    """datetime.time/str → 'HH:MM'."""
    import datetime as _dt
    if raw is None:
        return ""
    if isinstance(raw, (_dt.time, _dt.datetime)):
        return raw.strftime("%H:%M")
    s = str(raw).strip()
    # "8:00:00" → "8:00"
    if s.count(":") == 2:
        parts = s.split(":")
        return f"{parts[0]}:{parts[1]}"
    return s

#------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# Работа со списками детей (фича «Отправить файлом»)
# ----------------------------------------------------------------------------

KIDS_COLUMNS = ["ФИО", "Код", "Комната", "Группа"]


def parse_kids_list_xlsx(file_bytes: bytes) -> tuple[list[dict], list[str]]:
    """Парсит .xlsx со списком детей → (rows, warnings).

    Ожидаемые колонки (в любом порядке, но в таком):
        ФИО | Код | Комната | Группа
    Первая строка (заголовок) пропускается автоматически.
    """
    from openpyxl import load_workbook

    rows, warnings = [], []
    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as e:
        return [], [f"Не удалось открыть xlsx: {e}"]

    ws = wb.active
    for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        # Пропускаем заголовок: "ФИО", "Name" и т.п.
        first = str(row[0] or "").strip().lower()
        if idx == 1 and first in ("фио", "ф.и.о.", "name", "имя"):
            continue

        name = str(row[0] or "").strip() if len(row) > 0 else ""
        code = str(row[1] or "").strip() if len(row) > 1 else ""
        room = str(row[2] or "").strip() if len(row) > 2 else ""
        group = str(row[3] or "").strip() if len(row) > 3 else ""

        if not name:
            warnings.append(f"Стр. {idx}: нет ФИО — пропущено")
            continue

        rows.append({"name": name, "code": code, "room": room, "group": group})

    return rows, warnings


def parse_kids_list_pdf(file_bytes: bytes) -> tuple[list[dict], list[str]]:
    """Парсит PDF с таблицей детей → (rows, warnings).

    Работает для текстовых PDF (не скан).
    Колонки те же: ФИО | Код | Комната | Группа.
    """

    rows, warnings = [], []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                if not tables:
                    warnings.append(f"Стр. {page_num}: таблиц не найдено")
                    continue
                for table in tables:
                    for row_idx, row in enumerate(table):
                        if not row or all((c is None or str(c).strip() == "") for c in row):
                            continue
                        first = str(row[0] or "").strip().lower()
                        if first in ("фио", "ф.и.о.", "name", "имя"):
                            continue

                        name = str(row[0] or "").strip() if len(row) > 0 else ""
                        code = str(row[1] or "").strip() if len(row) > 1 else ""
                        room = str(row[2] or "").strip() if len(row) > 2 else ""
                        group = str(row[3] or "").strip() if len(row) > 3 else ""

                        if not name:
                            warnings.append(f"Стр. {page_num}, ст. {row_idx + 1}: нет ФИО — пропущено")
                            continue

                        rows.append({"name": name, "code": code, "room": room, "group": group})
    except Exception as e:
        warnings.append(f"Ошибка чтения PDF: {e}")

    return rows, warnings


def make_kids_list_xlsx(rows: list[dict], title: str = "Список детей") -> bytes:
    """Создаёт .xlsx из списка dict'ов → bytes.

    Используется для скачивания списка (кнопка «Скачать в Excel»).
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = title[:30]  # Excel ограничивает длину имени листа

    # Заголовки
    ws.append(KIDS_COLUMNS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Данные
    for r in rows:
        ws.append([
            r.get("name", ""),
            r.get("code", ""),
            r.get("room", ""),
            r.get("group", ""),
        ])

    # Автоширина столбцов (грубо, но красиво)
    for col_idx, col_letter in enumerate(["A", "B", "C", "D"], start=1):
        max_len = len(KIDS_COLUMNS[col_idx - 1])
        for r in rows:
            val = str(r.get(KIDS_COLUMNS[col_idx - 1].lower() if False else
                            ["name", "code", "room", "group"][col_idx - 1], ""))
            max_len = max(max_len, len(val))
        ws.column_dimensions[col_letter].width = min(max_len + 4, 40)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

#------------------------------------------------------------------------------------------------

# ============================================================================
# ВИЗУАЛ: общая шапка и подвал
# ============================================================================

def render_header(request, active_page: str = "") -> str:
    """Возвращает HTML шапки. active_page — для подсветки текущего раздела."""
    role = request.session.get('user_role')
    user_name = request.session.get('user_name', '')

    ROLE_LABELS = {
        'admin': 'Администрация',
        'support': 'Техподдержка',
        'vospitatel': 'Воспитатель',
        'kid': 'Участник',
    }
    role_label = ROLE_LABELS.get(role, '')

    # Счётчик непрочитанных уведомлений
    unread = 0
    try:
        from database import SessionLocal, User, Notification
        db = SessionLocal()
        u = db.query(User).filter(User.full_name == user_name).first()
        if u:
            unread = db.query(Notification).filter(
                Notification.user_id == u.id,
                Notification.is_read == "no"
            ).count()
        db.close()
    except Exception:
        pass

    bell_badge = f'<span class="badge">{unread}</span>' if unread > 0 else ''

    # Кнопки шапки — общие для всех ролей
    # Обрати внимание: значения active_page используются для подсветки
    def nav_item(href, label, icon, key):
        cls = "nav-btn active" if active_page == key else "nav-btn"
        return f'<a href="{href}" class="{cls}">{icon}<span>{label}</span></a>'

    send_notif_link = ""
    if role in ('admin', 'vospitatel'):
        send_notif_link = '<a href="/send_notification">📢 Отправить уведомление</a>'
    header_html = f"""
    <style>
        :root {{
            --brand-blue: #0d3b8f;
            --brand-blue-dark: #082759;
            --brand-orange: #ff7a1a;
            --brand-bg: #eef3fb;
            --text-main: #1f2937;
            --text-muted: #6b7280;
            --white: #ffffff;
            --shadow: 0 4px 14px rgba(13, 59, 143, 0.08);
        }}
        html, body {{
            margin: 0;
            padding: 0;
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
            background: var(--brand-bg);
            color: var(--text-main);
            display: flex;
            flex-direction: column;
        }}
        /* Убираем лишние отступы у подвала */
        footer {{
            margin-top: 0;
        }}
        /* Основной контент должен растягиваться, чтобы подвал прижимался к низу */
        main, .dashboard-main, .page-main {{
            flex: 1 0 auto;
        }}
        footer {{
            flex-shrink: 0;
        }}
        header.sozv-header {{
            background: var(--brand-blue);
            color: var(--white);
            padding: 0 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 64px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.15);
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .logo {{
            font-size: 20px;
            font-weight: bold;
            letter-spacing: 1px;
            color: var(--white);
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .logo::before {{
            content: "✦";
            color: var(--brand-orange);
            font-size: 24px;
        }}
                /* Пиксельный акцент в шапке */
        .pixel-accent {{
            display: flex;
            gap: 3px;
            margin-left: 15px;
        }}
        .pixel-accent span {{
            width: 8px;
            height: 8px;
            border-radius: 2px;
        }}
        .pixel-accent span:nth-child(1) {{ background: #ff7a1a; }}
        .pixel-accent span:nth-child(2) {{ background: #4ade80; }}
        .pixel-accent span:nth-child(3) {{ background: #60a5fa; }}
        .pixel-accent span:nth-child(4) {{ background: #facc15; }}
        .header-nav {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .nav-btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: var(--white);
            text-decoration: none;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 14px;
            transition: background 0.2s;
            position: relative;
        }}
        .nav-btn:hover {{
            background: rgba(255,255,255,0.12);
        }}
        .nav-btn.active {{
            background: rgba(255,255,255,0.18);
            font-weight: bold;
        }}
        .badge {{
            background: var(--brand-orange);
            color: white;
            font-size: 11px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 10px;
            margin-left: 4px;
        }}
        .profile-wrap {{
            position: relative;
        }}
        .profile-btn {{
            background: rgba(255,255,255,0.12);
            border: none;
            color: white;
            padding: 8px 14px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .profile-btn:hover {{
            background: rgba(255,255,255,0.22);
        }}
        .profile-name {{
            max-width: 140px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .profile-role {{
            font-size: 11px;
            opacity: 0.8;
        }}
        .profile-menu {{
            position: absolute;
            right: 0;
            top: 100%;
            background: var(--white);
            color: var(--text-main);
            border-radius: 10px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
            min-width: 200px;
            overflow: hidden;
            z-index: 200;
            /* Анимация */
            opacity: 0;
            transform: translateY(-10px) scaleY(0.8);
            transform-origin: top;
            pointer-events: none;
            transition: opacity 0.2s ease, transform 0.25s cubic-bezier(0.25, 1, 0.5, 1);
            margin-top: 8px;
        }}
        .profile-menu.open {{
            opacity: 1;
            transform: translateY(0) scaleY(1);
            pointer-events: auto;
        }}
        .profile-menu a {{
            display: block;
            padding: 12px 16px;
            color: var(--text-main);
            text-decoration: none;
            font-size: 14px;
        }}
        .profile-menu a:hover {{
            background: var(--brand-bg);
        }}
        .profile-menu a.danger {{
            color: #c0392b;
            border-top: 1px solid #eee;
        }}
        /* Анимация переезда страниц */
        body {{
            transition: transform 0.35s cubic-bezier(0.25, 1, 0.5, 1), opacity 0.35s ease;
        }}
        body.slide-out-left {{ transform: translateX(-100%); opacity: 0; }}
        body.slide-out-right {{ transform: translateX(100%); opacity: 0; }}
        body.slide-in-from-right {{ animation: slideFromRight 0.35s cubic-bezier(0.25, 1, 0.5, 1) forwards; }}
        body.slide-in-from-left {{ animation: slideFromLeft 0.35s cubic-bezier(0.25, 1, 0.5, 1) forwards; }}
        @keyframes slideFromRight {{
            from {{ transform: translateX(100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
        @keyframes slideFromLeft {{
            from {{ transform: translateX(-100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
    </style>
    
    <header class="sozv-header">
        <a href="/dashboard" class="logo">СОЗВЕЗДИЕ</a>
        <div class="pixel-accent">
            <span></span><span></span><span></span><span></span>
        </div>

        <div class="header-nav">
                        <div class="profile-wrap">
                <button class="nav-btn" onclick="toggleNotifMenu(event)" style="background: none; border: none; cursor: pointer;">
                    🔔 Уведомления {bell_badge}
                </button>
                <div class="profile-menu" id="notifMenu" style="min-width: 220px;">
                    <a href="/notifications">📋 Показать уведомления</a>
                    {send_notif_link}
                </div>
            </div>

            <div class="profile-wrap">
                <button class="profile-btn" onclick="toggleProfileMenu(event)">
                    <span>👤</span>
                    <span class="profile-name">{user_name or 'Профиль'}</span>
                </button>
                <div class="profile-menu" id="profileMenu">
                    <div style="padding: 10px 16px; background: #f8faff; font-size: 12px; color: #6b7280;">
                        {role_label}
                    </div>
                    <a href="/profile">👤 Мой профиль</a>
                    <a href="/messages">💬 Сообщения</a>
                    <a href="/logout" class="danger">🚪 Выйти из аккаунта</a>
                </div>
            </div>
        </div>
    </header>
    """
    # Все JS-функции — в отдельной обычной строке (без f)
    header_js = """
    <script>
        function toggleProfileMenu(e) {
            e.stopPropagation();
            document.getElementById('profileMenu').classList.toggle('open');
            document.getElementById('notifMenu').classList.remove('open');
        }
        function toggleNotifMenu(e) {
            e.stopPropagation();
            document.getElementById('notifMenu').classList.toggle('open');
            document.getElementById('profileMenu').classList.remove('open');
        }
        document.addEventListener('click', function() {
            document.getElementById('profileMenu').classList.remove('open');
            document.getElementById('notifMenu').classList.remove('open');
        });
    </script>
    """
    # Если страница открыта внутри iframe — прячем шапку (она уже есть снаружи)
    nav_script = """
    <script>
        (function() {
            // --- Убираем остатки классов от прошлых переходов ---
            document.body.classList.remove('slide-out-left', 'slide-out-right', 'slide-in-from-left', 'slide-in-from-right');

            // --- Анимация переезда при кликах по навигации ---
            document.addEventListener('click', function(e) {
                const link = e.target.closest('a');
                if (!link) return;
                const href = link.getAttribute('href');
                if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
                if (href.startsWith('http') && !href.includes(location.host)) return;
                if (window.self !== window.top) return;

                const isBack = link.textContent.includes('Назад') || href === '/dashboard';
                const isTarget = href.startsWith('/notifications') || href.startsWith('/tickets');

                if (isBack) {
                    e.preventDefault();
                    sessionStorage.setItem('nav_dir', 'back');
                    document.body.classList.add('slide-out-right');
                    setTimeout(() => { window.location.href = href; }, 350);
                } else if (isTarget) {
                    e.preventDefault();
                    sessionStorage.setItem('nav_dir', 'forward');
                    document.body.classList.add('slide-out-left');
                    setTimeout(() => { window.location.href = href; }, 350);
                }
            });

            // --- При загрузке: показываем въезд, если был переход ---
            window.addEventListener('load', function() {
                const dir = sessionStorage.getItem('nav_dir');
                // Не применяем анимацию на дашборде — чтобы не ломать position: fixed
                if (location.pathname === '/dashboard') {
                    document.body.classList.remove('slide-in-from-left', 'slide-in-from-right');
                    sessionStorage.removeItem('nav_dir');
                    return;
                }
                if (dir === 'back') {
                    document.body.classList.add('slide-in-from-left');
                } else if (dir === 'forward') {
                    document.body.classList.add('slide-in-from-right');
                }
                sessionStorage.removeItem('nav_dir');
            });

            // --- Прячем шапку/подвал внутри iframe ---
            if (window.self !== window.top) {
                const header = document.querySelector('header.sozv-header');
                if (header) header.style.display = 'none';
                const footer = document.querySelector('footer');
                if (footer) footer.style.display = 'none';
                // Скрываем кнопку поддержки и её попап внутри iframe
                const fab = document.querySelector('.feedback-fab');
                if (fab) fab.style.display = 'none';
                const popup = document.getElementById('feedbackPopup');
                if (popup) popup.style.display = 'none';
                document.body.style.paddingTop = '0';
                document.body.style.background = 'white';
            }
        })();
    </script>
    """
    # Кнопка поддержки (только для полных страниц, не в iframe)


    # Выводим кнопку, но с флагом: скрыть её, если мы в iframe
    return header_html + header_js + nav_script + render_feedback_fab()

def render_footer() -> str:
    return """
    <footer style="
        background: #082759;
        color: #cdd7ee;
        padding: 30px 24px 20px;
        text-align: center;
        font-size: 13px;
        margin-top: 0;
        flex-shrink: 0;
    ">
        <div style="font-weight: bold; color: white; margin-bottom: 10px; font-size: 15px;">
            ✦ СОЗВЕЗДИЕ
        </div>
        <p style="margin: 6px 0;">Внутренняя цифровая платформа ЦПОД ТО "СОЗВЕЗДИЕ"</p>
        <p style="margin: 6px 0; opacity: 0.7;">
            📞 +7 (000) 000-00-00 · ✉️ info@sozvezdie.local · 📍 г. Москва
        </p>
        <p style="margin-top: 16px; opacity: 0.5; font-size: 11px;">
            © 2026 · Все права защищены
        </p>
    </footer>
    <script>
        if (window.self !== window.top) {
            const f = document.querySelector('footer');
            if (f) f.style.display = 'none';
        }
    </script>
    """

#----------------------------------------------------------------------------------------------------------------------
# ============================================================================
# ХЭШИРОВАНИЕ ПАРОЛЕЙ
# ============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Превращает пароль в хэш (bcrypt)."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет, совпадает ли введённый пароль с хэшем."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

#----------------------------------------------------------------------------------------------------------------------

# ============================================================================
# Плавающая кнопка «Обратная связь»
# ============================================================================

def render_feedback_fab() -> str:
    """Плавающая кнопка поддержки в правом нижнем углу.
    Есть на каждой странице, где вызывается render_header.
    """
    return """
    <style>
        /* Скрываем кнопку внутри iframe — на уровне CSS */
        iframe .feedback-fab,
        iframe #feedbackPopup,
        iframe #feedback-widget {
            display: none !important;
        }        
        .feedback-fab {
            position: fixed;
            bottom: 24px;
            right: 24px;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: #ff7a1a;
            color: white;
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(255, 122, 26, 0.4);
            font-size: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            transition: transform 0.2s;
        }
        .feedback-fab:hover { transform: scale(1.1); }
        .feedback-popup {
            position: fixed;
            bottom: 90px;
            right: 24px;
            width: 320px;
            max-height: 400px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.2);
            z-index: 9999;
            display: none;
            flex-direction: column;
            overflow: hidden;
        }
        .feedback-popup.open { display: flex; }
        .feedback-popup-header {
            background: #0d3b8f;
            color: white;
            padding: 12px 16px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .feedback-popup-body {
            padding: 16px;
            overflow-y: auto;
            flex: 1;
            font-size: 14px;
            text-align: left;
        }
        .feedback-popup-body a {
            display: block;
            padding: 8px 12px;
            margin-bottom: 6px;
            background: #f4f7f6;
            border-radius: 6px;
            color: #1f2937;
            text-decoration: none;
        }
        .feedback-popup-body a:hover { background: #eef3fb; }
    </style>

    <button class="feedback-fab" onclick="toggleFeedback()">💬</button>
    <div class="feedback-popup" id="feedbackPopup">
        <div class="feedback-popup-header">
            <span>Обратная связь</span>
            <button onclick="toggleFeedback()" style="background:none;border:none;color:white;cursor:pointer;font-size:18px;">✕</button>
        </div>
        <div class="feedback-popup-body">
            <p style="color: #7f8c8d; margin-top: 0;">Выберите действие:</p>
            <a href="/tickets">📋 Мои обращения</a>
            <a href="/tickets/create">➕ Создать обращение</a>
        </div>
    </div>

    <script>
        if (window.self !== window.top) {
            const fab = document.querySelector('.feedback-fab');
            if (fab) fab.remove();
            const popup = document.getElementById('feedbackPopup');
            if (popup) popup.remove();
        }    
        function toggleFeedback() {
            document.getElementById('feedbackPopup').classList.toggle('open');
        }
        document.addEventListener('click', function(e) {
            const popup = document.getElementById('feedbackPopup');
            const fab = document.querySelector('.feedback-fab');
            if (popup && fab && !popup.contains(e.target) && !fab.contains(e.target)) {
                popup.classList.remove('open');
            }
        });
    </script>
    """
