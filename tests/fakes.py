"""Testlar uchun soxta Telegram API va soxta Google Sheets."""
import itertools
import json

from telebot import apihelper
from telebot.types import Update


# ---------------- Soxta Telegram ----------------
class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)
        self.reason = "OK"

    def json(self):
        return self._payload


class FakeTelegram:
    """apihelper.CUSTOM_REQUEST_SENDER orqali barcha so'rovlarni ushlaydi."""

    def __init__(self):
        self.calls = []
        self._ids = itertools.count(1000)
        self.fail_chats = set()
        apihelper.CUSTOM_REQUEST_SENDER = self

    def _msg(self, chat_id, text=None, chat_type="private"):
        return {"message_id": next(self._ids), "date": 0,
                "chat": {"id": int(chat_id) if str(chat_id).lstrip("-").isdigit() else -1001,
                         "type": chat_type}, "text": text or ""}

    def __call__(self, method, url, params=None, files=None, **kw):
        name = url.rsplit("/", 1)[-1]
        params = dict(params or {})
        self.calls.append((name, params))
        chat = params.get("chat_id")
        if chat is not None and str(chat) in self.fail_chats:
            return FakeResponse({"ok": False, "error_code": 403, "description": "Forbidden"}, 403)
        if name == "getMe":
            res = {"id": 999, "is_bot": True, "first_name": "Bot", "username": "galla_test_bot"}
        elif name in ("sendMessage", "sendPhoto", "editMessageText"):
            ctype = "channel" if str(chat).startswith("-100") else "private"
            res = self._msg(chat or 1, params.get("text") or params.get("caption"), ctype)
        elif name == "sendMediaGroup":
            media = json.loads(params["media"])
            res = [self._msg(chat, None, "channel") for _ in media]
        elif name == "getChatMember":
            perms = ["can_be_edited", "is_anonymous", "can_manage_chat", "can_delete_messages",
                     "can_manage_video_chats", "can_restrict_members", "can_promote_members",
                     "can_change_info", "can_invite_users", "can_post_stories", "can_edit_stories",
                     "can_delete_stories"]
            res = {"status": "administrator", **{p: True for p in perms},
                   "user": {"id": 999, "is_bot": True, "first_name": "Bot"}}
        else:
            res = True
        return FakeResponse({"ok": True, "result": res})

    # yordamchilar
    def sent(self, method=None):
        return [p for n, p in self.calls if method is None or n == method]

    def texts_to(self, chat_id):
        return [p.get("text") or p.get("caption") or "" for n, p in self.calls
                if n in ("sendMessage", "sendPhoto") and str(p.get("chat_id")) == str(chat_id)]

    def last_text(self, chat_id):
        t = self.texts_to(chat_id)
        return t[-1] if t else None

    def last_markup(self, chat_id):
        for n, p in reversed(self.calls):
            if n == "sendMessage" and str(p.get("chat_id")) == str(chat_id):
                return json.loads(p["reply_markup"]) if p.get("reply_markup") else None
        return None

    def clear(self):
        self.calls.clear()


# ---------------- Soxta yangilanishlar ----------------
_uid_counter = itertools.count(1)


def _user(uid, username=None):
    u = {"id": uid, "is_bot": False, "first_name": f"User{uid}"}
    if username:
        u["username"] = username
    return u


def text_update(uid, text, username=None):
    n = next(_uid_counter)
    return Update.de_json({"update_id": n, "message": {
        "message_id": n, "date": 0, "chat": {"id": uid, "type": "private"},
        "from": _user(uid, username), "text": text}})


def photo_update(uid, file_id, media_group_id=None):
    n = next(_uid_counter)
    msg = {"message_id": n, "date": 0, "chat": {"id": uid, "type": "private"}, "from": _user(uid),
           "photo": [{"file_id": file_id + "_s", "file_unique_id": "s", "width": 90, "height": 90},
                     {"file_id": file_id, "file_unique_id": "b", "width": 1280, "height": 960}]}
    if media_group_id:
        msg["media_group_id"] = media_group_id
    return Update.de_json({"update_id": n, "message": msg})


def sticker_update(uid):
    n = next(_uid_counter)
    return Update.de_json({"update_id": n, "message": {
        "message_id": n, "date": 0, "chat": {"id": uid, "type": "private"}, "from": _user(uid),
        "sticker": {"file_id": "stk", "file_unique_id": "stk", "type": "regular", "width": 512,
                    "height": 512, "is_animated": False, "is_video": False}}})


def contact_update(uid, phone, contact_uid=None):
    n = next(_uid_counter)
    return Update.de_json({"update_id": n, "message": {
        "message_id": n, "date": 0, "chat": {"id": uid, "type": "private"}, "from": _user(uid),
        "contact": {"phone_number": phone, "first_name": "X", "user_id": contact_uid or uid}}})


def callback_update(uid, data, message_id, text="msg", old=False):
    """old=True — 48 soatdan eski xabar (Telegram uni date=0 bilan, matnsiz yuboradi)."""
    n = next(_uid_counter)
    msg = {"message_id": message_id, "date": 0 if old else 1_700_000_000,
           "chat": {"id": uid, "type": "private"}}
    if not old:
        msg.update({"from": _user(999), "text": text})
    return Update.de_json({"update_id": n, "callback_query": {
        "id": str(n), "from": _user(uid), "chat_instance": "ci", "data": data, "message": msg}})


# ---------------- Soxta Google Sheets ----------------
class FakeAPIResponse:
    def __init__(self, code):
        self.status_code = code
        self.text = "err"

    def json(self):
        return {"error": {"code": self.status_code, "message": "fake", "status": "FAKE"}}


class FakeWorksheet:
    def __init__(self, title):
        self.title = title
        self.rows = []
        self.fail_with = None  # APIError bersin
        self.append_calls = []

    def _check(self):
        if self.fail_with:
            from gspread.exceptions import APIError
            raise APIError(FakeAPIResponse(self.fail_with))

    @staticmethod
    def _display(v):
        s = "" if v is None else str(v)
        return s[1:] if s.startswith("'") else s

    def row_values(self, i):
        self._check()
        return [self._display(v) for v in self.rows[i - 1]] if len(self.rows) >= i else []

    def update(self, values, range_name=None, **kw):
        self._check()
        assert range_name == "A1"
        if self.rows:
            self.rows[0] = list(values[0])
        else:
            self.rows.append(list(values[0]))

    def format(self, *a, **k):
        pass

    def freeze(self, *a, **k):
        pass

    def append_row(self, row, value_input_option="RAW", table_range=None, **kw):
        self._check()
        self.append_calls.append(value_input_option)
        self.rows.append(list(row))

    def append_rows(self, rows, value_input_option="RAW", table_range=None, **kw):
        for r in rows:
            self.append_row(r, value_input_option, table_range)

    def get_all_values(self):
        self._check()
        return [[self._display(v) for v in r] for r in self.rows]

    def update_cell(self, r, c, value):
        self._check()
        row = self.rows[r - 1]
        while len(row) < c:
            row.append("")
        row[c - 1] = value


class FakeSpreadsheet:
    def __init__(self):
        self.sheets = {}

    def worksheets(self):
        return list(self.sheets.values())

    def add_worksheet(self, title, rows, cols):
        ws = FakeWorksheet(title)
        self.sheets[title] = ws
        return ws

    def worksheet(self, title):
        return self.sheets[title]


class FakeClient:
    def __init__(self):
        self.sh = FakeSpreadsheet()

    def open_by_key(self, key):
        return self.sh
