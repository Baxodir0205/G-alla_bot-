"""Handlerlarni ro'yxatdan o'tkazish.

Tartib muhim: buyruqlar va menyu tugmalari birinchi tekshiriladi, shuning uchun
foydalanuvchi suhbat o'rtasida /hosil yoki /bekor yozsa, u "dala raqami" bo'lib
saqlanib qolmaydi — joriy amal to'xtab, yangi buyruq bajariladi.
"""
import logging

from telebot.types import Message, MessageOriginChannel

from .. import keyboards as kb
from .. import states as S
from .. import texts as T
from ..context import Ctx
from ..utils import esc
from . import admin, harvest, registration, report
from .common import active_user, safe, show_menu

log = logging.getLogger(__name__)

ALL_CONTENT = ["text", "photo", "contact", "document", "video", "voice", "audio",
               "sticker", "animation", "video_note", "location", "venue", "poll", "dice"]

STEPS = {
    S.REG_NAME: registration.on_name,
    S.REG_PHONE: registration.on_phone,
    S.REP_FIELD: report.on_field,
    S.REP_ACTIVITY: report.on_activity,
    S.REP_ACTIVITY_OTHER: report.on_activity_other,
    S.REP_AMOUNT: report.on_amount,
    S.REP_UNIT: report.on_unit,
    S.REP_COST: report.on_cost,
    S.REP_PHOTO: report.on_photo,
    S.REP_NOTE: report.on_note,
    S.REP_CONFIRM: report.on_confirm_text,
    S.REP_SENDING: report.on_sending,
    S.H_FIELD: harvest.on_field,
    S.H_SPIKES: harvest.on_spikes,
    S.H_GRAINS: harvest.on_grains,
    S.H_TKW: harvest.on_tkw,
    S.H_LOSS: harvest.on_loss,
}


def _private(m: Message) -> bool:
    return m.chat.type == "private"


def _button(*labels):
    return lambda m: _private(m) and m.content_type == "text" and (m.text or "").strip() in labels


# ---------- buyruqlar ----------
def cmd_start(ctx: Ctx, m: Message) -> None:
    uid = m.from_user.id
    ctx.store.clear(uid)
    if ctx.db.get_user(uid, fresh=True) is None:
        registration.begin(ctx, m)
        return
    user = active_user(ctx, m)
    if user:
        show_menu(ctx, uid, T.WELCOME.format(name=esc(user.name)))


def cmd_cancel(ctx: Ctx, m: Message) -> None:
    uid = m.from_user.id
    text = T.CANCELLED if ctx.store.clear(uid) else T.NOTHING_TO_CANCEL
    if active_user(ctx, m, notify=False):
        show_menu(ctx, uid, text)
    else:
        ctx.send(uid, text + "\n/start", kb.remove())


def cmd_help(ctx: Ctx, m: Message) -> None:
    if active_user(ctx, m, notify=False):
        show_menu(ctx, m.chat.id, T.HELP)
    else:
        ctx.send(m.chat.id, T.HELP)


def cmd_id(ctx: Ctx, m: Message) -> None:
    ctx.send(m.chat.id, T.YOUR_ID.format(id=m.from_user.id))


def start_report(ctx: Ctx, m: Message) -> None:
    ctx.store.clear(m.from_user.id)
    user = active_user(ctx, m)
    if user:
        report.begin(ctx, m, user)


def start_harvest(ctx: Ctx, m: Message) -> None:
    ctx.store.clear(m.from_user.id)
    user = active_user(ctx, m)
    if user:
        harvest.begin(ctx, m, user)


def route(ctx: Ctx, m: Message) -> None:
    """Boshqa barcha xabarlar: foydalanuvchi qaysi bosqichda bo'lsa, o'sha handlerga."""
    uid = m.from_user.id
    origin = getattr(m, "forward_origin", None)
    if ctx.is_admin(uid) and isinstance(origin, MessageOriginChannel):
        # Admin kanal postini forward qilsa — .env uchun kanal ID sini aytamiz
        ctx.send(uid, T.CHANNEL_ID_INFO.format(id=origin.chat.id, title=esc(origin.chat.title or "")))
        return
    if m.content_type == "text" and (m.text or "").startswith("/"):
        ctx.send(uid, T.UNKNOWN_COMMAND)
        return
    state, _ = ctx.store.get(uid)
    handler = STEPS.get(state)
    if handler:
        handler(ctx, m)
        return
    if state:  # eski versiyadan qolgan noma'lum holat
        ctx.store.clear(uid)
    if active_user(ctx, m):
        show_menu(ctx, uid)


def register_all(ctx: Ctx) -> None:
    bot = ctx.bot

    def on(handler, **filters):
        def run(m, _h=handler):
            _h(ctx, m)
        run.__name__ = handler.__name__  # logda handler nomi ko'rinishi uchun
        bot.register_message_handler(safe(ctx)(run), **filters)

    on(cmd_start, commands=["start"], func=_private)
    on(cmd_cancel, commands=["bekor", "cancel"], func=_private)
    on(cmd_cancel, func=_button(T.BTN_CANCEL))
    on(cmd_help, commands=["yordam", "help"], func=_private)
    on(cmd_help, func=_button(T.BTN_HELP))
    on(cmd_id, commands=["id"], func=_private)
    on(start_report, commands=["hisobot"], func=_private)
    on(start_report, func=_button(T.BTN_REPORT))
    on(start_harvest, commands=["hosil"], func=_private)
    on(start_harvest, func=_button(T.BTN_HARVEST))
    on(route, func=_private, content_types=ALL_CONTENT)

    bot.register_callback_query_handler(
        safe(ctx)(lambda c: report.on_callback(ctx, c)),
        func=lambda c: (c.data or "").startswith("rep:"))
    bot.register_callback_query_handler(
        safe(ctx)(lambda c: admin.on_callback(ctx, c)),
        func=lambda c: (c.data or "").startswith("adm:"))
    bot.register_callback_query_handler(
        lambda c: bot.answer_callback_query(c.id), func=lambda c: True)
