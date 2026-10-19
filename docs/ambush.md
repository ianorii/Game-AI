# Ambush Director — Tahap 3 (Local Search + CSP)

Sebelum NPC masuk battle mode, sistem menyusun squad penyerang yang pas
dengan kemampuan player: **CSP** menghasilkan konfigurasi valid →
**local search** menyetel difficulty ke target → verifikasi → buff dipakai
di duel 1v1 yang sudah ada.

## 1. Rumusan CSP (X, D, C)

| Unsur | Isi |
|---|---|
| X | `ROLE_1..ROLE_3`, `ITEM_1..ITEM_3` (slot 1 = lead, efek penuh) |
| D | `D(ROLE_1)` = 6 role + Boss + NONE; `D(ROLE_2..3)` tanpa Boss; `D(ITEM)` = 6 item + NONE |
| C-unary | Boss ⇒ wins ≥ 3, ber-HP **150** (`enemy_max_hp`), dan hanya boleh di slot aktif terakhir; Boss ikut antrean **hanya bila pencarian (CSP+LS) memilihnya** — tidak dijadwalkan tetap; ROLE NONE ⇒ ITEM NONE |
| C-biner | maks 1 Healer; matriks kompatibilitas role–item (Sword: Warrior/Archer/Boss; Shield: Warrior/Tank/Boss; Boots: Warrior/Archer/Mage; Charm: Healer/Mage/Tank; Fang: semua); slot kosong tak di tengah. **Mode antrean** (`queue_rules=True`): semua peran musuh saling berbeda, Boss hanya slot aktif terakhir, Healer/Tank tak berturutan |
| C-global | SEMUA item non-NONE saling beda (AllDifferent penuh, pairwise); squad ≥ 1 anggota; total power ≤ budget (`6 + target×6`) |

Satu sumber kebenaran: `BuffSummary` (`buff.py`) — overlay, evaluator,
dan battle membaca objek yang sama. Nilai placeholder NONE selalu dicoba
terakhir di `_order` (kalau tidak, LCV sistematis memilih NONE untuk ITEM
yang di-assign sebelum ROLE-nya). Domain variabel ter-assign dikunci
singleton agar AC-3/FC melihat assignment (tanpa ini revise selalu 0).

Data role/item adalah data **baru Tahap 3** (`game/ambush/types.py`) —
tahap 1–2 hanya punya potion duel. Solver: backtracking + MRV/degree +
LCV + AC-3 (REVISE + queue), forward checking opsional; semua toggleable;
seed mengacak tie-break value (sumber random restart). Solusi = complete
DAN consistent (dicek di tiap assign).

## 2. Local search

- State = squad valid; objective = `|difficulty − target|`.
- Evaluator satu interface: **heuristik affine yang difit ke simulasi**
  (`experiments/fit_heuristic.py`: 150 squad, korelasi 0.934, MAE 0.048 —
  sim margin vs AI sederajat depth-4-vs-4 sehingga buff yang memutuskan)
  untuk inner-loop, dan **simulasi** untuk validasi. Overlay menampilkan
  keduanya; keduanya mendekati target bersama (contoh: target 0.5 →
  heur 0.536/sim 0.602; target 0.7 → heur 0.695/sim 0.672).
- Neighbour: ganti role, ganti item, tukar item, tambah/hapus anggota —
  semua dicek constraint dulu (ditolak dihitung).
- Algoritma: hill climbing steepest-ascent + sideways, random restart
  (seed dari CSP acak), simulated annealing (`e^(deltaE/T)`, cooling 0.995),
  GA (di bawah).

**Mengapa crossover bermakna.** Kromosom = tuple per-slot `(role, item)`;
tiap gen adalah "kaset anggota utuh". Crossover single-point **antar slot**
mewariskan anggota-anggota utuh dari kedua induk — koherensi role–item tak
pernah disobek (berbeda dengan crossover per-bit).

**Penalti vs repair.** Default **penalti** fitness (`−gap − 0.5×pelanggaran`):
populasi boleh melintasi daerah infeasible dan tak butuh solver.
`ga_repair=True` memakai proyeksi deterministik murah
(`project_to_feasible`), bukan solver CSP penuh, agar GA tetap cepat.

## 3. Buff & governor

Tiap peran berefek beda (Tank = armor, Healer = regen, Archer = chip,
Mage = special + weaken heal musuh, Warrior/Boss = mentah); slot pendukung
kena diminishing returns `1/(1+0.5·i)`. `SequentialDuelPlan` selalu 1 ronde
sekarang — titik ekstensi duel berurutan. Governor: menang telak/beruntun
menaikkan target (maks 0.95), kalah beruntun menurunkan (min 0.15).

