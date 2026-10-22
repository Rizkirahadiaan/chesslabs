# Asesmen awal platform lisensi

Tanggal: 22 Oktober 2026. Workspace ini tidak memiliki metadata Git.

## Struktur dan alur aplikasi

- `src/chesslab/cli.py`: entry point `chesslab`; perintah `coach` dan `analyze` memulai analisis.
- `src/chesslab/coach.py`: `Coach.__init__` membuat `tk.Tk`, widget ttk, overlay, hotkey, dua ThreadPoolExecutor (visi dan pencarian papan), serta AnalysisService.
- `Coach.start` memulai pemantauan; `_request_advice` mengirim analisis; `_engine_tick` menerima hasil; `_show_advice` memperbarui overlay. `pause` mengubah generation agar hasil lama dibuang; `close` menghentikan executor, mesin, hotkey, dan Tk.
- `src/chesslab/engine.py`: AnalysisService mempertahankan mesin dan executor sendiri. Tidak perlu mengubah algoritma mesin.
- `src/chesslab/config.py`: dataclass Settings, JSON relatif terhadap lokasi berkas. Preferensi ditulis kembali oleh Coach.
- `src/chesslab/portable.py`: penyalinan aset pertama kali, log stdout/stderr ke `runtime/portable.log`, pemeriksaan paket.
- `packaging/build_portable.py`: PyInstaller satu EXE, aset Stockfish/template eksplisit. `Build-Portable.cmd` adalah launcher build.
- `tests/`: pytest untuk catur, visi, rekomendasi, overlay, dan paket. Virtual environment Python 3.13 tersedia; proyek mensyaratkan 3.11+.
- `android/`: produk terpisah, di luar integrasi lisensi Windows ini.

## Dependensi dan kompatibilitas

Dependensi awal: python-chess, OpenCV, NumPy, Pillow; PyInstaller dan pytest terpasang. Belum ada server, basis data, autentikasi, atau dashboard. Nama folder `licenses` pada paket lama berisi pemberitahuan lisensi dependensi, bukan kredensial pelanggan. Empat subfolder template tidak dapat dibaca oleh sandbox; aset tersebut tidak akan diubah.

## Titik integrasi

Tambahkan pustaka lisensi independen di `src/chesslab/licensing`. Buat controller setelah widget/overlay tersedia, gunakan executor jaringan terpisah agar timeout tidak menghambat visi. Poll Future hanya melalui `root.after` dari thread Tk; worker tidak memanggil Tk. Periksa entitlement sebelum start, pengiriman analisis, dan penayangan hasil. Saat entitlement hilang, pause dan hapus rekomendasi. CLI analyze juga memeriksa lisensi. Tetap sediakan kalibrasi, konfigurasi, ekspor, aktivasi, dan perpanjangan.

## Risiko dan keputusan

Pemeriksaan lisensi mengubah perilaku mulai otomatis secara sengaja: instalasi tanpa aktivasi tidak boleh menganalisis. Konfigurasi server/kunci publik wajib; tidak ada mode produksi yang melewati lisensi. Uji algoritma lama yang membangun objek melalui `__new__` harus tetap dapat menguji unit terisolasi. Cache Windows memakai DPAPI untuk pengguna saat ini; penyalinan folder ke PC lain tidak memindahkan entitlement. Seluruh jam server UTC; tampilan lokal menggunakan zona sistem. Lisensi offline pada komputer tidak tepercaya tidak dapat kebal terhadap modifikasi biner, snapshot, atau administrator lokal.

## Urutan pelaksanaan

1. Rekam baseline pytest dan inventaris kode (dokumen ini).
2. Buat model PostgreSQL, migrasi, servis transaksi, grant Ed25519, session admin dan API.
3. Buat verifier/cache/identitas perangkat/controller Tk dan integrasikan pada batas analisis.
4. Buat dashboard Next.js dengan operasi API sebenarnya.
5. Uji keamanan/lifecycle termasuk penguncian PostgreSQL.
6. Siapkan Compose, bootstrap, backup, build Windows, dokumentasi dan laporan hasil aktual.
