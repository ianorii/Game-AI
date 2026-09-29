# Hasil Eksperimen Adversarial Search

Benchmark: 600 state acak (seed tetap), 60 duel per kombinasi pada E5 dan E7.

## E0. Analisis horizon & kondisi early stop

| player HP | kedalaman min. agar terminal terlihat |
|---|---|
| 100 | 10 |
| 90 | 8 |
| 80 | 8 |
| 70 | 8 |
| 60 | 6 |
| 50 | 6 |
| 48 | 4 |
| 40 | 4 |
| 35 | 4 |
| 30 | 2 |
| 20 | 2 |
| 10 | 2 |

**Kondisi `is_decided` (dasar early stop):**

| player HP | potion | damage masuk maks | player bisa menghindar | duel diputuskan |
|---|---|---|---|---|
| 100 | 0 | 30 | True | False |
| 100 | 3 | 30 | True | False |
| 60 | 0 | 30 | True | False |
| 60 | 3 | 30 | True | False |
| 40 | 0 | 30 | True | False |
| 40 | 3 | 30 | True | False |
| 30 | 0 | 30 | True | False |
| 30 | 3 | 30 | True | False |
| 25 | 0 | 30 | True | False |
| 25 | 3 | 30 | True | False |
| 20 | 0 | 30 | True | False |
| 20 | 3 | 30 | True | False |
| 15 | 0 | 30 | False | True |
| 15 | 3 | 30 | True | False |
| 10 | 0 | 30 | False | True |
| 10 | 3 | 30 | True | False |

## E1. Minimax vs Alpha-Beta vs Early Stop

| depth | minimax node | alpha-beta node | hemat | early-stop node | hemat | early-stop hit | minimax ms | alpha-beta ms |
|---|---|---|---|---|---|---|---|---|
| 1 | 3.20 | 3.20 | 0.0% | 3.20 | 0.0% | 0.00 | 0.03 | 0.03 |
| 2 | 12.90 | 12.90 | 0.0% | 12.30 | 4.8% | 0.20 | 0.11 | 0.10 |
| 3 | 43.70 | 39.40 | 9.9% | 36.60 | 16.3% | 0.40 | 0.45 | 0.34 |
| 4 | 140.30 | 101.90 | 27.4% | 94.20 | 32.9% | 1.20 | 1.12 | 0.89 |
| 5 | 454.60 | 217.30 | 52.2% | 197.40 | 56.6% | 2.70 | 3.57 | 1.94 |
| 6 | 1455.00 | 494.50 | 66.0% | 449.90 | 69.1% | 7.10 | 12.25 | 4.48 |
| 7 | 4628.70 | 982.10 | 78.8% | 876.00 | 81.1% | 16.60 | 37.05 | 8.57 |

## E2. Perbandingan fungsi evaluasi

| evaluasi | node | eval | ms | % ATTACK | % DEFEND | % POTION | % SPECIAL |
|---|---|---|---|---|---|---|---|
| hp_diff | 111.30 | 75.10 | 0.87 | 43.33 | 5.33 | 41.00 | 10.33 |
| balanced | 101.90 | 68.00 | 0.87 | 61.33 | 3.83 | 24.17 | 10.67 |
| threat_aware | 100.90 | 67.00 | 0.89 | 59.67 | 7.17 | 23.50 | 9.67 |

**Matriks kesamaan keputusan antar fungsi evaluasi (baseline produksi = `balanced`):**

| evaluasi \ lainnya | hp_diff | balanced | threat_aware |
|---|---|---|---|
| hp_diff | 100% | 80% | 78% |
| balanced | 80% | 100% | 93% |
| threat_aware | 78% | 93% | 100% |

## E3. Perbandingan urutan aksi

| urutan | node | cutoff | ms | hemat node | % skor identik | % aksi sama | % beda karena seri | beda nyata |
|---|---|---|---|---|---|---|---|---|
| default | 217.30 | 43.60 | 1.79 | +0.0% | 100.0% | 100.0% | 0.0% | 0 |
| aggressive | 136.50 | 37.90 | 1.26 | +37.2% | 100.0% | 71.8% | 28.2% | 0 |
| defensive | 381.80 | 55.90 | 3.61 | -75.7% | 100.0% | 89.7% | 10.3% | 0 |
| random | 214.80 | 42.50 | 1.93 | +1.1% | 100.0% | 82.7% | 17.3% | 0 |

