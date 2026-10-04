"""Botning barcha matnlari bir joyda — tahrirlash oson bo'lishi uchun."""

# ---------- Tugmalar ----------
BTN_REPORT = "📝 Hisobot topshirish"
BTN_HARVEST = "🌾 Hosilni hisoblash"
BTN_HELP = "ℹ️ Yordam"
BTN_CANCEL = "❌ Bekor qilish"
BTN_SKIP = "⏭ O'tkazib yuborish"
BTN_NO_PHOTO = "⏭ Rasmsiz davom etish"
BTN_CONTINUE = "✅ Davom etish"
BTN_OTHER = "✏️ Boshqa"
BTN_NO_FIELD = "⏭ Dalani ko'rsatmasdan"
BTN_PHONE = "📱 Telefon raqamni yuborish"

UNITS = ["kg", "tonna", "litr", "m³", "gektar", "dona"]

# ---------- Umumiy ----------
WELCOME = "Assalomu alaykum, <b>{name}</b>! 👋\nKerakli bo'limni tanlang:"
MENU_HINT = "Quyidagi menyudan tanlang 👇"
CANCELLED = "❌ Bekor qilindi."
NOTHING_TO_CANCEL = "Bekor qiladigan amal yo'q."
TEXT_EXPECTED = "Iltimos, javobni matn ko'rinishida yozing yoki tugmalardan birini bosing."
PICK_FROM_LIST = "Iltimos, quyidagi ro'yxatdan tanlang 👇"
UNEXPECTED_ERROR = "⚠️ Kutilmagan xatolik yuz berdi. Qayta urinib ko'ring yoki /bekor ni bosing."
SERVICE_DOWN = "⚠️ Google jadval bilan aloqa vaqtincha yo'q. Bir necha daqiqadan so'ng qayta urinib ko'ring."
YOUR_ID = "Sizning Telegram ID raqamingiz: <code>{id}</code>"
UNKNOWN_COMMAND = "Noma'lum buyruq. Buyruqlar ro'yxati: /yordam"
CHANNEL_ID_INFO = (
    "📢 Kanal: <b>{title}</b>\nID: <code>{id}</code>\n\n"
    ".env fayliga yozing: <code>CHANNEL_ID={id}</code>\nva botni kanalga admin qiling."
)

HELP = (
    "<b>G'alla monitoringi boti</b>\n\n"
    f"{BTN_REPORT} — bajarilgan agrotexnik tadbir haqida hisobot (Google jadvalga yoziladi).\n"
    f"{BTN_HARVEST} — kutilayotgan hosildorlik prognozi.\n\n"
    "<b>Buyruqlar:</b>\n"
    "/hisobot — hisobot topshirish\n"
    "/hosil — hosildorlikni hisoblash\n"
    "/bekor — joriy amalni bekor qilish\n"
    "/id — Telegram ID raqamingiz\n\n"
    "<b>Hosildorlik formulasi:</b>\n"
    "<code>s/ga = boshoq/m² × don/boshoq × 1000 don vazni (g) ÷ 10 000</code>\n"
    "Bu biologik hosil. O'rimdagi yo'qotishlarni hisobga olish uchun yo'qotish foizini kiriting."
)

# ---------- Ro'yxatdan o'tish ----------
REG_WELCOME = (
    "Assalomu alaykum! 👋\n"
    "Botdan foydalanish uchun bir martalik ro'yxatdan o'ting.\n\n"
    "Ism va familiyangizni yozing:"
)
BAD_NAME = "Iltimos, ism va familiyangizni harflar bilan yozing (3–60 belgi)."
ASK_PHONE = f"Telefon raqamingizni yuboring: «{BTN_PHONE}» tugmasini bosing yoki raqamni yozing (masalan: +998901234567)."
BAD_PHONE = "Telefon raqami noto'g'ri. Masalan: +998901234567"
PHONE_NOT_OWN = "Iltimos, o'zingizning raqamingizni yuboring."
REG_PENDING = "✅ So'rovingiz adminga yuborildi. Tasdiqlangach, sizga xabar keladi."
STILL_PENDING = "⏳ So'rovingiz hali admin tomonidan tasdiqlanmagan. Iltimos, kuting."
NOT_REGISTERED = "Avval ro'yxatdan o'ting: /start"
ACCESS_DENIED = "⛔️ Sizga botdan foydalanish ruxsati berilmagan. Admin bilan bog'laning."
USER_APPROVED = "🎉 So'rovingiz tasdiqlandi! Endi botdan foydalanishingiz mumkin."
USER_REJECTED = "❌ So'rovingiz rad etildi. Savollar bo'lsa, admin bilan bog'laning."

