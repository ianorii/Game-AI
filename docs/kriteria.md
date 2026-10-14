# Pemetaan kriteria dosen → bukti (Tahap 3: duel berurutan)

Legenda bukti: kode `file:fungsi`, tes `tests/test_*.py::test_*`,
gambar `docs/screens/*.png`, data `data/*.csv`, laporan `docs/hasil.md`.

## a. Konfigurasi NPC sebelum menyerang (jumlah + karakter + item)

| Dituntut | Bukti |
|---|---|
| Jumlah & karakter NPC + item | `game/ambush/enemy_queue.py`: `EnemySlot(role, item)`, `EnemyQueue` (k = 2..4); peran Warrior/Archer/Mage/Healer/Tank/Boss/Minion + 5 item di `game/ambush/types.py` |
| Disusun SEBELUM menyerang | State machine `PREP_PLAYER → PREP_NPC_CSP → PREP_NPC_LS → PREP_REVIEW` (`game/ambush/flow/prep_state_machine.py`), duel baru mulai setelah Enter |
| Terlihat | `docs/screens/fase-review-f3.png` (tabel antrean + biaya/budget) |

## b. Tidak terlalu mudah / sulit (target + adaptif)

| Dituntut | Bukti |
|---|---|
| Target progres | Objective `1 − E[duel_menang/k]` (`chain_eval.py`); label overlay "target 0.50 (menang ~separuh duel)" |
| Difficulty adaptif | `governor.py:update()` memakai progres (kalah tipis menurunkan sedikit); menang-terus plateau di plafon 0.80, kalah-terus di lantai 0.40 (40 pertemuan, sintetis + rantai autoplay) |

## c. CSP (X, D, C, algoritma, complete + consistent)

| Dituntut | Bukti |
|---|---|
| X eksplisit | `ROLE_1..4`, `ITEM_1..4` (`constraints.py:variable_names`) |
| D (boleh beda per slot) | `build_domains`: BUFF: Boss hanya slot 1 (lead); SEQUENTIAL: Boss di slot AKTIF terakhir; Minion hanya SEQUENTIAL |
| C unary | Boss butuh wins; ROLE NONE ⇒ ITEM NONE |
| C binary | Maks 1 Healer; matriks kompatibilitas; canonical tanpa-lubang; Boss-terakhir; larangan Healer/Tank berturutan |
| C global | AllDifferent item (pairwise `!=` di `pair_ok`); budget; min-2 aktif |
| Backtracking | `csp_solver.py:_bt` (assign → inferensi → rekursi → restore) |
| MRV + degree | `_select` (tie-break degree lalu urutan tetap) |
| LCV | `_order` (NONE selalu terakhir, by-design agar seed ber-item) |
| AC-3 (+FC pembanding) | `_ac3`/`_revise` + `_fc`; toggle `R`; skenario hapus-Healer/Boss terbukti di tes |
| Complete + consistent | Dicek tiap assign; `complete + consistent OK` di overlay; tes multi-seed |

## d. Local search

| Dituntut | Bukti |
|---|---|
| Hill climbing + sideways | `queue_search.py:hill_climb_q` (steepest, `hc_sideways=10`) |
| Random restart | `random_restart_q` (seed CSP diacak + dedup) |
| Simulated annealing | `simulated_annealing_q` (`e^(deltaE/T)`, cooling 0.995, `accepted_bad` tercatat) |
| Genetic algorithm | `genetic_q`; encoding per-slot berurutan; crossover single-point antar-slot valid karena memindahkan blok anggota utuh (koherensi role–item + urutan tak disobek); penalti default, repair deterministik (opsi) |
| Neighbour dicek constraint | `neighbours()` + alasan penolakan tercatat (`tolak_CSP`) |

## e. Gabungan CSP + LS

