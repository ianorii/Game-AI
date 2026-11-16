# LAPORAN TEKNIS: KEPUTUSAN DI BAWAH KETIDAKPASTIAN (DECISIONS UNDER UNCERTAINTY)
## Implementasi Silabus Slide 3–23 & Integrasi Dunia Game Sunnyside Isle

---

### 1. Ringkasan Eksekutif & Pemetaan Silabus Kuliah

Modul ini mengimplementasikan teori formal **Pengambilan Keputusan di Bawah Ketidakpastian** (*Decisions Under Uncertainty*) sesuai silabus perkuliahan (Slide 3–23) secara murni dengan Python tanpa ketergantungan library AI/MDP eksternal. Sistem ini terintegrasi penuh ke dalam loop permainan RPG Sunnyside Isle, meliputi:
- Siklus cuaca stokastik 240 detik dengan status banjir tersembunyi (*hidden world state*).
- Papan pengumuman ramalan cuaca desa berbasis Teorema Bayes (*Bayesian belief update*).
- Model Markov Decision Process (MDP) dengan penyelesaian *Synchronous Value Iteration* berbasis persamaan Bellman.
- Evaluasi kebijakan optimal ($\pi^*$) dinamis dengan titik belok kritis analitik $f^* = \frac{2}{15} \approx 0.1333$.
- Visualisasi terpadu pada Tab 3 Panel **[F7] UnifiedPlannerPanel** dan banner mode **ADVISOR**.
- Evaluasi empiris Monte Carlo ganda ($N = 10.000$ hari): model utilitas slide abstrak dan model waktu nyata (detik) game.
- Mekanisme dinamis *Flood Flush* yang mengevakuasi hero ke tile kering terdekat (*nearest dry tile*) dengan animasi native swimming 12 frame tanpa memengaruhi entitas lain.
- Analisis mendalam Nilai Informasi vs Biaya Informasi (*Value of Information vs Information Cost*) dan amortisasi per hari cuaca.

**Tabel 1. Pemetaan Silabus Kuliah dan Implementasi Kode Keputusan di Bawah Ketidakpastian**

| Slide Kuliah | Topik Silabus | Implementasi Kode | Unit Test Terkait |
| :--- | :--- | :--- | :--- |
| **Slide 3–7** | Probabilitas Dasar, EV, EU, MEU | `src/decision/probability.py` (`expected_value`, `expected_utility`, `meu`) | `tests/test_decision_under_uncertainty.py::test_probability_basics` |
| **Slide 8–9** | Teorema Bayes & Bukti Pengamatan | `src/decision/probability.py` (`bayes_update`), `src/decision/weather_manager.py` | `tests/test_decision_under_uncertainty.py::test_bayes_rule`, `test_putaran3_uncertainty.py` |
| **Slide 10–15**| MDP Formulasi ($S, A, T, R, \gamma$) | `src/decision/mdp.py` (`class MDP`), `src/decision/flood_model.py` | `tests/test_decision_under_uncertainty.py::test_mdp_validation` |
| **Slide 16–21**| Bellman Equation & Value Iteration | `src/decision/mdp.py` (`value_iteration`, `compute_q`, `extract_policy`) | `tests/test_decision_under_uncertainty.py::test_value_iteration_convergence` |
| **Slide 22** | Sensitivitas $f^*$ & Pembalikan Policy | `src/decision/flood_model.py` (`analyze_sensitivity_f`), `src/decision/weather_manager.py` | `tests/test_decision_under_uncertainty.py::test_critical_threshold_f_star` |
| **Slide 23** | Varian Reward Shaping Trap (+3) | `src/decision/flood_model.py` (`create_flood_mdp(reward_shaping=True)`) | `tests/test_decision_under_uncertainty.py::test_reward_shaping_infinite_loop` |

---

### 2. Formulasi Matematika & Model MDP

#### 2.1 Ruang Keadaan (*State Space*) & Transisi ($S, A, T$)
Graf rute perjalanan terbagi menjadi 5 keadaan:
- $S = \{\text{Rumah}, \text{Warung}, \text{Jalan Raya}, \text{Kampus}, \text{Banjir}\}$
- Terminal states: $\text{Kampus}$ (Tujuan tercapai, reward $+10$), $\text{Banjir}$ (Terminal penalti, reward $-20$).
- Persimpangan keputusan berada di state **Warung**:
  - Aksi $\text{Raya}$: Menuju **Jalan Raya** secara deterministik ($P = 1.0$), biaya langkah $-2.0$, lalu ke **Kampus** (Total utilitas pasti $+6.0$).
  - Aksi $\text{Pintas}$: Melewati rute cepat pesisir pantai dengan ketidakpastian banjir $f$:
    $$T(\text{Warung}, \text{Pintas}, \text{Kampus}) = 1 - f$$
    $$T(\text{Warung}, \text{Pintas}, \text{Banjir}) = f$$

