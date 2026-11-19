# PANDUAN & LAPORAN RESMI: KEPUTUSAN DI BAWAH KETIDAKPASTIAN
## Multi-Armed Bandit (MAB 5 Spot Nelayan) & Kebijakan Risiko Live Combat — Sunnyside Isle

---

### 1. Ringkasan Eksekutif & Fokus Tunggal Implementasi

Modul **Decisions Under Uncertainty (DUU / UCC)** pada game *AI Labyrinth: Sunnyside Isle* difokuskan secara penuh pada satu titik implementasi inti yang nyata dan terpadu di dunia game: **Sistem Multi-Armed Bandit (MAB) 5 Spot Pemancingan**, yang disinergikan dengan **Kebijakan Risiko Pertempuran Live Combat (MEU)**.

Seluruh konsep teoretis keputusan stokastik diwujudkan ke dalam interaksi gameplay nyata:
1. **Dilema Eksplorasi vs Eksploitasi (*Exploration vs Exploitation*)**: Agen dan pemain dihadapkan pada ketidakpastian sejati mengenai tingkat keberhasilan tangkapan ikan di 5 titik perairan pulau.
2. **Pembaruan Konjugat Bayesian Eksak (Beta-Binomial)**: Keyakinan stokastik diperbarui secara kontinu berdasarkan bukti observasi tarikan umpan.
3. **Algoritma Keputusan Stokastik**: Implementasi algoritma pemenang penghargaan *Thompson Sampling* dan *UCB1 (Upper Confidence Bound)*.
4. **Jaminan Batas Penyesalan (*Regret Bound*) Optimal**: Pembuktian empiris batas penyesalan logaritmik Teorema Lai-Robbins: $R_T \le C \cdot \ln(T)$.
5. **Kebijakan Risiko Live Combat (MEU)**: Evaluasi Utilitas Harapan Maksimum (*Maximum Expected Utility*) saat berhadapan dengan minion goblin berkeliaran bebas dengan batas ambang keselamatan $\text{HP} \ge 35\%$.
6. **Antarmuka Visual Interaktif**: Modal terpadu **Jurnal Nelayan (`[B]`)** dan panel **Dock Inspector F8 (`[F8]`)**.

---

### 2. Arsitektur Modul & Struktur Berkas

```text
src/decision/
├── bandit.py           # Multi-Armed Bandit: Bernoulli arms, Thompson Sampling, UCB1, Regret Tracker
├── bandit_ui.py        # UI Modal Jurnal Nelayan & MAB Analyzer (Tombol [B])
├── probability.py      # Fungsi inti EV, EU, MEU, dan pembaruan Bayesian
└── __init__.py

src/combat_config.py    # Konfigurasi parameter live combat, hitbox, damage, dan HP player
src/entities/goblin.py  # AI minion goblin hijau berkeliaran bebas dengan respawn acak
src/planning/planner_ui.py # Dock Inspector F8: Visualisasi metrik MAB, kebijakan HP, & batas Lai-Robbins
```

---

### 3. Formulasi Teoretis Multi-Armed Bandit (MAB)

#### 3.1 Ruang Lengan ($K = 5$ Spot Pancingan)
Pulau Sunnyside memiliki 5 titik pemancingan alami dengan parameter peluang keberhasilan Bernoulli rahasia ($\theta_k \in (0, 1)$):
1. **Spot 1: Muara Sungai** ($\theta_1$) — Dekat jembatan desa.
2. **Spot 2: Dermaga Barat** ($\theta_2$) — Pesisir pantai barat.
3. **Spot 3: Dermaga Timur** ($\theta_3$) — Dekat gerbang kuno pantai timur.
4. **Spot 4: Tebing Pesisir** ($\theta_4$) — Area karang selatan.
5. **Spot 5: Danau Pedalaman** ($\theta_5$) — Perairan tenang tengah pulau.

Pemain dan agen AI pada awalnya **tidak mengetahui** nilai $\theta$ dari masing-masing spot.

#### 3.2 Pembaruan Keyakinan Bayesian Konjugat Beta-Binomial
Setiap kali umpan dilempar ke spot $k$, diperoleh hasil biner stokastik $r \in \{0, 1\}$ (0: gagal/zonk, 1: berhasil menangkap ikan berharga).

Dengan memilih distribusi prior konjugat $\text{Beta}(\alpha_0, \beta_0) = \text{Beta}(1, 1)$ (distribusi seragam / uninformative prior), fungsi kepekatan posterior diperbarui secara eksak:
$$\text{Beta}(\alpha_k^{\text{baru}}, \beta_k^{\text{baru}}) = \text{Beta}(\alpha_k + r, \beta_k + (1 - r))$$

Nilai ekspektasi keberhasilan (mean posterior) spot $k$ setelah $N_k = (\alpha_k + \beta_k - 2)$ tarikan adalah:
$$\mathbb{E}[\theta_k] = \hat{\mu}_k = \frac{\alpha_k}{\alpha_k + \beta_k}$$

#### 3.3 Algoritma Pengambilan Keputusan

##### A. Thompson Sampling (Bayesian Posterior Sampling)
Pada setiap keputusan memancing:
1. Tarik sampel acak dari distribusi posterior masing-masing lengan:
   $$\hat{\theta}_k \sim \text{Beta}(\alpha_k, \beta_k), \quad \forall k \in \{1, \dots, 5\}$$