| Dituntut | Bukti |
|---|---|
| Seed dari CSP | `director.py:plan_queue/run_gen_queue` (seed terbaik = gameplay, pertama = demo) |
| Neighbour valid | Fuzz 500 bersih (`test_neighbours_fuzz_valid`) |
| LS dilewati bila pas | Pesan "LS dilewati: seed sudah dalam toleransi (gap X <= Y)" |

## f. Debug overlay angka-angka

Isi (semua dari trace yang sama dengan CSV — ada tesnya): header fase/algo/pump/seed-mode/target/kalibrasi/plafon; LOG KEJADIAN 6 baris (✓/X, contoh di `docs/ambush.md`); CSP (nodes/backtrack/prune/ms, var+alasan, domain sebelum→sesudah, LCV, AC-3 queue/arc/hapus, pra-AC-3); LS (iter/cur/best, sideways, restart, SA T/dE/p/u + langkah-buruk, GA fit, penolakan + alasan, alasan berhenti); sebelum-vs-sesudah + sparkline + garis target; ringan/sim + selisih + label jujur (+ label plafon bila target > 0.80); per-posisi; perbandingan bertahap; kontrol per fase. Tombol: F3 T TAB F4 Spasi C X G Enter H. Bukti visual: `docs/screens/fase-*.png` (7 file).

## g. Kompetensi slide (satu baris + bukti)

| Kompetensi | Bukti |
|---|---|
| Path vs konfigurasi | A* mencari JALUR (`game/pathfinding/`), CSP/LS mencari KONFIGURASI (tim) — dua masalah, dua mesin (`docs/ambush.md` §1) |
| Failure mode | Local maximum/plateau (alasan berhenti tercatat), CSP unsatisfiable (fallback + tes HYBRID), saturasi label 62% (dilaporkan, bukan disembunyikan) |
| Encoding GA | Kromosom per-slot berurutan; crossover valid (blok utuh); penalti vs repair dijelaskan di komentar `queue_search.py` |
| Biaya satuan sama | Ablasi CSP = nodes/backtrack/ms; banding LS = gap/eval/ms (`data/results/`) |
| Kapan CSP vs LS cocok | Eksperimen CAL: seed dekat target → CSP cukup; jauh → LS perlu (`experiments/ambush_exp.py`, `docs/hasil.md`) |

## Yang sebagian / belum (jujur)

1. **Per-posisi p_win** butuh prefilter heuristik terkalibrasi; tanpanya overlay menampilkan HP-masuk sim saja (dilabeli). Penyebab: kalibrasi heuristik partial (di bawah).
2. **Kalibrasi heuristik partial** (Pearson 0.54–0.64 < 0.85): heuristik turun jadi pra-penyaring; objektif = sim ringan. Status tampil di overlay.
3. **Target 0.3 tak dibuka** (3–12% sampel, tertinggi 11.7% via loadout lemah
   < syarat 10% pada sedang): `gov_min=0.40`, siklus C 0.40/0.50/0.80/ADAPTIF;
   label jujur bila di luar jangkauan.
4. **Plafon Director ~0.75–0.81** (terukur, bukan teori): 0.80 vs 0.95 identik
   dalam noise; governor di-cap `governor_max_target=0.80` + label
   "target di atas plafon, antrean tersulit: {urutan}". Opsi Boss & jalur
   tersulit diuji-ditolak dengan data (`docs/balance_TahapA.md`).
5. **Kriteria clear direvisi** (disetujui): tidak jenuh (<90% @0.50),
   ≥10% antrean gagal per loadout, Director membedakan target.
   Alasan: clear bergantung kebijakan + se ~0.14 pada N kecil.
6. **Balance freeze** (`docs/balance.md` + tes penegak
   `test_balance_freeze`): tak ada tuning kecuali bug nyata / uji main manual.
7. **Tab ALL di 720p** masih memotong daftar panjang (kontrol + sparkline disematkan; detail di tab CSP/LS/CMP).
8. Validasi lawan manusia belum ada (MAE terhadap pemain simulasi saja).
