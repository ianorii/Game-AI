# Perbandingan Fundamental: Plan (Rencana Statis) vs Policy (Kebijakan Kontingensi)

Dokumen ini menjelaskan perbedaan konseptual dan komputasi antara **Plan** (rencana sekuensial deterministik, seperti STRIPS/HTN) dan **Policy** (kebijakan kondisional Markov Decision Process), mengacu pada Slide 12 materi *Decisions Under Uncertainty*.

---

## 1. Definisi & Paradigma

| Dimensi | Plan (Perencanaan Klasik / Deterministic) | Policy (Markov Decision Process / Uncertainty) |
| :--- | :--- | :--- |
| **Bentuk Output** | Barisan aksi linier tetap: $[a_1, a_2, a_3, \dots, a_n]$ | Fungsi pemetaan universal: $\pi: S \rightarrow A$ |
| **Asumsi Lingkungan** | Deterministik, statis, prediktabil penuh ($P(s' \mid s, a) = 1.0$) | Stokastik, berisiko, non-deterministik ($P(s' \mid s, a) \in [0, 1]$) |
| **Karakteristik Eksekusi** | "Buka mata sekali saat merencana, lalu pejamkan mata saat jalan" | Responsif di setiap langkah: aksi dipilih berdasarkan status $s$ saat ini |
| **Kelemahan Utama** | Rentan gagal total jika terjadi transisi tak terduga (*unexpected outcome*) atau parameter risiko lingkungan berubah | Biaya komputasi lebih tinggi untuk memetakan seluruh ruang status |

---

## 2. Studi Kasus: Menuju Kampus Saat Ancaman Banjir

Model perjalanan dari **Rumah** menuju **Kampus** memiliki dua opsi di persimpangan **Warung**:
1. **Jalan Pintas**: Cepat (+10 jika sukses), namun berisiko terperangkap banjir (-20) dengan probabilitas $f$.
2. **Jalan Raya**: Aman dan pasti (bebas banjir), namun memakan waktu lebih lama (+6 utilitas bersih).

### Skenario 1: Hari Biasa (Risiko Rendah, $f = 0.1$)
- **Plan Klasik (STRIPS)**:
  $$\text{Plan} = [\text{Jalan(Rumah, Warung)}, \text{Pintas(Warung, Kampus)}]$$
  Rencana ini berasumsi jalan pintas akan selalu membawa agen ke Kampus.
- **Policy MDP ($\pi$)**:
  - $\pi(\text{Rumah}) = \text{Jalan}$
  - $\pi(\text{Warung}) = \text{Pintas}$  *(karena $Q(\text{Warung}, \text{Pintas}) = 7.0 > Q(\text{Warung}, \text{Raya}) = 6.0$)*
  - $\pi(\text{Jalan Raya}) = \text{Jalan}$

### Skenario 2: Terjadi Perubahan Dinamis ($f$ naik menjadi $0.25$ akibat Berita Cuaca)
- **Kegagalan Plan Klasik**:
  Rencana tetap $[\text{Jalan}, \text{Pintas}]$ **tidak memiliki mekanisme internal untuk beradaptasi**. Karena rencana hanya berupa daftar langkah, agen akan tetap memaksakan melewati jalan pintas meskipun risiko banjir telah membengkak menjadi $25\%$. Akibatnya, nilai harapan anjlok drastis menjadi $2.5$ (jauh lebih buruk daripada jalur aman bernilai $6.0$). Agen tidak tahu cara bereaksi kecuali eksekusi telah benar-benar gagal dan memicu proses replanning dari awal.
- **Keunggulan Policy ($\pi$)**:
  Begitu parameter lingkungan $f$ diperbarui ($f = 0.25$), fungsi `value_iteration` atau evaluasi Bellman langsung memperbarui nilai $Q$:
  $$Q(\text{Warung}, \text{Pintas}) = 0.75(10) + 0.25(-20) = 2.5$$
  $$Q(\text{Warung}, \text{Raya}) = -2 + 0.8(10) = 6.0$$
  Kebijakan baru otomatis ter-ekstrak:
  $$\pi(\text{Warung}) = \text{Raya}$$
  Agen secara cerdas mengubah aksinya di Warung untuk berbelok ke **Jalan Raya** tanpa mengalami kegagalan terlebih dahulu.

---

## 3. Ketahanan Terhadap Transisi Stokastik (Outcome Tak Terduga)

Jika saat mengambil aksi `Pintas`, agen ternyata benar-benar mendarat di status tak terduga **Banjir**:
- **Plan**: Rencana linier langsung pecah (*broken plan*), karena prakondisi langkah berikutnya tidak terpenuhi.
- **Policy**: Karena $\pi$ memetakan seluruh ruang status $S$, agen sudah memiliki strategi respons untuk setiap status yang mungkin dicapai.

---

## 4. Kesimpulan Implementasi

Fungsi `extract_policy(mdp, V)` pada `src/decision/mdp.py` mengekstrak aturan keputusan optimal untuk setiap keadaan:
$$\pi^*(s) = \arg\max_{a \in A(s)} \sum_{s'} P(s' \mid s, a) [ R(s') + \gamma V^*(s') ]$$
Hal ini memberikan agen ketahanan penuh terhadap ketidakpastian (*robustness under uncertainty*), yang menjadi dasar pengambilan keputusan otonom dalam game modern.

---

## 5. Analisis Sensitivitas & Pencarian Bisection $f^*$ (Ekstensi di Luar Slide)

> [!NOTE]
> Label *(Slide 22)* pada materi kuliah merujuk pada diagram konvergensi Value Iteration kasus khusus $f = 0.25$. Analisis sensitivitas probabilitas banjir $f \in [0, 1]$ dan penentuan titik belok analitik $f^* = \frac{4}{30} = \frac{2}{15} \approx 0.133333$ merupakan **ekstensi analitik & numerik** untuk melengkapi studi kasus.

### Kriteria Berhenti Algoritma Bisection (`find_f_star_bisection`)
Fungsi `find_f_star_bisection(f_min=0.0, f_max=0.5, tol=1e-6, max_iter=100)` menggunakan dua kriteria terminasi yang ketat:
1. **Lebar Interval (Bracket Width)**: $\frac{f_{\max} - f_{\min}}{2} \le \text{tol}$.
   - Dari interval awal $[0.0, 0.5]$, lebar interval menyusut dengan faktor $2^{-k}$ pada iterasi ke-$k$.
   - Pada iterasi ke-18: $\frac{0.5}{2^{18}} \approx 1.907 \times 10^{-6}$.
   - Pada iterasi ke-19: $\frac{0.5}{2^{19}} \approx 9.537 \times 10^{-7} \le 10^{-6}$.
   - Dengan demikian, batas galat mutlak $|f - f^*| \le 10^{-6}$ dijamin tercapai secara matematis dalam 18–19 iterasi.
2. **Toleransi Fungsi (Residual / Function Tolerance)**: $|\text{diff}| < \text{tol}$, di mana $\text{diff} = Q(\text{Warung}, \text{Pintas}) - Q(\text{Warung}, \text{Raya}) = 4 - 30f$.
   - Jika residu selisih nilai $Q$ sudah berada di bawah ambang batas $10^{-6}$, algoritma dapat berhenti seketika (*early exit*) dengan solusi numerik valid.


