# Adversarial Search pada Turn-Based Battle Duel

| | |
|---|---|
| Nama | _isi di sini_ |
| NIM | _isi di sini_ |
| Mata kuliah | _isi di sini_ |
| Tugas | Tubes 2 - Adversarial Search |
| Tanggal | _isi di sini_ |

Laporan tugas kecerdasan buatan. Fokusnya adalah perumusan agent NPC duel
sebagai permainan zero-sum dengan Adversarial Search, beserta eksperimen
terukur. Cakupan laporan dibatasi pada komponen AI: perumusan state, fungsi
evaluasi, algoritma pencarian adversarial, dan pengukurannya. Alpha-beta
tercakup penuh di sini karena ia adalah salah satu algoritma yang diminta
tugas, dan diukur langsung pada bagian 5.2. Yang di luar lingkup laporan
adalah detail rendering dan sistem di luar duel.

Seluruh angka berasal dari `python experiments.py` terhadap 600 state acak
dengan seed tetap dan 60 duel per kombinasi pada E5 dan E7. Tabel mentah ada
di `hasil_eksperimen.md`, data duel nyata ada di `duel_log.csv`. Kolom waktu
(`ms`) adalah satu-satunya angka yang berubah antar-jalankan; node, eval,
persentase, dan distribusi aksi deterministik.

---

## 1. Asumsi-asumsi pemodelan

Slide 2 modul memandangi seluruh materi ini sebagai **pelonggaran asumsi
single-agent**. Duel ini melonggarkan dua di antaranya, dan itu yang
menentukan algoritma mana yang dipakai:

| Asumsi single-agent | Status di duel ini | Dampak ke algoritma |
|---|---|---|
| Single agent | Dilonggarkan: ada dua pihak bergantian, MAX dan MIN. | Wajib pakai Minimax, bukan pencarian single-agent biasa. |
| Fully observable | Tetap dipakai. | Tidak perlu belief state. |
| Deterministic | **Dilonggarkan.** Damage ATTACK diundi 15-20. | Alpha-beta harus memakai damage tetap; Expectimax jadi relevan. |
| Static | Tetap dipakai. | Tidak ada perubahan dari luar selama duel; damage hanya undian statis, bukan state yang bergerak. |
| Discrete | Tetap dipakai. | Tidak ada state kontinu. |
| Known | Tetap dipakai: kedua pihak tahu aturan dan bobot eval. | Tidak perlu mencari environment yang tidak dikenal. |

Jadi asumsi yang berubah adalah "single agent" dan "deterministic", dan
keduanya terlihat di hasil: yang pertama lewat struktur MAX/MIN di bagian
2.6, yang kedua lewat selisih 8.3% antara alpha-beta dan Expectimax di E6.
Sisanya sengaja dibiarkan sesuai supaya variabel lain tidak ikut berubah dan
perbandingan algoritmanya tetap terisolasi.

| # | Asumsi | Alasan | Konsekuensi kalau salah |
|---|---|---|---|
| A1 | Perfect information | Kedua pihak melihat HP, potion, dan cooldown satu sama lain. | Butuh belief state dan probabilitas parsial. |
| A2 | Zero-sum | Menang NPC berarti kalah Player, jadi satu skaler cukup. | Perlu multiobjektif atau vektor utility. |
| A3 | Player rasional | Player diasumsikan mencari nilai minimum, bukan acak. | Minimax kehilangan sifat pesimistik yang tepat. |
| A4 | Pertukaran giliran bersih | NPC dan Player bergantian tanpa mengulang state. | Simulasi jadi partizan. |
| A5 | Horizon terbatas | Pohon dibatasi `depth` ply; nilai di luar horizon diestimasi heuristik. | Pencarian tidak pernah melihat kemenangan. |
| A6 | Damage ATTACK acak seragam 15-20 | `battle_system` memakai `random.randint(15, 20)`, jadi asumsi deterministik modul harus dilonggarkan di sini. | Alpha-beta yang memakai damage tetap bisa salah menilai duel yang damage besarnya kebetulan tinggi. |
| A7 | HP terbawa antar-momen | `main.py` menyimpan `player_hp` ke state berikutnya, dan `start_battle()` memulihkannya. | Benchmark state acak tidak mewakili gameplay. |
| A8 | Ketidakpastian hanya aleatoris | Tidak ada informasi yang disembunyikan. | Ada ketidakpastian epistemis yang perlu Belief MDP. |
| A9 | Duel dipicu kedekatan, bukan encounter acak | `main.py` memakai jarak Manhattan `<= BATTLE_TRIGGER_DIST` (1 ubin) untuk masuk mode battle, sesuai contoh pada soal. | NPC bisa duluan menusuk dari jarak jauh tanpa masuk duel. |

A5 adalah asumsi yang paling menentukan, dan akan dibuktikan langsung pada
bagian 5.1: horizon yang terlalu pendek membuat AI tidak pernah melihat
kemenangan sama sekali.

A9 mengatur trigger duel dan perlu dijelaskan sekali, karena laporan ini
fokus pada AI. Ambang proximity dihitung di `main.py:929-931` dari jarak
Manhattan, bukan jarak Euclidean:

```
dist = abs(player.row - npc.row) + abs(player.col - npc.col)
if dist <= BATTLE_TRIGGER_DIST:   # BATTLE_TRIGGER_DIST = 1
    start_battle(state, player, npc, game_map)
```

Pemeriksaan ini hanya berjalan di mode `OVERWORLD`, bukan saat menu pengaturan
terbuka dan bukan pada mode edit. Threshold 1 ubin dipilih agar duel memicu
saat Player bertabrakan dengan NPC, bukan saat Player hanya berdiri di
seberang. Syarat A1 (perfect information) berlaku sejak trigger: begitu
duel dimulai, kedua pihak melihat seluruh state yang dirumuskan pada
bagian 2.1.

---

## 2. Formulasi formal

### 2.1 State

State `s` adalah tupel:

```
s = (hp_p, hp_n, pot_p, pot_n, def_p, def_n, cd_p, cd_n, turn)
```

