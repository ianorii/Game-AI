#!/usr/bin/env python3
"""
tools/submit_claude_defense_answers.py
Mengirimkan 10 jawaban komprehensif atas pertanyaan simulasi sidang dosen penguji
ke Claude AI di room chat https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980.
"""
import sys
import os
import json
import time
import re
import subprocess

ROOM_URL = "https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980"

PROMPT_TEXT = """Terima kasih atas pertanyaan-pertanyaan yang sangat tajam dan komprehensif, Pak/Bu Penguji. Berikut adalah jawaban resmi kami untuk ke-10 pertanyaan sidang:

### 1. A* Spatial Pathfinding: Admisibilitas, Rintangan Dinamis, & Uji 3.600 Step
Modul A* menggunakan grid 4-arah (`DIRS4`) dengan unit step cost 1.0 dan heuristik Manhattan $h(n) = |\\Delta x| + |\\Delta y|$ yang terbukti admissible ($h \\le h^*$) dan konsisten secara matematis (pergeseran 1 petak mengubah jarak Manhattan maksimal 1, memenuhi pertidaksamaan segitiga $h(u) \\le c(u,v) + h(v)$). Grid 4-arah sengaja dipilih untuk menjamin karakter tidak memotong sudut dinding (*corner cutting*) pada rintangan grid. Rintangan dinamis (NPC/hewan) diperiksa secara berkala oleh `PlanMonitor.check_preconditions()` sebelum tiap langkah; jika sel tujuan terhalang entitas lain atau jembatan roboh, `trigger_replan()` langsung mengalkulasi jalur alternatif baru. Uji 3.600 step (60 detik @ 60 FPS) membuktikan bahwa resolusi tabrakan antara waypoint A* dan mask biner berjalan stabil tanpa *jitter*, *deadlock*, atau *tunneling* tembus tembok pada seluruh 15 entitas yang bergerak bebas kontinu.

### 2. Minimax: Kebenaran Transposition Table & Verifikasi Keputusan
Transposition Table kami mengimplementasikan skema flag tiga kondisi standar Knuth/Schaeffer: `EXACT` jika nilai di dalam jendela $[\\alpha, \\beta]$, `LOWER` jika terjadi beta-cutoff ($val \\ge \\beta$), dan `UPPER` jika terjadi alpha-cutoff ($val \\le \\alpha$), dengan kunci state komprehensif `(player_hp, boss_hp, potion, p_def, b_def, b_hvy_cd, b_heal_cnt, turn, depth)`. Pada saat retrieval, entri `LOWER` hanya memangkas jika $val \\ge \\beta$ saat ini, dan `UPPER` jika $val \\le \\alpha$. Keputusan 100% identik diuji tidak hanya pada 4 skenario benchmark, tetapi diverifikasi secara menyeluruh pada rangkaian uji unit `tests/test_battle_mode.py` yang membandingkan output Minimax Murni versus Alpha-Beta + TT pada beragam kombinasi HP dan status cooldown.

### 3. Minimax: Asumsi Zero-Sum, Deterministik, dan Pemilihan Depth 7
Pertarungan bos diformulasikan sebagai zero-sum game pada fungsi evaluasi: $\\text{eval} = w_{\\text{hp}}(\\text{HP}_{\\text{boss}} - \\text{HP}_{\\text{player}}) + w_{\\text{def}}\\text{DEF} + w_{\\text{hvy}}\\text{HVY} + w_{\\text{res}}\\text{RES}$, di mana utilitas bos berbanding terbalik secara langsung terhadap hero. Dalam pencarian pohon Minimax, transisi aksi dibuat deterministik menggunakan nilai ekspektasi kerusakan (`HERO_ATTACK_EXPECTED`, `BOSS_ATTACK_EXPECTED`) untuk menghindari ledakan cabang chance node, sementara variasi acak $\\pm 10\\%$ baru diinjeksikan saat aksi dieksekusi di game loop nyata. Kedalaman 7 dipilih berdasarkan trade-off horizon vs budget frame 60 FPS ($16.6\\text{ ms}$): branching factor efektif $b \\approx 3-4$ menghasilkan ~224 node evaluasi dalam $12-15\\text{ ms}$, yang cukup dalam untuk melihat 3–4 siklus giliran penuh (mencegah *horizon effect* pada cooldown Heavy Attack 2 ronde) tanpa menjatuhkan frame rate.

### 4. CSP: Formulasi Masalah, Kontribusi LCV, & Ablasi Bertahap
Formulasi loadout adalah CSP murni (menemukan kombinasi 4 slot peralatan yang memenuhi seluruh batasan keras: Budget $\\le 6$, Weight $\\le 6$, Unlocked only, Kapak Berat dilarang dengan Jimat Kritis, dan Tongkat Api wajib Armor Kulit). Kontribusi LCV terukur nyata pada fungsi pencarian solusi pertama (`solve()`): LCV mengurutkan nilai domain berdasarkan dampak pemangkasan minimum pada variabel tetangga, sehingga solusi legal pertama langsung ditemukan pada kedalaman 4 tanpa backtrack sekalipun (0 backtrack). Pada pencarian seluruh solusi (`solve_all()`), ablasi 4 varian menunjukkan efek berjenjang: Backtracking Standar menekan 75.4% kegagalan, dan penambahan Forward Checking (FC) bersama MRV mendeteksi *domain wipeout* secara dini sehingga memangkas backtrack hingga 91.3% dibanding BT biasa (97.9% vs Naive Generate-and-Test).

### 5. Local Search: Fitness Function, Overfitting, dan Jadwal Pendinginan
Fungsi kebugaran (*fitness*) dihitung melalui simulasi deterministik $N$ rollout terbobot ekspektasi terhadap `OpponentModel` hero (yang melacak frekuensi aksi Hero dengan Laplace smoothing $\\alpha=1.0$). Skor kebugaran bersifat kontinu: $+100$ bonus kemenangan bos + selisih kerusakan bersih $(HP_{\\text{hero\\_lost}} - HP_{\\text{boss\\_lost}}) + HP_{\\text{boss\\_sisa}}$, dievaluasi dengan seed tetap per iterasi agar *noise-free*. Risiko overfitting dicegah melalui batasan ketat clamping bobot $[10, 80]$ di `BOSS_WEIGHT_BOUNDS`, serta pengujian generalisasi di mana bobot hasil penalaan diuji melawan profil lawan acak (*unseen playstyles*) di unit test `test_csp_local_search.py`. Jadwal pendinginan Simulated Annealing menggunakan *geometric cooling* $T_{k+1} = 0.95 T_k$ dari $T_0=50.0$ dengan batasan waktu $250\\text{ ms}$, dirancang agar muat dieksekusi saat animasi turn transisi bos tanpa membekukan game loop.

### 6. STRIPS: Definisi Biaya Rencana, Batas WA*, dan Demarkasi Modul
Angka $118.48\\text{ s}$ adalah **durasi eksekusi aksi fisik hero di dalam game** (waktu navigasi grid kontinu antar-lokasi desa ditambah durasi interaksi kerja seperti tebang pohon 3.5s), sedangkan waktu komputasi planner-nya adalah **1.093 ms** (~1.09 detik pada Tabel 6). Kami menggunakan Weighted A* dengan $w = 1.5$ pada heuristik Fast-Forward ($h_{\\text{FF}}$); karena $h_{\\text{FF}}$ diturunkan dari *Relaxed Planning Graph* (relaksasi hapus) yang tidak admissible, jaminan teoritis $w \\times \\text{optimal}$ tidak berlaku ketat, namun secara empiris pada problem P1 dan P2 biayanya 100% identik dengan solusi optimal UCS ($16.63\\text{ s}$ dan $23.07\\text{ s}$). Demarkasi arsitektur: Subgoal regression dan relasi mutex Planning Graph sengaja dibuat sebagai modul demonstrasi formal silabus perkuliahan (`src/main.py --demo-regression`, `--demo-graph`), sedangkan sistem runtime autopilot game utama ditenagai oleh forward state-space search WA* ($h_{\\text{FF}}$) karena efisiensinya dalam menangani ruang proposisi dinamis.

### 7. HTN: Keunggulan Dekomposisi Deklaratif vs FSM & Pemilihan STRIPS
Nilai tambah HTN dibanding FSM adalah separasi bersih antara basis pengetahuan prosedural (tugas majemuk, metode, prekondisi) dengan mesin unifikasi variabel hierarkis (`?plot`, `?crop`), menghindari *state explosion* yang pasti terjadi jika FSM harus melacak call-stack bertingkat. Kegagalan di tengah jalan tertangani melalui *method backtracking*: pada rutinitas Pak Tani (`manage_farm`), jika method pertama `m_harvest_and_sell` ditolak karena tanaman belum matang, HTN otomatis backtrack menguji `m_water_dry_plots`; jika tidak ada petak kering, ia backtrack lagi ke `m_plant_empty_plots` (tercatat di `htn_live_trace.txt`). Alasan teknis pemisahan: Hero menggunakan STRIPS karena ia berorientasi tujuan (*goal-driven*, mencari rantai aksi dari keadaan awal ke tujuan akhir tanpa resep tetap), sedangkan NPC menggunakan HTN karena mereka berorientasi proses berulang (*process-driven*, mengeksekusi resep tugas harian siklik dengan aturan SOP desa).

### 8. Decisions Under Uncertainty: Validasi Model 2.70s & Probabilitas Bayes
Model 2.70s membuktikan kesesuaian implementasi persamaan Bellman dan pembaruan Bayes pada kode kami terhadap contoh analitis silabus Slide 22 ($f^* = \\Delta R / D = 0.36 / 2.70 = 2/15 \\approx 0.1333$), sedangkan model 1.78s menguji batas fisis dunia nyata. Nilai prior $P(\\text{Banjir}) = 0.10$ diambil dari silabus, dan likelihood papan cuaca dimodelkan tidak sempurna (akurasi 90%): $P(\\text{Berita}\\mid\\text{Banjir}) = 0.90$ dan $P(\\text{Berita}\\mid\\text{Cerah}) = 0.10$, sehingga melalui teorema Bayes menghasilkan posterior tepat $P(\\text{Banjir}\\mid\\text{Berita}) = 0.50$. Titik belok kebijakan terjadi saat $P = f^*$: pada koridor penuh penalti 1.78s ($f^* = 0.4890$), kebijakan berbelok jika keyakinan banjir melampaui $48.9\\%$; kami mengakui secara terbuka bahwa margin $1.1\\%$ terhadap posterior $0.50$ adalah batas ketahanan (*robustness margin*) yang tipis.

### 9. MDP: Justifikasi Value Iteration & Rasionalitas Papan Cuaca
Value Iteration bukan sekadar untuk menghasilkan keputusan biner, melainkan untuk memvalidasi bahwa perhitungan fungsi nilai ekspektasi $V^*(s)$ dan nilai aksi $Q^*(s, a)$ pada rantai transisi stokastik berulang (state: `start`, `chokepoint`, `flooded`, `safe`; diskonto $\\gamma = 0.95$, konvergensi $\\epsilon = 10^{-6}$) menghasilkan pembalikan kebijakan yang identik dengan solusi analitis satu tahap MEU. Keberadaan papan cuaca di game justru menyajikan nilai edukatif tertinggi dalam teori keputusan: pada model sub-segmen lokal chokepoint, membaca papan **terbukti menguntungkan dan impas pada $K \\ge 2$ atau $K \\ge 3$ perjalanan/hari**; sementara pada koridor penuh, pembuktian kondisi TIDAK PERNAH IMPAS ($K = 56.7$ vs batas fisik 12-15) membuktikan prinsip fundamental ekonomi informasi: *akurasi informasi tidak berguna jika biaya akuisisinya melebihi kapasitas mitigasi risiko*.

### 10. Arsitektur Terpadu, Oracle Independen, & Bottleneck Skalabilitas
Ketujuh modul terintegrasi dalam satu aliran data: Rencana STRIPS memicu CSP untuk memformulasikan loadout senjata; loadout tersebut dibaca oleh `OpponentModel` sebagai prior Bayesian; `LocalSearch` menala bobot boss berdasarkan model tersebut; `Minimax` mengeksekusi duel boss dengan bobot tertala; dan saat navigasi autopilot, `WeatherManager` (Bayes/MDP) mengalihkan rute A* jika mendeteksi banjir. Kami menggunakan oracle independen: seluruh angka probabilitas Bayes dan ambang analitis dihitung manual berbasis rumus silabus Slide 3-23 sebagai acuan assert unit test, dan Minimax Alpha-Beta diverifikasi terhadap Minimax Murni exhaustif. Jika peta diperbesar $10\\times$ dan entitas menjadi 150, modul yang **pertama kali pecah adalah A* Spatial Pathfinding kontinu** pada CPU jika dijalankan tanpa *hierarchical pathfinding* (HPA*) karena batasan frame budget $16.6\\text{ ms}$, sedangkan STRIPS, CSP, dan Minimax tidak terpengaruh oleh skala spasial peta karena beroperasi pada ruang keadaan diskrit atau terisolasi.

Mohon evaluasi dan umpan balik Bapak/Ibu Dosen Penguji atas jawaban-jawaban kami!"""