2. Pilih spot dengan nilai sampel tertinggi:
   $$k^* = \arg\max_{k} \hat{\theta}_k$$
- **Sifat Alami**: Lengan dengan ketidakpastian tinggi (varians besar / sedikit tarikan) memiliki ekor distribusi yang lebar sehingga berpeluang terpilih untuk dieksplorasi. Saat data semakin banyak, distribusi menyempit di sekitar nilai riil dan algoritma otomatis beralih ke eksploitasi lengan terbaik.

##### B. UCB1 (Upper Confidence Bound)
Menerapkan prinsip optimisme dalam menghadapi ketidakpastian (*Optimism in the Face of Uncertainty*):
$$\text{UCB}_k = \hat{\mu}_k + c \sqrt{\frac{\ln N}{N_k}}$$
- $\hat{\mu}_k$: Rata-rata empiris hasil tangkapan spot $k$.
- $N$: Total seluruh tarikan pancingan di seluruh spot.
- $N_k$: Jumlah tarikan pada spot $k$.
- $c$: Konstanta eksplorasi (standar $c = \sqrt{2}$).

##### C. Teorema Batas Penyesalan Lai-Robbins
Penyesalan kumulatif (*cumulative regret*) $R_T$ didefinisikan sebagai selisih hasil jika selalu memilih spot terbaik ($\theta^* = \max_k \theta_k$):
$$R_T = T \cdot \theta^* - \sum_{t=1}^T \mathbb{E}[r_t]$$

Teorema Lai-Robbins (1985) menetapkan batas bawah teoritis penyesalan asimtotik:
$$\liminf_{T \to \infty} \frac{R_T}{\ln T} \ge \sum_{k: \Delta_k > 0} \frac{\Delta_k}{\text{KL}(\theta_k \parallel \theta^*)}$$

Implementasi UCB1 dan Thompson Sampling pada Sunnyside Isle menjamin penyesalan sub-linear $R_T = O(\ln T)$, membuktikan bahwa agen AI tidak membuang-buang umpan secara sia-sia.

---

### 4. Kebijakan Risiko Pertempuran Live Combat (MEU)

Di daratan pulau, minion goblin hijau berkeliaran bebas secara *live* dan muncul kembali (*respawn*) secara acak:

#### 4.1 Formulasi Expected Utility (MEU)
- **Ekspektasi Jarahan**: Mengalahkan goblin menghasilkan $+3$ hingga $+8$ koin (rata-rata $\mathbb{E}[\text{Loot}] = +5.5\text{ Koin}$).
- **Ekspektasi Kerusakan**: Serangan goblin menimbulkan damage kecil $3\text{ HP}$ per serangan.

#### 4.2 Ambang Batas Keamanan Keputusan
Evaluasi keputusan berbasis Maximum Expected Utility (MEU):
$$\text{Kebijakan}(\text{HP}) = \begin{cases} 
\textbf{ENGAGE} \ (\text{Serang \& Kumpulkan Modal}), & \text{jika } \text{HP} \ge 35\% \\ 
\textbf{EVADE} \ (\text{Menghindar \& Ambil Detour}), & \text{jika } \text{HP} < 35\% 
\end{cases}$$

- **HP $\ge 35\%$**: Hero berada dalam kondisi aman. Nilai harapan koin positif jauh melampaui risiko kerusakan ringan, sehingga rekomendasi keputusan adalah bertarung (*Engage*).
- **HP $< 35\%$**: Risiko terkena serangan beruntun dinilai fatal. Utilitas bertahan hidup memicu tindakan preventif (*Evade*) dengan mengambil rute memutar di luar radius kejar goblin ($220\text{ px}$).

---

### 5. Antarmuka Visual & Integrasi Gameplay

| Fitur | Tombol / Cara Akses | Tampilan & Fungsi |
| :--- | :---: | :--- |
| **Jurnal Nelayan & MAB Analyzer** | **`[B]`** | Modal visual interaktif menampilkan grafik kurva Beta, statistik tarikan per spot, *win rate*, dan rekomendasi spot terbaik. |
| **Unified Inspector Dock (F8)** | **`[F8]`** | Menampilkan Card 1 (Metrik MAB & Regret Bound), Card 2 (Kebijakan Risiko Live Combat & Status Goblin), dan Card 3 (Formulasi Stokastik UCB1/MEU). |
| **Memancing di Bibir Air** | **`[E]`** | Melempar umpan di dekat salah satu dari 5 spot pemancingan. |
| **Serangan Live Combat** | **`[SPACE]` / Klik** | Menebas minion goblin secara langsung di peta dengan animasi *slash arc* dan *hit spark*. |

---

### 6. Perintah Verifikasi & Demo Headless

Jalankan pengujian unit test dan simulasi empiris Multi-Armed Bandit langsung dari terminal:

```bash
# 1. Menjalankan unit test lengkap MAB (Thompson Sampling, UCB1, Lai-Robbins)
PYTHONPATH=src python3 -m unittest tests.test_multi_armed_bandit

# 2. Menjalankan unit test visualisasi F8 Inspector & MAB Dock
PYTHONPATH=src python3 -m unittest tests.test_debug_overlay
```
