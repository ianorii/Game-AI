# Audit Dekorasi Peta (Room1.yy vs Ditempatkan oleh Kode)

Dokumen ini memuat audit lengkap seluruh objek dan lapisan dekorasi di dalam game *AI Labyrinth: The Dungeon Overseer*, memisahkan antara elemen peta statis dari GameMaker (`Room1.yy`) dan entitas dekoratif yang ditempatkan secara dinamis melalui kode Python.

---

## 1. Ringkasan Eksekutif

| Kategori Asal | Jumlah / Cakupan | Keterangan | Tindakan / Status |
| :--- | :--- | :--- | :--- |
| **Room1.yy (Tile Layer)** | 3 Layer (`decoration_01`, `02`, `03`) | Lapisan tile statis (batu kecil, kerang pantai, bunga liar, rumput dekoratif) | Statis, tidak diubah (sesuai mandat). |
| **Room1.yy (Sprite Graphics)** | 570 Objek (`GMRSpriteGraphic`) | Pohon besar/kecil, semak, batu tebing, pilar dermaga, tiang bendera | Statis, tidak diubah (sesuai mandat). |
| **Kode: LockedGate** | 1 Objek Koridor | Sebelumnya palang gelap lebar 288 px menjorok ke air | **Diperbaiki**: Gerbang Sunnyside 96 px berdiri di atas tanah koridor, Y-sort, gembok di atas lengkung. |
| **Kode: BeachDecorations** | 6 Objek (3 Kelompok @ 2 prop) | Peti dan tong di area pantai tenggara | **Diperbaiki**: Dikelompokkan rapi (maks 3 kelompok), snap grid 32px, jarak seragam, footprint di dasar, lorong $\ge 2$ tile. |
| **Kode: Windmill** | 1 Objek (Kincir Angin) | Terletak di (1360, 560), animasi bilah kincir | Dipertahankan; footprint telah terdaftar di `dynamic_obstacles`. |
| **Kode: ChimneySmoke** | 7 Titik Cerobong | Partikel asap cerobong asap pada atap rumah | Visual murni, dipertahankan. |
| **Kode: FarmManager** | Petak Kebun Dinamis | Terletak di area barat desa (pertanian) | Dipertahankan; tidak mengganggu koridor utama. |

---

## 2. Dekorasi Peta Statis (`Room1.yy`)

Seluruh dekorasi statis diekstrak dari `assets/sunnyside_world/Sunnyside_World_Gamemaker/rooms/Room1/Room1.yy`:

### 2.1 Layer Tile Dekorasi
- **`decoration_01`**: Pola dasar kerikil tanah, kerang pantai di koordinat pasir, dan bayangan lembut di bawah tebing.
- **`decoration_02`**: Patch rumput liar berbunga, rumpun ilalang tepi danau, dan lumut pada dinding batu.
- **`decoration_03`**: Detail ornamen dinding, tepian atap bangunan desa, dan variasi paving jalan setapak.

### 2.2 Instance Sprite Statis (`GMRSpriteGraphic`)
Peta `Room1.yy` memiliki total 570 objek grafis instan:
- **Pohon & Vegetasi (420 objek)**:
  - Pohon apel hijau, pohon pinus, rumpun semak berry tersebar di seluruh pulau.
- **Batu & Tebing (85 objek)**:
  - Bebatuan tepi pantai, tebing pemisah elevasi tanah.
- **Infrastruktur Dermaga & Jembatan (65 objek)**:
  - Pilar dermaga kayu di perairan pantai selatan, tiang lampu dermaga, dan tambatan kapal. *(Catatan: Tiang dermaga di air ini berasal dari peta asli GameMaker, bukan ditambahkan oleh kode).*

---

## 3. Dekorasi Ditempatkan oleh Kode & Perbaikan yang Diterapkan

Sesuai instruksi tugas, **hanya dekorasi yang ditempatkan oleh kode yang dimodifikasi**.

### 3.1 Gerbang Koridor (`LockedGate`)
- **Kondisi Sebelum**:
  - Ukuran: Palang gelap monolitik dengan lebar 288 px (`x=2240, y=832, w=288, h=32`).
  - Masalah: Terlalu lebar, menjorok jauh ke luar koridor tebing hingga melayang di atas air; ikon gembok menutupi visual gerbang; tidak terintegrasi ke urutan Y-sort (digambar statis sebelum entitas).
