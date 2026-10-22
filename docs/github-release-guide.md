# Commit, GitHub Releases dan GitHub Packages

EXE Windows didistribusikan melalui **GitHub Releases** sebagai ZIP dan checksum.
**GitHub Packages** berisi dua image Docker/OCI melalui GHCR: API lisensi dan
dashboard. GitHub Packages bukan registry Python untuk proyek ini; tidak ada
publikasi PyPI atau npm. Menjalankan workflow tidak menerapkan server ke produksi.

## Alur validasi dan rilis

`.github/workflows/ci.yml` memvalidasi push branch dan pull request: tes Windows
dengan Stockfish resmi serta build kedua container tanpa push image.
`.github/workflows/release.yml` berjalan saat tag `v*` dipush:

1. Checkout tag dengan dependency Python terkunci.
2. Unduh Stockfish dari rilis resmi yang dipin dalam `packaging/windows-assets.json`.
   Checksum SHA-256 wajib sesuai; arsip dengan traversal/symlink ditolak.
3. Siapkan konfigurasi publik, jalankan setup, tes, build, audit serta smoke EXE.
4. Buat ZIP allowlist (`ChessLab-Coach.exe`, `BACA-DULU.txt`, `build-info.json`) dan checksum.
5. Build dan publish image API/dashboard ke GHCR dengan tag versi dan SHA commit.
6. Buat draft GitHub Release, unggah aset, lalu terbitkan setelah seluruh job lulus.

Action eksternal dipin ke commit SHA. Dependabot memeriksa pembaruannya setiap bulan.
Izin `contents:write` hanya ada pada job publikasi Release; `packages:write` hanya
ada pada job container. Workflow memakai `GITHUB_TOKEN`, bukan PAT yang ditanam
dalam sumber. Tidak diperlukan signing key privat di GitHub Actions.

## Pengaturan repositori satu kali

- Aktifkan GitHub Actions untuk repositori.
- Tambahkan **repository variable**, bukan berkas tracked,
  `CHESSLAB_LICENSE_PUBLIC_JSON` berisi konfigurasi publik yang disetujui.
  Strukturnya mengikuti `licensing-public.example.json`, tetapi harus berisi
  public key Ed25519 yang valid. Jangan memasukkan `.env` atau PEM privat.
- Pastikan kebijakan organisasi mengizinkan job meminta izin `packages:write`
  dan `contents:write`.
- Paket GHCR baru dapat memiliki visibility Private. Jika diperlukan akses anonim,
  pemilik mengatur visibility paket menjadi Public melalui pengaturan paket.
  Label OCI `org.opencontainers.image.source` menghubungkan paket dengan repositori.

Panduan resmi: [publikasi image](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images),
[Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry),
[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

## Menerbitkan versi baru

1. Commit dan push perubahan sumber pada branch yang sesuai, lalu pastikan CI lulus.
2. Samakan versi dasar tag dengan `project.version` dalam `pyproject.toml`.
3. Buat catatan rilis `docs/releases/<tag>.md`.
4. Buat annotated tag dan push tag tersebut. Contoh rilis UAT pertama:

```powershell
git tag -a v0.1.0-rc.1 -m 'ChessLab PC UAT Windows v0.1.0-rc.1'
git push origin v0.1.0-rc.1
```

Tag stable `v0.1.0` tidak menerima endpoint localhost. Untuk UAT lokal gunakan
`v0.1.0-rc.1`, `-beta.N` atau `-alpha.N`. Release yang sudah terbit tidak ditimpa
otomatis; gunakan versi baru. Job dapat melanjutkan draft yang belum terbit ketika
unggahan sebelumnya terputus. Prerelease tidak diberi label latest.

Jika ingin menyiapkan arsip lokal, build dahulu **setelah** commit dibuat:

```powershell
.\scripts\build-windows.ps1
.\.venv\Scripts\python.exe -E -s scripts\prepare_release.py --tag v0.1.0-rc.1
```

Metadata harus cocok dengan commit, sumber dan checksum EXE. File lokal yang tidak
terkait build seperti `.env` tetap tidak menjadi input arsip. Jangan menjalankan
build untuk menimpa EXE yang sedang terbuka; tutup aplikasi terlebih dahulu atau
gunakan output build lain di bawah `outputs/`.

## Menggunakan image Packages

Setelah image dipublikasikan, pilih versi secara eksplisit. Tetap gunakan `.env`
lokal dan Docker secret signing key yang sudah ada:

```powershell
$env:CHESSLAB_IMAGE_TAG = '0.1.0-rc.1'
docker compose -f compose.yaml -f compose.packages.yaml pull
# Jalankan hanya ketika memang ingin memperbarui stack lokal:
docker compose -f compose.yaml -f compose.packages.yaml up -d --no-build
```

Perintah kedua menerapkan pembaruan stack; workflow rilis tidak menjalankannya.
Untuk registry milik fork, tentukan `CHESSLAB_IMAGE_PREFIX`, misalnya
`ghcr.io/organisasi/chesslabs`. Tidak ada private key atau kredensial database
dalam image. Context Docker memakai allowlist sumber yang diperlukan saja.

## Pemeriksaan setelah publikasi

- Halaman Releases menampilkan prerelease dan ZIP Windows beserta `SHA256SUMS.txt`.
- Halaman Packages menampilkan `chesslabs-license-api` dan `chesslabs-admin-dashboard`.
- Periksa run Actions serta digest image; tag `sha-<commit>` membantu penelusuran.
- Gunakan `build-info.json` dalam ZIP untuk memastikan commit, key ID, API URL
  dan checksum sesuai target UAT.
