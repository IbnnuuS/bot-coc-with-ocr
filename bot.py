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
HERE = os.path.dirname(os.path.abspath(__file__))


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
    # filter base: cukup salah satu (gold ATAU elixir) supaya cepat dapat target
    TARGETS = {"Gold": 900_000, "Elixir": 900_000}   # Dark tidak difilter
    MAX_LOOT = {"Gold": 3_500_000, "Elixir": 3_500_000, "Dark": 50_000}
    ANY_TARGET = True            # True: gold/elixir salah satu lolos = serang

    # --- template state (1080p) ---
    TPL = {
        "HOME":  (os.path.join(HERE, "templates", "btn_battle.png"), (20, 880, 225, 1064)),
        "MENU":  (os.path.join(HERE, "templates", "btn_find.png"),   (100, 715, 555, 810)),
        "ARMY":  (os.path.join(HERE, "templates", "btn_attack.png"), (1520, 880, 1850, 958)),
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

    TAP_DELAY_HOME    = 0.8
    TAP_DELAY_MENU    = 1.0
    TAP_DELAY_ARMY    = 1.2
    TAP_DELAY_NEXT    = 1.0
    TAP_DELAY_UNKNOWN = 1.0

    # urutan deploy: (x, y, jumlah tap) — satu baris kartu, y=945
    DEPLOY_ORDER = [
        (206, 945, 10),   # 1. Electro Dragon x10
        (378, 945, 1),    # 2. Wall Wrecker
        (529, 945, 1),    # 3. Barbarian King 72
        (674, 945, 1),    # 4. Archer Queen 75
        (820, 945, 1),    # 5. Grand Warden 50
        (958, 945, 1),    # 6. Royal Champion 18
    ]
    SPELL_SLOT = (1127, 945)        # 7. Lightning Spell x11
    TOTAL_LIGHTNING = 11            # seluruh 11 spell petir digunakan habis
    # kartu hero (tap ulang = ability/ulti setelah hero turun)
    HERO_CARDS = [(529, 945), (674, 945), (820, 945), (958, 945)]   # BK, AQ, GW, RC
    ABILITY_DELAYS = (30, 62)       # detik setelah deploy; ronde 2 utk BK/AQ (2x pakai)
    # kuadran core base (base selalu kira-kira di tengah layar saat scout)
    LIGHTNING_SPOTS = [(780, 390), (1090, 390), (780, 650), (1090, 650)]
    DEPLOY_POINT = (140, 520)       # rumput tepi pantai (100% di luar batas base manapun)
    DEPLOY_SPREAD = (20, 45)

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
        return subprocess.run([self.cfg.ADB, "-s", self.cfg.SERIAL, *args],
                              capture_output=True, timeout=timeout)

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


def read_loot_home(img):
    return {k: ocr_number(img, r) for k, r in Config.REGION_HOME.items()}


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


def loot_enough(loot):
    """Hanya Gold & Elixir yang difilter; Dark diabaikan total."""
    vals = [(loot.get(k) or 0) >= t for k, t in Config.TARGETS.items()]
    return any(vals) if Config.ANY_TARGET else all(vals)


# ============================================================
#  BOT
# ============================================================
class Bot:
    def __init__(self):
        self.adb = Adb()
        os.makedirs(Config.OUT_DIR, exist_ok=True)
        self._csv_new = not os.path.exists(Config.CSV)
        self._unknown = 0

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
    def cast_lightning(self):
        """Sebar semua petir ke Config.LIGHTNING_SPOTS (kuadran core base).

        Deteksi Air Defense otomatis dibuang: template tidak pernah match >0.46
        jadi hasilnya selalu false positive. Petir ke kuadran core lebih stabil.
        """
        spots = Config.LIGHTNING_SPOTS
        logging.info("petir -> %d titik %s (%d spell)", len(spots), spots, Config.TOTAL_LIGHTNING)
        self.adb.tap(*Config.SPELL_SLOT)
        time.sleep(0.3)
        for i in range(Config.TOTAL_LIGHTNING):
            cx, cy = spots[i % len(spots)]
            jx, jy = np.random.randint(-15, 15), np.random.randint(-15, 15)
            self.adb.tap(cx + jx, cy + jy)
            time.sleep(0.18)

    def deploy(self):
        """Deploy cepat sesuai Config.DEPLOY_ORDER di rumput luar base."""
        dx, dy = Config.DEPLOY_SPREAD
        for sx, sy, taps in Config.DEPLOY_ORDER:
            self.adb.tap(sx + np.random.randint(-4, 4), sy + np.random.randint(-4, 4))
            time.sleep(0.2)
            for _ in range(taps):
                self.adb.tap(Config.DEPLOY_POINT[0] + np.random.randint(-dx, dx),
                             Config.DEPLOY_POINT[1] + np.random.randint(-dy, dy))
                time.sleep(0.12)
            time.sleep(0.1)

    def cast_hero_abilities(self):
        """Ulti hero = tap ulang kartu hero yang sudah turun (UI baru CoC mobile).

        Dijadwalkan Config.ABILITY_DELAYS dari akhir deploy: kalau diklik
        langsung, hero masih jalan ke base dan ability kebuang. Ronde 2 untuk
        BK/AQ yang ability-nya bisa 2x.
        """
        for i, delay in enumerate(Config.ABILITY_DELAYS):
            time.sleep(max(0.0, delay - (Config.ABILITY_DELAYS[i - 1] if i else 0)))
            img = self.snap()
            # Cek blob merah End Battle dulu (kebal naga/petir yang nutup teks atas)
            if img is None or not (end_button_visible(img) or battle_running(img)):
                logging.info("battle selesai sebelum ronde %d, ulti dihentikan", i + 1)
                return
            for x, y in Config.HERO_CARDS:
                self.adb.tap(x + np.random.randint(-3, 3), y + np.random.randint(-3, 3))
                time.sleep(0.25)
            logging.info("ulti hero ronde %d (+%ds)", i + 1, delay)

    def wait_battle_end(self):
        t0 = time.time()
        while time.time() - t0 < Config.BATTLE_WAIT:
            img = self.snap()
            if img is None:
                time.sleep(3)
                continue
            state = detect_state(img)
            if state == "HOME":
                logging.info("battle selesai, kembali ke home")
                return
            if state == "UNKNOWN":
                # layar hasil ("Total damage"/"Return Home") atau dialog
                self.adb.tap(*Config.BTN_RETURN)
                self.adb.tap(Config.W // 2, Config.H // 2)
            time.sleep(4)
        logging.warning("battle timeout; End Battle & lanjut")
        self.adb.tap(*Config.BTN_END)

    # ---------------- loop ----------------
    def step(self):
        img = self.snap("last" if Config.SAVE_DEBUG_SHOTS else None)
        if img is None:
            return
        state = detect_state(img)
        logging.info("state=%s", state)
        if state != "UNKNOWN":
            self._unknown = 0

        if state == "HOME":
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
            logging.info("loot=%s cukup=%s", loot, enough)
            self.log_csv(loot, enough)
            if enough:
                logging.info("Loot target terpenuhi! Langsung serang!")
                self.deploy()                  # 1-6: dragon x10, wall wrecker, BK, AQ, GW, RC
                img2 = self.snap()
                if img2 is not None and not battle_running(img2):
                    # deploy ditolak (masih "Battle starts in") -> ulang sekali
                    logging.info("deploy belum masuk, ulang 3 dtk lagi")
                    time.sleep(3)
                    self.deploy()
                self.cast_lightning()           # 7: semua 11 petir ke kuadran core
                self.cast_hero_abilities()      # 8: ulti hero, ronde +30s & +62s
                time.sleep(3)
                self.wait_battle_end()
            else:
                short = {k: loot.get(k) for k, t in Config.TARGETS.items() if (loot.get(k) or 0) < t}
                logging.info("SKIP base: %s < target %s", short,
                             {k: t for k, t in Config.TARGETS.items() if k in short})
                # Next: ganti base langsung (tanpa keluar ke home)
                self.adb.tap(*Config.BTN_NEXT)
                time.sleep(Config.TAP_DELAY_NEXT)
        else:
            # UNKNOWN sering cuma animasi 2-4 dtk (matchmaking / ganti base).
            # Butuh 2 frame berturut-turut sebelum tap buta: tap "Return Home"
            # di layar transisi jatuh ke bar pasukan dan malah memilih kartu.
            self._unknown += 1
            if self._unknown < 2:
                return
            self._unknown = 0
            # layar hasil (Total damage / Return Home) atau dialog
            self.snap("unknown")
            self.adb.tap(*Config.BTN_RETURN)
            self.adb.tap(Config.W // 2, Config.H // 2)
            time.sleep(Config.TAP_DELAY_UNKNOWN)

    def loop(self):
        while True:
            try:
                self.step()
            except KeyboardInterrupt:
                raise
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
        cv2.imwrite(os.path.join(Config.OUT_DIR, "calibrate.png"), vis)
        logging.info("state=%s scout_loot=%s home_loot=%s end_btn=%s",
                     detect_state(img), read_loot_scout(img), read_loot_home(img),
                     end_button_visible(img))


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
    assert loot_enough({"Gold": 10**6, "Elixir": 10**6, "Dark": 10**4})
    assert loot_enough({"Gold": 0, "Elixir": 10**6, "Dark": 10**4}) == Config.ANY_TARGET
    assert not loot_enough({"Gold": 1, "Elixir": 2, "Dark": 10**4})
    assert not loot_enough({"Gold": None, "Elixir": None, "Dark": None})
    assert _parse_loot_text("1 320 758") == 1_320_758
    assert _parse_loot_text("8995 740") == 995_740
    assert _parse_loot_text("9 999 999") is None
    assert _parse_loot_text("12 34") is None
    print("loot gate ok")


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
