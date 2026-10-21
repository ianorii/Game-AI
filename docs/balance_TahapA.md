# Laporan Tahap A: Sustain-dulu + Stat-peran setengah-langkah (STOP sebelum Fase 7)

> AMANDEMEN-1 (permintaan pemain): darah dasar musuh 100->70 (`ENEMY_BASE_HP`,
> `cfg.enemy_base_hp`) dan potion heal isi penuh tiap ganti lawan
> (`cfg.refill_potions_each_duel=True`, via `carry_potions()` di driver DAN
> sim). Cooldown SPECIAL memang sudah reset tiap duel (BattleSystem baru ->
> cd=0) sehingga tak diubah.
> AMANDEMEN-2 (rantai-Boss, atas keluhan "Boss terlalu kuat + darah tebal"):
> Boss (12/2/6/a.10)->(6/2/4/a.05) [=76 HP] dan npc_starting_potions 2->1
> (anti-stall: musuh terasa tebal karena heal 2x). Ukur apel-ke-apel vs NPC
> depth-4 (=game nyata), N=12, loadout sedang:
> M-W-B greedy .08->1.00, survive(manusiawi) 1.00->1.00;
> M-M-T-B greedy .00->.00 (tak heal = mati, wajar), survive .83->.92.
> K1-d4 1v1 pasca-amandemen-2: semua peran 1.00 kecuali Boss .92-1.00
> (band Tahap-A resmi gugur; metrik baru = rantai pemain-lemah di atas).
> AMANDEMEN-3 (permintaan pemain): SEMUA musuh mulai 100 HP - sama dengan
> pemain. `ENEMY_BASE_HP`/`cfg.enemy_base_hp` = 100 (kembali ke angka awal
> pra-amandemen-1) dan bonus HP peran dinolkan di ROLE_TABLE (hp=0 semua;
> identitas peran tinggal serangan/spesial/regen/armor/chip/weaken, mis.
> Minion tetap lemah dari atk-9). Konsekuensi: seluruh tabel keseimbangan di
> bawah (yang diukur pada base 70 + delta HP peran) menjadi RIWAYAT, bukan
> angka game saat ini; kalibrasi bobot heuristik (data/queue_weights.json,
> `calibrated:false`) juga sudah lama non-aktif sehingga tak berubah. Satu
> konteks bukti tes disesuaikan (`test_conserve_veto_binds` kini Minion
> seed=20) agar veto hemat tetap terbukti mengubah jalannya duel nyata.
> AMANDEMEN-4 (permintaan pemain "sampai melawan boss yang hpnya 150"):
> Boss kembali punya bonus HP di ROLE_TABLE di atas `ENEMY_BASE_HP`
> sehingga `enemy_max_hp` Boss = **150**.
> AMANDEMEN-5 (permintaan pemain "darah dari musuhnya jangan disamain sama
> darah player"): `ENEMY_BASE_HP`/`cfg.enemy_base_hp` = **70** + bonus HP
> peran aktif lagi (Minion -10 -> 60, Mage +10 -> 80, Boss +80 -> 150;
> Warrior/Archer/Tank/Healer tetap base 70). Tak ada musuh ber-HP 100
> seperti player. Base 100 (Amandemen-3) dan base-70 tanpa delta
> (Amandemen-1) menjadi RIWAYAT. Tabel keseimbangan di bawah diukur pada
> base 70 + delta HP peran, jadi arahnya kembali relevan, tetapi angka
> pastinya berubah karena Amandemen-5 memakai delta peran yang berbeda
> (Minion -10 vs dulu -50, Mage +10 vs dulu +2, Boss +80 vs dulu +6) dan
> HP player kini terbawa antar-duel (bukan dipaksa 100 tiap duel).
> Konteks bukti tes yang bergantung stat: `test_conserve_veto_binds` kini
> Warrior (Minion kembali tak mengubah lintasan), seed bukti potion dan
> progres disesuaikan.
> AMANDEMEN-4 (lanjutan): Boss TIDAK dijadwalkan di akhir; uji 96 rencana
> murni (wins 3/5/10 x
> target 0.5/0.75/0.9 x 4 seed) menunjukkan pencarian tak pernah memilihnya
> (biaya peran 7 selalu kalah anggaran / pencarian berhenti saat target
> tercapai), jadi pertemuan ber-Boss jarang - konsekuensi mekanisme
> pencarian yang berlaku, bukan bug.

Metode: CRN seed tetap 100-119 (N=20/sel depth-4/greedy/hemat; rentang antar-blok
seed 100-109 vs 110-119 sebagai noise; selisih dalam noise bukan alasan).
Loadout sedang = Iron Sword + Heavy Shield. K1/K2/K6 = 1v1 item NONE (kec. K6).
Mentah: `data/results/langkah_S.csv`, `langkah_S2.csv`, `langkah_R_{P0,R1,R2,R3}.csv`,
`k6detail_{R1,R2}.csv`.

## 1. Langkah 0 (kebijakan)
- Typo `key < key`: TIDAK DITEMUKAN di kode saat ini (semua greedy memakai
  `best_key` dua sisi). Seluruh kebijakan pemain disatukan ke
  `game/ambush/policies.py` (`greedy_action`, `hemat_veto`, `think_policy`);
  `chain_eval`, `balance_baseline`, `autoplay`, `run_all` mendelegasi ke sana.
- Hemat baru BERBEDA dari greedy: veto potion kecuali HP<40% DAN (duel terakhir
  ATAU potion tersisa > sisa duel). Tes: `test_policies_all_choose_special`
  (SEMUA kebijakan pilih SPECIAL saat tersedia), `test_hemat_veto_queue_binding`
  (veto mengikat di awal antrean, longgar di duel terakhir),
  `test_conserve_veto_binds` (Tank: greedy 30 plies vs hemat ~14-15 plies).
- Bug diperbaiki: `autoplay.main` punya kode mati setelah `return` (CSV tak
  tertulis) — kini menulis lalu mengembalikan rows.

## 2. Langkah S (stat musuh BELUM diubah)
(TABEL: kombinasi x 7 peran x 3 kebijakan, K1-K3 + spread — dari langkah_S.csv)
- npc 3->2: geser depth-4 nyata (Tank .45->.90, Archer .25->.55, Mage .30->.65).
  2->1 overshoot (>=.95) -> DITOLAK. bonus+1 tanpa efek -> DITOLAK (pembanding saja).
- rest 0->.35: tak mengubah K3b-duel (biaya per duel tetap ~.85-.90) TETAPI
  chainwin Minion->X: 0-0.20 (rest 0) -> 0.30-0.75 (rest .25) -> jenuh di .35.
- K5 tak rusak: rest .25 -> 19%/23%/54% (semua >=10%).
- TERPILIH (terkecil): rest_heal_pct=0.25 + npc_starting_potions=2 + bonus 0.

## 3. Putaran R (config S terkunci: rest 0.25 / npot 2 / bonus 0; N=20 CRN)

CATATAN METODOLOGI (jujur): paket R1 valid (deltas dari P0). Paket R2/R3
tertulis absolut-tak-kumulatif sehingga run R2/R3-paket mengukur hibrida
(bukan komposisi yang dimaksud) — kolomnya di bawah ditandai (*). Build
terkunci = komposisi yang dimaksud (R1+R2+R3); kolom FINAL mengukurnya
langsung di kode (`measure_R.py FINAL` tanpa paket). Keputusan dikunci pada
kolom FINAL, bukan kolom hibrida.

K1 1v1 depth-4 win(+-spread), greedy win sebagai lantai:

| Peran | P0 | R1 | R2(*) | R3-paket(*) | FINAL terkunci |
|---|---|---|---|---|---|
| Warrior d4 | .90±.0 | .95±.1 | .85±.1 | .85±.1 | .85±.1 |
| Tank d4 | .90±.2 | .95±.1 | 1.00±.0 | .70±.2 | .95±.1 |
| Healer d4 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Archer d4 | .55±.1 | .55±.1 | .80±.2 | .20±.4 | .20±.4 |
| Mage d4 | .65±.1 | .85±.1 | .80±.2 | .65±.3 | .75±.3 |
| Boss d4 | .25±.1 | .25±.1 | .10±.2 | .10±.2 | .10±.2 |
| Minion d4 (lost) | 1.00 (.27) | 1.00 (.27) | 1.00 (.27) | 1.00 (.27) | 1.00 (.27) |
| Greedy T/M/W | .00/.00/1.0 | .00/.25/1.0 | 1.0/.20/1.0 | .00/.20/1.0 | 1.0/.20/1.0 |
| K5 40/50/80 | 16/23/49 | 19/26/45 | 17/29/45 | 20/27/49 | 21/30/50 |
| K4 sedang-d4-t.5 clear/prog | .00/.44 | .00/.43 | .12/.45 | .12/.46 | .00/.46 |

- R1: Warrior hp15->13, Tank hp8->6/armor.15->.10, Healer regen3->2,
  Mage spec8->7, Fang 3/3->2/2. Mage-fix memperbaiki lantai greedy 0->.25.
  Healer-regen tanpa efek (1.00 tetap, dua putaran berturut).
- R2 (niat): bulk turun + offense naik; Tank armor->.05; Charm regen->1;
  Fang spec->1; Mage weaken->.15; Boss hp->12 (ronde-2).
- R3 (niat): Tank atk->2; Healer hp->-15/atk->1; Archer atk->3/hp->6;
  Mage atk->1/weaken->.10; Fang atk->1. Base turun via ANCAMAN (duel pendek).
- Kunci: komposisi FINAL. Stat lama->baru terkunci (P0->FINAL):
  Warrior(15/1)->(10/2); Archer(10/1/c1)->(6/3/c1); Mage(5/0/8/w.20)->(2/1/7/w.10);
  Healer(0/0/r3)->(-15/1/r2); Tank(8/0/a.15)->(4/2/a.05); Boss hp15->12;
  Fang(3/3)->(1/1); Charm regen2->1. Cost TAK berubah (semua) -> CSP/budget
  tak tersentuh, rerun 20x3 tetap 20/20.

## 4. Autoplay akhir 3 kebijakan x 3 target x 3 loadout (FINAL, n=8/sel)

progres/clear (HP masuk d1/d2 fraksi cap):

| Loadout | Policy | t=0.40 | t=0.50 | t=0.80 |
|---|---|---|---|---|
| lemah | greedy | .58/.00 (d1 .93) | .48/.00 (d1 .94) | .22/.00 |
| lemah | depth4 | .58/.00 (d1 .95) | .48/.00 (d1 .97) | .22/.00 |
| sedang | greedy | .59/.12 (d1 .72) | .50/.00 (d1 .79) | .19/.00 |
| sedang | depth4 | .54/.00 (d1 .70) | .46/.00 (d1 .80) | .16/.00 |
| kuat | greedy | .48/.00 (d1 .53) | .54/.12 (d1 .67) | .23/.00 |
| kuat | depth4 | .40/.00 (d1 .68) | .29/.00 (d1 .85) | .12/.00 |

Progres dalam +-0.1 dari target di 8/9 sel sedang+lemah (kuat-depth4-t.5 .29:
director meremehkan Fang-loadout). Clear penuh JAUH dari target (maks .12;
n=8 -> se~.12, sel .00 vs .12 dalam noise). HP masuk duel-2 .70-.80 (rest
bekerja; P0 .70).
Lintasan adaptif 20 pertemuan (gov dipakai ulang, sedang): target 0.5 ->
lantai 0.40 dalam 1-2 kekalahan, memantul ke .44-.51 tiap kemenangan
(kedua kebijakan; depth4 4W/20, greedy 3W/20). Governor tak hanyut.

## 5. K5: jangkauan target (FINAL, 150 antrean, sedang, N=6)
0.40: 21.3% | 0.50: 30.0% | 0.80: 50.0% (semua >=10% ✓).
TEMUAN: 0.30 kini 11.3% dalam +-0.15 (p10 distribusi = 0.25) -> TERJANGKAU
teknis; gov_min/target_cycle TAK diubah tanpa persetujuan (dilaporkan saja).

## 6. Default baru yang dikunci + tes + temuan lapgas
- `game/ambush/types.py`: 6 peran + Fang + Charm (tabel §3); cost TAK berubah.
- `game/ambush/config.py`: rest_heal_pct 0.0->0.25 (npot=2 sudah default).
- Tes: 107/107 hijau (6 file; +7 tes Tahap-A: kebijakan-semua-SPECIAL,
  hemat-veto-antrean, K1/K2 smoke + 42-kombinasi, K6 smoke, CSP 20x3,
  rest-driver==sim). Tes yang diperbarui mengikuti default/angka baru
  (config, Tank-Shield .15, Tank-skala, rest-flow, conserve-Boss, Warrior-hp).
  Mode BUFF/tahap-1-2 tak tersentuh. Bobot heuristik lama OTOMATIS tak berlaku
  (hash cf41870e vs file) — pengaman terbukti bekerja; sim ringan objektif.
  Fidelitas sampel kecil (n=30, light-N4 vs full-N6): pearson .833 / spearman
  .717 / rmse .155 — di bawah ambang (.85/.80/.08), dilaporkan apa adanya,
  tak memblokir.
- Temuan lapgas: (i) knife-edge: Mage kalah ~7HP (spec8->7 membalik greedy
  0->.25); Archer .80<->.20 antar-putaran (spread .40); (ii) typo greedy
  `key < key` tidak ada di kode (semua delegasi ke policies.py); autoplay.main
  punya kode-mati setelah return (diperbaiki); (iii) paket absolut-vs-kumulatif:
  run R2/R3-paket = hibrida (dilabeli, tak dipakai untuk keputusan); keputusan
  dari ukur-langsung-di-kode-terkunci; (iv) 0.30 terjangkau (11.3%).

## 7. Residual (belum terpenuhi + alasan + usulan)
1. K1-atas: Healer d4 1.00±.0 (regen-arkepe stall; dua potong regen+bulk tanpa
   efek) & Tank d4 .95±.1 (tepi-atas). Usulan: Healer butuh ancaman (±atk) atau
   perubahan constraint (butuh persetujuan); Tank stanow–dalam-noise.
2. K1-bawah: Archer d4 .20±.40 (overshoot atk3 + noise dominan; nilai benar
   .0-.6). Boss d4 .10±.2 (dalam noise dari .15). Usulan: verifikasi-N50
   sebelum sentuh; JANGAN sesuaikan dalam noise.
3. K3: semua non-Minion .69-.98 (biaya duel ~90% struktural: damage dasar
   17.5/rnd milik tahap-2 + potion 3+2). Sustain memberi keterwenangan rantai,
   bukan potongan biaya. Usulan di luar whitelist ( sebagaimana _dilarang_ ):
   tak ada — laporkan sebagai batas arsitektur.
4. K4-clear: d4 25-40% (terukur .00-.12, n=8, se~.12) & greedy >=10% (.00 di
   t.5-sedang). Penyebab: director merencanakan skala-depth4; greedy bermain
   di bawahnya. Usulan:kalibrasi ulang target-per-kebijakan atau terima
   progres-sebagai-metrik (progres ✓ 8/9 sel).
5. K2-plies: d4 15-21 plies = 7.5-10.5 ronde ✓ bila "giliran"=ronde; ✗ bila
   =plies (hanya Minion). Usulan: klarifikasi definisi; arah burst sudah benar.
6. K6-Boots: W -.60±.10 / T -.55±.20 / M -.65±.20 (chip satu-satunya stat Boots;
   semua tumpang-tindih noise di 0.50 — lolos-menurut-aturan-noise, tapi tema
   jelas). Fang ✓ (<=.30 semua), Healer/Archer/Boss/Minion ✓. Usulan (ronde-4,
   butuh persetujuan): Boots cost 1->2 + rerun CSP/diversity/budget; Fang kini
   atk1/spec1/cost3 terlihat mahal (cost 3->2 kandidat bersamaan — terpisah
   dari stat, sesuai aturan).
7. CSP/diversity: valid 20/20 ✓, ROLE_1max 45% ✓, unik 10-15/20 (gerbang
   ">=20" ditulis untuk 50 seed; 20 seed -> maks 20), minion 24-38/20-antrean
   (dominan di t.8; cost tak diubah -> di luar jangkauan putaran ini).
