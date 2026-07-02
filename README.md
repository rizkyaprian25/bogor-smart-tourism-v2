# 🚗 Bogor Smart Tourism — Optimasi Perencanaan Perjalanan Wisata

Aplikasi web yang membantu wisatawan merencanakan rute perjalanan wisata di Kota Bogor secara lebih efisien. Sistem tidak hanya menyusun urutan destinasi yang ingin dikunjungi, tetapi juga mempertimbangkan **prediksi kemacetan lalu lintas real-time**, sehingga rute yang dihasilkan lebih realistis dan menghemat waktu perjalanan pengguna.

🎥 **Demo:** [Tonton di sini](https://drive.google.com/file/d/15I_QUsRtC1KhCEeMXnjfdkpPvMxHEq9w/view?usp=drive_link) <!-- ganti # dengan link YouTube/Drive demo Anda -->

---

## ✨ Fitur Utama

- 🔮 **Prediksi kemacetan lalu lintas** menggunakan model *Random Forest Regression*, dilatih terpisah untuk kendaraan **mobil** dan **motor**.
- 🧭 **Optimasi urutan kunjungan destinasi** (rute open-path TSP) menggunakan **Google OR-Tools** (`PATH_CHEAPEST_ARC` + `Guided Local Search`).
- 🗺️ Estimasi rute & jarak real-time via **TomTom Routing API**.
- 👤 Sistem **autentikasi pengguna** (register/login) dengan password ter-hash (`werkzeug`).
- 📜 **Riwayat perjalanan** tersimpan per pengguna, lengkap dengan statistik rute optimal vs rute terburuk.
- 🗄️ Basis data & autentikasi menggunakan **Supabase** (PostgreSQL).
- 🐳 Siap deploy dengan **Docker & Docker Compose**.

---

## 🛠️ Tech Stack

| Kategori        | Teknologi                                   |
|------------------|---------------------------------------------|
| Backend          | Python, Flask                               |
| Machine Learning | Scikit-learn (Random Forest Regression)     |
| Optimasi Rute    | Google OR-Tools                             |
| Database         | Supabase (PostgreSQL)                       |
| Routing API      | TomTom Routing API                          |
| Frontend         | HTML, CSS, JavaScript                       |
| Deployment       | Docker, Docker Compose                      |

---

## 📂 Struktur Proyek

```
├── app.py                  # Entry point Flask & routing utama
├── run.py                  # Script menjalankan server + validasi dependencies
├── config.py                # Konfigurasi environment, path, dan constants
├── auth_manager.py          # Logika register & login pengguna
├── db_logger.py             # Simpan & ambil riwayat itinerary dari Supabase
├── supabase_client.py       # Inisialisasi koneksi Supabase
├── itinerary_engine.py      # Logika penyusunan itinerary
├── optimizer.py             # TSP Solver (OR-Tools)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── data/                    # Dataset traffic & master lokasi
└── models/                  # Model Random Forest (mobil & motor)
```

---

## 🚀 Cara Menjalankan

### 1. Clone repository
```bash
git clone https://github.com/rizkyaprian25/bogor-smart-tourism.git
cd bogor-smart-tourism
```

### 2. Buat file `.env`
Buat file `.env` di root project (lihat `.env.example` jika tersedia), isi dengan:
```env
TOMTOM_API_KEY=your_tomtom_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
FLASK_SECRET_KEY=your_random_secret_key
FLASK_DEBUG=False
```
> ⚠️ Jangan pernah commit file `.env` ke repository — file ini sudah masuk `.gitignore`.

### 3a. Jalankan dengan Docker (disarankan)
```bash
docker-compose up --build
```

### 3b. Atau jalankan secara lokal
```bash
pip install -r requirements.txt
python run.py
```

Aplikasi akan berjalan di `http://localhost:5000` (atau `http://localhost:5001` jika menggunakan Docker Compose).

---

## 📊 Hasil

Aplikasi berhasil menghasilkan rekomendasi rute wisata yang mempertimbangkan kondisi lalu lintas secara real-time, membantu wisatawan merencanakan perjalanan yang lebih efisien dan hemat waktu di Kota Bogor.

---

## 👤 Kontak

**Muhamad Rizky Aprian**
Mahasiswa S1 Ilmu Komputer, Universitas Pakuan Bogor

- 📧 rizkyboboy31@gmail.com
- 💼 [LinkedIn](https://linkedin.com/in/rizky-aprian-043b25360)
- 🐙 [GitHub](https://github.com/rizkyaprian25)
