# Game AI — Ambush Director (CSP + Local Search, duel berurutan)

Game 2D Python/pygame tugas besar Kecerdasan Buatan: Tahap 1 (A*),
Tahap 2 (duel 1v1 adversarial search), Tahap 3 (dokumen ini).

## Konsep: sutradara sebelum duel (analogi)

Bayangkan sutradara film laga: sebelum aktor berkelahi, ia memilih
pemeran pengganti (jumlah, karakter, senjata) yang **pas** — tidak terlalu
lemah (penonton bosan) juga tidak terlalu kuat (penonton frustrasi).
`Ambush Director` melakukan itu: menyusun **antrean 2–4 musuh** lewat
**CSP** (agar valid) lalu **local search** (agar pas target), semuanya
terlihat angkanya di overlay F3.

## Alur permainan

`EXPLORE` (A*, musuh mengejar) → NPC menyentuh → `PREP_PLAYER` (pilih
2 item loadout, Enter; Esc batal) → `PREP_NPC_CSP` (slot terisi per
langkah) → `PREP_NPC_LS` (neighbour + skor live) → `PREP_REVIEW`
(ringkasan, Enter duel / G susun ulang) → `BATTLE` MUSUH 1/k → layar
`TRANSISI` ("MUSUH #n MAJU - HP x/y") → … → menang semua / gagal →
catat hasil + target adaptif → `EXPLORE`.

## Cara menjalankan

Prasyarat: Python 3.10+, `pip install -r requirements.txt` (pygame 2.6.1;
pygbag 0.9.3 hanya untuk deploy web).

```bash
python main.py                          # main (fullscreen; F11 windowed)
python main.py --help 2>/dev/null || true
python3 tests/test_ambush_queue.py      # dan 5 file tes lain di tests/
python3 experiments/run_all.py --quick  # eksperimen final (lihat bawah)
```

Mode BUFF lama (1 NPC lead): `python3 -c` atur `AmbushConfig(mode="BUFF")`
atau ubah default `mode` di `game/ambush/config.py`; seluruh tes BUFF
(`tests/test_ambush_*.py` dengan CFG mode BUFF) tetap hijau.

## Tombol

| Kapan | Tombol | Fungsi |
|---|---|---|
| Persiapan | `F3` | overlay angka (+ mode demo SEED RANDOM) |
| | `T` | tab overlay ALL/CSP/LS/CMP |
| | `F4` | pump instant/slow/step |
| | `TAB` | ganti algoritma LS (run baru) |
| | `Spasi` | 1 langkah (mode step) |
| | `C` | target 0.40→0.50→0.80→ADAPTIF (F3+PREP_* saja) |
| | `X` | SEED BEST/RANDOM |
| | `G` | susun ulang |
| | `Enter` | lanjut/duel |
| Duel | `1-4`/panah+Enter | aksi |
| | `H` | HUD konfigurasi |
| | `D` | debug adversarial |
| | `-`/`+` | depth AI |
| | `Esc` | keluar duel |
| Overworld | WASD/klik | gerak / A* |
| | `F`/`R`/`M`/`P`/`L` | follow / reset / edit / simpan / muat grid |

## Struktur folder

```text
main.py battle_system.py adversarial_ai.py player.py npc.py
game/ambush/  config types constraints csp_solver local_search difficulty
              buff buff_ai director governor trace overlay_ambush csv_export
              chain_eval queue_search enemy_queue
              flow/prep_state_machine flow/queue_driver
              ui/player_loadout_screen ui/battle_hud ui/transition
              compare_panel player_loadout
game/map game/pathfinding game/adv_search
experiments/  run_all.py ablate_csp.py compare_ls.py fidelity.py
              fit_queue.py autoplay.py mae_report.py screens.py
tests/        test_ambush_{foundation,csp_ls,director,verify,prep,queue}.py
docs/         ambush.md kriteria.md hasil.md demo.md screens/
data/         csp_trace.csv ls_trace.csv summary.csv battle_result.csv
```

