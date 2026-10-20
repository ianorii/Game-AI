# Implementasi CSP & Local Search — Ambush Director

Sederhana: sebelum battle, game **menyusun antrean musuh** (2–4 Duel) lewat
duh tahap — **CSP** (menyusun kombinasi valid) lalu **Local Search**
(menyempurnakan ke target kesulitan). Semua terlihat di layar lewat **F3**.

## Alur singkat

```
seed CSP (solusi valid)  ->  local search (dekat target)  ->  rerank sim  ->  duel
```

1. **CSP** (`game/ambush/csp_solver.py` + `constraints.py`)
   - **Variabel**: `ROLE_1..4`, `ITEM_1..4` (tiap slot antrean).
   - **Domain**: 7 peran (Boss hanya slot aktif terakhir & butuh menang ≥3;
     Minion khusus mode antrean) + 5 item.
   - **Constraint**: budget power, maks 1 Healer, item berbeda, peran antrean
     saling berbeda, Healer/Tank tak berturutan, dst.
   - **Heuristik**: MRV (pilih variabel domain paling sedikit), degree
     (tie-break), LCV (nilai paling sedikit membuang), **forward checking**
     + **AC-3** (propagasi arc).
   - Hasil = beberapa **seed antrean valid** (bukan satu) untuk tahap berikut.
2. **Local Search** (`game/ambush/queue_search.py`)
   - Objektif: difficulty antrean sedekat mungkin dengan **target**
     (governor adaptif, di-cap 0.80).
   - Algoritma bisa dipilih saat demo: **hill climbing** (+ sideways move),
     **random restart**, **simulated annealing**, **genetic**.
   - Kandidat terbaik dinilai ulang dengan **simulasi duel penuh** (rerank).
3. **Eksekusi** (`director.py` → `flow/queue_driver.py`): antrean jadi battle
   berurutan; HP pemain terbawa, potion isi penuh tiap duel, rest 15%.

## Foto & keterangan

> Taruh file foto di `docs/screens/` lalu ganti nama berkas pada kolom
> "Foto" di bawah (nama bebas, mis. `csp-mrv.png`).

| Foto | Keterangan |
|---|---|
| *(taruh: `csp-backtracking.png`)* | **CSP berjalan** (tab CSP, F3): slot terisi satu per satu — log `CSP isi ROLE_2=… ✓`, backtracking bila buntu. |
| *(taruh: `csp-ac3.png`)* | **AC-3 / forward checking**: baris `AC-3 hapus … → domain 6→5` — constraint mengecilkan domain sebelum nilai dipilih (MRV memilih variabel tersisa paling sedikit). |
| *(taruh: `ls-hillclimb.png`)* | **Local search** (tab LS): grafik gap per iterasi mendekati garis target; opsi TAB ganti algoritma (HC → SA → GA). |
| *(taruh: `review-antrean.png`)* | **Hasil akhir** (PREP_REVIEW): tabel antrean final + cost/budget, difficulty ringan vs simulasi penuh, dan label jujur bila target di atas plafon 0.80. |
| *(taruh: `battle-duel.png`)* | **Battle berurutan**: DUEL 1/k berjalan dengan antrean hasil pencarian; layar hasil menunggu Enter sebelum duel berikutnya. |

## Cara memunculkannya di game

1. `python main.py`, dekati musuh → fase persiapan otomatis berjalan.
2. Tekan **F3** (overlay debug, otomatis mode demo SEED RANDOM).
3. **Tab T** = CSP, **TAB** = pilihan algoritma LS, **Spasi** = step per
   langkah (F4), **G** = ulang run, **Enter** = konfirmasi → battle.
