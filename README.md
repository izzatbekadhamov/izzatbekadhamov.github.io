# Izzatbek · HRD — shaxsiy sayt

Statik sayt: kontent `content/` papkasida, dizayn `assets/` va `build.py` dagi shablonlarda. Tashqi kutubxona kerak emas — faqat Python 3.

## Saytni yigʻish va koʻrish

```bash
python3 build.py
```

Natija `dist/` papkasiga yoziladi. Shu papkani istalgan statik hostingga yuklash mumkin.

Lokal koʻrish:

```bash
python3 -m http.server 4321 --directory dist
```

Soʻng brauzerda `http://localhost:4321` ni oching.

### Qoralamalar bilan koʻrish

```bash
python3 build.py --drafts
```

`dist-drafts/` ga yoziladi va `draft: true` boʻlgan keys, maqola va materiallarni ham koʻrsatadi. Bu variantni internetga joylamang.

## Internetga joylash (GitHub Pages)

`main` branchga push qilinganda `.github/workflows/pages.yml` saytni avtomatik yigʻadi va GitHub Pagesʼga joylaydi. Natijani repoʼning **Actions** boʻlimida kuzatish mumkin.

Sayt manzili: https://izzatbekadhamov.github.io/

Yigʻish paytida sayt manzili `SITE_URL` muhit oʻzgaruvchisi orqali beriladi: canonical havola, ulashish rasmi va `sitemap.xml` shu manzil bilan yaratiladi. Agar sayt ichki papkada joylashsa (masalan, `user.github.io/repo/`), papka nomi havolalarga avtomatik qoʻshiladi. Lokal `python3 build.py` domen ildizi uchun yigʻadi.

Keyinchalik shaxsiy domen ulansa: repo **Settings → Pages → Custom domain** boʻlimida domenni kiriting — havolalar avtomatik moslashadi.

## Kontentni yangilash

| Nima | Qayerda |
|---|---|
| Ism, aloqa manzillari, portret, menyu, sahifa sarlavhalari (`meta`) | `content/sayt.json` |
| Bosh sahifa matnlari | `content/bosh-sahifa.json` |
| “Men haqimda” sahifasi | `content/men-haqimda.md` |
| Keyslar | `content/keyslar/*.md` |
| Maqolalar | `content/maqolalar/*.md` |
| Maqola kategoriyalari | `content/kategoriyalar.json` |
| Materiallar | `content/materiallar/*.md` (yuklab olinadigan fayl boʻlsa — `content/fayllar/`) |
| Rasmlar | `content/rasmlar/` |

Har oʻzgarishdan keyin `python3 build.py` ni qayta ishga tushiring.

### Yangi maqola

`content/maqolalar/` da yangi fayl yarating. Fayl nomi manzil boʻladi (`birinchi-maqola.md` → `/maqolalar/birinchi-maqola/`).

```text
---
title: Maqola sarlavhasi
date: 2026-10-15
category: rekruting
summary: Bir-ikki gaplik qisqa mazmun.
draft: false
---

Matn shu yerdan boshlanadi.

## Kichik sarlavha

- roʻyxat bandi
```

`category` qiymatlari: `rekruting`, `onboarding`, `rahbarlik`, `hr-va-biznes`, `saboqlar`.

Oʻqish vaqti matn hajmidan avtomatik hisoblanadi.

### Yangi keys

`content/keyslar/` da fayl yarating (mavjud qoralamalardan nusxa olish qulay). Sozlamalar: `title`, `topic`, `summary`, `order` (tartib raqami), `draft`. Matn beshta `##` boʻlimdan iborat: Vaziyat, Muammo, Qilingan ishlar, Natija, Olingan saboq.

### Yangi material

`content/materiallar/` da fayl yarating. Sozlamalar: `title`, `type`, `audience` (kim uchun), `task` (qaysi vazifani hal qiladi), `summary`, `order`, `file`, `draft`. Har bir material oʻz oʻqish sahifasini oladi. `file` ga `content/fayllar/` dagi fayl nomi yozilsagina “Yuklab olish” tugmasi chiqadi.

### Markdown qisqacha

- `## Sarlavha`, `### Kichik sarlavha`
- `**qalin**`, `*kursiv*`, `[havola](https://...)`
- `- band` yoki `1. band` — roʻyxat
- `> iqtibos`
- `| ustun | ustun |` — jadval (ikkinchi qator `| --- | ---: |`; `---:` raqamlarni oʻngga tekislaydi)
- `---` — ajratuvchi chiziq
- `[[...]]` — toʻldirilishi kerak boʻlgan joy (qoralamada sariq koʻrinadi; eʼlon qilingan sahifada qolsa, `build.py` ogohlantiradi)

## Tuzilma

```text
content/      kontent (matnlar, sozlamalar, rasmlar, fayllar)
assets/       style.css, main.js, favicon.svg
build.py      generator va HTML shablonlar
dist/         tayyor ommaviy sayt (avtomatik yaratiladi)
TOLDIRISH.md  yetishmayotgan maʼlumotlar roʻyxati
```
