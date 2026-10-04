"""Handlerlar uchun umumiy yordamchilar."""
import functools
import logging
from typing import Iterable, Optional

import requests
from gspread.exceptions import APIError
from telebot.types import CallbackQuery, Message

from .. import keyboards as kb
from .. import texts as T
from ..context import Ctx
from ..sheets import ACTIVE, PENDING, SheetsError, User

log = logging.getLogger(__name__)

_SERVICE_ERRORS = (APIError, requests.RequestException, SheetsError)


def safe(ctx: Ctx):
    """Handler ichidagi har qanday xatoni log qiladi va foydalanuvchiga tushunarli javob beradi."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(obj):
            try:
                return fn(obj)
            except Exception as e:  # noqa: BLE001
                log.exception("Handler xatosi (%s)", fn.__name__)
                text = T.SERVICE_DOWN if isinstance(e, _SERVICE_ERRORS) else T.UNEXPECTED_ERROR
                try:
                    if isinstance(obj, CallbackQuery):
                        ctx.bot.answer_callback_query(obj.id)
                    ctx.bot.send_message(obj.from_user.id, text)
                except Exception:  # noqa: BLE001
                    log.exception("Xato haqida xabar yuborib bo'lmadi")
        return wrapper
    return deco


def show_menu(ctx: Ctx, chat_id: int, text: str = T.MENU_HINT) -> None:
    ctx.send(chat_id, text, kb.main_menu())


def active_user(ctx: Ctx, m: Message, notify: bool = True) -> Optional[User]:
    """Foydalanuvchi ro'yxatdan o'tgan va tasdiqlangan bo'lsa, uni qaytaradi."""
    uid = m.from_user.id
    user = ctx.db.get_user(uid)
    if user is None:
        if notify:
            ctx.send(uid, T.NOT_REGISTERED, kb.remove())
        return None
    if ctx.is_admin(uid) and user.status != ACTIVE:
        ctx.db.set_user_status(uid, ACTIVE)
        user.status = ACTIVE
    if user.status == ACTIVE:
        return user
    if notify:
        ctx.send(uid, T.STILL_PENDING if user.status == PENDING else T.ACCESS_DENIED, kb.remove())
    return None


def need_text(ctx: Ctx, m: Message) -> Optional[str]:
    """Matn kutilayotgan bosqichda rasm/stiker kelsa — qayta so'raydi (bot qotib qolmaydi)."""
    if m.content_type != "text" or not (m.text or "").strip():
        ctx.send(m.chat.id, T.TEXT_EXPECTED)
        return None
    return m.text.strip()


def _norm(s: str) -> str:
    for ch in "ʻʼ’‘`´":
        s = s.replace(ch, "'")
    return " ".join(s.lower().split())


def match_option(text: str, options: Iterable[str]) -> Optional[str]:
    """Kiritilgan matnni ro'yxatdagi variant bilan solishtiradi (katta-kichik harf farqsiz)."""
    t = _norm(text)
    for opt in options:
        if _norm(opt) == t:
            return opt
    return None


def save_row(ctx: Ctx, sheet: str, row: list, chat_id: int, label: str) -> bool:
    """Jadvalga yozadi. Google javob bermasa — navbatga qo'yadi (ma'lumot yo'qolmaydi).

    True — darhol yozildi, False — navbatga qo'yildi.
    """
    try:
        ctx.db.append(sheet, row)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("'%s' varag'iga yozilmadi (%s), navbatga qo'yildi", sheet, e)
    ctx.queue.add({"sheet": sheet, "row": row, "chat_id": chat_id, "label": label})
    return False