## X, D, C (contoh, kmax=4)

- **X**: `ROLE_1..4`, `ITEM_1..4` (slot 1 = depan antrean).
- **D**: peran (Boss hanya slot 1 di BUFF; Minion hanya SEQUENTIAL), item.
- **C**: unary (Boss butuh menang≥3; kosong⇒item kosong); biner (maks 1 Healer,
  kompatibilitas peran–item, tanpa-lubang, Boss-terakhir, larangan
  Healer/Tank berturutan); global (AllDifferent item-pairwise, budget,
  min-2 aktif). Contoh pelanggaran: `ROLE_2=Healer` setelah `ROLE_1=Tank`
  → "berturutan (defensif ganda)" → backtrack (lihat log overlay).

## Algoritma local search (parameter di `config.py`)

- Hill climbing steepest-ascent + sideways (`hc_sideways=10`,
  `hc_max_iters=200`), random restart (`hc_restarts=4`, seed CSP acak),
  simulated annealing (`sa_t0=0.5`, `cooling=0.995`, terima buruk
  `e^(deltaE/T)`), genetic (`ga_pop=24`, `ga_gens=40`, crossover
  single-point antar-slot — valid karena memindahkan blok anggota utuh).
- Neighbour: ganti peran/item, tukar item, tambah/kurang musuh (k 2..4),
  tukar urutan — semua dicek constraint dulu (penolakan tercatat).

## Evaluator tiga tingkat (mengapa tiga?)

Sim penuh akurat tapi ~0,6 dtk/antrean (tak muat inner-loop ratusan
evaluasi); heuristik cepat (~0,03 ms) tapi korelasi hanya ~0,6 (partial).
Solusi: **sim ringan greedy** (~10 ms) sebagai objektif (peringkatnya
cukup baik: pairwise 0,75–0,93), **heuristik** hanya pra-penyaring,
**sim penuh** untuk rerank top-2. Keduanya tampil di overlay.

## Satu sumber kebenaran

`slot_to_buff(slot, cfg)` — HUD, battle, heuristik, dan sim membaca objek
`Buff` yang sama. Tes `HUD==battle` menjamin angka tampil = angka dipakai.
`PlayerLoadout` (2 slot) dibaca kedua sisi duel.

## Format CSV

- `csp_trace.csv`: step, variabel, value, domain_size, pruned, backtrack, nodes.
- `ls_trace.csv`: run_id, algo, iter, current, best, target, T, deltaE,
  accepted, rejected_by_constraint (+ jenis neighbour di trace).
- `summary.csv`: ringkasan per run. `battle_result.csv`: per pertemuan
  (k, order, target, pred_light/full, progres aktual, HP/potion sisa,
  hasil, duel_gagal_ke).

## Tes & eksperimen

```bash
for t in tests/test_ambush_*.py; do python3 $t; done   # 114 tes
python3 experiments/run_all.py --quick    # beberapa menit
python3 experiments/run_all.py --full     # lama (100 seed)
python3 experiments/screens.py            # screenshot docs/screens/
```

## KETERBATASAN (jujur)

- **Label jenuh 62%** (sim ≥0.9): sebagian besar antrean acak terlalu
  sulit; korelasi dihitung juga pada subset non-jenuh.
- **Kalibrasi heuristik partial** (Pearson 0.54–0.64 < 0.85; ringan-vs-penuh
  0.54–0.95 per loadout): heuristik turun jadi pra-penyaring; status
  tampil di overlay ("calib: partial").
- **Target 0.3 tak terjangkau** (≤7,7% sampel di semua tuas: rest, potion,
  skala, Minion): siklus C = 0.40/0.50/0.80/ADAPTIF, `gov_min=0.40`
  (dari data: 0.40 = kelipatan 0.05 terendah dengan 14,7%).
- **Target = progres** (rata-rata fraksi duel dimenangkan), bukan peluang
  sapu-bersih; biner dicatat terpisah untuk governor/CSV.
