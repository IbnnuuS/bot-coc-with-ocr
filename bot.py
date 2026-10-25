"""CoC bot — ADB + sendevent edition (UI CoC 2026, LDPlayer).

`input tap` diblokir CoC untuk tombol konfirmasi, jadi tap dikirim sebagai
event touchscreen mentah (protocol B) via `sendevent` — terbukti lolos.

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
        "Gold":   (98, 130, 295, 175),
        "Elixir": (98, 192, 295, 237),
        "Dark":   (98, 252, 295, 295),
    }
    # bar loot sendiri (home): kanan-atas
    REGION_HOME = {
        "Gold":   (1560,  28, 1836,  76),
        "Elixir": (1560, 110, 1836, 154),
        "Dark":   (1560, 185, 1836, 228),
    }
    OCR_SMAX, OCR_VMIN = 70, 215
    TARGETS = {"Gold": 800_000, "Elixir": 800_000}   # Dark tidak difilter

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
    BTN_NEXT     = (1749, 769)   # Next: ganti base tanpa keluar (loot berubah saat diuji)
    BTN_END      = (180, 795)    # "End Battle" merah kiri-bawah saat scout/battle
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
    AD_FALLBACK = (930, 520)        # titik jatuh petir kalau AD tak terdeteksi (tengah base)
    BASE_ROI = (260, 130, 1600, 870)  # area base saat scout (tanpa UI)
    DEPLOY_POINT = (140, 520)       # rumput tepi pantai (100% di luar batas base manapun)
    DEPLOY_SPREAD = (20, 45)

    # deteksi tombol End Battle: blob merah kiri-bawah (UI baru tidak punya Next)
    END_ROI = (0, 740, 350, 880)

    POLL = 0.5
    BATTLE_WAIT = 210            # max detik tunggu battle selesai (3 menit + margin)
    PREP_TIMEOUT = 60            # countdown "Battle starts in" ~30 detik
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

    # ---- sendevent touchscreen (protocol B), node range 1280x720 ----
    TOUCH = "/dev/input/event4"

    def tap(self, gx, gy, hold=0.06):
        x, y = int(gx * 2 / 3), int(gy * 2 / 3)
        e = self.TOUCH
        seq = [
            f"sendevent {e} 3 47 0",          # MT_SLOT 0
            f"sendevent {e} 3 57 100",        # TRACKING_ID
            f"sendevent {e} 3 53 {x}",        # POSITION_X
            f"sendevent {e} 3 54 {y}",        # POSITION_Y
            f"sendevent {e} 3 58 1",          # PRESSURE
            f"sendevent {e} 1 330 1",         # BTN_TOUCH down
            f"sendevent {e} 0 0 0",
            f"sleep {hold}",
            f"sendevent {e} 3 47 0",
            f"sendevent {e} 3 57 4294967295", # tracking -1 = lepas
            f"sendevent {e} 1 330 0",
            f"sendevent {e} 0 0 0",
        ]
        self.shell(" ; ".join(seq))


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


def ocr_number(img, roi, smax=Config.OCR_SMAX, vmin=Config.OCR_VMIN, plain=False):
    """plain=True: angka putih polos (panel Available Loot) — threshold biasa."""
    x1, y1, x2, y2 = roi
    crop = img[y1:y2, x1:x2]
    if plain:
        up = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), None,
                        fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        bw = cv2.threshold(up, 180, 255, cv2.THRESH_BINARY)[1]
    else:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        m = ((hsv[:, :, 1] < smax) & (hsv[:, :, 2] > vmin)).astype(np.uint8) * 255
        bw = cv2.resize(m, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    txt = pytesseract.image_to_string(
        bw, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789")
    digits = re.sub(r"\D", "", txt)
    return int(digits) if digits else None


def read_loot_scout(img):
    """Membaca loot CoC format 3 digit berspasi (misal: 1 000 000, 800 000)."""
    out = {}
    for k, roi in Config.REGION_LOOT.items():
        x1, y1, x2, y2 = roi
        crop = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        up = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
        th = cv2.threshold(up, 175, 255, cv2.THRESH_BINARY)[1]
        raw = pytesseract.image_to_string(
            th, config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789 "
        ).strip()
        cleaned = re.sub(r"[^0-9]", "", raw)
        out[k] = int(cleaned) if cleaned else None
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


def find_air_defenses(img):
    """Deteksi Air Defense via template multi-skala (templates/ad_new.png).
    Return list (cx, cy)."""
    x1, y1, x2, y2 = Config.BASE_ROI
    crop = img[y1:y2, x1:x2]
    g0 = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gt = cv2.cvtColor(cv2.imread(os.path.join(os.path.dirname(__file__), "templates", "ad_new.png")),
                      cv2.COLOR_BGR2GRAY)
    hits = []
    for s in np.arange(0.7, 1.45, 0.1):
        t = cv2.resize(gt, None, fx=s, fy=s)
        if t.shape[0] >= g0.shape[0] or t.shape[1] >= g0.shape[1]:
            continue
        r = cv2.matchTemplate(g0, t, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(r >= 0.50)
        for y, x in zip(ys, xs):
            hits.append((float(r[y, x]), x + x1 + t.shape[1] // 2, y + y1 + t.shape[0] // 2))
    hits.sort(reverse=True)
    kept = []
    for sc, cx, cy in hits:
        if all(abs(cx - a) > 40 or abs(cy - b) > 40 for _, a, b in kept):
            kept.append((sc, cx, cy))
    out = [(c[1], c[2]) for c in kept[:4]]
    if out:
        return out
    # fallback heuristik lama (tip roket merah) kalau template nihil
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array([0, 170, 170], np.uint8), np.array([8, 255, 255], np.uint8))
    m |= cv2.inRange(hsv, np.array([172, 170, 170], np.uint8), np.array([180, 255, 255], np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if not (8 < w < 70 and 8 < h < 70 and cv2.contourArea(c) > 40):
            continue
        cx, cy = x + w // 2 + x1, y + h // 2 + y1
        bx1, bx2 = max(0, cx - 20 - x1), cx + 20 - x1
        by1, by2 = y + h // 2 + 10, y + h // 2 + 45
        body = hsv[by1:by2, bx1:bx2]
        if body.size and ((body[:, :, 1] < 60) & (body[:, :, 2] > 120)).mean() > 0.15:
            out.append((cx, cy))
    out.sort()
    merged = []
    for p in out:
        if merged and abs(p[0] - merged[-1][0]) < 30 and abs(p[1] - merged[-1][1]) < 30:
            continue
        merged.append(p)
    return merged[:4]


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
    return all((loot.get(k) or 0) >= t for k, t in Config.TARGETS.items())


# ============================================================
#  BOT
# ============================================================
class Bot:
    def __init__(self):
        self.adb = Adb()
        os.makedirs(Config.OUT_DIR, exist_ok=True)
        self._csv_new = not os.path.exists(Config.CSV)

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

    def wait_prep_end(self):
        """Tunggu countdown "Battle starts in" (~30 dtk) sebelum deploy.
        Selesai = kata 'starts' hilang dari layar atas. Deploy dipicu
        seketika setelah countdown habis (poll 1 dtk)."""
        t0 = time.time()
        while time.time() - t0 < Config.PREP_TIMEOUT:
            img = self.snap()
            if img is None:
                time.sleep(1)
                continue
            if "starts" not in top_text(img):
                logging.info("prep selesai (%.0fs)", time.time() - t0)
                return
            time.sleep(1)
        logging.info("prep timeout; lanjut deploy")

    # ---------------- aksi ----------------
    def cast_lightning(self, img):
        """Petir ke tiap Air Defense yang terdeteksi. SEMUA 11 spell petir digunakan habis."""
        ads = find_air_defenses(img)
        if not ads:
            ads = [Config.AD_FALLBACK]
            logging.info("Air Defense tidak terdeteksi, fallback ke %s", ads)
        dbg = img.copy()
        for cx, cy in ads:
            cv2.circle(dbg, (cx, cy), 40, (0, 0, 255), 3)
        cv2.imwrite(os.path.join(Config.OUT_DIR, "ad_detect.png"), dbg)
        logging.info("Air Defense: %s (cast %d petir)", ads, Config.TOTAL_LIGHTNING)

        # Pilih kartu petir di slot 7
        self.adb.tap(*Config.SPELL_SLOT)
        time.sleep(0.3)
        # Distribusikan seluruh 11 petir ke AD secara merata
        for i in range(Config.TOTAL_LIGHTNING):
            cx, cy = ads[i % len(ads)]
            jx, jy = np.random.randint(-12, 12), np.random.randint(-12, 12)
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
            enough = loot_enough(loot)
            logging.info("loot=%s cukup=%s", loot, enough)
            self.log_csv(loot, enough)
            if enough:
                logging.info("Loot target terpenuhi! Langsung serang!")
                self.deploy()                  # 1-6: naga x10, wall wrecker, BK, AQ, GW, RC (langsung trigger battle)
                self.cast_lightning(img)       # 7: semua 11 petir ke Air Defense
                time.sleep(3)
                self.wait_battle_end()
            else:
                # Next: ganti base langsung (tanpa keluar ke home)
                self.adb.tap(*Config.BTN_NEXT)
                time.sleep(Config.TAP_DELAY_NEXT)
        else:
            # UNKNOWN: layar hasil (Return Home) / dialog; tap tombol + tengah
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
    assert not loot_enough({"Gold": 0, "Elixir": 10**6, "Dark": 10**4})
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
