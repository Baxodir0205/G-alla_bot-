"""Google Sheets bilan ishlash.

- Kerakli varaqlar (Hisobotlar, Hosil prognozi, Xodimlar, Dalalar, Tadbirlar)
  birinchi ishga tushishda avtomatik yaratiladi.
- Qatorlar USER_ENTERED rejimida yoziladi: sana — sana, raqam — raqam bo'lib tushadi.
- Vaqtinchalik xatolarda (429, 5xx, tarmoq) avtomatik qayta urinadi.
- Ro'yxatlar keshlanadi, shuning uchun Google API limitlariga tushmaydi.
"""
import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, TypeVar

import gspread
import requests
from gspread.exceptions import APIError, SpreadsheetNotFound

from .utils import as_text, parse_number

log = logging.getLogger(__name__)
T = TypeVar("T")

REPORTS = "Hisobotlar"
HARVEST = "Hosil prognozi"
USERS = "Xodimlar"
FIELDS = "Dalalar"
ACTIVITIES = "Tadbirlar"

HEADERS: Dict[str, List[str]] = {
    REPORTS: ["ID", "Sana", "Vaqt", "Xodim", "Telegram ID", "Dala", "Tadbir turi",
              "Miqdor", "Birlik", "Summa (so'm)", "Rasm / post", "Izoh"],
    HARVEST: ["Sana", "Vaqt", "Xodim", "Telegram ID", "Dala", "Boshoq / m²", "Don / boshoq",
              "1000 don (g)", "Yo'qotish (%)", "Biologik (s/ga)", "Kutilayotgan (s/ga)",
              "Kutilayotgan (t/ga)", "Maydon (ga)", "Jami (t)"],
    USERS: ["Telegram ID", "Ism", "Telefon", "Username", "Holat", "Ro'yxatdan o'tgan"],
    FIELDS: ["Dala", "Maydon (ga)", "Izoh"],
    ACTIVITIES: ["Tadbir turi"],
}

DEFAULT_ACTIVITIES = [
    "Sug'orish", "O'g'itlash", "Dori sepish", "Shudgorlash", "Kultivatsiya",
    "Ekish", "Begona o't tozalash", "O'rim-yig'im",
]

# Xodim holatlari (jadvalda qo'lda ham o'zgartirish mumkin)
PENDING = "kutilmoqda"
ACTIVE = "faol"
REJECTED = "rad etildi"
BLOCKED = "bloklangan"

_RETRY_CODES = {429, 500, 502, 503, 504}


class SheetsError(Exception):
    """Sozlash xatolari (kalit fayl yo'q, jadvalga ruxsat yo'q va h.k.)."""


@dataclass
class User:
    id: int
    name: str
    phone: str
    username: str
    status: str
    row: int


@dataclass
class Field:
    name: str
    area_ha: Optional[float]


