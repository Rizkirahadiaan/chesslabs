from datetime import datetime
import tkinter as tk
from tkinter import ttk

from .controller import LicenseStateController
from .manager import default_manager


class LicenseActivationWindow(tk.Toplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.title("Aktivasi ChessLab Pro")
        self.resizable(False, False)
        body = ttk.Frame(self, padding=22); body.pack(fill="both", expand=True)
        ttk.Label(body, text="Aktifkan ChessLab Pro", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(body, text="Aktivasi pertama membutuhkan internet. Masa lisensi dimulai setelah aktivasi.", wraplength=430).pack(anchor="w", pady=10)
        ttk.Label(body, text="Kunci lisensi").pack(anchor="w")
        self.key = tk.StringVar()
        self.entry = ttk.Entry(body, textvariable=self.key, width=52, show="•"); self.entry.pack(fill="x", pady=6)
        self.button = ttk.Button(body, text="Aktifkan / coba lagi", command=self.activate); self.button.pack(anchor="w", pady=6)
        self.progress = ttk.Progressbar(body, mode="indeterminate"); self.progress.pack(fill="x", pady=8)
        self.message = tk.StringVar(value=controller.manager.message)
        ttk.Label(body, textvariable=self.message, wraplength=430).pack(anchor="w")
        ttk.Button(body, text="Petunjuk perpanjangan", command=lambda: LicenseRenewalWindow(self, controller)).pack(anchor="w", pady=10)
        self.entry.focus_set()
        self.after(100, self.update_status)

    def activate(self):
        value = self.key.get().strip()
        if not value:
            self.message.set("Masukkan kunci lisensi."); return
        if self.controller.refresh(value):
            self.key.set("")
            self.message.set("Memvalidasi ke server…")

    def update_status(self):
        if self.controller.closed:
            self.destroy(); return
        busy = self.controller.future is not None
        self.button.configure(state="disabled" if busy else "normal")
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop(); self.message.set(self.controller.manager.message)
        if self.controller.manager.entitled:
            self.destroy(); return
        self.after(250, self.update_status)


class LicenseRenewalWindow(tk.Toplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.title("Perpanjangan lisensi")
        body = ttk.Frame(self, padding=22); body.pack(fill="both", expand=True)
        ttk.Label(body, text="Perpanjang ChessLab Pro", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        payload = controller.manager.payload
        identifier = payload["license"] if payload else self.license_id(controller)
        ttk.Label(body, text="ID lisensi: " + identifier, wraplength=440).pack(anchor="w", pady=10)
        ttk.Label(body, text=getattr(controller.manager, "renewal_instructions", "Hubungi penjual untuk konfirmasi pembayaran manual."), wraplength=440).pack(anchor="w", pady=10)
        ttk.Label(body, text="Lisensi kedaluwarsa menghentikan analisis. Setelah pembayaran dikonfirmasi, perbarui status.", wraplength=440).pack(anchor="w")
        ttk.Button(body, text="Perbarui status lisensi", command=controller.refresh).pack(anchor="w", pady=14)
        self.message = tk.StringVar()
        ttk.Label(body, textvariable=self.message, wraplength=440).pack(anchor="w")
        self.controller = controller
        self.after(250, self.tick)

    def tick(self):
        self.message.set(self.controller.manager.message)
        if not self.controller.closed: self.after(500, self.tick)

    @staticmethod
    def license_id(controller):
        try: return controller.manager.verifier.payload(controller.manager.cache["grant"])["license"]
        except Exception: return "Lihat bukti pembelian atau hubungi penjual."


class LicenseStatusPanel(ttk.Frame):
    def __init__(self, parent, manager, controller):
        super().__init__(parent)
        self.manager, self.controller = manager, controller
        self.text = tk.StringVar(value="Lisensi belum aktif")
        ttk.Label(self, textvariable=self.text, wraplength=620).pack(anchor="w")
        row = ttk.Frame(self); row.pack(anchor="w", pady=4)
        self.activation = None
        ttk.Button(row, text="Aktivasi", command=self.open_activation).pack(side="left")
        ttk.Button(row, text="Status / perpanjangan", command=lambda: LicenseRenewalWindow(self, controller)).pack(side="left", padx=6)
        ttk.Button(row, text="Validasi ulang", command=controller.refresh).pack(side="left")
        self.after(0, self.tick)

    def open_activation(self):
        if self.activation is None or not self.activation.winfo_exists():
            self.activation = LicenseActivationWindow(self, self.controller)
        self.activation.lift()

    def tick(self):
        if self.controller.closed: return
        payload = self.manager.payload
        if payload:
            stamp = lambda value: datetime.fromtimestamp(value).astimezone().strftime("%d/%m/%Y %H:%M %Z")
            now = self.manager.anchor[0] + self.manager.monotonic() - self.manager.anchor[1] if self.manager.anchor else self.manager.wall()
            remaining = max(0, int(payload["subscription_exp"] - now))
            self.text.set(f'{payload["edition"]} • Aktif • Perangkat terdaftar\nAktivasi: {stamp(payload["activated"])} | Berakhir: {stamp(payload["subscription_exp"])}\nSisa: {remaining//86400} hari {(remaining%86400)//3600} jam {(remaining%3600)//60} menit')
        else:
            self.text.set("Akses premium dinonaktifkan. " + self.manager.message)
        self.after(1000, self.tick)


def install_license_ui(coach, body):
    try:
        manager = default_manager()
    except Exception:
        ttk.Label(body, text="Konfigurasi lisensi belum lengkap. Hubungi pengelola untuk URL API dan kunci publik.", wraplength=620).pack(anchor="w")
        coach.license_manager = None
        return
    coach.license_manager = manager

    coach.license_controller = LicenseStateController(coach.root, manager, coach._license_changed)
    panel = LicenseStatusPanel(body, manager, coach.license_controller)
    panel.pack(fill="x", pady=6)
    coach.license_panel = panel
    if not manager.entitled: coach.root.after(350, panel.open_activation)