#### 2.2 Persamaan Bellman & Value Iteration
Algoritma *Synchronous Value Iteration* memperbarui nilai keadaan secara iteratif hingga konvergen ($\|V_k - V_{k-1}\|_\infty < 10^{-6}$):
$$V_{k+1}(s) = \max_{a \in A(s)} \sum_{s'} T(s, a, s') \left[ R(s, a, s') + \gamma V_k(s') \right]$$
dengan faktor diskon $\gamma = 0.8$.

#### 2.3 Tabel Konvergensi Nilai State ($f = 0.10$ vs $f = 0.25$)

**Tabel 2. Konvergensi Nilai State Bellman Value Iteration dan Pembalikan Kebijakan**

| State ($s$) | $V(s)$ saat $f = 0.10$ (Prior Cuaca Normal) | $V(s)$ saat $f = 0.25$ (Risiko Banjir Tinggi) | Catatan / Kebijakan |
| :--- | :---: | :---: | :--- |
| **Rumah** | $3.60$ | $2.80$ | Aksi: Ke Warung |
| **Warung** | **$7.00$** ($\pi^* = \text{Pintas}$) | **$6.00$** ($\pi^* = \text{Raya}$) | **Pembalikan Kebijakan Optimal** |
| **Jalan Raya** | $6.00$ | $6.00$ | Aksi: Ke Kampus (Deterministik) |
| **Kampus** | $10.00$ | $10.00$ | Terminal Reward $+10$ |
| **Banjir** | $-20.00$ | $-20.00$ | Terminal Penalti $-20$ |

---

### 3. Sistem Bukti Bayes & Penentuan Titik Belok $f^*$

#### 3.1 Pembaruan Keyakinan (*Bayesian Belief Update*)
Pemain/agen memiliki prior $P(\text{Banjir}) = 0.10$. Dengan membaca Papan Pengumuman Cuaca di alun-alun desa (`(1504, 1024)`), agen menerima bukti observasi $E \in \{\text{Berita (Air Naik)}, \text{Langit Cerah}\}$ dengan model likelihood:
$$P(\text{Berita} \mid \text{Banjir}) = 0.90, \quad P(\text{Berita} \mid \text{NoBanjir}) = 0.10$$
$$P(\text{Cerah} \mid \text{Banjir}) = 0.10, \quad P(\text{Cerah} \mid \text{NoBanjir}) = 0.90$$

Perhitungan probabilitas marjinal bukti:
$$P(\text{Berita}) = (0.90)(0.10) + (0.10)(0.90) = 0.09 + 0.09 = 0.18$$
$$P(\text{Cerah}) = (0.10)(0.10) + (0.90)(0.90) = 0.01 + 0.81 = 0.82$$

Pembaruan Posterior Bayes:
- **Jika Muncul Berita Cuaca:**
  $$P(\text{Banjir} \mid \text{Berita}) = \frac{P(\text{Berita} \mid \text{Banjir}) P(\text{Banjir})}{P(\text{Berita})} = \frac{0.09}{0.18} = 0.50$$
- **Jika Langit Cerah:**
  $$P(\text{Banjir} \mid \text{Cerah}) = \frac{P(\text{Cerah} \mid \text{Banjir}) P(\text{Banjir})}{P(\text{Cerah})} = \frac{0.01}{0.82} \approx 0.012195 \ (1.22\%)$$

#### 3.2 Analisis Sensitivitas & Ambang Batas $f^*$
Expected Utility dari kedua opsi di titik Warung:
$$EU(\text{Pintas}) = (1 - f)(10) + f(-20) = 10 - 30f$$
$$EU(\text{Raya}) = 6.00$$

Titik kritis $f^*$ tercapai saat kedua pilihan memberikan nilai setara:
$$10 - 30f^* = 6 \implies 30f^* = 4 \implies f^* = \frac{4}{30} = \frac{2}{15} \approx 0.133333 \ (13.33\%)$$

- **Kondisi Normal (Belief $0.10 < 0.1333$):**
  $EU(\text{Pintas}) = 10 - 30(0.10) = 7.00 > 6.00 \implies \pi^*(\text{Warung}) = \text{Pintas}$.
