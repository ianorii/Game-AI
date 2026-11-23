# Panduan Lengkap & Naskah Video Demonstrasi Game AI: Eldoria
## Automated Planning & Decisions Under Uncertainty (DUU)

Panduan ini dibuat khusus untuk membantu kamu merekam video demonstrasi proyek Game AI dengan lancar, percaya diri, dan menarik. Bahasanya sudah disesuaikan agar **enak didengar, mengalir natural (tidak kaku seperti membaca buku teks), tetapi tetap mempertahankan ketepatan teknis dan istilah AI yang bernilai akademis tinggi.**

---

## 1. Rencana Alur & Durasi Video (Total: 5–7 Menit)

Berikut susunan alur rekaman video yang seimbang dan sistematis:

| Menit | Bagian Video | Aksi di Layar | Poin Kunci yang Disampaikan |
| :---: | :--- | :--- | :--- |
| **00:00 - 00:45** | **1. Pembukaan & Pengantar** | Hero bergerak santai di desa (WASD), overview pulau. | Sapaan ramah, perkenalan diri, tujuan demo: integrasi **Automated Planning** dan **DUU**. |
| **00:45 - 01:45** | **2. STRIPS Expedition Planner** | Tekan `[F9]` (Advisor), lalu `[SPACE]` (Auto-pilot). | Bedakan panduan cerdas (Advisor) vs gerak mandiri (Auto) untuk misi 37 langkah. |
| **01:45 - 02:45** | **3. Bedah Debug Overlay Planning [F7]** | Tekan `[F7]`, sorot Tab Planning & Heuristik. | Jelaskan 3 Card: Tujuan & Progres, Aksi Aktif STRIPS, Mesin Pencari WA* ($h_{FF}$). |
| **02:45 - 03:45** | **4. HTN Rutinitas Warga Desa** | Kamera ke ladang (Pak Tani) & kincir (Kang Penggiling). Buka tab HTN di overlay. | Dekomposisi tugas hierarkis SHOP-style, operator primitif, dan water safety guard. |
| **03:45 - 05:15** | **5. Live Combat Goblin & Overlay DUU [F8]** | Dekati goblin liar di luar desa, amati pertempuran, buka overlay `[F8]`. | **Paling interaktif!** Jarak chase 240px, update probabilitas Bayes, tombol MEU nyala hijau/merah, histeresis. |
| **05:15 - 06:15** | **6. Pembuktian via Terminal / CLI** | Pindah ke jendela terminal, jalankan unit test & validasi laporan. | Tunjukkan bukti 29 test case inti lulus 100% dan verifikasi integritas sistem `check_report.py`. |
| **06:15 - 07:00** | **7. Penutup & Rangkuman** | Kembali ke tampilan game, hero di desa. | Kesimpulan integrasi sistem cerdas, ucapan terima kasih yang ramah. |

---

## 2. Bedah Mendalam Dua Debug Overlay Utama

Bagian ini adalah kunci penjelasan saat kamu membuka panel overlay di layar:

### A. Debug Overlay Planning `[F7]`
Saat menekan tombol `[F7]`, jendela *Unified Planning Inspector* akan muncul di sisi kanan layar. Jelaskan elemen-elemen berikut:
1. **Card 1: Tujuan & Progres (Goal Checklist)**
   - Ada 3 checkbox tujuan misi: `gate_key` (kunci dibuat), `gate_open` (gerbang terbuka), dan `boss_defeated` (bos obsidian dikalahkan).
   - Menampilkan *progress bar* visual dan status jumlah langkah ekspedisi (misalnya: *Langkah 0/39*), estimasi total biaya waktu (*118.1 detik*), dan jumlah replanning yang aktif.
2. **Card 2: Aksi Aktif (STRIPS Grounded Action)**
   - Menampilkan aksi simbolik STRIPS yang sedang atau akan dieksekusi, contoh: `goto(spawn, shop)` atau `buy_seed_radish(c20, c15)`.
   - **Precondition**: Kondisi dunia yang wajib terpenuhi sebelum aksi jalan (misal: hero harus berada di lokasi asal dan jalurnya terkoneksi).
   - **Effect (Add/Delete list)**: Perubahan fakta dunia setelah aksi tuntas (misal: hero tiba di lokasi baru dan meninggalkan lokasi lama).
   - **State Diff**: Catatan delta perubahan kondisi tas dan lingkungan secara real-time.
