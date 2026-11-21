# CoC Auto Farmer — ADB + OCR Edition

> Bot farming otomatis Clash of Clans untuk Windows emulator (LDPlayer 9/14, BlueStacks, MEmu) yang dikendalikan lewat **ADB** + **Computer Vision**. Kombinasi screen capture ADB, deteksi state/tombol dengan template matching OpenCV, pembacaan loot dengan **PaddleOCR v5 (PP-OCR ONNX via `cv2.dnn`)** dan fallback Tesseract, penargetan Air Defense, deploy berbaris (*Line Deployment*), serta *Smart Attack* berbasis densitas storage. Dilengkapi GUI dark-mode (CustomTkinter) dan build executable mandiri.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green?logo=opencv)
![OCR](https://img.shields.io/badge/OCR-PaddleOCR%20v5%20(ONNX)-red)
![GUI](https://img.shields.io/badge/GUI-CustomTkinter-38bdf8)
![Platform](https://img.shields.io/badge/Platform-Windows%20%2B%20ADB-lightgrey?logo=windows)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🌟 Fitur

| Kategori | Fitur | Keterangan |
|---|---|---|
| 🖥️ **Antarmuka** | **Dashboard dark-mode (`gui.py`)** | CustomTkinter: START/STOP, snapshot/kalibrasi, mode loot + ambang target, pemilihan sisi deploy, switch Auto End / Auto Percepat / Event MOMMA, telemetry (state, jumlah serang, loot terakhir), dan log real-time. |
| 🧠 **OCR** | **PaddleOCR v5 ONNX** | Model `models/ocr/latin_PP-OCRv5_rec_mobile_infer.onnx` dijalankan dengan `cv2.dnn.readNetFromONNX` (tanpa `onnxruntime`). Kalau model tidak ada, otomatis fallback ke Tesseract (`C:\Program Files\Tesseract-OCR\tesseract.exe`). |
| 🎯 **Filter Loot** | **5 Mode Evaluasi** | `GOLD_AND_ELIXIR` *(default)*, `GOLD_OR_ELIXIR`, `GOLD_ONLY`, `ELIXIR_ONLY`, `DE_ONLY`. Target default: **999.999 Gold**, **999.999 Elixir**, **5.000 Dark**. Angka hasil OCR divalidasi (`MAX_LOOT` 3,5 jt / 50 rb DE) supaya salah baca tidak memicu serangan. |
| ⚔️ **Penyerangan** | **Smart Attack** | Deteksi Gold/Elixir/Dark Storage musuh (`templates/storages/`, masked multi-scale matching + verifikasi warna HSV + NMS), lalu pilih kuadran terpadat. Bobot Dark Elixir **2.5×**. |
| 📏 **Formasi** | **Line Deployment** | Pasukan diturunkan berbaris rata sepanjang garis perimeter (`KIRI_ATAS`, `KANAN_ATAS`, `KIRI_BAWAH`, `KANAN_BAWAH`, atau `FOUR_SIDES`) dengan jitter kecil — bukan menumpuk di satu pixel. |
| ⚡ **Spell** | **Lightning ke Air Defense** | 11 Lightning Spell dijatuhkan **sebelum** pasukan turun, tersebar ke setiap Air Defense terdeteksi (`templates/ad/`, level 7–16 + `ad_hq`). Jika AD tidak terdeteksi, fallback ke 4 titik core base. |
| 🛡️ **Anti-Macet** | **Deteksi kartu + fallback slot** | Kartu unit/hero dibaca dari bar bawah (`templates/units/`). Kalau terhalang animasi/skin, dipakai slot koordinat cadangan dengan proteksi anti-double-tap dan anti-slot-bentrok. Deploy diulang sekali bila battle belum dimulai. |
| 👑 **Hero** | **Ulti hero otomatis** | Kemampuan hero dipicu dengan tap ulang kartu hero pada **+8 detik** setelah deploy (battle sudah 4x, timing ini yang pas). Dibatalkan otomatis kalau battle sudah selesai. |
| ⏩ **Akselerasi** | **Auto Fast Forward** | Tombol `1x` dikenali via template (`btn_speed_1x`) di sisi kanan layar lalu di-tap **sekali per battle** → tempo jadi 4x. Tap kedua mengembalikan ke 1x, karena itu dikunci per battle. |
| ⏱️ **Efisiensi** | **Auto End Battle** | Surrender otomatis setelah detik ke-30 jika sisa Gold+Elixir ≤ 50.000 atau angkanya stagnan 2 cek berturut-turut. Batas keras battle: **180 detik**. |
| 🎉 **Event** | **Mass M.O.M.M.As (mirror)** | Toggle OFF secara default. Saat aktif, pasukan event 25 tap masuk slot ke-2 dan menyerang sisi mirror (Kiri Atas ↔ Kanan Atas, Kiri Bawah ↔ Kanan Bawah). |
| 🔧 **Template** | **Multi-varian** | Satu state bisa punya beberapa template (mis. `btn_battle.png` + `btn_battle_alt1.png`); skor tertinggi yang dipakai. Tambah varian, jangan ganti. |

---

## 🔄 Alur Siklus Bot

```text
[ START ]
   │
   ▼
detect_state()  ── HOME  ──► tap "Battle"
                ├─ MENU  ──► tap "Find a Match"
                ├─ ARMY  ──► tap "Attack!"
                └─ SCOUT ──► baca loot (OCR) ──► log ke loot.csv
                             │
                             ├─ TIDAK CUKUP ──► tap "Next" ──► ulangi
                             │
                             └─ CUKUP
                                  ├─ 1. Smart Attack: pilih sisi terpadat (default SMART)
                                  ├─ 2. Lightning × 11 ke Air Defense
                                  ├─ 3. Line deploy: dragon 10×, balloon 1×
                                  ├─ 4. Siege wall_wrecker 1× + 4 hero (sebar 3 titik garis)
                                  ├─ 5. Auto Fast Forward (1 tap → 4x)
                                  ├─ 6. Ulti hero (+8s)
                                  └─ 7. Auto End Battle (≤50k / stagnan / 180s)
                                        │
                                        ▼
                              layar hasil ──► "Return Home" ──► HOME
```

Susunan pasukan diatur di `Config.ARMY_ORDER` (`dragon`, `balloon`, `wall_wrecker`, `king`, `queen`, `warden`, `rc`; spell `lightning` terpisah), jadi komposisi bisa diubah tanpa menyentuh logika deploy.

---

## 📋 Persyaratan

1. **Windows 10/11 64-bit.**
2. **Emulator** dengan ADB aktif, resolusi **1920×1080 landscape**:
   - Default path ADB: `C:\LDPlayer\LDPlayer14\adb.exe`, serial `emulator-5554` (`Config.ADB`, `Config.SERIAL`).
   - Bot memaksa `wm size 1920x1080` saat start (`Config.FORCE_SIZE`); balikkan dengan `adb shell wm size reset`.
   - Bahasa in-game **English** (akurasi OCR).
3. **Python 3.10+** (kalau jalan dari source):
   ```bash
   pip install -r requirements.txt    # opencv-python, numpy, pytesseract, customtkinter
   ```
   Tesseract opsional — hanya dipakai kalau model ONNX tidak ditemukan.

---

## 🚀 Cara Menjalankan

```bash
# GUI (disarankan)
python gui.py

# CLI
python bot.py             # loop utama penuh
python bot.py --state     # baca state + loot sekali (read-only)
python bot.py --calibrate # screenshot + bounding box → debug/calibrate.png
python bot.py --selftest  # uji vision tanpa emulator
```

Launcher `run.bat` memanggil Laragon Python 3.10 dan meneruskan argumen ke `bot.py`:
```bash
run.bat                   # = python bot.py
run.bat --state
```

Build executable (opsional):
```bash
pyinstaller CoC_Bot.spec  # hasil: dist/CoC_Bot/CoC_Bot.exe
```

---

## ⚙️ Pengaturan Dashboard

**Panel Kontrol**
- **▶ START BOT / ⏹ STOP BOT** — mulai/hentikan loop.
- **🔍 Ambil Snapshot / Kalibrasi** — ambil frame emulator, tulis `debug/calibrate.png`.

**Target Looting**
- Mode: `GOLD_AND_ELIXIR` (default), `GOLD_OR_ELIXIR`, `GOLD_ONLY`, `ELIXIR_ONLY`, `DE_ONLY`.
- Ambang Gold/Elixir/Dark bisa diedit; **↺ Reset Default** → 999999 / 999999 / 5000.

**Strategi Serangan**
- `Smart Attack (Auto Cari Storage)` — default.
- `Rata Kiri Atas` — garis `(364,295) → (717,35)`
- `Rata Kanan Atas` — garis `(1149,36) → (1469,276)`
- `Rata Kiri Bawah (Pantai)` — garis `(187,414) → (201,601)`
- `Rata Kanan Bawah` — garis `(1670,427) → (1694,607)`
- `Sebar Rata 4 Sisi` — tap dirotasi ke 4 sisi.
- Switch: **Auto End Battle**, **Auto Percepat (4x)**, **Event Mass M.O.M.M.As (Mirror)**.

Semua koordinat terukur untuk 1080p; kalau resolusi emulator beda, jalankan `--calibrate` dulu.

---

## 🔍 Kalibrasi & Debug

`python bot.py --calibrate` menulis `debug/calibrate.png`:
- **Ungu** — region OCR loot (Gold/Elixir/Dark).
- **Kuning** — ROI state + skor template (HOME/MENU/ARMY).
- **Hijau** — kartu unit/hero terdeteksi di bar bawah beserta skor.
- **Merah** — Air Defense yang jadi target lightning.

File debug lain di `debug/` (di-*gitignore*): `state.png`, `unknown.png`, `ad_detect.png`, `titik_deploy_v2.png`, `user_drawn_mask.png`, `user_lines_overlay.png`, `last.png` (kalau `SAVE_DEBUG_SHOTS = True`).

---

## 📁 Struktur Proyek

```text
bot-coc-with-ocr/
├── bot.py                  # Config, ADB tap, vision, OCR, loop otomasi
├── gui.py                  # Dashboard CustomTkinter
├── CoC_Bot.spec            # Spec PyInstaller
├── run.bat                 # Launcher (Laragon Python 3.10)
├── requirements.txt
├── loot.csv                # Riwayat baca loot (time, gold, elixir, dark, attacked)
├── models/ocr/
│   ├── latin_PP-OCRv5_rec_mobile_infer.onnx
│   └── ppocrv5_latin_dict.txt
└── templates/
    ├── btn_battle.png, btn_battle_alt1.png, btn_find.png, btn_attack.png, btn_next.png
    ├── btn_speed_1x.png, btn_speed_1x_15.png
    ├── ad/         # ad_hq + ad_lvl7 … ad_lvl16 (RGBA transparan)
    ├── storages/   # gold.png, elixir.png, dark.png (RGBA transparan)
    └── units/      # dragon, balloon, wall_wrecker, king, queen, warden, rc, lightning
```

`debug/`, `build/`, `dist/`, `*.spec`, `*.log`, `__pycache__/` tidak masuk repo (lihat `.gitignore`) — executable di-build lokal.

---

## 🧪 Verifikasi Cepat

```bash
python bot.py --selftest
```
Mengecek: semua template state match di posisinya, 5 mode loot gate, parsing angka loot (`1 320 758` → 1320758, nilai mustahil ditolak), deteksi kartu unit, Smart Attack memilih sisi valid, dan deteksi Air Defense.

---

## 🛡️ Disclaimer

Dibuat untuk tujuan riset edukasi di bidang Computer Vision, OCR, dan automasi GUI. Automasi pada game online bisa melanggar Terms of Service Supercell. Gunakan dengan risiko dan tanggung jawab sendiri.

## 📄 Lisensi

MIT License.
