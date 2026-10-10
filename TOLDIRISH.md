# To‘ldirish ro‘yxati

Sayt ishlaydi, lekin quyidagi shaxsiy ma’lumotlar hali berilmagan. Ular to‘ldirilmaguncha saytda bo‘sh holat yoki vaqtinchalik element ko‘rinadi — hech narsa o‘ylab topilmagan.

## 1. Majburiy (e’lon qilishdan oldin)

- [ ] **Aloqa manzillari** — `content/sayt.json` → `contacts`
  - Telegram: `"url": "https://t.me/..."`
  - [x] LinkedIn — qo‘shildi
  - Email: `"url": "mailto:...@..."`
  - Ixtiyoriy: `"display"` — saytda ko‘rinadigan qisqa matn (masalan, `@username`).
  - Bo‘sh qolgan manzil faol havola bo‘lmaydi, “Manzil keyinroq qo‘shiladi” deb chiqadi.
- [x] **Sayt manzili** — https://izzatbekadhamov.github.io/ (GitHub Pages yig‘ishda avtomatik beriladi).
  Shaxsiy domen (masalan, `meningsaytim.uz`) ulash ixtiyoriy: repo **Settings → Pages → Custom domain**.
- [ ] **“Men haqimda” matnini tekshirish** — `content/men-haqimda.md` va `content/bosh-sahifa.json` → `about`.
  Matn briefdagi ma’lumotlar asosida yozildi; yondashuv va savollar sizning so‘zlaringizga mos kelishini tasdiqlang yoki tahrirlang.

## 2. Tavsiya etiladi

- [x] **Portret surati** — `content/rasmlar/portret.jpg` (800×1000). Almashtirish uchun shu faylni yangisi bilan almashtiring.
- [x] **Ulashish rasmi (Open Graph)** — `content/rasmlar/og.jpg` (1200×630).
  Eslatma: Telegram/LinkedIn rasmni ko‘rsatishi uchun `site_url` ham to‘ldirilgan bo‘lishi kerak (rasm manzili to‘liq URL bo‘lishi shart).

## 3. Kontent (tayyor bo‘lishi bilan)

- [ ] **Keyslar** — `content/keyslar/` dagi 3 ta qoralama:
  - Rekruting jarayonini tizimlashtirish
  - Onboarding jarayonini shakllantirish
  - Filial rahbarlari kompetensiya modelini ishlab chiqish

  `[[...]]` joylarini haqiqiy ma’lumot bilan almashtiring, faqat tasdiqlangan natijalarni yozing, so‘ng `draft: false` qiling.
- [ ] **Maqolalar** — `content/maqolalar/maqola-namunasi.md` ni nusxalab, birinchi maqolani yozing.
- [ ] **Materiallar** — faylni `content/fayllar/` ga qo‘ying, `content/materiallar.json` da `"file"` ga nomini yozing va `"draft": false` qiling.

## 4. Joylashtirish

- [ ] Hosting tanlash (masalan, Netlify, Cloudflare Pages, GitHub Pages yoki o‘z serveringiz) — `dist/` papkasini yuklash kifoya.
- [ ] Domenni hostingga ulash.