3. **Card 3: Mesin Pencari Weighted A\* & Antrean**
   - **Bobot Heuristik**: $w = 1.5$ (Weighted A\* yang seimbang antara kecepatan komputasi dan optimasi rute).
   - **Fungsi Heuristik**: Menggunakan $h_{FF}$ (*Fast-Forward Relaxed GraphPlan*) yang mengabaikan delete-list untuk memandu pencarian tanpa tersesat.
   - **Metrik Kinerja**: Menampilkan jumlah node yang diekspansi (~900 node) dan waktu pencarian kilat (hanya sekitar 1.1 ms per frame, jauh di bawah batas *budget* 20 ms).
   - **Invarian**: Validasi rute fisik geodesik terhadap jarak Manhattan dan status replanning IDLE.

---

### B. Debug Overlay Decisions Under Uncertainty (DUU) `[F8]`
Saat menekan tombol `[F8]`, jendela analitik ketidakpastian terbuka. **Overlay ini sekarang bersifat live dan interaktif terhadap musuh goblin liar:**
1. **Card 1: Minion Goblin - Inferensi Bayes**
   - **Status Badge Dinamis**:
     - Jika tidak ada goblin dekat: badge hijau `[PATROL/AMAN]` (*Wilayah aman*).
     - Jika goblin mendekat ($\le 280\text{ px}$): badge oranye `[TERDETEKSI]` / `[MENGEJAR]` lengkap dengan nama goblin, jarak real-time (misal: *Dist: 40px*), dan state goblin saat itu.
     - Jika goblin mengayunkan serangan: badge merah menyala `[SERANG!]`.
   - **Probabilitas Prior $P(\text{Elit})$**: Bernilai awal `0.20` (artinya ada peluang 20% goblin yang ditemui bertipe Elit).
   - **Bukti Observasi ($E$)**:
     - Bila terkena serangan goblin biasa: terdeteksi `Hit: 3 DMG (Biasa)` $\rightarrow$ posterior $P(\text{Elit} \mid E)$ seketika turun ke **$8.6\%$** dan badge bawah berubah hijau `[TIPE: BIASA]`.
     - Bila terkena serangan goblin elit: terdeteksi `Hit: 6 DMG (Elit)` $\rightarrow$ posterior $P(\text{Elit} \mid E)$ langsung melonjak ke **$46.7\%$** (atau $>75\%$ pada hit berikutnya), dan badge berubah menjadi `[TIPE: ELIT]`.
2. **Card 2: Kebijakan Risiko MEU (*Maximum Expected Utility*)**
   - **Kapsul Ruang Aksi $A = \{\text{ENGAGE}, \text{EVADE}, \text{HEAL}\}$**:
     - Tombol-tombol aksi di sini **menyala secara otomatis** mengikuti aksi terbaik $\arg\max_a EU(a)$!
     - Bila HP Hero tinggi ($\ge 35\%$): tombol `ENGAGE +5.9` menyala hijau tebal dengan badge `[REKOMENDASI: ENGAGE]`.
     - Bila HP Hero kritis ($< 25\%$): nilai utilitas bertarung menjadi negatif drastis ($EU = -12.4$), sehingga tombol `EVADE -1.5` otomatis **menyala merah tebal** dengan badge `[REKOMENDASI: EVADE]`.
     - Bila membawa ramuan dan sekarat: tombol `HEAL` akan diprioritaskan.
   - **Kondisi HP & Probabilitas Menang $P(\text{win})$**:
     - Dihitung kontinu melalui fungsi sigmoid terkalibrasi: $P(\text{win} \mid \text{HP}_{\text{hero}}, \text{Musuh})$.
   - **Ambang Titik Impas Matematis ($P^*$ dan $HP^*$)**:
     - Derivasi eksak: $P^* = \frac{U(\text{evade}) - U(\text{death})}{U(\text{loot}) - U(\text{death})} = \frac{-1.5 - (-20)}{5.5 - (-20)} = \frac{18.5}{25.5} = \mathbf{72.55\%}$.
     - Melalui inversi sigmoid, didapatkan ambang HP kritis: $\mathbf{HP^* = 35.0\%}$.
   - **Mekanisme Histeresis $10\%$**:
     - Mencegah keputusan bolak-balik (*thrashing*). Hero yang sudah bertarung (*engaged*) akan tetap bertahan menyerang selama HP $\ge 25\%$, dan baru diperintahkan kabur jika HP benar-benar drop di bawah $25\%$.
