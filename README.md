# Ambush Director — game menyusun antrean musuh sendiri

Game aksi 2D di Python/pygame untuk tugas besar Kecerdasan Buatan. Dua
bagian sebelumnya sudah menangani pergerakan karakter di peta dan duel 1v1
dengan AI adversarial; yang ditambahkan di sini adalah satu lapisan baru di
atas duel itu: sebelum pertempuran dimulai, game menyusun sendiri antrean
lawan — berapa orang, peran apa, membawa barang apa — lalu mereka maju satu
per satu. Antrean itu bukan hasil tebakan: susunannya dicari dengan **CSP**
supaya wajar, lalu **local search** menyetel tingkat kesulitannya sampai
mendekati target. Semua angkanya bisa dilihat langsung lewat overlay **F3**.

## Idenya: sutradara sebelum duel

Bayangkan sutradara film laga. Sebelum aktor berkelahi, ia memilih pemeran
pengganti yang pas — jangan terlalu lemah (penonton bosan), jangan terlalu
kuat (penonton frustrasi). Ambush Director melakukan hal yang sama, dan
sengaja dibuat kelihatan: tekan F3, lalu node CSP, iterasi local search, skor
tiap kandidat, sampai hasil simulasi duel ditampilkan live.

## Cara kerjanya

**1. Menyusun antrean yang sah — CSP.** Tiap slot antrean punya satu variabel
peran dan satu variabel barang (`ROLE_1..4` dan `ITEM_1..4`), domainnya 7
peran dan 5 barang. Constraint-nya yang menjaga susunan tetap masuk akal:
maksimal satu Healer, barang tidak boleh kembar, dua peran dalam satu
antrean tidak boleh sama, tidak boleh ada slot kosong di tengah, dan total
"power" susunan harus masuk anggaran yang dihitung dari target kesulitan.
Solvernya backtracking + MRV/degree + LCV + AC-3, dan setiap bagiannya bisa
dimatikan satu per satu (tombol Q/W/E/R) untuk melihat efeknya sendiri.
Hasilnya bukan satu susunan, tapi beberapa *seed* valid untuk tahap
berikutnya.

**2. Menyetel kesulitan — local search.** Seed dari CSP terlalu acak untuk
dipakai langsung, jadi tiap seed dirangkai ulang sedikit demi sedikit
(neighbor: ganti peran, ganti barang, tukar barang, tambah/kurangi musuh,
tukar urutan) sampai kesulitannya dekat dengan target. Setiap perubahan dicek
constraint dulu, dan yang ditolak ikut dihitung sebagai data. Empat algoritma
bisa dipilih saat main: hill climbing (+ sideways move), random restart,
simulated annealing, dan genetic algorithm.

**3. Memilih yang terbaik.** Dua kandidat teratas dinilai ulang dengan
simulasi duel sungguhan (AI di kedua sisi), lalu yang terbaik keluar sebagai
antrean final.

**4. Bertanding.** Antrean itu maju satu per satu. Di antara duel-duel itu
player boleh istirahat dan memakai potion, dan target kesulitan bergerak
sendiri: menang beruntun menaikkan target, kalah beruntun menurunkannya
(dibatasi 0,40–0,80). Kalau target yang diminta di luar jangkauan, label di
overlay mengatakannya terus terang — bukan dipaksa jadi angka yang enak
dilihat.

## Alur permainan

```
Jelajah → Prep (atur loadout) → Susun antrean (CSP → LS) → Review
        → Duel 1/k → Duel 2/k → … → Tuntas / Kalah → Catat hasil → Jelajah
```

Musuh di peta cuma satu sprite karakter Boss yang mengejar player. Yang
"dipanggil" adalah anak buahnya, dan itu baru terjadi di battle mode: begitu
pertemuan dimulai, game menyusun antrean lewat CSP + local search, lalu
antrean itulah yang melawan player berurutan. Di fase Prep player mengatur
loadout sendiri (dua slot barang), lalu boleh menyetujui atau menyusun ulang
antrean sebelum duel dimulai. Supaya tidak terasa berulang, peran-peran dari
pertemuan sebelumnya dikeluarkan dari pilihan di pertemuan berikutnya.

## Menjalankan

Butuh Python 3.10+. `pygame 2.6.1`; `pygbag 0.9.3` cuma dipakai kalau mau
deploy ke web.

```bash
pip install -r requirements.txt
python main.py                 # main (fullscreen; F11 buat windowed)
```

Mode lama dengan satu NPC lead (tanpa antrean) masih ada: set
`mode="BUFF"` di `game/ambush/config.py`, dan tes untuk mode itu tetap hijau.

Tes dan eksperimen:

```bash
for t in tests/test_ambush_*.py; do python3 $t; done   # 122 tes
python3 experiments/run_all.py --quick    # eksperimen ringkas, beberapa menit
python3 experiments/run_all.py --full     # 100 seed, lama
python3 experiments/screens.py            # screenshot ke docs/screens/
```

