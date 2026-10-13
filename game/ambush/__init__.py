"""game/ambush package - Tahap 3: Ambush Director (Local Search + CSP).

Menata squad penyerang SEBELUM battle mode: CSP menghasilkan konfigurasi
valid -> local search menyetel difficulty -> verifikasi -> dipakai di battle.

Solver TIDAK menggambar apa pun; semua angka proses dikirim ke trace buffer
(fase 5) yang dibaca overlay dan exporter CSV.
"""
