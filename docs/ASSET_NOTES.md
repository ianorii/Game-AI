# Catatan Teknis Aset & Gerbang (Asset Notes)

Dokumen ini mendokumentasikan spesifikasi teknis aset baru gerbang chokepoint menuju Boss (*Skeleton Overlord*), integrasi tileset Sunnyside World, audit lebar koridor, dan verifikasi jangkauan flood-fill.

---

## 1. Komposisi Gerbang Sunnyside World

### Sumber Tile Otentik
Gerbang disusun dari tile otentik yang dipotong langsung dari berkas tileset resmi:
- **Berkas Tileset**: `assets/sunnyside_world/Tileset/spr_tileset_sunnysideworld_16px.png` (resolusi 1024 x 1024 piksel, grid 16 x 16 piksel, 64 kolom x 64 baris).
- **Faktor Skala**: 2x (menjadi resolusi 32 x 32 piksel per tile untuk menyamai resolusi peta pulau HD 2752 x 1536).

### Komponen Potongan Tile:
1. **Lengkung Pilar Batu Otentik (Authentic Slate Grey Stone Arch)**:
   - Pilar Batu Kiri: Kolom 49, Baris 28–30 (skala 4x potongan tersedia di `docs/figures/tile_debug/stone_49_28_4x.png` s.d. `stone_49_30_4x.png`).
   - Pilar Batu Kanan: Kolom 50, Baris 28–30 (skala 4x potongan tersedia di `docs/figures/tile_debug/stone_50_28_4x.png` s.d. `stone_50_30_4x.png`).
   - Balok Lintel / Keystone Tengah: Kolom 49–50, Baris 28.
   - Kolase utuh potongan tile 4x: [gate_tiles_used_4x.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/figures/tile_debug/gate_tiles_used_4x.png).
2. **Daun Pintu Kayu (Wooden Gate Leaves)**:
   - Panel Kayu Berpola: Kolom 35 & 37, Baris 24 (`wood_35_24_4x.png`, `wood_37_24_4x.png`).
   - Tertutup: Pintu kayu ganda solid rapat dengan palang besi penguat dan gembok emas di tengah.
   - Terbuka: Daun pintu terlipat rapi ke pilar samping, lorong tengah tembus pandang (selisih piksel = **2.827 px**, jauh di atas ambang > 1.000 px).
3. **Simbol Gembok Emas**:
   - Gembok emas proporsional di tengah engsel gerbang, tidak menutupi lanskap maupun pilar.
4. **Klarifikasi Asal Tumpukan Peti/Tong di Bawah Gerbang**:
   - Dua tumpukan peti/tong di bawah gerbang berasal dari peta asli GameMaker (`Room1.yy`): `spr_deco_barrel_closed` pada koordinat $(2356, 894)$ dan $(2356, 916)$ (`graphic_219CF33` dan `graphic_614AA62E`).
   - Objek ini adalah dekorasi asli room room1.yy yang tidak boleh dimutasi tanpa merusak integritas room map. Tapak gerbang ditempatkan pada $y = 832..864$, sehingga terdapat jarak penyangga aman $\approx 30$ piksel di atas tong-tong tersebut.
5. **Klarifikasi Screenshot Bar Gelap 260px**:
   - Bar gelap transparan lebar ~260–288 px dengan titik kuning yang terlihat pada pengujian sebelumnya adalah sisa prototipe mockup komparasi (`OldLockedGate`). Seluruh mockup tersebut telah dibersihkan secara tuntas dari codebase.
6. **Fallback Mode**:
   - Jika berkas tileset tidak ditemukan di sistem, kode secara otomatis menjalankan rendering prosedural cadangan dengan palet warna resmi Sunnyside (`C_STONE_*`, `C_WOOD_*`, `C_IRON_*`, `C_GOLD_*`).

---

## 2. Geografi Koridor Chokepoint & Dimensi Gerbang

### Masalah Desain Lama (Sebelum Perbaikan):
- Lebar obstacle lama: **288 px** ($x = 2240 .. 2528$).
- Koridor fisik sebenarnya hanya selebar **96 px** ($x = 2368 .. 2464$).
- Dampak: Lebih dari 192 px dari bar gerbang lama melayang di atas air pantai barat dan menembus tebing timur.

### Spesifikasi Desain Baru (Setelah Perbaikan):
- **Posisi Gerbang**: $x = 2368$, $y = 832$.
- **Lebar Gerbang**: **96 px** (persis 3 tile ukuran 32 px: $x = 2368 .. 2464$).
- **Tinggi Tapak Gerbang**: **32 px** ($y = 832 .. 864$).
- **Hitbox Rintangan Dinamis**: `pygame.Rect(2368, 832, 96, 32)`.
- **Dinding Sisi Kiri (Barat)**: Tebing pantai dan dinding timur `building_70_26` pada $x \le 2368$.
- **Dinding Sisi Kanan (Timur)**: Tebing karang timur pada $x \ge 2464$.
- **Status Tanah**: **100% berdiri di atas daratan padat** (`walkable_mask == 1`, 0% piksel air). Diuji dan dibuktikan dalam unit test `test_gate_stands_on_land_not_water`.