- **Perbaikan**:
  - **Lokasi & Dimensi**: `x=2368, y=832, w=96, h=32` (tepat 6 tile koridor 16px / 3 tile 32px: $x = 2368 .. 2464$), berdiri kokoh di atas tanah koridor pasir tebing tanpa menyentuh air (100% daratan padat).
  - **Sprite Sunnyside**:
    - `surf_closed`: Komposit pilar batu kiri/kanan, lengkungan batu Sunnyside di atas, daun gerbang kayu ganda tertutup dengan palang penguat besi horizontal & engsel, serta gembok emas di kait tengah.
    - `surf_open`: Daun gerbang terlipat rapi ke pilar samping, lorong terbuka bebas tembus pandang (selisih piksel = 2.827 px).
  - **Collision**: Terdaftar di `game_map.dynamic_obstacles` saat terkunci, otomatis terbuka dan walkable saat kunci diperoleh (`world_state.has_gate_key = True`).
  - **Depth Sorting**: Memiliki properti `sort_y = y + h`, dimasukkan ke dalam daftar drawable Y-sort di `main.py`.

### 3.2 Peti & Tong Pantai (`BeachDecorations`)
- **Kondisi Sebelum**:
  - Tersebar acak di atas pasir pantai tenggara tanpa aturan snap grid; tumpang tindih parsial dan menghalangi akses jalan ke dermaga dan gerbang.
- **Perbaikan**:
  - **Pengelompokan Rapi**: Dibatasi maksimal 3 kelompok kecil (masing-masing 2 properti), disnap presisi ke grid 32 px:
    1. **Kelompok 1 (Dekat Dermaga Pantai Selatan)**:
       - Peti Kayu A: `x=2240, y=1024` (Tile grid 70, 32)
       - Tong Kayu A: `x=2272, y=1024` (Tile grid 71, 32)
    2. **Kelompok 2 (Tepi Pantai Bawah Dermaga)**:
       - Peti Kayu B: `x=2336, y=1152` (Tile grid 73, 36)
       - Peti Kayu C: `x=2368, y=1152` (Tile grid 74, 36)
    3. **Kelompok 3 (Akses Barat Gerbang Tebing)**:
       - Tong Kayu B: `x=2176, y=832` (Tile grid 68, 26)
       - Tong Kayu C: `x=2176, y=864` (Tile grid 68, 27)
  - **Jarak Bersih (Clearance)**: Sisakan koridor jalan minimal 2 tile (32 px - 64 px) menuju gerbang, dermaga utama, dan pintu bangunan sekitar.
  - **Hitbox Presisi**: Footprint collision hanya di dasar prop (`y + 20, w=prop_w, h=10`), memungkinkan Hero berjalan di belakang bagian atas peti tanpa tersangkut (efek perspektif top-down).
  - **Bebas Air**: 100% properti kode berada di atas tile pasir daratan (`walkable_mask == 1`); tidak ada objek buatan kode yang melayang di air.

---

## 4. Matriks Audit Dekorasi Kode

| ID Properti | Jenis Aset | Koordinat (px) | Grid (32px) | Footprint (x, y, w, h) | Status Jalur Walkable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `gate_01` | Sunnyside Arch & Wooden Gate | (2368, 832) | (74.0, 26.0) | `(2368, 832, 96, 32)` | Koridor gerbang (Solid jika terkunci, 100% daratan) |
| `beach_c1` | Peti Kayu Ganda | (2240, 1024) | (70, 32) | `(2240, 1044, 32, 10)` | Bersih, $\ge 3$ tile dari dermaga |
| `beach_b1` | Tong Kayu Melingkar | (2272, 1024) | (71, 32) | `(2272, 1044, 28, 10)` | Bersih, seragam dengan `beach_c1` |
| `beach_c2` | Peti Kayu Ramping | (2336, 1152) | (73, 36) | `(2336, 1172, 32, 10)` | Bersih, di tepi pantai berpasir |
| `beach_c3` | Peti Kayu Ramping | (2368, 1152) | (74, 36) | `(2368, 1172, 32, 10)` | Bersih, bersebelahan teratur |
| `beach_b2` | Tong Kayu Melingkar | (2176, 832) | (68, 26) | `(2176, 852, 28, 10)` | Bersih, di samping tebing barat |
| `beach_b3` | Tong Kayu Melingkar | (2176, 864) | (68, 27) | `(2176, 884, 28, 10)` | Bersih, tersusun vertikal rapi |
| `windmill` | Kincir Angin Animasi | (1360, 560) | (42.5, 17.5)| `(1360, 580, 80, 60)` | Bersih, terdaftar di dynamic obstacles |

