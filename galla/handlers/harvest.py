"""Hosildorlik prognozi: dala → boshoq/m² → don/boshoq → 1000 don vazni → yo'qotish %."""
from typing import Optional

from telebot.types import Message

from .. import keyboards as kb
from .. import states as S
from .. import texts as T
from ..context import Ctx
from ..sheets import HARVEST, User
from ..utils import as_text, calc_yield, esc, fmt_num, parse_number
from .common import match_option, need_text, save_row, show_menu

# Ruxsat etilgan oraliqlar (xato kiritishdan himoya)
RANGES = {
    "spikes": (50, 2000),   # boshoq / m²
    "grains": (1, 150),     # don / boshoq
    "tkw": (10, 80),        # 1000 don vazni, g
    "loss": (0, 50),        # yo'qotish, %
}


def begin(ctx: Ctx, m: Message, user: User) -> None:
    fields = ctx.db.get_fields()
    if fields:
        ctx.store.start(user.id, S.H_FIELD, staff=user.name)
        ctx.send(user.id, T.ASK_H_FIELD, kb.choices([f.name for f in fields], extra=[T.BTN_NO_FIELD]))
    else:
        ctx.store.start(user.id, S.H_SPIKES, staff=user.name, field="", area=None)
        ctx.send(user.id, T.ASK_SPIKES, kb.cancel_only())


def on_field(ctx: Ctx, m: Message) -> None:
    text = need_text(ctx, m)
    if text is None:
        return
    uid = m.from_user.id
    fields = ctx.db.get_fields()
    if text == T.BTN_NO_FIELD:
        field, area = "", None
    else:
        name = match_option(text, [f.name for f in fields])
        if not name:
            ctx.send(uid, T.PICK_FROM_LIST,
                     kb.choices([f.name for f in fields], extra=[T.BTN_NO_FIELD]))
            return
        field = name
        area = next(f.area_ha for f in fields if f.name == name)
    ctx.store.set_state(uid, S.H_SPIKES, field=field, area=area)
    ctx.send(uid, T.ASK_SPIKES, kb.cancel_only())


def _number(ctx: Ctx, m: Message, key: str) -> Optional[float]:
    text = need_text(ctx, m)
    if text is None:
        return None
    lo, hi = RANGES[key]
    n = parse_number(text)
    if n is None or not lo <= n <= hi:
        ctx.send(m.chat.id, T.BAD_RANGE.format(lo=fmt_num(lo), hi=fmt_num(hi)))
        return None
    return n


def on_spikes(ctx: Ctx, m: Message) -> None:
    n = _number(ctx, m, "spikes")
    if n is not None:
        ctx.store.set_state(m.from_user.id, S.H_GRAINS, spikes=n)
        ctx.send(m.chat.id, T.ASK_GRAINS)


def on_grains(ctx: Ctx, m: Message) -> None:
    n = _number(ctx, m, "grains")
    if n is not None:
        ctx.store.set_state(m.from_user.id, S.H_TKW, grains=n)
        ctx.send(m.chat.id, T.ASK_TKW)


def on_tkw(ctx: Ctx, m: Message) -> None:
    n = _number(ctx, m, "tkw")
    if n is not None:
        ctx.store.set_state(m.from_user.id, S.H_LOSS, tkw=n)
        ctx.send(m.chat.id, T.ASK_LOSS, kb.skip_cancel())


def on_loss(ctx: Ctx, m: Message) -> None:
    if m.content_type == "text" and (m.text or "").strip() == T.BTN_SKIP:
        loss = 0.0
    else:
        loss = _number(ctx, m, "loss")
        if loss is None:
            return
    finish(ctx, m.from_user.id, loss)


def result_text(d: dict, loss: float, res: dict) -> str:
    field, area = d.get("field") or "", d.get("area")
    field_line = T.HARVEST_FIELD_LINE.format(
        field=esc(field), area=f" ({fmt_num(area, 2)} ga)" if area else "") if field else ""
    return T.HARVEST_RESULT.format(
        field_line=field_line,
        spikes=fmt_num(d["spikes"]), grains=fmt_num(d["grains"]), tkw=fmt_num(d["tkw"]),
        loss_line=T.HARVEST_LOSS_LINE.format(loss=fmt_num(loss)) if loss else "",
        bio_c=fmt_num(res["bio_c"]), bio_t=fmt_num(res["bio_t"], 2),
        exp_line=(T.HARVEST_EXP_LINE.format(exp_c=fmt_num(res["exp_c"]), exp_t=fmt_num(res["exp_t"], 2))
                  if loss else T.HARVEST_NO_LOSS_NOTE),
        total_line=T.HARVEST_TOTAL_LINE.format(total=fmt_num(res["total_t"])) if res["total_t"] else "",
    )


def finish(ctx: Ctx, uid: int, loss: float) -> None:
    _, d = ctx.store.get(uid)
    res = calc_yield(d["spikes"], d["grains"], d["tkw"], loss, d.get("area"))
    now = ctx.now()
    row = [
        now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), as_text(d.get("staff", "")), as_text(uid),
        as_text(d.get("field") or ""), d["spikes"], d["grains"], d["tkw"], loss,
        round(res["bio_c"], 2), round(res["exp_c"], 2), round(res["exp_t"], 3),
        d.get("area") or "", round(res["total_t"], 3) if res["total_t"] else "",
    ]
    saved = save_row(ctx, HARVEST, row, uid, "Hosil prognozi")
    ctx.store.clear(uid)
    show_menu(ctx, uid, result_text(d, loss, res) + "\n" + (T.HARVEST_SAVED if saved else T.HARVEST_QUEUED))
