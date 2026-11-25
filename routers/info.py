# Статьи о Созвездии
# routers/info.py

from utils import is_admin_like, is_admin
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import SessionLocal, Article

router = APIRouter()


@router.get("/info", response_class=HTMLResponse)
async def info_page(request: Request):
    if not request.session.get('user_role'):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    articles = db.query(Article).all()

    html = """
    <html><body style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1>📖 Информация о Созвездии</h1>
        <p>Полезные статьи, правила и новости лагеря.</p>
        <div style="text-align: left; max-width: 700px; margin: 0 auto;">
    """

    for a in articles:
        html += f"""
        <div style="border: 1px solid #ccc; border-radius: 10px; padding: 20px; margin-bottom: 20px;">
            <h2>{a.title}</h2>
            <p style="white-space: pre-wrap;">{a.content}</p>
        """
        # Кнопка удаления — админ и поддержка
        if is_admin_like(request.session.get('user_role')):
            html += f"""
            <form action="/info/delete/{a.id}" method="POST" style="margin: 0;" onsubmit="return confirm('Удалить статью «{a.title}»?');">
                <button type="submit" style="padding: 5px 15px; background: #e74c3c; color: white; border: none; border-radius: 5px; cursor: pointer;">🗑️ Удалить</button>
            </form>
            """
        html += "</div>"

    if not articles:
        html += "<p style='text-align: center;'>Статей пока нет.</p>"

    html += "</div>"

    if is_admin(request.session.get('user_role')):  # is_admin, не is_admin_like!
        html += """
        <br><hr><br>
        <h3>Добавить новую статью (Только для Администрации)</h3>
        <form action="/info/add" method="POST">
            <p><input type="text" name="title" placeholder="Заголовок" required style="padding: 10px; width: 500px;"></p>
            <p><textarea name="content" placeholder="Текст статьи..." required style="padding: 10px; width: 500px; height: 100px;"></textarea></p>
            <button type="submit" style="padding: 10px 20px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer;">Опубликовать</button>
        </form>
        """

    html += """
    </body></html>
    """
    db.close()
    return html


@router.post("/info/add")
async def add_article(request: Request, title: str = Form(...), content: str = Form(...)):
    if not is_admin(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)

    db = SessionLocal()
    db.add(Article(title=title, content=content))
    db.commit()
    db.close()
    return RedirectResponse(url="/info", status_code=303)

#----------------------------------------------------------------------------------------

@router.post("/info/delete/{article_id}")
async def delete_article(request: Request, article_id: int):
    if not is_admin_like(request.session.get('user_role')):
        return RedirectResponse(url="/login", status_code=303)
    db = SessionLocal()
    a = db.query(Article).filter(Article.id == article_id).first()
    if a:
        db.delete(a)
        db.commit()
    db.close()
    return RedirectResponse(url="/info", status_code=303)