## E4. Perbandingan kedalaman pencarian

| depth | node (alpha-beta) | ms | sama dgn depth 7 |
|---|---|---|---|
| 1 | 3.20 | 0.03 | 73.5% |
| 2 | 12.90 | 0.11 | 81.8% |
| 3 | 39.40 | 0.31 | 64.5% |
| 4 | 101.90 | 0.93 | 68.8% |
| 5 | 217.30 | 2.09 | 72.5% |
| 6 | 494.50 | 4.45 | 76.3% |
| 7 | 982.10 | 9.10 | 100.0% |

## E5. Perilaku NPC untuk berbagai pendekatan

| opponent | profil NPC | stalemate | menang (decided) | menang (semua) | kalah | %ATK | %DEF | %POT | %SPC |
|---|---|---|---|---|---|---|---|---|---|
| greedy | aggressive | 0.0% | 0.0% | 0.0% | 100.0% | 26.60 | 29.10 | 33.80 | 10.50 |
| greedy | balanced | 0.0% | 5.0% | 5.0% | 95.0% | 42.70 | 1.90 | 42.00 | 13.50 |
| greedy | defensive | 0.0% | 1.7% | 1.7% | 98.3% | 18.90 | 27.20 | 33.00 | 20.90 |
| greedy | opportunist | 0.0% | 0.0% | 0.0% | 100.0% | 27.40 | 15.20 | 35.80 | 21.60 |
| random | aggressive | 0.0% | 75.0% | 75.0% | 25.0% | 55.10 | 13.90 | 20.90 | 10.00 |
| random | balanced | 0.0% | 90.0% | 90.0% | 10.0% | 68.40 | 4.10 | 19.70 | 7.80 |
| random | defensive | 0.0% | 88.3% | 88.3% | 11.7% | 39.70 | 26.30 | 5.40 | 28.60 |
| random | opportunist | 0.0% | 81.7% | 81.7% | 18.3% | 65.00 | 8.10 | 15.80 | 11.00 |
| ai | aggressive | 41.7% | 94.3% | 55.0% | 3.3% | 28.00 | 58.00 | 12.00 | 2.00 |
| ai | balanced | 0.0% | 91.7% | 91.7% | 8.3% | 73.30 | 0.50 | 20.50 | 5.70 |
| ai | defensive | 0.0% | 43.3% | 43.3% | 56.7% | 35.80 | 27.90 | 15.80 | 20.50 |
| ai | opportunist | 1.7% | 100.0% | 98.3% | 0.0% | 59.20 | 7.70 | 18.70 | 14.40 |

## E6. Expectimax

| depth | alpha-beta node | expectimax node | rasio node | alpha-beta ms | expectimax ms | aksi sama |
|---|---|---|---|---|---|---|
| 1 | 3.20 | 8.20 | 2.55 | 0.03 | 0.07 | 96.8% |
| 2 | 12.90 | 68.80 | 5.35 | 0.11 | 0.61 | 96.3% |
| 3 | 39.40 | 525.00 | 13.33 | 0.41 | 4.39 | 91.7% |
| 4 | 101.90 | 3773.80 | 37.03 | 0.98 | 30.52 | 91.7% |

## E7. Branching 3 vs 4 (aksi khusus)

| branching | node | ms | NPC menang | seri | belum selesai | distribusi aksi root |
|---|---|---|---|---|---|---|
| 3 (tanpa SPECIAL) | 46.90 | 0.46 | 40.0% | 0.0% | 60.0% | ATTACK 81.2% DEFEND 2.2% POTION 16.7% SPECIAL 0.0% |
| 4 (produksi) | 101.90 | 0.98 | 93.3% | 0.0% | 6.7% | ATTACK 61.3% DEFEND 3.8% POTION 24.2% SPECIAL 10.7% |

