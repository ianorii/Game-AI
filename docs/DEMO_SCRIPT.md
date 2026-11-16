# PANDUAN DAN SKRIP DEMONSTRASI SISTEM AI LABYRINTH
## Simulasi Live dan Presentasi Evaluasi Akademik (Durasi: 5–8 Menit)

---

### 1. Persiapan Sebelum Demonstrasi (Pre-Demo Checklist)

Sebelum memulai demonstrasi di hadapan dosen penguji atau audiens, pastikan langkah-langkah penyiapan berikut telah dipenuhi:

1. **Lingkungan Eksekusi:**
   - Sistem operasi: Linux / macOS / Windows dengan Python 3.10+ (direkomendasikan Python 3.14).
   - Pastikan dependensi rendering aktif: `pygame-ce` versi 2.6.1+.
   - Pastikan direktori kerja aktif berada di root repositori proyek: `cd "/mnt/kuliah/smt3/AI/Game AI"`.
2. **Reset Data dan Konfigurasi Bersih:**
   - Pastikan berkas `data/collision_overrides.json` dalam kondisi bersih (berisi `{}` atau `[]`).
   - Gunakan seed deterministik default `20261021` atau flag `--seed 42` jika ingin memastikan seluruh angka identik dengan laporan.
3. **Persiapan Flag Deterministik Ramalan Cuaca:**
   - Untuk menjamin modul ketidakpastian mendemonstrasikan fenomena pasang surut dan pembaruan keyakinan Bayes secara pasti tanpa bergantung pada probabilitas acak, jalankan game dengan flag:
     ```bash
     python3 src/main.py --demo-weather=berita
     ```
4. **Daftar Berkas Cadangan Visual (*Fallback Artifacts*):**
   Jika terjadi kendala teknis pada display proyektor atau perangkat keras grafis saat presentasi, pemateri dapat langsung membuka berkas bukti visual resolusi tinggi berikut di folder `docs/screenshots/`:
   - `docs/screenshots/weather_board_prompt.png` (Papan cuaca dan interaksi `[E]`).
   - `docs/screenshots/uncertainty_tab_panel_f7.png` (Tab 3 F7 dengan metrik posterior Bayes).
   - `docs/screenshots/autopilot_route_before_news.png` (Rute pintas titik cyan).
   - `docs/screenshots/autopilot_route_after_news.png` (Rute aman titik hijau memutar karang).
   - `docs/screenshots/hero_flood_flush_swimming.png` (Hero dievakuasi berenang ke tile kering).
   - `docs/screenshots/htn_f8_panel_live.png` (Panel HTN rutin harian Pak Tani & Kang Penggiling).
   - `docs/screenshots/gate_closeup_side_by_side.png` (Perbandingan gerbang tertutup vs terbuka).

---

### 2. Tabel Linimasa Demonstrasi (5–8 Menit)

| Menit | Segmen Demonstrasi | Tombol / Perintah CLI | Tampilan Layar | Narasi Presenter (Bahasa Indonesia) | Tindakan Cadangan (*Fallback*) |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **0:00 - 1:00** | **Pengantar & Navigasi Manual ($A^*$)** | `python3 src/main.py` <br> `W`, `A`, `S`, `D`, `Spasi` | Hero bergerak di desa Sunnyside Isle; kawanan ayam & sapi bergerak; kincir angin berputar. | *"Selamat pagi/siang bapak/ibu penguji. Game AI Labyrinth mengintegrasikan seluruh materi AI ke dalam satu RPG pulau terpadu tanpa library AI eksternal. Di awal, hero bergerak bebas dengan kendali manual, diiringi navigasi reaktif hewan dan NPC."* | Buka `docs/figures/architecture.png` jika jendela game gagal muncul. |
| **1:00 - 2:30** | **STRIPS Planning & Auto-Pilot (F9)** | Tekan `[F7]` lalu `[F9]` <br> Opsional: `[F1]` & `[F2]` | Panel Unified Planner menampilkan 37 langkah rencana ekspedisi makro. Hero bergerak otonom via autopilot $A^*$. | *"Saat menekan F7, mesin perencana STRIPS Weighted A\* dengan heuristik relaksasi Fast-Forward menyusun 37 langkah ekspedisi dalam 1 detik. Menekan F9 mengaktifkan mode Auto-Pilot di mana hero menjalankan rencana secara mandiri. Sistem memanggil A\* spasial untuk jarak nyata."* | Buka berkas `docs/report_data/benchmark.txt` (P4: 37 langkah, 118.48s). |
| **2:30 - 3:30** | **Uji Demonstrasi CLI Perencanaan** | Tutup game (`ESC`), jalankan: <br> `python3 src/main.py --demo-ojek` <br> `python3 src/main.py --demo-regression` <br> `python3 src/main.py --demo-graph` | Keluaran teks konsol terstruktur: pohon pencarian ojek, regresi mundur dari goal state, dan level planning graph mutex. | *"Berikut adalah verifikasi formal silabus perkuliahan: demo ojek kurir membuktikan pemenuhan prekondisi aksi, demo regresi membuktikan penelusuran mundur dari goal state, dan demo planning graph memperlihatkan relasi mutual exclusion (mutex) antar aksi."* | Buka berkas `docs/report_data/demo_ojek.txt` dan `demo_graph.txt`. |
| **3:30 - 5:00** | **Decisions Under Uncertainty & Papan Cuaca** | `python3 src/main.py --autopilot --demo-weather=berita` <br> Dekati papan alun-alun, tekan `[E]`, lalu tekan `[F7]` (Tab 3) | Prompt `[E] Baca Papan`. Banner mengabarkan 'air mulai naik'. Posterior $P(\text{Banjir})$ melompat dari 10% ke 50%. Rute autopilot berubah dari titik cyan (15 tile) ke hijau (19 tile). | *"Pada modul Keputusan di Bawah Ketidakpastian, jalur pesisir pantai memiliki risiko banjir pasang surut. Awalnya hero memilih rute pintas (15 tile). Namun setelah membaca papan cuaca di alun-alun desa, keyakinan Bayes diperbarui menjadi 50% (melampaui titik kritis analitik f\* = 0.1333). Hero otomatis memutar lewat rute aman."* | Jalankan CLI: `python3 src/main.py --demo-mdp` dan `--demo-sensitivity` untuk memperlihatkan konvergensi Bellman. |
| **5:00 - 6:30** | **Pertarungan Bos: CSP Loadout & Minimax** | Hero tiba di gerbang timur (`(2384, 880)`), tekan `[E]` untuk masuk arena <br> Panel `[F3]` dan `[F4]` | Layar pemilihan loadout (solver CSP). Arena pertarungan turn-based: status HP, opsi aksi, panel Minimax F3 & Local Search F4. | *"Sebelum melawan Skeleton Overlord, modul CSP Backtracking dengan Forward Checking mengoptimasi ramuan dan senjata di bawah batas beban ransel. Di arena, bos dikendalikan Minimax dengan Alpha-Beta Pruning dan Transposition Table, memangkas lebih dari 91% evaluasi cabang pohon."* | Jalankan CLI: `python3 src/main.py --benchmark-ai` untuk menampilkan tabel pruning kedalaman 7. |
| **6:30 - 7:30** | **Penutup, Hasil Kunci & Refleksi Keterbatasan** | Tekan `[F8]` di desa, lalu tampilkan dokumen ringkasan | Panel HTN rutinitas Pak Tani dan Kang Penggiling. Presenter memaparkan tabel ringkasan benchmark. | *"Sebagai penutup, seluruh 213 unit test repositori lulus 100%. Kami juga mendokumentasikan keterbatasan secara jujur: misalnya pada model koridor penuh pesisir pantai dengan penalti terukur 1.78s, biaya membaca papan cuaca tidak pernah impas karena frekuensi perjalanan harian tidak mencukupi mitigasi risikonya."* | Tampilkan berkas `docs/LAPORAN_INDUK.md` seksi Keterbatasan Terpadu. |