- **Setelah Membaca Berita Cuaca (Posterior $0.50 > 0.1333$):**
  $EU(\text{Pintas}) = 10 - 30(0.50) = -5.00 < 6.00 \implies \pi^*(\text{Warung}) = \text{Raya}$ (**Detour Memutar**).

---

### 4. Analisis Konsistensi Model & Kalibrasi Waktu Nyata

#### 4.1 Pemetaan Segmen: Sub-segmen vs Koridor Penuh
Pada pengujian game nyata Sunnyside Isle dengan kecepatan hero planner $4.6 \text{ tile/detik} = 147.2 \text{ px/s}$, terdapat dua cara mendefinisikan rute pintas vs rute aman:

1. **Sub-segmen Divergensi Lokal (`(2016, 880)` ke `(2208, 880)`)**:
   - Merepresentasikan segmen bercabang murni di mana jalur pantai dan jalur memutar batu karang terpisah, lalu menyatu kembali.
   - Pintas: $168.2 \text{ px} \implies 1.1427 \text{ s} \approx 1.14 \text{ s}$.
   - Aman: $220.4 \text{ px} \implies 1.4973 \text{ s} \approx 1.50 \text{ s}$ ($\Delta t = 0.3546 \text{ s} \approx 0.36 \text{ s}$, selisih +31.0%).
   - *Catatan Kalibrasi Slide*: Angka $1.14\text{ s}$ dan $1.50\text{ s}$ memiliki rasio utilitas langkah slide kuliah ($\Delta R = 0.36$, penalti $2.70\text{ s} \implies f^* = 0.36 / 2.70 = 2/15 \approx 0.1333$).

2. **Koridor Penuh Pantai (`(1984, 880)` ke `(2384, 880)`)**:
   - Merepresentasikan transit penuh dari mulut chokepoint pantai barat hingga gerbang pantai timur (mencakup jalur lurus sebelum dan sesudah titik belok).
   - Pintas: $15 \text{ tile} = 480.0 \text{ px} \implies 3.2609 \text{ s} \approx 3.26 \text{ s}$.
   - Aman: $19 \text{ tile} = 608.0 \text{ px} \implies 4.1304 \text{ s} \approx 4.13 \text{ s}$ ($\Delta t = 0.8696 \text{ s} \approx 0.87 \text{ s}$, selisih +26.7%).

Kedua rute adalah **100% rute alami** pada peta asli `walkable_mask.png` tanpa modifikasi collision map atau jembatan buatan. Label visual autopilot game menggunakan koridor penuh: `15 Tile / 3.26s` (Pintas) vs `19 Tile / 4.13s` (Aman).

#### 4.2 Matriks Perbandingan Komprehensif: 2 Definisi Segmen × 2 Model Penalti

Berikut adalah matriks komparasi lengkap dari `docs/report_data/corridor_segment_analysis.json`:

**Tabel 3. Matriks Komparasi 2 Definisi Segmen × 2 Model Penalti**

| Metrik Teoretis / Empiris | Sub-segmen Lokal ($\Delta t = 0.36\text{ s}$) [2.70s Calibrated] | Sub-segmen Lokal ($\Delta t = 0.36\text{ s}$) [1.78s Measured] | Koridor Penuh ($\Delta t = 0.87\text{ s}$) [2.70s Calibrated] | Koridor Penuh ($\Delta t = 0.87\text{ s}$) [1.78s Measured] |
| :--- | :---: | :---: | :---: | :---: |
| **Biaya Detour ($\Delta t$)** | $0.3546\text{ s}$ ($0.36\text{ s}$) | $0.3546\text{ s}$ ($0.36\text{ s}$) | $0.8696\text{ s}$ ($0.87\text{ s}$) | $0.8696\text{ s}$ ($0.87\text{ s}$) |
| **Penalti Banjir ($D$)** | $2.7000\text{ s}$ | $1.7783\text{ s}$ | $2.7000\text{ s}$ | $1.7783\text{ s}$ |
| **Ambang Batas Kritis ($f^*$)**| **$0.1313 \approx 0.1333$ ($2/15$)** | **$0.1994 \approx 0.2024$** | **$0.3221 \approx 0.32$** | **$0.4890 \approx 0.49$** |
| **Kebijakan Prior ($P=0.10$)** | Pintas ($0.10 < f^*$) | Pintas ($0.10 < f^*$) | Pintas ($0.10 < f^*$) | Pintas ($0.10 < f^*$) |
| **Kebijakan Berita ($P=0.50$)**| Raya ($0.50 > f^*$) | Raya ($0.50 > f^*$) | Raya ($0.50 > f^*$) | Raya ($0.50 > f^*$) |
| **Konsistensi Kebijakan ($\pi^*$)**| **100% KONSISTEN** | **100% KONSISTEN** | **100% KONSISTEN** | **100% KONSISTEN** |
| **Penghematan Kotor Papan** | $+0.1772\text{ s}$ | $+0.0952\text{ s}$ | $+0.0865\text{ s}$ | $+0.0035\text{ s}$ |
| **Neto 1 Trip (dari Rumah)** | $-0.0228\text{ s}$ | $-0.1048\text{ s}$ | $-0.1135\text{ s}$ | $-0.1965\text{ s}$ |
| **Batas Impas ($K$ Trip/Hari)**| **$K \ge 2$ trip/hari** | **$K \ge 3$ trip/hari** | **$K \ge 3$ trip/hari** | **TIDAK PERNAH IMPAS** ($K = 56.7$) |