| Simbol | Arti |
|---|---|
| `hp_p`, `hp_n` | HP Player dan NPC, rentang 0..100 |
| `pot_p`, `pot_n` | Sisa potion, 0..3 |
| `def_p`, `def_n` | Bendera DEFEND aktif, bertahan satu giliran lawan |
| `cd_p`, `cd_n` | Cooldown SPECIAL yang tersisa |
| `turn` | 0 = giliran Player, 1 = giliran NPC |

Implementasi: `BattleState` di `adversarial_ai.py`.

### 2.2 Initial state dan transition model

Soal searchable game listing insisted lima komponen: initial state, player,
transition model, available actions, terminal state, dan utility. Available
actions ada di 2.3 dan terminal di 2.4, jadi dua komponen yang sering
terlewat dibahas di sini.

**Initial state** `s0` adalah state duel yang bersih, yaitu seluruh default
`BattleState`:

```
s0 = (hp_p=100, hp_n=100, pot_p=3, pot_n=3, def_p=0, def_n=0,
      cd_p=0, cd_n=0, turn=0)
```

Artinya duel selalu mulai dari HP penuh, tiga potion per pihak, dan SPECIAL
langsung siap.

Ada satu perbedaan penting antara `s0` di atas dan state awal duel sungguhan.
`simulate_duel()` memakai `s0` persis, tetapi `start_battle()` membangun
state dari `BattleState(player_hp=...)` dengan HP player yang **diambil dari
penyimpanan overworld**, lalu dijepit ke rentang 1..100. Ini konsekuensi
asumsi A7: luka dari duel sebelumnya terbawa ke duel berikutnya. Jadi `s0`
adalah initial state untuk benchmark, sedangkan duel yang dimainkan bisa mulai
dari HP player di bawah 100. Perbedaan inilah yang membuat benchmark E5
tidak mencerminkan distribusi gameplay, dan sudah tercatat di bagian 7.

**Transition model** ditulis `apply(s, a, d)`, diimplementasikan oleh
`BattleState.apply_action()`. Argumen `d` adalah damage yang benar-benar
terjadi, bukan damage rata-rata, dan itu disengaja: pemanggilan runtime
mengundi `random.randint(15, 20)` lalu meneruskan hasilnya, sehingga model
ini bisa dipakai dua kali. Deterministik bila `d` diberikan (dipakai
alpha-beta), dan stokastik bila `d` tidak diberikan (dipakai Expectimax dan
duel sungguhan). State lama tidak pernah dimutasi; `apply_action()`
mengembalikan hasil `replace()`. Eksperimen E1 sampai E4 memakai jalur
deterministik dengan `d` tetap, sedangkan E6 dan duel sungguhan membiarkan
`d` diundi.

### 2.3 Actions

`A = {ATTACK, DEFEND, POTION, SPECIAL}`, sehingga branching maksimal 4 dan
memenuhi batasan tugas. `legal_actions(s, is_max)` menyaring aksi yang
tidak mungkin dilakukan.

| Aksi | Syarat legal | Efek |
|---|---|---|
| ATTACK | selalu | kurangi `d` HP lawan, `d` acak 15..20; jadi `ceil(d/2)` bila lawan DEFEND |
| DEFEND | selalu | aktifkan DEFEND satu giliran lawan, damage lawan dipotong 50% |
| POTION | `pot > 0` | `+25` HP (maks 100), `pot - 1` |
| SPECIAL | `cd = 0` | kurangi 30 HP lawan (jadi 15 bila lawan DEFEND), `cd = 2` |

Kedua pihak punya keempat aksi, jadi branching atas tetap 4 dan pohonnya
simetris. Yang membuat pohon tidak simetris adalah ketersediaan aksi di tiap
node: potion dan SPECIAL hanya sah bila stok atau cooldown masih ada.

### 2.4 Terminal

`is_terminal(s)` benar bila `hp_p = 0` atau `hp_n = 0`. Keduanya mati
bersamaan dianggap seri dengan nilai 0.


### 2.5 Fungsi evaluasi

Semua evaluasi berorientasi NPC: skor positif berarti NPC unggul. Pada state
terminal:

```
u(s) = +WIN_SCORE   jika hp_p = 0
u(s) = -WIN_SCORE   jika hp_n = 0
u(s) =  0           jika keduanya 0
dengan WIN_SCORE = 1000
```

Pada state non-terminal ada tiga varian yang diuji:

| Nama | Bentuk |
|---|---|
| `hp_diff` | `hp_n - hp_p` |
| `balanced` | `hp_n - hp_p + 10(pot_n - pot_p) + 15*def_n - 15*def_p` |
| `threat_aware` | `balanced`, ditambah atau dikurangi 60 bila satu pihak tidak bisa selamat dari damage masuk berikutnya |

`balanced` adalah baseline produksi. Ketiga fungsi menambahkan
`_terminal_bonus(state)` di akhir, yaitu `+1000` bila Player mati dan `-1000`
bila NPC mati. Jadi bonus ancaman `threat_aware` hanya menggeser urutan
keputusan di state non-terminal, dan nilai terminal tetap persis `WIN_SCORE`.

**Bentuk linear berbobot.** Slide modul memberi eval generik
`EVAL(s) = w1*f1(s) + w2*f2(s) + ... + wn*fn(s)`. Ketiga varian di atas
memang instance dari bentuk itu, dengan `f` dan `w` sebagai berikut:

| Varian | `f1` | `w1` | `f2` | `w2` | `f3` | `w3` | `f4` | `w4` |
|---|---|---|---|---|---|---|---|---|
| `hp_diff` | `hp_n - hp_p` | 1 | - | - | - | - | - | - |
| `balanced` | `hp_n - hp_p` | 1 | `pot_n - pot_p` | 10 | `def_n` | 15 | `def_p` | -15 |
| `threat_aware` | `balanced` | 1 | `escapes_death(p) - escapes_death(n)` | 60 | - | - | - | - |

Bobot 10 dan 15 dipilih supaya efek satu potion atau satu DEFEND terasa
sekitar sepadan dengan 10 sampai 15 HP, yaitu sekitar satu giliran
pertahanan. Ini angka tebakan yang tidak dioptimasi; E2 mengukur akibatnya,
bukan membukankannya optimal.