**Buff-aware tanpa menyentuh tahap 2** (`game/ambush/buff_ai.py`):
`BuffBattleState` (transisi buff-aware dua sisi: buff NPC + loadout player —
bonus atk/spec, cap potion, regen awal giliran, armor prescale dua arah,
weaken heal, chip dua arah via hook yang sama untuk sim dan battle nyata)
dan `BuffAwareAI` (eval tahap 2 di atas HP efektif K=3 ronde, simetris).
Battle log menampilkan buff aktif ("Buff: Tank: -13% damage diterima"…)
agar pengaruhnya terverifikasi di HUD. Verifikasi: squad vs tanpa squad
(N=100, seed tetap) → margin +0.458 (0.413 → 0.872).

## 4. Kontrol & alur persiapan

Alur eksplisit (tak ada fase terlewat otomatis): `EXPLORE → PREP_PLAYER
(pilih 2 slot loadout) → PREP_NPC = DIRECTOR (CSP → LS bertahap) →
PREP_REVIEW (tahan hingga Enter, G = susun ulang) → BATTLE → EXPLORE`.
Esc di PREP_PLAYER batal kembali ke EXPLORE.

Di mode antrean (k≥2) alurnya `BATTLE → TRANSITION → BATTLE ...`. Layar
TRANSITION menampilkan HASIL duel terakhir (MENANG/KALAH/KABUR) + lawan
berikutnya (nama, item, HP, efek) dan **menunggu Enter** — tidak ada lanjut
otomatis (jeda 1.5 dtk lama dihapus). Enter memulai duel berikutnya; di akhir
pertemuan (menang semua/kalah/kabur) Enter mengembalikan ke EXPLORE.

**Aturan variasi musuh (permintaan pemain).** (1) Dalam SATU pertemuan
semua peran musuh wajib berbeda — "tidak ada musuh yang sama dua kali":
dicek `enemy_queue.check_queue` (cermin `constraints.check`) dan dipangkas
pairwise oleh CSP, jadi solusi/neighbour LS tak pernah memuat duplikat.
(2) Antar-pertemuan: `main.py` mencatat `last_queue_roles` saat pertemuan
tutup dan mengopernya sebagai `avoid_roles` ke director — peran itu keluar
dari domain CSP, LS, dan repair; bila CSP tak menemukan antrean bebas
(kasus langka), kandidat valid apa adanya tetap dipakai supaya duel tidak
pernah berubah jadi "duel polos" (variasi = best-effort). Pemilihan akhir
(rerank) hanya di antara kandidat bebas peran lama.

Tombol SIAP (`Enter`/`ESC`) menuntaskan sisa langkah run **tanpa mengubah
pump mode pemain** (`pump_director(..., instant=True)`) — animasi demo
slow/step tetap tampil lagi di pertemuan berikutnya, bukan sekali pakai.

**Musuh di peta = karakter Boss (permintaan pemain).** Yang mengejar di
peta adalah satu sprite karakter Boss — "kembali seperti semula, tapi
diganti jadi karakter Boss": `spawn_enemy` selalu memasang sprite role
"Boss" (tanpa formasi, tanpa undian). "Anak buahnya" baru dipanggil di
battle mode: begitu pertemuan dimulai, director menyusun antrean lewat
CSP → local search (fase PREP), dan antrean itulah yang dilawan berurutan
(`_queue_slot_sprite` memasang sprite peran tiap duel). Boss ikut jadi
lawan hanya bila **pencarian** menempatkannya di slot aktif terakhir
(wins ≥ `boss_min_wins`), bukan dijadwalkan tetap. Catatan temuan: pada uji
96 rencana murni (wins 3/5/10 × target 0.5/0.75/0.9 × 4 seed) Boss tidak
pernah terpilih — selalu kalah anggaran (biaya 7) atau pencarian berhenti
saat target kesulitan tercapai; jadi pertemuan ber-Boss memang jarang, dan
itu konsekuensi mekanisme pencarian yang berlaku.

| Tombol | Fungsi |
|---|---|
| `F3` | overlay angka-angka |
| `F4` | pump slow → step → instant, default **slow** (menu formasi terlihat langkah per langkah + jeda baca tiap fase; bisa dari overworld, berlaku duel berikut) |
| `TAB` | ganti algo LS, run baru (bisa dari overworld, berlaku duel berikut) |
| `TAB` | ganti algo LS (run baru) |
| `Spasi` | 1 langkah (mode step); bila sudah selesai = mulai duel |
| `Enter`/`ESC` | tombol SIAP: tuntaskan sisa langkah run ini lalu mulai duel (pump mode tak diubah, demo tetap tampil di pertemuan berikutnya) |
| `H` (duel) | HUD konfigurasi Player vs NPC+Squad (angka = buff battle) |
| PREP_PLAYER | Atas/Bawah slot, Kiri/Kanan item, Enter lanjut, Esc batal |
| `G` | ulang run (seed baru) |
| `Q/W/E/R` | toggle MRV / degree / LCV / inferensi (berlaku run berikut) |