> **Catatan Krusial**: Perhatikan bahwa kondisi $0.10 < f^* < 0.50$ terpenuhi pada keempat kombinasi model! Artinya, **keputusan agen AI untuk beralih dari rute Pintas ke rute Aman (Raya) setelah membaca berita cuaca adalah konsisten terhadap pilihan definisi segmen maupun model penalti**. Namun kami mencatat margin ketahanan (*robustness margin*) pada model koridor penuh penalti 1.78s tergolong tipis: $f^* = 0.4890$ berada persis di bawah $P=0.50$ (margin $1.1\%$). Secara matematis, dengan prior $P=0.10$, akurasi papan cuaca $p = P(\text{berita}\mid\text{banjir})$ harus $\ge 89.6\%$ agar posterior $\ge 0.4890$. Margin ketahanan terhadap akurasi ramalan cuaca hanyalah $0.4$ poin persentase dari akurasi nominal $90.0\%$; jika akurasi turun di bawah $89.6\%$, kebijakan koridor penuh langsung berbalik (agen tetap memilih Pintas). Invariansi ini bersyarat ketat pada asumsi posterior berita $P(\text{banjir}\mid\text{berita}) \ge 0.50$.

#### 4.3 Pengukuran Penalti Banjir Empiris ($N = 200$ Percobaan Headless)
Kami mengukur keterlambatan fisik nyata saat hero terperangkap banjir di zona pantai `(2016, 864, 352, 96)`:
- Kunci animasi berenang (`swimming`): $1.5000 \text{ s}$.
- Jarak re-walk dari tile kering terdekat (`find_nearest_dry_tile`) ke jalur: rata-rata $0.2783 \text{ s}$ ($0.2174\text{ s} - 0.4348\text{ s}$).
- **Total Keterlambatan Fisik Nyata**:
  $$\text{Mean Delay} = 1.7783 \text{ s} \quad (95\% \text{ CI}: [1.7647, 1.7918] \text{ s}, \quad \text{Std Dev} = 0.0979 \text{ s})$$
- **Interpretasi Quasi-Deterministik CI 95%**: Interval kepercayaan 95% yang sangat sempit ($[1.7647, 1.7918]\text{ s}$) dari $N=200$ sampel atas variasi offset piksel masuk mencerminkan sifat simulasi Pygame dan pathfinding A* yang beroperasi secara kuasi-deterministik. Variansi kecil ($\sigma = 0.0979\text{ s}$) timbul semata-mata dari offset koordinat piksel masuk diskrit ($0-32\text{ px}$) saat hero menyentuh garis batas zona banjir, yang memicu variasi jarak tempuh evakuasi re-walk antara $0.2174\text{ s} - 0.4348\text{ s}$, bukan berasal dari stokastisitas atau noise lingkungan acak.
- **Rasionalisasi Dua Nilai Penalti**:
  1. *Penalti Terukur Nyata ($1.78\text{ s}$)*: Durasi fisik empiris aktual dalam game engine ($1.50\text{ s}$ animasi + $0.28\text{ s}$ re-walk).
  2. *Penalti Terkalibrasi Mundur ($2.70\text{ s}$)*: Nilai hipotetis yang diturunkan secara terbalik (*reverse-calibrated*) untuk mengkalibrasi rasio detour terhadap penalti agar tepat mereplikasi ambang batas silabus perkuliahan Slide 22 ($f^* = \Delta R / D = 0.36 / 2.70 = 2/15 \approx 0.1333$).
  3. *Invariansi Kebijakan & Batas Ketahanan*: Terlepas dari nilai penalti yang dipakai ($1.78\text{ s}$ maupun $2.70\text{ s}$), kesimpulan kebijakan agen AI adalah konsisten: rute Pintas selalu dipilih saat hari cerah ($0.10 < f^*$), dan rute Raya selalu dipilih setelah menerima berita banjir ($0.50 > f^*$, dengan margin ketahanan $1.1\%$ pada koridor penuh).