## Tombol

| Kapan | Tombol | Fungsi |
|---|---|---|
| Persiapan | `F3` | overlay angka (menyalakan mode demo SEED RANDOM) |
| | `T` | ganti tab overlay (ALL / CSP / LS / CMP) |
| | `F4` | kecepatan tampilan: instant / slow / step |
| | `Spasi` | maju satu langkah (mode step) |
| | `TAB` | ganti algoritma local search, jalankan ulang |
| | `Q` `W` `E` `R` | toggle MRV / degree / LCV / inferensi (AC-3 → FC → mati) |
| | `C` | target 0,40 → 0,50 → 0,80 → ADAPTIF |
| | `X` | seed BEST / RANDOM |
| | `G` | susun ulang dengan seed baru |
| | `Enter` | lanjut (siap duel) |
| | `Esc` | batal / keluar |
| Duel | `1`–`4`, panah + `Enter` | aksi |
| | `H` | HUD konfigurasi |
| | `D` | debug adversarial search |
| | `-` / `+` | kedalaman pencarian AI |
| | `Esc` | keluar duel |
| Jelajah | `WASD` / klik | bergerak |
| | `F` / `R` | ikut player / reset status duel |
| | `M` / `P` / `L` | edit peta / simpan grid / muat grid |
| | `Q` `E` / `T` `G` | heuristic player / NPC |

## Ringkasan CSP (X, D, C)

| Unsur | Isi |
|---|---|
| X | `ROLE_1..4`, `ITEM_1..4` (slot 1 = depan antrean) |
| D | peran: Minion, Warrior, Archer, Mage, Healer, Tank, Boss; barang: Iron Sword, Heavy Shield, Swift Boots, Healing Charm, Dragon Fang — plus `NONE` |
| C unary | Boss baru boleh masuk antrean kalau player sudah menang minimal 3 kali, dan posisinya harus di slot aktif terakhir; peran `NONE` ⇒ barang `NONE` |
| C biner | maksimal satu Healer; kompatibilitas peran–barang; tanpa slot kosong di tengah; Healer dan Tank tak boleh berturutan |
| C global | semua barang aktif saling berbeda; total power ≤ budget (`8 + target × 8`); minimal 2 musuh aktif |

Contoh kalau mau lihat solver-nya bekerja: `ROLE_2 = Healer` tepat
setelah `ROLE_1 = Tank` itu pelanggaran "berturutan (defensif ganda)", jadi
solver mundur dan mencoba nilai lain.

## Local search

Parameternya tinggal diubah di `game/ambush/config.py`:

- Hill climbing steepest-ascent + sideways move (`hc_sideways=10`,
  `hc_max_iters=200`), random restart (`hc_restarts=4`, seed CSP diacak),
  simulated annealing (`sa_t0=0.5`, cooling `0.995`, langkah buruk diterima
  dengan peluang `e^(deltaE/T)`), dan genetic algorithm (`ga_pop=24`,
  `ga_gens=40`).
- Crossover GA memotong antar-slot, jadi blok "peran + barang"-nya pindah
  utuh — koherensi role–item tidak pernah rusak.
- Semua neighbor dicek constraint sebelum dievaluasi, dan alasan penolakan
  dicatat di trace.

## Menilai seberapa sulit sebuah antrean

Tidak ada satu angka aja yang bisa dipercaya, jadi evaluatornya bertingkat.
Simulasi duel penuh akurat, tapi terlalu lambat untuk dipanggil ratusan kali
di tengah pencarian; heuristik cepat, tapi korelasinya cuma sekitar 0,6, jadi
tidak boleh dipakai sebagai nilai absolut. Jalan keluarnya: **simulasi
ringan** (sekitar 10 ms) yang jadi objektif local search — peringkatnya
sendiri sudah cukup bagus (pairwise 0,75–0,93) — dengan **heuristik** hanya
sebagai pra-penyaring, lalu **simulasi penuh** untuk menentukan dua kandidat
teratas. Ketiganya tampil di overlay, lengkap dengan selisihnya.

## Satu sumber kebenaran

`slot_to_buff(slot, cfg)` dipakai bersama oleh HUD, battle, heuristik, dan
simulasi, jadi angka yang tampil di layar dijamin sama dengan angka yang
dipakai menghitung. Ada tes yang menjaga hal ini (`HUD == battle`), dan
`PlayerLoadout` yang dipilih player di Prep dibaca kedua sisi duel.

## Struktur folder

