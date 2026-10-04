"""Dala hisoboti: dala → tadbir → miqdor/birlik → summa → rasm → izoh → tasdiqlash → yuborish."""
import logging
import secrets
from typing import List

from telebot.apihelper import ApiTelegramException
from telebot.types import CallbackQuery, InputMediaPhoto, Message

from .. import keyboards as kb
from .. import states as S
from .. import texts as T
from ..context import Ctx
from ..sheets import ACTIVE, REPORTS, User
from ..utils import as_text, clean_text, esc, fmt_num, parse_number
from .common import match_option, need_text, save_row, show_menu

log = logging.getLogger(__name__)

MAX_PHOTOS = 10
MAX_NOTE = 1000
MAX_AMOUNT = 10_000_000
MAX_COST = 1_000_000_000_000


# ---------- bosqichlar ----------
def begin(ctx: Ctx, m: Message, user: User) -> None:
    ctx.store.start(user.id, S.REP_FIELD, staff=user.name)
    ask_field(ctx, user.id)


def ask_field(ctx: Ctx, uid: int) -> None:
    fields = ctx.db.get_fields()
    if fields:
        ctx.send(uid, T.ASK_FIELD, kb.choices([f.name for f in fields]))
    else:
        ctx.send(uid, T.ASK_FIELD_FREE, kb.cancel_only())


def on_field(ctx: Ctx, m: Message) -> None:
    text = need_text(ctx, m)
    if text is None:
        return
    uid = m.from_user.id
    fields = ctx.db.get_fields()
    if fields:
        name = match_option(text, [f.name for f in fields])
        if not name:  # erkin matn qabul qilinmaydi — jadvalda bir xil nomlar bo'lishi uchun
            ctx.send(uid, T.PICK_FROM_LIST, kb.choices([f.name for f in fields]))
            return
    else:
        name = clean_text(text, 50)
    ctx.store.set_state(uid, S.REP_ACTIVITY, field=name)
    ask_activity(ctx, uid)


def ask_activity(ctx: Ctx, uid: int) -> None:
    ctx.send(uid, T.ASK_ACTIVITY, kb.choices(ctx.db.get_activities(), extra=[T.BTN_OTHER]))


def on_activity(ctx: Ctx, m: Message) -> None:
    text = need_text(ctx, m)
    if text is None:
        return
    uid = m.from_user.id
    if match_option(text, [T.BTN_OTHER]):
        ctx.store.set_state(uid, S.REP_ACTIVITY_OTHER)
        ctx.send(uid, T.ASK_ACTIVITY_OTHER, kb.cancel_only())
        return
    name = match_option(text, ctx.db.get_activities())
    if not name:
        ctx.send(uid, T.PICK_FROM_LIST, kb.choices(ctx.db.get_activities(), extra=[T.BTN_OTHER]))
        return
    _set_activity(ctx, uid, name)


def on_activity_other(ctx: Ctx, m: Message) -> None:
    text = need_text(ctx, m)
    if text is None:
        return
    name = clean_text(text, 60)
    if len(name) < 2:
        ctx.send(m.chat.id, T.ASK_ACTIVITY_OTHER)
        return
    _set_activity(ctx, m.from_user.id, name)


def _set_activity(ctx: Ctx, uid: int, name: str) -> None:
    ctx.store.set_state(uid, S.REP_AMOUNT, activity=name)
    ctx.send(uid, T.ASK_AMOUNT, kb.skip_cancel())


def on_amount(ctx: Ctx, m: Message) -> None:
    text = need_text(ctx, m)
    if text is None:
        return
    uid = m.from_user.id
    if text == T.BTN_SKIP:
        ctx.store.set_state(uid, S.REP_COST, amount=None, unit="")
        ctx.send(uid, T.ASK_COST, kb.skip_cancel())
        return
    n = parse_number(text)
    if n is None or n <= 0 or n > MAX_AMOUNT:
        ctx.send(uid, T.BAD_AMOUNT)
        return
    ctx.store.set_state(uid, S.REP_UNIT, amount=n)
    ctx.send(uid, T.ASK_UNIT, kb.choices(T.UNITS, width=3))


def on_unit(ctx: Ctx, m: Message) -> None:
    text = need_text(ctx, m)
    if text is None:
        return
    uid = m.from_user.id
    unit = match_option(text, T.UNITS)
    if not unit:
        ctx.send(uid, T.PICK_FROM_LIST, kb.choices(T.UNITS, width=3))
        return
    ctx.store.set_state(uid, S.REP_COST, unit=unit)
    ctx.send(uid, T.ASK_COST, kb.skip_cancel())