---

## 3. Kebijakan Area Atap Bangunan 2.5D (Roof Policy)

Dalam perspektif 2.5D *top-down* RPG (proyeksi miring), atap bangunan menjulang ke atas pada koordinat kanvas layar (koordinat $y$ lebih kecil).
1. **Pondasi Dasar Tembok (40% Bawah)**: Kotak collision footprint ditempatkan secara presisi pada pita dasar pondasi tembok (40% bagian bawah sprite bangunan), di mana kaki karakter berdiri di tanah.
2. **Keterjangkauan Jalur Pulau (Reachability)**: Uji empiris membuktikan bahwa apabila footprint ditarik menutupi seluruh atap bangunan, jalur utara menuju `forest_wood` dan `boss` akan terputus total.
3. **Oklusi Alami via Y-Sorting**: Entitas diperbolehkan secara sah melintas di jalur setapak di belakang rumah (di sebelah utara tembok dasar), di mana tubuh entitas secara natural tertutup oleh atap rumah melalui pengurutan kedalaman rendering Y-sort (`sort_y = entity.py + TILE_SIZE`). Terbukti pada tangkapan layar `roof_occlusion_behind_house.png`.

---

## 3. Bukti Flood-Fill Reachability

Pengujian flood-fill dan A* dari titik awal pemain (Spawn `(1440, 1056)`) membuktikan:
1. **Saat Gerbang Tertutup (`is_open = False`)**:
   - Titik Boss `(2464, 448)`: **TIDAK TERJANGKAU** (`reachable = False`).
   - Tidak ada kebocoran celah di sisi barat maupun timur gerbang.
2. **Saat Gerbang Terbuka (`is_open = True`)**:
   - Titik Boss `(2464, 448)`: **TERJANGKAU** (`reachable = True`, durasi $\approx 11.96$ detik via A*).
   - Seluruh 12 lokasi `LOCATIONS` resmi terjangkau 100%:
     - `spawn`: Terjangkau (0 langkah)
     - `shop`: Terjangkau
     - `workshop`: Terjangkau
     - `bed`: Terjangkau
     - `farm`: Terjangkau
     - `gate`: Terjangkau
     - `chicken_coop`: Terjangkau
     - `cow_pasture`: Terjangkau
     - `river_fishing`: Terjangkau
     - `forest_wood`: Terjangkau
     - `quarry_rock`: Terjangkau
     - `boss`: Terjangkau

---

## 4. Tautan Tangkapan Layar
- Gerbang Tertutup Close-Up (Hero di depan gerbang, F1 Mati): [gate_closeup_closed.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/gate_closeup_closed.png)
- Gerbang Terbuka Close-Up (Hero di depan gerbang, F1 Mati): [gate_closeup_open.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/gate_closeup_open.png)
- Area Pantai & Gerbang Tertutup (Normal, F1 Mati, Kamera Pas): [beach_gate_closed_normal.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/beach_gate_closed_normal.png)
- Area Pantai & Gerbang Terbuka (Normal, F1 Mati, Kamera Pas): [beach_gate_open_normal.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/beach_gate_open_normal.png)
- Overlay F1 Debug Koridor Gerbang: [beach_gate_f1_debug.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/beach_gate_f1_debug.png)
- Eksplorasi Bersih (Tanpa Log Pembuka): [clean_exploration_5s.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/clean_exploration_5s.png)
- Oklusi Atap 2.5D di Belakang Rumah: [roof_occlusion_behind_house.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/roof_occlusion_behind_house.png)
- Tabrakan Dinding Sapi Side-by-Side: [cow_wall_collision_side_by_side.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/cow_wall_collision_side_by_side.png)
- Tabrakan Dinding Domba Side-by-Side: [sheep_wall_collision_side_by_side.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/sheep_wall_collision_side_by_side.png)
- Tabrakan Dinding Pak Tani Side-by-Side: [npc_wall_collision_side_by_side.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/npc_wall_collision_side_by_side.png)
- Tabrakan Dinding Kang Penggiling Side-by-Side: [miller_wall_collision_side_by_side.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/miller_wall_collision_side_by_side.png)
- Panel Live HTN (F8): [htn_f8_panel_live.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/screenshots/htn_f8_panel_live.png)
- Contact Sheet 22 Footprint Bangunan: [contact_sheet_footprints.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/figures/footprints/contact_sheet_footprints.png)
- Kolase Potongan Tile Gerbang 4x: [gate_tiles_used_4x.png](file:///mnt/kuliah/smt3/AI/Game%20AI/docs/figures/tile_debug/gate_tiles_used_4x.png)
