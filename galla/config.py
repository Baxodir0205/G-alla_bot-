"""Sozlamalar: hammasi .env faylidan o'qiladi (kodda maxfiy ma'lumot yo'q)."""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

# Loyiha papkasi. Barcha nisbiy yo'llar shu papkaga nisbatan hisoblanadi,
# shuning uchun bot qaysi papkadan ishga tushirilishidan qat'i nazar ishlaydi
# (systemd, PythonAnywhere always-on task va h.k.).
BASE_DIR = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """Sozlamalarda xato bo'lsa chiqariladi."""


@dataclass(frozen=True)
class Config:
    bot_token: str
    spreadsheet_id: str
    admin_ids: FrozenSet[int]
    credentials_file: Path
    channel_id: Optional[str]
    tz: ZoneInfo
    data_dir: Path
    log_dir: Path


# Nusxalashda ko'rinmas belgilar qo'shilib qolishi mumkin (ayniqsa telefondan)
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def _get(key: str) -> str:
    """Qiymatni o'qiydi: bo'shliq, qo'shtirnoq va ko'rinmas belgilarni olib tashlaydi."""
    return os.getenv(key, "").translate(_INVISIBLE).strip().strip("'\"").strip()


def _shown(value: str) -> str:
    if not value:
        return "bo'sh"
    return repr(value if len(value) <= 70 else value[:67] + "...")


def _duplicate_keys(path: Path) -> set:
    """.env faylida ikki marta yozilgan kalitlar (oxirgisi kuchga kiradi — ko'p uchraydigan xato)."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    seen, dups = set(), set()
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key = s.split("=", 1)[0].strip()
        if key.startswith("export "):
            key = key[7:].strip()
        (dups if key in seen else seen).add(key)
    return dups


def _path(value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else BASE_DIR / p


def load_config(env_file: Optional[Path] = None) -> Config:
    env_path = Path(env_file) if env_file else BASE_DIR / ".env"
    load_dotenv(env_path)
    dups = _duplicate_keys(env_path)
    errors = []

    def hint(key: str) -> str:
        return f" Diqqat: {key} .env faylida bir necha marta yozilgan — ortiqchasini o'chiring." if key in dups else ""

    token = _get("BOT_TOKEN")
    if not re.fullmatch(r"\d+:[\w-]{20,}", token):
        state = "bo'sh" if not token else "formati noto'g'ri"
        errors.append(f"BOT_TOKEN {state} (@BotFather bergan tokenni yozing).{hint('BOT_TOKEN')}")

    # Jadval ID si yoki to'liq havolasi qabul qilinadi (har qanday Google Sheets havolasi).
    raw_sheet = _get("SPREADSHEET_ID")
    m = re.search(r"/d/([\w-]{20,})", raw_sheet)
    sheet = m.group(1) if m else raw_sheet
    if not re.fullmatch(r"[\w-]{20,}", sheet):
        errors.append(
            f"SPREADSHEET_ID noto'g'ri. Bot o'qigan qiymat: {_shown(raw_sheet)}. "
            "Jadval havolasini to'liq yoki /d/ va /edit orasidagi qismni yozing."
            + hint("SPREADSHEET_ID"))

    admin_ids = set()
    raw_admins = _get("ADMIN_IDS")
    for part in re.split(r"[,\s;]+", raw_admins):
        if not part:
            continue
        if part.isdigit():
            admin_ids.add(int(part))
        else:
            errors.append(f"ADMIN_IDS ichida noto'g'ri qiymat: {part!r} (faqat raqamli Telegram ID).")
    if not admin_ids:
        errors.append(
            "ADMIN_IDS kiritilmagan. Kamida bitta admin Telegram ID si kerak "
            "(ID ni bilish uchun botga /id yuboring yoki @userinfobot dan foydalaning)."
        )

    credentials_file = _path(_get("GOOGLE_CREDENTIALS") or "credentials.json")

    channel_id = _get("CHANNEL_ID") or None
    if channel_id and not (channel_id.startswith("@") or re.fullmatch(r"-100\d+", channel_id)):
        errors.append("CHANNEL_ID noto'g'ri: -100 bilan boshlanuvchi raqam yoki @kanal_nomi bo'lishi kerak.")

    tz_name = os.getenv("TIMEZONE", "Asia/Tashkent").strip()
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        errors.append(f"TIMEZONE noto'g'ri: {tz_name!r}")
        tz = None

    if errors:
        if not env_path.is_file():
            errors.append(f".env fayli topilmadi: {env_path}")
        raise ConfigError("\n".join(f"  • {e}" for e in errors))

    return Config(
        bot_token=token,
        spreadsheet_id=sheet,
        admin_ids=frozenset(admin_ids),
        credentials_file=credentials_file,
        channel_id=channel_id,
        tz=tz,
        data_dir=_path(os.getenv("DATA_DIR", "data").strip()),
        log_dir=_path(os.getenv("LOG_DIR", "logs").strip()),
    )
