"""CoC bot — ADB + OCR edition (UI CoC 2026, LDPlayer 1920x1080).

Tap dikirim lewat `input touchscreen tap` (terbukti diterima CoC).
Filter: Gold >= 900k ATAU Elixir >= 900k (Config.ANY_TARGET).
Loot cocok -> deploy 6 unit + 11 petir ke core + ulti hero (+30s, +62s).

  python bot.py --state       # baca state + loot sekali (read-only)
  python bot.py --calibrate   # simpan debug/calibrate.png beranotasi
  python bot.py --selftest    # cek vision tanpa device
  python bot.py               # loop utama (log ke loot.csv)
"""

import csv
import logging
import os
import re
import subprocess
import sys
import time

import cv2
import numpy as np
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if getattr(sys, "frozen", False):
    HERE = os.path.dirname(sys.executable)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))


def asset_path(*paths):
    """Cari path di direktori kerja atau bundle PyInstaller (_MEIPASS / _internal)."""
    p = os.path.join(HERE, *paths)
    if os.path.exists(p):
        return p
    p_internal = os.path.join(HERE, "_internal", *paths)
    if os.path.exists(p_internal):
        return p_internal
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        mp = os.path.join(meipass, *paths)
        if os.path.exists(mp):
            return mp
    return p


class Config:
    ADB = r"C:\LDPlayer\LDPlayer14\adb.exe"
    SERIAL = "emulator-5554"
    FORCE_SIZE = "1920x1080"     # `adb shell wm size reset` untuk balikin
    W, H = 1920, 1080

    OUT_DIR = os.path.join(HERE, "debug")
    CSV = os.path.join(HERE, "loot.csv")

    # --- loot saat scout: panel kiri-atas "Available Loot" ---
    # x1=98 melewati icon koin/elixir, x2=295 memuat angka hingga 10 000 000 (3 angka berspasi)
    REGION_LOOT = {
        "Gold":   (100, 128, 330, 178),
        "Elixir": (100, 190, 330, 240),
        "Dark":   (100, 250, 330, 300),
    }
    # bar loot sendiri (home): kanan-atas
    REGION_HOME = {
        "Gold":   (1560,  28, 1836,  76),
        "Elixir": (1560, 110, 1836, 154),
        "Dark":   (1560, 185, 1836, 228),
    }
    OCR_SMAX, OCR_VMIN = 70, 215
    # --- Filter Loot (COCotz: GOLD_OR_ELIXIR, GOLD_AND_ELIXIR, GOLD_ONLY, ELIXIR_ONLY, DE_ONLY) ---
    LOOT_MODE: str = "GOLD_OR_ELIXIR"
    TARGETS = {"Gold": 999_999, "Elixir": 999_999, "Dark": 5_000}
    MAX_LOOT = {"Gold": 3_500_000, "Elixir": 3_500_000, "Dark": 50_000}
    ANY_TARGET = True            # backward-compatibility jika LOOT_MODE tidak diset

    # --- Auto End Battle ---
    MAX_BATTLE_TIME = 180            # max durasi battle (detik) dari awal deploy
    END_IF_LOOT_EMPTY: bool = True   # akhiri lebih awal jika loot habis / stagnan
    LOOT_EMPTY_THRESHOLD = 50_000    # total sisa Gold+Elixir di bawah ini dianggap habis
    STAGNANT_CHECKS = 2              # jumlah cek berturut-turut tanpa perubahan loot
    BTN_SURRENDER_CONFIRM = (1090, 670)  # tombol Okay hijau konfirmasi surrender

    # --- Auto Collector di Home Base ---
    AUTO_COLLECT: bool = True        # klaim gelembung koin/elixir di home base
    COLLECT_EVERY_N = (1, 3)         # klaim tiap 1-3 serangan

    # --- Auto Stop & Protection ---
    AUTO_STOP_ENABLED: bool = False
    AUTO_STOP_MINUTES: int = 0       # 0 = nonaktif (menit durasi kerja)
    STOP_GOLD_CAP: int = 0           # 0 = nonaktif (cap storage base sendiri)
    STOP_ELIXIR_CAP: int = 0         # 0 = nonaktif

    # --- Upgrade Wall Otomatis ---
    UPGRADE_WALL_MODE: str = "OFF"   # "OFF", "1X_PER_LOOP", "ALWAYS_CHECK_LIMIT"
    WALL_GOLD_LIMIT: int = 2_000_000 # Simpan minimal Gold ini di storage
    WALL_ELIXIR_LIMIT: int = 2_000_000 # Simpan minimal Elixir ini
    WALL_TAP_COORD: tuple = (1070, 675) # Titik segmen wall di base
    WALL_UPGRADE_BTN: tuple = (1040, 960) # Tombol Upgrade wall di bar bawah
    WALL_GOLD_BTN: tuple = (900, 810)     # Tombol opsi bayar Gold
    WALL_ELIXIR_BTN: tuple = (1020, 810)  # Tombol opsi bayar Elixir
    WALL_DESELECT_PT: tuple = (200, 150)  # Rumput luar base aman (atas-kiri) deselect

    # --- Auto Reconnect & Pop-up Dismiss ---
    AUTO_RECONNECT: bool = True
    BTN_POPUP_OKAY: tuple = (960, 670) # Tombol reload / okay di dialog tengah
    TPL_CLOSE_X: str = asset_path("templates", "btn_close_x.png")

    # --- template state (1080p) ---
    TPL = {
        "HOME":  (asset_path("templates", "btn_battle.png"), (20, 880, 225, 1064)),
        "MENU":  (asset_path("templates", "btn_find.png"),   (95, 710, 565, 890)),
        "ARMY":  (asset_path("templates", "btn_attack.png"), (1500, 915, 1890, 1010)),
    }
    TPL_THRESHOLD = 0.80

    # --- koordinat tetap (1080p, terukur) ---
    # slot pasukan (pusat kartu, bar bawah; terukur live)
    BTN_BATTLE   = (122, 972)    # tombol "Battle" di home
    BTN_FIND     = (330, 790)    # "Find a Match"
    BTN_ATTACK   = (1696, 964)   # "Attack!" hijau (ARMY panel)
    BTN_NEXT     = (1750, 775)   # Next: pusat tombol terukur (template btn_next center 1749,769)
    BTN_END      = (137, 800)    # "End Battle" merah: pusat blob terukur (28..247, 774..842)
    BTN_RETURN   = (961, 932)    # "Return Home" di layar hasil
    AUTO_SPEED_UP: bool = True
    BTN_SPEED_TPL = asset_path("templates", "btn_speed_1x.png")

    TAP_DELAY_HOME    = 0.8
    TAP_DELAY_MENU    = 1.0
    TAP_DELAY_ARMY    = 1.2
    TAP_DELAY_NEXT    = 1.0
    TAP_DELAY_UNKNOWN = 1.0

    # --- Susunan Pasukan Dinamis (Template Matching bar y=945..980) ---
    UNIT_TPL_DIR = asset_path("templates", "units")
    UNIT_THRESHOLD = 0.65
    AD_TPL_DIR = asset_path("templates", "ad")
    AD_THRESHOLD = 0.80
    STORAGE_TPL_DIR = asset_path("templates", "storages")
    STORAGE_THRESHOLD = 0.84
    # Urutan deploy: (nama_unit, jumlah_tap, jenis)
    # jenis: "troop", "siege", "hero", "spell"
    ARMY_ORDER = [
        ("edrag", 10, "troop"),
        ("wall_wrecker", 1, "siege"),
        ("minion_prince", 1, "hero"),
        ("king", 1, "hero"),
        ("queen", 1, "hero"),
        ("warden", 1, "hero"),
        ("rc", 1, "hero"),
    ]
    SPELL_UNIT = "lightning"
    TOTAL_LIGHTNING = 11
    # Koordinat cadangan jika template belum dicrop / tidak match
    FALLBACK_SLOTS = {
        "edrag": (206, 980),
        "wall_wrecker": (378, 980),
        "minion_prince": (529, 980),
        "king": (529, 980),
        "queen": (674, 980),
        "warden": (820, 980),
        "rc": (958, 980),
        "lightning": (968, 980),
    }
    HERO_CARDS = [(529, 980), (674, 980), (820, 980), (958, 980)]   # fallback hero cards
    ABILITY_DELAYS = (30, 62)       # detik setelah deploy; ronde 2 utk BK/AQ (2x pakai)
    # kuadran core base (base selalu kira-kira di tengah layar saat scout)
    LIGHTNING_SPOTS = [(780, 390), (1090, 390), (780, 650), (1090, 650)]

    # --- Model Penyerangan Rata Sisi & Smart Attack ---
    ATTACK_STRATEGY: str = "SMART"  # "SMART", "KIRI_ATAS", "KANAN_ATAS", "KIRI_BAWAH", "KANAN_BAWAH", "FOUR_SIDES"
    ATTACK_LINES = {
        "KIRI_ATAS":   ((180, 360), (320, 220)),   # Pesisir barat laut luar
        "KANAN_ATAS":  ((1600, 220), (1740, 360)), # Rumput timur laut luar
        "KIRI_BAWAH":  ((120, 420), (130, 620)),   # Pantai berbatu barat daya (100% legal)
        "KANAN_BAWAH": ((1780, 420), (1780, 620)), # Tepi tenggara luar
    }
    SAFE_BEACH_DROP = (135, 520)    # Titik pantai 100% aman untuk kuras sisa pasukan
    DEPLOY_POINT = (140, 520)       # fallback titik pantai
    DEPLOY_SPREAD = (15, 25)
    DEPLOY_MODE: str = "SINGLE"     # backward-compatibility
    DEPLOY_SPOTS = [
        (160, 520),   # Sisi Kiri (Pantai)
        (550, 180),   # Sisi Atas-Kiri
        (1350, 180),  # Sisi Atas-Kanan
        (1650, 480),  # Sisi Kanan
    ]

    # deteksi tombol End Battle: blob merah kiri-bawah (UI baru tidak punya Next)
    END_ROI = (0, 740, 350, 880)

    POLL = 0.5
    BATTLE_WAIT = 210            # max detik tunggu battle selesai (3 menit + margin)
    SAVE_DEBUG_SHOTS = False


