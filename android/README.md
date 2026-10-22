# ChessLab Coach Android — prototipe 0.2.1

Target utama: Samsung Galaxy A34 5G, Android 16. APK ARM64, minimum Android 14,
target API 36. Ini aplikasi Android native Java; aplikasi PC tetap terpisah.

## Menu mengambang dan logo

- Ketuk **Minimalkan** atau judul Coach untuk menyembunyikan seluruh panel menjadi
  logo pion kecil 48 dp. Teks, status, dan tombol ikut disembunyikan.
- Ketuk logo untuk membuka menu kembali. Logo maupun judul dapat digeser.
- **Sembunyi otomatis: ON/OFF** mengatur pengecilan otomatis setelah 5 detik
  tanpa sentuhan. Bawaan ON; pilihan tersimpan untuk sesi berikutnya.
- Saat OFF, menu tetap terbuka sampai diminimalkan secara manual. Logo tetap
  terlihat samar ketika diminimalkan agar lokasi untuk membuka menu mudah ditemukan.
- Area sentuh saat diminimalkan hanya sebesar logo, bukan bekas panel besar.
  Letakkan logo di luar papan agar pembacaan tetap berjalan.
- Pembacaan dan analisis terus berjalan saat menu diminimalkan. Perubahan status
  tidak membuka panel sendiri. Pemilihan Area menunda penyembunyian otomatis.

## Respons cepat dan mekanisme otomatis dari PC

- Pemeriksaan layar berkala; frame akhir langkah tidak dibuang karena pembatas
  waktu. Layar yang diam menggunakan piksel terakhir sampai ada frame baru.
- Cache per petak: hanya gambar petak yang berubah yang diklasifikasi ulang.
  Huruf koordinat, termasuk **b** pada **b1** kosong, diabaikan.
- Buffer capture dipakai ulang. Mesin disiapkan ketika sesi dimulai; analisis
  posisi lama dibatalkan dan posisi terbaru segera diproses. Hasil posisi yang
  sama dapat digunakan kembali.
- Papan dicari otomatis saat sesi dimulai. Tema tersimpan dicoba otomatis;
  tema baru tetap memerlukan **Pelajari** satu kali pada posisi awal.
- Pencarian ulang setelah kegagalan selama sekitar satu detik, dengan jarak
  minimal tiga detik. Pencarian papan dan tema berjalan di worker terpisah.
- Pergeseran ukuran layar, orientasi papan, posisi awal partai baru, serta satu
  langkah pembuka putih ditangani otomatis. Reset partai memerlukan tiga
  pengamatan stabil; langkah biasa memerlukan dua.
- **Baca kini** menyambung posisi berjalan tanpa mempelajari ulang tema.
  Warna pemain tetap sama saat tampilan dibalik. Pilihan **Otomatis saat mulai**
  mengambil warna sisi bawah saat pertama sinkron dan ketika partai baru dikenali.

| Respons | Interval pemeriksaan target | Anggaran analisis |
|---|---:|---:|
| Cepat | 80 ms | 180 ms |
| Seimbang | 120 ms | 450 ms |
| Mendalam | 180 ms | 1.200 ms |

**Human kini memakai anggaran yang sama, tanpa pengali 3.** Cepat menjadi bawaan
untuk pemasangan baru; pilihan yang sudah tersimpan tetap digunakan. Ketuk tombol
nama profil pada overlay untuk beralih Cepat → Seimbang → Mendalam → Cepat.
Angka ini merupakan interval/anggaran, bukan janji latensi total di HP.
Analisis singkat bisa mencapai kedalaman lebih rendah.

Indikator **Baca** mengukur pengenalan dan menunjukkan jumlah petak yang dihitung
ulang. **Mesin** menunjukkan waktu analisis terakhir. Waktu tangkap layar dan
penantian posisi stabil tidak termasuk. Lihat `HASIL-RESPONS-ANDROID.md` untuk
pengukuran di komputer pengembangan.

## Perbaikan pembacaan yang tetap disertakan

- Memperbaiki deteksi yang dapat bergeser satu baris atau memotong tepi papan,
  khususnya pada papan yang memenuhi lebar layar. Label koordinat tidak lagi
  menjadi satu-satunya lokasi sampel untuk mencari pola papan.
- Mengganti area otomatis saat pemulihan hanya jika area baru berhasil dibaca.
- Pesan kegagalan menyebut petak yang belum jelas, misalnya **e6**.
- **Pelajari** memeriksa semua petak berisi/kosong terhadap posisi awal. Posisi
  setelah **1.e4 e6** ditolak agar tidak menyimpan contoh tema yang salah.

Pasang APK pembaruan di atas versi lama, lalu mulai sesi baru. Tema lama tetap
dapat dipakai. Jika tema lama masih gagal: mulai partai baru dengan semua bidak
pada posisi awal, tekan **Cari**, lalu **Pelajari** sebelum melangkah.
Jika batas papan masih salah, gunakan **Area** untuk memilih seluruh papan 8×8.

