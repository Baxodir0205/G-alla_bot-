"""Yordamchi funksiyalar: raqamlarni o'qish/formatlash va hosildorlik formulasi."""
import html
import re
from typing import Optional

_SPACES = re.compile(r"[\s  '’`]")
_TRAILING_UNIT = re.compile(r"[^\d.,]+$")


def parse_number(text: Optional[str], money: bool = False) -> Optional[float]:
    """Foydalanuvchi yozgan raqamni o'qiydi.

    Qabul qilinadi: "450", "40,5", "40.5", "1 500 000", "1.500.000", "45 ta", "40 g".
    money=True bo'lsa, bitta ajratkichdan keyin aynan 3 ta raqam kelsa
    ("1,500") u minglik ajratkich deb hisoblanadi.
    Manfiy yoki raqam bo'lmagan qiymatlar uchun None qaytaradi.
    """
    if text is None:
        return None
    s = _SPACES.sub("", str(text).strip())
    s = _TRAILING_UNIT.sub("", s)  # "45ta", "40g", "500so'm", "10%" -> raqam qismi
    if not s or not re.fullmatch(r"\d[\d.,]*\d|\d", s):
        return None

    seps = re.findall(r"[.,]", s)
    if not seps:
        return float(s)

    if len(seps) > 1:
        if len(set(seps)) == 1:
            # 1.500.000 yoki 1,500,000 — minglik ajratkichlar
            groups = s.split(seps[0])
            if all(len(g) == 3 for g in groups[1:]):
                return float("".join(groups))
            return None
        # Aralash: oxirgi ajratkich — o'nlik, qolganlari — minglik (1.500,75 / 1,500.75)
        last = max(s.rfind("."), s.rfind(","))
        int_part = re.sub(r"[.,]", "", s[:last])
        return float(f"{int_part}.{s[last + 1:]}")

    int_part, frac = re.split(r"[.,]", s)
    if money and len(frac) == 3:
        return float(int_part + frac)
    return float(f"{int_part}.{frac}")


def fmt_num(x: Optional[float], decimals: int = 1) -> str:
    """57.6 -> "57,6"; 1500000 -> "1 500 000" (o'zbekcha yozilish)."""
    if x is None:
        return "—"
    if abs(x - round(x)) < 1e-9:
        s = f"{int(round(x)):,}"
    else:
        s = f"{x:,.{decimals}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
    return s.replace(",", " ").replace(".", ",")


def calc_yield(spikes: float, grains: float, tkw: float,
               loss_pct: float = 0.0, area_ha: Optional[float] = None) -> dict:
    """Biologik hosildorlik formulasi.

    Hosildorlik (s/ga) = boshoq/m² × don/boshoq × 1000 don vazni (g) / 10 000
    (1 m² dagi don massasi grammda × 10 000 m² ÷ 100 000 g/sentner).
    """
    bio_c = spikes * grains * tkw / 10_000
    exp_c = bio_c * (1 - loss_pct / 100)
    return {
        "bio_c": bio_c,
        "bio_t": bio_c / 10,
        "exp_c": exp_c,
        "exp_t": exp_c / 10,
        "total_t": exp_c / 10 * area_ha if area_ha else None,
    }


def esc(value) -> str:
    """Foydalanuvchi matnini Telegram HTML uchun xavfsiz qiladi."""
    return html.escape(str(value), quote=False)


def as_text(value) -> str:
    """Google Sheets'ga matnni "matn" sifatida yozish.

    USER_ENTERED rejimida "+998..." raqamga, "12.10" sanaga, "=..." formulaga
    aylanib ketadi. Boshiga ' qo'yilsa, Sheets uni oddiy matn sifatida saqlaydi
    va ' belgisi katakda ko'rinmaydi.
    """
    if value is None or value == "":
        return ""
    return "'" + str(value)


def clean_text(text: str, max_len: int) -> str:
    """Ortiqcha bo'shliqlarni olib tashlaydi va uzunlikni cheklaydi."""
    return " ".join(str(text).split())[:max_len]
