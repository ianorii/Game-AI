# Hasil eksperimen (`experiments/run_all.py --quick`, seed tetap)

 mentah: `data/results/*.csv`. Full (100 seed) memakai skrip sama
 (`--full`); kualitatif konsisten (lihat catatan tiap tabel).

## 1. Ablasi CSP (nodes mean, 10 seed; lengkap di `csp_ablasi.csv`)

| Target/skenario | tetap | acak | +MRV | +MRV/deg | +LCV | +FC/+AC-3 |
|---|---|---|---|---|---|---|
| 0.5 normal | 9 | 15 | 12 | 12 | 11 | 12 |
| 0.5 wins9 | 9 | 13 | 13 | 13 | 16 | 22 |
| 0.3 normal | 9 | 36 | 23 | 23 | 23 | 12 |

**Interpretasi jujur**: urutan tetap kebetulan menang di instans mudah;
baseline ACAK yang adil selalu terburuk (efek ekor p90 hanya terlihat
jelas di full 100-seed; jalankan `--full` untuk mereproduksi). FC ≡ AC-3
di constraint set ini (propagasi cukup kedalaman-1; AC-3 jaring pengaman).
Solved 100% di semua sel.

## 2. Perbandingan LS (gap mean, 5 seed × 3 target × 3 loadout)

| Mode | HC polos | HC+side | Restart | SA | GA |
|---|---|---|---|---|---|
| BEST gap/eval/ms | 0.041/45/100 | 0.041/250/204 | **0.031**/965/663 | 0.030/141/472 | 0.063/29/42 |
| RANDOM gap/eval/ms | 0.039/52/134 | 0.039/268/216 | 0.031/965/587 | 0.030/143/590 | 0.063/29/51 |
| tol tercapai | 33% | 33% | 33% | 33% | 33% |

SA menerima rata-rata **16 langkah buruk** (anil terbukti). Restart
termurah-hasil-terbaik termahal; GA termurah (setelan demo 8×5) tapi
terburuk. tol 33% seragam di semua algoritma = **batas keterjangkauan**,
bukan kelemahan algoritma (target di luar wilayah tak bisa dicapai
siapa pun; overlay melabelinya jujur).

## 3. Fidelitas (dari `data/fidelity.json`)

Lemah 0.95/0.70/0.056 · sedang 0.54/0.58/0.19 · kuat 0.68/0.68/0.22
(Pearson/Spearman/RMSE). Status partial; ambang 0.85/0.80 tetap.

## 4. Autoplay + lintasan adaptif

| Policy | menang% | progres | MAE ringan/penuh |
|---|---|---|---|
| greedy | 0–3 | 0.50 | 0.02/0.05 |
| hemat | 3–10 | 0.51–0.55 | 0.02/0.05 |
| depth4 | 0 | 0.45–0.50 | 0.05/0.05 |

MAE kecil sebagian karena kuantisasi (prediksi menumpuk di target) —
yang diukur adalah **konsistensi** sim-vs-autoplay se-kebijakan, bukan
keakuratan lawan manusia. Target adaptif: 0.5 → ~0.4 dalam 2–3 pertemuan
kalah, pulih ke ~0.57 setelah menang beruntun (tak hanyut permanen).