## Memasang dan menggunakan

1. Salin `outputs/android/ChessLab-Coach-Android.apk` ke HP dan buka APK tersebut.
   Izinkan pemasangan dari aplikasi yang dipakai membuka APK jika Android memintanya.
2. Buka **ChessLab Coach**, pilih level (bawaan **Human**) dan **Respons: Cepat**.
   Warna pemain dan sisi bawah dapat memakai pilihan otomatis.
3. Tekan **Izinkan tampil di atas aplikasi**, aktifkan izin untuk Coach, lalu kembali.
4. Tekan **Mulai pembacaan layar**. Setujui berbagi layar penuh dan izin notifikasi.
   Sesi berjalan sebagai foreground service dengan notifikasi Hentikan.
5. Buka aplikasi papan tujuan. Tema yang pernah dipelajari akan dipakai otomatis.
   Untuk tema baru, tampilkan **posisi awal standar lengkap**.
6. Geser panel Coach ke luar papan dengan menarik judulnya. Ketuk judul untuk
   mengecilkan panel menjadi logo; ketuk logo untuk membukanya. Panel yang menutupi papan akan menghentikan pembacaan.
7. Tunggu pencarian otomatis; **Cari** memicu pencarian langsung. Jika batas kurang tepat, tekan **Area**,
   lalu tarik dari satu sudut papan ke sudut seberangnya. Area harus seluruh 8×8 petak.
8. Untuk tema baru, tekan **Pelajari** saat posisi awal masih terlihat. Warna sisi
   bawah dicoba otomatis; jika ambigu pilih Putih/Hitam di pengaturan. Tema disimpan
   setelah gambar diam, lalu pembacaan dilanjutkan. Jangan memakai Pelajari di tengah permainan.
9. Lingkaran kosong menandai asal; titik penuh menandai tujuan. Gerakkan bidak manual.
   **Jeda/Lanjut** mengendalikan pemantauan; **Balik** mengubah orientasi;
   **Baca kini** menyambung posisi sekarang; **Stop**
   mengakhiri sesi dan melepas izin tangkapan layar aktif.

Tema yang sudah tersimpan dicoba kembali jika pengenalan tema aktif gagal. Untuk
tema baru, ulangi pembelajaran dari posisi awal. Tidak ada daftar nama aplikasi
atau koordinat papan khusus yang di-hardcode. Papan harus 2D, persegi, terlihat
penuh, dan cukup besar. Pola warna bertekstur/3D dapat memerlukan kalibrasi manual
atau belum bisa dikenali.

## Menyambung posisi dan pergantian orientasi

Saat sesi baru dimulai, Coach mencoba posisi awal/FEN tersimpan dan kesinambungan
langkah legal. Dengan tema tersimpan, posisi tengah permainan juga bisa dibaca
setelah tiga pengamatan stabil. Pilihan **Giliran awal: Auto** menunggu satu
langkah yang terlihat untuk membuktikan giliran; posisi skak dapat membuktikan
giliran tanpa menunggu. Pilih Putih/Hitam jika giliran sudah diketahui.

Sambungan dari gambar tidak mengaktifkan hak rokade atau en passant lama yang
belum diketahui. Masukkan **FEN lengkap** dan gunakan **Simpan pengaturan /
sinkronkan FEN** untuk mempertahankan informasi itu. Pelacak mencocokkan satu atau
dua ply. Jika lebih banyak langkah terlewat, ketuk **Baca kini** atau sinkronkan FEN.

Orientasi yang dibalik diselesaikan melalui kesinambungan langkah legal. Saat
pertama menyambung tengah permainan, posisi pion membantu memilih orientasi;
posisi endgame yang ambigu memerlukan pilihan sisi bawah Putih/Hitam. Tombol
**Balik** tetap tersedia. Rotasi/resolusi layar memicu pencarian ulang otomatis
dan tetap menghormati **Jeda** yang dipilih pengguna.

## Level dan privasi

- **Maksimal**: rekomendasi utama Stockfish dalam anggaran waktu yang dipilih.
- **Human**: Skill Level 20 dengan MultiPV hingga 5, pemilihan acak berbobot dan
  preferensi langkah sederhana. Toleransi estimasi 35 cp, atau 15 cp saat skak/
  tersisa paling banyak 10 buah. Garis mat terbaik diprioritaskan. Kekuatan bisa
  berkurang dan ini bukan jaminan gaya manusia/Elo tertentu.
- **Menengah/Pemula**: Skill Level 10/0; hasil mengikuti bestmove mesin.
- **Blunder 15%**: peluang memilih kandidat dengan penurunan setidaknya 150 cp,
  bila pencarian menyediakan kandidat tersebut.

