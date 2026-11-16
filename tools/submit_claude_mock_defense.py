#!/usr/bin/env python3
"""
tools/submit_claude_mock_defense.py
Mengirimkan permintaan sesi tanya jawab (simulasi penguji galak) ke Claude AI di room chat
https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980 via Playwright MCP.
"""
import sys
import os
import json
import time
import re
import subprocess

ROOM_URL = "https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980"

PROMPT_TEXT = """Halo Claude! Seluruh 6 poin penyelarasan yang kamu minta sebelumnya:
1. Konsistensi bangunan: 20 bangunan fisik aktif di daratan pulau (dari 22 entri GameMaker asli termasuk 2 phantom di luar kanvas yang dinonaktifkan) dipetakan ke 29 bounding box rect tapak.
2. Robustness margin tipis f* = 0.4890 vs P(berita) = 0.50 (margin 1.1% pada koridor penuh 1.78s) ditegaskan secara eksplisit bersama kondisi batas ketahanan kebijakannya.
3. Penalti 2.70s diakui secara transparan sebagai kalibrasi mundur analitis (reverse-calibrated) agar tepat mereplikasi contoh perkuliahan Slide 22 (f* = 2/15), dibanding 1.78s penalti empiris nyata di game engine.
4. Rata-rata pemangkasan Minimax dikoreksi menjadi 92.2% terbobot matematis (7.549 murni -> 590 node AB+TT lintas 4 skenario).
5. Atribusi sinergis Minimax ditegaskan (gabungan Alpha-Beta, Move Ordering, dan Transposition Table), serta CSP dilengkapi ablasi bertahap (BT Standar 75.4%, BT+MRV+FC+LCV 91.3% vs BT Standar, dan 97.9% vs Naive Generate-and-Test).
6. Interpretasi CI 95% sempit [1.765, 1.792]s dijelaskan sebagai sampel atas offset piksel masuk 0-32px pada sifat kuasi-deterministik Pygame, bukan noise stokastik lingkungan acak.

Semua poin di atas telah kami cantumkan rapi di LAPORAN_INDUK.md dan DECISION_UNCERTAINTY.md, serta LOLOS 100% verifikasi tools/check_report.py (0 error, 0 warning).

Kami sangat menyambut tawaranmu! Silakan perankan "dosen penguji yang kritis dan agak galak". Ajukan 8–10 pertanyaan paling tajam, menantang, dan menjebak yang kemungkinan besar akan ditanyakan dosen penguji terhadap 7 modul AI proyek LABYRINTH ini (A* Spatial, Minimax Duel, CSP Inventory, Local Search Tuning, STRIPS Expedition, HTN Village Routines, Decision under Uncertainty Bayes/MDP/Information Cost, serta Arsitektur & Keterbatasan).

Tantang asumsi kami, gali potensi kelemahan teoretis maupun implementasi teknis, dan jangan ragu untuk menguji batas pemahaman kami. Kami siap menjawabnya satu per satu untuk menyempurnakan kesiapan sebelum presentasi!"""


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
    print("[Playwright MCP] Mengetik prompt simulasi tanya-jawab ke Claude...")
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
    print("HASIL PERTANYAAN DOSEN PENGUJI DARI CLAUDE:")
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
    with open("docs/report_data/claude_mock_defense_questions.txt", "w", encoding="utf-8") as f:
        f.write(last_article)

    # 8. Tutup browser dengan aman
    proc.terminate()
    print("[Playwright MCP] Browser ditutup dengan aman.")
    return last_article


if __name__ == "__main__":
    main()

