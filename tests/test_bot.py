"""Botning barcha asosiy oqimlarini oflayn sinash: python -m pytest -q"""
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from telebot import TeleBot

from galla import sheets as SH
from galla import states as S
from galla import texts as T
from galla.config import Config, ConfigError, load_config
from galla.context import Ctx
from galla.handlers import register_all
from galla.sheets import SheetsDB
from galla.storage import PendingQueue, SessionStore
from galla.utils import as_text, calc_yield, fmt_num, parse_number

from fakes import (FakeClient, FakeTelegram, callback_update, contact_update, photo_update,
                   sticker_update, text_update)

ADMIN = 111
WORKER = 222
CHANNEL = "-1001234567890"
TOKEN = "123456:ABCdefGhIJKlmnOPQrstUVwxyz12345"


# ======================= utils =======================
@pytest.mark.parametrize("text,money,expected", [
    ("450", False, 450), ("40,5", False, 40.5), ("40.5", False, 40.5), (" 45 ta ", False, 45),
    ("40g", False, 40), ("1 500 000", True, 1_500_000), ("1.500.000", True, 1_500_000),
    ("1,500", True, 1500), ("1,5", True, 1.5), ("1.500,75", True, 1500.75),
    ("1 500 000 so'm", True, 1_500_000), ("10%", False, 10),
    ("abc", False, None), ("-5", False, None), ("", False, None), (None, False, None),
    ("1.2.3", False, None),
])
def test_parse_number(text, money, expected):
    assert parse_number(text, money=money) == expected


def test_fmt_and_formula():
    assert fmt_num(57.6) == "57,6"
    assert fmt_num(1_500_000) == "1 500 000"
    assert fmt_num(5.76, 2) == "5,76"
    r = calc_yield(450, 32, 40)
    assert round(r["bio_c"], 4) == 57.6 and round(r["bio_t"], 4) == 5.76
    r = calc_yield(450, 32, 40, loss_pct=10, area_ha=12.5)
    assert round(r["exp_c"], 2) == 51.84 and round(r["total_t"], 2) == 64.8
    assert as_text("+998901234567") == "'+998901234567" and as_text("") == ""


# ======================= config =======================
def test_config_validation(tmp_path, monkeypatch):
    for k in ("BOT_TOKEN", "SPREADSHEET_ID", "ADMIN_IDS", "CHANNEL_ID", "TIMEZONE"):
        monkeypatch.delenv(k, raising=False)
    bad = tmp_path / "bad.env"
    bad.write_text("BOT_TOKEN=xxx\nADMIN_IDS=abc\nCHANNEL_ID=kanal\n")
    with pytest.raises(ConfigError) as e:
        load_config(bad)
    msg = str(e.value)
    assert "BOT_TOKEN" in msg and "SPREADSHEET_ID" in msg and "ADMIN_IDS" in msg and "CHANNEL_ID" in msg

    for k in ("BOT_TOKEN", "SPREADSHEET_ID", "ADMIN_IDS", "CHANNEL_ID"):
        monkeypatch.delenv(k, raising=False)
    good = tmp_path / "good.env"
    good.write_text(
        f"BOT_TOKEN={TOKEN}\n"
        "SPREADSHEET_ID=https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF/edit\n"
        "ADMIN_IDS=111, 333\n")
    cfg = load_config(good)
    assert cfg.spreadsheet_id == "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF"
    assert cfg.admin_ids == {111, 333} and cfg.channel_id is None
    assert cfg.tz.key == "Asia/Tashkent" and cfg.credentials_file.is_absolute()


@pytest.mark.parametrize("value", [
    "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF/edit?usp=sharing",
    "https://docs.google.com/spreadsheets/u/1/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF/edit#gid=0",
    '"1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF"',
    "​1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF​",
])
def test_spreadsheet_id_formats(tmp_path, monkeypatch, value):
    for k in ("BOT_TOKEN", "SPREADSHEET_ID", "ADMIN_IDS", "CHANNEL_ID"):
        monkeypatch.delenv(k, raising=False)
    f = tmp_path / ".env"
    f.write_text(f"BOT_TOKEN={TOKEN}\nSPREADSHEET_ID={value}\nADMIN_IDS=111\n", encoding="utf-8")
    assert load_config(f).spreadsheet_id == "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF"


