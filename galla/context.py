"""Barcha handlerlar uchun umumiy bog'liqliklar."""
from dataclasses import dataclass
from datetime import datetime

from telebot import TeleBot

from .config import Config
from .sheets import SheetsDB
from .storage import PendingQueue, SessionStore


@dataclass
class Ctx:
    bot: TeleBot
    cfg: Config
    db: SheetsDB
    store: SessionStore
    queue: PendingQueue

    def now(self) -> datetime:
        """Joriy vaqt sozlangan vaqt zonasida (server UTC bo'lsa ham to'g'ri)."""
        return datetime.now(self.cfg.tz)

    def is_admin(self, uid: int) -> bool:
        return uid in self.cfg.admin_ids

    def send(self, chat_id: int, text: str, kb=None):
        return self.bot.send_message(chat_id, text, reply_markup=kb)