def main():
    profile_dir = "/home/rarch/.claude-browser-profile"
    chrome_path = "/usr/bin/chromium"

    cmd = [
        "playwright-mcp",
        "--user-data-dir", profile_dir,
        "--executable-path", chrome_path
    ]

    print("[Playwright MCP] Memulai browser Chromium...")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    req_id = 1
    def send_rpc(method, params=None):
        nonlocal req_id
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        req_id += 1
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            return None
        return json.loads(line)

    # 1. Initialize
    send_rpc("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "claude-review-client", "version": "1.0.0"}
    })
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()
    print("[Playwright MCP] Terhubung ke Playwright MCP.")

    # 2. Navigate to room chat
    print(f"[Playwright MCP] Membuka room chat utama: {ROOM_URL} ...")
    send_rpc("tools/call", {
        "name": "browser_navigate",
        "arguments": {"url": ROOM_URL}
    })
    time.sleep(3)

    # 3. Ambil snapshot untuk mencari target textbox
    snap = send_rpc("tools/call", {"name": "browser_snapshot", "arguments": {}})
    text = snap.get("result", {}).get("content", [{}])[0].get("text", "")

    m = re.search(r'textbox \"Write your prompt to Claude\".*?\[ref=(e\d+)\]', text)
    if not m:
        print("[Playwright MCP] ERROR: Textbox tidak ditemukan di snapshot.")
        proc.terminate()
        return None

    tb_ref = m.group(1)
    print(f"[Playwright MCP] Textbox ditemukan pada ref: {tb_ref}")

    # 4. Ketik prompt laporan
    print("[Playwright MCP] Mengetik jawaban sidang ke Claude...")
    send_rpc("tools/call", {
        "name": "browser_type",
        "arguments": {
            "target": tb_ref,
            "text": PROMPT_TEXT
        }
    })
    time.sleep(1)

    # 5. Cari tombol "Send message" dari snapshot terbaru
    snap_after = send_rpc("tools/call", {"name": "browser_snapshot", "arguments": {}})
    text_after = snap_after.get("result", {}).get("content", [{}])[0].get("text", "")

    btn_m = re.search(r'button \"Send message\".*?\[ref=(e\d+)\]', text_after)
    if btn_m:
        btn_ref = btn_m.group(1)
        print(f"[Playwright MCP] Tombol kirim ditemukan pada ref: {btn_ref}. Mengklik tombol kirim...")
        send_rpc("tools/call", {
            "name": "browser_click",
            "arguments": {"target": btn_ref}
        })
    else:
        print("[Playwright MCP] Tombol kirim tidak ditemukan dengan selector tombol, mencoba Enter...")
        send_rpc("tools/call", {
            "name": "browser_press_key",
            "arguments": {"key": "Enter"}
        })

    # 6. Tunggu respons selesai
    print("[Playwright MCP] Menunggu evaluasi & nilai dari Claude...")
    time.sleep(4)

    last_snap_text = ""
    stable_count = 0
    max_wait = 240  # Maksimal 4 menit
    waited = 0

    while waited < max_wait:
        time.sleep(5)
        waited += 5
        cur_snap = send_rpc("tools/call", {"name": "browser_snapshot", "arguments": {}})
        content = cur_snap.get("result", {}).get("content", [{}])[0].get("text", "")

        is_generating = ("stop response" in content.lower()) or ("stop generating" in content.lower())
        if is_generating:
            print(f"[Playwright MCP] Claude sedang menghasilkan penilaian sidang... ({waited}s)")
            stable_count = 0
            last_snap_text = content
        else:
            if len(content) > 1000 and content == last_snap_text:
                stable_count += 1
                if stable_count >= 2:
                    print(f"[Playwright MCP] Respons selesai terdeteksi ({waited}s).")
                    break
            else:
                stable_count = 0
                last_snap_text = content

    # 7. Ekstrak pesan jawaban Claude
    print("\n" + "=" * 80)
    print("HASIL EVALUASI & NILAI SIDANG DARI CLAUDE:")
    print("=" * 80)

    articles = re.findall(r'article \"Message \d+ of \d+\".*?(?=article \"Message \d+ of \d+\"|$)', last_snap_text, re.DOTALL)
    if articles:
        last_article = articles[-1]
    else:
        last_article = last_snap_text

    print(last_article)
    print("=" * 80 + "\n")

    # Simpan jawaban mentah ke file
    os.makedirs("docs/report_data", exist_ok=True)
    with open("docs/report_data/claude_mock_defense_evaluation.txt", "w", encoding="utf-8") as f:
        f.write(last_article)

    # 8. Tutup browser dengan aman
    proc.terminate()
    print("[Playwright MCP] Browser ditutup dengan aman.")
    return last_article


if __name__ == "__main__":
    main()