**Tiga syarat eval dari slide modul**, dan bagaimana evaluator ini
memenuhinya:

| Syarat | Status di evaluator ini |
|---|---|
| Sejalan dengan utility di terminal: menang > seri > kalah | Terpenuhi. `_terminal_bonus` mengembalikan `±WIN_SCORE` persis, bukan aproksimasi. |
| Cepat | Terpenuhi. Fungsi eval adalah operasi aritmetika murni tanpa loop; terlihat di kolom `ms` E2 yang di bawah 1.2 ms per state pada kedalaman 4. |
| Berkorelasi dengan probabilitas menang | Terpenuhi sebagian, dan inilah yang diuji E5. Urutan profil di sana tidak sama dengan win rate, jadi korelasinya nyata tetapi tidak sempurna. |

Syarat ketiga memang yang paling sulit, dan E5 adalah cara mengukurnya:
bukan dengan menebak koefisien, melainkan dengan membiarkan duel dimainkan
seserhana mungkin.

### 2.6 Fungsi utility

NPC memaksimumkan `u`, Player mengambil nilai minimum:

```
V(s) = max_{a in A(s)} V(apply(s, a))   jika turn = NPC
V(s) = min_{a in A(s)} V(apply(s, a))   jika turn = Player
V(s) = u(s)                            jika terminal
```

Karena `u` berorientasi NPC, ketika root adalah giliran Player, Player
memilih aksi dengan skor terendah. Inilah alasan `think()` punya parameter
`root_is_npc`: tanpa itu, agen Player akan tanpa sadar memaksimumkan
keuntungan NPC. Eksperimen E5 memakai parameter ini agar lawannya
benar-benar bersaing.


---

## 3. Algoritma

### 3.1 Minimax

Eksplorasi penuh tanpa pemangkasan. Dipakai sebagai baseline kebenaran: setiap
algoritma lain diverifikasi menghasilkan aksi yang identik dengannya.

### 3.2 Alpha-Beta Pruning

Memakai `alpha` dan `beta` dengan pemangkasan `beta <= alpha` pada node MIN.
Setiap aksi root dievaluasi dengan jendela penuh `(-INF, INF)` agar skor tiap
cabang tetap eksak dan bisa ditampilkan di overlay tanpa bias pruning.

Alpha-beta bersifat order-independent pada level nilai: untuk state yang sama,
pemetaan `{aksi: skor}` dari semua aksi root harus identik apa pun urutan
eksplorasi. Yang berubah hanya tie-break saat dua aksi bernilai sama persis.
Eksperimen E3 dipakai untuk membuktikan klaim ini.

### 3.3 Early Stop

Dua bentuk diterapkan:

1. **`is_decided(s)`**, kondisi duel yang hasilnya sudah tidak dapat dibalik
   oleh aksi mana pun. Dasar: `escapes_death()` memeriksa apakah sebuah pihak
   masih bisa selamat dari damage masuk berikutnya memakai DEFEND dan POTION
   yang tersisa.
2. **Iterative deepening dengan `node_budget`**, menjalankan kedalaman 1, 2, 3,
   lalu berhenti begitu anggaran node habis. Hanya iterasi yang tuntas yang
   dipakai sebagai jawaban.

Bentuk pertama **heuristik dan tidak dijamin sound**. `escapes_death()` hanya
melihat satu giliran ke depan, jadi cabang yang dipangkas masih mungkin dapat
dibalik oleh gerakan berikutnya. Tidak ada pembuktian formal bahwa pemangkasan
ini mempertahankan nilai optimal. Bentuk kedua bersifat anytime: jawabannya
selalu ada walau belum optimal, jadi pemotongan di sini merusak kedalaman
pencarian, bukan kelangsungan jawaban.

Bentuk pertama punya bukti empiris, bukan hanya argumen. Pada state seimbang
dengan potion habis, `is_decided` aktif 5 sampai 6 kali dan membuat
`early_stop` memilih `ATTACK` (skor 42) padahal `SPECIAL` (skor 48) lebih
baik, sementara `minimax` dan `alpha-beta` tetap memilih `SPECIAL` dengan
`root_scores` yang identik. Pengukurannya ada di bagian 4. Config produksi
yang dipakai di semua pengukuran tersebut adalah `depth=4`,
`algorithm=alphabeta`, `eval=balanced`, `order=default`, sesuai
`DEFAULT_DEPTH`, `DEFAULT_ALGORITHM`, `DEFAULT_EVAL`, dan `DEFAULT_ORDER`
di `adversarial_ai.py`.

### 3.4 Move ordering

Empat urutan tersedia: `default`, `aggressive` (SPECIAL, ATTACK, POTION,
DEFEND), `defensive` (DEFEND, POTION, ATTACK, SPECIAL), dan `random`. Urutan
tidak boleh mengubah nilai, hanya memengaruhi berapa banyak node dieksplorasi.

Slide modul menyebut empat heuristik untuk mendekati urutan optimal:
iterative deepening, mendahulukan aksi yang menyerang bagian penting lawan,
killer move, dan coba-coba urutan. Yang diimplementasikan hanya iterative
deepening (dipakai di 3.3) dan urutan tetap per profil. Killer move belum
ada. Syarat "urutan tidak boleh mengubah nilai" di atas justru membuat
killer move tidak sepele di model ini, karena killer move memaksa sebuah
cabang dieksplorasi lebih awal dan memotong batasnya, sehingga
skor root harus tetap dijamin eksak. Ini tercatat di bagian 7.

### 3.5 Expectimax

Mengganti node MAX dan MIN di bagian yang acak. Damage ATTACK diundi dari
`ATTACK_OUTCOMES = [15..20]` dengan peluang sama besar. Pada node chance nilai
adalah rata-rata ekspektasi; pada node Player yang memperkirakan gerakan
Player, yang diambil adalah nilai ekspektasi terkecil.

Alpha-beta deterministik memakai `ATTACK_DAMAGE = 18`, sedangkan rata-rata
sebenarnya 15..20 adalah 17.5, jadi 18 adalah pendekatan satu poin.

Slide modul menyebut tiga tantangan Expectimax. Ketiganya nyata di duel ini:

