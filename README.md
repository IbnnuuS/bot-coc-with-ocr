# 🤖 Clash of Clans Farming Bot (Computer Vision)

> Bot otomatisasi farming Clash of Clans berbasis **Computer Vision** — tanpa ADB, tanpa root, bekerja di emulator apa pun.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green?logo=opencv)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📌 Fitur Utama

| Fitur | Keterangan |
|---|---|
| 🔍 **OCR Resource** | Membaca Gold, Elixir, Dark Elixir secara real-time via Tesseract |
| ⏭️ **Auto Next** | Klik tombol Next otomatis via template matching + fallback deteksi warna oranye |
| 🎯 **Filter Loot** | Serang kalau Gold **atau** Elixir ≥ `Config.TARGETS` (default 400k); Dark diabaikan |
| ⚡ **Spell Petir Otomatis** | 11 Lightning Spell disebar ke `Config.LIGHTNING_SPOTS` (kuadran core base) |
| 🦸 **Ulti Hero** | Kartu hero ditap ulang +30 s & +62 s setelah deploy (ability 2x untuk BK/AQ) |
| 🐉 **Deploy 1 Arah** | Semua pasukan diturunkan dari satu titik/sisi (`Config.DEPLOY_POINT`), langsung setelah base dinilai |
| 🏠 **Post-Battle Handler** | Otomatis kembali ke layar pencarian setelah battle selesai |
| 🖥️ **Multi-Monitor** | Mendukung emulator di monitor utama maupun monitor kedua |
| 🔧 **Mode Kalibrasi** | Jalankan `--calibrate` untuk menghasilkan overlay visual semua koordinat |

---

## ⚙️ Teknologi