def test_spreadsheet_id_duplicate_line_is_explained(tmp_path, monkeypatch):
    for k in ("BOT_TOKEN", "SPREADSHEET_ID", "ADMIN_IDS", "CHANNEL_ID"):
        monkeypatch.delenv(k, raising=False)
    f = tmp_path / ".env"
    f.write_text(f"BOT_TOKEN={TOKEN}\nSPREADSHEET_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF\n"
                 "ADMIN_IDS=111\nSPREADSHEET_ID=\n", encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_config(f)
    assert "bo'sh" in str(e.value) and "bir necha marta" in str(e.value)


# ======================= muhit =======================
@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(SH.time, "sleep", lambda s: None)


@pytest.fixture
def env(tmp_path):
    tg = FakeTelegram()
    client = FakeClient()
    db = SheetsDB(client=client, spreadsheet_id="x")
    db.connect()
    db.setup()
    # Dalalar ro'yxati
    fields = client.sh.sheets[SH.FIELDS]
    fields.rows += [["1-dala", "20", ""], ["3-dala", "12,5", ""], ["Bog' ortidagi", "", ""]]
    cfg = Config(bot_token=TOKEN, spreadsheet_id="x", admin_ids=frozenset({ADMIN}),
                 credentials_file=tmp_path / "c.json", channel_id=CHANNEL,
                 tz=ZoneInfo("Asia/Tashkent"), data_dir=tmp_path, log_dir=tmp_path)
    bot = TeleBot(TOKEN, parse_mode="HTML", threaded=False)
    ctx = Ctx(bot=bot, cfg=cfg, db=db, store=SessionStore(tmp_path / "s.json"),
              queue=PendingQueue(tmp_path / "q.json"))
    register_all(ctx)

    class E:
        pass
    e = E()
    e.tg, e.client, e.db, e.ctx, e.bot, e.tmp = tg, client, db, ctx, bot, tmp_path
    e.send = lambda upd: bot.process_new_updates([upd])
    e.say = lambda uid, text: bot.process_new_updates([text_update(uid, text)])
    e.ws = lambda title: client.sh.sheets[title]
    return e


def register(e, uid, name, phone="+998901112233"):
    e.say(uid, "/start")
    e.say(uid, name)
    e.send(contact_update(uid, phone))


def approve(e, uid):
    msg_id = 5555
    e.send(callback_update(ADMIN, f"adm:ok:{uid}", msg_id, text="Yangi xodim"))


# ======================= Google Sheets qatlami =======================
def test_sheets_setup_creates_all(env):
    sh = env.client.sh.sheets
    assert set(sh) == {SH.REPORTS, SH.HARVEST, SH.USERS, SH.FIELDS, SH.ACTIVITIES}
    for title, header in SH.HEADERS.items():
        assert sh[title].rows[0] == header
    assert [r[0] for r in sh[SH.ACTIVITIES].rows[1:]] == SH.DEFAULT_ACTIVITIES
    # qayta setup — takror sarlavha yoki tadbir qo'shilmaydi
    env.db.setup()
    assert len(sh[SH.ACTIVITIES].rows) == len(SH.DEFAULT_ACTIVITIES) + 1
    fields = env.db.get_fields()
    assert [(f.name, f.area_ha) for f in fields] == [("1-dala", 20), ("3-dala", 12.5), ("Bog' ortidagi", None)]


# ======================= Ro'yxatdan o'tish va tasdiqlash =======================
def test_admin_registration_is_auto_active(env):
    register(env, ADMIN, "Admin Adminov")
    u = env.db.get_user(ADMIN, fresh=True)
    assert u.status == SH.ACTIVE and u.name == "Admin Adminov" and u.phone == "+998901112233"
    assert "Admin Adminov" in env.tg.last_text(ADMIN)
    assert env.tg.last_markup(ADMIN)["keyboard"][0][0]["text"] == T.BTN_REPORT
    # telefon matn bo'lib saqlangan (raqamga aylanib ketmasligi uchun)
    assert env.ws(SH.USERS).rows[1][2] == "'+998901112233"


def test_worker_needs_approval(env):
    register(env, ADMIN, "Admin Adminov")
    env.tg.clear()
    env.say(WORKER, "/start")
    env.say(WORKER, "12345")                    # noto'g'ri ism
    assert env.tg.last_text(WORKER) == T.BAD_NAME
    env.say(WORKER, "Ali   Valiyev")
    env.send(contact_update(WORKER, "998907776655", contact_uid=777))   # birovning kontakti
    assert env.tg.last_text(WORKER) == T.PHONE_NOT_OWN
    env.say(WORKER, "90 777 66 55")             # qo'lda yozilgan raqam
    assert env.tg.last_text(WORKER) == T.REG_PENDING
    u = env.db.get_user(WORKER, fresh=True)
    assert u.status == SH.PENDING and u.name == "Ali Valiyev" and u.phone == "+998907776655"

    # adminga tasdiqlash tugmali xabar keldi
    admin_msg = [p for p in env.tg.sent("sendMessage") if str(p["chat_id"]) == str(ADMIN)][-1]
    assert "Ali Valiyev" in admin_msg["text"] and f"adm:ok:{WORKER}" in admin_msg["reply_markup"]

    # tasdiqlanmagan xodim hisobot bera olmaydi
    env.say(WORKER, T.BTN_REPORT)
    assert env.tg.last_text(WORKER) == T.STILL_PENDING

    # admin bo'lmagan odam tasdiqlay olmaydi
    env.send(callback_update(WORKER, f"adm:ok:{WORKER}", 1))
    assert env.db.get_user(WORKER, fresh=True).status == SH.PENDING

    approve(env, WORKER)
    assert env.db.get_user(WORKER, fresh=True).status == SH.ACTIVE
    assert env.tg.last_text(WORKER) == T.USER_APPROVED
    edited = env.tg.sent("editMessageText")[-1]["text"]
    assert "Tasdiqlandi" in edited
    # ikkinchi marta bosish — o'zgarish yo'q
    env.tg.clear()
    approve(env, WORKER)
    assert env.tg.sent("sendMessage") == []


def test_approve_old_message(env):
    """Admin so'rovni 2 kundan keyin tasdiqlasa ham ishlaydi (eski xabar)."""
    register(env, ADMIN, "Admin Adminov")
    register(env, WORKER, "Ali Valiyev")
    env.tg.clear()
    env.send(callback_update(ADMIN, f"adm:ok:{WORKER}", 4444, old=True))
    assert env.db.get_user(WORKER, fresh=True).status == SH.ACTIVE
    assert "Tasdiqlandi" in env.tg.last_text(ADMIN)
    assert env.tg.last_text(WORKER) == T.USER_APPROVED


def test_report_buttons_on_old_message(worker):
    e = worker
    e.say(WORKER, T.BTN_REPORT)
    for t in ("1-dala", "Ekish", T.BTN_SKIP, T.BTN_SKIP, T.BTN_NO_PHOTO, T.BTN_SKIP):
        e.say(WORKER, t)
    mid = e.ctx.store.get(WORKER)[1]["summary_mid"]
    e.send(callback_update(WORKER, "rep:send", mid, old=True))
    assert len(e.ws(SH.REPORTS).rows) == 2


def test_admin_forward_shows_channel_id(env):
    from telebot.types import Update
    env.send(Update.de_json({"update_id": 77001, "message": {
        "message_id": 1, "date": 1, "chat": {"id": ADMIN, "type": "private"},
        "from": {"id": ADMIN, "is_bot": False, "first_name": "A"}, "text": "post",
        "forward_origin": {"type": "channel", "date": 1, "message_id": 5,
                           "chat": {"id": -1009876543210, "type": "channel", "title": "Dala hisobotlari"}}}}))
    assert "CHANNEL_ID=-1009876543210" in env.tg.last_text(ADMIN)


def test_unregistered_user_is_blocked(env):
    env.say(WORKER, T.BTN_HARVEST)
    assert env.tg.last_text(WORKER) == T.NOT_REGISTERED
    env.say(WORKER, "/id")
    assert str(WORKER) in env.tg.last_text(WORKER)


# ======================= Hisobot oqimi =======================
@pytest.fixture
def worker(env):
    register(env, ADMIN, "Admin Adminov")
    register(env, WORKER, "Ali Valiyev", "+998907776655")
    approve(env, WORKER)
    env.tg.clear()
    return env


def test_full_report_flow(worker):
    e = worker
    e.say(WORKER, T.BTN_REPORT)
    kb = e.tg.last_markup(WORKER)
    assert [b["text"] for row in kb["keyboard"] for b in row][:3] == ["1-dala", "3-dala", "Bog' ortidagi"]

    e.say(WORKER, "99-dala")                       # ro'yxatda yo'q
    assert e.tg.last_text(WORKER) == T.PICK_FROM_LIST
    e.say(WORKER, "bog’ ortidagi")                  # boshqa apostrof va kichik harf
    assert e.ctx.store.get(WORKER)[1]["field"] == "Bog' ortidagi"
    e.say(WORKER, "sug'orish")
    e.send(sticker_update(WORKER))                  # stiker — bot qotmaydi
    assert e.tg.last_text(WORKER) == T.TEXT_EXPECTED
    e.say(WORKER, "-5")
    assert e.tg.last_text(WORKER) == T.BAD_AMOUNT
    e.say(WORKER, "12,5")
    e.say(WORKER, "LITR")
    e.say(WORKER, "1 500 000")
    assert e.ctx.store.state(WORKER) == S.REP_PHOTO

    # albom: 2 ta rasm, faqat bitta javob
    before = len(e.tg.texts_to(WORKER))
    e.send(photo_update(WORKER, "ph1", media_group_id="alb1"))
    e.send(photo_update(WORKER, "ph2", media_group_id="alb1"))
    assert len(e.tg.texts_to(WORKER)) == before + 1
    e.say(WORKER, T.BTN_CONTINUE)
    e.say(WORKER, "=HYPERLINK(\"x\") 12.10 kuni suv kam keldi")
    assert e.ctx.store.state(WORKER) == S.REP_CONFIRM

    summary = e.tg.last_text(WORKER)
    assert "Bog' ortidagi" in summary and "12,5 litr" in summary and "2 ta" in summary
    mid = e.ctx.store.get(WORKER)[1]["summary_mid"]

    e.say(WORKER, "salom")                          # tugma o'rniga matn
    assert e.tg.last_text(WORKER) == T.CONFIRM_USE_BUTTONS

    e.send(callback_update(WORKER, "rep:send", mid))
    # kanalga albom joylandi
    media = e.tg.sent("sendMediaGroup")
    assert len(media) == 1 and media[0]["chat_id"] == CHANNEL
    assert len(json.loads(media[0]["media"])) == 2

    rows = e.ws(SH.REPORTS).rows
    assert len(rows) == 2
    row = rows[1]
    assert row[3] == "'Ali Valiyev" and row[5] == "'Bog' ortidagi" and row[6] == "'Sug'orish"
    assert row[7] == 12.5 and row[8] == "'litr" and row[9] == 1_500_000
    assert re.fullmatch(r"https://t\.me/c/1234567890/\d+", row[10])
    assert row[11].startswith("'=HYPERLINK")       # formula emas, matn
    assert e.ws(SH.REPORTS).append_calls[-1] == "USER_ENTERED"

    # vaqt Toshkent vaqtida
    now = datetime.now(ZoneInfo("Asia/Tashkent"))
    stamp = datetime.strptime(f"{row[1]} {row[2]}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Tashkent"))
    assert abs(now - stamp) < timedelta(minutes=2)

    assert e.ctx.store.state(WORKER) is None
    assert "qabul qilindi va Google jadvalga yozildi" in e.tg.last_text(WORKER)

    # ikkinchi bosish — takror yozilmaydi
    e.send(callback_update(WORKER, "rep:send", mid))
    assert len(e.ws(SH.REPORTS).rows) == 2