| Tantangan | Bentuknya di duel ini |
|---|---|
| Magnitude | Skor utility bersifat win/lose, sementara damage hanya 15-20 HP dari 100. Satu node chance karena ATTACK menggeser nilai jauh lebih kecil daripada skala utility, sehingga rata-rata ekspektasi nyaris tenggelam di antara nilai-nilai diskret. |
| Order sensitivity | Rata-rata di node chance tidak pernah menjadi nilai ekstrem, sehingga tidak bisa dipangkas dengan aturan `alpha >= beta` yang sama seperti pada alpha-beta. |
| Pruning | Akibatnya pruning hampir tidak berhasil. Implementasi di sini memakai pencarian penuh tanpa pangkas, dan itu bagian dari alasan biayanya 37 kali alpha-beta di depth 4. |

### 3.6 Kompleksitas

Dengan `b` = branching dan `m` = kedalaman, minimax eksplorasi penuh
membutuhkan **waktu `O(b^m)`**. Slide modul memakai catur sebagai ilustrasi:
`b` sekitar 35 dan satu permainan berjalan sekitar 80 langkah, jadi `35^80`
tidak mungkin dihitung.

Untuk duel di laporan ini situasinya jauh lebih ringan: `b <= 4` dan `m <= 7`.
Angka eksperimen mengonfirmasi: minimax di depth 7 rata-rata 4628.7 node, bukan
`4^7 = 16384`, karena `legal_actions()` memangkas POTION dan SPECIAL saat stok
atau cooldown habis, sehingga branching efektif di bawah 4.

Alpha-beta menurunkan waktu ekspektasinya menjadi `O(b^(m/2))` dengan urutan
aksi yang baik. Slide modul memberi angka acuan untuk `b = 4, m = 8`, yaitu
`2 * 4^4 - 1 = 511` daun pada urutan terbaik, dibanding 65536 daun tanpa
pruning. E1 mengukur hal yang sama pada duel: hemat 78.8% di depth 7.

**Memori.** Klaim `O(b^m)` di slide modul mengasumsikan pohonnya ditabung
penuh. Implementasi di laporan ini memakai DFS rekursif yang hanya menyimpan
jalur yang sedang ditelusuri, jadi memorinya `O(m * b)`, yaitu `O(m)` untuk
`b` tetap, dengan stack terdalam 7 frame. Karena itu kedalaman dibatasi ke 7
karena alasan waktu, bukan karena kehabisan memori. Expectimax tidak mengubah
analisis memori, hanya menambah konstanta dan satu tingkat kedalaman karena
node chance punya 6 anak.


---

## 4. Debug overlay

Tombol `D` menampilkan atau menyembunyikan panel, tombol `C` mengaktifkan
tabel perbandingan. Isi panel:

1. Skor evaluasi tiap aksi di root dengan bar relatif, dan aksi yang dipilih.
2. Node count minimax versus alpha-beta, node terpangkas, persentase efisiensi
   pruning, jumlah cutoff, jumlah evaluasi daun, dan waktu kalkulasi.
3. Fungsi evaluasi dan urutan aksi yang sedang dipakai.
4. **Tabel perbandingan tiga algoritma** pada state yang sama: minimax,
   alpha-beta, dan early stop, lengkap dengan node, waktu, dan aksi yang
   dipilih masing-masing, ditambah indikator apakah ketiganya sepakat.

Mode perbandingan memanggil `compare_all()`, yang menelusuri pohon tiga kali,
jadi biayanya sekitar tiga kali pencarian biasa. Karena itu mode ini mati
secara default.

Penempatan panel bukan sekadar "bikin muat". Isi overlay dirender lebih dulu ke
permukaan terpisah, lalu permukaan itu diletakkan di area aman yang
dihindari dari panel status, menu aksi, dan battle log.

| resolusi | non-compare | compare | perilaku |
|---|---|---|---|
| 1920x1080 | 18 baris | 15 baris | muat di area aman |
| 1600x900 | 14 baris | 13 baris | muat, mulai padat |
| 1366x768 atau lebih kecil | 11-15 baris | 11-15 baris | modal penuh dengan latar redup |

Kriteria turun ke modal adalah tinggi baris efektif < 15 piksel, bukan
resolusi tetap. Pada 1366x768 isi linear tidak muat dengan legibilitas cukup,
jadi overlay berubah menjadi modal berlatar redup: duel tetap terlihat di
belakang, tapi overlay tidak lagi menabrak panel mana pun.

Tabel perbandingan di overlay diambil dari `compare_all()` yang dijalankan
sungguhan, jadi angkanya bisa diperiksa ulang. Berikut hasil ukurnya untuk
lima state dengan config produksi (`depth`, `alphabeta`, `balanced`, `default`):

| State | Depth | minimax | alpha-beta | early stop | hemat | aksi |
|---|---|---|---|---|---|---|
| Awal duel | 4 | 305 | 198 | 198 | 35.1% | sepakat |
| Awal duel | 5 | 1115 | 370 | 370 | 66.8% | sepakat |
| NPC unggul tipis | 4 | 276 | 232 | 214 | 15.9% | sepakat |
| NPC unggul jauh | 4 | 204 | 155 | 94 | 24.0% | sepakat |
| NPC unggul jauh | 5 | 748 | 363 | 319 | 51.5% | sepakat |
| Seimbang, potion habis | 4 | 100 | 82 | 68 | 18.0% | **tidak sepakat** |
| Seimbang, potion habis | 5 | 260 | 147 | 109 | 43.5% | **tidak sepakat** |
| Giliran Player | 4 | 280 | 212 | 212 | 24.3% | sepakat |
| Giliran Player | 5 | 1008 | 415 | 415 | 58.8% | sepakat |

Baris "tidak sepakat" itu bukan bug, dan justru bukti bahwa pemangkasan
`is_decided` memang tidak sound seperti diklaim di bagian 3.3. Pada state
seimbang dengan potion habis, `minimax` dan `alpha-beta` **selalu menghasilkan
aksi yang sama** dan `root_scores` yang identik, yaitu
`[('SPECIAL', 48), ('ATTACK', 42), ('DEFEND', 9)]` di depth 5. Yang menyimpang
hanya `early_stop`, yang memilih `ATTACK` skor 42 padahal ada `SPECIAL` skor
48. Jadi yang dirusak oleh `is_decided` adalah kualitas pilihan, bukan
kebenaran alpha-beta.