def on_cost(ctx: Ctx, m: Message) -> None:
    text = need_text(ctx, m)
    if text is None:
        return
    uid = m.from_user.id
    if text == T.BTN_SKIP:
        cost = None
    else:
        cost = parse_number(text, money=True)
        if cost is None or cost > MAX_COST:
            ctx.send(uid, T.BAD_COST)
            return
    ctx.store.set_state(uid, S.REP_PHOTO, cost=cost, photos=[], album=None)
    ctx.send(uid, T.ASK_PHOTO, kb.photo_step(False))


def on_photo(ctx: Ctx, m: Message) -> None:
    uid = m.from_user.id
    if m.content_type == "photo":
        n = ctx.store.append(uid, "photos", m.photo[-1].file_id, MAX_PHOTOS)
        if n is None:
            ctx.send(uid, T.PHOTO_LIMIT, kb.photo_step(True))
        elif m.media_group_id:
            # Albomdagi har bir rasmga alohida javob yozib chatni to'ldirmaymiz
            if ctx.store.swap(uid, "album", m.media_group_id):
                ctx.send(uid, T.PHOTOS_ADDED_ALBUM, kb.photo_step(True))
        else:
            ctx.send(uid, T.PHOTO_ADDED.format(n=n), kb.photo_step(True))
        return
    if m.content_type == "document" and (m.document.mime_type or "").startswith("image/"):
        ctx.send(uid, T.PHOTO_AS_PHOTO)
        return
    if m.content_type == "text" and m.text.strip() in (T.BTN_CONTINUE, T.BTN_NO_PHOTO, T.BTN_SKIP):
        ctx.store.set_state(uid, S.REP_NOTE)
        ctx.send(uid, T.ASK_NOTE, kb.skip_cancel())
        return
    _, d = ctx.store.get(uid)
    ctx.send(uid, T.PHOTO_EXPECTED, kb.photo_step(bool(d.get("photos"))))


def on_note(ctx: Ctx, m: Message) -> None:
    text = need_text(ctx, m)
    if text is None:
        return
    uid = m.from_user.id
    if text == T.BTN_SKIP:
        note = ""
    elif len(text) > MAX_NOTE:
        ctx.send(uid, T.NOTE_TOO_LONG)
        return
    else:
        note = text
    ctx.store.set_state(uid, S.REP_CONFIRM, note=note)
    show_confirm(ctx, uid)


# ---------- tasdiqlash ----------
def _values(d: dict) -> dict:
    photos = d.get("photos") or []
    amount = f"{fmt_num(d['amount'], 2)} {d.get('unit', '')}".strip() if d.get("amount") is not None else "—"
    cost = f"{fmt_num(d['cost'])} so'm" if d.get("cost") is not None else "—"
    return {
        "staff": esc(d.get("staff", "")),
        "field": esc(d.get("field", "")),
        "activity": esc(d.get("activity", "")),
        "amount": esc(amount),
        "cost": cost,
        "photos": f"{len(photos)} ta" if photos else "yo'q",
        "note": esc(d.get("note") or "—"),
    }


def show_confirm(ctx: Ctx, uid: int) -> None:
    _, d = ctx.store.get(uid)
    ctx.send(uid, T.CHECK_REPORT, kb.cancel_only())
    msg = ctx.send(uid, T.REPORT_SUMMARY.format(**_values(d)), kb.confirm_report())
    ctx.store.update(uid, summary_mid=msg.message_id)


def on_confirm_text(ctx: Ctx, m: Message) -> None:
    ctx.send(m.chat.id, T.CONFIRM_USE_BUTTONS)


def on_sending(ctx: Ctx, m: Message) -> None:
    ctx.send(m.chat.id, T.SENDING_WAIT)


def on_callback(ctx: Ctx, c: CallbackQuery) -> None:
    uid = c.from_user.id
    action = c.data.split(":", 1)[1]
    state, d = ctx.store.get(uid)

    def drop_buttons():
        try:
            ctx.bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
        except ApiTelegramException:
            pass

    # Eski hisobot xabaridagi tugmalar bosilsa, joriy hisobotga ta'sir qilmasin
    stale = d.get("summary_mid") != c.message.message_id
    if action == "send":
        if stale or not ctx.store.transition(uid, S.REP_CONFIRM, S.REP_SENDING):
            ctx.bot.answer_callback_query(c.id, T.ALREADY_HANDLED)
            drop_buttons()
            return
        ctx.bot.answer_callback_query(c.id, "⏳")
        drop_buttons()
        submit(ctx, uid)
        return

    if stale or state != S.REP_CONFIRM:
        ctx.bot.answer_callback_query(c.id, T.ALREADY_HANDLED)
        drop_buttons()
        return
    ctx.bot.answer_callback_query(c.id)
    drop_buttons()
    if action == "restart":
        ctx.store.start(uid, S.REP_FIELD, staff=d.get("staff", ""))
        ask_field(ctx, uid)
    else:
        ctx.store.clear(uid)
        show_menu(ctx, uid, T.CANCELLED)


