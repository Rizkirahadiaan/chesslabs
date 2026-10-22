# Laporan pemulihan build ChessLab PC — 22 Oktober 2026

Pekerjaan dilakukan pada branch `fix/windows-build-bootstrap`, dari commit dasar
`47166195e6502d0b0234d1b9e0678ac8f362c60f`. Laporan awal ini dibuat sebelum commit
dan publikasi; proses rilis lanjutan mengikuti `github-release-guide.md`.
Perubahan pengguna yang sudah ada pada `.env.example` dan `.vscode/` dipertahankan.
Tidak ada deployment produksi, rotasi kunci, perubahan record lisensi nyata,
atau pemasangan paket Python global.

## 1. Akar masalah yang terverifikasi

| Temuan | Dampak dan penyelesaian |
| --- | --- |
| Hanya Python 3.14.2 tersedia pada awal pemeriksaan | Build sebelumnya belum memiliki kontrak interpreter/dependency. Python 3.13.17 x64 dipasang berdampingan di `.tools/python313/` dan `.venv` dibuat darinya. Python sistem tetap ada. |
| PyInstaller tidak ada di interpreter global | Setup kini memasang PyInstaller dan seluruh dependency build di `.venv`, dengan versi terkunci. |
| Editable global menunjuk checkout lama | Setup memasang ulang checkout aktif; preflight memeriksa lokasi tepat `src/chesslab/__init__.py`. Launcher mengabaikan user site dan PYTHONPATH/PYTHONHOME. |
| `config.json` tidak ada | Initializer membentuk config dari contoh dan Settings sebenarnya setelah aset/kunci publik valid, tanpa menimpa config lama. |
| Stockfish berada di luar Git | Engine ditemukan di folder `../stockfish/`, dengan sumber dan lisensi. Pengguna clone baru harus memprovision distribusi resmi lengkap. |
| Build lama hanya memeriksa sebagian aset dan belum otomatis memvalidasi hasil | Build kini mewajibkan preflight, audit arsip, uji UCI, seluruh kelas template dan smoke EXE sebelum mempromosikan output. |
| Rename folder smoke test pernah ditolak Windows setelah proses berakhir | Retry PermissionError dibatasi lima detik. Regresi memakai handle direktori Windows nyata; kegagalan persisten tetap menghentikan build. |

Python 3.14 bukan terbukti sebagai penyebab inkompatibilitas seluruh dependency:
PyInstaller mendukungnya sejak 6.15, dan dry-run resolusi seluruh lock pada 3.14.2
berhasil. Namun impor runtime dan build/smoke EXE pada 3.14 berstatus **NOT RUN**.
Jalur build yang diuji dan diterima saat ini adalah CPython 3.13 x64 standar.

## 2. Perubahan yang diterapkan

Alur `setup-windows.ps1` menyeleksi interpreter, membuat `.venv`, memasang lock,
memasang editable lokal, menjalankan pip check dan memvalidasi aset. Setup awal
clone baru berhenti secara eksplisit jika konfigurasi/aset belum diprovision,
setelah dependency berhasil dipasang. Pengulangan setup tidak menimpa konfigurasi.

`init-chesslab-config.ps1` menggunakan validator bersama, meminta path engine jika
perlu, dan menerbitkan config secara atomik setelah validasi. `preflight_build.py`
memberi PASS/FAIL/WARNING serta exit nonzero untuk kondisi kritis. Build tetap
memakai `packaging/build_portable.py` dan executable bernama `ChessLab-Coach.exe`.

Paket dibuat melalui staging baru dan input yang dipilih eksplisit. Audit arsip
lama dipertahankan dan diperluas dengan pemeriksaan manifest/hash, isi ZIP sumber,
nilai public key lengkap, konfigurasi relatif dan penolakan berkas rahasia.
Kegagalan validasi tidak mempromosikan EXE baru ke output final.

## 3. Berkas yang dibuat atau diubah

Berkas baru:

