# Panduan demo 5–7 menit (asistensi Ambush Director)

Siapkan: `python main.py`, musuh sudah muncul (tunggu ~8 dtk), F3 siap.

## 0:00 — NPC mendekat & persiapan (1 mnt)

- Gerakkan player ke dekat musuh (atau diam, musuh mengejar via A*).
- Saat jarak ≤1: game dijeda → **PREP_PLAYER**. Pilih 2 item
  (Kiri/Kanan ganti, Atas/Bawah slot), Enter.
- Katakan: "Duel 1 lawan antrean 2–4 musuh; HP dan potion terbawa."

## 0:60 — CSP bertahap (1,5 mnt)

- Nyalakan F3 (otomatis mode demo SEED RANDOM). Tab T = CSP.
- Tekan F4 sampai `step`, tekan Spasi berulang: slot terisi satu per satu.
- Tunjuk log: `CSP isi ROLE_2=... ✓`, `... X melanggar: ...`,
  `AC-3 hapus ... -> domain 6->5`, `backtrack`.
- Jelaskan MRV ("domain terkecil dulu"), LCV ("paling sedikit membuang"),
  AC-3 (REVISE + antrean arc).
- Matikan MRV/LCV/AC-3 (Q/W/E/R), tekan G: tunjukkan nodes berubah
  (bandingkan dengan panel CMP nanti).

## 2:30 — Local search (1,5 mnt)

- Tunggu fase LOCAL SEARCH (atau Enter bila sudah REVIEW lalu G).
- TAB untuk ganti algoritma (HC → SA): tunjukkan baris SA
  (`T/dE/p/u TERIMA-TOLAK`) dan "langkah buruk diterima" saat muncul.
- Tekan C (target 0.40→0.50→0.80→ADAPTIF) + G: tunjukkan antrean akhir
  berubah (target tinggi = musuh lebih banyak/kuat).
- Tekan X (BEST): tunjukkan seed berubah; bila "LS dilewati…",
  jelaskan seed sudah dalam toleransi.

## 4:00 — Panel perbandingan (0,5 mnt)

- Di REVIEW, tunggu "menghitung n/11" → 5 LS + 6 CSP terisi.
- Baca: SA vs HC (gap/eval/ms), polos vs +AC-3 (nodes/backtrack).

## 4:30 — Battle berurutan (1,5 mnt)

- Enter → **DUEL 1/k** (judul + baris "Sekarang melawan: X | Berikutnya: Y |
  Sudah kalah: ..."). Menangkan duel (atau mainkan), lalu saksikan **LAYAR
  HASIL** ("HASIL DUEL 1/k — MENANG", lawan tadi, sisa HP, dan musuh
  berikutnya + efeknya). Layar ini **menunggu Enter** (tidak lanjut otomatis).
  Baris "kamu masuk duel berikutnya dengan HP …" **sudah dihapus** karena
  tiap duel antrean selalu mulai dengan darah penuh. Tekan H untuk HUD.
- Tunjuk log pemicu buff ("Healer NPC memulihkan 3 HP") + panel berkedip.
- Menang semua → "ANTREAN TUNTAS!"; kalah → "PERTEMUAN BERAKHIR" (keduanya
  menunggu Enter lalu kembali ke EXPLORE). `data/battle_result.csv` bertambah
  1 baris.
- **Musuh selalu beda**: dalam satu pertemuan tak ada peran musuh yang
  muncul dua kali; di pertemuan berikutnya (musuh baru mengejar di peta)
  peran musuh pertemuan sebelumnya tidak dipakai lagi. Animasi demo
  (slow/step) juga ikut tampil lagi — Enter (SIAP) hanya menuntaskan run
  saat itu, pump mode tidak dipaksa jadi instant.
- **Musuh di peta = karakter Boss**: yang mengejar di peta adalah satu
  sprite karakter **Boss** (perilaku awal satu musuh, tapi tampilannya
  Boss). "Anak buahnya" baru dipanggil di battle mode: begitu pertemuan
  dimulai, animasi PREP menampilkan CSP + local search menyusun antrean
  (2..4 musuh, sprite peran tiap duel diambil dari antrean). Boss ikut jadi
  lawan hanya bila pencarian menaruhnya di slot terakhir (wins ≥ 3) — bukan
  dijadwalkan tetap; pada uji 96 rencana murni Boss memang tidak pernah
  terpilih (selalu kalah anggaran), jadi pertemuan ber-Boss jarang.

## 6:00 — CSV (0,5 mnt)

- Buka `data/csp_trace.csv`, `ls_trace.csv`, `battle_result.csv`:
  angka overlay == baris CSV (ada tesnya).

## Tanya-jawab dosen (jawaban singkat berbasis proyek)

1. **Mengapa MRV?** Variabel tersempit dulu → gagal cepat → hemat.
2. **Mengapa AC-3 identik FC di sini?** Semua revise menyentuh tetangga
   langsung variabel ter-assign (propagasi cukup kedalaman-1) + pass awal
   tak menemukan apa-apa; AC-3 tetap jaring pengaman struktural.
3. **Mengapa +MRV/degree merugikan?** Degree memilih klik ITEM (derajat 4)
   sebelum ROLE-nya dikenal → incompat beruntun; urutan indeks (ROLE dulu)
   kebetulan benar.
4. **Mengapa heuristik hanya pra-penyaring?** Korelasi 0.54–0.64 < 0.85;
   peringkat lumayan (pairwise 0.75–0.93) tapi skala tak dipercaya.
5. **Mengapa crossover valid?** Kromosom per-slot berurutan; single-point
   antar-slot memindahkan blok anggota utuh (koherensi + urutan).
6. **Mengapa target 0.3 tak terjangkau?** Lantai struktural: carry
   (musuh segar + potion terbawa + rest 0) membuat sapuan penuh hampir
   mustahil; wilayah Minion-padat terlalu tipis (<10% sampel). Diganti
   0.40 berbasis data (14,7%).
7. **Apa arti progres 0.5?** Rata-rata fraksi duel dimenangkan (bukan
   peluang sapu-bersih); biner dicatat terpisah.
8. **Kapan CSP cukup vs LS perlu?** Seed dalam toleransi → LS dilewati
   (tertulis); jauh → LS memperbaiki (seed→akhir di overlay).
9. **Seberapa cepat?** CSP ~3–8 ms, LS ~1 dtk, instant total <2 dtk
   (batas 3 dtk); sim penuh hanya rerank.
10. **Validasi lawan manusia?** Belum — MAE terhadap pemain simulasi
    (tertulis di README); target adaptif memakai progres agar adil.
