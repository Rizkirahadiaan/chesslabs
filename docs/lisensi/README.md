# Platform lisensi ChessLab

Platform ini terdiri dari pustaka desktop Windows, API FastAPI, PostgreSQL, dan dashboard Next.js. Logika catur, Stockfish, visi, tracker, hotkey, dan algoritma overlay tetap memakai implementasi sebelumnya. Asesmen awal ada di [01-asesmen.md](01-asesmen.md); hasil pelaksanaan ada di [LAPORAN-IMPLEMENTASI.md](LAPORAN-IMPLEMENTASI.md).

## Memulai stack lokal

Jalankan PowerShell dari direktori proyek. Docker Desktop harus menyediakan engine Linux dan Docker Compose v2.

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe deploy/init_local.py
docker compose up -d --build
docker compose ps
docker compose run --rm api python -m app.cli bootstrap
```

`init_local.py` membuat `.env`, `secrets/license-private.pem`, dan `licensing-public.json` dengan nilai acak. Perintah menolak menimpa berkas lama. Simpan ketiganya dengan aman. Bootstrap meminta email dan kata sandi secara interaktif, minimal 14 karakter; tidak ada akun produksi bawaan. Bootstrap juga menyediakan ChessLab PC / ChessLab Pro, 432.000 detik, Rp50.000, satu perangkat. Untuk lingkungan otomatis, bootstrap menerima `CHESSLAB_BOOTSTRAP_EMAIL` dan `CHESSLAB_BOOTSTRAP_PASSWORD` dari lingkungan proses; jangan simpan password di riwayat shell.

Buka [dashboard lokal](http://localhost:8080). Hanya reverse proxy yang membuka port host, terikat `127.0.0.1`. PostgreSQL, API, dan dashboard tetap berada di jaringan Compose. [Health check](http://localhost:8080/healthz) memeriksa koneksi database dan tabel versi migrasi. OpenAPI tersedia melalui API langsung pada `/docs` dan `/openapi.json`; lihat perintah menjalankan API mandiri di bawah. Proxy publik hanya meneruskan `/api/*` dan `/healthz`.

Di dashboard: buat pelanggan → buat lisensi → salin kunci yang hanya ditampilkan sekali → buka Coach → aktivasi. Setelah konfirmasi pembayaran manual, buka detail lisensi dan pilih Perpanjang. Referensi pembayaran wajib diisi. Catatan perpanjangan dan audit tidak dapat diubah atau dihapus melalui aplikasi maupun akun database runtime.

```powershell
.\.venv\Scripts\python.exe -m chesslab.cli --config config.json coach
docker compose stop
docker compose start
docker compose down
```

`down` mempertahankan volume. Jangan menambahkan `-v` jika data perlu dipertahankan. Stack pengujian pelaksanaan ini memakai proyek terpisah `chesslab-license-qa` dan `work/compose.env`, bukan `.env` produksi.

## Arsitektur dan data

```text
src/chesslab/licensing/
  api.py          HTTP dengan timeout dan kebijakan HTTPS
  verifier.py     Ed25519 dan validasi klaim
  device.py       identitas perangkat yang di-hash
  storage.py      cache pengguna Windows melalui DPAPI
  manager.py      entitlement, jam tepercaya, validasi, cache
  controller.py   executor jaringan dan polling Future di main thread
  ui.py           aktivasi, status, petunjuk perpanjangan
license-server/
  app/api.py            REST versi v1 dan RBAC
  app/auth.py           sesi admin, CSRF, pembatasan permintaan
  app/models.py         model SQLAlchemy
  app/schemas.py        validasi masukan Pydantic
  app/repositories.py   kueri dan penguncian baris lisensi
  app/services.py       siklus lisensi dan transaksi
  app/core/             konfigurasi, hashing, penandatanganan
  app/db.py             sesi dan waktu UTC
  app/cli.py            bootstrap, keygen, pemeliharaan
  app/migrate.py        migrasi dan izin akun database runtime
  alembic/versions/0001_initial.py
  tests/
admin-dashboard/
  app/             dashboard Next.js, TypeScript, Tailwind
  lib/api.ts       kontrak data dan klien API satu origin
  tests/           pengujian Playwright terhadap API sebenarnya
deploy/            konfigurasi Caddy dan inisialisasi lokal
compose.yaml
```

Database mempunyai sepuluh tabel: customers, products, license_plans, licenses, device_activations, license_renewals, audit_logs, administrators, admin_sessions, dan rate_buckets. Identitas bisnis memakai UUID; rate bucket memakai pasangan hash/window. Foreign key, unique constraint, pemeriksaan status/durasi/tanggal, indeks masa berlaku, pasangan paket/produk, dan indeks unik perangkat aktif diterapkan di database. Ketentuan durasi serta batas perangkat disalin ke lisensi saat pembelian; perubahan paket tidak mengubah pembelian lama. Perpanjangan memakai durasi/harga paket server yang dipilih saat konfirmasi. Batas perangkat lisensi lama tetap dipertahankan.

Aktivasi, validasi, reset, perpanjangan, dan perubahan status mengunci baris induk lisensi dengan `SELECT FOR UPDATE`. Batas perangkat diperiksa di dalam transaksi tersebut. Perpanjangan menyimpan unique `(license_id, idempotency_key)`, memeriksa kesamaan paket dan referensi pembayaran saat permintaan diulang, serta mencatat pembayaran dan audit dalam transaksi yang sama. Kunci idempotensi harus digunakan ulang saat mengulang konfirmasi pembayaran yang sama; jangan membuka operasi baru jika hasil pembayaran sebelumnya belum dipastikan. Dashboard mempertahankan kunci selama dialog tetap terbuka.

Migrasi `0001` membekukan skema dan memasang trigger penolak UPDATE/DELETE/TRUNCATE atas riwayat PostgreSQL. Akun `chesslab_api` tidak diberi hak mengubah/menghapus riwayat maupun DDL. Migrator terpisah memegang hak skema. Downgrade destruktif sengaja ditolak; gunakan backup dan prosedur rollback terencana. Pemilik database tetap dapat mengubah skema; immutable pada tingkat aplikasi bukan pengganti penyimpanan audit eksternal yang tahan administrator database.

## Status lisensi

| Status awal | Status tujuan | Pemicu |
|---|---|---|
| PENDING | ACTIVE | Aktivasi pertama berhasil; mulai durasi |
| PENDING | SUSPENDED / REVOKED | Tindakan admin |
| ACTIVE | EXPIRED | Waktu server mencapai akhir langganan |
| ACTIVE | SUSPENDED / REVOKED | Tindakan admin |
| EXPIRED | ACTIVE | Perpanjangan terkonfirmasi |
| EXPIRED | SUSPENDED / REVOKED | Tindakan admin |
| SUSPENDED | REVOKED | Pencabutan oleh admin |
| REVOKED | Tidak ada | Terminal |

Pemulihan SUSPENDED tidak disediakan pada versi ini; perpanjangan tidak mengaktifkannya secara diam-diam. PENDING juga tidak boleh diperpanjang. Jika masih aktif, perpanjangan dimulai dari akhir langganan saat ini; jika kedaluwarsa, dari waktu konfirmasi server. UUID lisensi, pelanggan, dan riwayat tetap sama. Status kedaluwarsa selalu dihitung secara server-authoritative saat membaca/memvalidasi. Penulisan transisi EXPIRED dan audit fisik dilakukan saat transaksi yang berhasil membaca detail/perpanjangan atau melalui perintah pemeliharaan.

Semua tanggal database memakai UTC dengan zona waktu. UI menampilkan zona lokal perangkat/browser. Durasi lima hari berarti 432.000 detik, bukan pergantian hari kalender. Misalnya aktivasi 22 Oktober 2026 pukul 10.00 WIB berakhir 27 Oktober 2026 pukul 10.00 WIB.

## Kontrak API

Prefix seluruh endpoint adalah `/api/v1`. Respons kesalahan berbentuk `{"error":{"code":"KODE_STABIL","message":"Pesan Indonesia"}}`. Validasi masukan tidak mengembalikan isi password atau kunci yang salah. Data terdaftar memiliki `items`, `total`, `page`, dan `size` (maksimal 100). Lisensi mendukung filter status/prefiks dan pengurutan created_at/expires_at/key_prefix; pelanggan mendukung pencarian nama/email; audit mendukung tindakan/resource_id.

| Endpoint | Autentikasi / fungsi |
|---|---|
| POST /licenses/activate | Kunci lisensi, product_code, device_hash; mengembalikan grant dan activation_secret sekali |
| POST /licenses/validate | Bearer activation_secret dan product_code/device_hash; mengembalikan grant baru |
| GET /licenses/status | Bearer yang sama; product_code/device_hash pada query |
| POST /licenses/deactivate | Bearer perangkat; menonaktifkan aktivasi tersebut |
| POST /admin/auth/login | Origin yang diizinkan, email/password |
| POST /admin/auth/logout | Sesi + CSRF |
| GET /admin/auth/me | Memeriksa sesi dan peran |
| GET /admin/dashboard/summary | Statistik dan aktivitas terbaru |
| GET /admin/customers | Semua peran |
| POST /admin/customers | admin / operator |
| PATCH /admin/customers/{id} | admin; nama/email/status |
| GET /admin/products | Semua peran |
| POST /admin/products | admin |
| GET /admin/plans | Semua peran |
| POST /admin/plans, PUT /admin/plans/{id} | admin; harga/durasi/batas perangkat/status |
| GET /admin/licenses, GET /admin/licenses/{id} | Semua peran |
| POST /admin/licenses | admin / operator; kunci lengkap hanya pada respons ini |
| POST /admin/licenses/{id}/renew | admin / operator; plan_id, payment_reference, idempotency_key |
| POST /admin/licenses/{id}/revoke, /suspend | admin; alasan wajib |
| GET /admin/licenses/{id}/devices | Semua peran |
| POST /admin/licenses/{id}/devices/reset | admin; alasan wajib |
| GET /admin/audit-logs | Semua peran |

Tidak ada endpoint admin yang menerima kunci lisensi sebagai autentikasi admin. Peran viewer hanya membaca. Kunci pembelian tidak disimpan di cache desktop; activation_secret adalah kredensial acak khusus perangkat, hanya hash-nya disimpan server. Aktivasi ulang perangkat yang masih terdaftar membutuhkan kredensial tersebut. Jika cache hilang, admin harus mereset perangkat. Jika respons aktivasi pertama hilang setelah server melakukan commit, reset admin mungkin diperlukan karena kredensial perangkat tidak dapat diambil kembali.

## Grant dan kebijakan offline

Format token adalah `base64url(header).base64url(payload).base64url(signature)`, tanpa padding. Header `{alg: EdDSA, typ: CLG, kid: ...}` dan payload diserialisasi JSON ASCII dengan urutan kunci leksikografis, `ensure_ascii=True`, pemisah `,` dan `:` tanpa spasi. Ed25519 menandatangani byte ASCII dari dua segmen pertama dengan titik di antaranya. Ini format khusus CLG, bukan JWT generik yang menerima algoritma berbeda.

Klaim: v, product, license, activation, device, edition, status, activated, iat, exp, subscription_exp. Timestamp berupa integer detik Unix UTC. `exp = min(iat + konfigurasi_grant, subscription_exp)`; konfigurasi grant dibatasi maksimum 43.200 detik. Verifier menolak algoritma/kid/tanda tangan salah, produk/perangkat salah, status selain ACTIVE, struktur rusak, grant terlalu panjang, waktu mundur jelas, dan masa berlaku habis. Harga tidak ditanam ke desktop.

- Aktivasi awal wajib online; tanpa cache valid tidak ada akses premium.
- Startup memeriksa tanda tangan cache lalu memvalidasi online di worker.
- Validasi normal setiap 30 menit; kesalahan jaringan/server/429 dicoba lagi setelah 60 detik.
- Gangguan jaringan memakai grant terakhir sampai batas 12 jam sejak penerbitan, dengan batas tambahan akhir langganan.
- Pencabutan/penangguhan/reset yang diketahui dari server langsung menghapus entitlement lokal. Saat offline, perubahan tersebut efektif selambat-lambatnya saat grant berakhir.
- Jam server yang ditandatangani dan penghitung monotonic menjadi jangkar selama proses berjalan. Cache menyimpan waktu terakhir; rollback jelas (>120 detik) memerlukan validasi online. Checkpoint setiap 60 detik dan saat aplikasi ditutup.
- Semua callback widget dipanggil melalui polling Future pada `root.after` milik main thread. Worker jaringan tidak memanggil Tk.
- Cache menggunakan DPAPI pengguna Windows; penggantian akun/PC atau kerusakan cache memerlukan pemulihan melalui admin.

Identitas perangkat berasal dari Windows MachineGuid yang dibaca tanpa hak admin, diberi namespace produk lalu SHA-256. Jika registry tidak tersedia, gunakan identitas instalasi acak yang dilindungi DPAPI. Tidak menggunakan MAC address dan tidak mengirim pengenal hardware mentah. Instal ulang Windows, image Windows hasil kloning, VM/snapshot, dan pengubahan biner oleh administrator lokal membatasi keandalan identitas/offline licensing. Sistem ini tidak menjanjikan perlindungan mutlak pada komputer pengguna yang tidak tepercaya.

Reset perangkat tidak dapat menarik grant offline yang sudah diterbitkan. Ada kemungkinan sementara dua mesin memiliki grant lama/baru sampai batas grant lama. Batas **registrasi aktif pada server** tetap satu. Menghapus kemungkinan itu memerlukan kebijakan selalu online, yang bertentangan dengan toleransi offline 12 jam.

## Keamanan operasional

Password Argon2id; sesi acak hanya disimpan dalam bentuk hash, kedaluwarsa default delapan jam. Cookie sesi HttpOnly, SameSite=Strict, dan Secure pada konfigurasi produksi. Cookie CSRF dapat dibaca JavaScript dan wajib cocok dengan hash session serta Origin untuk mutasi. Login dibatasi per IP dan email, aktivasi per IP, validasi per IP dan kredensial. Rate bucket memakai upsert atomik database sehingga berlaku lintas worker. Mode reverse proxy hanya mempercayai CIDR yang dikonfigurasi; deployment Compose menggunakan jaringan internal 172.16.0.0/12 dan Caddy menimpa X-Forwarded-For. Sesuaikan CIDR jika jaringan Docker berbeda. API tidak membuka port host.

Tidak ada logging body request, bearer, password, kunci pembelian, maupun private key. Uvicorn access log dimatikan dan SQLAlchemy menyembunyikan parameter. Header no-store mencegah cache respons API. Dashboard memakai API satu origin; rahasia database dan signing tidak diberikan ke JavaScript. Container API/dashboard memakai pengguna non-root, root filesystem read-only, dan capability yang dilepas. Reverse proxy menggunakan image resmi Caddy.

Untuk produksi, siapkan domain/alamat TLS, ubah URL publik desktop dan `CHESSLAB_PUBLIC_ORIGIN` ke origin HTTPS, serta `CHESSLAB_SECURE_COOKIES=true`. Gunakan Caddy dengan alamat domain pada `CHESSLAB_SITE_ADDRESS`, port 80/443 pada override Compose khusus produksi, dan health check proxy yang cocok dengan skema/port tersebut. Health check default ditujukan HTTP lokal port 8080; jangan menyalin konfigurasi lokal tanpa menyesuaikannya. Simpan private key dan pepper dalam secret manager atau berkas dengan ACL terbatas. Jangan ubah pepper tanpa strategi migrasi hash. Cadangkan kunci dan pepper bersama database melalui kanal aman terpisah.

Rotasi Ed25519: terbitkan desktop yang mempercayai kid lama dan baru → pasang private key baru hanya di server → ganti CHESSLAB_SIGNING_KEY_ID/path → restart API → pertahankan kunci publik lama selama seluruh grant lama masih berlaku (maksimal 12 jam), plus masa pembaruan klien. Desktop frozen mengambil konfigurasi publik dari bundle, bukan file JSON yang dapat diganti melalui menu pengaturan.

## Migrasi, pemeliharaan, backup

```powershell
docker compose run --rm migrate
docker compose exec api python -m app.cli maintenance
docker compose logs --tail 100 api
```

Pemeliharaan menandai kedaluwarsa, membersihkan sesi, dan menghapus rate bucket lama. Jalankan berkala melalui scheduler operasional sesuai infrastruktur; hak akses premium sudah berhenti berdasarkan waktu server/grant meski perintah ini belum dijalankan.

Backup PostgreSQL format custom tanpa melewatkan data biner melalui redirection PowerShell:

```powershell
docker compose exec -T db pg_dump -U chesslab_migrator -d chesslab -Fc -f /tmp/chesslab.dump
docker compose cp db:/tmp/chesslab.dump ./backup/chesslab.dump
docker compose exec -T db pg_restore --list /tmp/chesslab.dump
```

Buat folder backup terlebih dahulu; beri nama arsip berbeda untuk setiap backup, enkripsi, dan uji pemulihan pada database terpisah. Pada pemulihan terencana, hentikan API/dashboard, salin dump ke container database tujuan, buat database kosong tujuan, jalankan `pg_restore --exit-on-error -U chesslab_migrator -d NAMA_DATABASE_TUJUAN /tmp/chesslab.dump`, lalu jalankan migrate untuk memulihkan role/hak runtime. Jangan menguji restore ke database produksi. Trigger audit tidak menghalangi restore ke tabel kosong.

## Pengembangan tanpa Compose

```powershell
cd license-server
..\.venv\Scripts\python.exe -m pip install -r requirements.lock
# Isi CHESSLAB_DATABASE_URL, CHESSLAB_KEY_PEPPER, CHESSLAB_SIGNING_KEY_PATH,
# CHESSLAB_PUBLIC_ORIGIN, dan CHESSLAB_SECURE_COOKIES pada lingkungan proses.
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Di terminal kedua, `cd admin-dashboard`, `npm ci`, `npm run dev`. Untuk development origin harus `http://localhost:3000`, cookie Secure false hanya di localhost, dan API_INTERNAL_URL diarahkan ke API lokal. Dokumentasi [FastAPI cookie](https://fastapi.tiangolo.com/advanced/response-cookies/), [transaksi SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/session_basics.html), dan [instalasi Next.js](https://nextjs.org/docs/app/getting-started/installation) menjadi referensi implementasi. Node 22 digunakan dalam pengujian dan Dockerfile.

## Build dan verifikasi Windows

```powershell
.\.venv\Scripts\python.exe -m pip install -e . -r requirements-build.txt
.\.venv\Scripts\python.exe packaging/build_portable.py --license-config licensing-public.json
.\.venv\Scripts\python.exe packaging/check_license_bundle.py outputs/licensed/ChessLab-Coach.exe
.\.venv\Scripts\python.exe packaging/verify_portable.py --exe outputs/licensed/ChessLab-Coach.exe
```

`Build-Portable.cmd` memakai alur yang sama. Output baru `outputs/licensed` mempertahankan EXE lama di `outputs/portable`. Build menambahkan metadata versi Python/aplikasi/dependensi, API URL, dan kid publik. Input aset terbatas pada konfigurasi desktop yang di-allowlist, template aktif, Stockfish, pemberitahuan dependensi, kunci publik, dan metadata. Pemeriksa arsip menolak berkas server/private key/.env; bundel sertifikat CA publik `certifi/cacert.pem` memang diperlukan TLS.

Versi dependensi desktop yang dipakai pengujian tercatat pada `outputs/licensed-test/build-info.json` dan pemberitahuan dependensi; gunakan virtual environment bersih dan versi yang sama untuk reproduksi. Build bersifat prosedural dapat diulang, bukan jaminan hash biner identik antar mesin. Kode signing Windows dan installer bertanda tangan belum dikonfigurasi. Paket QA memakai URL localhost dan kunci QA; bangun ulang dengan URL serta kunci publik produksi sebelum distribusi.

## Menjalankan pengujian

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=work/pytest-desktop-baru
cd license-server
..\.venv\Scripts\python.exe -m pytest tests -q --basetemp=../work/pytest-server-baru
# Untuk PostgreSQL sungguhan: isi CHESSLAB_TEST_DATABASE_URL.
# Database wajib berakhiran _test. Setiap fixture membuat dan menghapus hanya schema UUID miliknya.
..\.venv\Scripts\python.exe -m pytest tests -q --basetemp=../work/pytest-pg-baru
cd ../admin-dashboard
npm run typecheck
npm run build
npm run test:e2e
```

Uji Playwright memakai Chrome lokal dan mengasumsikan server QA sudah siap serta `work/e2e-runtime/password.txt` berisi kata sandi akun QA `e2e@example.com`. Variabel CHESSLAB_E2E_URL dan CHESSLAB_E2E_API memilih origin UI/API. Berkas `work/start_test_api.py` yang dipakai pelaksanaan awal adalah harness lokal, bukan server produksi. Jangan membuat akun QA pada deployment produksi.

Untuk uji Tk jaringan nyata, isi CHESSLAB_QA_API, CHESSLAB_QA_ADMIN_EMAIL, CHESSLAB_QA_ADMIN_PASSWORD, dan CHESSLAB_QA_PUBLIC_CONFIG lalu jalankan `packaging/verify_license_lifecycle.py`. Harness membuat data pelanggan/lisensi QA baru, cache workspace terpisah, memeriksa aktivasi dan Stockfish, lalu mencabut lisensi QA. Secara default pencarian papan diganti target uji. Jika `CHESSLAB_QA_TRAINING_BOARD=true`, harness menggunakan fixture papan lokal yang sudah tersedia di `work/coach-vision-fixture`, membuka jendela ChessLab Local Board, dan benar-benar menjalankan capture, pengenalan, analisis, serta overlay sebelum mencabut lisensi. Fixture ini aset QA lokal, tidak dimasukkan ke paket distribusi. Kedua mode berhasil dijalankan pada pelaksanaan ini.
