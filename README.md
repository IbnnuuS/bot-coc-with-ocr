# CoC Bot — ADB + OCR

> Bot farming Clash of Clans otomatis untuk emulator: screenshot lewat ADB, baca
> loot lewat Tesseract OCR, tap lewat `input touchscreen tap`. Tanpa mod, tanpa
> memory reading, tanpa root.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green?logo=opencv)
![Platform](https://img.shields.io/badge/Platform-Windows%20%2B%20LDPlayer-lightgrey?logo=windows)

---

## Alur kerja

```
HOME --tap Battle--> MENU --tap Find a Match--> ARMY --tap Attack!--> SCOUT
                                                                        |
                          +---------------------------------------------+
                          |
                   loot cukup? --tidak--> tap Next --> SCOUT (base lain)
                          |
                         ya
                          |
              deploy pasukan (6 slot, satu titik)
                          |
              battle jalan? tidak -> deploy ulang 3 dtk
                          |
              11 Lightning Spell ke 4 kuadran core
                          |
              ulti hero: +30 dtk, +62 dtk (cek battle masih jalan)
                          |
              tunggu battle selesai --> HOME
```

`UNKNOWN` (layar hasil battle / transisi matchmaking) butuh **2 frame
berturut-turut** sebelum bot tap "Return Home". Satu frame transisi saja tidak
cukup: tap buta di layar transisi mendarat di bar pasukan dan malah memilih
kartu.

---

## Filter loot

Panel "Available Loot" dibaca OCR dengan format ribuan CoC — `1 000 000`,
`100 000`, `10 000`, `1000`. Spasi di dalam angka digabung otomatis sebelum
di-parse, jadi `1 000 000` tetap terbaca 1000000.

```python
TARGETS = {"Gold": 400_000, "Elixir": 400_000}   # Dark tidak difilter
ANY_TARGET = True    # gold ATAU elixir lolos = serang
```

| Setelan | Perilaku |
|---|---|
| `ANY_TARGET = True` | cukup salah satu lolos → lebih cepat dapat lawan |
| `ANY_TARGET = False` | gold **dan** elixir harus lolos |
| Dark Elixir | selalu diabaikan |

Tidak lolos → tap `Next`, lanjut base berikutnya tanpa balik ke home.

---

## Deploy

Semua pasukan diturunkan ke satu titik di rumput tepi pantai
(`DEPLOY_POINT = (140, 520)`), bukan melingkar, urut sesuai `DEPLOY_ORDER`:

| # | Unit | Tap |
|---|------|-----|
| 1 | Electro Dragon | 10 |
| 2 | Wall Wrecker | 1 |
| 3 | Barbarian King | 1 |
| 4 | Archer Queen | 1 |
| 5 | Grand Warden | 1 |
| 6 | Royal Champion | 1 |

Tap titik deploy diberi jitter ±20/±45 px (`DEPLOY_SPREAD`) supaya unit
menyebar, bukan menumpuk di satu pixel.

Kalau loot sudah lolos, bot **tidak menunggu** countdown "Battle starts in"
selesai — deploy langsung. Kalau ternyata ditolak (CoC belum masuk fase
battle), bot cek `battle_running()` lalu deploy sekali lagi setelah 3 detik.

---

## Petir

11 Lightning Spell dipakai **habis** per serangan: tap slot spell, lalu sebar
bergiliran ke 4 titik kuadran core (`LIGHTNING_SPOTS`), jitter ±15 px, jeda
0.18 dtk.

Deteksi Air Defense otomatis sudah dibuang — `templates/AD_template.png` tidak
pernah match di atas 0.46 (selalu false positive), hasilnya lebih buruk
daripada titik core tetap.

---

## Ulti hero

Tap kartu hero = ability (UI CoC mobile baru tidak punya tombol ability
terpisah). Jadwal dihitung dari akhir deploy:

```python
ABILITY_DELAYS = (30, 62)   # ronde 1 di +30 dtk, ronde 2 di +62 dtk
```

Kalau diklik langsung setelah deploy, hero masih jalan ke base dan ability
terbuang. Tiap ronde diawali cek `battle_running()`: kalau battle keburu
selesai, ulti dihentikan — tidak ada tap nyasar di layar hasil. Ronde 2 untuk
BK/AQ yang ability-nya bisa 2x.

---

## Instalasi

1. **Python 3.10** + dependensi:
   ```bash
   pip install -r requirements.txt
   ```
2. **Tesseract OCR** di `C:\Program Files\Tesseract-OCR\tesseract.exe`
   (path di-set di `bot.py` baris 25).
3. **LDPlayer 14** dengan ADB di `C:\LDPlayer\LDPlayer14\adb.exe`, CoC sudah
   login, resolusi **1920x1080** (bot memaksa `wm size` sendiri saat start).
4. Cek device terdeteksi:
   ```bash
   adb devices    # emulator-5554  device
   ```

---

## Menjalankan

```bash
python bot.py               # loop utama (serang terus sampai dihentikan)
python bot.py --state       # baca state + loot sekali, read-only
python bot.py --calibrate   # simpan debug/calibrate.png beranotasi
python bot.py --selftest    # cek vision tanpa device
```

`--state` dan `--calibrate` tidak menekan tombol apa pun, jadi aman dijalankan
saat bot sedang jalan. Kalau bot dinyalakan ketika battle masih berlangsung
(deteksi `battle_running`), bot menunggu battle itu selesai dulu, tidak tap
`Next` di tengah pertempuran.

Output:

| File | Isi |
|---|---|
| `loot.csv` | `time,gold,elixir,dark,attacked` — satu baris per base dinilai |
| `bot.log` | log kalau dijalankan `python bot.py >> bot.log 2>&1` |
| `debug/calibrate.png` | overlay ROI loot + skor template state |
| `debug/` | frame tambahan kalau `SAVE_DEBUG_SHOTS = True` |

---

## Konfigurasi

Semua di class `Config` (`bot.py`).

| Variabel | Default | Arti |
|---|---|---|
| `TARGETS` | Gold/Elixir 400k | Ambang loot |
| `ANY_TARGET` | `True` | Cukup satu jenis loot |
| `DEPLOY_POINT` | `(140, 520)` | Titik turun pasukan |
| `DEPLOY_ORDER` | 6 slot | Unit + jumlah tap |
| `SPELL_SLOT` | `(1127, 945)` | Slot Lightning Spell |
| `TOTAL_LIGHTNING` | `11` | Petir per serangan |
| `LIGHTNING_SPOTS` | 4 titik core | Sasaran petir |
| `HERO_CARDS` | 4 kartu | Kartu hero (BK, AQ, GW, RC) |
| `ABILITY_DELAYS` | `(30, 62)` | Jadwal ulti hero (detik) |
| `BATTLE_WAIT` | `210` | Batas tunggu battle selesai |
| `POLL` | `0.5` | Jeda antar iterasi loop |
| `OCR_SMAX`, `OCR_VMIN` | `70`, `215` | Threshold preprocessing OCR |

Koordinat tombol (`BTN_BATTLE`, `BTN_FIND`, `BTN_ATTACK`, `BTN_NEXT`,
`BTN_END`, `BTN_RETURN`), slot kartu pasukan, dan ROI loot diukur langsung di
1920x1080. Ganti emulator atau resolusi → ukur ulang, jangan dikira-kira.

---

## Troubleshooting

| Gejala | Penyebab / solusi |
|---|---|
| Pasukan tidak turun sama sekali | Pastikan `DEPLOY_POINT` masih baris sendiri di `Config` — assignment yang ketelan komentar membuat nilainya tidak pernah ada |
| Bot diam di layar scout | Loot tidak lolos target, lihat baris `SKIP base:` di log |
| Petir tidak keluar | `SPELL_SLOT` bergeser setelah update UI — jalankan `--calibrate` |
| Ulti tidak kena | Hero mati sebelum +30 dtk, atau kartu hero bergeser — cek `HERO_CARDS` |
| Angka loot kebaca `None` / 0 | Resolusi bukan 1920x1080, atau panel loot bergeser — cek `debug/calibrate.png` |
| Battle tidak selesai > 210 dtk | `BTN_END` meleset; bot tap End Battle lalu lanjut |
| Tap tidak diterima emulator | `input touchscreen tap` yang dipakai; `sendevent` event4 di emulator ini sering di-drop tanpa error |

---

## Batasan

- Tidak membaca bintang atau persentase damage — hasil serangan tidak
  dievaluasi, langsung cari lawan berikutnya.
- Tidak ada deteksi Air Defense (lihat bagian Petir).
- Layout pasukan diasumsikan tetap: satu baris kartu, `y=945`.
- `debug/`, `bot.log`, `run*.log`, `__pycache__` tidak masuk repo (`.gitignore`).

---

## Disclaimer

> Dibuat untuk keperluan edukasi Computer Vision & otomasi Python.
> Penggunaan bot di game online dapat melanggar Terms of Service Supercell.
> **Gunakan dengan risiko sendiri.**

## Lisensi

MIT — bebas dipakai, dimodifikasi, dan didistribusikan dengan mencantumkan
kredit.
