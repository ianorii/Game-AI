# PANDUAN RESMI: KEPUTUSAN DI BAWAH KETIDAKPASTIAN (DECISIONS UNDER UNCERTAINTY)
## Jaringan Keputusan, Klasifikasi Bayesian Tipe Musuh, & Kebijakan Risiko Live Combat MEU — Sunnyside Isle

---

### 1. Ringkasan Eksekutif & Fokus Tunggal Implementasi

Modul **Decisions Under Uncertainty (DUU)** pada game *AI Labyrinth: Sunnyside Isle* difokuskan secara penuh pada satu titik implementasi inti yang nyata dan terpadu di dunia game: **Sistem Pengambilan Keputusan Taktis Pertempuran Menghadapi Minion Goblin Liar Real-Time**.

Seluruh konsep teoretis keputusan probabilistik diwujudkan ke dalam interaksi gameplay nyata:
1. **Jaringan Keputusan (*Decision Network*)**: Memodelkan simpul peluang (*chance node*) tipe goblin $T \in \{\text{NORMAL}, \text{ELITE}\}$ dan utilitas hasil pertempuran.
2. **Pembaruan Keyakinan Bayesian (*Bayesian Belief Updating*)**: Memperbarui keyakinan secara real-time dari prior $P(\text{ELITE}) = 0,20$ menjadi posterior berbasis bukti pertukaran damage serangan awal musuh.
3. **Model Probabilitas Kemenangan Kontinu ($P(\text{win})$)**: Fungsi sigmoid kontinu berbasis sisa HP hero, sisa HP goblin, dan jumlah goblin musuh, memungkinkan aksi penuntasan (*finishing blow*) pada goblin sekarat.
4. **Evaluasi Maximum Expected Utility (MEU)**: Memilih tindakan optimal $\arg\max_{a} EU(a)$ dari tiga alternatif: $\text{ENGAGE}$, $\text{EVADE}$, dan $\text{HEAL}$.
5. **Derivasi Titik Impas Analitik**: Penurunan formal $P^*(\text{win}) = 72,55\% \iff \text{HP}^* = 35,0\%$ untuk goblin normal.
6. **Mekanisme Histeresis 10%**: Mencegah *flickering* perilaku bolak-balik saat HP berfluktuasi di sekitar 35% (decommit ke Evade hanya jika $\text{HP} < 25\%$).
7. **Antarmuka Visual Terpadu**: Panel **Unified AI Inspector Dock F8 (`[F8]`)**.

---

### 2. Arsitektur Modul & Struktur Berkas

```text
src/decision/
├── combat_policy.py    # Inti DUU: Decision Network, BayesianMinionBelief, MEU, Histeresis
├── probability.py      # Fungsi matematis probabilitas, utilitas harapan, dan aturan Bayes
└── __init__.py

src/entities/goblin.py  # AI minion goblin hijau berkeliaran bebas dengan respawn acak
src/combat_config.py    # Konfigurasi parameter stat tempur, hitbox, damage, dan HP player
src/planning/planner_ui.py # Dock Inspector F8: Visualisasi metrik DUU, inferensi Bayes, & MEU
```

---

### 3. Formulasi Teoretis & Jaringan Keputusan

#### 3.1 Klasifikasi Bayesian Tipe Musuh
- **Prior Awal**: $P(\text{ELITE}) = 0,20$ dan $P(\text{NORMAL}) = 0,80$.
- **Bukti Observasi ($E$)**: Hero mengamati damage yang diterima dari pertukaran serangan pertama:
  - $P(\text{HighDamage} \mid \text{ELITE}) = 0,70, \quad P(\text{HighDamage} \mid \text{NORMAL}) = 0,20$
  - $P(\text{LowDamage} \mid \text{ELITE}) = 0,30, \quad P(\text{LowDamage} \mid \text{NORMAL}) = 0,80$
- **Pembaruan Posterior**:
  $$P(\text{ELITE} \mid E) = \frac{P(E \mid \text{ELITE}) P(\text{ELITE})}{P(E \mid \text{ELITE}) P(\text{ELITE}) + P(E \mid \text{NORMAL}) P(\text{NORMAL})}$$
  Saat menerima damage tinggi, keyakinan melonjak menjadi $\approx 0,4667$ (46,67%).