- Penalti ini dikonfigurasi melalui `config.FLOOD_PENALTY_TIME = 1.78`, dan seluruh notifikasi HUD serta log game menampilkan waktu penalti sebenarnya (tidak ada lagi nilai hardcode `-20s`).

#### 4.4 Verifikasi Geometri Buffer Zona Banjir Pesisir
Kritik penempatan zona banjir diuji secara kuantitatif terhadap 24 tile walkable di dalam rect `(2016, 864, 352, 96)`:
- **10 tile (41.7%)**: Jarak Euclidean $1.00\text{ tile}$ persis di samping air laut (*water shore boundary*).
- **12 tile (50.0%)**: Jarak Euclidean $1.41 - 2.24\text{ tile}$ dari air laut.
- **2 tile (8.3%)**: Jarak Euclidean $2.83\text{ tile}$ dari air laut.
- **100% tile (24/24)**: Berada dalam jarak Chebyshev radius $\le 2\text{ tile}$ dari air laut.
- Visualisasi lengkap telah dirender ke `docs/figures/flood_zone_water_distance_map.png`. Overlay banjir sungguhan menggunakan rendering gelombang air organik lembut (*organic soft water ripples*) pada tile pasir pantai ber-alpha transparan, tanpa menutupi bangunan atau kios di sekitarnya.
- Seluruh 24 tile walkable di dalam zona banjir terbukti 100% berhasil dievakuasi ke 17 tile daratan kering unik di luar zona banjir dengan konektivitas A* sempurna menuju gerbang boss.

---

### 5. Analisis Nilai vs Biaya Informasi (*Information Cost & VPI*)

Strategi adaptif menghasilkan nilai teoritis $\text{VPI} = +1.98$ poin utilitas pada model slide abstrak. Namun, **informasi observasi tidak pernah gratis di dunia nyata**. Membaca papan cuaca memerlukan interaksi fisik tombol `[E]` selama $0.20\text{ s}$ ditambah deviasi jarak A* menuju koordinat papan `(1504, 1024)`.

#### 5.1 Biaya Tempuh Membaca Papan Ramalan Cuaca: Model Sub-segmen ($\Delta t = 0.36\text{ s}$)

**Tabel 4. Biaya Tempuh Membaca Papan Ramalan Cuaca: Model Sub-segmen**

