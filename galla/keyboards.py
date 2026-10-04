"""Klaviatura tugmalari."""
from typing import Iterable, List, Optional

from telebot.types import (InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardMarkup, ReplyKeyboardRemove)

from . import texts as T


def _reply(rows: List[List[str]]) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for row in rows:
        kb.row(*[KeyboardButton(t) for t in row])
    return kb


def main_menu() -> ReplyKeyboardMarkup:
    return _reply([[T.BTN_REPORT], [T.BTN_HARVEST], [T.BTN_HELP]])


def remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def cancel_only() -> ReplyKeyboardMarkup:
    return _reply([[T.BTN_CANCEL]])


def skip_cancel() -> ReplyKeyboardMarkup:
    return _reply([[T.BTN_SKIP], [T.BTN_CANCEL]])


def choices(options: Iterable[str], width: int = 2,
            extra: Optional[List[str]] = None) -> ReplyKeyboardMarkup:
    opts = list(options)
    rows = [opts[i:i + width] for i in range(0, len(opts), width)]
    if extra:
        rows.append(extra)
    rows.append([T.BTN_CANCEL])
    return _reply(rows)


def contact_request() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton(T.BTN_PHONE, request_contact=True))
    kb.row(KeyboardButton(T.BTN_CANCEL))
    return kb


def photo_step(has_photos: bool) -> ReplyKeyboardMarkup:
    return _reply([[T.BTN_CONTINUE if has_photos else T.BTN_NO_PHOTO], [T.BTN_CANCEL]])


def confirm_report() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton(T.BTN_SEND, callback_data="rep:send"))
    kb.row(InlineKeyboardButton(T.BTN_RESTART, callback_data="rep:restart"),
           InlineKeyboardButton(T.BTN_CANCEL, callback_data="rep:cancel"))
    return kb


def approve_user(tid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm:ok:{tid}"),
           InlineKeyboardButton("❌ Rad etish", callback_data=f"adm:no:{tid}"))
    return kb