def test_report_minimal_and_custom_activity(worker):
    e = worker
    e.say(WORKER, "/hisobot")
    e.say(WORKER, "1-dala")
    e.say(WORKER, T.BTN_OTHER)
    e.say(WORKER, "Mulchalash")
    e.say(WORKER, T.BTN_SKIP)          # miqdor yo'q -> birlik so'ralmaydi
    assert e.ctx.store.state(WORKER) == S.REP_COST
    e.say(WORKER, T.BTN_SKIP)
    e.say(WORKER, T.BTN_NO_PHOTO)
    e.say(WORKER, T.BTN_SKIP)
    mid = e.ctx.store.get(WORKER)[1]["summary_mid"]
    e.send(callback_update(WORKER, "rep:send", mid))
    row = e.ws(SH.REPORTS).rows[1]
    assert row[6] == "'Mulchalash" and row[7] == "" and row[8] == "" and row[9] == ""
    assert re.fullmatch(r"https://t\.me/c/1234567890/\d+", row[10])   # matnli post ham kanalda
    assert e.tg.sent("sendMediaGroup") == [] and e.tg.sent("sendPhoto") == []


def test_command_mid_flow_does_not_leak(worker):
    e = worker
    e.say(WORKER, T.BTN_REPORT)
    e.say(WORKER, "1-dala")
    e.say(WORKER, "/hosil")              # suhbat o'rtasida boshqa buyruq
    assert e.ctx.store.state(WORKER) == S.H_FIELD
    e.say(WORKER, "/nimadir")
    assert e.tg.last_text(WORKER) == T.UNKNOWN_COMMAND
    assert e.ctx.store.state(WORKER) == S.H_FIELD
    e.say(WORKER, T.BTN_CANCEL)
    assert e.ctx.store.state(WORKER) is None and e.tg.last_text(WORKER) == T.CANCELLED