- **[OpenCV](https://opencv.org/)** — Template matching tombol & deteksi Air Defense
- **[Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)** — Membaca angka Gold/Elixir/Dark dari layar
- **[mss](https://python-mss.readthedocs.io/)** — Screen capture ultra-ringan (multi-monitor)
- **[PyAutoGUI](https://pyautogui.readthedocs.io/)** — Klik & kontrol mouse otomatis
- **Tanpa ADB** — Agnostik terhadap jenis emulator (LDPlayer, BlueStacks, MuMu, dll.)

---

## 🚀 Instalasi

### 1. Clone Repository

```bash
git clone https://github.com/username/bot_coc.git
cd bot_coc
```

### 2. Install Tesseract OCR

Download dan install dari:
👉 https://github.com/UB-Mannheim/tesseract/wiki

Pastikan path instalasi sesuai dengan yang ada di `bot.py`:
```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### 3. Install Dependensi Python

```bash
pip install -r requirements.txt
```

**Isi `requirements.txt`:**
```
opencv-python
numpy
mss
pytesseract
pyautogui
```

---

## 🗂️ Struktur Project

```
bot_coc/
├── bot.py                  # File utama bot
├── requirements.txt        # Dependensi Python
├── README.md
└── templates/
    ├── next_btn.png        # Template tombol Next (wajib ada)
    ├── attack_btn.png      # Template tombol Attack (opsional)
    └── AD_template.png     # Template Air Defense untuk deteksi otomatis
```

---

## 🖼️ Menyiapkan Template

Template adalah crop kecil gambar UI yang digunakan untuk pencocokan (`matchTemplate`).

| File | Cara Membuat |
|---|---|
| `next_btn.png` | Screenshot tombol **Next** di layar pencarian lawan, crop rapat |
| `attack_btn.png` | Screenshot tombol **Attack/Find Match** |
| `AD_template.png` | Screenshot bangunan **Air Defense** milik musuh, crop rapat tanpa background |

> ⚠️ Simpan semua file template ke dalam folder `templates/`

---

## ⚡ Cara Pakai

### Mode Kalibrasi (jalankan dulu sebelum bot)

```bash
python bot.py --calibrate
```

Akan menghasilkan dua file:
- `calibrate_full.png` — Screenshot penuh area game
- `calibrate_overlay.png` — Visualisasi semua koordinat yang dikonfigurasi (region OCR, titik serangan, slot pasukan, Air Defense)

Buka `calibrate_overlay.png` dan sesuaikan koordinat di bagian `Config` pada `bot.py`.

### Jalankan Bot

```bash
python bot.py
```

Bot akan otomatis:
1. Scan loot base musuh via OCR
2. Jika loot belum cukup → klik Next
3. Jika loot mencukupi target → mulai serang:
   - **Fase 1:** Deteksi Air Defense → jatuhkan Spell Petir
   - **Fase 2:** Deploy semua pasukan dan hero dari satu sisi
4. Tunggu battle selesai (180 detik)
5. Tekan ESC untuk kembali ke layar pencarian
6. Ulangi dari awal

---

## 🛠️ Konfigurasi

Semua pengaturan ada di class `Config` di dalam `bot.py`.

### Target Loot

```python
TARGET_GOLD   = 500000   # Minimum Gold
TARGET_ELIXIR = 500000   # Minimum Elixir
TARGET_DARK   = 5000     # Minimum Dark Elixir
```

### Monitor & Emulator

```python
MONITOR_INDEX    = 1    # 1 = monitor utama, 2 = monitor kedua
EMULATOR_OFFSET_X = 0  # Jika emulator tidak fullscreen, isi offset X
EMULATOR_OFFSET_Y = 0  # Offset Y
GAME_WIDTH  = 1850      # Lebar area game
GAME_HEIGHT = 1020      # Tinggi area game
```

### Slot Pasukan

```python
SLOT_NAMES = [
    "Naga Petir",     # Slot 0
    "Naga Api",       # Slot 1
    "Wall Wrecker",   # Slot 2
    "Barbarian King", # Slot 3
    "Archer Queen",   # Slot 4
    "Grand Warden",   # Slot 5
    "Royal Champion", # Slot 6
    "Spell Petir",    # Slot 7
]
```

### Jumlah Deploy Per Slot

```python
TROOP_DEPLOY_COUNT = {
    0: 8,   # Naga Petir  → 8 titik
    1: 8,   # Naga Api    → 8 titik
    2: 1,   # Wall Wrecker → 1 titik (siege machine)
    3: 1,   # Hero         → 1 titik
    ...
}
```

### Titik Serangan (1 Arah)

```python
ATTACK_X = 200   # Koordinat X titik deploy (sisi kiri)
ATTACK_Y = 500   # Koordinat Y titik deploy (tengah vertikal)
ATTACK_SPREAD_X = 30   # Spread acak X agar terlihat natural
ATTACK_SPREAD_Y = 80   # Spread acak Y
```

### Air Defense (Spell Petir)

```python
LIGHTNING_PER_AIR_DEF = 3   # Jumlah Spell Petir per Air Defense
MAX_AIR_DEFENSES      = 4   # Maks AD yang dicari (TH12 = 4)
AD_MATCH_THRESHOLD    = 0.70  # Sensitivitas deteksi (turunkan jika sering gagal)
```

Bot akan **otomatis mendeteksi** posisi Air Defense menggunakan `templates/AD_template.png`. Jika gagal, akan fallback ke koordinat di `AIR_DEFENSE_COORDS`.

---

## 🔍 File Debug

Bot otomatis menyimpan gambar debug untuk membantu troubleshooting:

| File | Isi |
|---|---|
| `debug_Gold_thresh.png` | Hasil preprocessing OCR Gold |
| `debug_Elixir_thresh.png` | Hasil preprocessing OCR Elixir |
| `debug_Dark_thresh.png` | Hasil preprocessing OCR Dark Elixir |
| `debug_ad_detect.png` | Deteksi Air Defense — kotak merah di setiap AD yang ditemukan |
| `debug_next_mask.png` | Mask warna oranye (fallback deteksi tombol Next) |
| `calibrate_overlay.png` | Overlay semua koordinat aktif |

---

## 🧩 Alur Kerja Bot

```
START
  │
  ▼
Scan Resource (OCR Gold / Elixir / Dark)
  │
  ├─ [Tidak Memenuhi Target] ──► Klik Next ──► Tunggu 5s ──► Kembali Scan
  │
  └─ [Memenuhi Target]
        │
        ▼
     FASE 1: Deploy Spell Petir ke Air Defense
        │  └── Deteksi AD via AD_template.png
        │  └── 3x Spell per AD
        │
        ▼
     FASE 2: Deploy Pasukan & Hero dari 1 Titik
        │  └── Naga Petir (8x)
        │  └── Naga Api (8x)
        │  └── Wall Wrecker (1x)
        │  └── Hero × 4 (1x each)
        │
        ▼
     Tunggu Battle Selesai (180 detik)
        │
        ▼
     Tekan ESC → Kembali ke Home
        │
        ▼
     Kembali Scan (loop)
```

---

## ⚠️ Disclaimer

> Bot ini dibuat untuk keperluan **edukasi dan pembelajaran** Computer Vision & Python Automation.
> Penggunaan bot di game online dapat melanggar Terms of Service (ToS) dari Supercell.
> **Gunakan dengan risiko sendiri.** Developer tidak bertanggung jawab atas akun yang diblokir.

---

## 📄 Lisensi

Proyek ini menggunakan lisensi **MIT**. Bebas digunakan, dimodifikasi, dan didistribusikan dengan tetap mencantumkan kredit.

---

*Built with ❤️ using Python + OpenCV + Tesseract*
