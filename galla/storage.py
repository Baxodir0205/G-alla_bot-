"""Diskda saqlanadigan holatlar.

SessionStore — har bir foydalanuvchining qaysi bosqichda ekanligi va kiritgan
ma'lumotlari. Bot qayta ishga tushsa ham yarim qolgan hisobot yo'qolmaydi.

PendingQueue — Google Sheets vaqtincha ishlamay qolsa, qatorlar shu navbatga
yoziladi va keyin avtomatik ravishda jadvalga yuboriladi.

Fayllar "atomik" yoziladi (avval vaqtinchalik faylga, keyin almashtiriladi),
shuning uchun yozish o'rtasida tok o'chsa ham fayl buzilmaydi.
"""
import copy
import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _load(path: Path, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError):
        broken = path.with_name(path.name + ".broken")
        log.exception("%s o'qilmadi, %s nomi bilan saqlab qo'yildi", path, broken.name)
        try:
            os.replace(path, broken)
        except OSError:
            pass
        return default


class SessionStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._data: Dict[str, dict] = _load(self.path, {})

    def _save(self) -> None:
        _atomic_write(self.path, self._data)

    def get(self, uid: int) -> Tuple[Optional[str], dict]:
        with self._lock:
            s = self._data.get(str(uid))
            if not s:
                return None, {}
            return s["state"], copy.deepcopy(s["data"])

    def state(self, uid: int) -> Optional[str]:
        return self.get(uid)[0]

    def start(self, uid: int, state: str, **data) -> None:
        """Yangi suhbat boshlash (oldingi ma'lumotlar o'chadi)."""
        with self._lock:
            self._data[str(uid)] = {"state": state, "data": dict(data)}
            self._save()

    def set_state(self, uid: int, state: str, **updates) -> None:
        with self._lock:
            s = self._data.setdefault(str(uid), {"state": state, "data": {}})
            s["state"] = state
            s["data"].update(updates)
            self._save()

    def update(self, uid: int, **updates) -> None:
        with self._lock:
            s = self._data.get(str(uid))
            if s:
                s["data"].update(updates)
                self._save()

    def append(self, uid: int, key: str, value: Any, limit: int) -> Optional[int]:
        """Ro'yxatga qo'shadi; limitga yetgan bo'lsa None qaytaradi."""
        with self._lock:
            s = self._data.get(str(uid))
            if not s:
                return None
            items = s["data"].setdefault(key, [])
            if len(items) >= limit:
                return None
            items.append(value)
            self._save()
            return len(items)

    def swap(self, uid: int, key: str, value: Any) -> bool:
        """Qiymat o'zgargan bo'lsa yozadi va True qaytaradi (albom uchun)."""
        with self._lock:
            s = self._data.get(str(uid))
            if not s or s["data"].get(key) == value:
                return False
            s["data"][key] = value
            self._save()
            return True

    def transition(self, uid: int, expected: str, new: str) -> bool:
        """Holat `expected` bo'lsa, uni `new` ga o'zgartiradi (ikki marta bosishdan himoya)."""
        with self._lock:
            s = self._data.get(str(uid))
            if not s or s["state"] != expected:
                return False
            s["state"] = new
            self._save()
            return True

    def clear(self, uid: int) -> bool:
        with self._lock:
            if self._data.pop(str(uid), None) is None:
                return False
            self._save()
            return True


class PendingQueue:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._flush_lock = threading.Lock()
        self._items: List[dict] = _load(self.path, [])

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def add(self, item: dict) -> None:
        with self._lock:
            self._items.append({**item, "qid": uuid.uuid4().hex})
            _atomic_write(self.path, self._items)
        log.warning("Navbatga qo'shildi: %s (navbatda %d ta)", item.get("label"), len(self))

    def flush(self, sender: Callable[[dict], None],
              on_sent: Optional[Callable[[dict], None]] = None) -> int:
        """Navbatdagilarni tartib bilan yuboradi. Birinchi xatoda to'xtaydi."""
        if not self._flush_lock.acquire(blocking=False):
            return 0
        sent = 0
        try:
            with self._lock:
                snapshot = list(self._items)
            for item in snapshot:
                try:
                    sender(item)
                except Exception as e:  # noqa: BLE001 — keyingi safar qayta urinamiz
                    log.warning("Navbatni yuborib bo'lmadi (%s), keyinroq qayta urinamiz", e)
                    break
                with self._lock:
                    self._items = [i for i in self._items if i["qid"] != item["qid"]]
                    _atomic_write(self.path, self._items)
                sent += 1
                if on_sent:
                    try:
                        on_sent(item)
                    except Exception:  # noqa: BLE001
                        log.exception("Navbat xabarnomasida xato")
        finally:
            self._flush_lock.release()
        if sent:
            log.info("Navbatdan %d ta qator jadvalga yozildi", sent)
        return sent