3. **Card 3: Formulasi Formal DUU Minion**
   - Menampilkan ringkasan kaidah keputusan formal $\arg\max_a EU(a)$, titik impas $P^* = 72.55\%$, ambang batas $HP^* = 35.0\%$, serta tiga baris verifikasi invarian berstatus hijau `[OK]`.

---

## 3. Naskah Percakapan Video (Siap Baca & Mengalir Natural)

Gunakan naskah ini saat merekam suara (*voiceover* atau bicara langsung di depan mikrofon). Tanda kurung siku `[seperti ini]` adalah panduan aksi yang harus kamu lakukan di layar game.

---

### Segmen 1: Pembukaan & Gambaran Umum (00:00 – 00:45)
> *"Halo semua! Selamat datang di video demonstrasi Game AI untuk proyek game action-RPG 2D kita, **Eldoria**.*  
>  
> *[Gerakkan Hero sedikit keliling desa menggunakan tombol WASD]*  
>  
> *Di video kali ini, saya ingin menunjukkan bagaimana dua konsep kecerdasan buatan modern diterapkan secara harmonis di dalam satu game loop yang hidup.*  
>  
> *Yang pertama adalah **Automated Planning**, di mana kita memadukan perencana simbolik STRIPS untuk memandu misi petualangan Hero, serta Hierarchical Task Network atau HTN untuk rutinitas mandiri para warga desa.*  
>  
> *Dan yang kedua adalah **Decisions Under Uncertainty (DUU)**, yaitu pengambilan keputusan berbasis probabilitas Bayes dan Maximum Expected Utility saat Hero berhadapan dengan ancaman musuh goblin liar di alam bebas.*  
>  
> *Yuk, langsung saja kita lihat bagaimana sistem ini bekerja!"*

---

### Segmen 2: STRIPS Expedition Planner — Advisor vs Auto (00:45 – 01:45)
> *"Pertama, kita bahas sistem **Automated Planning pada Hero**.*  
>  
> *Tujuan utama Hero di game ini adalah melakukan ekspedisi panjang: mengumpulkan material kayu dan batu, membeli benih dan botol di toko desa, menanam lobak, meracik potion, membuat kunci, dan membuka gerbang menuju Obsidian Keep.*  
>  
> *Sistem perencanaan STRIPS di game ini punya dua mode unik yang fleksibel banget:*  
>  
> *[Tekan tombol F9 untuk mengaktifkan mode ADVISOR]*  
>  
> *Mode pertama adalah **ADVISOR**. Teman-teman bisa lihat di banner bagian atas layar, AI memberikan saran langkah berikutnya tanpa mengambil alih kontrol pemain sama sekali. Saya tetap bebas menggerakkan Hero secara manual pakai tombol WASD. Hebatnya, begitu saya selesai melakukan langkah yang disarankan—misalnya membeli benih lobak di toko—AI langsung mendeteksi perubahannya dan otomatis memperbarui saran ke langkah selanjutnya.*  
>  
> *[Tekan SPACE atau F9 lagi ke mode AUTO]*  
>  
> *Nah, mode kedua adalah **AUTO**. Di mode ini, Hero bergerak otomatis secara mandiri. Perencana STRIPS tingkat tinggi berkolaborasi dengan algoritma pencarian rute spasial A\* untuk menavigasi pulau tile-by-tile secara mulus menyelesaikan seluruh 37 langkah misi tanpa terjebak jalan buntu."*

