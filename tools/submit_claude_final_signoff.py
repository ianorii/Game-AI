#!/usr/bin/env python3
"""
tools/submit_claude_final_signoff.py
Mengirimkan konfirmasi pemenuhan 4 syarat sign-off ke Claude AI di room chat
https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980 via Playwright MCP.
"""
import sys
import os
import json
import time
import re
import subprocess

ROOM_URL = "https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980"

PROMPT_TEXT = """Halo Claude! Terima kasih atas evaluasi mendalam dan rekomendasi presentasinya. Seluruh 4 syarat sebelum sign-off telah kami tindak lanjuti secara menyeluruh di kode dan dokumen laporan:

### PEMENUHAN 4 SYARAT SIGN-OFF REVIEWER

1. **Audit Konsistensi Angka Lintas Dokumen & Cross-Validation JSON (`tools/check_report.py`)**:
   - Kami telah memperluas skrip validasi mandiri `tools/check_report.py` dengan fungsi audit silang langsung dari berkas sumber JSON mentah (`verify_ground_truth_crosscheck()`).
   - Skrip membaca langsung:
     • `unittest.json`: 213 unit tests pada 14 berkas (100% OK).
     • `benchmark.json`: P4 WA* (h_FF) tepat 37 langkah, durasi 118.48s.
     • `corridor_segment_analysis.json`: Koridor penuh $\\Delta t = 0.87\\text{s}$ vs sub-segmen $\\Delta t = 0.36\\text{s}$ (0.3546s), penghematan kotor $+0.0035\\text{s}$.
     • `flood_penalty_measurement.json`: Mean delay 1.7783s ($1.5000\\text{s}$ animasi + $0.2783\\text{s}$ re-walk), 95% CI [1.7647, 1.7918]s, penalti kalibrasi 2.70s, ambang $f^* = 0.1333$ (2/15).
     • `information_cost_analysis.json`: VPI abstrak +1.98 poin, interaksi 0.20s, titik impas koridor 1.78s adalah $K = 56.7$ trip/hari (TIDAK PERNAH IMPAS vs batas fisik 12–15 trip).
     • `footprint_audit.json`: 29 rects tapak bangunan pada 22 bangunan fisik, luas terbuang terbobot 4.21% (7.758 px / 184.160 px).
     • `checksums.sha256`: Total 43 berkas artefak terverifikasi hash.
   - Hasil eksekusi `python3 tools/check_report.py`: **SELURUH 3 DOKUMEN LAPORAN & AUDIT SILANG JSON LOLOS VERIFIKASI DENGAN SUKSES (0 ERROR, 0 WARNING)**.

2. **Baseline Formal Minimax (>91% Depth 7) dan CSP (Reduksi Backtrack 97.9%)**:
   - **Minimax Baseline**: Dihitung terhadap *Minimax Murni tanpa pruning Alpha-Beta dan tanpa Transposition Table*. Pada Depth 7, node dievaluasi terpangkas masif dari 2.951 menjadi 238 node (91.9% pemangkasan pada state awal) dan 3.022 menjadi 224 node (92.6% pemangkasan pada state kritis bos), dengan rata-rata reduksi 92.1% sembari mempertahankan keputusan taktis yang 100% identik.
   - **CSP Baseline**: Dihitung terhadap *Naive Generate-and-Test*. Dari 187 backtrack terpangkas menjadi hanya 4 backtrack pada solver Backtracking + MRV + FC + LCV (reduksi backtrack $(187-4)/187 = 97.86\\% \\approx 97.9\\%$, dan node dieksplorasi terpangkas 93.0% dari 257 menjadi 18 node).
   - Keduanya telah diformalkan dalam Tabel 3 dan Tabel 4 di `docs/LAPORAN_INDUK.md`.

3. **Penalti Terkalibrasi 2.70s vs Terukur 1.78s & Invariansi Kebijakan Optimal**:
   - Kami menegaskan rasionalisasi kedua nilai penalti:
     • **1.78s ($1.7783\\text{s}$)** adalah keterlambatan fisik empiris nyata di game engine (animasi renang 1.50s + re-walk rata-rata 0.28s).
     • **2.70s** adalah kalibrasi analitis agar rasio biaya terhadap penalti mereplikasi persis slide perkuliahan Slide 22 ($f^* = 0.36 / 2.70 = 2/15 \\approx 0.1333$).
   - **Invariansi Kebijakan Optimal**: Tabel perbandingan sensitivitas telah ditampilkan di Tabel 8 Dokumen Induk & Tabel 3 Laporan Ketidakpastian, membuktikan bahwa pada keempat kombinasi model (2 definisi segmen × 2 model penalti), kondisi $0.10 < f^* < 0.50$ selalu terpenuhi. Kebijakan agen AI adalah **100% invarian**: selalu memilih Pintas saat cerah ($P=0.10 < f^*$) dan selalu beralih ke Raya setelah kabar banjir ($P=0.50 > f^*$).

4. **Interpretasi Quasi-Deterministik CI 95% [1.765, 1.792]s**:
   - Kami secara eksplisit menjelaskan dalam laporan bahwa interval sempit ini ($0.027\\text{s}$) dari $N=200$ simulasi headless mencerminkan sifat game loop Pygame dan pathfinding A* yang beroperasi secara kuasi-deterministik.
   - Variansi kecil ($\sigma = 0.098\\text{s}$) timbul semata-mata dari offset koordinat piksel masuk diskrit ($0-32\\text{ px}$) saat hero menyentuh batas zona banjir pesisir, yang memicu variasi jarak tempuh evakuasi re-walk antara $0.22\\text{s} - 0.43\\text{s}$, bukan berasal dari stokastisitas atau noise lingkungan acak.

---

### TINDAK LANJUT STRATEGI PRESENTASI
- **Framing Ramalan Cuaca**: Kami mengadopsi saran Anda untuk membingkai hasil bukan sebagai permintaan maaf, melainkan sebagai demonstrasi edukatif batas rasionalitas: model formal membuktikan kapan informasi layak dibeli ($f^* = 2/15$) dan kapan biaya perolehan menjadikannya irasional ($K = 56.7$ trip/hari).
- **Rencana Live Demo (5-8 Menit)**: Memfokuskan live demo pada 3 modul utama: (1) Duel taktis Minimax boss, (2) Rutinitas harian dekomposisi HTN warga desa, dan (3) Keputusan di bawah ketidakpastian (flood flush & autopilot adaptif Bayes). Sisa modul (A*, CSP, Local Search, STRIPS) diringkas dalam slide visual.
- **Kesiapan Teknis**: Cadangan video simulasi telah disiapkan untuk mengantisipasi potensi kendala driver/resolusi proyektor saat presentasi langsung.

Dengan terpenuhinya seluruh poin di atas, kami memohon konfirmasi apakah proyek ini kini telah siap untuk **final sign-off resmi** tanpa syarat. Terima kasih banyak atas bimbingan dan koreksi kritisnya!"""


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
    print("[Playwright MCP] Mengetik prompt konfirmasi ke Claude...")
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

    # 7. Ekstrak pesan jawaban Claude
    print("\n" + "=" * 80)
    print("HASIL RESPONS CLAUDE (FINAL SIGN-OFF):")
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
    with open("docs/report_data/claude_final_signoff.txt", "w", encoding="utf-8") as f:
        f.write(last_article)

    # 8. Tutup browser dengan aman
    proc.terminate()
    print("[Playwright MCP] Browser ditutup dengan aman.")
    return last_article


if __name__ == "__main__":
    main()