- `scripts/windows-common.ps1`
- `scripts/setup-windows.ps1`
- `scripts/init-chesslab-config.ps1`
- `scripts/init_chesslab_config.py`
- `scripts/preflight_build.py`
- `scripts/build_support.py`
- `scripts/build-windows.ps1`
- `scripts/verify_local_license.py`
- `requirements-windows.lock`
- `tests/test_windows_build.py`
- `docs/windows-build-guide.md`
- `docs/windows-build-recovery-report.md`

Berkas tracked yang diubah:

- `.gitignore`, `pyproject.toml`, `requirements-build.txt`, `config.example.json`
- `Build-Portable.cmd`, `Start-Coach.cmd`, `README.md`
- `packaging/build_portable.py`, `packaging/check_license_bundle.py`
- `packaging/verify_portable.py`, `packaging/BACA-DULU.txt`
- `src/chesslab/config.py` (dukungan UTF-8 BOM dari alat Windows)
- `src/chesslab/portable.py` (tambahan pemeriksaan UI lisensi dalam self-test)

Berkas lokal yang dibuat dan diabaikan Git: `.tools/`, `.venv/`, `config.json`,
`work/`, dan `outputs/`. Konfigurasi publik dan private key yang sudah ada tidak
ditimpa atau diregenerasi. Log dan hasil pengujian berada di `work/`.

## 4. Perbaikan dependency

Versi utama terpasang: Python **3.13.17**, PyInstaller **6.22.3**, hooks **2026.9**,
NumPy **2.5.4**, OpenCV **5.0.0.93**, Pillow **13.0.0**, python-chess **1.999**
(chess **1.11.2**), cryptography **50.0.2**, httpx **0.28.1**, pytest **9.1.1**.
Dependency transitif, pip, setuptools dan wheel juga dipin di lock.
`pip check`, pemeriksaan versi lock dan impor library native lulus.
Pemasangan/editable global lama tetap utuh dan tidak dipakai untuk build.

## 5. Konfigurasi dan aset

Loader memakai folder config sebagai dasar seluruh path relatif. Field wajib
konfigurasi adalah `stockfish_path`, `allowed_window_titles`, dan `board`;
field/default lain mengikuti Settings. Validator menolak field asing/rahasia.

Stockfish lokal teridentifikasi sebagai **Stockfish 19**, berhasil handshake/ping
UCI dan menghasilkan langkah legal. Sebanyak **64 PNG tracked** terbaca sebagai
**13 kelas** template. Tidak ada template dummy atau engine pengganti untuk rilis.
Hanya kelas template yang dibaca aplikasi dibundel. Sumber Stockfish, Copying,
AUTHORS, README, lisensi Python dan pemberitahuan dependency dipertahankan.

Config dalam EXE memakai `engine/stockfish.exe`, `templates`, dan `runtime`;
path absolut mesin pengembang tidak dibawa dalam config distribusi. Saat startup,
data writable ditempatkan di `ChessLab-data/` di samping EXE, terpisah dari
resource onefile `_MEIPASS`. Preferensi tetap bertahan setelah relokasi.
Kecocokan visual template dengan tema papan UAT masih memerlukan pemeriksaan manual.

## 6. Hasil integrasi lisensi

| Pemeriksaan | Hasil |
| --- | --- |
| Endpoint publik | PASS — `http://localhost:8080` |
| ID public key | PASS — `ed25519-2026-01` |
| Pasangan public/private lokal | PASS — challenge non-grant ditandatangani dan diverifikasi hanya dalam memori |
| Fingerprint public key, ID dan origin container API | PASS — cocok dengan konfigurasi lokal |
| Server lokal `/healthz` | PASS — HTTP 200; service Compose sehat saat diperiksa |
| Arsip EXE | PASS — konfigurasi publik cocok, manifest/hash sesuai, tidak ada berkas private key/.env/konfigurasi server atau modul backend terlarang |
| Startup tanpa cache aktivasi | PASS — UI Aktivasi tersedia dan premium terkunci |
| Responsivitas Tk saat latensi/error jaringan | PASS — pengujian worker dan heartbeat Tk lama tetap lulus |
| Aktivasi online dengan lisensi QA nyata | **NOT RUN** — kunci/kredensial QA khusus belum disediakan |
| Lifecycle online lengkap | **NOT RUN** — membutuhkan admin QA khusus; tidak mengubah record nyata |

