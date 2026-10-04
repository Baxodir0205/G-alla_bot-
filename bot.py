"""Botni ishga tushirish: python bot.py"""
import logging
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

import telebot
from telebot import ExceptionHandler, TeleBot
from telebot.apihelper import ApiTelegramException
from telebot.types import BotCommand

from galla import texts as T
from galla.config import Config, ConfigError, load_config
from galla.context import Ctx
from galla.handlers import register_all
from galla.sheets import SheetsDB, SheetsError
from galla.storage import PendingQueue, SessionStore
from galla.utils import esc

log = logging.getLogger("galla")

QUEUE_FLUSH_INTERVAL = 60  # soniya

COMMANDS = [
    BotCommand("start", "Asosiy menyu"),
    BotCommand("hisobot", "Dala hisobotini topshirish"),
    BotCommand("hosil", "Hosildorlikni hisoblash"),
    BotCommand("bekor", "Joriy amalni bekor qilish"),
    BotCommand("yordam", "Yordam"),
    BotCommand("id", "Telegram ID raqamim"),
]


def setup_logging(cfg: Config) -> None:
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(cfg.log_dir / "bot.log", maxBytes=1_000_000,
                                       backupCount=5, encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console)
    telebot.logger.setLevel(logging.WARNING)


class LogExceptions(ExceptionHandler):
    def handle(self, exception):
        log.error("Telegram polling xatosi: %s", exception, exc_info=exception)
        return True


def check_channel(bot: TeleBot, cfg: Config, bot_id: int) -> None:
    if not cfg.channel_id:
        log.warning("CHANNEL_ID sozlanmagan: rasmli hisobotlar adminlarga yuboriladi.")
        return
    try:
        member = bot.get_chat_member(cfg.channel_id, bot_id)
        if member.status not in ("administrator", "creator"):
            log.error("Bot %s kanalida admin emas — hisobotlar joylanmaydi. Botni kanalga admin qiling.",
                      cfg.channel_id)
    except ApiTelegramException as e:
        log.error("Kanal %s ga kirib bo'lmadi (%s). Botni kanalga admin qilib qo'shing.", cfg.channel_id, e)
    except Exception as e:  # noqa: BLE001 — bu faqat tekshiruv, bot ishlashiga to'sqinlik qilmasin
        log.warning("Kanalni tekshirib bo'lmadi: %s", e)


def queue_worker(ctx: Ctx, stop: threading.Event) -> None:
    def send(item):
        ctx.db.append(item["sheet"], item["row"])

    def notify(item):
        if item.get("chat_id"):
            try:
                ctx.send(item["chat_id"], T.QUEUE_FLUSHED.format(label=esc(item.get("label", "Ma'lumot"))))
            except ApiTelegramException as e:
                log.warning("Navbat xabarnomasi yetmadi: %s", e)

    while not stop.is_set():
        if len(ctx.queue):
            ctx.queue.flush(send, notify)
        stop.wait(QUEUE_FLUSH_INTERVAL)


def connect_sheets(cfg: Config) -> SheetsDB:
    db = SheetsDB(cfg.credentials_file, cfg.spreadsheet_id)
    for attempt in range(1, 6):
        try:
            db.connect()
            db.setup()
            return db
        except SheetsError:
            raise  # sozlash xatosi — qayta urinishdan foyda yo'q
        except Exception as e:  # noqa: BLE001 — tarmoq xatosi
            log.warning("Google Sheets'ga ulanib bo'lmadi (%s), urinish %d/5", e, attempt)
            time.sleep(5 * attempt)
    raise SheetsError("Google Sheets'ga ulanib bo'lmadi. Internet aloqasini tekshiring.")


def main() -> None:
    try:
        cfg = load_config()
    except ConfigError as e:
        print("❌ .env sozlamalarida xato:\n" + str(e), file=sys.stderr)
        sys.exit(1)

    setup_logging(cfg)
    log.info("Bot ishga tushmoqda...")

    try:
        db = connect_sheets(cfg)
    except SheetsError as e:
        log.error("❌ %s", e)
        sys.exit(1)
    log.info("Google Sheets ulandi")

    bot = TeleBot(cfg.bot_token, parse_mode="HTML", num_threads=4,
                  exception_handler=LogExceptions())
    try:
        me = bot.get_me()
    except ApiTelegramException as e:
        log.error("❌ BOT_TOKEN noto'g'ri yoki bot o'chirilgan: %s", e)
        sys.exit(1)

    ctx = Ctx(bot=bot, cfg=cfg, db=db,
              store=SessionStore(cfg.data_dir / "sessions.json"),
              queue=PendingQueue(cfg.data_dir / "pending.json"))
    register_all(ctx)

    try:
        bot.set_my_commands(COMMANDS)
    except ApiTelegramException as e:
        log.warning("Buyruqlar menyusini o'rnatib bo'lmadi: %s", e)
    check_channel(bot, cfg, me.id)

    stop = threading.Event()
    threading.Thread(target=queue_worker, args=(ctx, stop), daemon=True, name="queue").start()

    log.info("✅ @%s ishga tushdi. Adminlar: %s", me.username, ", ".join(map(str, cfg.admin_ids)))
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=20,
                             allowed_updates=["message", "callback_query"],
                             logger_level=logging.WARNING)
    finally:
        stop.set()
        log.info("Bot to'xtatildi")


if __name__ == "__main__":
    main()