- **Kriteria clear direvisi (disetujui pasca-diagnosis)**: target lama
  (25-40% depth-4 @0.50) ditulis sebelum data nyata dan tidak dikejar —
  clear bergantung kebijakan pemain dan se ~0.14 pada N kecil. Kriteria baru:
  (i) tidak jenuh: clear penuh < 90% @0.50 untuk kedua kebijakan;
  (ii) >= 10% antrean gagal (progres <= 0.5) pada tiap loadout;
  (iii) Director dapat membedakan target (0.8 vs 0.95 tidak identik).
- **Hemat identik dengan greedy** (temuan jujur): refill penuh membuat
  cadangan potion selalu penuh sehingga veto hemat tak pernah mengikat;
  tidak dipisahkan paksa.
- **MAE terhadap pemain simulasi** (greedy/depth-4/hemat), bukan manusia.
- **Rest & potion+1 tak berpengaruh** pada jangkauan (terukur ~nol).
- **Potion player diisi penuh tiap ganti lawan** (`refill_potions_each_duel`,
  berbeda dari rencana awal "terbawa"; sim == driver via `carry_potions()`,
  ada tesnya). Darah dasar musuh 70 (`ENEMY_BASE_HP`, player tetap 100).
- **Bias Healer** (−0.55 heuristik, −0.07 ringan): regen+potion musuh
  sulit dimodelkan murah.
- **Perjalanan keputusan**: label biner jenuh → progres; bug rest
  dead-code (`is_terminal` selalu True) diperbaiki + tes ekstrem;
  tuduhan "cache basi" dicabut setelah audit (salah label arsip M1/M3 —
  kunci cache tetap dikeraskan + 4 tes); M1 = stat dasar (bukan
  "terlemah") → M3 (−50% HP/ATK) terpilih dari data.
- **Sensitif sustain**: rest 25% → 15% menurunkan clear depth-4 @0.50 dari
  ~0.50 ke ~0.00 (n=8 vs n=12, Fisher p~0.02), sementara progres aktual
  ~0.42-0.50 mendekati target 0.50. Target progres 0.5 = "menang ~separuh
  duel", jadi clear penuh yang rendah adalah konsekuensi wajar — bukan bug.
  Akarnya duel dasar tahap 2 yang knife-edge (pemenang kehilangan ~90% HP).
- **Plafon Director ~0.75-0.81** karena batas constraint (budget), bukan
  pencarian: 0.80 vs 0.95 identik dalam noise; opsi A (Boss untuk target
  tinggi: antrean-Boss prog .58-.70, lebih mudah dari keluaran .25) dan
  opsi B (jalur tersulit valid: tak mengalahkan keluaran Director untuk
  depth-4) diuji dan ditolak dengan datanya. Governor di-cap 0.80 + label
  jujur "target di atas plafon, antrean tersulit: {urutan}".
- **Boss tak lebih sulit dari antrean biasa** pada praktiknya (rantai
  berakhir-Boss acak prog ~0.58-0.70 vs keluaran Director ~0.25);
  keterbatasan yang dicatat, bukan diperbaiki (Boss-tetap-terakhir).
- **Hemat ≡ greedy** (refill penuh → cadangan selalu penuh; tidak dipisahkan
  paksa). **0.30 tidak dibuka** (3-12% < syarat 10% pada sedang; hanya lemah
  11.7%). Potion player isi-penuh tiap duel dan HP terbawa. MAE terhadap
  pemain simulasi, bukan manusia.
- **Metodologi**: paket tuning absolut-tak-kumulatif (run R2/R3-paket =
  hibrida, dilabeli; keputusan dari ukur-di-kode-terkunci); bug harness
  `is_queue_valid` (bool dipakai sebagai daftar) ditemukan dan dikoreksi
  sebelum menyimpulkan opsi B; selisih dalam noise tidak dijadikan alasan.
