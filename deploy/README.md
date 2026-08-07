# Multi-project VPS deployment — README

Template `docker-compose.yml` untuk menjalankan **Speech Translator + project lain** dalam satu VPS (target: 4GB RAM / 2–4 vCPU).

## Alokasi RAM (VPS 4GB)

| Service | RAM limit | CPU | Port |
|---|---|---|---|
| `translator` | 1.4 GB | 1.0 | 8080 |
| `webapp` (project lain) | 512 MB | 0.5 | 3000 |
| `postgres` | 1.0 GB | 0.5 | 5432 |
| `nginx` | 128 MB | 0.1 | 80/443 |
| **Total** | ~3.0 GB | 2.1 | — |

> Sisa ~1GB untuk OS + buffer. Naikkan spec jika tambah banyak project.

## Cara pakai

```bash
# 1. Siapkan secrets translator
cp ../server/.env.example ../server/.env
nano ../server/.env      # isi GROQ_API_KEY, GEMINI_API_KEY, AUTH_SECRET, ADMIN_API_KEY

# 2. Database password
cp .env.example .env
nano .env                # set DB_PASSWORD

# 3. Isi folder project lain (opsional)
mkdir -p sites/app1
echo "<h1>My App</h1>" > sites/app1/index.html

# 4. Jalankan semua
docker-compose up -d --build

# 5. Cek status
docker-compose ps
```

## Menambah project lain

1. Tambah service baru di `docker-compose.yml` (port beda, `mem_limit`/`cpus` disesuaikan).
2. Tambah blok `server` di `nginx.conf` untuk subdomain baru.
3. `docker-compose up -d`.

## Catatan RAM

- **Translator penuh** (`torch` + `faster-whisper` + `piper`) butuh ~1.5GB+. Untuk VPS 4GB aman, untuk S-1 (1GB) wajib versi ringan.
- Jika OOM, turunkan `mem_limit` atau matikan fallback lokal berat.
