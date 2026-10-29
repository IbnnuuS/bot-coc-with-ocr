# CoC Auto Farmer — ADB + Deep Learning OCR Edition

> Bot farming otomatis untuk Clash of Clans di Windows emulator (LDPlayer / BlueStacks / MEmu). Mengombinasikan screen capture ADB berkecepatan tinggi, deteksi kartu dinamis OpenCV Template Matching, pengenalan teks neural network **PaddleOCR v5 (PP-OCR ONNX)** berlatensi ~17 ms, penargetan presisi Air Defense, serta strategi penyerangan taktis berbasis garis (*Line Deployment*) & *Smart Attack*. Dilengkapi GUI modern dark-mode (CustomTkinter) dan bundle executable mandiri (`.exe`).

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green?logo=opencv)
![PaddleOCR](https://img.shields.io/badge/OCR-PaddleOCR%20v5%20(ONNX)-red?logo=onnx)
![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-38bdf8?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows%20%2B%20LDPlayer-lightgrey?logo=windows)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🌟 Fitur Unggulan

| Kategori | Fitur | Penjelasan |
|---|---|---|
| 🖥️ **Antarmuka** | **Modern Dark Dashboard (`gui.py` / `.exe`)** | Antarmuka grafis elegan CustomTkinter: kontrol START/STOP di posisi atas akses cepat, tombol reset default target, live telemetry, switch strategi serangan, dan streaming log real-time tanpa jendela CMD berkedip. |
| 🧠 **Deep Learning** | **Neural Engine PaddleOCR v5 (ONNX)** | Membaca angka loot dan teks status game secara native dalam **~17 ms** menggunakan model `latin_PP-OCRv5_rec_mobile_infer.onnx`. Sangat akurat pada font *Supercell Magic*, tahan bayangan/outline, dan **100% portabel tanpa perlu instalasi Tesseract di Windows**. |
| 🎯 **Filter Looting** | **5 Mode Evaluasi (Default: `GOLD_AND_ELIXIR`)** | Pilihan mode: `GOLD_AND_ELIXIR` (keduanya wajib tembus), `GOLD_OR_ELIXIR`, `GOLD_ONLY`, `ELIXIR_ONLY`, `DE_ONLY`. Nilai acuan default: **999.999 Gold**, **999.999 Elixir**, dan **5.000 Dark Elixir** dengan pembersihan spasi ribuan otomatis. |
| ⚔️ **Penyerangan** | **Smart Attack (Deteksi Storage Dinamis)** | Memindai posisi bangunan Gold Storage, Elixir Storage, dan Dark Elixir Storage lawan (`templates/storages/`) via masked template matching multi-scale dan verifikasi warna inti di 4 kuadran base. Sisi terpadat otomatis diserang (prioritas Dark Elixir **2.5×**). |
| 📏 **Formasi Serang** | **Line Deployment (Rata Sisi Luar)** | Pasukan diturunkan **berbaris rata** di sepanjang perimeter luar (`KIRI_ATAS`, `KANAN_ATAS`, `KIRI_BAWAH`, `KANAN_BAWAH`, atau `FOUR_SIDES`) untuk penetrasi merata, bukan bertumpuk di satu titik pixel. |
| ⚡ **Anti-Air Defeat** | **Pinpoint Air Defense Targeting** | 11 Lightning Spell otomatis dijatuhkan **sebelum pasukan turun** tepat ke lokasi Air Defense musuh Level 7–13 yang terdeteksi via template matching ber-mask transparansi (`templates/ad/`). |
| 🛡️ **Anti-Macet** | **Fail-Proof Troop & Hero Deployment** | Posisi kartu dideteksi secara visual di bar bawah. Jika deteksi terhalang animasi/pet/skin, bot otomatis menggunakan **fallback coordinate slot** anti-skip dengan proteksi anti-double-tap (misal Minion Prince vs King). Seluruh naga, siege, dan hero dijamin **100% turun ke arena**. |
| 👑 **Kemampuan Hero** | **Dual-Stage Hero Abilities** | Jurus/kemampuan aktif seluruh hero yang diturunkan dipicu secara berkala pada jeda **+30 detik** dan **+62 detik** (untuk hero dengan 2x pemakaian) dengan perlindungan pembatalan otomatis jika battle selesai duluan. |
| ⏩ **Akselerasi** | **Auto Speed-Up 4x** | Otomatis mendeteksi tombol kecepatan `1x` hijau di paruh bawah layar saat pertempuran berlangsung dan langsung melakukan tap 2x untuk mempercepat durasi pertempuran ke `4x`. |
| ⏱️ **Efisiensi** | **Auto End Battle (Early Surrender)** | Menyerah lebih awal pasca detik ke-30 jika sisa loot $\le$ 50.000 atau angka perolehan stagnan selama 2 cek berturut-turut untuk menghemat waktu farming. |

---

## 🔄 Alur Kerja Siklus Bot

```text
[ START BOT ]
      │
      ▼
 [ HOME BASE ] ────────► Tekan Tombol "Battle" (Kiri Bawah)
      │
      ▼
 [ MATCHMAKING ] ──────► Tekan "Find a Match"
      │
      ▼
 [ SCOUT BASE ]
      │
      ├──► Baca Angka Loot via PaddleOCR v5 (17 ms)
      │
      ├──► Loot TIDAK CUKUP? ──► Tekan "Next" ──► Ulangi SCOUT
      │
      └──► Loot MEMENUHI TARGET!
                │
                ├──► 1. Analisis Smart Attack (Pilih kuadran storage paling kaya)
                ├──► 2. Cast Lightning Spell (Hancurkan Air Defense musuh)
                ├──► 3. Line Deploy Pasukan Naga (Rata sepanjang garis perimeter)
                ├──► 4. Deploy Siege Machine & Hero di pusat garis
                ├──► 5. Cek & Tap Tombol Percepat (1x -> 4x Speed)
                ├──► 6. Trigger Ulti Hero Bertahap (+30s & +62s)
                └──► 7. Auto End Battle Monitor (Surrender jika loot habis / timeout)
                          │
                          ▼
                    [ RETURN HOME ] ──► Catat rekaman hasil ke loot.csv
```

---

## 📋 Persyaratan Sistem

1. **Sistem Operasi**: Windows 10 atau Windows 11 (64-bit).
2. **Emulator**: LDPlayer 9 / 14 (atau BlueStacks / MEmu):
   - Resolusi layar: **1920 × 1080** (Landscape, 240/320 DPI).
   - Mode Root/ADB: **Aktif** (`127.0.0.1:5554` / `emulator-5554`).
   - Bahasa in-game Clash of Clans: **English** (wajib untuk akurasi pembacaan).
3. **Mesin OCR**:
   - Model neural network sudah terpasang bawaan di folder `models/ocr/`.
   - **Tidak memerlukan instalasi software OCR tambahan (seperti Tesseract) di Windows.**
4. **Python Runtime** (Opsional, hanya jika menjalankan dari source code):
   - Python 3.10+ (disarankan menggunakan Laragon `C:\laragon\bin\python\python-3.10`).

---

## 🚀 Cara Menjalankan

### Cara 1: Menjalankan File Executable (.exe) — *Paling Praktis*
Buka langsung aplikasi executable hasil build portabel:
```text
dist\CoC_Bot\CoC_Bot.exe
```
*Semua aset template gambar, model OCR ONNX, dan runtime GUI sudah dibundel mandiri.*

### Cara 2: Menjalankan GUI via Launcher Script
```bash
run.bat gui.py
# atau langsung:
python gui.py
```

### Cara 3: Mode CLI Tradisional (Terminal)
```bash
python bot.py               # Menjalankan loop automasi penuh via console
python bot.py --state       # Membaca state dan loot layar saat ini (read-only)
python bot.py --calibrate   # Mengambil screenshot dan menggambar bounding box validasi
python bot.py --selftest    # Menjalankan uji diagnosa mandiri tanpa emulator
```

---

## ⚙️ Panduan Pengaturan Dashboard

### 1. Panel Kontrol Utama
- **▶ START BOT**: Memulai loop pencarian dan penyerangan otomatis.
- **⏹ STOP BOT**: Menghentikan proses loop bot dengan aman.
- **🔍 Ambil Snapshot / Kalibrasi**: Mengambil frame emulator dan menandai bounding box deteksi ke `debug/calibrate.png`.

### 2. Target Looting
- **Mode Filter**:
  - `GOLD_AND_ELIXIR` *(Default)*: Gold **DAN** Elixir wajib sama-sama tembus target minimal.
  - `GOLD_OR_ELIXIR`: Cukup salah satu dari Gold atau Elixir tembus target.
  - `GOLD_ONLY`: Hanya mencari Gold melimpah.
  - `ELIXIR_ONLY`: Hanya mencari Elixir melimpah.
  - `DE_ONLY`: Khusus memburu Dark Elixir (minyak hitam).
- **Ambang Batas Nilai**: Masukkan angka minimal (contoh: `999999` Gold/Elixir, `5000` Dark).
- **↺ Reset Default**: Satu klik untuk mengembalikan target ke konfigurasi optimal (`GOLD_AND_ELIXIR`, 999.999 / 5.000).

### 3. Strategi Serangan
- **Model Deploy / Sisi**:
  - `Smart Attack (Auto Cari Storage)`: Memindai posisi penyimpanan musuh dan memilih sisi terdekat dengan simpanan terbanyak.
  - `Rata Kiri Atas`: Garis serbu barat laut `(180, 360)` s/d `(320, 220)`.
  - `Rata Kanan Atas`: Garis serbu timur laut `(1600, 220)` s/d `(1740, 360)`.
  - `Rata Kiri Bawah`: Garis serbu barat daya `(120, 420)` s/d `(130, 620)`.
  - `Rata Kanan Bawah`: Garis serbu tenggara `(1780, 420)` s/d `(1780, 620)`.
  - `Sebar Rata 4 Sisi`: Pasukan dibagi rata mengelilingi 4 sisi base musuh.
- **Auto End Battle**: Menghentikan serangan lebih awal jika loot habis untuk efisiensi waktu.
- **Auto Percepat (Speed Up 4x)**: Mengakselerasi tempo pertandingan game ke 4x secara instan.

---

## 🔍 Kalibrasi & Validasi Visual

Jika ingin memeriksa apakah resolusi dan deteksi bot sesuai dengan emulator kamu, tekan tombol **"🔍 Ambil Snapshot / Kalibrasi"** atau jalankan perintah:
```bash
python bot.py --calibrate
```
Hasil anotasi visual akan tersimpan di `debug/calibrate.png`:
- **Kotak Ungu**: Area pemindaian OCR angka Gold, Elixir, dan Dark Elixir.
- **Kotak Kuning**: Deteksi tombol state navigasi (Battle, Find a Match, Attack).
- **Kotak Hijau**: Kartu pasukan dan hero yang teridentifikasi di bar bawah beserta skor kecocokan.
- **Lingkaran Merah**: Bangunan Air Defense musuh yang ditargetkan untuk dihancurkan oleh spell petir.

---

## 📁 Struktur Direktori Proyek

```text
bot-coc-with-ocr/
├── dist/CoC_Bot/           # Executable mandiri siap pakai
│   └── CoC_Bot.exe
├── models/                 # Model Deep Learning & Neural Network
│   └── ocr/
│       ├── latin_PP-OCRv5_rec_mobile_infer.onnx   # Model pengenal teks PaddleOCR
│       └── ppocrv5_latin_dict.txt                 # Kamus karakter alfabet & angka CoC
├── templates/              # Aset visual OpenCV Template Matching
│   ├── btn_attack.png      # Tombol konfirmasi "Attack!" hijau
│   ├── btn_battle.png      # Tombol "Battle" di Home Screen
│   ├── btn_find.png        # Tombol "Find a Match" di menu matchmaking
│   ├── btn_next.png        # Tombol "Next" lewati base lawan
│   ├── btn_speed_1x.png    # Tombol percepat battle (1x -> 4x)
│   ├── ad/                 # Template transparan Air Defense (Level 7 - 13)
│   ├── storages/           # Template transparan Gold, Elixir, dan Dark Elixir Storage
│   └── units/              # Template kartu pasukan, hero, dan mantra
│       ├── edrag.png
│       ├── wall_wrecker.png
│       ├── minion_prince.png
│       ├── king.png
│       ├── queen.png
│       ├── warden.png
│       ├── rc.png
│       └── lightning.png
├── bot.py                  # Logika utama otomasi, OpenCV Vision & PaddleOCR Engine
├── gui.py                  # Antarmuka Dashboard desktop (CustomTkinter)
├── requirements.txt        # Daftar dependensi Python
├── loot.csv                # Rekap riwayat hasil pertempuran dan loot yang diperoleh
└── run.bat                 # Script launcher cepat via Laragon
```

---

## 🛡️ Disclaimer

Proyek ini dikembangkan semata-mata untuk tujuan riset edukasi di bidang **Computer Vision, Optical Character Recognition, dan Automasi Antarmuka Grafis**. Penggunaan bot automasi pada game online dapat melanggar Ketentuan Layanan (*Terms of Service*) Supercell. Gunakan perangkat lunak ini secara bijak dan atas risiko serta tanggung jawab pribadi sepenuhnya.

## 📄 Lisensi

Didistribusikan di bawah lisensi resmi **MIT License**. Bebas untuk digunakan, dimodifikasi, dan dikembangkan lebih lanjut.
