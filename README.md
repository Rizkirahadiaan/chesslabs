# ChessLab — Stockfish untuk papan lokal/test

## Platform lisensi Windows

Implementasi lisensi komersial, backend PostgreSQL/FastAPI, dashboard admin, deployment,
serta panduan build Windows tersedia di [panduan platform lisensi](docs/lisensi/README.md).
Hasil uji aktual dan syarat peluncuran dicatat di [laporan implementasi](docs/lisensi/LAPORAN-IMPLEMENTASI.md).
Pemulihan build dari clone baru, setup Python 3.13, provisioning aset, audit lisensi dan
validasi EXE dijelaskan di [panduan build Windows](docs/windows-build-guide.md).
Otomasi ZIP Windows di GitHub Releases serta image API/dashboard di GitHub Packages
tersedia dalam [panduan rilis GitHub](docs/github-release-guide.md).
Versi sumber dan build berlisensi baru memerlukan aktivasi untuk analisis premium.
EXE portable lama tidak ditimpa. Build baru menggunakan direktori `outputs/licensed`.
Harga dan paket ditentukan server; aktivasi awal membutuhkan koneksi internet.

## Android: prototipe untuk ARM64 / Android 16

APK tersedia di `outputs/android/ChessLab-Coach-Android.apk`. Versi Android memakai
izin berbagi layar, deteksi papan 2D, pembelajaran tema dari posisi awal, kalibrasi
manual, dan panel rekomendasi mengambang dengan level Human. Panduan pemasangan,
batasan, status uji, dan build ada di [android/README.md](android/README.md).
APK belum diuji langsung pada Samsung A34; minimum Android 14, target API 36.

## EXE portable: langsung buka tanpa instalasi

Hasil build berlisensi tersedia di `outputs/licensed/ChessLab-Coach.exe`. Buka EXE tersebut
untuk langsung menjalankan Coach tanpa terminal, instalasi Python, atau Stockfish
terpisah. Windows 64-bit diperlukan. Pembukaan awal membutuhkan beberapa saat.

EXE membuat folder `ChessLab-data` di sampingnya untuk pengaturan, template,
Stockfish, lisensi, log, dan PGN. Salin EXE beserta folder tersebut saat ingin
memindahkan pengaturan ke komputer/USB lain. EXE saja tetap bisa digunakan;
pengaturan dan template bawaan akan dibuat ulang. Simpan di folder yang bisa ditulis.
Konfigurasi versi portable ada di `ChessLab-data/config.json`.

Untuk membangun ulang setelah mengubah kode, konfigurasi, atau template aktif,
buka `Build-Portable.cmd`. Build memakai `config.json`, Stockfish yang dirujuk
konfigurasi tersebut, dan folder template aktif. Mesin build memerlukan dependensi
proyek serta PyInstaller; pengguna EXE tidak memerlukannya. Detail pendek tersedia
di `outputs/portable/BACA-DULU.txt`.

## Coach Python: penanda titik minimalis

Gunakan tombol pilihan **Bayangan** atau **Titik** pada **Tampilan rekomendasi**.
Bayangan memakai petak merah seperti tampilan sebelumnya: asal lebih samar,
tujuan lebih kuat. Titik memakai lingkaran kecil seperti dijelaskan di bawah.
Pilihan langsung berlaku dan disimpan dalam `overlay_style` (`shadow`/`dots`).
Slider **Kejelasan** berlaku untuk kedua tampilan; ukuran titik aktif pada mode Titik.

Script Python kini menampilkan dua tanda abu-abu kecil di sudut kanan atas petak:
lingkaran kosong untuk petak asal dan titik penuh untuk petak tujuan. Ukuran bawaan
5 piksel dengan kejelasan 45%. Atur **Ukuran titik (px)** (3–10) dan **Kejelasan**
(15–80%) di panel; pilihan disimpan sebagai `marker_size` dan `marker_opacity`.
Tombol **Minimalkan panel** menyisakan tanda di papan. `Ctrl+Alt+H` menampilkan/
menyembunyikan tanda, dan `Ctrl+Alt+P` menjeda/melanjutkan pemantauan.
Penanda sengaja dibuat samar, tetapi tetap dapat dilihat oleh orang yang memperhatikan layar.
EXE terbaru di `outputs/portable/ChessLab-Coach.exe` juga menyertakan pilihan
Bayangan/Titik ini. Saat memperbarui versi lama, ganti EXE dan pertahankan folder
`ChessLab-data` untuk memakai pengaturan serta template tersimpan.