Tidak ada pengurangan signature verification, masa berlaku, Origin Validation,
device binding, certificate verification atau entitlement enforcement.

## 7. Pengujian otomatis dan clone bersih

**185 passed**, tanpa kegagalan atau skip pada run akhir. Seluruh **146 tes lama**
tetap dijalankan. Tambahan **39 kasus** mencakup konfigurasi/engine/template hilang,
PNG rusak, key/API invalid, import salah checkout, versi/arsitektur interpreter
yang tidak didukung, kebocoran rahasia, pemeliharaan config pada pengulangan,
pasangan kunci, pembatasan output dan penguncian direktori Windows.

Uji integrasi clone memakai clone Git lokal bersih dari commit dasar ditambah
patch kerja ini, tanpa `.venv`, config atau rahasia pengguna. Setup pertama
berhasil memasang dependency lalu menolak konfigurasi/aset yang belum diprovision.
Setelah konfigurasi publik dan engine resmi diprovision, setup/preflight lulus;
initializer dan setup yang diulang mempertahankan hash config.
Ini bukan klaim bahwa perubahan sudah tersedia pada clone GitHub publik: patch
belum dipush. Clone pada komputer Windows lain tetap memerlukan patch/branch ini.

Bukti lokal: `work/tests-windows.xml`, `work/preflight.json`,
`work/license-local.json`, `work/fresh-clone-result.json`,
`work/fresh-clone-setup-complete.log`, `work/resolution-python314.json`.
Pemeriksaan whitespace berkas tugas lulus; perubahan `.env.example` milik pengguna
tidak dimodifikasi untuk menuntaskan pemeriksaan tersebut.

## 8. Hasil build Windows dan validasi EXE

Build sebenarnya dijalankan pada **Microsoft Windows 11 Pro x64 10.0.26200**.
PyInstaller membentuk onefile windowed, lalu audit dan smoke test lulus.
Smoke test mengeksekusi binary Windows nyata dengan Python dihapus dari PATH,
cwd berbeda, LOCALAPPDATA QA terpisah, dan cache lisensi kosong.

Pemeriksaan runtime lulus untuk Stockfish, langkah legal, 13 kelas template,
Coach Tk, overlay shadow/dots, mode Human, UI Aktivasi, dan premium terkunci.
EXE beserta data dipindahkan ke folder berspasi/non-ASCII dan diuji ulang;
preferensi yang diubah tetap dipertahankan. Log portable tidak mengandung traceback.
Tidak diperlukan Python global untuk menjalankan hasil EXE.

## 9. Lokasi hasil

Relatif terhadap root repositori:

```text
outputs/licensed/ChessLab-Coach.exe
outputs/licensed/BACA-DULU.txt
outputs/licensed/build-info.json
```

Lokasi EXE dihitung relatif terhadap checkout aktif, tanpa path pengguna tertentu.
Versi, source/payload hashes, endpoint, ID kunci, hasil validasi dan SHA-256 EXE
tersedia dalam `build-info.json`. Build log ada di `work/build-windows.log`;
laporan relokasi terbaru di `work/portable-verification/result.json`.

## 10. Batas verifikasi dan hal yang tersisa

- Aktivasi/lifecycle online memakai data QA: NOT RUN karena belum ada kunci/admin QA
  khusus yang disediakan. Tidak ada upaya mengambil kredensial admin atau memakai lisensi nyata.
- Windows 10 dan PC kedua: NOT RUN. Target didokumentasikan, tetapi pengujian aktual
  hanya pada Windows 11 di atas dan clone lokal terpisah.
- Python 3.14: resolusi dependency PASS; impor native, build dan smoke EXE NOT RUN.
- Validasi tema papan dan alur latihan manual: belum dilakukan; tergantung papan UAT.
- Keaslian sumber Stockfish terhadap binary diasumsikan dari distribusi lokal yang
  disediakan. File sumber/lisensi dan eksekusi UCI telah diverifikasi; sumber dan
  binary tidak dibangun ulang untuk membuktikan kesamaan secara independen.