---

### 3. Lembar Perintah Cepat (*Cheat Sheet*) untuk Presenter

Berikut adalah ringkasan perintah baris yang dapat disalin-tempel dengan cepat selama sesi demonstrasi berlangsung:

```bash
# ----------------------------------------------------------------------
# 1. LIVE GAMEPLAY DENGAN RAMALAN CUACA BANJIR DETERMINISTIK (REKOMENDASI UTAMA)
# ----------------------------------------------------------------------
python3 src/main.py --autopilot --demo-weather=berita

# ----------------------------------------------------------------------
# 2. DEMONSTRASI CLI PERENCANAAN OTOMATIS (STRIPS & GRAPH)
# ----------------------------------------------------------------------
python3 src/main.py --demo-ojek           # Silabus Slide 1-26, 30
python3 src/main.py --demo-regression     # Silabus Slide 27, 30
python3 src/main.py --demo-graph          # Silabus Slide 31-35

# ----------------------------------------------------------------------
# 3. DEMONSTRASI CLI KEPUTUSAN DI BAWAH KETIDAKPASTIAN (BAYES & MDP)
# ----------------------------------------------------------------------
python3 src/main.py --demo-bayes          # Silabus Slide 3-8 (Prior & Posterior)
python3 src/main.py --demo-mdp            # Silabus Slide 13-21 (Tabel Value Iteration)
python3 src/main.py --demo-sensitivity    # Silabus Slide 22 (Batas f* = 0.1333)
python3 src/main.py --demo-reward-shaping # Silabus Slide 23 (Jebakan Loop Abadi +3)

# ----------------------------------------------------------------------
# 4. BENCHMARK DAN VERIFIKASI REPRODUKSIBILITAS
# ----------------------------------------------------------------------
python3 src/main.py --benchmark-ai        # Minimax, CSP, Local Search
python3 src/main.py --selftest 120        # Simulasi stabilitas 120 frame headless
python3 -m unittest discover -s tests -p 'test_*.py' # 213 Unit Tests
```

---

### 4. Prosedur Penanganan Kendala Teknis Saat Live Demo (*Troubleshooting*)

1. **Jendela Game Tidak Terbuka atau Error Driver Tampilan:**
   - Masalah: Driver grafis lokal tidak mengenali hardware acceleration OpenGL.
   - Solusi: Tutup sesi, buka terminal dan jalankan demonstrasi mode CLI (`--demo-ojek`, `--demo-mdp`, `--benchmark-ai`), lalu tunjukkan tangkapan layar di `docs/screenshots/`.
2. **Hero Autopilot Terjebak di Belakang Pagar atau Pintu:**
   - Solusi: Tekan `[F9]` untuk beralih ke kendali Manual, arahkan hero keluar menggunakan tombol panah, lalu tekan `[F9]` kembali untuk melanjutkan Auto-Pilot.
3. **Papan Cuaca Menampilkan 'Langit Cerah' saat Presenter Ingin Menunjukkan 'Banjir':**
   - Solusi: Tutup game dan jalankan kembali dengan flag deterministik khusus `--demo-weather=berita`.

