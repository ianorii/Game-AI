# PANDUAN & LAPORAN RESMI: KEPUTUSAN DI BAWAH KETIDAKPASTIAN
## Decisions Under Uncertainty & Multi-Armed Bandit (UCC) — Sunnyside Isle

---

### 1. Ringkasan Eksekutif & Pemetaan Silabus Kuliah

Modul **Decisions Under Uncertainty (UCC)** pada game *AI Labyrinth: Sunnyside Isle* mengimplementasikan seluruh materi pokok silabus perkuliahan AI (Slide 3–23) secara murni dengan Python tanpa ketergantungan *library* AI/MDP eksternal. Sistem ini terintegrasi penuh ke dalam siklus hidup game dunia terbuka (*open-world game loop*), meliputi:

1. **Teori Utilitas & MEU (Slide 3–7)**: Perhitungan Nilai Harapan (*Expected Value* / EV), Utilitas Harapan (*Expected Utility* / EU), dan Prinsip Utilitas Harapan Maksimum (*Maximum Expected Utility* / MEU).
2. **Pembaruan Keyakinan Bayes (Slide 8–9)**: Model observasi stokastik dengan *likelihood* dan bukti pengamatan melalui Papan Pengumuman Cuaca desa.
3. **Formulasi MDP Formal (Slide 10–15)**: Pendefinisian tupel $\langle S, A, T, R, \gamma \rangle$ pada jaringan rute pesisir pantai.
4. **Persamaan Bellman & Value Iteration (Slide 16–21)**: Algoritma *Synchronous Value Iteration* hingga konvergen ($\|V_{k} - V_{k-1}\|_\infty < 10^{-6}$) dengan faktor diskon $\gamma = 0.8$.
5. **Sensitivitas Titik Belok Kritis $f^*$ (Slide 22)**: Titik balik kebijakan analitik $f^* = \frac{2}{15} \approx 0.1333$ yang membalikkan kebijakan optimal dari rute Pintas ke rute Raya.
6. **Mekanik Nyata *Flood Flush* & Penalti Fisik**: Keterlambatan fisik nyata $1.78\text{ detik}$ (animasi berenang $1.50\text{ s}$ + evakuasi re-walk ke tile kering terdekat $0.28\text{ s}$).
7. **Nilai vs Biaya Informasi (VPI & Information Cost)**: Analisis teoretis $VPI = +1.98$ poin vs biaya tempuh fisik membaca papan ramalan cuaca.
8. **Multi-Armed Bandit (MAB 5 Spot)**: Dilema eksplorasi vs eksploitasi pada 5 dermaga pemancingan pulau menggunakan pembaruan konjugat Beta-Binomial, *Thompson Sampling*, dan UCB1 (*Regret Bound* $O(\ln T)$).
9. **Kebijakan Risiko Live Combat**: Model evaluasi risiko MEU pertempuran *real-time* melawan minion goblin hijau dengan batas ambang keamanan $\text{HP} \ge 35\%$.

---

### 2. Arsitektur Modul & Struktur Berkas

```text
src/decision/
├── probability.py      # Fungsi inti EV, EU, MEU, dan Teorema Bayes (Slide 3-9)
├── mdp.py              # Kelas formal MDP, Bellman update, Value Iteration (Slide 10-21)
├── flood_model.py      # Model MDP rute banjir pesisir, sensitivitas f*, reward shaping
├── weather_manager.py  # Pengelola siklus cuaca dunia, interaksi papan ramalan, flood flush
├── bandit.py           # Multi-Armed Bandit: Bernoulli arms, Thompson Sampling, UCB1
├── bandit_ui.py        # UI Modal Jurnal Nelayan & MAB Analyzer (Tombol [B])
├── demo_cli.py         # Script demonstrasi interaktif seluruh pembuktian matematis via terminal
└── __init__.py

src/combat_config.py    # Konfigurasi parameter live combat, hitbox, damage, dan HP player
docs/DECISION_UNCERTAINTY.md # Laporan komprehensif 3,684 kata dengan audit 10.000 Monte Carlo
```

---

### 3. Formulasi Matematika & Model MDP Banjir Pesisir