CSV (`data/`): `csp_trace.csv`, `ls_trace.csv`, `summary.csv` ditulis tiap
pencarian selesai.

## 5. File & uji

```
game/ambush/  config types buff buff_ai constraints difficulty csp_solver
              local_search governor director trace csv_export overlay_ambush
tests/        test_ambush_foundation/csp_ls/director/verify (33 test)
experiments/  ambush_exp.py (CS1 LS1 CAL, seed tetap) + fit_heuristic.py
```

```bash
python3 tests/test_ambush_foundation.py   # 13
python3 tests/test_ambush_csp_ls.py       # 10
python3 tests/test_ambush_director.py     # 5
python3 tests/test_ambush_verify.py       # 5 (sim N=100 ~10 dtk)
python3 experiments/ambush_exp.py --quick # CS1+LS1+CAL
python3 experiments/fit_heuristic.py      # fit ulang bobot bila tabel berubah
```

Integrasi kode lama (minimal, terdaftar): `main.py` (fase DIRECTOR +
pump + overlay + governor), `battle_system.py` (param opsional `npc_buff`;
`None` = perilaku tahap 2 persis). `adversarial_ai.py`, `experiments.py`,
tahap 1 tak tersentuh.

## 6. Temuan jujur (bahan demo)

- Budget longgar → 7 nodes/0 backtrack (gameplay tak membeku).
- Budget ketat → polos 7/0, **MRV 18-24 nodes**: degree memilih ITEM duluan
  (derajat 3 via edge AllDifferent) — heuristik bisa merugikan; FC/AC-3
  memangkas kembali ke 7 nodes (pruned 4-8, revises > 0).
- Heuristik vs simulasi kini satu skala (fit korelasi 0.934); baseline sim
  0.43 (kosong) – 0.87 (buff penuh) mencakup target 0.5–0.9.
- `w_spec ≈ 0`: AI jarang memakai SPECIAL dalam horizon sim — efeknya tak
  terukur, dipertahankan apa adanya (noise, bukan di-nol-kan manual).

## 7. Keterbatasan terukur (jalur 3, opsi A bersyarat)

Target progres 0.3 terbukti tak terjangkau (<=1.7% dari 300 antrean dalam
+-0.15, di semua skala/rest/potion/Minion). Penyebab: lantai struktural —
mekanik carry (musuh segar + potion terbawa + rest 0) membuat sapuan penuh
hampir mustahil; wilayah 0.3 (antrean padat-Minion) terlalu tipis untuk
mewakili 10% sampel acak. Pengganti: 0.40 (14.7%, kelipatan 0.05 terendah
yang lolos), `gov_min=0.40`, siklus C = 0.40/0.50/0.80/ADAPTIF. Overlay
menampilkan "target di luar jangkauan, hasil terbaik: X" bila gap akhir di
luar toleransi (lihat `honest_gap_label`).

## 8. Fidelitas sim ringan vs penuh (Fase 4.1, MELAPORKAN bukan memblokir)

`experiments/fidelity.py` (300 antrean × 3 loadout, N=8, seed tetap):
lemah Pearson **0.95** (lolos) / sedang 0.54 / kuat 0.68; ambang internal
tetap 0.85/0.80 (selisih ditampilkan, tidak diturunkan). Status:
"calibrated: partial" (`data/fidelity.json`). Peta monoton linear
dipakai hanya untuk pelaporan, bukan objektif (objektif = sim ringan
mentah agar peringkat jujur). Akibatnya objektif LS = "sim ringan",
rerank = "sim penuh" — label keduanya tampil di overlay.

## 9. Definisi "evaluasi" + MAE (Fase 5/6)

- Satu "evaluasi" = satu pemanggilan `evaluator.evaluate()` di DALAM
  search (skor neighbour + skor akhir); evaluasi pemilihan seed (3×) dan
  rerank sim-penuh TIDAK ikut hitungan `evals` (tercatat terpisah).
  HC polos berhenti di non-improvement pertama (mist. 51 eval) sementara
  HC+sideways menjelajah dataran (mist. 264 eval) — selisih BEST vs RANDOM
  pada MS dipengaruhi panjang duel (musuh sustain = eval mahal), bukan
  hanya jumlah eval.
- MAE prediksi-vs-aktual diukur terhadap PEMAIN SIMULASI (greedy/depth-4/
  hemat), bukan manusia. Jangan klaim validasi lawan manusia.