Jalankan `chesslab --config config.json coach` atau buka `Start-Coach.cmd`.
Coach langsung mencari papan pada jendela aktif menggunakan template tersimpan.
Tampilkan seluruh papan dan aktifkan jendelanya; tidak perlu menekan Mulai.
Jika belum ditemukan, pencarian diulang otomatis. Dengan **Anda: auto** dan
**Di bawah: auto**, warna mengikuti orientasi papan yang dikenali.
Setelah partai selesai, pemantauan tetap berjalan dan rekomendasi berlanjut
ketika posisi awal match baru terdeteksi, termasuk jika warna berganti.
Tombol Jeda menghentikan pemantauan serta pencarian. Untuk mematikan mulai
otomatis saat aplikasi dibuka, tambahkan `"auto_start": false` ke konfigurasi.
Tema baru tetap perlu **Deteksi & pelajari** sekali sebelum bisa dikenali.
Panel menyediakan deteksi papan, pembelajaran template, Mulai/Jeda, dan rekomendasi
yang diperbarui otomatis. Anda menggerakkan bidak manual; perintah `play-local`
lama sudah dinonaktifkan. Panduan terbaru: `outputs/PANDUAN-COACH.md`.

Menu **Kecerdasan** disimpan otomatis: **Maksimal** menggunakan kekuatan penuh
dalam waktu analisis pilihan Respons; **Menengah** memakai Skill Level 10;
**Pemula** memakai Skill Level 0. **Blunder 15%** memiliki peluang 15% per
rekomendasi baru untuk memilih langkah lebih lemah, dengan prioritas penurunan
evaluasi minimal 1,5 pion. Posisi dengan langkah paksa atau alternatif setara
tidak selalu menyediakan blunder. Ini peluang acak, bukan tepat 15 dari 100 langkah.
Pilihan tersimpan sebagai `engine_strength`; konfigurasi lama memakai Maksimal.
Anda bebas memainkan langkah legal lain: Coach mengikuti posisi aktual, menunggu
balasan lawan, lalu menghitung rekomendasi berikutnya. Hasil analisis posisi atau
tingkat kecerdasan sebelumnya dibuang.

Level **Human** tersedia langsung di menu **Kecerdasan**. Mesin tetap memakai
Skill Level 20, tetapi memilih secara acak berbobot dari maksimal lima kandidat
kuat: langkah sederhana lebih disukai dan peluang menurun sesuai selisih evaluasi.
Toleransi penurunan evaluasi maksimal 0,35 pion, dipersempit menjadi 0,15 pion
saat skak atau ketika tersisa maksimal 10 buah. Angka ini estimasi pencarian,
bukan jaminan kerugian aktual atau Elo. Garis mat yang sudah ditemukan dipertahankan.
Pencarian tambahan dapat lebih dangkal dari pencarian utama sehingga kekuatan
bisa berkurang. Rekomendasi tidak diacak ulang pada frame posisi yang sama.
Human bekerja terlepas dari ON/OFF gaya setara; kontrol tersebut dinonaktifkan
selama Human dipilih. Konfigurasi proyek sekarang memilih Human.

Menu **Gaya setara: ON/OFF** disimpan sebagai `human_style`. ON mempertahankan
anggaran pencarian utama dan pengaturan kekuatan, lalu membandingkan hingga tiga
kandidat pada kedalaman minimal yang sama. Hanya kandidat dengan evaluasi terbaik
yang sama persis (toleransi 0 centipawn), dan tidak lebih rendah dari pencarian awal,
yang diprioritaskan berdasarkan rokade, pengembangan kuda/gajah, pusat, dan tangkapan
balik. Bila pembandingan belum cukup dalam, posisi skak, atau ada evaluasi mat,
rekomendasi pencarian utama dipertahankan. Evaluasi ini adalah estimasi mesin;
fitur ini tidak menjamin gaya manusia atau kekuatan/Elo yang identik.
Waktu analisis ON dapat mencapai sekitar empat kali anggaran biasa. OFF memakai
alur lama. Menengah/Pemula dan giliran blunder tetap mengikuti mode kecerdasan
tersebut; pilih Maksimal untuk kekuatan penuh dengan gaya manusiawi.
Konfigurasi lama yang belum memiliki `human_style` memakai OFF; konfigurasi proyek
ini sudah diatur ON. Perubahan ON/OFF langsung membuang rekomendasi lama dan
menghitung ulang posisi aktif. EXE harus dibangun ulang untuk memuat perubahan kode.