Kolom "hemat" juga perlu dibaca hati-hati. Early stop tidak selalu
menghemat: di state awal duel pada depth 4 dan 5, `early_stop` menghasilkan
node yang sama persis dengan alpha-beta, karena tidak ada cabang yang
memenuhi `is_decided`. Di state "NPC unggul jauh" early stop memangkas jauh
lebih banyak, dari 155 menjadi 94, justru di state ekstrem tempat kemenangan
sudah tidak dapat dibalik.

Geometri panel diuji pada resolusi 800x600 sampai 1920x1080, dan 1200 kasus
clipping otomatis tidak menemukan satu pun teks yang keluar dari panel.


---

## 5. Hasil eksperimen

### 5.1 E0. Horizon pencarian dan kondisi early stop

| player HP | kedalaman min. agar terminal terlihat |
|---|---|
| 100 | 10 |
| 90 sampai 70 | 8 |
| 60 sampai 50 | 6 |
| 48 sampai 35 | 4 |
| 30 ke bawah | 2 |

**Temuan utama.** Dengan HP penuh, terminal baru terlihat pada kedalaman 10,
sedangkan kedalaman produksi adalah 4. Artinya pada sebagian besar state,
cabang `WIN_SCORE` tidak pernah dieksplorasi. AI praktis berperilaku sebagai
heuristic berhorizon pendek, bukan sebagai pemain yang merencanakan cara
menang. Menaikkan kedalaman saja tidak cukup murah, karena biaya pencarian
tumbuh eksponensial (bagian 5.5).

Kondisi `is_decided` hanya terpenuhi sangat sempit: Player dengan HP 15 atau
10 **dan** tanpa potion. Begitu ada satu potion, Player masih bisa pulih dan
duel tidak diputuskan. Akibatnya early stop jarang aktif, dan
ini menjelaskan hematnya yang modest pada bagian 5.2.

### 5.2 E1. Minimax versus alpha-beta versus early stop

| depth | minimax | alpha-beta | hemat | early stop | hemat | hit |
|---|---|---|---|---|---|---|
| 1 | 3.2 | 3.2 | 0.0% | 3.2 | 0.0% | 0.0 |
| 2 | 12.9 | 12.9 | 0.0% | 12.3 | 4.8% | 0.2 |
| 3 | 43.7 | 39.4 | 9.9% | 36.6 | 16.3% | 0.4 |
| 4 | 140.3 | 101.9 | 27.4% | 94.2 | 32.9% | 1.2 |
| 5 | 454.6 | 217.3 | 52.2% | 197.4 | 56.6% | 2.7 |
| 6 | 1455.0 | 494.5 | 66.0% | 449.9 | 69.1% | 7.1 |
| 7 | 4628.7 | 982.1 | 78.8% | 876.0 | 81.1% | 16.6 |

Hemat alpha-beta terhadap minimax naik stabil bersama naiknya kedalaman,
dari 0% di kedalaman 2 menjadi 78.8% di kedalaman 7.
Pola ini konsisten dengan kompleksitas teoretis `O(b^d)` menjadi `O(b^(d/2))`
untuk alpha-beta dengan urutan aksi yang baik.

Early stop menambah hanya 2 sampai 3 poin di atas alpha-beta. Ini hasil yang
jujur dan layak dipertahankan di laporan: alpha-beta sudah memangkas sebagian
besar cabang yang tidak berguna, sementara kondisi `is_decided` terlalu sempit
untuk berkontribusi banyak.

Saran perbaikan untuk membuat early stop lebih berguna ada dua. Pertama,
longgarkan syarat `is_decided`: anggap duel sudah diputuskan bila selisih HP
sudah melebihi total damage yang bisa diberikan dalam satu siklus potion.
Kedua, pakai incremental deepening, karena memberi jawaban anytime.


### 5.3 E2. Perbandingan fungsi evaluasi

| evaluasi | node | eval | %ATK | %DEF | %POT | %SPC |
|---|---|---|---|---|---|---|
| hp_diff | 111.3 | 75.1 | 43.3 | 5.3 | 41.0 | 10.3 |
| balanced | 101.9 | 68.0 | 61.3 | 3.8 | 24.2 | 10.7 |
| threat_aware | 100.9 | 67.0 | 59.7 | 7.2 | 23.5 | 9.7 |

Matriks kesamaan keputusan:

| evaluasi | hp_diff | balanced | threat_aware |
|---|---|---|---|
| hp_diff | 100% | 80% | 78% |
| balanced | 80% | 100% | 93% |
| threat_aware | 78% | 93% | 100% |

Jumlah node hampir sama untuk ketiganya. Secara teori struktur pohon
ditentukan oleh `depth` dan `legal_actions`, sehingga evaluasi tidak boleh
mengubahnya. Selisih kecil yang muncul memang berasal dari alpha-beta:
syarat cutoff `beta <= alpha` membandingkan skor asli, jadi skala fungsi
evaluasi memengaruhi seberapa cepat jendela menyempit.

Perbedaan yang paling mencolok ada pada perilaku, bukan biaya. `hp_diff`
minum potion 41% waktu karena mengabaikan persediaan potion sama sekali.
`balanced` memangkas itu jadi 24% sekaligus menaikkan serangan jadi 61%.
`threat_aware` menambah defend menjadi 7.2%, sesuai desainnya.

### 5.4 E3. Perbandingan urutan aksi

| urutan | node | cutoff | ms | hemat | % skor identik | % aksi sama | % beda seri | beda nyata |
|---|---|---|---|---|---|---|---|---|
| default | 217.3 | 43.6 | 1.79 | +0.0% | 100.0% | 100.0% | 0.0% | 0 |
| aggressive | 136.5 | 37.9 | 1.26 | +37.2% | 100.0% | 71.8% | 28.2% | 0 |
| defensive | 381.8 | 55.9 | 3.61 | -75.7% | 100.0% | 89.7% | 10.3% | 0 |
| random | 214.8 | 42.5 | 1.93 | +1.1% | 100.0% | 82.7% | 17.3% | 0 |