class SheetsDB:
    USERS_TTL = 60      # soniya — admin jadvalda holatni o'zgartirsa, 1 daqiqada kuchga kiradi
    LISTS_TTL = 300     # soniya — dalalar va tadbirlar ro'yxati

    def __init__(self, credentials_file: Optional[Path] = None,
                 spreadsheet_id: Optional[str] = None, client=None):
        self._creds = Path(credentials_file) if credentials_file else None
        self._sid = spreadsheet_id
        self._client = client
        self._sh = None
        self._ws: Dict[str, object] = {}
        self._lock = threading.RLock()
        self._cache: Dict[str, tuple] = {}

    # ---------- ulanish ----------
    def service_email(self) -> str:
        try:
            return json.loads(self._creds.read_text(encoding="utf-8"))["client_email"]
        except Exception:  # noqa: BLE001
            return "(credentials.json dagi client_email)"

    def connect(self) -> None:
        if self._client is None:
            if not self._creds or not self._creds.is_file():
                raise SheetsError(f"Google kalit fayli topilmadi: {self._creds}")
            try:
                self._client = gspread.service_account(filename=str(self._creds))
            except (ValueError, KeyError) as e:
                raise SheetsError(f"Google kalit fayli noto'g'ri: {e}") from e
        try:
            self._sh = self._call(lambda: self._client.open_by_key(self._sid))
        except (SpreadsheetNotFound, PermissionError) as e:
            api = e if isinstance(e, APIError) else e.__cause__
            detail = str(getattr(api, "error", {}).get("message", "")) if api is not None else ""
            if "has not been used" in detail or "disabled" in detail.lower():
                raise SheetsError(
                    "Google Sheets API bu loyihada yoqilmagan.\n"
                    "console.cloud.google.com/apis/library/sheets.googleapis.com sahifasida "
                    "service account loyihasini tanlab, Enable ni bosing va 1-2 daqiqa kuting."
                ) from e
            raise SheetsError(
                "Jadval topilmadi yoki botga ruxsat yo'q.\n"
                f"Jadvalni oching → Share (Bulishish) → {self.service_email()} "
                "manzilini Editor (Muharrir) sifatida qo'shing va SPREADSHEET_ID ni tekshiring."
                + (f"\nGoogle javobi: {detail}" if detail else "")
            ) from e

    def setup(self) -> None:
        """Varaqlarni tekshiradi, yo'qlarini sarlavhasi bilan yaratadi."""
        existing = {ws.title: ws for ws in self._call(self._sh.worksheets)}
        for title, header in HEADERS.items():
            ws = existing.get(title)
            if ws is None:
                ws = self._call(lambda t=title, h=header: self._sh.add_worksheet(
                    title=t, rows=1000, cols=max(len(h), 5)))
                log.info("'%s' varag'i yaratildi", title)
            first = self._call(lambda w=ws: w.row_values(1))
            if not any(c.strip() for c in first):
                self._call(lambda w=ws, h=header: w.update([h], "A1"))
                try:
                    self._call(lambda w=ws: w.format("1:1", {"textFormat": {"bold": True}}))
                    self._call(lambda w=ws: w.freeze(rows=1))
                except Exception:  # noqa: BLE001 — bezak, majburiy emas
                    log.warning("'%s' sarlavhasini formatlab bo'lmadi", title)
                if title == ACTIVITIES:
                    self._call(lambda w=ws: w.append_rows(
                        [[a] for a in DEFAULT_ACTIVITIES], value_input_option="USER_ENTERED",
                        table_range="A1"))
            elif [c.strip() for c in first[:len(header)]] != header:
                log.warning("'%s' varag'ining sarlavhasi kutilganidan farq qiladi: %s", title, first)
            self._ws[title] = ws

    def _worksheet(self, title: str):
        ws = self._ws.get(title)
        if ws is None:
            ws = self._call(lambda: self._sh.worksheet(title))
            self._ws[title] = ws
        return ws

    def _call(self, fn: Callable[[], T], retries: int = 3) -> T:
        delay = 1.0
        for attempt in range(retries + 1):
            try:
                with self._lock:
                    return fn()
            except APIError as e:
                if e.code in _RETRY_CODES and attempt < retries:
                    log.warning("Google Sheets %s xatosi, %.0f s dan keyin qayta urinish", e.code, delay)
                else:
                    raise
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt < retries:
                    log.warning("Google Sheets bilan aloqa yo'q (%s), qayta urinish", type(e).__name__)
                else:
                    raise
            time.sleep(delay)
            delay *= 2
        raise RuntimeError("unreachable")

    # ---------- yozish ----------
    def append(self, title: str, row: list) -> None:
        ws = self._worksheet(title)
        self._call(lambda: ws.append_row(row, value_input_option="USER_ENTERED", table_range="A1"))

    # ---------- keshlangan o'qish ----------
    def _cached(self, key: str, ttl: float, loader: Callable[[], T], force: bool = False) -> T:
        hit = self._cache.get(key)
        if hit and not force and time.monotonic() - hit[0] < ttl:
            return hit[1]
        try:
            value = loader()
        except Exception:
            if hit:  # Google javob bermasa — eski ma'lumot bilan ishlashda davom etamiz
                log.warning("'%s' yangilanmadi, keshdagi ma'lumot ishlatilmoqda", key)
                return hit[1]
            raise
        self._cache[key] = (time.monotonic(), value)
        return value

    def _load_users(self) -> Dict[int, User]:
        rows = self._call(lambda: self._worksheet(USERS).get_all_values())
        users = {}
        for i, r in enumerate(rows[1:], start=2):
            r = list(r) + [""] * 6
            tid = r[0].strip().lstrip("'")
            if not tid.isdigit():
                continue
            users[int(tid)] = User(
                id=int(tid), name=r[1].strip(), phone=r[2].strip(), username=r[3].strip(),
                status=r[4].strip().lower() or PENDING, row=i,
            )
        return users

    def get_user(self, tid: int, fresh: bool = False) -> Optional[User]:
        return self._cached("users", self.USERS_TTL, self._load_users, force=fresh).get(tid)

    def add_user(self, tid: int, name: str, phone: str, username: str,
                 status: str, registered_at: str) -> None:
        self.append(USERS, [as_text(tid), as_text(name), as_text(phone),
                            as_text(username), status, registered_at])
        self._cache.pop("users", None)

    def set_user_status(self, tid: int, status: str) -> bool:
        user = self.get_user(tid, fresh=True)
        if not user:
            return False
        ws = self._worksheet(USERS)
        self._call(lambda: ws.update_cell(user.row, 5, status))
        self._cache.pop("users", None)
        return True

    def _load_fields(self) -> List[Field]:
        rows = self._call(lambda: self._worksheet(FIELDS).get_all_values())
        fields, seen = [], set()
        for r in rows[1:]:
            r = list(r) + ["", ""]
            name = " ".join(r[0].split())
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            area = parse_number(r[1])
            fields.append(Field(name=name, area_ha=area if area and area > 0 else None))
        return fields

    def get_fields(self) -> List[Field]:
        return self._cached("fields", self.LISTS_TTL, self._load_fields)

    def _load_activities(self) -> List[str]:
        rows = self._call(lambda: self._worksheet(ACTIVITIES).get_all_values())
        acts, seen = [], set()
        for r in rows[1:]:
            name = " ".join((r[0] if r else "").split())
            if name and name.lower() not in seen:
                seen.add(name.lower())
                acts.append(name)
        return acts or list(DEFAULT_ACTIVITIES)

    def get_activities(self) -> List[str]:
        return self._cached("activities", self.LISTS_TTL, self._load_activities)