| Titik Keberangkatan Hero | Waktu Langsung ke Boss | Waktu via Papan Cuaca | Biaya Detour + Interaksi [E] | Selisih Neto (1 Trip, 2.70s) | Impas $K$ (2.70s) | Selisih Neto (1 Trip, 1.78s) | Impas $K$ (1.78s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Rumah (Spawn Desa)** | $7.39 \text{ s}$ | $7.59 \text{ s}$ | $0.00 \text{ s} + 0.20 \text{ s} = \mathbf{0.20 \text{ s}}$ | **$-0.0228 \text{ s}$** | $K \ge 2$ trip/hari | **$-0.1048 \text{ s}$** | $K \ge 3$ trip/hari |
| **Alun-alun (Pusat Desa)** | $6.52 \text{ s}$ | $6.94 \text{ s}$ | $0.22 \text{ s} + 0.20 \text{ s} = \mathbf{0.42 \text{ s}}$ | **$-0.2428 \text{ s}$** | $K \ge 3$ trip/hari | **$-0.3248 \text{ s}$** | $K \ge 5$ trip/hari |
| **Warung (Awal Koridor)** | $3.26 \text{ s}$ | $11.07 \text{ s}$ | $7.61 \text{ s} + 0.20 \text{ s} = \mathbf{7.81 \text{ s}}$ | **$-7.6328 \text{ s}$** | $K \ge 45$ (Tidak Realistis) | **$-7.7148 \text{ s}$** | $K \ge 83$ (Tidak Realistis) |
| **Ladang (Pak Tani)** | $20.43 \text{ s}$ | $21.29 \text{ s}$ | $0.66 \text{ s} + 0.20 \text{ s} = \mathbf{0.86 \text{ s}}$ | **$-0.6828 \text{ s}$** | $K \ge 5$ trip/hari | **$-0.7648 \text{ s}$** | $K \ge 10$ trip/hari |

#### 5.2 Biaya Tempuh Membaca Papan Ramalan Cuaca: Model Koridor Penuh ($\Delta t = 0.87\text{ s}$)

**Tabel 5. Biaya Tempuh Membaca Papan Ramalan Cuaca: Model Koridor Penuh**

| Titik Keberangkatan Hero | Biaya Detour + Interaksi [E] | Selisih Neto (1 Trip, 2.70s) | Impas $K$ (2.70s) | Selisih Neto (1 Trip, 1.78s) | Impas $K$ (1.78s) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Rumah (Spawn Desa)** | $\mathbf{0.20 \text{ s}}$ | **$-0.1135 \text{ s}$** | $K \ge 3$ trip/hari ($2.31$) | **$-0.1965 \text{ s}$** | **TIDAK PERNAH IMPAS** ($K = 56.7$) |
| **Alun-alun (Pusat Desa)** | $\mathbf{0.42 \text{ s}}$ | **$-0.3335 \text{ s}$** | $K \ge 5$ trip/hari ($4.86$) | **$-0.4165 \text{ s}$** | **TIDAK PERNAH IMPAS** ($K = 119.2$) |
| **Warung (Awal Koridor)** | $\mathbf{7.81 \text{ s}}$ | **$-7.7235 \text{ s}$** | $K \ge 91$ trip/hari | **$-7.8065 \text{ s}$** | **TIDAK PERNAH IMPAS** ($K = 2215$) |
| **Ladang (Pak Tani)** | $\mathbf{0.86 \text{ s}}$ | **$-0.7735 \text{ s}$** | $K \ge 10$ trip/hari ($9.94$) | **$-0.8565 \text{ s}$** | **TIDAK PERNAH IMPAS** ($K = 244$) |

#### 5.3 Wawasan Teori Keputusan Formal
1. **Kenyataan Informasi: Selalu Merugikan untuk Single-Trip**:
   Bahkan dari Rumah (di mana papan berada persis di sepanjang rute keluar desa tanpa deviasi jarak), jeda interaksi $0.20\text{ s}$ sudah melampaui penghematan kotor teoretis ($+0.1772\text{ s}$ atau $+0.0865\text{ s}$). Dengan kata lain, **membaca papan cuaca untuk satu kali jalan saja selalu tidak rasional**.
2. **Kekuatan vs Batasan Amortisasi Siklus Harian ($K$ Perjalanan per 240 Detik)**:
   - Pada model sub-segmen ($1.14\text{ s}$ vs $1.50\text{ s}$), impas dapat dicapai pada $K \ge 2$ trip/hari (2.70s) atau $K \ge 3$ trip/hari (1.78s).
   - Namun pada model koridor penuh dengan penalti terukur $1.78\text{ s}$, penghematan kotor informasi hanyalah $+0.0035\text{ s}$ per trip. Karena biaya interaksi $0.20\text{ s}$ adalah $57\times$ lebih besar dari penghematan kotor, titik impas membutuhkan $K = 56.7\text{ perjalanan}$. Mengingat 1 perjalanan membutuhkan waktu minimal $15-20\text{ detik}$, jumlah perjalanan maksimum yang mungkin secara fisik dalam 1 hari cuaca ($240\text{ detik}$) hanyalah $12-15\text{ trip}$. Kasus ini secara definitif membuktikan kondisi **TIDAK PERNAH IMPAS**.
3. **Pelajaran Berharga Teori Keputusan**:
   Informasi ramalan cuaca terbukti akurat secara Bayes ($P(\text{Banjir}\mid\text{Berita}) = 50\%$), namun **tidak bernilai ekonomis untuk dicari** ketika biaya akuisisi informasi melebihi kapasitas mitigasi risiko. Agen yang rasional dalam kondisi ini lebih memilih *Blind Policy* (mengabaikan papan dan langsung berangkat).

---

### 6. Hasil Evaluasi Empiris Monte Carlo ($N = 10.000$ Hari)

Simulasi Monte Carlo dijalankan dengan seed deterministik `20261021` selama 10.000 hari cuaca:

#### 6.1 Model Waktu Game Nyata (Satuan Detik)

**Tabel 6. Hasil Simulasi Monte Carlo Waktu Game Nyata (N = 10.000 Hari)**

| No | Strategi Navigasi | Rata-rata Waktu Nyata | 95% Confidence Interval | Nilai Teori | Penghematan vs Fast |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | **Selalu Rute Cepat (Pintas)** | **$1.4046 \text{ s}$** | $[1.3889, 1.4203]$ | $1.4100 \text{ s}$ | $0.0000 \text{ s}$ (Basis) |
| 2 | **Selalu Rute Aman (Raya)** | **$1.5000 \text{ s}$** | $[1.5000, 1.5000]$ | $1.5000 \text{ s}$ | $-0.0954 \text{ s}$ |
| 3 | **Blind MDP (Tanpa Cek Papan)** | **$1.4046 \text{ s}$** | $[1.3889, 1.4203]$ | $1.4100 \text{ s}$ | $0.0000 \text{ s}$ |
| 4 | **Adaptif Bayes (Membaca Papan)**| **$1.2274 \text{ s}$** | $[1.2219, 1.2330]$ | **$1.2318 \text{ s}$** | **$+0.1772 \text{ s}$** |

#### 6.2 Model Slide Abstrak (Satuan Poin Utilitas)

**Tabel 7. Hasil Simulasi Monte Carlo Model Slide Abstrak (N = 10.000 Hari)**

| No | Strategi Navigasi | Rata-rata Payoff Empiris | 95% Confidence Interval | Nilai Teori EU | Deviasi Empiris vs Teori |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | **Selalu Rute Cepat (Pintas)** | **$7.0600$** | $[6.8852, 7.2348]$ | $7.0000$ | $+0.85\%$ |
| 2 | **Selalu Rute Aman (Raya)** | **$6.0000$** | $[6.0000, 6.0000]$ | $6.0000$ | $0.00\%$ |
| 3 | **Blind MDP (Tanpa Cek Papan)** | **$7.0600$** | $[6.8852, 7.2348]$ | $7.0000$ | $+0.85\%$ |
| 4 | **Adaptif Bayes (Membaca Papan)**| **$9.0286$** | $[8.9670, 9.0902]$ | **$8.9800$** | $+0.54\%$ |

---

### 7. Integrasi Gameplay, UI & Audit Entitas

#### 7.1 Daftar Entitas Resmi Dunia Game
Berdasarkan data spawn resmi dari `assets/maps/sunnyside_isle.json` (`game.tile_map.animals`, `game.npcs`, `game.hero`, `game.boss`):
- **1 Hero**: Bergerak manual / autopilot (`(1440, 1056)`).
- **2 NPC HTN Otonom**: Pak Tani (`(528, 448)`) & Kang Penggiling (`(1328, 640)`).
- **11 Hewan Ternak**:
  - 4 Domba (Sheep) di padang rumput timur (`(1920, 320)`, `(2016, 352)`, `(1920, 288)`, `(1856, 384)`).
  - 2 Sapi (Cow) di kandang barat (`(704, 480)`, `(672, 448)`).
  - 3 Ayam (Chicken) di sekitar desa (`(1344, 992)`, `(640, 416)`, `(1344, 960)`).
  - 2 Bebek (Duck) di danau desa (`(1280, 320)`, `(1344, 352)`, `is_water_animal=True`).
- **1 Boss Statis**: Skeleton Overlord di arena gerbang (`(2464, 448)`).
- **Total Entitas**: Tepat **14 entitas bergerak + 1 boss statis = 15 total entitas**. Babi (*pig*) hanya merupakan kelas uji di `src/core/animal.py` dan tidak di-spawn pada peta pulau aktif.
- **Catatan Aset Gerbang & Pantai**: Gerbang terkunci (*LockedGate*) telah direposisi ke *chokepoint* alami di antara tebing batu menuju Obsidian Keep Ruins pada koordinat $(2496, 512)$ (Petak 79, Baris 16). Area pantai dan tebing telah dibersihkan dari gubuk serta krat kayu, dengan *collision* terdaftar pada `walkable_mask.png` sehingga rute navigasi A* berjalan mulus tanpa ada *clipping* visual.

#### 7.2 Audit Footprint Bangunan Aktif (`docs/report_data/footprint_audit.csv`)
Dari total 20 entri bangunan yang dikelola (18 bangunan fisik aktif yang terlihat di peta pulau dan 2 entri bangunan *phantom* di luar batas kanvas pulau dinonaktifkan), seluruhnya dipetakan secara presisi ke dalam 27 bounding box (*rect*) tapak. Audit pemindaian piksel opak non-transparan (alpha > 0) membuktikan:
- Rata-rata cakupan dinding opak: **98.8%**.
- **Metrik Tunggal Standar: Luas Terbuang Terbobot (*Weighted Wasted Area*) = 4.21%**
  - Dihitung sebagai $\frac{\sum \text{piksel transparan di dalam footprint}}{\sum \text{luas tapak bangunan}} = \frac{7.758 \text{ px}}{184.160 \text{ px}} = 4.21\%$.
  - Rerata aritmatika per bangunan adalah $6.07\%$.
- *Klarifikasi Nilai Lama*: Angka lama 1.83% dinyatakan **tidak valid** karena hanya menghitung perkiraan bounding box kasar tanpa alpha masking; metrik tunggal $4.21\%$ dihasilkan dari audit alpha masking beresolusi piksel terhadap atap bangunan berarsitektur miring (*slanted roofs*).

#### 7.3 Verifikasi Test Suite Komprehensif (213 Unit Tests, 14 Berkas)
Test suite dijalankan penuh dan lulus 100% (`Ran 213 tests in ~86s. OK`):
1. `test_asset_catalog`: 10 tests
2. `test_battle_mode`: 11 tests
3. `test_collision_and_decor_fixes`: 20 tests (termasuk simulasi 60s game loop @ 60 FPS pada 15 entitas resmi)
4. `test_collision_editor`: 9 tests
5. `test_csp_local_search`: 31 tests
6. `test_decision_under_uncertainty`: 17 tests
7. `test_hero_sprite`: 8 tests
8. `test_htn`: 9 tests
9. `test_lecture_planning`: 16 tests
10. `test_phase1a`: 17 tests
11. `test_putaran3_uncertainty`: 16 tests (termasuk tes konsistensi koridor vs sub-segmen, biaya informasi, zona buffer air, evakuasi dry tile, config penalti, dan label rute)
12. `test_strips_planner`: 31 tests
13. `test_village_deco`: 9 tests
14. `test_world_actions`: 9 tests
*Asal-usul kenaikan 189 -> 213 (+24 tests)*: +16 test dari modul uncertainty baru (`test_putaran3_uncertainty.py`), +7 test collision & simulasi loop (`test_collision_and_decor_fixes.py`), +1 test animasi berenang (`test_hero_sprite.py`).

---

### 8. Evaluasi Keterbatasan & Hasil Negatif yang Jujur

1. **Kasus Koridor Penuh 1.78s Tidak Pernah Impas ($K = 56.7$ Trip/Hari)**:
   Pada definisi koridor penuh pantai ($3.26\text{ s}$ vs $4.13\text{ s}$, selisih $\Delta t = 0.87\text{ s}$) dengan keterlambatan fisik terukur $1.78\text{ s}$, penghematan kotor ramalan cuaca hanya $+0.0035\text{ s}$. Karena biaya interaksi membaca papan adalah $0.20\text{ s}$ ($57\times$ lebih besar), pemain memerlukan $56.7$ perjalanan dalam 1 hari cuaca ($240\text{ detik}$) untuk mencapai titik impas. Secara fisik ini mustahil (batas fisik maksimal hanya $12-15$ perjalanan per hari). Ini adalah temuan ilmiah yang berharga: **akurasi ramalan cuaca tidak otomatis menjamin nilai ekonomis ketika biaya akuisisi melampaui kemampuan mitigasi risiko**.
2. **Penghematan Sub-segmen Sangat Kecil (~0.10s – 0.18s)**:
   Bahkan pada model sub-segmen lokal, penghematan rata-rata bersih berkisar antara $+0.10\text{ s}$ hingga $+0.18\text{ s}$. Selisih fraksional detik ini hampir tidak terasa oleh pemain manusia, meskipun secara teoretis optimal bagi agen otonom.
3. **Keterbatasan Lokasi Papan Cuaca**:
   Membaca papan cuaca hanya memberikan keuntungan bersih jika hero berangkat dari pemukiman desa (Rumah/Alun-alun). Jika hero berangkat dari area pantai atau ladang, deviasi langkah menuju papan memakan waktu hingga $7.8\text{ s}$, menghasilkan kerugian bersih masif ($-7.7\text{ s}$).
4. **Peti dan Krat Kayu di Gerbang Pantai**:
   Krat-krat kayu di dasar gerbang pantai adalah grafis tileset asli GameMaker dari `assets/maps/sunnyside_isle.json` yang telah memiliki collision mask terdaftar pada `walkable_mask.png`, sehingga pathfinding A* secara otomatis memutari krat tersebut tanpa tabrakan.
5. **Asumsi Model Meteorologi**:
   Likelihood observasi $P(\text{Berita}\mid\text{Banjir}) = 0.90$ dan $P(\text{Berita}\mid\text{NoBanjir}) = 0.10$ merupakan parameter sintetis dari silabus perkuliahan untuk mengilustrasikan inversi probabilitas Bayes, bukan model simulasi iklim realistik.