Kolom `% skor identik` adalah bukti kebenaran alpha-beta: untuk semua urutan,
pemetaan `{aksi: skor}` di root identik. Kolom `% aksi sama` bisa di bawah 100%
karena tie-break mengikuti urutan, dan kolom `% beda seri` membuktikan bahwa
seluruh selisih itu berasal dari nilai yang sama. Contoh nyatanya: pada satu
state skor `ATTACK` dan `POTION` sama-sama -20, dan pada state lain `ATTACK`
dan `SPECIAL` sama-sama +1118. Semua perbedaan itu ekuivalen secara gameplay,
bukan kesalahan keputusan. Kolom `beda nyata` bernilai 0 di semua urutan.

`aggressive` menghemat 37.2% node karena menaruh SPECIAL dan ATTACK lebih
dulu, dua aksi yang biasanya menang besar. `defensive` justru menambah biaya
75.7%. Menariknya urutan acak hampir secepat default di kedalaman 5.


### 5.5 E4. Kedalaman pencarian

| depth | node | ms | sama dgn depth 7 |
|---|---|---|---|
| 1 | 3.2 | 0.03 | 73.5% |
| 2 | 12.9 | 0.11 | 81.8% |
| 3 | 39.4 | 0.31 | 64.5% |
| 4 | 101.9 | 0.93 | 68.8% |
| 5 | 217.3 | 2.09 | 72.5% |
| 6 | 494.5 | 4.45 | 76.3% |
| 7 | 982.1 | 9.10 | 100.0% |

Dua hal menarik di sini. Pertama, jumlah node naik sekitar 2.2x per ply, sesuai
`O(b^(d/2))` untuk `b` efektif sekitar 2. Kedua, kesamaan keputusan dengan
depth 7 **tidak monotonik**: depth 2 cocok 81.8%, tetapi depth 3 hanya 64.5%.
Artinya menambah kedalaman tidak selalu memperbaiki keputusan pada state yang
sama, karena yang berubah adalah urutan tie-break dan hasil horizon, bukan
kualitasnya secara monoton.

Kedalaman produksi 4 sampai 5 (sekitar 0.9 sampai 2.1 ms per state) adalah titik
kompromi yang masuk akal: memberi 68.8 sampai 72.5% kesamaan dengan depth 7
dengan biaya di bawah 2.2 ms. Untuk duel yang satu giliran berbasis timer,
di bawah 2.2 ms berarti tidak terasa oleh pemain.

### 5.6 E5. Perilaku NPC terhadap berbagai lawan

Tiga lawan: `greedy` (serang kalau bisa), `random` (acak sah), dan `ai` (NPC
seperti produksi, tapi dipakai sebagai Player-min dengan `root_is_npc=False`).

| lawan | profil | stalemate | menang (decided) | menang (semua) | kalah |
|---|---|---|---|---|---|
| greedy | aggressive | 0.0% | 0.0% | 0.0% | 100.0% |
| greedy | balanced | 0.0% | 5.0% | 5.0% | 95.0% |
| greedy | defensive | 0.0% | 1.7% | 1.7% | 98.3% |
| greedy | opportunist | 0.0% | 0.0% | 0.0% | 100.0% |
| random | aggressive | 0.0% | 75.0% | 75.0% | 25.0% |
| random | balanced | 0.0% | 90.0% | 90.0% | 10.0% |
| random | defensive | 0.0% | 88.3% | 88.3% | 11.7% |
| random | opportunist | 0.0% | 81.7% | 81.7% | 18.3% |
| ai | aggressive | 41.7% | 94.3% | 55.0% | 3.3% |
| ai | balanced | 0.0% | 91.7% | 91.7% | 8.3% |
| ai | defensive | 0.0% | 43.3% | 43.3% | 56.7% |
| ai | opportunist | 1.7% | 100.0% | 98.3% | 0.0% |

Kolom `menang (decided)` mengabaikan duel yang masih berjalan sampai batas 80
ply, sedangkan `menang (semua)` menghitungnya sebagai 0. Kolom itu penting
karena beberapa profil sengaja tidak menyelesaikan duel.

Temuan paling penting ada di baris `ai`. Terhadap `greedy` dan `random`,
semua profil menang tinggi, jadi metrik itu tidak membedakan kualitas.
Terhadap `ai` yang rasional, baris-baris ini baru informatif:

- **`balanced` menang 91.7%** dan tidak pernah stalemate. Ini baseline yang
  dipakai produksi.
- **`aggressive` hanya 55.0%** jika duel yang belum selesai dihitung kalah, dan
  41.7% duel tidak pernah selesai dalam 80 ply. Agresif itu mengorbankan
  ketahanan, jadi duelnya bisa menggantung melawan NPC defensif.
- **`defensive` kalah 56.7%**. Terlalu banyak DEFEND (27.9%) dan tidak cukup
  pernah menyerang.
- **`opportunist` menang 98.3%** dan hanya 1.7% stalemate: profil paling kuat
  di benchmark ini.

Catatan: `ai` bukan lawan yang kuat secara absolut (hanya menang 0% sampai
5% terhadap `greedy`), tapi ia cukup rasional untuk menguji strategi
NPC. Karena itu E5 harus dibaca terutama pada blok `ai`.


### 5.7 E6. Expectimax

| depth | node alpha-beta | node expectimax | rasio | ms alpha-beta | ms expectimax | aksi sama |
|---|---|---|---|---|---|---|
| 1 | 3.2 | 8.2 | 2.55 | 0.03 | 0.07 | 96.8% |
| 2 | 12.9 | 68.8 | 5.35 | 0.11 | 0.61 | 96.3% |
| 3 | 39.4 | 525.0 | 13.33 | 0.41 | 4.39 | 91.7% |
| 4 | 101.9 | 3773.8 | 37.03 | 0.98 | 30.52 | 91.7% |