Pilihan **Anda: auto** mengikuti warna bidak di bawah, termasuk saat papan
terdeteksi berbalik. Pilih **black** atau **white** jika warna Anda berbeda dari
orientasi tampilan; pilihan ini disimpan sebagai `player_colour` di konfigurasi.
**Di bawah: auto** mendeteksi orientasi memakai template yang sudah dipelajari
dan tetap otomatis ketika papan berbalik. Pilihannya disimpan sebagai
`orientation_mode`; `board.orientation` menyimpan hasil deteksi terakhir.
Untuk belajar pertama kali atau saat tema belum dikenali, pilih orientasi
**white/black** sekali pada **Deteksi & pelajari**, lalu kembalikan ke **auto**.
Untuk hitam, rekomendasi muncul setelah putih bergerak. Setelah langkah Anda
terbaca, Coach menunggu lawan dan memperbarui rekomendasi otomatis saat giliran
Anda kembali. Dua langkah yang terlewat di antara pembacaan dapat disinkronkan
dari FEN terakhir, termasuk saat baru menekan Mulai.

Coach juga bisa dibuka di tengah match dengan template tersimpan. Biarkan FEN
bawaan: posisi aktual dibaca setelah tiga frame stabil. **Giliran awal: auto**
menunggu satu langkah untuk menentukan giliran (atau mendeteksinya dari skak).
Untuk rekomendasi langsung, pilih **white/black** sesuai pihak yang akan bergerak,
bukan warna Anda. **Baca posisi sekarang** memulai sesi baru dari papan yang tampak;
gunakan ini setelah banyak langkah terlewat, bukan Deteksi & pelajari.
Orientasi awal diperkirakan dari pion dekat baris asal; jika belum jelas, pilih
**Di bawah: white/black**. Posisi yang sudah tersinkron tetap dilacak dari langkah legal.
Tanpa FEN lengkap, hak rokade/en-passant awal dan riwayat sebelum Coach dibuka
tidak diketahui; hak tersebut tidak diasumsikan. Masukkan FEN lengkap jika perlu
mempertahankannya. Giliran awal kembali ke auto setiap kali aplikasi dibuka.

Bagian di bawah adalah referensi perintah pengambilan gambar dan analisis lama;
petunjuk klik otomatis di bagian lama tidak lagi berlaku.

ChessLab membaca papan catur dari tangkapan layar, membandingkan posisi stabil untuk
mendeteksi langkah lawan, meminta analisis ke Stockfish 19 melalui UCI, lalu (hanya
opsional) mengklik langkah pada papan **lokal atau lingkungan pengujian yang
diizinkan**.

> Fair play: jangan gunakan proyek ini untuk bermain atau memperoleh bantuan real-time
> di situs catur online, turnamen, atau permainan melawan manusia. Mode klik dibatasi
> oleh daftar judul jendela lokal pada konfigurasi. Jangan menambahkan browser/situs
> permainan online ke daftar itu. Sebagai perlindungan tambahan, judul yang memuat
> nama layanan catur online umum ditolak meskipun dimasukkan ke konfigurasi.

## Instalasi Windows

Di PowerShell dari folder proyek:

```powershell
.\scripts\setup-windows.ps1
# Jika setup berhenti karena config/aset belum tersedia, provision Stockfish dan
# licensing-public.json terlebih dahulu, lalu:
.\scripts\init-chesslab-config.ps1 -StockfishPath 'C:\tools\stockfish\stockfish-windows-x86-64-universal.exe'
.\scripts\setup-windows.ps1
.\.venv\Scripts\python.exe -E -s scripts\preflight_build.py
.\scripts\build-windows.ps1
```

Gunakan CPython 3.13 x64 standar dengan pip dan Tcl/Tk. Unduh/extract distribusi
Stockfish 19 resmi lengkap dengan `Copying.txt`, `AUTHORS`, `README.md` dan `src/`.
64 PNG pada 13 kelas template tersedia di Git. `licensing-public.json` harus
dipasok pengelola server dengan kunci publik yang benar; contoh berisi kunci kosong.
Setup awal memasang `.venv`, lalu berhenti jika konfigurasi/aset belum diprovision.
Instruksi lengkap dan diagnosis kegagalan ada di [panduan build](docs/windows-build-guide.md).

`opencv-python` dan kontrol Windows bawaan membutuhkan desktop Windows aktif; jalankan dari
komputer lokal, bukan sesi headless.

