<div align="center">

# Game AI - 2D Pathfinding RPG

Game RPG 2D yang dibangun dengan **Python** dan **Pygame** yang menampilkan algoritma AI pathfinding dengan visualisasi secara *real-time*.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Pygame](https://img.shields.io/badge/Pygame-2.6-12D000?style=for-the-badge&logo=pygame&logoColor=white)](https://pygame.org)
[![License](https://img.shields.io/badge/Lisensi-MIT-yellow?style=for-the-badge)](#)

---

</div>

## Fitur Utama

- **Pathfinding A*** dengan 5 heuristik yang dapat diatur
  - Manhattan, Euclidean, Chebyshev, Octile, dan UCS (*Uniform Cost Search*)
- **NPC Otonom** yang mengikuti pemain menggunakan A* dengan interpolasi mulus
- **Grid Editor Interaktif** untuk mengubah peta tabrakan (*collision map*) secara *real-time*
- **Debug Overlay** untuk memvisualisasikan node yang dikunjungi, jalur, dan statistik ekspansi
- **Deteksi Objek Berbasis Piksel** dari gambar peta untuk tabrakan yang akurat
- **Analisis Konektivitas Grid** untuk memastikan area yang bisa dilalui membentuk satu komponen terhubung
- **Kontrol Ganda**: WASD/Tombol Panah untuk gerakan manual, klik mouse untuk navigasi A*
- **Mode Layar Penuh / Jendela** dengan pengaturan ulang dinamis

## Tangkapan Layar

<div align="center">
  <img src="assets/images/full map.png" alt="Full Map" width="100%">
</div>

## Instalasi

1. **Clone repositori**
   ```bash
   git clone https://github.com/ianorii/Game-AI.git
   cd Game-AI
   ```

2. **Instal dependensi**
   ```bash
   pip install -r requirements.txt
   ```

3. **Jalankan game**
   ```bash
   python main.py
   ```

## Kontrol

| Tombol | Aksi |
|---|---|
| `WASD` / `Tombol Panah` | Gerakkan pemain secara manual |
| `Klik Kiri` | Atur target pathfinding A* |
| `Q` / `E` | Ganti heuristik pemain |
| `T` / `G` | Ganti algoritma NPC |
| `F` | Aktifkan/nonaktifkan mode ikuti NPC |
| `M` | Buka/tutup grid editor |
| `P` | Simpan grid ke file |
| `L` | Muat grid dari file |
| `R` | Reset pemain & NPC |
| `1` / `2` / `3` | Alihkan lapisan debug |
| `F11` | Alihkan layar penuh |
| `ESC` | Keluar |

## Struktur Proyek

```
Game-AI/
├── main.py              # Titik masuk & loop utama game
├── map.py               # Pemuatan peta, grid tabrakan, viewport
├── npc.py               # Perilaku NPC & pathfinding
├── player.py            # Gerakan pemain & navigasi A*
├── pathfinding.py       # Algoritma A* dengan varian heuristik
├── debug_overlay.py     # Lapisan visualisasi debug
├── utils.py             # Fungsi utilitas bersama
├── grid_override.txt    # Data override grid
├── requirements.txt     # Dependensi Python
└── assets/              # Aset game (gambar, font, suara)
```

## Cara Kerja

### Pathfinding

Game menggunakan algoritma **A*** dengan *priority queue* untuk menghitung jalur optimal. Setiap heuristik memberikan keseimbangan berbeda antara kecepatan dan akurasi:

| Heuristik | Terbaik Untuk | Strategi |
|---|---|---|
| **Manhattan** | Grid 4 arah | `|dx| + |dy|` |
| **Euclidean** | Jarak umum | `sqrt(dx² + dy²)` |
| **Chebyshev** | Grid 8 arah | `max(|dx|, |dy|)` |
| **Octile** | 8 arah dengan diagonal | Jarak oktil yang dioptimalkan |
| **UCS** | Eksplorasi seragam | `h(n) = 0` |

### Sistem Tabrakan

1. Analisis warna tingkat piksel mendeteksi objek penghalang (air, atap, batu, pagar)
2. Area jembatan dan taman mendapat penanganan tabrakan khusus
3. Analisis komponen terhubung memastikan area yang dapat dilalui membentuk satu wilayah yang terjangkau
4. Grid dapat diedit secara manual serta disimpan/dimuat dari `grid_override.txt`

## Lisensi

Lisensi MIT - bebas digunakan dan dimodifikasi untuk proyek Anda.