def test_restart_and_cancel_buttons(worker):
    e = worker
    e.say(WORKER, T.BTN_REPORT)
    for t in ("1-dala", "Ekish", T.BTN_SKIP, T.BTN_SKIP, T.BTN_NO_PHOTO, T.BTN_SKIP):
        e.say(WORKER, t)
    mid = e.ctx.store.get(WORKER)[1]["summary_mid"]
    e.send(callback_update(WORKER, "rep:restart", mid))
    assert e.ctx.store.state(WORKER) == S.REP_FIELD
    # eski xabardagi "Yuborish" endi ishlamaydi
    e.send(callback_update(WORKER, "rep:send", mid))
    assert len(e.ws(SH.REPORTS).rows) == 1
    for t in ("1-dala", "Ekish", T.BTN_SKIP, T.BTN_SKIP, T.BTN_NO_PHOTO, T.BTN_SKIP):
        e.say(WORKER, t)
    mid = e.ctx.store.get(WORKER)[1]["summary_mid"]
    e.send(callback_update(WORKER, "rep:cancel", mid))
    assert e.ctx.store.state(WORKER) is None and len(e.ws(SH.REPORTS).rows) == 1


def test_session_survives_restart(worker):
    e = worker
    e.say(WORKER, T.BTN_REPORT)
    e.say(WORKER, "3-dala")
    e.say(WORKER, "O'g'itlash")
    # "bot qayta ishga tushdi" — saqlangan fayldan yangi store
    reloaded = SessionStore(e.tmp / "s.json")
    state, data = reloaded.get(WORKER)
    assert state == S.REP_AMOUNT and data["field"] == "3-dala" and data["activity"] == "O'g'itlash"