class Adb:
    def __init__(self, cfg=Config):
        self.cfg = cfg
        self._lock_size()

    def run(self, *args, timeout=25):
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.run([self.cfg.ADB, "-s", self.cfg.SERIAL, *args],
                              capture_output=True, timeout=timeout,
                              creationflags=flags, startupinfo=startupinfo)

    def shell(self, cmd, timeout=25):
        return self.run("shell", cmd, timeout=timeout).stdout.decode("utf-8", "replace")

    def _lock_size(self):
        if self.cfg.FORCE_SIZE and self.cfg.FORCE_SIZE not in self.shell("wm size"):
            self.shell(f"wm size {self.cfg.FORCE_SIZE}")
            time.sleep(2)
            logging.info("resolusi -> %s", self.cfg.FORCE_SIZE)

    def shot(self):
        for _ in range(3):
            try:
                r = self.run("exec-out", "screencap -p")
                img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    return img
            except Exception as e:
                logging.warning("screenshot gagal: %s", e)
            time.sleep(0.5)
        return None

    def tap(self, gx, gy):
        """Tap via InputManager (terbukti diterima CoC di LDPlayer)."""
        self.shell(f"input touchscreen tap {int(gx)} {int(gy)}")


# ============================================================
#  VISION
# ============================================================
_tpl_cache = {}


def _tpl(path):
    if path not in _tpl_cache:
        _tpl_cache[path] = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return _tpl_cache[path]


def match_score(img, tpl_path, roi=None):
    tpl = _tpl(tpl_path)
    if tpl is None:
        return 0.0
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if roi:
        x1, y1, x2, y2 = roi
        g = g[y1:y2, x1:x2]
    if g.shape[0] < tpl.shape[0] or g.shape[1] < tpl.shape[1]:
        return 0.0
    return float(cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED).max())


