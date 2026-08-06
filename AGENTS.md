# Project Rules (AGENTS.md)

## ⚠️ Path Rule — WAJIB

Selalu gunakan path lengkap dengan username yang **BENAR**:

```
C:\Users\erland.faturrahman\Documents\Pribadi\speech-translator-enterprise
```

**JANGAN PERNAH** memakai path dengan typo `erald` (tanpa "n"):

- ❌ `C:\Users\erald.faturrahman\...` — SALAH
- ✅ `C:\Users\erland.faturrahman\...` — BENAR

> Alasan: memakai `erald` membuat folder/direktori terpisah, sehingga file yang diedit tidak muncul di proyek yang benar. Ini pernah menyebabkan revisi, `.gitignore`, dan `.env.example` tersimpan ke folder salah.

## Pedoman Operasional

1. Untuk perintah bash, gunakan parameter `workdir` yang benar:
   `C:\Users\erland.faturrahman\Documents\Pribadi\speech-translator-enterprise`
   (atau subfolder seperti `server`, `extension`).
2. Untuk edit/read/write file, selalu tulis path penuh `...\erland.faturrahman\...`.
3. Jangan pernah menghapus atau menimpa file di luar workspace tanpa izin.
4. Berhati-hati mengetik path: `erland` (dengan "n"), bukan `erald`.

## ⚠️ Self-Check Anti-Typo `erald` — WAJIB DI SETIAP SESI

Model cenderung berulang kali mengetik `erald` (tanpa "n") saat menulis path. Untuk
mencegah file tersimpan ke folder salah, patuhi langkah berikut:

1. **Setelah SETIAP operasi edit/read/write file**, verifikasi path yang DITULIS
   memakai `erland` (dengan "n"), BUKAN `erald`. Jika ragu, salin path dari hasil
   `pwd`/`sed` sebelumnya, jangan mengetik ulang manual.
2. **Di awal & akhir sesi**, cek apakah folder typo muncul:
   ```bash
   ls -la "C:\Users\erald.faturrahman" 2>/dev/null && echo "⚠️ FOLDER ERALD ADA" || echo "✅ bersih"
   ```
   Jika ada, laporkan ke user dan (dengan izin) pindahkan/hapus file duplikatnya.
3. **Jangan asumsikan `tool` sukses = path benar.** Tool kadang "berhasil" menulis
   ke folder `erald`. Selalu konfirmasi file ada di path `erland` yang benar
   (misal cek `mtime`/`ls`) bila ragu.

