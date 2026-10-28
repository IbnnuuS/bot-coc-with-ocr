"""GUI Control Panel Clash of Clans Bot (CustomTkinter + ADB/OCR).

Menyediakan UI modern & clean untuk memantau state, loot, konfigurasi filter,
strategi deploy, dan logs secara real-time.
"""

import logging
import os
import sys
import threading
import time
import customtkinter as ctk

# Ensure working directory / imports
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from bot import Bot, Config


class TextboxLogHandler(logging.Handler):
    """Logging handler yang mengirim baris log ke CTkTextbox via root.after."""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        try:
            msg = self.format(record)
            self.callback(msg)
        except Exception:
            pass


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CoC Auto Farmer — ADB + OCR")
        self.geometry("920x660")
        self.minsize(860, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.bot = Bot()
        self.bot_thread = None

        self._build_ui()
        self._setup_logging()
        self._start_stats_poller()

    def _build_ui(self):
        # Grid layout 1x2 (Sidebar kiri, Dashboard kanan)
        self.grid_columnconfigure(0, weight=0, minsize=320)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ================= LEFT SIDEBAR (SETTINGS) =================
        self.sidebar = ctk.CTkScrollableFrame(self, corner_radius=0, width=320)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # Title / Brand
        lbl_title = ctk.CTkLabel(self.sidebar, text="CoC Auto Farmer",
                                 font=ctk.CTkFont(size=20, weight="bold"))
        lbl_title.grid(row=0, column=0, padx=16, pady=(16, 2), sticky="w")

        lbl_sub = ctk.CTkLabel(self.sidebar, text="ADB + OCR Intelligent Engine",
                               font=ctk.CTkFont(size=11), text_color="gray60")
        lbl_sub.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="w")

        # --- Card 1: Target Loot ---
        card_loot = ctk.CTkFrame(self.sidebar, corner_radius=10)
        card_loot.grid(row=2, column=0, padx=12, pady=6, sticky="ew")
        card_loot.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card_loot, text="🎯 TARGET LOOTING",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color="#38bdf8").grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 8), sticky="w")

        ctk.CTkLabel(card_loot, text="Mode:").grid(row=1, column=0, padx=12, pady=4, sticky="w")
        self.opt_mode = ctk.CTkOptionMenu(
            card_loot,
            values=["GOLD_OR_ELIXIR", "GOLD_AND_ELIXIR", "GOLD_ONLY", "ELIXIR_ONLY", "DE_ONLY"],
            command=self._on_loot_mode_change
        )
        self.opt_mode.set(Config.LOOT_MODE)
        self.opt_mode.grid(row=1, column=1, padx=12, pady=4, sticky="ew")

        ctk.CTkLabel(card_loot, text="Min Gold:").grid(row=2, column=0, padx=12, pady=4, sticky="w")
        self.entry_gold = ctk.CTkEntry(card_loot, placeholder_text="900000")
        self.entry_gold.insert(0, str(Config.TARGETS.get("Gold", 900_000)))
        self.entry_gold.grid(row=2, column=1, padx=12, pady=4, sticky="ew")

        ctk.CTkLabel(card_loot, text="Min Elixir:").grid(row=3, column=0, padx=12, pady=4, sticky="w")
        self.entry_elixir = ctk.CTkEntry(card_loot, placeholder_text="900000")
        self.entry_elixir.insert(0, str(Config.TARGETS.get("Elixir", 900_000)))
        self.entry_elixir.grid(row=3, column=1, padx=12, pady=4, sticky="ew")

        ctk.CTkLabel(card_loot, text="Min Dark:").grid(row=4, column=0, padx=12, pady=(4, 12), sticky="w")
        self.entry_dark = ctk.CTkEntry(card_loot, placeholder_text="5000")
        self.entry_dark.insert(0, str(Config.TARGETS.get("Dark", 5_000)))
        self.entry_dark.grid(row=4, column=1, padx=12, pady=(4, 12), sticky="ew")

        # --- Card 2: Serangan & Strategi ---
        card_strat = ctk.CTkFrame(self.sidebar, corner_radius=10)
        card_strat.grid(row=3, column=0, padx=12, pady=6, sticky="ew")
        card_strat.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card_strat, text="⚔️ STRATEGI SERANGAN",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color="#f59e0b").grid(row=0, column=0, padx=12, pady=(10, 6), sticky="w")

        ctk.CTkLabel(card_strat, text="Model Deploy / Sisi:").grid(row=1, column=0, padx=12, pady=(2, 4), sticky="w")
        self.opt_deploy = ctk.CTkOptionMenu(
            card_strat,
            values=[
                "Smart Attack (Auto Cari Storage)",
                "Rata Kiri Atas",
                "Rata Kanan Atas",
                "Rata Kiri Bawah (Pantai)",
                "Rata Kanan Bawah",
                "Sebar Rata 4 Sisi",
            ],
            command=self._on_opt_change
        )
        self.opt_deploy.set("Smart Attack (Auto Cari Storage)")
        self.opt_deploy.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="ew")

        self.sw_auto_end = ctk.CTkSwitch(card_strat, text="Auto End Battle (Loot Habis)",
                                         command=self._on_switch_change)
        if Config.END_IF_LOOT_EMPTY:
            self.sw_auto_end.select()
        self.sw_auto_end.grid(row=3, column=0, padx=12, pady=4, sticky="w")

        self.sw_auto_collect = ctk.CTkSwitch(card_strat, text="Auto Collector (Home Base)",
                                             command=self._on_switch_change)
        if Config.AUTO_COLLECT:
            self.sw_auto_collect.select()
        self.sw_auto_collect.grid(row=4, column=0, padx=12, pady=4, sticky="w")

        self.sw_auto_reconnect = ctk.CTkSwitch(card_strat, text="Auto Reconnect & Pop-up",
                                               command=self._on_switch_change)
        if Config.AUTO_RECONNECT:
            self.sw_auto_reconnect.select()
        self.sw_auto_reconnect.grid(row=5, column=0, padx=12, pady=(4, 12), sticky="w")

        # --- Card 3: Upgrade Wall ---
        card_wall = ctk.CTkFrame(self.sidebar, corner_radius=10)
        card_wall.grid(row=4, column=0, padx=12, pady=6, sticky="ew")
        card_wall.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card_wall, text="🧱 AUTO UPGRADE WALL",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color="#ec4899").grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 8), sticky="w")

        ctk.CTkLabel(card_wall, text="Mode:").grid(row=1, column=0, padx=12, pady=4, sticky="w")
        self.opt_wall = ctk.CTkOptionMenu(
            card_wall,
            values=["OFF", "1X_PER_LOOP", "ALWAYS_CHECK_LIMIT"],
            command=self._on_opt_change
        )
        self.opt_wall.set(Config.UPGRADE_WALL_MODE)
        self.opt_wall.grid(row=1, column=1, padx=12, pady=4, sticky="ew")

        ctk.CTkLabel(card_wall, text="Keep Gold:").grid(row=2, column=0, padx=12, pady=4, sticky="w")
        self.entry_wall_gold = ctk.CTkEntry(card_wall, placeholder_text="2000000")
        self.entry_wall_gold.insert(0, str(Config.WALL_GOLD_LIMIT))
        self.entry_wall_gold.grid(row=2, column=1, padx=12, pady=4, sticky="ew")

        ctk.CTkLabel(card_wall, text="Keep Elixir:").grid(row=3, column=0, padx=12, pady=(4, 12), sticky="w")
        self.entry_wall_elixir = ctk.CTkEntry(card_wall, placeholder_text="2000000")
        self.entry_wall_elixir.insert(0, str(Config.WALL_ELIXIR_LIMIT))
        self.entry_wall_elixir.grid(row=3, column=1, padx=12, pady=(4, 12), sticky="ew")

        # --- Card 4: Auto Stop & Protection ---
        card_stop = ctk.CTkFrame(self.sidebar, corner_radius=10)
        card_stop.grid(row=5, column=0, padx=12, pady=6, sticky="ew")
        card_stop.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card_stop, text="🛡️ AUTO STOP & LIMIT",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      text_color="#a855f7").grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 8), sticky="w")

        self.sw_auto_stop = ctk.CTkSwitch(card_stop, text="Aktifkan Auto Stop",
                                          command=self._on_switch_change)
        if Config.AUTO_STOP_ENABLED:
            self.sw_auto_stop.select()
        self.sw_auto_stop.grid(row=1, column=0, columnspan=2, padx=12, pady=4, sticky="w")

        ctk.CTkLabel(card_stop, text="Timer (menit):").grid(row=2, column=0, padx=12, pady=4, sticky="w")
        self.entry_stop_min = ctk.CTkEntry(card_stop, placeholder_text="0 (nonaktif)")
        self.entry_stop_min.insert(0, str(Config.AUTO_STOP_MINUTES))
        self.entry_stop_min.grid(row=2, column=1, padx=12, pady=4, sticky="ew")

        ctk.CTkLabel(card_stop, text="Cap Gold:").grid(row=3, column=0, padx=12, pady=4, sticky="w")
        self.entry_stop_gold = ctk.CTkEntry(card_stop, placeholder_text="0 (nonaktif)")
        self.entry_stop_gold.insert(0, str(Config.STOP_GOLD_CAP))
        self.entry_stop_gold.grid(row=3, column=1, padx=12, pady=4, sticky="ew")

        ctk.CTkLabel(card_stop, text="Cap Elixir:").grid(row=4, column=0, padx=12, pady=(4, 12), sticky="w")
        self.entry_stop_elixir = ctk.CTkEntry(card_stop, placeholder_text="0 (nonaktif)")
        self.entry_stop_elixir.insert(0, str(Config.STOP_ELIXIR_CAP))
        self.entry_stop_elixir.grid(row=4, column=1, padx=12, pady=(4, 12), sticky="ew")

        # --- Card 5: Action Controls ---
        card_act = ctk.CTkFrame(self.sidebar, corner_radius=10)
        card_act.grid(row=6, column=0, padx=12, pady=6, sticky="ew")
        card_act.grid_columnconfigure(0, weight=1)

        self.btn_start = ctk.CTkButton(
            card_act, text="▶ START BOT",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#10b981", hover_color="#059669", height=40,
            command=self.start_bot
        )
        self.btn_start.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")

        self.btn_stop = ctk.CTkButton(
            card_act, text="⏹ STOP BOT",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#ef4444", hover_color="#dc2626", height=38,
            state="disabled",
            command=self.stop_bot
        )
        self.btn_stop.grid(row=1, column=0, padx=12, pady=6, sticky="ew")

        self.btn_calibrate = ctk.CTkButton(
            card_act, text="🔍 Ambil Snapshot / Kalibrasi",
            font=ctk.CTkFont(size=12),
            fg_color="#334155", hover_color="#475569", height=32,
            command=self.run_calibrate
        )
        self.btn_calibrate.grid(row=2, column=0, padx=12, pady=(6, 12), sticky="ew")

        # ================= RIGHT DASHBOARD & LOGS =================
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Top Stats Row
        stats_frame = ctk.CTkFrame(self.main_frame, corner_radius=10)
        stats_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for i in range(4):
            stats_frame.grid_columnconfigure(i, weight=1)

        # Card: Status
        f_st = ctk.CTkFrame(stats_frame, fg_color="#1e293b", corner_radius=8)
        f_st.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(f_st, text="STATUS", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray60").pack(pady=(6, 0))
        self.lbl_status = ctk.CTkLabel(f_st, text="IDLE", font=ctk.CTkFont(size=15, weight="bold"), text_color="#94a3b8")
        self.lbl_status.pack(pady=(0, 6))

        # Card: Current State
        f_state = ctk.CTkFrame(stats_frame, fg_color="#1e293b", corner_radius=8)
        f_state.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(f_state, text="CURRENT STATE", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray60").pack(pady=(6, 0))
        self.lbl_state = ctk.CTkLabel(f_state, text="-", font=ctk.CTkFont(size=15, weight="bold"), text_color="#38bdf8")
        self.lbl_state.pack(pady=(0, 6))

        # Card: Total Attacks
        f_att = ctk.CTkFrame(stats_frame, fg_color="#1e293b", corner_radius=8)
        f_att.grid(row=0, column=2, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(f_att, text="TOTAL ATTACKS", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray60").pack(pady=(6, 0))
        self.lbl_attacks = ctk.CTkLabel(f_att, text="0", font=ctk.CTkFont(size=15, weight="bold"), text_color="#facc15")
        self.lbl_attacks.pack(pady=(0, 6))

        # Card: Last Loot
        f_loot = ctk.CTkFrame(stats_frame, fg_color="#1e293b", corner_radius=8)
        f_loot.grid(row=0, column=3, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(f_loot, text="LAST ATTACK LOOT", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray60").pack(pady=(6, 0))
        self.lbl_loot = ctk.CTkLabel(f_loot, text="Belum ada", font=ctk.CTkFont(size=11), text_color="#4ade80")
        self.lbl_loot.pack(pady=(0, 6))

        # Center/Bottom: Live Log Viewer
        log_container = ctk.CTkFrame(self.main_frame, corner_radius=10)
        log_container.grid(row=1, column=0, sticky="nsew")
        log_container.grid_columnconfigure(0, weight=1)
        log_container.grid_rowconfigure(1, weight=1)

        log_head = ctk.CTkFrame(log_container, fg_color="transparent")
        log_head.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        log_head.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(log_head, text="📜 Live Activity Log",
                      font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")

        btn_clear = ctk.CTkButton(log_head, text="Clear", width=60, height=24,
                                  fg_color="#334155", hover_color="#475569",
                                  command=self.clear_logs)
        btn_clear.grid(row=0, column=1, sticky="e")

        self.txt_log = ctk.CTkTextbox(log_container, font=ctk.CTkFont(family="Consolas", size=12),
                                      activate_scrollbars=True)
        self.txt_log.grid(row=1, column=0, sticky="nsew", padx=12, pady=(4, 12))

    def _setup_logging(self):
        handler = TextboxLogHandler(self._append_log_safe)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

    def _append_log_safe(self, message):
        self.after(0, lambda: self._append_log(message))

    def _append_log(self, message):
        self.txt_log.insert("end", message + "\n")
        self.txt_log.see("end")

    def clear_logs(self):
        self.txt_log.delete("1.0", "end")

    def _sync_config(self):
        """Ambil value dari UI dan terapkan ke Config."""
        Config.LOOT_MODE = self.opt_mode.get()
        try:
            Config.TARGETS["Gold"] = int(self.entry_gold.get().replace("_", "").replace(",", "").strip())
        except ValueError:
            pass
        try:
            Config.TARGETS["Elixir"] = int(self.entry_elixir.get().replace("_", "").replace(",", "").strip())
        except ValueError:
            pass
        try:
            Config.TARGETS["Dark"] = int(self.entry_dark.get().replace("_", "").replace(",", "").strip())
        except ValueError:
            pass

        strat_val = self.opt_deploy.get()
        if "Smart" in strat_val:
            Config.ATTACK_STRATEGY = "SMART"
        elif "Kiri Atas" in strat_val:
            Config.ATTACK_STRATEGY = "KIRI_ATAS"
        elif "Kanan Atas" in strat_val:
            Config.ATTACK_STRATEGY = "KANAN_ATAS"
        elif "Kiri Bawah" in strat_val:
            Config.ATTACK_STRATEGY = "KIRI_BAWAH"
        elif "Kanan Bawah" in strat_val:
            Config.ATTACK_STRATEGY = "KANAN_BAWAH"
        elif "4 Sisi" in strat_val:
            Config.ATTACK_STRATEGY = "FOUR_SIDES"
        else:
            Config.ATTACK_STRATEGY = "SMART"

        Config.END_IF_LOOT_EMPTY = bool(self.sw_auto_end.get())
        Config.AUTO_COLLECT = bool(self.sw_auto_collect.get())
        Config.AUTO_RECONNECT = bool(self.sw_auto_reconnect.get())

        # Upgrade wall
        Config.UPGRADE_WALL_MODE = self.opt_wall.get()
        try:
            Config.WALL_GOLD_LIMIT = int(self.entry_wall_gold.get().replace("_", "").replace(",", "").strip())
        except ValueError:
            pass
        try:
            Config.WALL_ELIXIR_LIMIT = int(self.entry_wall_elixir.get().replace("_", "").replace(",", "").strip())
        except ValueError:
            pass

        # Auto stop
        Config.AUTO_STOP_ENABLED = bool(self.sw_auto_stop.get())
        try:
            Config.AUTO_STOP_MINUTES = int(self.entry_stop_min.get().replace("_", "").replace(",", "").strip())
        except ValueError:
            pass
        try:
            Config.STOP_GOLD_CAP = int(self.entry_stop_gold.get().replace("_", "").replace(",", "").strip())
        except ValueError:
            pass
        try:
            Config.STOP_ELIXIR_CAP = int(self.entry_stop_elixir.get().replace("_", "").replace(",", "").strip())
        except ValueError:
            pass

    def _on_opt_change(self, choice):
        self._sync_config()

    def _on_loot_mode_change(self, choice):
        self._sync_config()
        logging.info("Loot Mode -> %s", choice)

    def _on_deploy_mode_change(self, choice):
        self._sync_config()
        logging.info("Deploy Mode -> %s", choice)

    def _on_switch_change(self):
        self._sync_config()

    def start_bot(self):
        if self.bot.running:
            return
        self._sync_config()
        self.bot.running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.lbl_status.configure(text="RUNNING", text_color="#10b981")

        self.bot_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.bot_thread.start()
        logging.info("Bot dimulai. Target: Gold >= %s, Elixir >= %s [%s] | Strategi: %s",
                     f"{Config.TARGETS['Gold']:,}", f"{Config.TARGETS['Elixir']:,}", Config.LOOT_MODE, Config.ATTACK_STRATEGY)
        if Config.AUTO_STOP_ENABLED and Config.AUTO_STOP_MINUTES > 0:
            logging.info("[AUTO STOP] Timer aktif: berhenti setelah %d menit", Config.AUTO_STOP_MINUTES)
        if Config.UPGRADE_WALL_MODE != "OFF":
            logging.info("[WALL] Mode: %s (Simpan min: G=%s, E=%s)",
                         Config.UPGRADE_WALL_MODE, f"{Config.WALL_GOLD_LIMIT:,}", f"{Config.WALL_ELIXIR_LIMIT:,}")

    def stop_bot(self):
        self.bot.stop()
        self.lbl_status.configure(text="STOPPING...", text_color="#f59e0b")
        self.btn_stop.configure(state="disabled")

        def _wait():
            if self.bot_thread:
                self.bot_thread.join(timeout=3.0)
            self.after(0, self._on_stopped)

        threading.Thread(target=_wait, daemon=True).start()

    def _on_stopped(self):
        self.lbl_status.configure(text="IDLE", text_color="#94a3b8")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        logging.info("Bot dihentikan.")

    def _run_loop(self):
        try:
            self.bot.loop()
        finally:
            self.bot.running = False
            self.after(0, self._on_stopped)

    def run_calibrate(self):
        self._sync_config()
        logging.info("Menjalankan snapshot kalibrasi...")
        threading.Thread(target=self.bot.calibrate, daemon=True).start()

    def _start_stats_poller(self):
        def _poll():
            if self.bot:
                st = getattr(self.bot, "current_state", "-")
                self.lbl_state.configure(text=st)
                self.lbl_attacks.configure(text=str(getattr(self.bot, "total_attacks", 0)))
                loot = getattr(self.bot, "last_loot", {})
                if loot:
                    g = loot.get("Gold") or 0
                    e = loot.get("Elixir") or 0
                    d = loot.get("Dark") or 0
                    self.lbl_loot.configure(text=f"G:{g//1000}k | E:{e//1000}k | DE:{d}")
            self.after(1000, _poll)

        self.after(1000, _poll)


if __name__ == "__main__":
    app = App()
    app.mainloop()