Mesin memakai 2 thread dan hash 64 MiB. Human memakai MultiPV hingga 5 dalam
anggaran profil yang dipilih. Rekomendasi memerlukan posisi legal dan stabil.
Hasil lama dibuang saat posisi/pengaturan/sesi berubah; analisisnya dihentikan.

APK tidak meminta INTERNET. Gambar layar diproses di memori dan tidak disimpan.
Yang disimpan: pengaturan dan fitur gambar tema bidak. Izin layar diperlukan lagi
untuk setiap sesi baru. Android/aplikasi tujuan dapat melindungi layar atau menolak
overlay; aplikasi ini tidak melewati pembatasan tersebut.

## Status pengujian

Sudah diperiksa pada mesin pengembangan:

- Kompilasi Java dan DEX untuk API 36.
- Perft posisi awal sampai kedalaman 4 (197.281 node).
- 224 posisi langkah legal dibandingkan dengan python-chess.
- 164 pemeriksaan pembacaan dari 92 kasus gambar buatan memakai tema PC, termasuk
  orientasi terbalik, marker overlay, highlight kuning, dan posisi **1.e4 e6**.
- Deteksi dan pembelajaran otomatis pada lebar 720, 738, dan 1080 piksel,
  dilanjutkan pembacaan langkah. Ini simulasi geometri layar HP, bukan pengujian
  langsung terhadap file screenshot pengguna.
- Penyimpanan/pemuatan tema, penolakan layar kosong dan enam percobaan pembelajaran
  setelah **1.e4 e6**, serta pesan petak **e6** saat gambarnya tertutup.
- Rekonstruksi posisi **1.d4 d6 2.e4 Nf6 3.Nc3 e5**, huruf koordinat pada petak
  kosong, cache 0/2 petak, pergantian tema/area, dan kompatibilitas tema 0.1.1.
- 49 pemeriksaan aturan otomatis, termasuk sambung posisi/giliran, orientasi,
  reset partai baru, dan pembatasan pencarian ulang.
- Protokol Java UCI untuk kelima level terhadap Stockfish Windows, termasuk mat,
  pembatalan analisis lama, dan kelanjutan analisis setelah pembatalan.

**Belum diuji secara langsung pada Samsung A34 atau emulator Android.** Pengujian
JVM memakai adapter gambar untuk matematika pengenalan, bukan pengganti runtime
Android. Stabilitas izin layar, proses ARM64, koordinat overlay, dan tema aplikasi
di HP harus diverifikasi setelah pemasangan. APK ditandatangani dengan kunci
pengembangan lokal, belum merupakan rilis Play Store.

Rincian pemeriksaan APK ada di `verification.json`; hasil pengenalan dan hash
kode yang diuji ada di `vision-verification.json` dan `automation-verification.json`.

## Build

Java 17 diperlukan. Cara tanpa Android Studio (PowerShell dari root proyek):

```powershell
.\.venv\Scripts\python.exe android/tools/prepare.py
.\.venv\Scripts\python.exe android/tools/build.py
```

`prepare.py` mengambil SDK resmi Google dan binary Stockfish resmi yang dipin
dengan SHA-256. Untuk build saat server aset GitHub tidak dapat diakses:

```powershell
.\.venv\Scripts\python.exe android/tools/ndk_parts.py
.\.venv\Scripts\python.exe android/tools/build_engine.py
.\.venv\Scripts\python.exe android/tools/build.py
```

Build mesin lokal menggunakan sumber distribusi Stockfish yang dirujuk
`config.json`, mengekspor NNUE dari mesin Windows tersebut dan memverifikasi hash
nama jaringannya. NDK r27d menghasilkan ARM64 NEON PIE dengan alignment 16 KiB.
`engine-build.json` mencatat hash binary. Source dan NNUE lengkap disertakan
dalam `assets/engine-source.zip` bersama lisensi GPLv3.

SDK/NDK dan hasil perantara berada di `work/`; kunci pengembangan ada di
`work/android-build/development.jks`. Pertahankan kunci ini untuk memasang pembaruan
di atas APK yang sama. Jangan gunakan kunci pengembangan ini untuk distribusi publik.

Alternatif: buka folder `android` di Android Studio (AGP 8.10.1, SDK 36), setelah
`app/src/main/jniLibs/arm64-v8a/libstockfish.so` dan assets mesin tersedia.

## Rujukan platform

- https://developer.android.com/media/grow/media-projection
- https://developer.android.com/reference/android/media/ImageReader#acquireLatestImage()
- https://developer.android.com/develop/background-work/services/fgs/service-types
- https://developer.android.com/reference/android/Manifest.permission#SYSTEM_ALERT_WINDOW
- https://developer.android.com/guide/practices/page-sizes
- https://stockfishchess.org/download/