```text
main.py battle_system.py adversarial_ai.py player.py npc.py settings_menu.py
game/ambush/  config types constraints csp_solver local_search queue_search
              director governor difficulty chain_eval enemy_queue buff buff_ai
              trace csv_export overlay_ambush compare_panel player_loadout
              policies
              flow/prep_state_machine flow/queue_driver
              ui/player_loadout_screen ui/battle_hud ui/transition
game/pathfinding/  game/adv_search/
experiments/  run_all.py ablate_csp.py compare_ls.py fidelity.py fit_queue.py
              autoplay.py mae_report.py screens.py ambush_exp.py fit_heuristic.py
tests/        test_ambush_{foundation,csp_ls,director,verify,prep,queue}.py
docs/         ambush.md kriteria.md hasil.md demo.md csp_local_search.md
              balance.md balance_TahapA.md
data/         csp_trace.csv ls_trace.csv summary.csv battle_result.csv
              fidelity.json queue_weights.json results/
```

## Data yang dihasilkan

- `csp_trace.csv` — jejak pencarian CSP: step, variabel, nilai, ukuran
  domain, jumlah pruned, backtrack, node.
- `ls_trace.csv` — jejak local search: run, algoritma, iterasi, skor
  sekarang & terbaik, target, suhu, deltaE, diterima/ditolak (+ jenis
  neighbor).
- `summary.csv` — ringkasan per run. `battle_result.csv` — hasil per
  pertemuan: jumlah & urutan musuh, target, prediksi ringan & penuh, progres
  aktual, sisa HP/potion, hasil duel.

Angka di overlay dan angka di CSV berasal dari trace yang sama, ada tesnya.

## Yang masih belum rapi (catatan jujur)

- **Heuristik belum terkalibrasi penuh.** Korelasinya 0,54–0,64, jauh dari
  ambang 0,85, jadi ia turun kelas jadi pra-penyaring dan objektifnya
  dipindah ke simulasi ringan. Statusnya ditampilkan di overlay ("calib:
  partial"), bukan disembunyikan.
- **Label "jenuh" 62%** di simulasi: sebagian besar antrean acak memang
  terlalu sulit untuk label biner, jadi korelasi juga dihitung pada subset
  non-jenuh.
- **Target 0,30 memang tak terjangkau** — hanya 7,7% sampel atau kurang di
  semua variasi. Karena itu siklus target dimulai dari 0,40 (kelipatan 0,05
  terendah yang lolos) dengan batas bawah 0,40.
- **Plafon Director sekitar 0,75–0,81**, dan ini karena batas constraint
  (budget), bukan karena pencariannya lemah. Opsi "pakai Boss untuk target
  tinggi" dan "jalur valid tersulit" sudah diuji dan ditolak dengan datanya;
  governor di-cap 0,80, dan kalau diminta lebih tinggi, overlay menulis
  "target di atas plafon, antrean tersulit: {urutan}".
- **Boss tidak selalu lebih sulit.** Rantai yang berakhir dengan Boss acak
  justru lebih mudah (progres 0,58–0,70) daripada keluaran Director (sekitar
  0,25). Ini dicatat apa adanya, tidak dipaksa.
- **Kebijakan "hemat" identik dengan greedy**, karena potion player diisi
  penuh tiap ganti lawan sehingga veto hemat tak pernah mengikat.
- **Target adalah progres** (rata-rata fraksi duel yang dimenangkan),
  bukan peluang menyapu semua lawan; versi binernya dicatat terpisah untuk
  governor dan CSV.
- **Besarnya istirahat dan potion tambahan hampir tak mengubah jangkauan
  target** (terukur ~nol), tapi jelas mengubah seberapa sering player bisa
  menyapu semua lawan: turunnya porsi istirahat dari 25% ke 15% menurunkan
  `clear` depth-4 @0,50 dari ~0,50 ke ~0,00 (sampel kecil: 8 vs 12).
  **`clear` penuh yang rendah adalah konsekuensi wajar**, bukan bug: duel
  dasarnya knife-edge (pemenang kehilangan ~90% HP), jadi menyapu semua lawan
  memang jarang.
- **MAE diukur terhadap pemain simulasi** (greedy / depth-4 / hemat), bukan
  manusia — jadi jangan diklaim tervalidasi lawan manusia.
- **Angka musuh memang beda dari player**: dasar 70 HP (Minion 60,
  Warrior/Archer/Tank/Healer 70, Mage 80, Boss 150). Semua riwayat
  amandemen tercatat di `docs/balance_TahapA.md`.

## Dokumen lain

- `docs/ambush.md` — penjelasan lengkap CSP, local search, buff, dan alur
  persiapan.
- `docs/kriteria.md` — pemetaan tiap kriteria soal ke file, tes, dan
  screenshot.
- `docs/hasil.md` — ringkasan angka eksperimen (ablasi CSP, banding LS,
  fidelitas, autoplay).
- `docs/demo.md` — skrip demo 5–7 menit plus jawaban tanya-jawab.
- `docs/csp_local_search.md` — versi ringkas dengan kolom foto.