def ocr_number(img, roi, smax=Config.OCR_SMAX, vmin=Config.OCR_VMIN):
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 1] < smax) & (hsv[:, :, 2] > vmin)).astype(np.uint8) * 255
    bw = cv2.resize(m, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    txt = pytesseract.image_to_string(
        bw, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789")
    digits = re.sub(r"\D", "", txt)
    return int(digits) if digits else None


def _parse_loot_text(raw, max_val=3_500_000):
    """Parse format ribuan CoC ('1 320 758', '800 000', '1000').

    Buang digit artefak tepi icon di grup pertama (mis. '8995 740' -> '995 740')
    dan tolak nilai di atas max_val.
    """
    groups = re.findall(r"\d+", raw or "")
    if len(groups) > 1 and len(groups[0]) > 3:
        groups[0] = groups[0][-3:]
    if not groups or any(len(g) != 3 for g in groups[1:]):
        return None
    val = int("".join(groups))
    return val if val <= max_val else None


def read_loot_scout(img):
    out = {}
    for k, roi in Config.REGION_LOOT.items():
        x1, y1, x2, y2 = roi
        gray = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        up = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
        th = cv2.threshold(up, 175, 255, cv2.THRESH_BINARY)[1]
        raw = pytesseract.image_to_string(
            th, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789 "
        ).strip()
        out[k] = _parse_loot_text(raw, Config.MAX_LOOT[k])
    return out


MAX_HOME_LOOT = {"Gold": 25_000_000, "Elixir": 25_000_000, "Dark": 500_000}


def read_loot_home(img):
    out = {}
    for k, roi in Config.REGION_HOME.items():
        x1, y1, x2, y2 = roi
        crop = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        up = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
        th = cv2.threshold(up, 170, 255, cv2.THRESH_BINARY)[1]
        raw = pytesseract.image_to_string(
            th, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789 "
        ).strip()
        max_val = MAX_HOME_LOOT.get(k, 25_000_000)
        parsed = _parse_loot_text(raw, max_val)
        if parsed is None:
            digits = re.sub(r"\D", "", raw)
            if digits and int(digits) <= max_val:
                parsed = int(digits)
        out[k] = parsed
    return out


def end_button_visible(img):
    """True kalau blob merah End Battle terlihat (kiri-bawah)."""
    x1, y1, x2, y2 = Config.END_ROI
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, np.array([0, 150, 140], np.uint8), np.array([10, 255, 255], np.uint8))
    m2 = cv2.inRange(hsv, np.array([165, 150, 140], np.uint8), np.array([180, 255, 255], np.uint8))
    m = cv2.bitwise_or(m1, m2)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return any(cv2.contourArea(c) > 5000 for c in cnts)


def top_text(img):
    """OCR teks countdown area atas (putih saat prep, merah saat battle)."""
    crop = img[0:110, 300:1600]
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    bw = cv2.threshold(cv2.resize(g, None, fx=2, fy=2), 160, 255, cv2.THRESH_BINARY)[1]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    red = cv2.inRange(hsv, np.array([0, 120, 90], np.uint8), np.array([12, 255, 255], np.uint8))
    red |= cv2.inRange(hsv, np.array([168, 120, 90], np.uint8), np.array([180, 255, 255], np.uint8))
    red = cv2.resize(red, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    out = []
    for m in (bw, red):
        out.append(pytesseract.image_to_string(m, config="--oem 3 --psm 11").lower())
    return " ".join(out)


def battle_running(img):
    """True kalau countdown 'Battle ends in' tampil (sudah di fase battle)."""
    return "ends" in top_text(img)


def detect_state(img):
    for state, (path, roi) in Config.TPL.items():
        if match_score(img, path, roi) >= Config.TPL_THRESHOLD:
            return state
    if end_button_visible(img):
        return "SCOUT"          # End Battle terlihat = sedang scouting/base musuh
    return "UNKNOWN"


def find_collector_bubbles(img):
    """Deteksi gelembung koin Gold & tetesan Elixir di desa utama."""
    village = img[130:920, 100:1820]
    hsv = cv2.cvtColor(village, cv2.COLOR_BGR2HSV)
    m_gold = cv2.inRange(hsv, np.array([18, 150, 180]), np.array([32, 255, 255]))
    m_elixir = cv2.inRange(hsv, np.array([135, 120, 120]), np.array([165, 255, 255]))

    points = []
    for mask, name in [(m_gold, "gold"), (m_elixir, "elixir")]:
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            area = cv2.contourArea(c)
            if 300 < area < 1500:
                x, y, w, h = cv2.boundingRect(c)
                if 0.6 < w / h < 1.6 and 20 <= w <= 50 and 20 <= h <= 50:
                    points.append((name, x + w // 2 + 100, y + h // 2 + 130))
    return points


def loot_enough(loot):
    """Filter base lawan sesuai Config.LOOT_MODE (atau fallback Config.ANY_TARGET)."""
    g = loot.get("Gold") or 0
    e = loot.get("Elixir") or 0
    d = loot.get("Dark") or 0
    tg = Config.TARGETS.get("Gold", 0)
    te = Config.TARGETS.get("Elixir", 0)
    td = Config.TARGETS.get("Dark", 0)

    mode = getattr(Config, "LOOT_MODE", None)
    if not mode:
        return (g >= tg or e >= te) if getattr(Config, "ANY_TARGET", True) else (g >= tg and e >= te)

    mode = mode.upper()
    if mode == "GOLD_ONLY":
        return g >= tg
    if mode == "ELIXIR_ONLY":
        return e >= te
    if mode == "DE_ONLY":
        return d >= td
    if mode == "GOLD_AND_ELIXIR":
        return g >= tg and e >= te
    # default / "GOLD_OR_ELIXIR"
    return g >= tg or e >= te


def detect_army_cards(img, tpl_dir=Config.UNIT_TPL_DIR, thresh=Config.UNIT_THRESHOLD):
    """Deteksi posisi kartu unit di bar pasukan (y=850..1075, x=50..1870).
    Return dict: {name: (cx, cy, score)}."""
    if not os.path.isdir(tpl_dir):
        return {}
    bar = img[850:1075, 50:1870]
    gray = cv2.cvtColor(bar, cv2.COLOR_BGR2GRAY)
    detected = {}

    import glob
    for p in glob.glob(os.path.join(tpl_dir, "*.png")):
        name = os.path.splitext(os.path.basename(p))[0]
        tpl = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if tpl is None or gray.shape[0] < tpl.shape[0] or gray.shape[1] < tpl.shape[1]:
            continue

        scales = [1.0] if tpl.shape[0] < 100 else [1.0, 0.85, 0.75]
        best_v, best_l, best_sz = 0.0, (0, 0), tpl.shape
        for s in scales:
            if s == 1.0:
                r_tpl = tpl
            else:
                w = int(tpl.shape[1] * s)
                h = int(tpl.shape[0] * s)
                r_tpl = cv2.resize(tpl, (w, h), interpolation=cv2.INTER_AREA)
            if r_tpl.shape[0] >= gray.shape[0] or r_tpl.shape[1] >= gray.shape[1]:
                continue
            res = cv2.matchTemplate(gray, r_tpl, cv2.TM_CCOEFF_NORMED)
            _, max_v, _, max_l = cv2.minMaxLoc(res)
            if max_v > best_v:
                best_v = float(max_v)
                best_l = max_l
                best_sz = r_tpl.shape

        if best_v >= thresh:
            cx = int(best_l[0] + 50 + best_sz[1] // 2)
            cy = int(best_l[1] + 850 + best_sz[0] // 2)
            detected[name] = (cx, cy, best_v)
    return detected


def find_air_defenses(img, tpl_dir=Config.AD_TPL_DIR, threshold=Config.AD_THRESHOLD):
    """Deteksi bangunan Air Defense lawan via multi-scale masked template matching (Level 7-13)."""
    if not os.path.isdir(tpl_dir):
        return []
    x_off, y_off = 280, 130
    roi = img[y_off:850, x_off:1640]
    hits = []

    import glob
    for p in glob.glob(os.path.join(tpl_dir, "*.png")):
        tpl_bgra = cv2.imread(p, cv2.IMREAD_UNCHANGED)
        if tpl_bgra is None or tpl_bgra.shape[2] < 4:
            continue
        t_bgr = tpl_bgra[:, :, :3]
        t_mask = tpl_bgra[:, :, 3]

        for s in [0.45, 0.50, 0.55, 0.60]:
            resized_bgr = cv2.resize(t_bgr, None, fx=s, fy=s)
            resized_mask = cv2.resize(t_mask, None, fx=s, fy=s)
            if resized_bgr.shape[0] >= roi.shape[0] or resized_bgr.shape[1] >= roi.shape[1]:
                continue
            res = cv2.matchTemplate(roi, resized_bgr, cv2.TM_CCORR_NORMED, mask=resized_mask)
            ys, xs = np.where(res >= threshold)
            for y, x in zip(ys, xs):
                score = float(res[y, x])
                cx = int(x + x_off + resized_bgr.shape[1] // 2)
                cy = int(y + y_off + resized_bgr.shape[0] // 2)
                hits.append((score, cx, cy))

    hits.sort(reverse=True)
    kept = []
    for sc, cx, cy in hits:
        if all(abs(cx - a) > 60 or abs(cy - b) > 60 for _, a, b in kept):
            kept.append((sc, cx, cy))
            if len(kept) >= 4:
                break
    return [(cx, cy) for _, cx, cy in kept]


def find_speed_button(img, thresh=0.80):
    """Cari tombol percepat battle (1x / hijau) di paruh bawah layar."""
    tpl_p = Config.BTN_SPEED_TPL
    if not os.path.exists(tpl_p):
        return None
    tpl = cv2.imread(tpl_p)
    if tpl is None:
        return None
    roi = img[600:1080, :]
    for s in [1.0, 1.4, 1.8]:
        w = int(tpl.shape[1] * s)
        h = int(tpl.shape[0] * s)
        if w >= roi.shape[1] or h >= roi.shape[0]:
            continue
        r_tpl = cv2.resize(tpl, (w, h), interpolation=cv2.INTER_LINEAR)
        res = cv2.matchTemplate(roi, r_tpl, cv2.TM_CCOEFF_NORMED)
        _, max_v, _, max_l = cv2.minMaxLoc(res)
        if max_v >= thresh:
            cx = int(max_l[0] + w // 2)
            cy = int(max_l[1] + 600 + h // 2)
            return cx, cy, float(max_v)
    return None


def get_line_points(p1, p2, count, jitter=12):
    """Bagi garis p1->p2 menjadi count titik berjarak rata (line deploy) dengan sedikit jitter."""
    if count <= 1:
        return [((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)]
    points = []
    x1, y1 = p1
    x2, y2 = p2
    for i in range(count):
        t = i / float(count - 1)
        x = int(x1 + t * (x2 - x1)) + int(np.random.randint(-jitter, jitter + 1))
        y = int(y1 + t * (y2 - y1)) + int(np.random.randint(-jitter, jitter + 1))
        points.append((x, y))
    return points


def find_base_storages(img, tpl_dir=Config.STORAGE_TPL_DIR, thresh=Config.STORAGE_THRESHOLD):
    """Deteksi posisi spesifik Gold, Elixir, dan Dark Elixir Storage via masked template matching."""
    crop_base = img[160:860, 240:1700]
    hsv = cv2.cvtColor(crop_base, cv2.COLOR_BGR2HSV)
    detected = []

    for tpl_name in ["gold", "elixir", "dark"]:
        tpl_path = os.path.join(tpl_dir, f"{tpl_name}.png")
        if not os.path.exists(tpl_path):
            continue
        rgba = cv2.imread(tpl_path, cv2.IMREAD_UNCHANGED)
        if rgba is None or rgba.shape[2] != 4:
            continue
        bgr = rgba[:, :, :3]
        mask = rgba[:, :, 3]

        for scale in [0.40, 0.50, 0.60, 0.70]:
            w = int(bgr.shape[1] * scale)
            h = int(bgr.shape[0] * scale)
            if w >= crop_base.shape[1] or h >= crop_base.shape[0] or w < 20 or h < 20:
                continue
            r_bgr = cv2.resize(bgr, (w, h), interpolation=cv2.INTER_AREA)
            r_mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_AREA)
            _, r_mask = cv2.threshold(r_mask, 127, 255, cv2.THRESH_BINARY)

            res = cv2.matchTemplate(crop_base, r_bgr, cv2.TM_CCORR_NORMED, mask=r_mask)
            locs = np.where(res >= thresh)
            for pt in zip(*locs[::-1]):
                bx, by = pt[0] + w // 2, pt[1] + h // 2
                hw, hh = w // 2, h // 2
                sub_hsv = hsv[max(0, by - hh):min(hsv.shape[0], by + hh), max(0, bx - hw):min(hsv.shape[1], bx + hw)]
                if sub_hsv.size == 0:
                    continue

                valid = False
                if tpl_name == "elixir":
                    valid = np.count_nonzero(cv2.inRange(sub_hsv, np.array([135, 70, 70]), np.array([170, 255, 255]))) > 20
                elif tpl_name == "gold":
                    valid = np.count_nonzero(cv2.inRange(sub_hsv, np.array([18, 100, 120]), np.array([35, 255, 255]))) > 35
                elif tpl_name == "dark":
                    valid = np.count_nonzero(cv2.inRange(sub_hsv, np.array([125, 50, 25]), np.array([175, 255, 140]))) > 25

                if valid:
                    gx = bx + 240
                    gy = by + 160
                    detected.append((gx, gy, float(res[pt[1], pt[0]]), tpl_name))

    # Non-maximum suppression
    detected.sort(key=lambda x: x[2], reverse=True)
    kept = []
    for d in detected:
        if not any((d[0] - k[0]) ** 2 + (d[1] - k[1]) ** 2 < 55 ** 2 for k in kept):
            kept.append(d)
    return kept


def detect_best_attack_side(img):
    """Pindai densitas storage Gold/Elixir/Dark di 4 kuadran base lawan (Smart Attack)."""
    storages = find_base_storages(img)
    weights = {"gold": 1.0, "elixir": 1.0, "dark": 2.5}
    cx, cy = 960, 500

    if len(storages) >= 2:
        scores = {"KIRI_ATAS": 0.0, "KANAN_ATAS": 0.0, "KIRI_BAWAH": 0.0, "KANAN_BAWAH": 0.0}
        counts = {"gold": 0, "elixir": 0, "dark": 0}
        for sx, sy, sc, st in storages:
            counts[st] += 1
            w = weights.get(st, 1.0)
            if sx < cx and sy < cy:
                scores["KIRI_ATAS"] += w
            elif sx >= cx and sy < cy:
                scores["KANAN_ATAS"] += w
            elif sx < cx and sy >= cy:
                scores["KIRI_BAWAH"] += w
            else:
                scores["KANAN_BAWAH"] += w

        best = max(scores, key=lambda k: scores[k])
        logging.info("[SMART] Deteksi Storage via template: %d Gold, %d Elixir, %d Dark Storage",
                     counts["gold"], counts["elixir"], counts["dark"])
        return best, scores

    # Fallback jika base tertutup kabut/skin khusus
    crop_base = img[160:840, 240:1700]
    hsv = cv2.cvtColor(crop_base, cv2.COLOR_BGR2HSV)

    # Elixir storage: magenta/purple
    m_elixir = cv2.inRange(hsv, np.array([140, 110, 110]), np.array([168, 255, 255]))
    # Gold storage: gold/yellow
    m_gold = cv2.inRange(hsv, np.array([19, 140, 160]), np.array([32, 255, 255]))
    # Dark Elixir / Town hall core accents: dark or cyan
    m_dark = cv2.inRange(hsv, np.array([90, 80, 20]), np.array([135, 255, 80]))

    combined = cv2.bitwise_or(m_elixir, m_gold)
    combined = cv2.bitwise_or(combined, m_dark)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    opened = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
    cnts, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    scores = {"KIRI_ATAS": 0.0, "KANAN_ATAS": 0.0, "KIRI_BAWAH": 0.0, "KANAN_BAWAH": 0.0}

    for c in cnts:
        area = cv2.contourArea(c)
        if 200 < area < 10000:
            x, y, w, h = cv2.boundingRect(c)
            if 0.4 < w / h < 2.5:
                bx = x + w // 2 + 240
                by = y + h // 2 + 160
                if bx < cx and by < cy:
                    scores["KIRI_ATAS"] += area
                elif bx >= cx and by < cy:
                    scores["KANAN_ATAS"] += area
                elif bx < cx and by >= cy:
                    scores["KIRI_BAWAH"] += area
                else:
                    scores["KANAN_BAWAH"] += area

    best = max(scores, key=lambda k: scores[k])
    return best, scores


# ============================================================
#  BOT
# ============================================================
class Bot:
    def __init__(self):
        self.adb = Adb()
        os.makedirs(Config.OUT_DIR, exist_ok=True)
        self._csv_new = not os.path.exists(Config.CSV)
        self._unknown = 0
        self._attacks_since_collect = 1
        self._next_collect_after = np.random.randint(Config.COLLECT_EVERY_N[0], Config.COLLECT_EVERY_N[1] + 1)
        self.running = False
        self.current_state = "IDLE"
        self.total_attacks = 0
        self.last_loot = {}
        self.start_time = time.time()

    def stop(self):
        self.running = False

    def dismiss_popups(self, img):
        """Tutup pop-up (X merah) atau dialog error / putus koneksi (Reload / Try Again)."""
        if not Config.AUTO_RECONNECT:
            return False

        # 1. Cek tombol X merah penutup modal dialog (khusus area modal tengah, hindari HUD/frame emulator)
        if os.path.exists(Config.TPL_CLOSE_X):
            tpl_x = _tpl(Config.TPL_CLOSE_X)
            if tpl_x is not None:
                x1, y1, x2, y2 = (600, 50, 1750, 450)
                g_roi = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
                if g_roi.shape[0] >= tpl_x.shape[0] and g_roi.shape[1] >= tpl_x.shape[1]:
                    res = cv2.matchTemplate(g_roi, tpl_x, cv2.TM_CCOEFF_NORMED)
                    _, max_v, _, max_l = cv2.minMaxLoc(res)
                    if max_v >= 0.82:
                        cx = max_l[0] + x1 + tpl_x.shape[1] // 2
                        cy = max_l[1] + y1 + tpl_x.shape[0] // 2

                        # Verifikasi warna merah pada tombol X
                        crop = img[max(0, cy - 20):cy + 20, max(0, cx - 20):cx + 20]
                        if crop.size:
                            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                            m1 = cv2.inRange(hsv, np.array([0, 120, 120]), np.array([10, 255, 255]))
                            m2 = cv2.inRange(hsv, np.array([170, 120, 120]), np.array([180, 255, 255]))
                            red_ratio = float((cv2.bitwise_or(m1, m2) > 0).mean())
                            if red_ratio >= 0.15:
                                logging.info("[POPUP] Menutup modal dialog (X merah) di (%d, %d)", cx, cy)
                                self.adb.tap(cx, cy)
                                time.sleep(1.0)
                                return True

        # 2. Cek teks dialog tengah (koneksi terputus / reload / out of sync)
        crop = img[300:780, 550:1370]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        txt = pytesseract.image_to_string(gray, config="--oem 3 --psm 11").lower()
        keywords = ("reload", "try again", "connection", "client", "server",
                    "out of sync", "personal break", "maintenance", "another device")
        if any(w in txt for w in keywords):
            first_line = txt.strip().splitlines()[0] if txt.strip() else "popup"
            logging.info("[RECONNECT] Terdeteksi dialog '%s', menekan Reload/Okay", first_line)
            self.adb.tap(*Config.BTN_POPUP_OKAY)
            time.sleep(3.0)
            return True

        return False

    def check_auto_stop(self, img=None):
        """Evaluasi batas waktu dan resource cap untuk perlindungan akun."""
        if not Config.AUTO_STOP_ENABLED:
            return False

        # 1. Timer check
        if Config.AUTO_STOP_MINUTES > 0:
            elapsed_m = (time.time() - self.start_time) / 60.0
            if elapsed_m >= Config.AUTO_STOP_MINUTES:
                logging.info("[AUTO STOP] Batas waktu operasional %d menit tercapai! Menghentikan bot.",
                             Config.AUTO_STOP_MINUTES)
                self.stop()
                return True

        # 2. Resource cap check saat di HOME
        if img is not None and detect_state(img) == "HOME":
            loot = read_loot_home(img)
            g = loot.get("Gold") or 0
            e = loot.get("Elixir") or 0
            if Config.STOP_GOLD_CAP > 0 and g >= Config.STOP_GOLD_CAP:
                logging.info("[AUTO STOP] Gold di base mencapai target (%s >= %s)! Menghentikan bot.",
                             f"{g:,}", f"{Config.STOP_GOLD_CAP:,}")
                self.stop()
                return True
            if Config.STOP_ELIXIR_CAP > 0 and e >= Config.STOP_ELIXIR_CAP:
                logging.info("[AUTO STOP] Elixir di base mencapai target (%s >= %s)! Menghentikan bot.",
                             f"{e:,}", f"{Config.STOP_ELIXIR_CAP:,}")
                self.stop()
                return True

        return False

    def upgrade_wall(self):
        """Upgrade wall di Home Base jika saldo melebihi limit."""
        if Config.UPGRADE_WALL_MODE == "OFF":
            return
        img = self.snap()
        if img is None or detect_state(img) != "HOME":
            return
        loot = read_loot_home(img)
        g = loot.get("Gold")
        e = loot.get("Elixir")

        # Jika salah satu gagal baca/None, batalkan demi keamanan
        if g is None or e is None:
            return

        gold_ready = g > Config.WALL_GOLD_LIMIT
        elixir_ready = e > Config.WALL_ELIXIR_LIMIT

        if not gold_ready and not elixir_ready:
            return

        max_cycles = 5 if Config.UPGRADE_WALL_MODE == "ALWAYS_CHECK_LIMIT" else 1
        for _ in range(max_cycles):
            # 1. Pilih wall
            self.adb.tap(*Config.WALL_TAP_COORD)
            time.sleep(0.7)

            # 2. Verifikasi keamanan: pastikan objek yang dipilih benar Wall
            img_sel = self.snap()
            if img_sel is None:
                self.adb.tap(*Config.WALL_DESELECT_PT)
                return

            crop_title = img_sel[840:910, 700:1220]
            txt_title = pytesseract.image_to_string(
                cv2.cvtColor(crop_title, cv2.COLOR_BGR2GRAY)
            ).strip().lower()

            if "wall" not in txt_title:
                logging.info("[WALL] Objek terpilih bukan Wall ('%s'), membatalkan upgrade agar aman", txt_title or "kosong")
                self.adb.tap(*Config.WALL_DESELECT_PT)
                time.sleep(0.5)
                return

            logging.info("[WALL] Wall terverifikasi! Upgrade (Gold: %s, Elixir: %s, Limit: %s/%s)",
                         f"{g:,}", f"{e:,}", f"{Config.WALL_GOLD_LIMIT:,}", f"{Config.WALL_ELIXIR_LIMIT:,}")

            # 3. Tap tombol Upgrade wall di bar bawah
            self.adb.tap(*Config.WALL_UPGRADE_BTN)
            time.sleep(0.6)

            # 4. Tap opsi bayar (Gold jika cukup, atau Elixir)
            if gold_ready:
                self.adb.tap(*Config.WALL_GOLD_BTN)
            elif elixir_ready:
                self.adb.tap(*Config.WALL_ELIXIR_BTN)
            time.sleep(0.6)

            # 5. Deselect di rumput aman luar base
            self.adb.tap(*Config.WALL_DESELECT_PT)
            time.sleep(0.5)

            if Config.UPGRADE_WALL_MODE != "ALWAYS_CHECK_LIMIT":
                break

            # Cek saldo baru
            img_new = self.snap()
            if img_new is not None:
                loot = read_loot_home(img_new)
                g = loot.get("Gold")
                e = loot.get("Elixir")
                if g is None or e is None:
                    break
                gold_ready = g > Config.WALL_GOLD_LIMIT
                elixir_ready = e > Config.WALL_ELIXIR_LIMIT
                if not gold_ready and not elixir_ready:
                    break

    def snap(self, name=None):
        img = self.adb.shot()
        if img is not None and name:
            cv2.imwrite(os.path.join(Config.OUT_DIR, f"{name}.png"), img)
        return img

    def log_csv(self, loot, attacked):
        with open(Config.CSV, "a", newline="") as f:
            w = csv.writer(f)
            if self._csv_new:
                w.writerow(["time", "gold", "elixir", "dark", "attacked"])
                self._csv_new = False
            w.writerow([time.strftime("%H:%M:%S"),
                        loot.get("Gold"), loot.get("Elixir"),
                        loot.get("Dark"), int(attacked)])

    # ---------------- aksi ----------------
    def collect_resources(self):
        """Klaim gelembung Gold/Elixir di Home Base."""
        if not Config.AUTO_COLLECT:
            return
        img = self.snap()
        if img is None or detect_state(img) != "HOME":
            return
        bubbles = find_collector_bubbles(img)
        if not bubbles:
            return
        logging.info("klaim collector: terdeteksi %d gelembung", len(bubbles))
        seen = set()
        for btype, x, y in bubbles:
            if btype not in seen:
                seen.add(btype)
                self.adb.tap(x + np.random.randint(-4, 4), y + np.random.randint(-4, 4))
                time.sleep(0.4)
        self._attacks_since_collect = 0
        self._next_collect_after = np.random.randint(Config.COLLECT_EVERY_N[0], Config.COLLECT_EVERY_N[1] + 1)

    def end_battle(self):
        """Akhiri battle secara manual (tap End Battle merah + konfirmasi Okay)."""
        logging.info("akhiri battle manual (surrender)")
        self.adb.tap(*Config.BTN_END)
        time.sleep(0.6)
        self.adb.tap(*Config.BTN_SURRENDER_CONFIRM)
        time.sleep(1.0)

    def cast_lightning(self, card_map=None, img=None):
        """Jatuhkan petir ke Air Defense yang terdeteksi, atau fallback ke titik core base."""
        card_map = card_map or {}
        if Config.SPELL_UNIT in card_map:
            sx, sy = card_map[Config.SPELL_UNIT][0], card_map[Config.SPELL_UNIT][1]
        else:
            sx, sy = Config.FALLBACK_SLOTS.get(Config.SPELL_UNIT, (1127, 945))

        spots = []
        if img is not None:
            spots = find_air_defenses(img)

        if not spots:
            spots = Config.LIGHTNING_SPOTS
            logging.info("[PETIR] AD tidak terdeteksi, fallback ke core base %s (%d spell)", spots, Config.TOTAL_LIGHTNING)
        else:
            logging.info("[PETIR] Terdeteksi %d Air Defense: %s (%d spell)", len(spots), spots, Config.TOTAL_LIGHTNING)

        self.adb.tap(sx, sy)
        time.sleep(0.35)
        for i in range(Config.TOTAL_LIGHTNING):
            cx, cy = spots[i % len(spots)]
            jx = int(np.random.randint(-10, 10))
            jy = int(np.random.randint(-10, 10))
            self.adb.tap(cx + jx, cy + jy)
            time.sleep(0.18)

    def deploy(self, card_map=None, target_side=None):
        """Deploy pasukan berbaris rata di sisi terpilih (Kiri Atas, Kanan Atas, Kiri Bawah, Kanan Bawah, atau Smart)."""
        card_map = card_map or {}
        strat = getattr(Config, "ATTACK_STRATEGY", "SMART")
        side = target_side or strat

        if side not in Config.ATTACK_LINES and side != "FOUR_SIDES":
            side = "KIRI_BAWAH"

        logging.info("deploy strategi: %s (sisi aktif: %s)", strat, side)

        for name, taps, utype in Config.ARMY_ORDER:
            if name in card_map:
                sx, sy = card_map[name][0], card_map[name][1]
            elif utype in ("troop", "siege") and name in Config.FALLBACK_SLOTS:
                sx, sy = Config.FALLBACK_SLOTS[name]
                logging.info("kartu '%s' pakai fallback slot (%d, %d)", name, sx, sy)
            elif not card_map and name in Config.FALLBACK_SLOTS:
                sx, sy = Config.FALLBACK_SLOTS[name]
            else:
                logging.info("kartu '%s' tidak dibawa / tidak aktif, skip", name)
                continue

            self.adb.tap(sx + np.random.randint(-4, 4), sy + np.random.randint(-4, 4))
            time.sleep(0.30)

            if side == "FOUR_SIDES":
                all_sides = list(Config.ATTACK_LINES.keys())
                total_taps = taps + 3 if utype == "troop" else max(3, taps)
                for tap_idx in range(total_taps):
                    s_name = all_sides[tap_idx % len(all_sides)]
                    p1, p2 = Config.ATTACK_LINES[s_name]
                    pt = ((p1[0] + p2[0]) // 2 + int(np.random.randint(-15, 15)),
                          (p1[1] + p2[1]) // 2 + int(np.random.randint(-15, 15)))
                    self.adb.tap(pt[0], pt[1])
                    time.sleep(0.10)
            else:
                # 1 Sisi: Berbaris RATA sepanjang garis perimeter
                p1, p2 = Config.ATTACK_LINES[side]
                if utype == "troop":
                    # Taps ekstra (taps + 4) agar seluruh naga keluar rata tanpa tertahan
                    points = get_line_points(p1, p2, taps + 4)
                    for pt in points:
                        self.adb.tap(pt[0], pt[1])
                        time.sleep(0.10)
                elif utype == "siege":
                    # Siege Machine (Wall Wrecker): tap 4x agar pasti turun menembus batas merah
                    cx = (p1[0] + p2[0]) // 2
                    cy = (p1[1] + p2[1]) // 2
                    for _ in range(4):
                        jx, jy = int(np.random.randint(-10, 10)), int(np.random.randint(-10, 10))
                        self.adb.tap(cx + jx, cy + jy)
                        time.sleep(0.12)
                else:
                    cx = (p1[0] + p2[0]) // 2 + int(np.random.randint(-10, 10))
                    cy = (p1[1] + p2[1]) // 2 + int(np.random.randint(-10, 10))
                    for _ in range(max(2, taps)):
                        self.adb.tap(cx, cy)
                        time.sleep(0.12)

            time.sleep(0.15)

        # 2. Failsafe Cleanup Sweep (Sapu Bersih Sisa Pasukan & Siege di Pantai Bebas Red-Line)
        time.sleep(0.3)
        beach_x, beach_y = getattr(Config, "SAFE_BEACH_DROP", (135, 520))
        logging.info("[DEPLOY] Sapu bersih sisa pasukan & siege di pantai aman (%d, %d)...", beach_x, beach_y)
        for name, taps, utype in Config.ARMY_ORDER:
            if utype in ("troop", "siege"):
                if name in card_map:
                    sx, sy = card_map[name][0], card_map[name][1]
                elif name in Config.FALLBACK_SLOTS:
                    sx, sy = Config.FALLBACK_SLOTS[name]
                else:
                    continue
                self.adb.tap(sx, sy)
                time.sleep(0.2)
                t_count = 6 if utype == "troop" else 3
                for _ in range(t_count):
                    jx, jy = int(np.random.randint(-15, 15)), int(np.random.randint(-25, 25))
                    self.adb.tap(beach_x + jx, beach_y + jy)
                    time.sleep(0.10)

        time.sleep(0.4)
        self.check_speed_up()

    def check_speed_up(self, img=None):
        """Otomatis tap tombol percepat battle (1x -> 4x) jika terdeteksi."""
        if not getattr(Config, "AUTO_SPEED_UP", True):
            return False
        img = img if img is not None else self.snap()
        if img is None:
            return False
        btn = find_speed_button(img)
        if btn:
            cx, cy, sc = btn
            logging.info("[PERCEPAT] Tombol 1x terdeteksi di (%d, %d) [skor %.2f], tap 2x ke 4x", cx, cy, sc)
            self.adb.tap(cx, cy)
            time.sleep(0.18)
            self.adb.tap(cx, cy)
            return True
        return False

    def cast_hero_abilities(self, card_map=None):
        """Ulti hero = tap ulang kartu hero yang sudah turun (UI baru CoC mobile).

        Dijadwalkan Config.ABILITY_DELAYS dari akhir deploy: kalau diklik
        langsung, hero masih jalan ke base dan ability kebuang. Ronde 2 untuk
        BK/AQ yang ability-nya bisa 2x.
        """
        card_map = card_map or {}
        hero_slots = []
        for name, _, utype in Config.ARMY_ORDER:
            if utype == "hero":
                if name in card_map:
                    hero_slots.append((card_map[name][0], card_map[name][1]))
                elif not card_map and name in Config.FALLBACK_SLOTS:
                    hero_slots.append(Config.FALLBACK_SLOTS[name])
        if not hero_slots:
            hero_slots = Config.HERO_CARDS

        for i, delay in enumerate(Config.ABILITY_DELAYS):
            time.sleep(max(0.0, delay - (Config.ABILITY_DELAYS[i - 1] if i else 0)))
            img = self.snap()
            # Cek blob merah End Battle dulu (kebal naga/petir yang nutup teks atas)
            if img is None or not (end_button_visible(img) or battle_running(img)):
                logging.info("battle selesai sebelum ronde %d, ulti dihentikan", i + 1)
                return
            for x, y in hero_slots:
                self.adb.tap(x + np.random.randint(-3, 3), y + np.random.randint(-3, 3))
                time.sleep(0.25)
            logging.info("ulti hero ronde %d (+%ds, %d hero)", i + 1, delay, len(hero_slots))
            self.check_speed_up(img)

    def wait_battle_end(self, battle_t0=None):
        t0 = battle_t0 or time.time()
        last_loot_sum = None
        stagnant_count = 0

        while True:
            elapsed = time.time() - t0
            if elapsed >= Config.MAX_BATTLE_TIME:
                logging.warning("battle timeout (%ds >= %ds); akhiri battle",
                                int(elapsed), Config.MAX_BATTLE_TIME)
                self.end_battle()
                break

            img = self.snap()
            if img is None:
                time.sleep(2)
                continue

            state = detect_state(img)
            if state == "HOME":
                logging.info("battle selesai, kembali ke home")
                return
            if state == "UNKNOWN":
                # layar hasil ("Total damage"/"Return Home")
                self.adb.tap(*Config.BTN_RETURN)
                time.sleep(2)
                continue

            # Percepat battle ke 4x jika tombol 1x terdeteksi
            self.check_speed_up(img)

            # Auto End Battle jika loot habis atau stagnan
            if Config.END_IF_LOOT_EMPTY and elapsed >= 30 and (end_button_visible(img) or battle_running(img)):
                current_loot = read_loot_scout(img)
                g = current_loot.get("Gold") or 0
                e = current_loot.get("Elixir") or 0
                loot_sum = g + e

                if 0 < loot_sum <= Config.LOOT_EMPTY_THRESHOLD:
                    logging.info("loot tersisa habis (%d <= %d); akhiri battle (+%ds)",
                                 loot_sum, Config.LOOT_EMPTY_THRESHOLD, int(elapsed))
                    self.end_battle()
                    break

                if last_loot_sum is not None and loot_sum == last_loot_sum and loot_sum > 0:
                    stagnant_count += 1
                    if stagnant_count >= Config.STAGNANT_CHECKS:
                        logging.info("loot stagnan %d cek (%d); akhiri battle (+%ds)",
                                     stagnant_count, loot_sum, int(elapsed))
                        self.end_battle()
                        break
                else:
                    stagnant_count = 0
                    last_loot_sum = loot_sum

            time.sleep(4)

        # Tunggu kembali ke HOME pasca surrender
        t_post = time.time()
        while time.time() - t_post < 30:
            img = self.snap()
            if img is None:
                time.sleep(2)
                continue
            state = detect_state(img)
            if state == "HOME":
                logging.info("kembali ke home")
                return
            self.adb.tap(*Config.BTN_RETURN)
            time.sleep(3)

    # ---------------- loop ----------------
    def step(self):
        if not self.running:
            return
        if self.check_auto_stop():
            return

        img = self.snap("last" if Config.SAVE_DEBUG_SHOTS else None)
        if img is None:
            return

        state = detect_state(img)
        self.current_state = state
        logging.info("state=%s", state)
        if state != "UNKNOWN":
            self._unknown = 0

        if state == "HOME":
            if self.check_auto_stop(img):
                return
            if self._attacks_since_collect >= self._next_collect_after:
                self.collect_resources()
            self.upgrade_wall()
            self.adb.tap(*Config.BTN_BATTLE)
            time.sleep(Config.TAP_DELAY_HOME)
        elif state == "MENU":
            self.adb.tap(*Config.BTN_FIND)
            time.sleep(Config.TAP_DELAY_MENU)
        elif state == "ARMY":
            self.adb.tap(*Config.BTN_ATTACK)
            time.sleep(Config.TAP_DELAY_ARMY)
        elif state == "SCOUT":
            if battle_running(img):
                # bot dinyalakan saat battle masih jalan: jangan tap Next, tunggu selesai
                logging.info("battle sedang berjalan, tunggu selesai")
                self.wait_battle_end()
                return
            loot = read_loot_scout(img)
            if loot["Gold"] is None and loot["Elixir"] is None:
                # awan transisi baru buka -> tunggu sebentar lalu baca ulang sekali
                time.sleep(0.7)
                img = self.snap() or img
                loot = read_loot_scout(img)
            enough = loot_enough(loot)
            logging.info("loot=%s mode=%s cukup=%s", loot, Config.LOOT_MODE, enough)
            self.log_csv(loot, enough)
            if enough:
                logging.info("Loot target terpenuhi! Langsung serang!")
                self.total_attacks += 1
                self.last_loot = loot
                t_deploy = time.time()
                card_map = detect_army_cards(img)
                if card_map:
                    logging.info("kartu terdeteksi di bar: %s",
                                 {k: (v[0], v[1]) for k, v in card_map.items()})

                # Evaluasi Smart Attack atau Sisi Pilihan
                chosen_side = Config.ATTACK_STRATEGY
                if chosen_side == "SMART":
                    best_side, scores = detect_best_attack_side(img)
                    chosen_side = best_side
                    logging.info("Smart Attack memilih sisi %s (densitas storage: %s)",
                                 best_side, {k: int(v) for k, v in scores.items()})

                # 1. Spell petir jatuh PERTAMA menghancurkan Air Defense musuh
                self.cast_lightning(card_map, img)

                # 2. Deploy pasukan & hero berbaris rata di sisi perimeter luar
                self.deploy(card_map, chosen_side)
                img2 = self.snap()
                if img2 is not None and not battle_running(img2):
                    # deploy ditolak (masih "Battle starts in") -> ulang sekali
                    logging.info("deploy belum masuk, ulang 3 dtk lagi")
                    time.sleep(3)
                    self.deploy(card_map, chosen_side)

                # 3. Ulti hero
                self.cast_hero_abilities(card_map)      # ulti hero, ronde +30s & +62s
                time.sleep(2)
                self.wait_battle_end(t_deploy)
                self._attacks_since_collect += 1
            else:
                short = {k: loot.get(k) for k, t in Config.TARGETS.items() if (loot.get(k) or 0) < t}
                logging.info("SKIP base [%s]: %s < target %s", Config.LOOT_MODE, short,
                             {k: t for k, t in Config.TARGETS.items() if k in short})
                # Next: ganti base langsung (tanpa keluar ke home)
                self.adb.tap(*Config.BTN_NEXT)
                time.sleep(Config.TAP_DELAY_NEXT)
        else:
            # UNKNOWN sering cuma animasi awan 2-5 dtk (matchmaking / ganti base).
            # Butuh beberapa frame sebelum action agar tidak salah tap saat awan buka.
            self._unknown += 1
            if self._unknown < 4:
                return

            # Coba tutup pop-up / dialog reconnect jika ada yang menghalangi
            if self.dismiss_popups(img):
                self._unknown = 0
                return

            if self._unknown < 6:
                return
            self._unknown = 0
            self.snap("unknown")
            self.adb.tap(*Config.BTN_RETURN)
            time.sleep(Config.TAP_DELAY_UNKNOWN)

    def loop(self):
        self.running = True
        self.start_time = time.time()
        while self.running:
            try:
                self.step()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error("loop error: %s", e)
            time.sleep(Config.POLL)

    def calibrate(self):
        img = self.snap("calibrate")
        if img is None:
            return logging.error("screenshot gagal")
        vis = img.copy()
        for state, (path, (x1, y1, x2, y2)) in Config.TPL.items():
            s = match_score(img, path, (x1, y1, x2, y2))
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(vis, f"{state} {s:.2f}", (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        for k, (x1, y1, x2, y2) in Config.REGION_LOOT.items():
            cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 255), 2)
            cv2.putText(vis, k, (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
        army_cards = detect_army_cards(img)
        for name, (cx, cy, score) in army_cards.items():
            cv2.rectangle(vis, (cx - 35, cy - 45), (cx + 35, cy + 45), (0, 255, 0), 2)
            cv2.putText(vis, f"{name} {score:.2f}", (cx - 35, cy - 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        ad_targets = find_air_defenses(img)
        for i, (cx, cy) in enumerate(ad_targets):
            cv2.circle(vis, (int(cx), int(cy)), 30, (0, 0, 255), 2)
            cv2.putText(vis, f"AD {i+1}", (int(cx) - 20, int(cy) - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
        cv2.imwrite(os.path.join(Config.OUT_DIR, "calibrate.png"), vis)
        logging.info("state=%s scout_loot=%s home_loot=%s end_btn=%s bubbles=%d cards=%d ads=%d",
                     detect_state(img), read_loot_scout(img), read_loot_home(img),
                     end_button_visible(img), len(find_collector_bubbles(img)), len(army_cards), len(ad_targets))


def selftest():
    """Vision check tanpa device: template harus match di posisinya sendiri."""
    for state, (path, roi) in Config.TPL.items():
        tpl = _tpl(path)
        assert tpl is not None, f"template hilang: {path}"
        canvas = np.full((Config.H, Config.W, 3), 30, np.uint8)
        x, y = roi[0], roi[1]
        canvas[y:y + tpl.shape[0], x:x + tpl.shape[1]] = cv2.cvtColor(tpl, cv2.COLOR_GRAY2BGR)
        got = detect_state(canvas)
        assert got == state, f"{state}: dapat {got}"
        print(f"{state:6s} ok")

    # test loot modes
    Config.LOOT_MODE = "GOLD_OR_ELIXIR"
    assert loot_enough({"Gold": 10**6, "Elixir": 0})
    assert loot_enough({"Gold": 0, "Elixir": 10**6})
    Config.LOOT_MODE = "GOLD_AND_ELIXIR"
    assert not loot_enough({"Gold": 10**6, "Elixir": 0})
    assert loot_enough({"Gold": 10**6, "Elixir": 10**6})
    Config.LOOT_MODE = "GOLD_ONLY"
    assert loot_enough({"Gold": 10**6, "Elixir": 0})
    assert not loot_enough({"Gold": 0, "Elixir": 10**6})
    Config.LOOT_MODE = "ELIXIR_ONLY"
    assert loot_enough({"Elixir": 10**6, "Gold": 0})
    assert not loot_enough({"Gold": 10**6, "Elixir": 0})
    Config.LOOT_MODE = "DE_ONLY"
    assert loot_enough({"Dark": 10**4})
    assert not loot_enough({"Dark": 100})
    print("loot gate ok (semua mode)")

    assert _parse_loot_text("1 320 758") == 1_320_758
    assert _parse_loot_text("8995 740") == 995_740
    assert _parse_loot_text("9 999 999") is None
    assert _parse_loot_text("12 34") is None
    print("loot parsing ok")

    state_path = os.path.join(HERE, "debug", "state.png")
    if os.path.exists(state_path):
        state_img = cv2.imread(state_path)
        if state_img is not None:
            bubbles = find_collector_bubbles(state_img)
            assert len(bubbles) > 0, "harus mendeteksi gelembung di state.png"
            print(f"collector bubbles ok ({len(bubbles)} terdeteksi)")

    ad_path = os.path.join(HERE, "debug", "ad_detect.png")
    if os.path.exists(ad_path):
        im_ad = cv2.imread(ad_path)
        if im_ad is not None:
            cards = detect_army_cards(im_ad)
            assert len(cards) >= 1, "harus mendeteksi kartu unit di army bar"
            print(f"army cards ok ({len(cards)} unit terdeteksi via template)")

    ptr_path = os.path.join(HERE, "debug", "ptr_test.png")
    if os.path.exists(ptr_path):
        im_ptr = cv2.imread(ptr_path)
        if im_ptr is not None and os.path.exists(Config.TPL_CLOSE_X):
            tpl_x = _tpl(Config.TPL_CLOSE_X)
            res = cv2.matchTemplate(cv2.cvtColor(im_ptr, cv2.COLOR_BGR2GRAY), tpl_x, cv2.TM_CCOEFF_NORMED)
            _, max_v, _, _ = cv2.minMaxLoc(res)
            assert max_v >= 0.82
            print(f"popup dismiss X ok (skor {max_v:.2f})")

    # test line points & smart attack
    pts = get_line_points((260, 260), (650, 140), 10, jitter=0)
    assert len(pts) == 10 and pts[0] == (260, 260) and pts[-1] == (650, 140)
    if os.path.exists(ad_path):
        im_ad = cv2.imread(ad_path)
        if im_ad is not None:
            side, sc = detect_best_attack_side(im_ad)
            assert side in Config.ATTACK_LINES
            print(f"smart attack ok (terpilih {side})")
            detected_ads = find_air_defenses(im_ad)
            assert len(detected_ads) >= 1, "harus mendeteksi Air Defense di ad_detect.png"
            print(f"air defense detection ok ({len(detected_ads)} AD terdeteksi)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--selftest":
        selftest()
    else:
        bot = Bot()
        if arg == "--calibrate":
            bot.calibrate()
        elif arg == "--state":
            img = bot.snap("state")
            print("state =", detect_state(img))
            print("scout =", read_loot_scout(img))
            print("home  =", read_loot_home(img))
        else:
            bot.loop()