#### 3.1 Ruang Keadaan (*State Space*) & Transisi ($S, A, T$)
Graf perjalanan terbagi menjadi 5 keadaan:
- $S = \{\text{Rumah}, \text{Warung}, \text{Jalan Raya}, \text{Kampus}, \text{Banjir}\}$
- Terminal states: $\text{Kampus}$ (Tujuan tercapai, reward $+10$), $\text{Banjir}$ (Terminal penalti, reward $-20$).
- Persimpangan keputusan berada di state **Warung**:
  - **Aksi Raya**: Menuju **Jalan Raya** secara deterministik ($P = 1.0$), biaya langkah $-2.0$, lalu ke **Kampus** (Total utilitas pasti $+6.0$).
  - **Aksi Pintas**: Melewati rute cepat pesisir pantai dengan probabilitas banjir $f$:
    $$T(\text{Warung}, \text{Pintas}, \text{Kampus}) = 1 - f$$
    $$T(\text{Warung}, \text{Pintas}, \text{Banjir}) = f$$

#### 3.2 Persamaan Bellman & Konvergensi Nilai State
Algoritma *Synchronous Value Iteration* memperbarui nilai keadaan secara iteratif:
$$V_{k+1}(s) = \max_{a \in A(s)} \sum_{s'} T(s, a, s') \left[ R(s, a, s') + \gamma V_k(s') \right]$$

**Tabel Konvergensi Nilai State Bellman Value Iteration ($\gamma = 0.8$):**

| State ($s$) | $V(s)$ saat $f = 0.10$ (Prior Cuaca Normal) | $V(s)$ saat $f = 0.25$ (Risiko Banjir Tinggi) | Kebijakan Optimal ($\pi^*$) |
| :--- | :---: | :---: | :--- |
| **Rumah** | $3.60$ | $2.80$ | Aksi: Ke Warung |
| **Warung** | **$7.00$** ($\pi^* = \text{Pintas}$) | **$6.00$** ($\pi^* = \text{Raya}$) | **Pembalikan Kebijakan Optimal** |
| **Jalan Raya** | $6.00$ | $6.00$ | Aksi: Ke Kampus (Deterministik) |
| **Kampus** | $10.00$ | $10.00$ | Terminal Reward $+10$ |
| **Banjir** | $-20.00$ | $-20.00$ | Terminal Penalti $-20$ |

---

### 4. Sistem Bukti Bayes & Ambang Kritis $f^*$

#### 4.1 Pembaruan Keyakinan (*Bayesian Belief Update*)
Pemain/agen memiliki keyakinan awal (*prior*) $P(\text{Banjir}) = 0.10$. Dengan membaca Papan Pengumuman Cuaca di alun-alun desa (`(1504, 1024)`), agen menerima bukti observasi $E \in \{\text{Berita (Air Naik)}, \text{Langit Cerah}\}$ dengan model likelihood:
$$P(\text{Berita} \mid \text{Banjir}) = 0.90, \quad P(\text{Berita} \mid \text{NoBanjir}) = 0.10$$
$$P(\text{Cerah} \mid \text{Banjir}) = 0.10, \quad P(\text{Cerah} \mid \text{NoBanjir}) = 0.90$$

Pembaruan Posterior Bayes:
- **Jika Muncul Berita Cuaca (Air Mulai Naik):**
  $$P(\text{Banjir} \mid \text{Berita}) = \frac{(0.90)(0.10)}{(0.90)(0.10) + (0.10)(0.90)} = \frac{0.09}{0.18} = \mathbf{0.50} \ (50.0\%)$$
- **Jika Langit Cerah:**
  $$P(\text{Banjir} \mid \text{Cerah}) = \frac{(0.10)(0.10)}{(0.10)(0.10) + (0.90)(0.90)} = \frac{0.01}{0.82} \approx \mathbf{0.0122} \ (1.22\%)$$

#### 4.2 Ambang Batas Kritis $f^*$
Expected Utility di titik Warung:
$$EU(\text{Pintas}) = (1 - f)(10) + f(-20) = 10 - 30f$$
$$EU(\text{Raya}) = 6.00$$

Titik kritis $f^*$ tercapai saat kedua pilihan setara:
$$10 - 30f^* = 6 \implies 30f^* = 4 \implies f^* = \frac{4}{30} = \frac{2}{15} \approx \mathbf{0.133333} \ (13.33\%)$$

- **Kondisi Normal ($P = 0.10 < 0.1333$):** $EU(\text{Pintas}) = 7.00 > 6.00 \implies \pi^* = \text{Pintas}$.
- **Setelah Membaca Berita ($P = 0.50 > 0.1333$):** $EU(\text{Pintas}) = -5.00 < 6.00 \implies \pi^* = \text{Raya}$ (**Detour Memutar**).

---

### 5. Dampak Fisik Nyata di Dunia Permainan (*Flood Flush*)

1. **Pengukuran Empiris Penalti Waktu ($N = 200$ Percobaan)**:
   - Durasi animasi renang paksa (*swimming animation*): $1.50\text{ s}$.
   - Jarak evakuasi re-walk ke tile kering terdekat (*nearest dry tile*): rata-rata $0.28\text{ s}$.
   - Total keterlambatan fisik nyata terukur: **$1.7783\text{ detik}$ (95% CI: $[1.7647, 1.7918]\text{ s}$)**.