#### 3.2 Probabilitas Kemenangan Prediktif
$$P(\text{win}) = (1 - P(\text{ELITE} \mid E)) \cdot P(\text{win} \mid \text{NORMAL}) + P(\text{ELITE} \mid E) \cdot P(\text{win} \mid \text{ELITE})$$
dengan fungsi sigmoid:
$$P(\text{win} \mid \text{HP}_{\text{hero}}, \text{HP}_{\text{goblin}}, n, T) = \frac{1}{1 + \exp\left(-\frac{\text{HP}_{\text{hero}} - \text{center}(\text{HP}_{\text{goblin}}, n, T)}{\text{scale}}\right)}$$
Jika goblin sekarat ($\text{HP}_{\text{goblin}} \le 0,33$), titik tengah bergeser drastis sehingga $P(\text{win}) \ge 0,75$ meskipun HP hero di bawah 35%.

#### 3.3 Evaluasi Utilitas Harapan (MEU)
- Ruang Aksi: $A = \{\text{ENGAGE}, \text{EVADE}, \text{HEAL}\}$
- Nilai Utilitas:
  - $U(\text{loot}) = (1 - P(\text{ELITE})) \cdot 5,5 + P(\text{ELITE}) \cdot 12,0$ koin
  - $U(\text{death}) = -20,0$ koin
  - $U(\text{evade}) = -1,5$ koin (peluang tertangkap $c = 0$ karena kecepatan hero $147,2 >$ kecepatan goblin $90,0$)
  - $U(\text{potion}) = -3,0$ koin
- Formulasi EU:
  $$EU(\text{ENGAGE}) = P(\text{win}) \cdot U(\text{loot}) + (1 - P(\text{win})) \cdot U(\text{death})$$
  $$EU(\text{EVADE}) = -1,5$$
  $$EU(\text{HEAL}) = EU(\text{ENGAGE} \mid \min(1,0, \text{HP} + 0,50)) - 3,0$$

#### 3.4 Derivasi Titik Impas Analitik & Histeresis
$$EU(\text{ENGAGE}) = EU(\text{EVADE}) \implies P^*(\text{win}) \cdot 5,5 + (1 - P^*(\text{win})) \cdot (-20,0) = -1,5$$
$$25,5 \cdot P^*(\text{win}) = 18,5 \implies P^*(\text{win}) = \frac{18,5}{25,5} \approx 72,55\% \iff \text{HP}^* = 35,0\%$$
- **Histeresis 10%**:
  Saat sudah bertarung, hero tetap berkomitmen selama $\text{HP} \ge 25,0\%$ ($\text{HP}^* - 0,10$). Hero hanya kabur (*Evade*) jika HP jatuh ke $< 25,0\%$.

#### 3.5 Parameter Pengejaran & Spawn Acak Minion
- **Jarak Deteksi (*Chase Radius*)**: $240,0\text{ px}$ (~7,5 tile). Hero yang masuk ke dalam radius ini langsung dikejar oleh goblin dengan kecepatan agresif $90,0\text{ px/s}$.
- **Jarak Pelepasan (*Deleash Radius*)**: $360,0\text{ px}$ (~11,25 tile). Goblin melepaskan pengejaran jika jarak melebihi batas ini.
- **Jarak Serang (*Attack Range*)**: $36,0\text{ px}$ (~1,1 tile) untuk mengaktifkan animasi serangan dan damage knockback.
- **Mekanisme Spawn & Respawn**: 7 zona spawn luar desa, pemilihan lokasi acak berjarak $\ge 300\text{ px}$ dari hero, dan jitter koordinat acak $\pm 32\text{ px}$.

---

### 4. Antarmuka Visual & Integrasi Gameplay

| Fitur | Tombol / Cara Akses | Tampilan & Fungsi |
| :--- | :---: | :--- |
| **Unified Inspector Dock (F8)** | **`[F8]`** | Menampilkan Card 1 (Inferensi Bayes Tipe Musuh), Card 2 (Evaluasi MEU Tiga Aksi: Engage/Evade/Heal), dan Card 3 (Formulasi Matematika DUU). |
| **Advisor Mode Banner** | **`[F7]`** | Menampilkan saran langkah strategis dari perencana otomatis STRIPS di atas layar. |
| **Autopilot Mode Toggle** | **`[TAB]`** | Mengalihkan kendali penuh antara Player (Manual) dan AI (Autopilot). |
| **Serangan Live Combat** | **`[SPACE]` / Klik** | Menebas minion goblin secara langsung di peta dengan animasi *slash arc* dan *hit spark*. |

---

### 5. Perintah Pengujian Mandiri

Jalankan pengujian unit test DUU Minion langsung dari terminal:

```bash
# Menjalankan unit test lengkap DUU Minion (Oracle T-A1 s.d. T-A7, State Machine T-B1 s.d. T-B9, dan Chase Range)
PYTHONPATH=src python3 -m unittest tests.test_minion_duu tests.test_goblin_chase tests.test_plan_validator
```