def test_blocked_during_flow(worker):
    e = worker
    e.say(WORKER, T.BTN_REPORT)
    for t in ("1-dala", "Ekish", T.BTN_SKIP, T.BTN_SKIP, T.BTN_NO_PHOTO, T.BTN_SKIP):
        e.say(WORKER, t)
    mid = e.ctx.store.get(WORKER)[1]["summary_mid"]
    e.db.set_user_status(WORKER, SH.BLOCKED)        # admin jadvalda blokladi
    e.send(callback_update(WORKER, "rep:send", mid))
    assert e.tg.last_text(WORKER) == T.BLOCKED_DURING_FLOW
    assert len(e.ws(SH.REPORTS).rows) == 1


# ======================= Google ishlamay qolsa =======================
def test_sheets_down_report_is_queued_then_flushed(worker):
    e = worker
    e.say(WORKER, T.BTN_REPORT)
    for t in ("1-dala", "Ekish", "100", "kg", T.BTN_SKIP):
        e.say(WORKER, t)
    e.send(photo_update(WORKER, "solo"))
    e.say(WORKER, T.BTN_CONTINUE)
    e.say(WORKER, T.BTN_SKIP)
    mid = e.ctx.store.get(WORKER)[1]["summary_mid"]

    e.ws(SH.REPORTS).fail_with = 503
    e.send(callback_update(WORKER, "rep:send", mid))
    assert len(e.ctx.queue) == 1
    assert "avtomatik yoziladi" in e.tg.last_text(WORKER)
    assert e.ctx.store.state(WORKER) is None
    assert len(e.tg.sent("sendPhoto")) == 1         # rasm kanalga baribir joylandi

    # navbat fayli diskda saqlangan
    assert len(PendingQueue(e.tmp / "q.json")) == 1

    e.ws(SH.REPORTS).fail_with = None
    sent = e.ctx.queue.flush(lambda it: e.db.append(it["sheet"], it["row"]),
                             lambda it: e.ctx.send(it["chat_id"], T.QUEUE_FLUSHED.format(label=it["label"])))
    assert sent == 1 and len(e.ctx.queue) == 0
    assert len(e.ws(SH.REPORTS).rows) == 2 and e.ws(SH.REPORTS).rows[1][7] == 100
    assert "Google jadvalga yozildi" in e.tg.last_text(WORKER)