---

### Segmen 3: Bedah Debug Overlay Planning [F7] (01:45 – 02:45)
> *[Tekan tombol F7 untuk membuka panel Unified Planning]*  
>  
> *Untuk melihat isi 'otak' dari perencana STRIPS ini, kita bisa buka **Debug Overlay Planning** dengan menekan tombol **[F7]**.*  
>  
> *[Arahkan kursor mouse ke Card 1 di sebelah kanan]*  
> *Di kartu paling atas, kita bisa melihat **Tujuan & Progres**. Di sini ada tiga target utama yang dipantau: pembuatan kunci gerbang, status gerbang terbuka, dan bos dikalahkan. Ada juga progress bar visual serta estimasi durasi misi sekitar 118 detik.*  
>  
> *[Arahkan mouse ke Card 2]*  
> *Kartu kedua menampilkan **Aksi Aktif**. Di sini terlihat aksi grounded yang sedang jalan, misalnya `goto(spawn, shop)`. Di bawahnya ada rincian prekondisi yang wajib terpenuhi, efek aksi berupa penambahan atau pengurangan fakta dunia, serta delta perubahan state.*  
>  
> *[Arahkan mouse ke Card 3]*  
> *Kartu ketiga adalah **Mesin Pencari Weighted A\***. Kami menggunakan bobot $w = 1.5$ dan heuristik canggih $h_{FF}$ atau Fast-Forward Relaxed GraphPlan. Algoritma ini hanya butuh waktu sekitar 1,1 milidetik untuk mengekspansi sekitar 900 node, jauh lebih cepat daripada batas toleransi 20 milidetik. Jika jalur terhalang, sistem monitor eksekusi akan seketika memicu **dynamic replanning** tanpa bikin game nge-lag atau freeze."*

---

### Segmen 4: HTN Rutinitas Warga Desa Sunnyside (02:45 – 03:45)
> *[Tutup F7, jalankan Hero ke area ladang di sebelah barat dan kincir angin]*  
>  
> *Sekarang mari kita tengok kehidupan para warga desa Sunnyside. Berbeda dari NPC game biasa yang gerakannya cuma jalan mondar-mandir tanpa tujuan, NPC di sini punya kesibukan nyata berkat **Hierarchical Task Network (HTN)** dengan mesin dekomposisi SHOP-style.*  
>  
> *[Arahkan kamera ke Pak Tani]*  
> *Di sebelah barat ini ada **Pak Tani**. Tugas utamanya adalah merawat ladang. HTN akan memecah tugas kompleks ini secara cerdas: kalau ada tanaman yang sudah matang, dia otomatis memilih metode panen dan pergi menjualnya ke toko. Kalau tanahnya kering, dia bakal menyiram air. Dan kalau petaknya kosong, dia pergi beli benih untuk menanam lagi.*  
>  
> *[Arahkan kamera ke Kang Penggiling di dekat kincir angin]*  
> *Di dekat kincir angin, ada **Kang Penggiling** yang bertugas mengelola suplai gandum dan perawatan kincir.*  
>  
> *[Buka overlay F8, lalu klik tab 'HTN (Ops)']*  
> *Di tab HTN pada overlay ini, kita bisa memantau status real-time lokasi dan operator aksi dari masing-masing NPC. Semua NPC ini juga sudah dilindungi dengan *collision dan water safety guard*, jadi dijamin tidak akan pernah ada bug berdiri di atas air ataupun menembus tembok bangunan."*

---

