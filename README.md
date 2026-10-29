# CoC Auto Farmer — ADB + OCR Edition

> Bot farming Clash of Clans otomatis untuk Windows emulator (LDPlayer / BlueStacks / MEmu): screen capture via ADB, deteksi kartu dinamis via OpenCV Template Matching, pembacaan resource via Tesseract OCR, dan penyerangan taktis berbasis garis (Line Deploy) & Smart Attack. Dilengkapi antarmuka grafis modern (CustomTkinter GUI) dan format executable (.exe).

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green?logo=opencv)
![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-38bdf8?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows%20%2B%20LDPlayer-lightgrey?logo=windows)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🌟 Fitur Utama

| Kategori | Fitur | Penjelasan |
|---|---|---|
| 🖥️ **Antarmuka** | **Modern Dark GUI (`gui.py` / `.exe`)** | Dashboard kontrol lengkap: tombol START/STOP di posisi atas akses cepat, tombol reset default target, live telemetry, toggle strategi serangan, dan live streaming log terminal tanpa popup CMD yang mengganggu. |
| 🎯 **Filter Loot** | **5 Mode Evaluasi Fleksibel** | Pilihan mode: `GOLD_AND_ELIXIR` (default), `GOLD_OR_ELIXIR`, `GOLD_ONLY`, `ELIXIR_ONLY`, `DE_ONLY` dengan nilai default `999.999` Gold/Elixir & `5.000` Dark. Dilengkapi pembersihan spasi ribuan (`1 000 000`) dan sanitasi batas atas OCR (`MAX_HOME_LOOT`). |
| ⚔️ **Penyerangan** | **Smart Attack (Auto Cari Storage)** | Memindai densitas dan posisi spesifik gedung Gold Storage, Elixir Storage, dan Dark Elixir Storage lawan (`templates/storages/`) via masked template matching dan verifikasi warna inti di 4 kuadran base, lalu otomatis memilih sudut serangan terbaik (prioritas DE 2.5x). |
| 📏 **Formasi** | **Line Deployment (Rata Sisi)** | Pasukan diturunkan **berbaris rata** di sepanjang garis perimeter luar (`KIRI_ATAS`, `KANAN_ATAS`, `KIRI_BAWAH`, `KANAN_BAWAH`, atau `FOUR_SIDES`), bukan bertumpuk di satu titik pixel. |
| 🛡️ **Failsafe** | **Beach Cleanup Sweep** | Sapu bersih sisa pasukan & Siege Machine otomatis di area pantai aman `(135, 520)`. Menjamin 100% naga, hero, dan wall wrecker turun tuntas meskipun base musuh memiliki *corner buildings* yang melebarkan zona merah. |
| 🃏 **Adaptif** | **Dynamic Card Matching (`templates/units/`)** | Posisi kartu unit di bar pasukan dideteksi secara real-time via template matching portrait bersih 1080p. Mendukung Wall Wrecker dengan peringatan tanda seru (`!`) dan fallback koordinat otomatis. |
| ⚡ **Mantra & Hero** | **Pinpoint Air Defense & Hero Ability** | 11 Lightning Spell otomatis dijatuhkan **sebelum** pasukan ke lokasi Air Defense musuh yang terdeteksi via template matching multi-scale Level 7–13 (`templates/ad/`). Kemampuan hero diaktifkan bertahap pada delay +30 dtk dan +62 dtk. |
| ⏩ **Akselerasi** | **Auto Percepat (Speed Up 4x)** | Otomatis mendeteksi tombol kecepatan `1x` hijau di paruh bawah layar saat pertempuran berlangsung dan langsung melakukan tap 2x untuk mempercepat durasi battle ke `4x`. |
| ⏱️ **Efisiensi** | **Auto End Battle (Early Surrender)** | Menyerah lebih awal pasca detik ke-30 jika sisa loot $\le$ 50.000 atau angka loot stagnan selama 2 cek berturut-turut (mencegah bot bengong menunggu waktu habis). |

---

## 🔄 Alur Kerja Sistem

```
[ START ]
    │
    ▼
[ HOME BASE ] ──► Tap "Battle"
    │
    ▼
[ MATCHMAKING ]
    │
    ▼
[ SCOUT BASE ]
    │
    ├──► Loot tidak cukup? ──► Tap "Next" ──► Ulangi SCOUT
    │
    └──► Loot MEMENUHI TARGET!
              │
              ├──► Analisis Smart Attack (Cari kuadran storage terbanyak)
              ├──► Line Deployment (Sebar naga berbaris rata di sisi terpilih)
              ├──► Deploy Hero & Siege Machine di pusat garis
              ├──► Failsafe Cleanup Sweep (Kuras sisa naga di pantai aman)
              ├──► Sebar 11 Petir ke kuadran core base
              ├──► Ulti Hero bertahap (+30s & +62s)
              └──► Auto End Battle monitor (Loot habis / timeout)
                        │
                        ▼
                  [ RETURN HOME ] ──► Catat riwayat ke loot.csv
```

---

## 📋 Persyaratan Sistem

1. **OS**: Windows 10 atau Windows 11 (64-bit).
2. **Emulator**: LDPlayer 9 / 14 (atau BlueStacks / MEmu):
   - Resolusi layar: **1920 × 1080** (Landscape).
   - Mode ADB: **Aktif** (`127.0.0.1:5554` / `emulator-5554`).
   - Bahasa in-game Clash of Clans: **English** (wajib agar OCR presisi).
