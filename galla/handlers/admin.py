"""Admin: yangi xodimlarni tasdiqlash yoki rad etish."""
import logging

from telebot.apihelper import ApiTelegramException
from telebot.types import CallbackQuery

from .. import keyboards as kb
from .. import texts as T
from ..context import Ctx
from ..sheets import ACTIVE, PENDING, REJECTED
from ..utils import esc

log = logging.getLogger(__name__)


def notify_admins(ctx: Ctx, text: str, markup=None) -> None:
    for aid in ctx.cfg.admin_ids:
        try:
            ctx.send(aid, text, markup)
        except ApiTelegramException as e:
            log.warning("Admin %s ga xabar yetmadi: %s (admin botga /start bosmagan bo'lishi mumkin)", aid, e)


def on_callback(ctx: Ctx, c: CallbackQuery) -> None:
    if not ctx.is_admin(c.from_user.id):
        ctx.bot.answer_callback_query(c.id, T.ADMIN_ONLY, show_alert=True)
        return
    try:
        _, action, tid = c.data.split(":")
        tid = int(tid)
    except ValueError:
        ctx.bot.answer_callback_query(c.id)
        return

    user = ctx.db.get_user(tid, fresh=True)
    if not user:
        ctx.bot.answer_callback_query(c.id, T.USER_NOT_FOUND, show_alert=True)
        return
    if user.status != PENDING:
        ctx.bot.answer_callback_query(c.id, T.ADMIN_ALREADY.format(status=user.status), show_alert=True)
        try:
            ctx.bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
        except ApiTelegramException:
            pass
        return

    new_status = ACTIVE if action == "ok" else REJECTED
    ctx.db.set_user_status(tid, new_status)
    log.info("Admin %s: xodim %s holati -> %s", c.from_user.id, tid, new_status)

    admin_name = esc(c.from_user.first_name or c.from_user.id)
    suffix = (T.ADMIN_APPROVED if new_status == ACTIVE else T.ADMIN_REJECTED).format(admin=admin_name)
    # 48 soatdan eski xabarlar Telegram'da "InaccessibleMessage" bo'lib keladi — matni yo'q
    original = getattr(c.message, "html_text", None)
    edited = False
    if original:
        try:
            ctx.bot.edit_message_text(original + suffix, c.message.chat.id, c.message.message_id)
            edited = True
        except ApiTelegramException as e:
            log.warning("Admin xabarini tahrirlab bo'lmadi: %s", e)
    if not edited:
        try:
            ctx.bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
        except ApiTelegramException:
            pass
        ctx.send(c.from_user.id, f"👤 {esc(user.name)} (<code>{tid}</code>){suffix}")
    ctx.bot.answer_callback_query(c.id, "Bajarildi ✅")

    try:
        if new_status == ACTIVE:
            ctx.send(tid, T.USER_APPROVED, kb.main_menu())
        else:
            ctx.send(tid, T.USER_REJECTED, kb.remove())
    except ApiTelegramException as e:
        log.warning("Xodim %s ga javob yetmadi: %s", tid, e)