2. **Invariansi Kebijakan Lintas Definisi Segmen**:
   Baik diuji pada **Sub-segmen Lokal** ($\Delta t = 0.36\text{ s}$) maupun **Koridor Penuh Pantai** ($\Delta t = 0.87\text{ s}$), nilai prior $0.10 < f^*$ dan nilai berita $0.50 > f^*$ tetap konsisten 100% memicu pembalikan rute dari Pintas ke Raya.

---

### 6. Sistem Multi-Armed Bandit (MAB 5 Spot)

1. **Dilema Eksplorasi vs Eksploitasi**:
   Pemain memiliki 5 spot memancing dengan parameter Bernoulli tersembunyi $\theta_1, \dots, \theta_5$.
2. **Pembaruan Konjugat Beta-Binomial**:
   Setiap tarikan pancingan dengan hasil reward $r \in \{0, 1\}$ memperbarui posterior secara eksak:
   $$\text{Beta}(\alpha_{\text{baru}}, \beta_{\text{baru}}) = \text{Beta}(\alpha + r, \beta + (1 - r))$$
3. **Algoritma Keputusan**:
   - **Thompson Sampling**: Menarik sampel acak $\hat{\theta}_k \sim \text{Beta}(\alpha_k, \beta_k)$, lalu memilih spot dengan sampel tertinggi.
   - **UCB1 (Upper Confidence Bound)**: Menghitung bound atas optimis:
     $$\text{UCB}_k = \hat{\mu}_k + c \sqrt{\frac{\ln N}{N_k}}$$
     Menjamin batas penyesalan teoritis logaritmik sesuai Teorema Lai-Robbins: $R_T \le C \cdot \ln(T)$.
4. **Jurnal Nelayan (`[B]`)**:
   Pemain dapat membuka antarmuka visual terpadu untuk melihat visualisasi distribusi Beta, total pull, win rate, dan rekomendasi AI.

---

### 7. Kebijakan Risiko Pertempuran Live Combat

Minion goblin hijau berkeliaran secara *live* di daratan pulau dengan mekanisme *respawn* acak:
- **Analisis MEU**:
  Setiap goblin yang dikalahkan menjatuhkan $+3$ s.d. $+8$ koin (rata-rata $+5.5$ koin). Risiko yang dihadapi adalah kerusakan ringan $3\text{ HP}$ per serangan musuh.
- **Kebijakan Ambang Batas HP**:
  - **$\text{HP} \ge 35\%$**: Nilai harapan jarahan koin menguntungkan dan risiko kematian nol $\rightarrow$ **Engage (Lawan Goblin)**.
  - **$\text{HP} < 35\%$**: Risiko terkena serangan mematikan sangat besar $\rightarrow$ **Evade (Menghindar / Detour)** di luar jangkauan deteksi musuh ($220\text{ px}$).

---

### 8. Panduan Tombol Kontrol di Permainan

| Tombol | Fungsi Terkait Decisions Under Uncertainty & MAB |
| :--- | :--- |
| **`[F8]`** | Membuka/menutup **Unified AI Inspector Dock** (Tab Uncertainty & Live Combat Policy). |
| **`[B]`** | Membuka/menutup **Jurnal Nelayan (MAB 5 Spot Analyzer)** modal UI. |
| **`[E]`** | Interaksi dunia: Membaca Papan Pengumuman Cuaca di alun-alun desa / Melempar pancingan. |
| **`[SPACE]` / Klik** | Serangan pedang *live combat* terhadap minion goblin yang mendekat. |
| **`[G]`** | Menampilkan garis lintasan rute $A^*$ (memperlihatkan perubahan rute Pintas $\leftrightarrow$ Raya). |

---

### 9. Perintah Verifikasi & Demo Headless

Jalankan perintah berikut di terminal untuk memverifikasi perhitungan matematis dan simulasi Monte Carlo:

```bash
# 1. Menjalankan CLI demo interaktif (Bayes, Value Iteration, Sensitivitas f*, MAB)
python3 src/decision/demo_cli.py

# 2. Menjalankan benchmark Monte Carlo (10.000 sampel hari cuaca)
python3 tools/simulate_game_loop_20min.py

# 3. Menjalankan unit test khusus UCC & MAB
PYTHONPATH=src python3 -m unittest tests.test_decision_under_uncertainty tests.test_multi_armed_bandit tests.test_putaran3_uncertainty
```