3. **Tesseract OCR**:
   - Terpasang di `C:\Program Files\Tesseract-OCR\tesseract.exe`.
4. **Python Runtime** (Jika menjalankan via script):
   - Python 3.10+ (misal Laragon `C:\laragon\bin\python\python-3.10`).

---

## 🚀 Cara Menjalankan

### Cara 1: Menjalankan File Executable (.exe) — Rekomendasi
Cukup buka file executable hasil build:
```
dist\CoC_Bot\CoC_Bot.exe
```
Semua dependensi GUI, OpenCV, dan template aset sudah terintegrasi rapi tanpa perlu terminal console.

### Cara 2: Menjalankan GUI via Python
```bash
python gui.py
# Atau via launcher Laragon:
run.bat gui.py
```

### Cara 3: Mode CLI Tradisional
```bash
python bot.py               # Loop utama CLI
python bot.py --state       # Baca state & resource sekali (read-only)
python bot.py --calibrate   # Simpan visual snapshot debug/calibrate.png
python bot.py --selftest    # Uji validasi vision tanpa device
```

---

## ⚙️ Panduan Pengaturan (GUI Dashboard)

### 1. Target Looting
- **Mode**:
  - `GOLD_OR_ELIXIR`: Cukup salah satu lolos (paling cepat dapat lawan).
  - `GOLD_AND_ELIXIR`: Kedua resource wajib lolos (sangat selektif).
  - `GOLD_ONLY`: Hanya mencari Gold.
  - `ELIXIR_ONLY`: Hanya mencari Elixir.
  - `DE_ONLY`: Khusus mencari Dark Elixir.
- **Min Gold / Elixir / Dark**: Masukkan ambang angka minimal (contoh: `900000`).

### 2. Strategi Serangan & Failsafe
- **Model Deploy / Sisi**:
  - `Smart Attack (Auto Cari Storage)`: Memindai kuadran paling kaya secara dinamis.
  - `Rata Kiri Atas`: Garis serbu pesisir barat laut `(180, 360)` s/d `(320, 220)`.
  - `Rata Kanan Atas`: Garis serbu rumput timur laut `(1600, 220)` s/d `(1740, 360)`.
  - `Rata Kiri Bawah (Pantai)`: Garis serbu pantai barat daya `(120, 420)` s/d `(130, 620)`.
  - `Rata Kanan Bawah`: Garis serbu tenggara `(1780, 420)` s/d `(1780, 620)`.
  - `Sebar Rata 4 Sisi`: Pasukan dibagi rata ke 4 sektor keliling base.
- **Auto End Battle**: Mengakhiri serangan jika loot tersisa $\le$ 50k atau angka stagnan.
- **Auto Percepat**: Mempercepat pertempuran ke 4x begitu tombol 1x terdeteksi.

---

## 🔍 Kalibrasi & Validasi Visual

Gunakan tombol **"🔍 Ambil Snapshot / Kalibrasi"** di GUI atau jalankan `python bot.py --calibrate`. File hasil akan disimpan di `debug/calibrate.png`:

- **Kotak Ungu**: Area baca OCR Gold, Elixir, dan Dark Elixir.
- **Kotak Kuning**: Deteksi tombol state navigasi (Battle, Find, Attack).
- **Kotak Hijau**: Kartu unit pasukan yang terdeteksi di bar bawah beserta skor kecocokannya.

---

## 📁 Struktur Proyek

```
bot-coc-with-ocr/
├── dist/CoC_Bot/           # Executable portable siap pakai
│   └── CoC_Bot.exe
├── templates/              # Aset gambar template matching
│   ├── btn_attack.png      # Tombol Attack hijau
│   ├── btn_battle.png      # Tombol Battle di Home
│   ├── btn_find.png        # Tombol Find a Match
│   ├── btn_next.png        # Tombol Next lawan
│   ├── btn_speed_1x.png    # Tombol percepat battle (1x -> 4x)
│   ├── ad/                 # Template bangunan Air Defense (Lvl 7-13)
│   ├── storages/           # Template bangunan Gold, Elixir & Dark Storage
│   └── units/              # Template kartu pasukan & mantra
│       ├── edrag.png
│       ├── wall_wrecker.png
│       ├── king.png
│       ├── queen.png
│       ├── warden.png
│       ├── rc.png
│       └── lightning.png
├── bot.py                  # Mesin logika automasi, CV & OCR
├── gui.py                  # Antarmuka CustomTkinter Dashboard
├── requirements.txt        # Dependensi Python
├── loot.csv                # Rekap riwayat looting (waktu & perolehan)
└── run.bat                 # Launcher script Laragon
```

---

## 🛡️ Disclaimer

Proyek ini dibuat untuk tujuan edukasi Computer Vision dan automasi antarmuka Python. Penggunaan bot pada game online dapat melanggar Ketentuan Layanan (Terms of Service) penyedia game. Gunakan secara bijak dan dengan risiko sendiri.

## 📄 Lisensi

Didistribusikan di bawah lisensi **MIT**. Bebas digunakan, dimodifikasi, dan dikembangkan kembali.