### Segmen 5: Live Combat Minion & Bedah Debug Overlay DUU [F8] (03:45 – 05:15)
> *[Tutup overlay, arahkan Hero keluar desa menuju area alam liar di mana ada goblin]*  
>  
> *Nah, ini dia bagian yang paling seru dan sangat dinamis: **Decisions Under Uncertainty (DUU) pada Pertempuran Minion Goblin**.*  
>  
> *Goblin-goblin liar ini spawn secara acak di alam bebas luar desa. Mereka punya radius patroli dan pengejaran berbasis jarak:*  
> *- Kalau jarak kita di atas **240 piksel**, mereka santai saja berpatroli.*  
> *- Tapi begitu Hero masuk radius **240 piksel**, goblin langsung mendeteksi ancaman dan beralih mengejar kita dengan kecepatan tinggi.*  
>  
> *[Buka tombol F8, klik tab 'Uncertainty']*  
>  
> *Sekarang coba kita buka overlay DUU dengan menekan **[F8]**.*  
>  
> *[Dekatkan Hero ke arah goblin agar goblin mengejar dan menyerang]*  
>  
> *Lihat! Begitu goblin mulai mengejar, status di kartu atas langsung berganti dari `[PATROL/AMAN]` menjadi `[MENGEJAR]` atau `[SERANG!]`, lengkap dengan jarak dan nama targetnya secara live!*  
>  
> *Di sinilah **Inferensi Bayesian** bekerja:*  
> *Hero awalnya tidak tahu pasti apakah goblin ini tipe Biasa atau tipe Elit yang serangannya mematikan. AI menetapkan peluang awal bahwa 20% goblin adalah tipe Elit. Begitu goblin melancarkan pukulan pertama:*  
> *- Kalau damagenya kecil (3 damage), bukti menunjukkan ini goblin biasa, sehingga keyakinan posterior langsung turun ke **8.6%** dan muncul label `[TIPE: BIASA]`.*  
> *- Tapi kalau goblin itu ternyata tipe Elit dengan damage besar (6 damage), keyakinan melonjak drastis ke **46.7%** dan sistem langsung waspada bahwa musuh adalah tipe Elit!*  
>  
> *[Arahkan mouse ke Card 2: MEU Policy]*  
> *Berdasarkan probabilitas itu, kartu kedua mengevaluasi **Maximum Expected Utility (MEU)**.*  
> *Perhatikan tombol-tombol aksi di sini:*  
> *- Saat HP Hero kita masih tebal di atas 35%, peluang menang kita sangat tinggi, mencapai lebih dari 90%. Karena itu, nilai Expected Utility untuk bertarung sangat besar (+5.9), dan tombol **`[ENGAGE]` otomatis menyala hijau tebal**.*  
>  
> *[Biarkan goblin memukul Hero hingga HP di bawah 25%]*  
>  
> *Tapi coba perhatikan apa yang terjadi saat HP Hero terkuras habis sampai di bawah 25%:*  
> *Peluang menang anjlok ke 26%. Risiko mati menjadi sangat fatal dengan penalti utilitas minus 20. Seketika itu juga, AI menghitung bahwa opsi terbaik adalah kabur. Tombol **`[EVADE]` langsung menyala merah tebal**, dan rekomendasi aksi otomatis berubah menjadi `[REKOMENDASI: EVADE]`!*  
>  
> *AI ini juga dilengkapi **histeresis 10%** agar tidak terjadi 'thrashing' atau kebingungan bolak-balik antara menyerang dan kabur. Ambang matematis impas kita ada di $HP^* = 35\%$, dan Hero hanya akan melepaskan diri menjadi Evade jika HP benar-benar tembus di bawah $25\%$. Semua perhitungan ini terjadi secara instan dan interaktif tiap frame!"*

---

### Segmen 6: Pembuktian Ilmiah via Terminal & Unit Test (05:15 – 06:15)
> *[Minimize game atau geser layar ke jendela Terminal]*  
>  
> *Agar pembuktiannya tuntas secara ilmiah, kami tidak hanya mengandalkan visualisasi di dalam game, tetapi juga menyiapkan rangkaian pengujian otomatis (*automated unit test*) yang sangat ketat.*  
>  
> *Mari kita jalankan pengujian inti untuk modul DUU, pengejaran goblin, dan HTN:*  
>  
> *[Ketik dan jalankan perintah:]*  
> ```bash
> PYTHONPATH=src python3 -m unittest tests.test_minion_duu tests.test_goblin_chase tests.test_plan_validator tests.test_htn
> ```  
>  
> *Seperti yang kita lihat di terminal, seluruh **29 unit test** berhasil lulus seratus persen (*OK*) dalam waktu singkat sekitar 1,5 detik! Ini membuktikan kebenaran matematis dari derivasi titik impas $P^* = 72.55\%$, kalibrasi fungsi sigmoid $HP^* = 35\%$, formula Bayes, serta mekanisme histeresis.*  
>  
> *Selain itu, kita juga bisa jalankan alat pemeriksa integritas sistem:*  
>  
> *[Ketik dan jalankan:]*  
> ```bash
> python3 tools/check_report.py
> ```  
>  
> *Skrip ini memverifikasi bahwa seluruh data matematis, aset gambar, dan konfigurasi kode game berada dalam sinkronisasi yang sempurna tanpa ada data palsu atau salah hitung."*

