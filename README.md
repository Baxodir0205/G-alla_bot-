# G'alla monitoringi boti (v2)

Dala hisobotlarini (agrotexnik tadbirlar) yig'ib Google Sheets'ga yozadigan va kutilayotgan hosildorlikni hisoblaydigan Telegram bot.

Stack TZ bo'yicha saqlangan: **Python + pyTelegramBotAPI + Google Sheets**.

## Eski koddan nimalar tuzatildi

| Muammo | Yechim |
|---|---|
| `if name == 'main'`, kirill "гektariga" | Tuzatildi |
| Rasm/stiker yuborilsa suhbat qotib qolardi | Har bosqich kiritilgan turni tekshiradi va qayta so'raydi |
| "40,5" (vergul) qabul qilinmasdi | `40,5`, `1 500 000`, `45 ta` va boshqa yozuvlar qabul qilinadi |
| Suhbat o'rtasidagi `/hosil` "dala raqami" bo'lib saqlanardi | Buyruqlar har doim ustun turadi. ❌ Bekor qilish va `/bekor` qo'shildi |
| Vaqt serverda UTC (5 soat farq) | `Asia/Tashkent` vaqt zonasi |
| Rasmning o'zi saqlanmasdi | Hisobot rasmlari bilan yopiq kanalga joylanadi, jadvalga post havolasi yoziladi |
| Sana va raqamlar jadvalga matn bo'lib tushardi | `USER_ENTERED`: sana sana, raqam raqam bo'lib yoziladi |
| Jadval xatosida barcha ma'lumot o'chardi | Avtomatik qayta urinish. Bo'lmasa navbatga qo'yiladi va keyin o'zi yoziladi |
| `oauth2client` eskirgan | `gspread.service_account()` (google-auth) |
| Holat xotirada edi, restartda yo'qolardi | Holat diskda (`data/sessions.json`) saqlanadi |
| Kirish nazorati yo'q edi | Ro'yxatdan o'tish + admin tasdig'i. Holatni jadvalda bloklash mumkin |
| Ism har safar so'ralardi | Bir marta ro'yxatdan o'tiladi |
| Dala va tadbir erkin matn edi | Jadvaldagi ro'yxatdan tugma bilan tanlanadi |
| Xarajat va hajm bitta ustunda edi | Miqdor, Birlik va Summa (so'm) alohida ustunlarda |
| Token kod ichida edi | `.env` fayli, `.gitignore` |
| Logging yo'q edi | `logs/bot.log` (aylanma fayl) |
| Hosil natijasi saqlanmasdi | "Hosil prognozi" varag'iga yoziladi, yo'qotish % va dala bo'yicha jami tonna hisoblanadi |
| Formula orqali jadvalni buzish (`=...`) mumkin edi | Barcha matnlar jadvalga xavfsiz matn sifatida yoziladi |

## O'rnatish

### 1. Telegram bot
1. @BotFather → `/newbot` → tokenni oling.
2. O'zingizning Telegram ID ingizni @userinfobot dan bilib oling (admin uchun).

### 2. Google service account
1. [console.cloud.google.com](https://console.cloud.google.com) → yangi loyiha.
2. **APIs & Services → Library** → **Google Sheets API** ni yoqing.
3. **Credentials → Create credentials → Service account** → yarating.
4. Service account → **Keys → Add key → JSON** → yuklangan faylni loyiha papkasiga `credentials.json` nomi bilan qo'ying.
5. Google jadvalni oching → **Share** → JSON ichidagi `client_email` manzilini **Editor** qilib qo'shing.

### 3. Kanal (tavsiya etiladi)
1. Yopiq kanal yarating (masalan "Dala hisobotlari"). Rahbariyatni a'zo qiling.
2. Botni kanalga **admin** qilib qo'shing.
3. Kanal ID si keyin aniqlanadi (5-qadamga qarang).

Kanal sozlanmasa ham bot ishlaydi. Bunda rasmli hisobotlar adminlarga shaxsiy xabar sifatida yuboriladi.

### 4. Ishga tushirish
```bash
cd galla-bot
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # keyin .env ni to'ldiring
python bot.py
```
Birinchi ishga tushishda bot jadvalda kerakli varaqlarni o'zi yaratadi.

### 5. Birinchi sozlashlar
1. Botga `/start` bosing. Admin avtomatik tasdiqlanadi.
2. Kanal ID si: kanaldagi istalgan postni botga **forward** qiling, bot ID ni ko'rsatadi. Uni `.env` ga `CHANNEL_ID=...` qilib yozing va botni qayta ishga tushiring.
3. Jadvaldagi **Dalalar** varag'ini to'ldiring (pastga qarang).

## Jadval tuzilmasi

| Varaq | Vazifasi | Kim to'ldiradi |
|---|---|---|
| **Hisobotlar** | Barcha dala hisobotlari | Bot |
| **Hosil prognozi** | Hosildorlik hisob-kitoblari | Bot |
| **Xodimlar** | Ro'yxatdan o'tganlar. **Holat**: `kutilmoqda` / `faol` / `rad etildi` / `bloklangan` | Bot + admin |
| **Dalalar** | A: dala nomi, B: maydon (ga). Bot shu ro'yxatni tugma qilib ko'rsatadi | Admin |
| **Tadbirlar** | Tadbir turlari ro'yxati (standartlari avtomatik qo'shiladi) | Admin |

- Xodimni bloklash uchun **Xodimlar → Holat** ga `bloklangan` deb yozing. Bu 1 daqiqada kuchga kiradi.
- Dalalar va tadbirlar o'zgarishi 5 daqiqada botda ko'rinadi.
- **Dalalar** varag'ida maydon (ga) ko'rsatilsa, hosil prognozida "dala bo'yicha jami tonna" ham hisoblanadi.
- Eski kod yozgan birinchi varaq (Sheet1) o'zgarishsiz qoladi.

## Hosildorlik formulasi

```
Biologik hosil (s/ga) = boshoq/m² × don/boshoq × 1000 don vazni (g) ÷ 10 000
Kutilayotgan hosil   = biologik × (1 − yo'qotish% ÷ 100)
```
Misol: 450 × 32 × 40 ÷ 10 000 = **57,6 s/ga** (5,76 t/ga).

## 24/7 ishlatish (xosting)

`nohup` bilan konsolda ishga tushirish **ishonchli emas**: PythonAnywhere konsollari vaqti-vaqti bilan qayta ishga tushiriladi va bot o'chadi.

- **VPS / Ubuntu server (tavsiya):** `deploy/galla-bot.service` faylidagi ko'rsatmaga amal qiling. Bot yiqilsa yoki server qayta yoqilsa, systemd uni avtomatik qayta ishga tushiradi.
- **PythonAnywhere:** faqat pullik akkauntdagi **Always-on task** orqali. Buyruq: `/home/USERNAME/galla-bot/venv/bin/python /home/USERNAME/galla-bot/bot.py`

⚠️ Bot bir vaqtda faqat **bitta** joyda ishlashi kerak. Kompyuterda va serverda birga ishlatilsa, Telegram `409 Conflict` xatosini beradi.

## Loyiha tuzilmasi

```
bot.py                 — ishga tushirish, logging, navbat ishchisi
galla/config.py        — .env sozlamalarini o'qish va tekshirish
galla/sheets.py        — Google Sheets: varaqlar, kesh, qayta urinish
galla/storage.py       — suhbat holati va navbat (diskda)
galla/texts.py         — botning barcha matnlari (shu yerda tahrirlang)
galla/keyboards.py     — tugmalar
galla/handlers/        — ro'yxatdan o'tish, hisobot, hosil, admin
tests/                 — oflayn testlar
deploy/                — systemd xizmati
```

## Testlar
```bash
pip install pytest
python -m pytest -q
```
Testlar soxta Telegram va soxta jadval bilan ishlaydi. Internet kerak emas.