# ---------- yuborish ----------
def _message_link(target: str, message_id: int) -> str:
    if target.startswith("@"):
        return f"https://t.me/{target[1:]}/{message_id}"
    if target.startswith("-100"):
        return f"https://t.me/c/{target[4:]}/{message_id}"
    return ""


def _post(ctx: Ctx, target, caption: str, photos: List[str]):
    if not photos:
        return ctx.bot.send_message(target, caption)
    if len(photos) == 1:
        return ctx.bot.send_photo(target, photos[0], caption=caption)
    media = [InputMediaPhoto(fid, caption=caption if i == 0 else None,
                             parse_mode="HTML" if i == 0 else None)
             for i, fid in enumerate(photos)]
    return ctx.bot.send_media_group(target, media)[0]


def publish(ctx: Ctx, d: dict, rid: str, date_s: str, time_s: str) -> str:
    """Hisobotni kanalga joylaydi va post havolasini qaytaradi.

    Kanal sozlanmagan bo'lsa, rasmli hisobotlar adminlarga yuboriladi
    (rasmlar hech qachon yo'qolib ketmasligi uchun).
    """
    v = _values(d)
    note = d.get("note") or ""
    if len(note) > 600:  # rasm izohi 1024 belgidan oshmasligi kerak
        note = note[:600] + "…"
    caption = T.CHANNEL_POST.format(rid=rid, date=date_s, time=time_s, staff=v["staff"],
                                    field=v["field"], activity=v["activity"], amount=v["amount"],
                                    cost=v["cost"], note=esc(note) or "—")
    photos = d.get("photos") or []
    channel = ctx.cfg.channel_id
    targets = [channel] if channel else (list(ctx.cfg.admin_ids) if photos else [])
    link = ""
    for target in targets:
        try:
            msg = _post(ctx, target, caption, photos)
        except ApiTelegramException as e:
            log.error("Hisobot #%s %s ga joylanmadi: %s", rid, target, e)
            continue
        if channel and target == channel:
            link = _message_link(channel, msg.message_id)
    return link


def submit(ctx: Ctx, uid: int) -> None:
    _, d = ctx.store.get(uid)
    try:
        user = ctx.db.get_user(uid)
        if not ctx.is_admin(uid) and (user is None or user.status != ACTIVE):
            ctx.store.clear(uid)
            ctx.send(uid, T.BLOCKED_DURING_FLOW, kb.remove())
            return

        # ID, sana va post havolasi birinchi urinishda saqlanadi — qayta urinishda takrorlanmaydi
        now = ctx.now()
        rid = d.get("rid") or f"{now:%y%m%d}-{secrets.token_hex(2).upper()}"
        date_s = d.get("date") or now.strftime("%Y-%m-%d")
        time_s = d.get("time") or now.strftime("%H:%M")
        ctx.store.update(uid, rid=rid, date=date_s, time=time_s)

        photos = d.get("photos") or []
        link = d.get("post_link")
        if link is None:
            link = publish(ctx, d, rid, date_s, time_s)
            ctx.store.update(uid, post_link=link)
        if link:
            photo_cell = link
        elif photos:
            where = "kanalga joylanmadi" if ctx.cfg.channel_id else "adminlarga yuborilgan"
            photo_cell = as_text(f"{len(photos)} ta rasm ({where})")
        else:
            photo_cell = ""

        row = [
            as_text(rid), date_s, time_s, as_text(d.get("staff", "")), as_text(uid),
            as_text(d.get("field", "")), as_text(d.get("activity", "")),
            d["amount"] if d.get("amount") is not None else "",
            as_text(d.get("unit") or ""),
            d["cost"] if d.get("cost") is not None else "",
            photo_cell, as_text(d.get("note") or ""),
        ]
        saved = save_row(ctx, REPORTS, row, uid, f"Hisobot #{rid}")
    except Exception:  # noqa: BLE001 — ma'lumot saqlanib qoladi, foydalanuvchi qayta bosadi
        log.exception("Hisobotni yuborishda xato (foydalanuvchi %s)", uid)
        ctx.store.transition(uid, S.REP_SENDING, S.REP_CONFIRM)
        ctx.send(uid, T.SEND_FAILED)
        show_confirm(ctx, uid)
        return

    ctx.store.clear(uid)
    log.info("Hisobot #%s qabul qilindi (xodim %s, jadvalga yozildi=%s)", rid, uid, saved)
    show_menu(ctx, uid, (T.REPORT_SAVED if saved else T.REPORT_QUEUED).format(rid=rid))
