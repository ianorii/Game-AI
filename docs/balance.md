# BALANCE FREEZE (kunci default)

Tanggal: 2026-10-14. Commit: `3efdbb5` (branch CSP). Berlaku setelah opsi C
disetujui. **Re-lock 2026-10-20** setelah merge `origin/CSP-Jaka` (amandemen-3/4
pemain: musuh 100 HP, Boss 150 HP — lihat bagian bawah). Perubahan apa pun
setelah ini kembali butuh persetujuan. disetujui. Tidak ada tuning lagi
kecuali (a) bug nyata atau (b) hasil uji main manual yang jelas melaporkan
masalah. Tes penegak: `tests/test_ambush_queue.py::test_balance_freeze`
(gagal bila default bergeser diam-diam).

## Sustain (antar-duel, tahap 3 saja)
| Kunci | Nilai |
|---|---|
| `rest_heal_pct` | 0.15 |
| `npc_starting_potions` | 1 |
| `refill_potions_each_duel` (potion player isi penuh tiap lawan) | True |
| `potion_bonus_per_duel` | 0 |
| `npc_potions_carry` | False |
| `enemy_base_hp` | **100** (Amandemen-3: semua musuh = pemain; Boss +50 = 150 via ROLE_TABLE) |

## Stat peran (hp/atk/spec/regen/armor/chip/weaken/cost)
Nilai hp di bawah sudah RIWAYAT sejak Amandemen-3/4 (CSP-Jaka): kini hp=0
untuk semua peran dan Boss hp=50 (100 base + 50 = 150); kolom hp lama
ditandai `(dulu)`.

| Peran | hp | atk | spec | regen | armor | chip | weaken | cost |
|---|---|---|---|---|---|---|---|---|
| Minion | 0 (dulu −50) | -9 | 0 | 0 | 0 | 0 | 0 | 1 |
| Warrior | 0 (dulu 10) | 2 | 0 | 0 | 0 | 0 | 0 | 3 |
| Archer | 0 (dulu 6) | 3 | 0 | 0 | 0 | 1 | 0 | 3 |
| Mage | 0 (dulu 2) | 1 | 7 | 0 | 0 | 0 | 0.10 | 4 |
| Healer | 0 (dulu −15) | 1 | 0 | 2 | 0 | 0 | 0 | 3 |
| Tank | 0 (dulu 4) | 2 | 0 | 0 | 0.05 | 0 | 0 | 4 |
| Boss | 50 (dulu 6) | 2 | 4 | 0 | 0.05 | 0 | 0 | 7 |

Item: Dragon Fang atk1/spec1/cost3 (legendaris); Healing Charm regen1/cost1;
Iron Sword atk2/c1; Heavy Shield armor.10/c1; Swift Boots chip1/c1.

## Governor & budget (tak berubah sejak awal kecuali cap)
`gov_init` 0.50, `gov_min` 0.40, `governor_max_target` **0.80** (plafon opsi C),
`gov_max` 0.95 (pengaman absolut), `gov_up` 0.05, `gov_down` 0.07,
`target_cycle` (0.40, 0.50, 0.80), `boss_min_wins` 3,
`base_q` 8, `budget_q_scale` 8, `base_budget` 6, `budget_scale` 6.

## Perjalanan keputusan (ringkas; detail di docs/balance_TahapA.md)
Tahap A: sustain-dulu (rest .25 + npot 2) lalu stat setengah-langkah 3 putaran
(R1-R3, komposisi FINAL diukur-di-kode). Amandemen pemain: base musuh 100->70
+ refill penuh (ukuran duel ~90% HP hilang -> ~60%). Amandemen rantai-Boss:
Boss 82->76 + npot 2->1 (clear rantai-Boss greedy .08->1.00). Diagnosis:
rentang tak jenuh (gagal 14-41%), plafon Director .8=.95 (tanpa Boss),
rest .25->.15 (satu-satunya tuas dua-arah). Opsi A (Boss) & B (terkeras)
gugur oleh data; opsi C (cap 0.80 + label) diterapkan di sini.
**Amandemen-3/4 (2026-10-19, via CSP-Jaka, permintaan pemain terbaru)**:
SEMUA musuh kembali 100 HP (delta HP peran dinolkan; base-70 jadi riwayat)
dan Boss 150 HP (ROLE_TABLE hp=50); kalibrasi bobot heuristik lama
non-aktif, jadi sim/battle/HUD tetap satu jalur `enemy_max_hp()`.
Selain itu: peran musuh wajib berbeda dalam satu antrean, layar hasil duel
menunggu Enter, sprite per-an di peta/HUD (aset `assets/images/08_karakter`).
Koreksi metodologi: paket R2/R3 absolut-tak-kumulatif (run = hibrida,
diberi label; keputusan dari ukur-di-kode-terkunci); bug harness
`is_queue_valid` bool-sebagai-daftar ditemukan sebelum menyimpulkan opsi B.