def test_users_cache_survives_outage(worker):
    e = worker
    e.db._cache.clear()
    e.db.get_user(WORKER)                           # keshni to'ldirish
    e.ws(SH.USERS).fail_with = 503
    e.db._cache["users"] = (0, e.db._cache["users"][1])   # kesh eskirgan
    assert e.db.get_user(WORKER).status == SH.ACTIVE      # eski kesh bilan ishlaydi


def test_service_down_without_cache_gives_friendly_error(env):
    env.ws(SH.USERS).fail_with = 503
    env.say(WORKER, "/start")
    assert env.tg.last_text(WORKER) == T.SERVICE_DOWN


# ======================= Hosildorlik =======================
def test_harvest_flow(worker):
    e = worker
    e.say(WORKER, T.BTN_HARVEST)
    e.say(WORKER, "3-dala")
    e.say(WORKER, "5000")                           # oraliqdan tashqari
    assert "50 dan 2" in e.tg.last_text(WORKER)
    e.send(photo_update(WORKER, "x"))               # raqam o'rniga rasm
    assert e.tg.last_text(WORKER) == T.TEXT_EXPECTED
    e.say(WORKER, "450")
    e.say(WORKER, "32")
    e.say(WORKER, "40")
    e.say(WORKER, "10")
    res = e.tg.last_text(WORKER)
    assert "57,6 s/ga" in res and "5,76 t/ga" in res
    assert "51,8 s/ga" in res and "64,8 t" in res and "12,5 ga" in res
    assert "г" not in res                          # kirill harf yo'q
    row = e.ws(SH.HARVEST).rows[1]
    assert row[4] == "'3-dala" and row[5:9] == [450, 32, 40, 10]
    assert row[9] == 57.6 and row[10] == 51.84 and row[11] == 5.184 and row[12] == 12.5 and row[13] == 64.8
    assert e.ctx.store.state(WORKER) is None


def test_harvest_without_field_and_loss(worker):
    e = worker
    e.say(WORKER, "/hosil")
    e.say(WORKER, T.BTN_NO_FIELD)
    for t in ("450", "32", "40,0", T.BTN_SKIP):
        e.say(WORKER, t)
    res = e.tg.last_text(WORKER)
    assert "57,6 s/ga" in res and "hisobga olinmagan" in res and "Dala bo'yicha jami" not in res
    row = e.ws(SH.HARVEST).rows[1]
    assert row[4] == "" and row[8] == 0 and row[12] == "" and row[13] == ""


class _Resp:
    def __init__(self, code, msg):
        self.status_code, self.text, self._m = code, msg, msg

    def json(self):
        return {"error": {"code": self.status_code, "message": self._m, "status": "X"}}


@pytest.mark.parametrize("msg,expected", [
    ("Google Sheets API has not been used in project 123 before or it is disabled.", "yoqilmagan"),
    ("The caller does not have permission", "Google javobi: The caller does not have permission"),
])
def test_connect_error_messages(msg, expected):
    from gspread.exceptions import APIError

    class Client:
        def open_by_key(self, key):
            try:
                raise APIError(_Resp(403, msg))
            except APIError as ex:
                raise PermissionError from ex

    db = SheetsDB(client=Client(), spreadsheet_id="x")
    with pytest.raises(SH.SheetsError) as e:
        db.connect()
    assert expected in str(e.value)