Sandbox awal tidak dapat dimulai karena volume D: terkunci BitLocker. Pekerjaan
yang relevan berhasil dijalankan melalui eksekusi yang disetujui di luar sandbox;
tidak diperlukan pembukaan atau perubahan drive tersebut.

## 11. Langkah menyelesaikan UAT

1. Jalankan stack lokal di PC yang menjalankan EXE; pastikan endpoint dan pasangan
   kunci cocok dengan `scripts/verify_local_license.py`.
2. Minta pengelola menyediakan kunci lisensi **khusus QA** untuk `chesslab-pc`.
3. Buka EXE, aktivasi melalui UI, lalu periksa status aktif dan analisis pada papan
   latihan lokal dengan tema/ukuran template yang sesuai.
4. Tutup/buka kembali untuk memeriksa cache perangkat dan uji error jaringan dengan
   data QA. Lifecycle admin hanya diuji memakai record QA yang dibuat khusus.
5. Ulangi setup/build/smoke pada Windows 10 atau PC target lain bila termasuk matriks UAT.

Perintah build ulang utama: `.\scripts\build-windows.ps1`.
Panduan lengkap: [windows-build-guide.md](windows-build-guide.md).

## Perbaikan lanjutan: lisensi aktif tetapi rekomendasi belum tampil

Tangkapan layar lanjutan menunjukkan lisensi aktif, tetapi belum ada analisis mesin.
Replay gambar menemukan batas papan yang benar; template bawaan menghasilkan skor
sekitar 0,46–0,72 untuk sejumlah bidak, di bawah ambang 0,74. Karena itu posisi
tidak diteruskan ke engine. Status `Papan tidak ditemukan` pada aplikasi juga berarti
jendela papan perlu diaktifkan selama pencarian, bukan mengulang aktivasi lisensi.

Perbaikan kode menghubungkan transisi lisensi pertama ke autostart yang sempat
ditolak lisensi, sambil mempertahankan Jeda manual, `auto_start=false`, dan seluruh
penolakan saat lisensi tidak aktif. Pesan kegagalan pengenalan kini mengarahkan
pengguna memilih orientasi eksplisit, FEN yang sesuai, dan Deteksi & pelajari.
Template maupun konfigurasi portable pengguna tidak diganti secara diam-diam.

Fixture `tests/fixtures/start-board-green.png` hanya berisi papan dari gambar yang
diberikan; panel/informasi lisensi tidak disalin. Regresi membuktikan pembelajaran
tema pada ukuran aslinya membaca seluruh posisi awal, kemudian menjalankan
Stockfish nyata dan meneruskan langkah legal sampai pemanggilan overlay.
Grant QA untuk pengujian ditandatangani dan diverifikasi secara kriptografis melalui
transport khusus test; tidak memakai cache pengguna atau mengubah record server.

Run lanjutan menghasilkan **192 passed**, termasuk integrasi Stockfish nyata.
Bukti: `work/tests-recommendations-all.xml` dan `work/build-recommendations.log`.
Pengguna tetap perlu melakukan pembelajaran tema sekali melalui UI pada papan
yang benar; langkahnya ada pada bagian pemecahan masalah di panduan build.

EXE lanjutan telah dibentuk dan lolos audit arsip serta smoke/relokasi. Saat
publikasi hasil, EXE lama sedang dibuka pengguna sehingga Windows menolak
penimpaan file tersebut. Hasil yang telah tervalidasi disimpan sebagai
`outputs/licensed/ChessLab-Coach-Update.exe`, dengan metadata
`outputs/licensed/build-info-update.json`. EXE lama beserta metadata lamanya
dipertahankan. Tutup aplikasi lama, lalu buka EXE Update di folder yang sama;
konfigurasi `ChessLab-data` dan cache aktivasi tetap dapat dipakai.
Bukti final: `work/recommendation-final-validation.json`. Build log mencatat
PermissionError publikasi nama lama; audit/smoke binary baru sudah lulus dan
audit diulang setelah salinan Update tersedia.