Expectimax jelas tidak sepadan. Rasio node tumbuh dari 2.55 di depth 1 menjadi
37.03 di depth 4, karena setiap node ATTACK pecah menjadi 6 cabang hasil.
Waktu di depth 4 adalah sekitar 30.5 ms, sekitar 31 kali alpha-beta, sehingga
tidak layak untuk produksi pada model duel saat ini.

Kolom `aksi sama` perlu dibaca dengan hati-hati. Nilai 91.7% berarti
expectimax memilih aksi berbeda pada sekitar 8% state, tetapi itu **bukan
bukti bahwa alpha-beta salah**. Alpha-beta memakai `ATTACK_DAMAGE = 18`,
sedangkan expectimax memakai rata-rata 17.5. Perbedaan 0.5 HP itu cukup
untuk membalik pilihan pada state yang ketat. Alpha-beta di sini mengutamakan
kecepatan, bukan expectimax yang selalu benar.

Kesimpulan praktisnya: expectimax baru masuk akal kalau damage acak
menjadi komponen dominan. Untuk duel dengan empat aksi dan horizon 4, biaya
membayar 6 outcome per serangan terlalu besar dibanding manfaatnya.

### 5.8 E7. Branching 3 versus branching 4

Tugas menyebut tiga aksi per giliran (`attack`, `defend`, `potion`) dengan
batas `branching <= 4`. Implementasi produksi memakai empat aksi karena
`SPECIAL` saya tambahkan sebagai fitur sendiri. Pertanyaannya: apakah tambahan
itu searing biaya yang dibayar, dan apakah tugas tetap terpenuhi tanpa ia.

E7 diukur dengan subclass `NoSpecialState` yang men-filter `SPECIAL` dari
`legal_actions()`, sehingga branching turun ke tiga tanpa mengubah
`BattleState` produksi.

| branching | node | ms | NPC menang | seri | belum selesai | distribusi aksi root |
|---|---|---|---|---|---|---|
| 3 (tanpa SPECIAL) | 46.9 | 0.46 | 40.0% | 0.0% | 60.0% | ATTACK 81.2% DEFEND 2.2% POTION 16.7% |
| 4 (produksi) | 101.9 | 0.98 | 93.3% | 0.0% | 6.7% | ATTACK 61.3% DEFEND 3.8% POTION 24.2% SPECIAL 10.7% |

Dua hal terbaca dari tabel ini.

Pertama, harganya murah dan sebanding. Node naik dari 46.9 ke 101.9, jadi
sekitar 2.2 kali, dan waktu naik dari 0.46 ke 0.98 ms per state. Pada duel
yang satu giliran per giliran, tambahan 0.5 ms tidak terasa. Batas
`branching <= 4` juga tetap respected, karena empat sudah berada tepat di
batas.

Kedua, buahnya besar dan bukan sekadar kosmetik. Tanpa `SPECIAL` hanya 40%
duel yang dimenangkan dalam 80 ply, sedangkan 60% menggantung. Dengan
`SPECIAL` tingkat kemenangan naik ke 93.3%. Penyebabnya terlihat di kolom
distribusi: tanpa `SPECIAL`, agent hampir selalu bermain `ATTACK` (81.2%),
sehingga duel berubah menjadi saling tukar serangan kecil tanpa cara keluar.
`ATTACK` hanya memberi 15-20 damage, sedangkan `SPECIAL` memberi 30 damage
dalam satu giliran, jadi ia menyediakan cara menutup duel yang tidak bisa
ditutup `ATTACK` biasa. AI langsung memakainya 10.7% waktu.

Perlu dicatat bahwa `SPECIAL` bukan aksi yang selalu unggul:
`SPECIAL_COOLDOWN = 2` berarti setelah dipakai aksi itu tidak tersedia
selama dua giliran, dan `DEFEND_REDUCTION` memotongnya kalau lawan sedang
bertahan. Jadi biaya sebenarnya bukan hanya node, melainkan juga satu giliran
regenerasi yang hilang. Karena itu pemakaian 10.7% bukan pemborosan, melainkan
pola "hajar berat sekali, lalu tablur dua giliran".

Kesimpulannya: `SPECIAL` layak dipertahankan sebagai fitur tambahan, dan
branching tiga aksi tetap bisa dipresentasikan sebagai baseline pembanding.
Yang perlu jujur disebut adalah bahwa win rate tinggi pada branching
empat tidak hanya datang dari algoritma yang lebih baik, melainkan juga dari
ruang aksi yang lebih besar; E7 itulah yang memisahkan kedua pengaruh itu.

---

## 6. Ringkasan temuan

1. **Kecepatan utama datang dari alpha-beta.** Hemat node naik dari 0%
   di depth 2 menjadi 78.8% di depth 7, dan pada depth 7 waktu turun dari
   37.05 ms menjadi 8.57 ms, sekitar 4.3 kali lebih cepat. Ini hampir gratis,
   karena tidak ada perkiraan yang dikorbankan.
2. **Move ordering adalah pengali, bukan toggle.** `aggressive` menambah
   37.2% penghematan tanpa mengubah satu pun nilai aksi. Urutan yang buruk
   (`defensive`) justru menambah 75.7% biaya.
3. **Fungsi evaluasi dominan secara perilaku, kecil secara biaya.**
   `hp_diff` dan `balanced` berbeda pada 20% state dengan selisih node
   kurang dari 10%, dan `balanced` memangkas potion dari 41% ke 24%.
4. **Early stop jujur tapi modest.** Menambah 2 sampai 3 poin di atas
   alpha-beta. Kondisi `is_decided` hanya aktif pada kasus ekstrem
   (HP 15 atau 10 tanpa potion), jadi sebagian besar kasus belum bisa diputuskan.
5. **Horizon adalah batas utama kualitas, bukan pruning.** Terminal baru
   terlihat di depth 10 pada HP penuh, sedangkan produksi memakai depth 4.
   Apa yang diperbaiki pruning adalah biaya, bukan seberapa jauh AI melihat.
6. **Kedalaman tidak monoton.** Depth 2 lebih sering cocok dengan depth 7
   (81.8%) daripada depth 3 (64.5%). Menambah kedalaman tidak selalu
   memperbaiki keputusan.
