#!/usr/bin/env python3
"""
tools/submit_claude_review.py
Mengirimkan laporan penutup Decision under Uncertainty ke Claude AI di room chat utama
https://claude.ai/chat/5edab99b-6887-47c6-9f3c-58538dd79984 via Playwright MCP,
melampirkan tangkapan layar, menunggu balasan, dan mengekstrak respons lengkap Claude.
"""
import sys
import os
import json
import time
import re
import subprocess

ROOM_URL = "https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980"

SCREENSHOTS = [
    os.path.abspath("docs/screenshots/uncertainty_tab_panel_f7.png"),
    os.path.abspath("docs/screenshots/weather_board_prompt.png"),
    os.path.abspath("docs/screenshots/hero_flood_flush_swimming.png"),
    os.path.abspath("docs/screenshots/gate_closeup_side_by_side.png"),
    os.path.abspath("docs/screenshots/autopilot_route_before_news.png"),
    os.path.abspath("docs/screenshots/autopilot_route_after_news.png"),
]

PROMPT_TEXT = """Berikut laporan penutup komprehensif Decision under Uncertainty sesuai instruksi reviewer:

### TABEL LAPORAN VERIFIKASI PENUTUP

| Poin | Status | Bukti Pengujian & Metrik Nyata |
| :--- | :---: | :--- |
| **1. Biaya Informasi & Net VPI** | **LULUS** | Lokasi papan di alun-alun `(1504, 1024)`. Biaya jalan + jeda interaksi `[E]` (0.20s) vs penghematan kotor:<br>• **Per-Single Trip (K=1)**: Membaca papan adalah **RUGI BERSIH** di semua titik awal karena jeda 0.20s: Dari Rumah (detour 0.0s + 0.20s = 0.20s $\implies$ Neto -0.02s model 2.7s / -0.10s model 1.78s), Dari Warung (detour 7.81s $\implies$ Neto -7.63s).<br>• **Amortisasi Siklus Harian (240s)**: Belief Bayes bertahan 1 hari penuh. Impas tercapai di **$K \\ge 2$ trips** (model kalibrasi 2.70s: +0.15s pada 2 trip, +0.69s pada 5 trip) atau **$K \\ge 3$ trips** (model empiris 1.78s: +0.09s pada 3 trip, +0.28s pada 5 trip).<br>• Model Abstrak: VPI = +1.98 poin utilitas.<br>• Tab 3 [F7] menampilkan: `Biaya Papan: Neto -0.02s/trip (Impas jika K >= 2 trip/hari)`. Data: `docs/report_data/information_cost_analysis.json` & `information_cost_amortization_mc.json`. |
| **2. Pengukuran Penalti Banjir (N=200)** | **LULUS** | Headless N=200 kejadian banjir nyata di zona pantai:<br>• **Mean Delay Terukur**: **1.7783s** (95% CI: [1.7647, 1.7918]s, Std Dev: 0.0979s).<br>• Komponen: Animasi berenang 1.5000s, Re-walk dari tile terdekat: mean 0.2783s (0.22s–0.43s).<br>• Titik impas empiris murni: $f^*_{\\text{empiris}} = 0.36 / 1.7783 = \\mathbf{0.2024}$ (20.24%).<br>• Titik impas terkalibrasi: $f^* = \\mathbf{0.1333}$ (2/15) dengan delay 2.70s.<br>• **Konsistensi Kebijakan**: Kedua $f^*$ menghasilkan aksi identik: Prior $10\% < f^* \\implies$ Pintas; Berita $50\% > f^* \\implies$ Raya (Detour).<br>• **Evakuasi**: 24/24 tile rawan banjir 100% dievakuasi ke daratan kering di luar zona banjir dengan jalur A* aktif ke boss. Data: `docs/report_data/flood_penalty_measurement.json`. |
| **3. Sub-Segmen vs Koridor Penuh** | **LULUS** | • **Sub-segmen (dipakai MDP)**: 168.2 px (1.14s) vs 220.4 px (1.50s), $\\Delta t = 0.36\\text{s}$ (+31.0%). Ini segmen divergensi chokepoint.<br>• **Koridor Penuh**: 480 px (3.26s) vs 608 px (4.13s), $\\Delta t = 0.87\\text{s}$ (+26.7%). Jika dipakai, $f^* \\approx 0.32$ (delay 2.70s) atau delay harus 6.53s untuk $f^* = 2/15$. Data: `docs/report_data/corridor_segment_analysis.json`. |
| **4. Daftar Entitas Resmi Dunia Game** | **LULUS** | Sumber resmi: `assets/maps/sunnyside_isle.json` (`game.tile_map.animals`):<br>• 1 Hero di (1440, 1056).<br>• 2 NPC HTN: Pak Tani (528, 448) & Kang Penggiling (1328, 640).<br>• 11 Hewan: 4 Domba, 2 Sapi, 3 Ayam, 2 Bebek (bebek adalah water animal di danau).<br>• 1 Boss Statis: Skeleton Overlord di (2464, 448).<br>• **Total: Tepat 14 bergerak + 1 boss statis = 15 total entitas**. Babi hanya kelas uji hitbox di `animal.py`, tidak pernah di-spawn di live map. |
| **5. Tabel Footprint 20 Bangunan Aktif & Aset Gerbang** | **LULUS** | Dari `docs/report_data/footprint_audit.csv` (20 bangunan terlihat, 2 phantom diabaikan):<br>• Total luas tapak: 184.160 px, total area terbuang: 7.758 px.<br>• Rata-rata persentase terbuang: **4.21% luas terbobot**, **6.07% rerata per bangunan**, **5.52% rerata skala peta**.<br>• Cakupan dinding opak rata-rata: **98.8%**.<br>• **Tabel lama (1.83%) dinyatakan TIDAK VALID** karena hanya perkiraan bounding box kasar tanpa alpha mask genteng miring.<br>• **Aset Krat Gerbang**: Krat kayu dekat gerbang pantai adalah tileset asli GameMaker dari `sunnyside_isle.json` (bukan prop kode runtime) dengan collision terdaftar rapi tanpa clipping visual. |
| **6. Verifikasi Test Suite & Screenshots** | **LULUS** | • **14 berkas, total 207 unit tests LULUS 100%** (`Ran 207 tests in 83.042s. OK`).<br>• Asal kenaikan 189 $\\to$ 207 (+18 tests): +10 test `test_putaran3_uncertainty.py`, +7 test `test_collision_and_decor_fixes.py` (termasuk simulasi live game loop 60s @ 60 FPS), +1 test `test_hero_sprite.py` (animasi swimming).<br>• Selftest 120 frame lolos, demo CLI planning & decision lolos, SHA256 checksums tersimpan.<br>• **6 tangkapan layar PNG dilampirkan langsung pada pesan ini** (Tab 3 Panel F7, Papan Cuaca [E], Animasi Berenang Flood Flush, Gate Closeup Side-by-Side 880px, Rute Autopilot Sebelum Berita, Rute Autopilot Sesudah Berita). |
| **7. Dokumen Teknis & Laporan** | **LULUS** | `docs/DECISION_UNCERTAINTY.md` dan `ROADMAP.md` telah disinkronkan memuat seluruh analisis amortisasi biaya informasi, penalti empiris 1.78s vs kalibrasi 2.70s, batas impas, dan audit entitas. |

### HAL YANG BERMASALAH (KETERBATASAN & HASIL JUJUR)
1. **Penghematan Waktu Nyata Sangat Kecil (~0.18 Detik)**:
   Meskipun model matematisnya presisi, penghematan waktu bersih rute chokepoint pantai di game nyata hanya $0.1772\\text{ s}$ per perjalanan. Bagi pemain manusia, perbedaan ini hampir tidak terasa.
2. **Keterbatasan Lokasi Papan Ramalan Cuaca (Per-Trip Selalu Negatif)**:
   Membaca papan cuaca untuk satu perjalanan saja selalu merugikan secara waktu ($\le -0.02\\text{ s}$ dari Rumah, $-7.63\\text{ s}$ dari Warung). Nilai informasi baru positif jika diamortisasi minimal 2–3 perjalanan per siklus cuaca 240s.
3. **Kalibrasi 2.70s vs Nilai Terukur 1.78s**:
   Delay fisik nyata yang diukur adalah $1.7783\\text{ s}$ ($f^* = 0.2024$). Angka $2.70\\text{ s}$ adalah kalibrasi buatan yang kami pilih di config agar $f^* = 2/15$ persis dengan slide kuliah. Untungnya, kedua threshold menghasilkan kebijakan optimal yang 100% konsisten.
4. **Status Ekstensi VPI**:
   Metrik Value of Perfect Information (+1.98 poin) diakui secara terbuka sebagai materi pengayaan teori keputusan formal di luar silabus slide kuliah standar.

Mohon konfirmasi reviewer apakah seluruh kriteria penutup Decision under Uncertainty telah terpenuhi untuk penutupan fitur, serta arahan template master dokumen final (`LAPORAN_AUTOMATED_PLANNING.md`) dan skenario demo 5–8 menit."""


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

    # 4. Lampirkan tangkapan layar langsung via browser_drop
    valid_screenshots = [p for p in SCREENSHOTS if os.path.exists(p)]
    print(f"[Playwright MCP] Melampirkan {len(valid_screenshots)} tangkapan layar PNG...")
    if valid_screenshots:
        drop_res = send_rpc("tools/call", {
            "name": "browser_drop",
            "arguments": {
                "target": tb_ref,
                "paths": valid_screenshots
            }
        })
        time.sleep(3)

    # 5. Ketik prompt laporan
    print("[Playwright MCP] Mengetik prompt laporan ke Claude...")
    send_rpc("tools/call", {
        "name": "browser_type",
        "arguments": {
            "target": tb_ref,
            "text": PROMPT_TEXT
        }
    })
    time.sleep(1)

    # 6. Cari tombol "Send message" dari snapshot terbaru
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

    # 7. Tunggu respons selesai
    print("[Playwright MCP] Menunggu respons dari Claude...")
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
            print(f"[Playwright MCP] Claude sedang menghasilkan balasan... ({waited}s)")
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

    # 8. Ekstrak pesan jawaban Claude
    print("\n" + "=" * 80)
    print("HASIL RESPONS CLAUDE:")
    print("=" * 80)

    # Pisahkan pesan dan ambil artikel terakhir
    articles = re.findall(r'article \"Message \d+ of \d+\".*?(?=article \"Message \d+ of \d+\"|$)', last_snap_text, re.DOTALL)
    if articles:
        last_article = articles[-1]
    else:
        last_article = last_snap_text

    print(last_article)
    print("=" * 80 + "\n")

    # Simpan jawaban mentah ke file
    os.makedirs("docs/report_data", exist_ok=True)
    with open("docs/report_data/claude_putaran3_review.txt", "w", encoding="utf-8") as f:
        f.write(last_article)

    # 9. Tutup browser dengan aman
    proc.terminate()
    print("[Playwright MCP] Browser ditutup dengan aman.")
    return last_article


if __name__ == "__main__":
    main()
