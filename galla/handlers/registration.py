"""Bir martalik ro'yxatdan o'tish: ism → telefon → admin tasdig'i."""
import logging
import re
from typing import Optional

from telebot.types import Message

from .. import keyboards as kb
from .. import states as S
from .. import texts as T
from ..context import Ctx
from ..sheets import ACTIVE, PENDING
from ..utils import clean_text, esc
from .admin import notify_admins
from .common import active_user, need_text, show_menu

log = logging.getLogger(__name__)


def begin(ctx: Ctx, m: Message) -> None:
    ctx.store.start(m.from_user.id, S.REG_NAME)
    ctx.send(m.chat.id, T.REG_WELCOME, kb.cancel_only())


def on_name(ctx: Ctx, m: Message) -> None:
    text = need_text(ctx, m)
    if text is None:
        return
    name = clean_text(text, 100)
    letters = len(re.findall(r"[^\W\d_]", name))
    if not 3 <= len(name) <= 60 or letters < 3 or re.search(r"[\d@/<>#]", name):
        ctx.send(m.chat.id, T.BAD_NAME)
        return
    ctx.store.set_state(m.from_user.id, S.REG_PHONE, name=name)
    ctx.send(m.chat.id, T.ASK_PHONE, kb.contact_request())


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:  # 901234567 -> +998901234567
        digits = "998" + digits
    if not 10 <= len(digits) <= 15:
        return None
    return "+" + digits


def on_phone(ctx: Ctx, m: Message) -> None:
    uid = m.from_user.id
    if m.content_type == "contact":
        if m.contact.user_id and m.contact.user_id != uid:
            ctx.send(uid, T.PHONE_NOT_OWN)
            return
        phone = normalize_phone(m.contact.phone_number)
    elif m.content_type == "text":
        phone = normalize_phone(m.text)
    else:
        ctx.send(uid, T.ASK_PHONE)
        return
    if not phone:
        ctx.send(uid, T.BAD_PHONE)
        return
    finish(ctx, m, phone)


def finish(ctx: Ctx, m: Message, phone: str) -> None:
    uid = m.from_user.id
    _, data = ctx.store.get(uid)
    name = data.get("name")
    if not name:
        begin(ctx, m)
        return

    if ctx.db.get_user(uid, fresh=True):  # ikki marta yuborilgan bo'lsa, takror qator yozmaymiz
        ctx.store.clear(uid)
        if active_user(ctx, m):
            show_menu(ctx, uid)
        return

    is_admin = ctx.is_admin(uid)
    username = f"@{m.from_user.username}" if m.from_user.username else ""
    ctx.db.add_user(uid, name, phone, username, ACTIVE if is_admin else PENDING,
                    ctx.now().strftime("%Y-%m-%d %H:%M"))
    ctx.store.clear(uid)
    log.info("Yangi xodim: %s (%s), admin=%s", name, uid, is_admin)

    if is_admin:
        show_menu(ctx, uid, T.WELCOME.format(name=esc(name)))
        return
    ctx.send(uid, T.REG_PENDING, kb.remove())
    notify_admins(
        ctx,
        T.ADMIN_NEW_USER.format(name=esc(name), phone=esc(phone),
                                username=esc(username or "—"), id=uid),
        kb.approve_user(uid),
    )