7. **Strategi, bukan kecepatan, menentukan hasil duel.** Terhadap `ai`,
   rentang win-rate antar profil adalah 43.3% sampai 98.3%, sementara
   perbedaan biaya antar profil cuma satu orde magnitude.
8. **Stalemate adalah mode gagal tersendiri.** Profil `aggressive`
   menggantung 41.7% duel, yang tidak terlihat kalau yang dihitung hanya
   duel yang selesai.
9. **Ruang aksi berperan lebih besar daripada algoritma.** Menurunkan
   branching dari 4 ke 3 (E7) **menurunkan** biaya node dari 101.9 menjadi
   46.9, yaitu sekitar 2.2 kali lebih murah, tetapi sekaligus menurunkan
   win rate dari 93.3% ke 40.0% karena 60% duel tidak pernah selesai. Jadi
   sebagian besar selisih win rate antara profil di E5 adalah soal ruang aksi
   dan fungsi evaluasi, bukan soal algoritma pencarian.


---

## 7. Keterbatasan pekerjaan ini

1. **Benchmark state acak bukan distribusi gameplay.** 600 state diambil
   acak, bukan dari duel yang benar-benar dimainkan. State yang jarang muncul
   saat pemain manusia bermain bisa jadi terlalu sering di sini.
2. **Win-rate saja bukan ukuran kualitas.** E5 hanya mengukur win-rate. Tidak
   mengukur rasa permainan, misalnya duel yang menang tapi terasa tidak adil
   karena NPC selalu aman.
3. **Self-play untuk E5 dan E7.** Lawan `ai` memakai heuristik dan kedalaman
   yang sama dengan NPC (`simulate_duel()` membangun NPC di `depth=3` untuk
   pemain dan `depth=4` untuk NPC di mode produksi), jadi hasilnya bisa saling
   mengonfirmasi. Ini bukan self-play kedalaman sama, dan opponent yang
   benar-benar independen akan memberi angka berbeda.
4. **Horizon tetap.** Semua hasil berlaku untuk depth 4 sampai 7. Pada depth
   10 kesimpulannya berubah, karena itu baru menyentuh terminal.
5. **Satu jenis ketidakpastian.** Damage acak dimodelkan, tapi tidak ada
   ketidakpastian informasi atau sebagian observability.
6. **`escapes_death()` memakai batas atas damage.** Fungsi itu menganggap
   penyerang tidak memilih DEFEND, jadi `incoming_damage` adalah batas atas,
   bukan damage yang pasti. Akibatnya `threat_aware` bisa menganggap suatu
   pihak aman padahal tidak.
7. **Batas 80 ply pada duel.** Duel yang belum selesai dihitung sebagai
   bukan kemenangan, yang bisa tidak adil bagi profil yang suka menggantung.
8. **Beban overlay.** Mode perbandingan menelusuri pohon tiga kali. Itu
   hanya untuk diagnostik, bukan jalur produksi.
9. **`is_decided` tidak dijamin optimal.** Hanya melihat satu giliran,
   sehingga bisa memangkas cabang yang masih dapat dibalik. Karena itu
   hemat early stop pada bagian 5.2 tidak boleh dibaca sebagai jaminan
   bahwa nilainya sama dengan pencarian penuh.
10. **Killer move belum diimplementasikan.** Dari empat heuristik urutan aksi
    di slide modul, hanya iterative deepening yang dipakai. Urutan `aggressive`
    masih urutan statis, belum belajar dari cabang mana yang dulunya baik.
11. **Bobot eval tidak dioptimasi.** Koefisien 10, 15, dan 60 pada bagian 2.5
    dipilih dengan penalaran, bukan pencarian. E2 dan E5 mengukur akibatnya,
    tetapi belum mencari koefisien yang terbaik.

---

## 8. Reproduksi

Seluruh angka berasal dari satu perintah, dijalankan dari direktori proyek:

```
python experiments.py --out hasil_eksperimen.md --log-csv duel_log.csv
```

Opsi lain yang tersedia:

```
python experiments.py --only E1 E5     # jalankan eksperimen tertentu saja
python experiments.py --only E7         # hanya perbandingan branching 3 vs 4
python experiments.py --quick          # lebih sedikit state, untuk iterasi cepat
python experiments.py --help           # daftar lengkap opsi
```

Uji kebenaran alpha-beta ada langsung di modul utama:

```
python adversarial_ai.py
```

Perintah itu membandingkan aksi alpha-beta dengan minimax pada kedalaman 1
sampai 6, lalu mencetak perbandingan node ketiga algoritma dan rata-rata
damage ATTACK. Keluarannya harus menunjukkan node alpha-beta selalu lebih
sedikit atau sama dengan minimax, aksi selalu sama, dan mean damage 17.50.

Isi `hasil_eksperimen.md` adalah output langsung perintah pertama, tanpa
angka yang diedit tangan, sehingga angka utama bagian 5 bisa dicocokkan dengan
file itu. Perlu satu catatan: kolom node, skor, dan persentase bersifat
deterministik dan selalu sama untuk seed yang sama, sedangkan kolom `ms`
berubah-ubah mengikuti beban mesin. Angka waktu di laporan ini adalah
ukuran dari satu run dan bisa berbeda di run berikutnya, sementara seluruh
angka lain harus identik.

Determinisme tersebut sudah diverifikasi, bukan hanya diklaim. Dua kali
berurutan atas `hasil_eksperimen.md` dibandingkan baris per baris, dan yang
berbeda hanya kolom `ms`; kolom node, eval, persentase, dan distribusi aksi
identik. `duel_log.csv` juga dibandingkan per kombinasi
`duel|ply|action|score|nodes` dan seluruh 814 barisnya identik.

`duel_log.csv` ditulis **per giliran NPC**, bukan satu baris per duel. Setiap
baris menyimpan nomor giliran (`ply`), keadaan duel sebelum NPC bertindak, aksi
yang dipilih, skornya, dan statistik pruning. Baris penutup tiap duel ditandai
`is_last=True`. Jadi file itu bisa dipakai untuk menganalisis kapan AI
memilih potion atau DEFEND sepanjang duel, bukan hanya hasil akhirnya.