ADMIN_NEW_USER = (
    "🆕 <b>Yangi xodim ro'yxatdan o'tmoqchi</b>\n\n"
    "👤 {name}\n📱 {phone}\n🔗 {username}\n🆔 <code>{id}</code>"
)
ADMIN_APPROVED = "\n\n✅ Tasdiqlandi ({admin})"
ADMIN_REJECTED = "\n\n❌ Rad etildi ({admin})"
ADMIN_ALREADY = "Bu so'rov allaqachon ko'rib chiqilgan (holat: {status})"
ADMIN_ONLY = "Bu amal faqat adminlar uchun"
USER_NOT_FOUND = "Xodim topilmadi"

# ---------- Hisobot ----------
ASK_FIELD = "🌾 Qaysi dalada ish bajarildi? Ro'yxatdan tanlang:"
ASK_FIELD_FREE = "🌾 Dala raqami yoki nomini yozing:"
ASK_ACTIVITY = "🛠 Qanday agrotexnik tadbir bajarildi?"
ASK_ACTIVITY_OTHER = "Tadbir nomini yozing:"
ASK_AMOUNT = (
    "📦 Ishlatilgan resurs miqdorini yozing (faqat raqam, masalan: 250 yoki 12,5).\n"
    f"Miqdor bo'lmasa — «{BTN_SKIP}»."
)
BAD_AMOUNT = "Miqdor noto'g'ri. Musbat raqam yozing, masalan: 250 yoki 12,5"
ASK_UNIT = "O'lchov birligini tanlang:"
ASK_COST = (
    "💰 Sarflangan pul miqdori (so'mda), masalan: 1 500 000.\n"
    f"Xarajat bo'lmasa — «{BTN_SKIP}»."
)
BAD_COST = "Summa noto'g'ri. Masalan: 1500000 yoki 1 500 000"
ASK_PHOTO = (
    "📷 Dala holatidan rasm yuboring (bir nechta bo'lishi mumkin, 10 tagacha).\n"
    f"Rasm bo'lmasa — «{BTN_NO_PHOTO}»."
)
PHOTO_ADDED = f"📷 Rasm qabul qilindi ({{n}}). Yana yuborishingiz yoki «{BTN_CONTINUE}» tugmasini bosishingiz mumkin."
PHOTOS_ADDED_ALBUM = f"📷 Rasmlar qabul qilinmoqda. Tayyor bo'lsa, «{BTN_CONTINUE}» tugmasini bosing."
PHOTO_LIMIT = f"Ko'pi bilan 10 ta rasm. «{BTN_CONTINUE}» tugmasini bosing."
PHOTO_AS_PHOTO = "Rasmni fayl emas, oddiy rasm (Foto) sifatida yuboring."
PHOTO_EXPECTED = f"Rasm yuboring yoki «{BTN_NO_PHOTO}» tugmasini bosing."
ASK_NOTE = f"💬 Qo'shimcha izoh yoki muammolar bo'lsa yozing (ixtiyoriy). Bo'lmasa — «{BTN_SKIP}»."
NOTE_TOO_LONG = "Izoh juda uzun. Iltimos, 1000 belgidan qisqaroq yozing."
CHECK_REPORT = "Hisobotni tekshiring 👇"
CONFIRM_USE_BUTTONS = "Iltimos, hisobot ostidagi tugmalardan birini bosing: ✅ Yuborish yoki ❌ Bekor qilish."
SENDING_WAIT = "⏳ Hisobot yuborilmoqda, kuting..."
ALREADY_HANDLED = "Bu hisobot allaqachon yuborilgan yoki bekor qilingan"
BLOCKED_DURING_FLOW = "⛔️ Sizning ruxsatingiz bekor qilingan. Hisobot yuborilmadi."

