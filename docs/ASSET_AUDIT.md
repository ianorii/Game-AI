# AUDIT PEMAKAIAN ASET SUNNYSIDE WORLD
**Tanggal Audit**: 2026-11-06 22:16:47
**Direktori Aset**: `assets/sunnyside_world/` (Filter: Mengabaikan `Sunnyside_World_Gamemaker`, `GIF`, `_Source`)

## 1. RINGKASAN EKSEKUTIF
- **Total File Aset (.png)**: **398** file
- **Aset Digunakan Eksplisit di Gameplay/Renderer**: **40** file (10.1%)
- **Aset Dimuat Generik ke Dictionary / Template**: **113** file (28.4%)
- **Aset Menganggur (Belum Dipakai Sama Sekali)**: **245** file (61.6%)

> [!NOTE]
> Sebagian besar aset (khususnya variasi aksi manusia, seluruh tanaman 6 tahap, hewan, prop kincir angin, dan perahu) sudah tersedia dengan format strip berkualitas tinggi, namun belum diintegrasikan ke gameplay loop dungeon/overworld.

## 2. TABEL STATISTIK PER FOLDER
| Folder | Total File | Eksplisit | Generic / Dimuat | Belum Dipakai (Unused) | % Tidak Terpakai |
|---|:---:|:---:|:---:|:---:|:---:|
| `Characters/Goblin/PNG` | 20 | 6 | 0 | 14 | 70.0% |
| `Characters/Human/ATTACK` | 8 | 2 | 0 | 6 | 75.0% |
| `Characters/Human/AXE` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/CARRY` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/CASTING` | 8 | 1 | 0 | 7 | 87.5% |
| `Characters/Human/CAUGHT` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/DEATH` | 8 | 1 | 0 | 7 | 87.5% |
| `Characters/Human/DIG` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/DOING` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/HAMMERING` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/HURT` | 8 | 1 | 0 | 7 | 87.5% |
| `Characters/Human/IDLE` | 8 | 1 | 0 | 7 | 87.5% |
| `Characters/Human/JUMP` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/MINING` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/REELING` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/ROLL` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/RUN` | 8 | 1 | 0 | 7 | 87.5% |
| `Characters/Human/SWIMMING` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Human/WAITING` | 8 | 1 | 0 | 7 | 87.5% |
| `Characters/Human/WALKING` | 8 | 1 | 0 | 7 | 87.5% |
| `Characters/Human/WATERING` | 8 | 0 | 0 | 8 | 100.0% |
| `Characters/Skeleton/PNG` | 6 | 5 | 0 | 1 | 16.7% |
| `Elements/Animals` | 7 | 0 | 7 | 0 | 0.0% |
| `Elements/Crops` | 78 | 2 | 0 | 76 | 97.4% |
| `Elements/Other` | 5 | 0 | 4 | 1 | 20.0% |
| `Elements/Plants` | 6 | 0 | 6 | 0 | 0.0% |
| `Elements/VFX/Chimney Smoke` | 5 | 0 | 5 | 0 | 0.0% |
| `Elements/VFX/Fire` | 2 | 1 | 1 | 0 | 0.0% |
| `Elements/VFX/Glint` | 2 | 2 | 0 | 0 | 0.0% |
| `Root` | 1 | 0 | 0 | 1 | 100.0% |
| `Tileset` | 4 | 3 | 0 | 1 | 25.0% |
| `UI` | 75 | 12 | 63 | 0 | 0.0% |
| `UI/9slice_box_white` | 27 | 0 | 27 | 0 | 0.0% |

## 3. AUDIT MENDALAM TARGET KHUSUS

### A. Characters / Human (160 File)
Setiap folder aksi memiliki 8 file: `base_*`, 6 varian rambut (`bowlhair`, `curlyhair`, `longhair`, `mophair`, `shorthair`, `spikeyhair`), dan `tools_*`.

| Aksi | Folder | Status Base | Rambut Terpakai | Status Tools | Status Keseluruhan |
|---|---|:---:|:---:|:---:|---|
| **ATTACK** (Serangan jarak dekat) | `Characters/Human/ATTACK` | ✅ Digunakan | spikeyhair | ✅ Digunakan | Aktif (Battle & Dunia) |
| **AXE** (Menebang pohon / kapak kayu) | `Characters/Human/AXE` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **CARRY** (Membawa peti / hasil panen) | `Characters/Human/CARRY` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **CASTING** (Merapal mantra sihir) | `Characters/Human/CASTING` | ✅ Digunakan | spikeyhair | ❌ Belum | Aktif (Battle & Dunia) |
| **CAUGHT** (Tertangkap / ekspresi kaget) | `Characters/Human/CAUGHT` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **DEATH** (Animasi roboh / gugur (13 frame)) | `Characters/Human/DEATH` | ✅ Digunakan | spikeyhair | ❌ Belum | Aktif (Battle & Dunia) |
| **DIG** (Mencangkul tanah dengan sekop) | `Characters/Human/DIG` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **DOING** (Interaksi generik / berkarya) | `Characters/Human/DOING` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **HAMMERING** (Menempa / memukul palu (23 frame)) | `Characters/Human/HAMMERING` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **HURT** (Terkena pukulan / hitstun) | `Characters/Human/HURT` | ✅ Digunakan | spikeyhair | ❌ Belum | Aktif (Battle & Dunia) |
| **IDLE** (Diam / napas idle (9 frame)) | `Characters/Human/IDLE` | ✅ Digunakan | spikeyhair | ❌ Belum | Aktif (Battle & Dunia) |
| **JUMP** (Melompat rintangan / jurang) | `Characters/Human/JUMP` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **MINING** (Menambang batu / ore pickaxe) | `Characters/Human/MINING` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **REELING** (Memancing ikan / menarik kail) | `Characters/Human/REELING` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **ROLL** (Gulingan menghindar (dodge roll)) | `Characters/Human/ROLL` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **RUN** (Berlari kencang (8 frame)) | `Characters/Human/RUN` | ✅ Digunakan | spikeyhair | ❌ Belum | Aktif (Battle & Dunia) |
| **SWIMMING** (Berenang di air / danau) | `Characters/Human/SWIMMING` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |
| **WAITING** (Menunggu giliran / santai) | `Characters/Human/WAITING` | ✅ Digunakan | spikeyhair | ❌ Belum | Aktif (Battle & Dunia) |
| **WALKING** (Berjalan standar (8 frame)) | `Characters/Human/WALKING` | ✅ Digunakan | spikeyhair | ❌ Belum | Aktif (Battle & Dunia) |
| **WATERING** (Menyiram tanaman dengan ember) | `Characters/Human/WATERING` | ❌ Belum | - | ❌ Belum | Menganggur (Tersedia) |

> **Gaya Rambut Tersedia**: `bowlhair`, `curlyhair`, `longhair`, `mophair`, `shorthair`, `spikeyhair`. Saat ini konfigurasi aktif adalah `spikeyhair` (merah). 5 gaya rambut lainnya (100+ file) siap digunakan untuk kustomisasi hero atau NPC desa.

### B. Characters / Skeleton & Goblin
#### 1. Skeleton (6 File)
| File | Strip | Status | Catatan Pemakaian |
|---|:---:|:---:|---|
| `skeleton_idle_strip6.png` | 6 | ✅ Aktif | Digunakan untuk Boss Idle (skala 7x) |
| `skeleton_attack_strip7.png` | 7 | ✅ Aktif | Digunakan untuk Boss Attack animasi |
| `skeleton_hurt_strip7.png` | 7 | ✅ Aktif | Digunakan untuk Boss Hurt animasi |
| `skeleton_death_strip10.png` | 10 | ✅ Aktif | Digunakan untuk Boss Death & sisa tengkorak |
| `skeleton_walk_strip8.png` | 8 | ⚠️ Dimuat parsial | Dimuat di asset_loader tetapi Boss statis, belum berpatroli |
| `skeleton_jump_strip10.png` | 10 | ❌ Belum | Animasi lompat/slam attack belum diimplementasikan |

#### 2. Goblin (20 File)
Folder `Characters/Goblin/PNG/` memiliki seluruh set aksi (20 animasi lengkap strip) identik dengan hero human.
- **Animasi tersedia**: `attack`, `axe`, `carry`, `casting`, `caught`, `death`, `dig`, `doing`, `hammering`, `hurt`, `idle`, `jump`, `mining`, `reeling`, `roll`, `run`, `swimming`, `waiting`, `walk`, `watering`.
- **Status saat ini**: `spr_idle_strip9`, `spr_run_strip8`, `spr_walk_strip8`, `spr_attack_strip10`, `spr_hurt_strip8`, `spr_death_strip13` sudah dibaca oleh `AssetManager`, namun monster Goblin belum aktif spawn di dunia game sebagai entitas hidup yang dapat berinteraksi.

### C. Elements / Crops (78 File)
Total 11 varian tanaman agrikultur, masing-masing dengan 6 tahap pertumbuhan (`_00` benih hingga `_05` panen matang):
- **Daftar Tanaman (66 File)**: `beetroot`, `cabbage`, `carrot`, `cauliflower`, `kale`, `parsnip`, `potato`, `pumpkin`, `radish`, `sunflower`, `wheat`.
- **Daftar Tanah & Barang (12 File)**:
  - Tanah: `soil_00.png` (kering datar), `soil_01.png` (lembab), `soil_03.png` (sudut), `soil_04.png` (gundukan)
  - Hasil Tani & Material: `seeds_generic.png`, `wood.png`, `rock.png`, `crate_base.png`, `crate_top.png`
  - Makanan/Produk: `egg.png`, `milk.png`, `fish.png`
- **Status Pemakaian**: ❌ **100% Menganggur** (hanya `rock.png` yang dirujuk di kode map). Belum ada sistem ladang bercocok tanam atau pengumpulan bahan.

### D. Elements / VFX (9 File)
| File / Subfolder | Strip | Status | Catatan Pemakaian |
|---|:---:|:---:|---|
| `Elements/VFX/Fire/spr_deco_fire_01_strip4.png` | 4 | ✅ Aktif | Animasi api jebakan merah & es biru |
| `Elements/VFX/Fire/spr_deco_fire_02_strip4.png` | 4 | ❌ Belum | Variasi kobaran api kedua belum dipakai |
| `Elements/VFX/Glint/spr_deco_glint_01_strip6.png` | 6 | ✅ Aktif | Hit sparks efek tebasan serangan |
| `Elements/VFX/Glint/spr_deco_glint_02_strip4.png` | 4 | ⚠️ Dimuat | Alternatif kilatan glint |
| `Elements/VFX/Chimney Smoke/chimneysmoke_01_strip30.png` | 30 | ❌ Belum | Animasi asap cerobong 30 frame (varian 1) |
| `Elements/VFX/Chimney Smoke/chimneysmoke_02_strip30.png` | 30 | ❌ Belum | Animasi asap cerobong 30 frame (varian 2) |
| `Elements/VFX/Chimney Smoke/chimneysmoke_03_strip30.png` | 30 | ❌ Belum | Animasi asap cerobong 30 frame (varian 3) |
| `Elements/VFX/Chimney Smoke/chimneysmoke_04_strip30.png` | 30 | ❌ Belum | Animasi asap cerobong 30 frame (varian 4) |
| `Elements/VFX/Chimney Smoke/chimneysmoke_05_strip30.png` | 30 | ❌ Belum | Animasi asap cerobong 30 frame (varian 5) |

### E. Elements / Other (5 File)
| File | Status | Deskripsi & Rekomendasi |
|---|:---:|---|
| `spr_deco_windmill_strip9.png` | ❌ Belum | Kincir angin berputar (9 frame). Sangat cocok untuk pusat desa / peternakan. |
| `spr_deco_windmillshadow_strip9.png` | ❌ Belum | Bayangan kincir angin berputar (9 frame). Memberikan kedalaman visual realistis. |
| `spr_deco_windmill_withshadow_strip9.png` | ❌ Belum | Kincir angin gabungan dengan bayangan dalam satu sprite. |
| `spr_deco_coracle_land.png` | ❌ Belum | Perahu bulat tradisional bertengger di daratan/pesisir. |
| `spr_deco_coracle_strip4.png` | ❌ Belum | Perahu bulat mengapung di air dengan animasi goyangan air 4 frame. |

### F. Antarmuka / UI (102 File)
Folder `UI` (75 file) dan `UI/9slice_box_white` (27 file).
- **Ikon Emosi & Status Terpakai**: `expression_alerted`, `expression_attack`, `expression_confused`, `expression_love`, `expression_chat`, `indicator`.
- **Resource Bars Menganggur**: `bluebar_00` s/d `bluebar_05` (mana/stamina bar), `greenbar_00` s/d `greenbar_06` (health bar hijau), `redbar_00` s/d `redbar_06` (health bar merah). Saat ini HUD menggambar bar via poligon pygame dasar, belum memakai sprite strip otentik ini.
- **Ikon Perkakas / Senjata Menganggur**: `axe.png`, `hammer.png`, `pickaxe.png`, `shovel.png`, `rod.png`, `water.png`, `sword.png`, `basket.png`, `plant.png`.
- **Elemen Kontrol Menganggur**: `confirm.png`, `cancel.png`, `itemdisc_01.png`, `itemdisc_02.png`, `sandtimer.png`, `stopwatch.png`, `playercount.png`, `hand_closed_01/02`, `hand_open_01/02`, `cursor_01` s/d `cursor_05`, `happiness_01` s/d `04`.
- **9-Slice Box Menganggur**: 27 slice kotak dialog/panel putih siap pakai untuk merender jendela dialog modular.

## 4. REKOMENDASI INTEGRASI KE GAMEPLAY & DUNIA
Berikut rekomendasi konkret pemanfaatan aset tanpa mengganggu mekanisme kecerdasan buatan (Minimax, CSP, Local Search, A*):

1. **Kincir Angin Desa (`spr_deco_windmill_strip9.png`)**:
   - Letakkan 1 bangunan kincir angin di area desa/tengah peta.
   - Menggunakan animasi 9-frame looping lambat (8-10 FPS) dengan y-sort dan bayangan.
2. **Efek Asap Cerobong (`chimneysmoke_01..05_strip30.png`)**:
   - Pasang emitter asap di atas atap rumah-rumah desa Sunnyside.
   - Siklus 30 frame halus dengan alpha blending menghidupkan suasana pedesaan.
3. **Ladang Pertanian Interaktif (`soil_00..04` + `crops` 6 tahap)**:
   - Tambahkan petak ladang di desa dengan tanaman bertumbuh (mis. Gandum / Labu / Wortel).
   - Hero dapat berinteraksi menekan [E] untuk memanen bahan consumable/potion.
4. **Ikon UI Asli pada HUD & Prep Screen**:
   - Ganti bar HP kotak polos dengan sprite `greenbar_00-06` dan `redbar_00-06`.
   - Gunakan ikon alat otentik (`sword.png`, `axe.png`, `water.png`, `sandtimer.png`) pada layar Persiapan CSP / Prep UI.
5. **Patroli Goblin & Skeleton Mengembara**:
   - Spawn minion Goblin dan Skeleton liar di luar zona aman desa yang berpatroli (A*).
   - Menggunakan animasi `walk` dan `jump` yang belum terpakai.
6. **Perahu Pesisir (`spr_deco_coracle_strip4.png`)**:
   - Tempatkan perahu mengapung di dermaga atau tepian danau pulau dengan animasi 4 frame.

## 5. DAFTAR LENGKAP ASET BELUM DIPAKAI (UNUSED)
Total: **245** file yang siap dimuat oleh `src/asset_catalog.py`:

| No | Path Relatif | Ukuran Frame Strip | Ukuran File |
|:---:|---|:---:|:---:|
| 1 | `Characters/Goblin/PNG/spr_axe_strip10.png` | 10 frame | 5,256 byte |
| 2 | `Characters/Goblin/PNG/spr_carry_strip8.png` | 8 frame | 3,002 byte |
| 3 | `Characters/Goblin/PNG/spr_casting_strip15.png` | 15 frame | 7,260 byte |
| 4 | `Characters/Goblin/PNG/spr_caught_strip10.png` | 10 frame | 4,825 byte |
| 5 | `Characters/Goblin/PNG/spr_dig_strip13.png` | 13 frame | 5,955 byte |
| 6 | `Characters/Goblin/PNG/spr_doing_strip8.png` | 8 frame | 2,283 byte |
| 7 | `Characters/Goblin/PNG/spr_hammering_strip23.png` | 23 frame | 10,790 byte |
| 8 | `Characters/Goblin/PNG/spr_jump_strip9.png` | 9 frame | 2,502 byte |
| 9 | `Characters/Goblin/PNG/spr_mining_strip10.png` | 10 frame | 5,842 byte |
| 10 | `Characters/Goblin/PNG/spr_reeling_strip13.png` | 13 frame | 5,817 byte |
| 11 | `Characters/Goblin/PNG/spr_roll_strip10.png` | 10 frame | 2,917 byte |
| 12 | `Characters/Goblin/PNG/spr_swimming_strip12.png` | 12 frame | 1,163 byte |
| 13 | `Characters/Goblin/PNG/spr_waiting_strip9.png` | 9 frame | 2,629 byte |
| 14 | `Characters/Goblin/PNG/spr_watering_strip5.png` | 5 frame | 1,602 byte |
| 15 | `Characters/Human/ATTACK/bowlhair_attack_strip10.png` | 10 frame | 1,416 byte |
| 16 | `Characters/Human/ATTACK/curlyhair_attack_strip10.png` | 10 frame | 1,594 byte |
| 17 | `Characters/Human/ATTACK/longhair_attack_strip10.png` | 10 frame | 1,679 byte |
| 18 | `Characters/Human/ATTACK/mophair_attack_strip10.png` | 10 frame | 1,313 byte |
| 19 | `Characters/Human/ATTACK/shorthair_attack_strip10.png` | 10 frame | 672 byte |
| 20 | `Characters/Human/ATTACK/spikeyhair_attack_strip10.png` | 10 frame | 1,195 byte |
| 21 | `Characters/Human/AXE/base_axe_strip10.png` | 10 frame | 2,356 byte |
| 22 | `Characters/Human/AXE/bowlhair_axe_strip10.png` | 10 frame | 1,200 byte |
| 23 | `Characters/Human/AXE/curlyhair_axe_strip10.png` | 10 frame | 1,659 byte |
| 24 | `Characters/Human/AXE/longhair_axe_strip10.png` | 10 frame | 1,649 byte |
| 25 | `Characters/Human/AXE/mophair_axe_strip10.png` | 10 frame | 1,299 byte |
| 26 | `Characters/Human/AXE/shorthair_axe_strip10.png` | 10 frame | 667 byte |
| 27 | `Characters/Human/AXE/spikeyhair_axe_strip10.png` | 10 frame | 1,110 byte |
| 28 | `Characters/Human/AXE/tools_axe_strip10.png` | 10 frame | 2,935 byte |
| 29 | `Characters/Human/CARRY/base_carry_strip8.png` | 8 frame | 1,490 byte |
| 30 | `Characters/Human/CARRY/bowlhair_carry_strip8.png` | 8 frame | 1,211 byte |
| 31 | `Characters/Human/CARRY/curlyhair_carry_strip8.png` | 8 frame | 1,372 byte |
| 32 | `Characters/Human/CARRY/longhair_carry_strip8.png` | 8 frame | 1,319 byte |
| 33 | `Characters/Human/CARRY/mophair_carry_strip8.png` | 8 frame | 1,033 byte |
| 34 | `Characters/Human/CARRY/shorthair_carry_strip8.png` | 8 frame | 607 byte |
| 35 | `Characters/Human/CARRY/spikeyhair_carry_strip8.png` | 8 frame | 825 byte |
| 36 | `Characters/Human/CARRY/tools_carry_strip8.png` | 8 frame | 2,181 byte |
| 37 | `Characters/Human/CASTING/bowlhair_casting_strip15.png` | 15 frame | 1,650 byte |
| 38 | `Characters/Human/CASTING/curlyhair_casting_strip15.png` | 15 frame | 1,899 byte |
| 39 | `Characters/Human/CASTING/longhair_casting_strip15.png` | 15 frame | 2,178 byte |
| 40 | `Characters/Human/CASTING/mophair_casting_strip15.png` | 15 frame | 1,555 byte |
| 41 | `Characters/Human/CASTING/shorthair_casting_strip15.png` | 15 frame | 860 byte |
| 42 | `Characters/Human/CASTING/spikeyhair_casting_strip15.png` | 15 frame | 1,291 byte |
| 43 | `Characters/Human/CASTING/tools_casting_strip15.png` | 15 frame | 4,952 byte |
| 44 | `Characters/Human/CAUGHT/base_caught_strip10.png` | 10 frame | 1,443 byte |
| 45 | `Characters/Human/CAUGHT/bowlhair_caught_strip10.png` | 10 frame | 1,370 byte |
| 46 | `Characters/Human/CAUGHT/curlyhair_caught_strip10.png` | 10 frame | 1,149 byte |
| 47 | `Characters/Human/CAUGHT/longhair_caught_strip10.png` | 10 frame | 1,485 byte |
| 48 | `Characters/Human/CAUGHT/mophair_caught_strip10.png` | 10 frame | 1,203 byte |
| 49 | `Characters/Human/CAUGHT/shorthair_caught_strip10.png` | 10 frame | 665 byte |
| 50 | `Characters/Human/CAUGHT/spikeyhair_caught_strip10.png` | 10 frame | 1,066 byte |
| 51 | `Characters/Human/CAUGHT/tools_caught_strip10.png` | 10 frame | 3,438 byte |
| 52 | `Characters/Human/DEATH/bowlhair_death_strip13.png` | 13 frame | 915 byte |
| 53 | `Characters/Human/DEATH/curlyhair_death_strip13.png` | 13 frame | 846 byte |
| 54 | `Characters/Human/DEATH/longhair_death_strip13.png` | 13 frame | 966 byte |
| 55 | `Characters/Human/DEATH/mophair_death_strip13.png` | 13 frame | 782 byte |
| 56 | `Characters/Human/DEATH/shorthair_death_strip13.png` | 13 frame | 543 byte |
| 57 | `Characters/Human/DEATH/spikeyhair_death_strip13.png` | 13 frame | 671 byte |
| 58 | `Characters/Human/DEATH/tools_death_strip13.png` | 13 frame | 505 byte |
| 59 | `Characters/Human/DIG/base_dig_strip13.png` | 13 frame | 2,041 byte |
| 60 | `Characters/Human/DIG/bowlhair_dig_strip13.png` | 13 frame | 1,666 byte |
| 61 | `Characters/Human/DIG/curlyhair_dig_strip13.png` | 13 frame | 1,699 byte |
| 62 | `Characters/Human/DIG/longhair_dig_strip13.png` | 13 frame | 2,001 byte |
| 63 | `Characters/Human/DIG/mophair_dig_strip13.png` | 13 frame | 1,525 byte |
| 64 | `Characters/Human/DIG/shorthair_dig_strip13.png` | 13 frame | 830 byte |
| 65 | `Characters/Human/DIG/spikeyhair_dig_strip13.png` | 13 frame | 1,357 byte |
| 66 | `Characters/Human/DIG/tools_dig_strip13.png` | 13 frame | 2,704 byte |
| 67 | `Characters/Human/DOING/base_doing_strip8.png` | 8 frame | 1,263 byte |
| 68 | `Characters/Human/DOING/bowlhair_doing_strip8.png` | 8 frame | 1,149 byte |
| 69 | `Characters/Human/DOING/curlyhair_doing_strip8.png` | 8 frame | 1,259 byte |
| 70 | `Characters/Human/DOING/longhair_doing_strip8.png` | 8 frame | 1,365 byte |
| 71 | `Characters/Human/DOING/mophair_doing_strip8.png` | 8 frame | 1,139 byte |
| 72 | `Characters/Human/DOING/shorthair_doing_strip8.png` | 8 frame | 573 byte |
| 73 | `Characters/Human/DOING/spikeyhair_doing_strip8.png` | 8 frame | 936 byte |
| 74 | `Characters/Human/DOING/tools_doing_strip8.png` | 8 frame | 1,090 byte |
| 75 | `Characters/Human/HAMMERING/base_hamering_strip23.png` | 23 frame | 3,814 byte |
| 76 | `Characters/Human/HAMMERING/bowlhair_hamering_strip23.png` | 23 frame | 1,811 byte |
| 77 | `Characters/Human/HAMMERING/curlyhair_hamering_strip23.png` | 23 frame | 2,224 byte |
| 78 | `Characters/Human/HAMMERING/longhair_hamering_strip23.png` | 23 frame | 2,331 byte |
| 79 | `Characters/Human/HAMMERING/mophair_hamering_strip23.png` | 23 frame | 1,836 byte |
| 80 | `Characters/Human/HAMMERING/shorthair_hamering_strip23.png` | 23 frame | 1,171 byte |
| 81 | `Characters/Human/HAMMERING/spikeyhair_hamering_strip23.png` | 23 frame | 1,745 byte |
| 82 | `Characters/Human/HAMMERING/tools_hamering_strip23.png` | 23 frame | 5,263 byte |
| 83 | `Characters/Human/HURT/bowlhair_hurt_strip8.png` | 8 frame | 1,196 byte |
| 84 | `Characters/Human/HURT/curlyhair_hurt_strip8.png` | 8 frame | 1,288 byte |
| 85 | `Characters/Human/HURT/longhair_hurt_strip8.png` | 8 frame | 1,471 byte |
| 86 | `Characters/Human/HURT/mophair_hurt_strip8.png` | 8 frame | 1,067 byte |
| 87 | `Characters/Human/HURT/shorthair_hurt_strip8.png` | 8 frame | 578 byte |
| 88 | `Characters/Human/HURT/spikeyhair_hurt_strip8.png` | 8 frame | 930 byte |
| 89 | `Characters/Human/HURT/tools_hurt_strip8.png` | 8 frame | 937 byte |
| 90 | `Characters/Human/IDLE/bowlhair_idle_strip9.png` | 9 frame | 1,244 byte |
| 91 | `Characters/Human/IDLE/curlyhair_idle_strip9.png` | 9 frame | 1,306 byte |
| 92 | `Characters/Human/IDLE/longhair_idle_strip9.png` | 9 frame | 1,417 byte |
| 93 | `Characters/Human/IDLE/mophair_idle_strip9.png` | 9 frame | 1,139 byte |
| 94 | `Characters/Human/IDLE/shorthair_idle_strip9.png` | 9 frame | 613 byte |
| 95 | `Characters/Human/IDLE/spikeyhair_idle_strip9.png` | 9 frame | 980 byte |
| 96 | `Characters/Human/IDLE/tools_idle_strip9.png` | 9 frame | 544 byte |
| 97 | `Characters/Human/JUMP/base_jump_strip9.png` | 9 frame | 1,554 byte |
| 98 | `Characters/Human/JUMP/bowlhair_jump_strip9.png` | 9 frame | 1,433 byte |
| 99 | `Characters/Human/JUMP/curlyhair_jump_strip9.png` | 9 frame | 1,807 byte |
| 100 | `Characters/Human/JUMP/longhair_jump_strip9.png` | 9 frame | 2,398 byte |
| 101 | `Characters/Human/JUMP/mophair_jump_strip9.png` | 9 frame | 1,397 byte |
| 102 | `Characters/Human/JUMP/shorthair_jump_strip9.png` | 9 frame | 677 byte |
| 103 | `Characters/Human/JUMP/spikeyhair_jump_strip9.png` | 9 frame | 1,229 byte |
| 104 | `Characters/Human/JUMP/tools_jump_strip9.png` | 9 frame | 771 byte |
| 105 | `Characters/Human/MINING/base_mining_strip10.png` | 10 frame | 2,355 byte |
| 106 | `Characters/Human/MINING/bowlhair_mining_strip10.png` | 10 frame | 1,200 byte |
| 107 | `Characters/Human/MINING/curlyhair_mining_strip10.png` | 10 frame | 1,659 byte |
| 108 | `Characters/Human/MINING/longhair_mining_strip10.png` | 10 frame | 1,649 byte |
| 109 | `Characters/Human/MINING/mophair_mining_strip10.png` | 10 frame | 1,299 byte |
| 110 | `Characters/Human/MINING/shorthair_mining_strip10.png` | 10 frame | 667 byte |
| 111 | `Characters/Human/MINING/spikeyhair_mining_strip10.png` | 10 frame | 1,116 byte |
| 112 | `Characters/Human/MINING/tools_mining_strip10.png` | 10 frame | 3,468 byte |
| 113 | `Characters/Human/REELING/base_reeling_strip13.png` | 13 frame | 1,718 byte |
| 114 | `Characters/Human/REELING/bowlhair_reeling_strip13.png` | 13 frame | 1,540 byte |
| 115 | `Characters/Human/REELING/curlyhair_reeling_strip13.png` | 13 frame | 1,720 byte |
| 116 | `Characters/Human/REELING/longhair_reeling_strip13.png` | 13 frame | 1,922 byte |
| 117 | `Characters/Human/REELING/mophair_reeling_strip13.png` | 13 frame | 1,328 byte |
| 118 | `Characters/Human/REELING/shorthair_reeling_strip13.png` | 13 frame | 774 byte |
| 119 | `Characters/Human/REELING/spikeyhair_reeling_strip13.png` | 13 frame | 1,173 byte |
| 120 | `Characters/Human/REELING/tools_reeling_strip13.png` | 13 frame | 3,560 byte |
| 121 | `Characters/Human/ROLL/base_roll_strip10.png` | 10 frame | 2,497 byte |
| 122 | `Characters/Human/ROLL/bowlhair_roll_strip10.png` | 10 frame | 2,455 byte |
| 123 | `Characters/Human/ROLL/curlyhair_roll_strip10.png` | 10 frame | 2,593 byte |
| 124 | `Characters/Human/ROLL/longhair_roll_strip10.png` | 10 frame | 3,088 byte |
| 125 | `Characters/Human/ROLL/mophair_roll_strip10.png` | 10 frame | 2,338 byte |
| 126 | `Characters/Human/ROLL/shorthair_roll_strip10.png` | 10 frame | 1,713 byte |
| 127 | `Characters/Human/ROLL/spikeyhair_roll_strip10.png` | 10 frame | 2,034 byte |
| 128 | `Characters/Human/ROLL/tools_roll_strip10.png` | 10 frame | 884 byte |
| 129 | `Characters/Human/RUN/bowlhair_run_strip8.png` | 8 frame | 1,386 byte |
| 130 | `Characters/Human/RUN/curlyhair_run_strip8.png` | 8 frame | 1,436 byte |
| 131 | `Characters/Human/RUN/longhair_run_strip8.png` | 8 frame | 1,508 byte |
| 132 | `Characters/Human/RUN/mophair_run_strip8.png` | 8 frame | 1,234 byte |
| 133 | `Characters/Human/RUN/shorthair_run_strip8.png` | 8 frame | 618 byte |
| 134 | `Characters/Human/RUN/spikeyhair_run_strip8.png` | 8 frame | 999 byte |
| 135 | `Characters/Human/RUN/tools_run_strip8.png` | 8 frame | 633 byte |
| 136 | `Characters/Human/SWIMMING/base_swimming_strip12.png` | 12 frame | 1,017 byte |
| 137 | `Characters/Human/SWIMMING/bowlhair_swimming_strip12.png` | 12 frame | 1,303 byte |
| 138 | `Characters/Human/SWIMMING/curlyhair_swimming_strip12.png` | 12 frame | 1,289 byte |
| 139 | `Characters/Human/SWIMMING/longhair_swimming_strip12.png` | 12 frame | 1,610 byte |
| 140 | `Characters/Human/SWIMMING/mophair_swimming_strip12.png` | 12 frame | 1,275 byte |
| 141 | `Characters/Human/SWIMMING/shorthair_swimming_strip12.png` | 12 frame | 775 byte |
| 142 | `Characters/Human/SWIMMING/spikeyhair_swimming_strip12.png` | 12 frame | 1,092 byte |
| 143 | `Characters/Human/SWIMMING/tools_swimming_strip12.png` | 12 frame | 475 byte |
| 144 | `Characters/Human/WAITING/bowlhair_waiting_strip9.png` | 9 frame | 1,243 byte |
| 145 | `Characters/Human/WAITING/curlyhair_waiting_strip9.png` | 9 frame | 1,043 byte |
| 146 | `Characters/Human/WAITING/longhair_waiting_strip9.png` | 9 frame | 1,406 byte |
| 147 | `Characters/Human/WAITING/mophair_waiting_strip9.png` | 9 frame | 970 byte |
| 148 | `Characters/Human/WAITING/shorthair_waiting_strip9.png` | 9 frame | 618 byte |
| 149 | `Characters/Human/WAITING/spikeyhair_waiting_strip9.png` | 9 frame | 869 byte |
| 150 | `Characters/Human/WAITING/tools_waiting_strip9.png` | 9 frame | 1,655 byte |
| 151 | `Characters/Human/WALKING/bowlhair_walk_strip8.png` | 8 frame | 1,211 byte |
| 152 | `Characters/Human/WALKING/curlyhair_walk_strip8.png` | 8 frame | 1,372 byte |
| 153 | `Characters/Human/WALKING/longhair_walk_strip8.png` | 8 frame | 1,319 byte |
| 154 | `Characters/Human/WALKING/mophair_walk_strip8.png` | 8 frame | 1,033 byte |
| 155 | `Characters/Human/WALKING/shorthair_walk_strip8.png` | 8 frame | 607 byte |
| 156 | `Characters/Human/WALKING/spikeyhair_walk_strip8.png` | 8 frame | 918 byte |
| 157 | `Characters/Human/WALKING/tools_walk_strip8.png` | 8 frame | 536 byte |
| 158 | `Characters/Human/WATERING/base_watering_strip5.png` | 5 frame | 701 byte |
| 159 | `Characters/Human/WATERING/bowlhair_watering_strip5.png` | 5 frame | 803 byte |
| 160 | `Characters/Human/WATERING/curlyhair_watering_strip5.png` | 5 frame | 730 byte |
| 161 | `Characters/Human/WATERING/longhair_watering_strip5.png` | 5 frame | 851 byte |
| 162 | `Characters/Human/WATERING/mophair_watering_strip5.png` | 5 frame | 671 byte |
| 163 | `Characters/Human/WATERING/shorthair_watering_strip5.png` | 5 frame | 400 byte |
| 164 | `Characters/Human/WATERING/spikeyhair_watering_strip5.png` | 5 frame | 547 byte |
| 165 | `Characters/Human/WATERING/tools_watering_strip5.png` | 5 frame | 1,006 byte |
| 166 | `Characters/Skeleton/PNG/skeleton_jump_strip10.png` | 10 frame | 1,813 byte |
| 167 | `Elements/Crops/beetroot_00.png` | 1 frame | 123 byte |
| 168 | `Elements/Crops/beetroot_01.png` | 1 frame | 149 byte |
| 169 | `Elements/Crops/beetroot_02.png` | 1 frame | 197 byte |
| 170 | `Elements/Crops/beetroot_03.png` | 1 frame | 268 byte |
| 171 | `Elements/Crops/beetroot_04.png` | 1 frame | 360 byte |
| 172 | `Elements/Crops/beetroot_05.png` | 1 frame | 318 byte |
| 173 | `Elements/Crops/cabbage_00.png` | 1 frame | 131 byte |
| 174 | `Elements/Crops/cabbage_01.png` | 1 frame | 211 byte |
| 175 | `Elements/Crops/cabbage_02.png` | 1 frame | 209 byte |
| 176 | `Elements/Crops/cabbage_03.png` | 1 frame | 303 byte |
| 177 | `Elements/Crops/cabbage_04.png` | 1 frame | 390 byte |
| 178 | `Elements/Crops/cabbage_05.png` | 1 frame | 253 byte |
| 179 | `Elements/Crops/carrot_00.png` | 1 frame | 171 byte |
| 180 | `Elements/Crops/carrot_01.png` | 1 frame | 166 byte |
| 181 | `Elements/Crops/carrot_02.png` | 1 frame | 187 byte |
| 182 | `Elements/Crops/carrot_03.png` | 1 frame | 259 byte |
| 183 | `Elements/Crops/carrot_04.png` | 1 frame | 310 byte |
| 184 | `Elements/Crops/carrot_05.png` | 1 frame | 248 byte |
| 185 | `Elements/Crops/cauliflower_00.png` | 1 frame | 120 byte |
| 186 | `Elements/Crops/cauliflower_01.png` | 1 frame | 151 byte |
| 187 | `Elements/Crops/cauliflower_02.png` | 1 frame | 199 byte |
| 188 | `Elements/Crops/cauliflower_03.png` | 1 frame | 244 byte |
| 189 | `Elements/Crops/cauliflower_04.png` | 1 frame | 263 byte |
| 190 | `Elements/Crops/cauliflower_05.png` | 1 frame | 249 byte |
| 191 | `Elements/Crops/crate_base.png` | 1 frame | 234 byte |
| 192 | `Elements/Crops/crate_top.png` | 1 frame | 242 byte |
| 193 | `Elements/Crops/egg.png` | 1 frame | 229 byte |
| 194 | `Elements/Crops/fish.png` | 1 frame | 256 byte |
| 195 | `Elements/Crops/kale_00.png` | 1 frame | 119 byte |
| 196 | `Elements/Crops/kale_01.png` | 1 frame | 141 byte |
| 197 | `Elements/Crops/kale_02.png` | 1 frame | 163 byte |
| 198 | `Elements/Crops/kale_03.png` | 1 frame | 196 byte |
| 199 | `Elements/Crops/kale_04.png` | 1 frame | 217 byte |
| 200 | `Elements/Crops/kale_05.png` | 1 frame | 239 byte |
| 201 | `Elements/Crops/milk.png` | 1 frame | 206 byte |
| 202 | `Elements/Crops/parsnip_00.png` | 1 frame | 142 byte |
| 203 | `Elements/Crops/parsnip_01.png` | 1 frame | 140 byte |
| 204 | `Elements/Crops/parsnip_02.png` | 1 frame | 182 byte |
| 205 | `Elements/Crops/parsnip_03.png` | 1 frame | 225 byte |
| 206 | `Elements/Crops/parsnip_04.png` | 1 frame | 300 byte |
| 207 | `Elements/Crops/parsnip_05.png` | 1 frame | 328 byte |
| 208 | `Elements/Crops/potato_00.png` | 1 frame | 148 byte |
| 209 | `Elements/Crops/potato_01.png` | 1 frame | 166 byte |
| 210 | `Elements/Crops/potato_02.png` | 1 frame | 198 byte |
| 211 | `Elements/Crops/potato_03.png` | 1 frame | 245 byte |
| 212 | `Elements/Crops/potato_04.png` | 1 frame | 309 byte |
| 213 | `Elements/Crops/potato_05.png` | 1 frame | 204 byte |
| 214 | `Elements/Crops/pumpkin_00.png` | 1 frame | 170 byte |
| 215 | `Elements/Crops/pumpkin_01.png` | 1 frame | 189 byte |
| 216 | `Elements/Crops/pumpkin_02.png` | 1 frame | 263 byte |
| 217 | `Elements/Crops/pumpkin_03.png` | 1 frame | 357 byte |
| 218 | `Elements/Crops/pumpkin_04.png` | 1 frame | 328 byte |
| 219 | `Elements/Crops/pumpkin_05.png` | 1 frame | 310 byte |
| 220 | `Elements/Crops/radish_00.png` | 1 frame | 153 byte |
| 221 | `Elements/Crops/radish_01.png` | 1 frame | 141 byte |
| 222 | `Elements/Crops/radish_02.png` | 1 frame | 180 byte |
| 223 | `Elements/Crops/radish_03.png` | 1 frame | 226 byte |
| 224 | `Elements/Crops/radish_04.png` | 1 frame | 313 byte |
| 225 | `Elements/Crops/radish_05.png` | 1 frame | 314 byte |
| 226 | `Elements/Crops/seeds_generic.png` | 1 frame | 231 byte |
| 227 | `Elements/Crops/soil_00.png` | 1 frame | 229 byte |
| 228 | `Elements/Crops/soil_01.png` | 1 frame | 231 byte |
| 229 | `Elements/Crops/soil_03.png` | 1 frame | 267 byte |
| 230 | `Elements/Crops/soil_04.png` | 1 frame | 306 byte |
| 231 | `Elements/Crops/sunflower_00.png` | 1 frame | 165 byte |
| 232 | `Elements/Crops/sunflower_01.png` | 1 frame | 195 byte |
| 233 | `Elements/Crops/sunflower_02.png` | 1 frame | 219 byte |
| 234 | `Elements/Crops/sunflower_03.png` | 1 frame | 284 byte |
| 235 | `Elements/Crops/sunflower_04.png` | 1 frame | 442 byte |
| 236 | `Elements/Crops/sunflower_05.png` | 1 frame | 402 byte |
| 237 | `Elements/Crops/wheat_00.png` | 1 frame | 127 byte |
| 238 | `Elements/Crops/wheat_01.png` | 1 frame | 158 byte |
| 239 | `Elements/Crops/wheat_02.png` | 1 frame | 187 byte |
| 240 | `Elements/Crops/wheat_03.png` | 1 frame | 235 byte |
| 241 | `Elements/Crops/wheat_04.png` | 1 frame | 259 byte |
| 242 | `Elements/Crops/wheat_05.png` | 1 frame | 203 byte |
| 243 | `Elements/Other/spr_deco_coracle_land.png` | 1 frame | 688 byte |
| 244 | `Sunnyside_World_ExampleScene.png` | 1 frame | 1,153,088 byte |
| 245 | `Tileset/spr_tileset_sunnysideworld_forest_32px.png` | 1 frame | 6,847 byte |