---

### Segmen 7: Penutup (06:15 – 07:00)
> *[Kembali ke tampilan game]*  
>  
> *Sebagai kesimpulan, proyek Game AI Eldoria ini berhasil membuktikan bahwa integrasi antara **Automated Planning** yang bersifat deterministik-hierarkis dengan **Decisions Under Uncertainty** yang bersifat probabilistik dapat menciptakan pengalaman gameplay yang luar biasa kaya.*  
>  
> *Agen AI di game ini tidak cuma mengikuti instruksi kaku, tetapi mampu bernalar, memprediksi risiko, mengamati bukti dari lingkungan, dan mengambil tindakan optimal secara real-time demi mencapai tujuannya.*  
>  
> *Sekian demonstrasi dari saya. Terima kasih banyak atas waktu dan perhatiannya! Sampai jumpa di proyek AI berikutnya!"*

---

## 4. Lembar Pintasan Tombol (*Cheat Sheet Hotkeys*)

Simpan tabel ini di dekat monitormu saat merekam:

| Tombol | Kegunaan Utama Saat Rekaman | Momen Penggunaan |
| :---: | :--- | :--- |
| `[WASD]` | Kontrol manual Hero | Saat menunjukkan pergerakan manual dan mode Advisor. |
| `[SPACE]` | Toggle Auto-Pilot (A\* + STRIPS) | Saat mendemokan Hero berjalan mandiri 37 langkah. |
| `[F9]` | Ganti Mode: MANUAL $\to$ ADVISOR $\to$ AUTO | Tekan untuk memperlihatkan banner panduan cerdas di atas. |
| `[F7]` | Buka / Tutup **Planning Inspector Overlay** | Saat membedah 3 Card STRIPS dan kinerja pencarian WA\*. |
| `[F8]` | Buka / Tutup **Decisions Under Uncertainty Overlay** | Saat mendemokan live combat goblin, Bayes, dan tombol MEU. |
| `[F1]` | Debug Hitbox Kaki & Radius Deteksi | Opsional: jika ingin memperlihatkan lingkaran radius 240px goblin. |
| `[I]` | Buka Tas Inventori Hero | Menunjukkan koin, ramuan potion, benih, dan kunci. |
| `[R]` | Restart Game Loop | Jika ingin mengulang simulasi dari awal seed pulau. |

---

## 5. Tips Sukses Perekaman Layar (OBS Studio)

1. **Pengaturan Tampilan OBS**:
   - Jalankan game pada resolusi native `1024x768`.
   - Di OBS Studio, buat kanvas `1920x1080` (16:9), posisikan window game di tengah dengan latar belakang warna gelap elegan (misal: `#0f172a`), atau rekam dengan mode *Window Capture*.
2. **Kualitas Suara**:
   - Pastikan suara mikrofon terdengar jelas dan berada di atas musik latar game.
   - Atur volume BGM game sekitar -18 dB agar tidak menenggelamkan suaramu saat berbicara.
3. **Pacing / Kecepatan Berbicara**:
   - Bicaralah dengan tempo santai dan artikulasi jelas.
   - Berikan jeda 1 detik setelah menekan tombol hotkey (misal tombol F7 atau F8) agar penonton video sempat melihat panel muncul sebelum kamu menjelaskannya.
   - Gerakkan kursor mouse mengitari kartu atau angka probabilitas yang sedang kamu sebutkan untuk mengunci fokus penonton.