REPORT_SUMMARY = (
    "📋 <b>Hisobot</b>\n\n"
    "👤 Xodim: {staff}\n"
    "🌾 Dala: {field}\n"
    "🛠 Tadbir: {activity}\n"
    "📦 Miqdor: {amount}\n"
    "💰 Summa: {cost}\n"
    "📷 Rasmlar: {photos}\n"
    "💬 Izoh: {note}"
)
BTN_SEND = "✅ Yuborish"
BTN_RESTART = "✏️ Qaytadan to'ldirish"
REPORT_SAVED = "✅ Hisobot <b>#{rid}</b> qabul qilindi va Google jadvalga yozildi!"
REPORT_QUEUED = (
    "✅ Hisobot <b>#{rid}</b> qabul qilindi.\n"
    "⏳ Google jadval hozir javob bermayapti — hisobot saqlab qo'yildi va aloqa tiklanishi bilan "
    "avtomatik yoziladi. Qayta yuborish shart emas."
)
QUEUE_FLUSHED = "✅ {label} Google jadvalga yozildi."
SEND_FAILED = "⚠️ Hisobotni yuborishda xatolik. Ma'lumotlaringiz saqlangan — «✅ Yuborish» ni qayta bosing."

CHANNEL_POST = (
    "📝 <b>Hisobot #{rid}</b>\n"
    "🕒 {date} {time}\n"
    "👤 {staff}\n"
    "🌾 Dala: {field}\n"
    "🛠 {activity}\n"
    "📦 Miqdor: {amount}\n"
    "💰 Summa: {cost}\n"
    "💬 {note}"
)

# ---------- Hosil ----------
ASK_H_FIELD = "🌾 Qaysi dala uchun hisoblaymiz?"
ASK_SPIKES = "1 m² dagi hosilli boshoqlar sonini kiriting (masalan: 450):"
ASK_GRAINS = "Bitta boshoqdagi o'rtacha donlar sonini kiriting (masalan: 32):"
ASK_TKW = "1000 ta don vaznini grammda kiriting (masalan: 40):"
ASK_LOSS = (
    "O'rim-yig'imdagi taxminiy yo'qotish foizini kiriting (masalan: 10).\n"
    f"Bilmasangiz — «{BTN_SKIP}» (faqat biologik hosil hisoblanadi)."
)
BAD_RANGE = "Qiymat noto'g'ri. {lo} dan {hi} gacha bo'lgan raqam kiriting."

HARVEST_RESULT = (
    "📊 <b>Hosildorlik prognozi</b>\n"
    "{field_line}"
    "\n🌾 Boshoqlar: {spikes} ta/m²\n"
    "🔢 Don/boshoq: {grains} ta\n"
    "⚖️ 1000 don vazni: {tkw} g\n"
    "{loss_line}"
    "\n🌱 Biologik hosil: <b>{bio_c} s/ga</b> ({bio_t} t/ga)\n"
    "{exp_line}"
    "{total_line}"
)
HARVEST_FIELD_LINE = "📍 Dala: {field}{area}\n"
HARVEST_LOSS_LINE = "📉 Yo'qotish: {loss}%\n"
HARVEST_EXP_LINE = "✅ Kutilayotgan hosil: <b>{exp_c} s/ga</b> ({exp_t} t/ga)\n"
HARVEST_NO_LOSS_NOTE = "<i>O'rimdagi yo'qotishlar hisobga olinmagan.</i>\n"
HARVEST_TOTAL_LINE = "📦 Dala bo'yicha jami: <b>{total} t</b>\n"
HARVEST_SAVED = "💾 Natija jadvalga saqlandi."
HARVEST_QUEUED = "💾 Natija saqlab qo'yildi, jadval javob berishi bilan avtomatik yoziladi."