### Memperbaiki launcher setelah folder proyek dipindahkan

Jika `chesslab` menampilkan `Fatal error in launcher` dengan lokasi Python lama,
pasang ulang paket dari folder proyek agar launcher dan referensi sumber diperbarui:

```powershell
.\scripts\setup-windows.ps1
.\.venv\Scripts\Activate.ps1
chesslab --config config.json coach
```

Setup memasang ulang sumber editable checkout aktif dan menyelaraskan dependency
dengan lock Windows. Jika `.venv\Scripts\python.exe` tidak dapat dijalankan,
backup/pindahkan `.venv` lalu jalankan setup memakai CPython 3.13 x64 standar.

## Alur satu kali

1. Buka aplikasi papan lokal (misalnya aplikasi latihan yang Anda buat sendiri) dengan
   judul jendela yang terdaftar pada `allowed_window_titles`.
2. Kalibrasikan dua sudut seluruh papan 8x8. Tekan Enter di terminal lalu pindahkan
   mouse ke sudut kiri-atas dalam 5 detik. Setelah sudut pertama direkam, pindahkan
   mouse ke sudut kanan-bawah dalam 5 detik berikutnya. Jangan kembali mengklik terminal.
   Hasil yang terbalik, terlalu kecil, atau jauh dari persegi akan ditolak tanpa
   mengubah konfigurasi. Kalibrasi bisa diulang meskipun koordinat lama rusak:

   ```powershell
   chesslab --config config.json calibrate --orientation white
   ```

3. Buat template tampilan bidak dan petak kosong. Dari posisi yang FEN-nya diketahui
   (biasanya posisi awal), ambil screenshot dan potong setiap petak ke
   `templates/<nama>/` (atau `templates/empty/`). Contoh:

   ```powershell
   chesslab --config config.json collect-templates `
     --fen "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
   ```

   Ulangi setelah mengubah tema/ukuran papan. Template yang direkam mewakili tema yang
   sama; jangan gunakan template dari situs atau jendela lain.

4. Periksa hasil pengenalan tanpa menggerakkan mouse:

   ```powershell
   chesslab --config config.json inspect
   ```

   Hasil harus berupa FEN yang sesuai dan gambar debug di `runtime/last-board.png`.

## Analisis dan kontrol uji

Untuk analisis posisi (tanpa klik):

```powershell
chesslab --config config.json analyze --depth 16
```

Untuk pengawasan satu giliran di papan lokal yang diizinkan dan menjalankan langkah
Stockfish ketika warna Anda mendapat giliran:

```powershell
chesslab --config config.json play-local --my-color white --depth 16 --confirm-local-test
```

`play-local` meminta konfirmasi interaktif sebelum kontrol mouse diaktifkan. Tombol
darurat tetap aktif: arahkan mouse ke pojok kiri-atas layar untuk menghentikan klik
berikutnya.

Untuk posisi bukan awal permainan, berikan FEN lengkap sebagai sumber metadata hak
rokade, en-passant, dan giliran; ChessLab akan menolak bila susunan bidaknya tidak
cocok dengan gambar. Misalnya tambahkan `--initial-fen "..."` ke `play-local` atau
`--fen "..."` ke `analyze`.

## Cara kerja

```
window screenshot → crop 8×8 terkalibrasi → pencocokan template
       → posisi papan → langkah legal python-chess → Stockfish UCI
       → (hanya target lokal yang diizinkan) klik from → klik to
```

Pengenalan sengaja konservatif: sel dengan skor di bawah `min_template_score` dianggap
tidak pasti. ChessLab menolak mengklik bila posisi ambigu, posisi berubah di antara dua
frame, jendela target tidak aktif, bukan giliran warna yang dipilih, atau judul jendela
tidak ada di allowlist.

## Batasan praktis

- Sistem template ini paling andal bila skala, tema, dan orientasi papan tetap. Tambah
  template dengan `collect-templates` untuk setiap variasi visual.
- Animasi dapat menghasilkan frame sementara; pengawasan menunggu dua frame sama.
- Promosi membutuhkan UI papan yang menerima klik tujuan promosi; versi awal memilih
  promosi ratu dan memerlukan dialog promosi otomatis dari papan lokal.
- FEN hasil visi dipadankan dengan semua langkah legal dari posisi sebelumnya sehingga
  hak rokade, en-passant, dan giliran tidak ditebak dari gambar semata.
