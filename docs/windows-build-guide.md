# Panduan build Windows ChessLab PC

Panduan ini menghasilkan `outputs/licensed/ChessLab-Coach.exe` untuk UAT lokal
Windows 10/11 x64, menggunakan sumber checkout aktif dan verifikasi lisensi tetap aktif.
Tidak ada deployment produksi atau push Git otomatis.

## Prasyarat dan versi yang didukung

- Git, PowerShell 5.1 atau lebih baru, koneksi ke PyPI, dan desktop Windows aktif.
- CPython **3.13 x64 standar** (bukan free-threaded), lengkap dengan pip dan Tcl/Tk.
  Build pemulihan ini memakai **3.13.17**. Instal berdampingan dari
  [Python.org](https://www.python.org/downloads/windows/); jangan hapus Python sistem.
- Disk kosong untuk venv, engine sekitar 100 MB, ekstraksi onefile dan hasil build.
- Distribusi resmi Stockfish **19** sesuai CPU beserta sumber/lisensi yang cocok.
- Konfigurasi lisensi publik yang sesuai server target. Untuk UAT server lokal,
  Docker Compose yang sudah dikonfigurasi berjalan di `http://localhost:8080`.

`pyproject.toml` tetap mengizinkan Python >=3.11 untuk pengembangan umum.
Kontrak **build Windows** sengaja lebih ketat: 3.13 x64. PyInstaller sudah mendukung
Python 3.14 sejak 6.15 ([changelog resmi](https://pyinstaller.org/en/v6.16.0/CHANGES.html));
karena rentang dependency lama terbuka, kegagalan mesin ini tidak membuktikan 3.14
tidak didukung. Lock dan smoke test rilis di panduan ini disertifikasi pada 3.13,
sehingga preflight menolak 3.14. Dry-run resolusi seluruh lock pada Python 3.14.2
juga berhasil tanpa memasang paket global; impor runtime dan smoke EXE 3.14 belum
diuji. Migrasi tetap memerlukan pengujian terpisah.

Versi runtime, dependency transitif, backend build, pytest dan PyInstaller dikunci
di `requirements-windows.lock`; `requirements-build.txt` merujuk lock tersebut.
`pip check`, impor native library, serta pemeriksaan setiap versi lock wajib lulus.
Build dapat diulang dengan input sama; EXE tidak dijanjikan identik byte per byte
karena metadata waktu dan proses packaging. Untuk integritas input eksternal, cocokkan
checksum rilis resmi bila tersedia. Build mencatat SHA-256 payload, sumber, lock dan EXE.

## Clone dan setup awal

```powershell
git clone https://github.com/Rizkirahadiaan/chesslabs.git
cd chesslabs
.\scripts\setup-windows.ps1
```

Setup mencari Python melalui `.venv`, `py -3.13`, `.tools/python313/python.exe`,
dan interpreter pada PATH. Untuk instalasi berdampingan yang tidak ditemukan:

```powershell
.\scripts\setup-windows.ps1 -Python 'C:\Python313\python.exe'
```

Setup membuat `.venv` tanpa system-site-packages, memasang dependency terkunci,
memasang checkout aktif secara editable, memeriksa asal impor `chesslab`, lalu
menjalankan preflight. **Clone baru belum memiliki konfigurasi lokal**: setup
pertama dapat berakhir dengan FAIL konfigurasi setelah dependency selesai dipasang.
Provision aset/kunci publik, jalankan inisialisasi di bawah, lalu ulangi setup.
Tidak ada pemasangan global sebagai fallback. `.venv` yang rusak/berversi salah
harus dipindahkan atau dicadangkan secara manual sebelum dibuat ulang.

Semua wrapper memakai `.venv/Scripts/python.exe -E -s`, sehingga editable global lama,
PYTHONPATH, PYTHONHOME dan user site-packages tidak dipakai. Wrapper tidak memerlukan
aktivasi venv. Jika ingin memakai perintah `python` singkat, aktifkan terlebih dahulu:

```powershell
.\.venv\Scripts\Activate.ps1
python -E -s scripts\preflight_build.py
```

Jika kebijakan eksekusi menolak skrip lokal, jalankan skrip yang telah diperiksa
dengan `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\setup-windows.ps1`.
Ini berlaku pada proses tersebut dan tidak mengubah kebijakan mesin.

## Provision Stockfish dan template

Unduh [Stockfish 19 resmi](https://stockfishchess.org/download/), lalu ekstrak
**seluruh arsip** ke folder terpisah, misalnya `engine/` yang diabaikan Git atau
`C:\tools\stockfish`. Pertahankan binary, `Copying.txt`, `AUTHORS`, `README.md`,
`src/` (termasuk Makefile), dan `scripts/` jika tersedia. Jangan hanya menyalin EXE.
Sumber harus sesuai binary; preflight memeriksa keberadaan sumber dan lisensi,
sedangkan kecocokan sumber dengan distribusi resmi tetap tanggung jawab penyedia aset.
Binary universal x64 resmi dapat memilih kemampuan CPU secara otomatis. Preflight
membuka engine melalui UCI dengan batas waktu, memeriksa nama Stockfish 19, dan
memastikan satu langkah legal. Tidak ada unduhan engine atau penggantian otomatis.

Repositori sudah melacak **64 PNG asli pada 13 kelas** di `templates/`: enam jenis
bidak putih, enam hitam, dan `empty`. Tidak ada template dummy yang dibuat saat setup.
Setiap kelas harus memiliki PNG yang bisa dibaca Pillow dan TemplateRecognizer.
Pencocokan gambar tetap bergantung pada tema, skala dan orientasi papan UAT.
Untuk tema berbeda, gunakan papan latihan lokal dan alur `collect-templates`
di README atau tombol **Deteksi & pelajari**, kemudian validasi ulang aset.
Template tambahan dalam folder `coach-*` bersifat lokal dan tidak dibundel otomatis;
pilih direktori template yang lengkap melalui `-TemplatesDir` bila ingin memakainya.
Jangan menaruh `.env`, kunci privat, atau data server dalam pohon template.

## Konfigurasi aplikasi dan kunci publik

Minta pengelola server memberikan `licensing-public.json`. Contoh tracked
`licensing-public.example.json` sengaja berisi `public_keys` kosong dan belum valid
untuk build. File publik hanya boleh memiliki:

```json
{
  "api_url": "http://localhost:8080",
  "product": "chesslab-pc",
  "public_keys": {"ID-KUNCI-SERVER": "BASE64URL-PUBLIC-KEY-ED25519-32-BYTE"},
  "renewal_instructions": "Hubungi administrator untuk perpanjangan."
}
```

Nilai di atas adalah placeholder dokumentasi. Gunakan nilai asli dari server.
HTTP hanya diizinkan untuk localhost/127.0.0.1; target lain wajib HTTPS tanpa
kredensial, path, query atau fragment. Public key bukan private PEM. Jangan jalankan
`deploy/init_local.py` pada lingkungan yang sudah memiliki kunci: skrip itu membuat
lingkungan baru dan bukan prosedur recovery build ini. Jangan merotasi kunci untuk
mengatasi ketidakcocokan.

```powershell
.\scripts\init-chesslab-config.ps1 -StockfishPath 'C:\tools\stockfish\stockfish-windows-x86-64-universal.exe'
# Opsional: -TemplatesDir 'C:\aset\templates'
.\scripts\setup-windows.ps1
```

Jika `engine/stockfish.exe` tersedia, initializer dapat memakai path relatif contoh;
jika belum, initializer menanyakan path engine. Untuk otomasi gunakan
`-NoPrompt -StockfishPath <path>`. Semua nilai selain path berasal dari
`config.example.json` dan divalidasi terhadap `Settings`/`BoardBox` sebenarnya.
File baru diterbitkan hanya setelah aset dan kunci publik valid. Path relatif
selalu dihitung dari folder config, bukan folder kerja pemanggil.

`config.json` yang sudah ada **tidak pernah ditimpa**, termasuk saat validasi gagal.
Menjalankan ulang initializer hanya memvalidasinya; argumen path baru tidak mengganti
preferensi lama. Untuk mengubahnya, cadangkan dan edit sendiri secara eksplisit.
Koordinat papan contoh perlu dikalibrasi untuk papan latihan pengguna.

## Preflight dan pemeriksaan server read-only

```powershell
.\.venv\Scripts\python.exe -E -s scripts\preflight_build.py --report work\preflight.json
.\.venv\Scripts\python.exe -E -s scripts\verify_local_license.py --report work\license-local.json
```

Preflight mencetak PASS/FAIL/WARNING dan keluar nonzero pada kegagalan kritis:
Python/venv/impor, dependency lock dan Tk, JSON, executable/UCI Stockfish,
sumber/lisensi, seluruh kelas PNG, struktur Ed25519/API URL, input rahasia dan
tujuan output. Endpoint valid selain `http://localhost:8080` diberi WARNING.
Preflight tidak membutuhkan signing key privat; build desktop bisa dilakukan
hanya dengan konfigurasi publik dan aset.

Pemeriksaan server adalah langkah terpisah ketika kunci server tersedia lokal.
`verify_local_license.py` menandatangani challenge **yang bukan grant lisensi**
dalam memori, lalu memverifikasinya menggunakan public key. Skrip membandingkan
ID, fingerprint publik dan origin dengan container `api`, serta GET `/healthz`.
Isi PEM dan environment container tidak dicetak/diekspor. Untuk rotasi yang sudah
memiliki beberapa public key, pilih `--key-id <ID>` secara eksplisit.
Mismatch menyebabkan FAIL tanpa mengubah kunci, container atau record lisensi.
Pada komputer build tanpa Docker/key privat, tandai pemeriksaan server NOT RUN;
jangan menyalin rahasia server ke workstation hanya agar preflight lulus.

## Build dan validasi EXE

```powershell
.\scripts\build-windows.ps1
# Alternatif klik ganda: Build-Portable.cmd
```

Wrapper memakai `packaging/build_portable.py`. Pemanggilan Python langsung juga
menjalankan preflight. Build membuat staging baru di `work/portable-build/`, menyalin
hanya PNG kelas aktif, engine, config relatif, konfigurasi publik dan lisensi.
Sumber Stockfish serta pemberitahuan dependency (termasuk cryptography/httpx dan
transitif) dipertahankan. Tidak ada penyalinan rekursif repositori/server ke seed.

Audit membaca arsip PyInstaller, menolak nama/isi kunci privat dan modul server,
memverifikasi manifest/hash payload, dan membandingkan **nilai public key lengkap**
dengan konfigurasi target. Smoke test menjalankan EXE tanpa Python di PATH dari
cwd berbeda, menggunakan LOCALAPPDATA QA terpisah. Pengujian menguji engine,
template, GUI, UI aktivasi dan penolakan premium tanpa lisensi. EXE beserta data
kemudian dipindahkan ke folder berspasi/non-ASCII dan diuji ulang; preferensi harus tetap.
Hanya setelah seluruh tahap lulus, hasil dipromosikan ke:

```text
outputs/licensed/
  ChessLab-Coach.exe
  BACA-DULU.txt
  build-info.json
```

Metadata berisi commit Git, status dirty, versi Python/dependency, ID kunci publik,
endpoint, hash sumber/payload/lock dan hash EXE akhir. Metadata eksternal mencatat
hasil validasi; metadata tertanam merekam input sebelum EXE dibentuk.
Build gagal tidak mengganti hasil final lama; selalu periksa timestamp dan metadata.
Tidak ada argumen untuk melewati audit atau smoke test pada build rilis ini.

Validasi ulang dan tes regresi:

```powershell
.\.venv\Scripts\python.exe -E -s -m pytest -q
.\.venv\Scripts\python.exe -E -s packaging\check_license_bundle.py outputs\licensed\ChessLab-Coach.exe --expected-public licensing-public.json
.\.venv\Scripts\python.exe -E -s packaging\verify_portable.py
```

## UAT aktivasi

1. Pastikan stack lokal sehat (`docker compose ps`) dan `verify_local_license.py` lulus.
2. Jalankan EXE dari folder yang bisa ditulis. Saat pertama dibuka EXE menyiapkan
   `ChessLab-data/` di sampingnya; path engine/template/config tetap relatif sehingga
   portable onefile tidak bergantung pada lokasi ekstraksi `_MEIPASS`.
3. UI **Aktivasi** harus terbuka. Tanpa aktivasi, analisis premium tetap dinonaktifkan.
4. Gunakan kunci lisensi **khusus QA** yang diterbitkan administrator untuk produk
   `chesslab-pc`. Jangan memakai/reset/mencabut record nyata untuk pengujian.
5. Aktivasi pertama dapat memulai masa berlaku. Verifikasi status aktif, analisis
   pada papan latihan lokal, lalu tutup dan buka lagi untuk memeriksa cache perangkat.
6. Periksa kegagalan jaringan dengan data QA; UI tetap responsif karena HTTP berjalan
   di worker. Jangan menonaktifkan signature, kedaluwarsa, Origin Validation atau device binding.

Cache aktivasi tetap di `%LOCALAPPDATA%/ChessLab/licensing` dan dilindungi DPAPI.
Menghapus data portable tidak menghapus cache perangkat. Untuk pengujian cache kosong,
gunakan `packaging/verify_portable.py` yang mengisolasi LOCALAPPDATA secara otomatis.
`packaging/verify_license_lifecycle.py` membutuhkan kredensial admin QA khusus dan
membuat/mencabut record QA baru; jalankan hanya jika data/kredensial QA tersedia.
Ketiadaan kredensial tersebut harus dilaporkan NOT RUN untuk aktivasi/lifecycle online.
`localhost` selalu berarti PC yang menjalankan EXE; pindah PC tidak dapat menghubungi
stack di PC pengembang melalui URL itu. Perubahan endpoint/public key memerlukan build ulang.

## Pemecahan masalah

| Gejala | Tindakan |
| --- | --- |
| `No module named PyInstaller` | Ulangi setup; gunakan `.venv/Scripts/python.exe`, bukan Python global. |
| Editable menunjuk folder lama | Ulangi setup; pemasangan lokal memakai `--force-reinstall --no-deps`. Global lama tetap ada. |
| Python hanya 3.14 | Pasang 3.13 x64 berdampingan dan pilih `-Python`. Jangan menimpa Python sistem. |
| `config.json` belum ada | Provision public key/aset, jalankan initializer lalu ulangi setup. |
| Stockfish tidak bisa dieksekusi | Pilih binary resmi sesuai arsitektur/CPU; ekstrak arsip penuh dan periksa Windows blocking. |
| Lisensi/sumber engine hilang | Pulihkan distribusi resmi yang cocok; build sengaja berhenti. |
| Template kelas hilang/rusak | Pulihkan PNG tracked atau provision hasil pelatihan tema yang lengkap. |
| ID/key/origin server berbeda | Cocokkan konfigurasi target dengan pengelola server; jangan regenerasi kunci otomatis. |
| Venv rusak setelah folder dipindah | Backup/pindahkan `.venv`, lalu setup dari interpreter 3.13 yang benar. |
| Tk/smoke test tidak bisa berjalan | Gunakan desktop Windows interaktif. Jangan mengklaim EXE lulus pada sesi headless. |
| EXE gagal saat startup | Pastikan folder bisa ditulis; lihat `ChessLab-data/runtime/portable.log`. |
| Lisensi aktif, tetapi rekomendasi belum muncul / Mesin — | Aktifkan jendela papan dan pastikan seluruh papan terlihat. Jika tema/ukuran belum cocok, ikuti pembelajaran tema di bawah. |

### Lisensi aktif tetapi rekomendasi belum muncul

Aktivasi mengizinkan analisis; posisi papan tetap harus dikenali dengan yakin.
Skor di bawah ambang tidak diteruskan ke engine. Mulai build perbaikan ini,
aktivasi pertama melanjutkan autostart yang sempat tertahan lisensi. Jeda manual
dan pengaturan `auto_start=false` tetap dihormati. Tidak ada pelonggaran verifikasi
lisensi atau ambang pengenalan untuk memaksa rekomendasi.

Untuk tema atau ukuran papan baru:

1. Pastikan seluruh papan terlihat dan panel tidak menutupinya.
2. Pilih **Di bawah: white** jika bidak putih berada di bawah, atau **black** jika
   hitam di bawah. Gunakan orientasi eksplisit saat belajar tema pertama kali.
3. Klik **Posisi awal** hanya jika posisi memang masih awal; untuk posisi lain
   isi FEN lengkap yang benar. Jangan melabeli posisi berjalan sebagai posisi awal.
4. Klik **Deteksi & pelajari (3 dtk)**, lalu segera aktifkan jendela papan dengan
   klik atau Alt+Tab. Pertahankan papan sampai pesan **Papan dan template siap** muncul.
5. Klik **Mulai / lanjut (3 dtk)** lalu aktifkan kembali jendela papan. Rekomendasi
   muncul ketika posisi stabil dan giliran sesuai pilihan **Anda**.

Template yang dipelajari disimpan dalam profil lokal `ChessLab-data/templates/coach-*`.
Pilihan ini tidak mengubah cache aktivasi perangkat dan dipertahankan saat EXE diperbarui.
Untuk menguji replay tema regresi beserta engine nyata tanpa memakai lisensi pengguna:

```powershell
$env:CHESSLAB_TEST_ENGINE = 'C:\tools\stockfish\stockfish-windows-x86-64-universal.exe'
.\.venv\Scripts\python.exe -E -s -m pytest -q tests\test_activation_recommendations.py
```

Pengujian memakai grant QA bertanda tangan yang diverifikasi melalui transport
khusus test; tidak menerbitkan atau mengubah lisensi pada server. Pengujian
Stockfish nyata berstatus SKIP jika `CHESSLAB_TEST_ENGINE` belum diprovision.

## Berkas Git dan berkas lokal

Track sumber, skrip, lock dependency, contoh config, template PNG asli, tes dan dokumen.
Jangan track `config.json`, `licensing-public.json`, `engine/`, `.tools/`, `.venv/`,
`work/`, `outputs/`, EXE/spec hasil build, `.env*`, private keys atau kredensial admin.
`.env.example` tetap boleh tracked tanpa rahasia. Kunci publik bukan rahasia, tetapi
konfigurasi deployment lokal tetap dikecualikan Git untuk menghindari salah target.

Hasil pengujian pemulihan pada mesin ini dicatat terpisah di
[laporan recovery](windows-build-recovery-report.md); pisahkan hasil terverifikasi
dari hal yang masih memerlukan UAT manual.
