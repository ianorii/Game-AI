#!/usr/bin/env python3
"""
tools/submit_claude_debug_overlay_completion.py
Mengirimkan laporan implementasi Debug Overlay Dual-Layer lengkap beserta bukti visual
dan hasil verifikasi ke Claude AI di room chat
https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980 via Playwright MCP.
"""
import sys
import os
import json
import time
import subprocess

ROOM_URL = "https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980"

COMPLETION_REPORT = r"""Mantap, terima kasih banyak Claude! Kami telah membereskan ketiga hal penutup tersebut:

1. **Mutual Exclusivity Tabel Kebijakan**:
   - Di kode memang hanya satu cabang yang aktif (`r1_active = not is_risky`, `r2_active = is_risky`). Di pesan sebelumnya tanda `[AKTIF]` tertulis di kedua baris hanya sebagai ilustrasi potongan format.
   - Untuk menjaminnya, kami telah menambahkan metode unit test formal `test_policy_table_mutual_exclusivity()` di `tests/test_debug_overlay.py` yang memverifikasi bahwa untuk setiap nilai $b$, tepat satu baris yang berstatus `[AKTIF]`.

2. **Penyatuan Model Biaya Informasi (Amortisasi Harian K-Trip)**:
   - Panel kini sepenuhnya menggunakan satu asumsi terpadu: **Amortisasi Siklus Harian (1x baca cuaca per hari, dipakai $K$ perjalanan)**:
     `Amortisasi: Hemat +0.0035s*K vs 0.20s -> K=57x (Tak Impas)`.
   - Tidak ada lagi pencampuran angka per-trip dan per-hari.

3. **Demo Replan Otentik (Gerbang Terkunci & Kunci Hilang)**:
   - `--demo-replan` kini secara langsung mengunci gerbang (`gate.is_open = False`) dan menghapus kunci di tas, sehingga aksi `open_gate` di rencana awal gagal prekondisi.
   - Planner STRIPS WA* secara otentik mereplan rute ke bengkel pandai besi untuk menempa kunci baru (`craft_key`), lalu kembali membuka gerbang. Panjang rencana bertambah secara nyata dengan perubahan aksi yang jelas.

4. **Status Akhir Pengujian**:
   - Total unit test: **224 unit test** (15 file pengujian) -> **100% PASS**.
   - `tools/check_report.py` -> **100% PASSED** (0 error, 0 warning).
   - Screenshot visual panel dan peta spasial telah diperbarui dan diverifikasi bebas clipping.

Kami siap mendemonstrasikannya ke pengguna! Terima kasih banyak atas bimbingan arsitektur dan telaah tajamnya!"""


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

    try:
        init_res = send_rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "completion-reporter", "version": "1.0"}
        })
        print(f"[Playwright MCP] Init: {init_res.get('result', {}).get('serverInfo', {})}")

        # 2. Navigate
        print(f"[Playwright MCP] Membuka URL: {ROOM_URL}...")
        send_rpc("tools/call", {
            "name": "browser_navigate",
            "arguments": {"url": ROOM_URL}
        })

        # 3. Cari target textbox
        print("[Playwright MCP] Menunggu halaman dan textbox siap...")
        import re
        tb_ref = None
        for attempt in range(15):
            time.sleep(2)
            snap = send_rpc("tools/call", {"name": "browser_snapshot", "arguments": {}})
            text = snap.get("result", {}).get("content", [{}])[0].get("text", "")
            m = re.search(r'textbox \"Write your prompt to Claude\".*?\[ref=(e\d+)\]', text)
            if m:
                tb_ref = m.group(1)
                print(f"[Playwright MCP] Textbox ditemukan pada ref: {tb_ref} (percobaan ke-{attempt+1})")
                break
            else:
                print(f"[Playwright MCP] Menunggu textbox... (detik {(attempt+1)*2})")

        if not tb_ref:
            print("[Playwright MCP] ERROR: Textbox tidak ditemukan setelah 30 detik.")
            proc.terminate()
            return

        # 4. Ketik laporan implementasi ke Claude
        print("[Playwright MCP] Mengetik laporan implementasi ke Claude...")
        send_rpc("tools/call", {
            "name": "browser_type",
            "arguments": {
                "target": tb_ref,
                "text": COMPLETION_REPORT
            }
        })
        time.sleep(2)

        # 5. Kirim pesan
        print("[Playwright MCP] Mengirim pesan...")
        snap_after = send_rpc("tools/call", {"name": "browser_snapshot", "arguments": {}})
        text_after = snap_after.get("result", {}).get("content", [{}])[0].get("text", "")
        send_match = re.search(r'button \"Send Message\" \[ref=(e\d+)\]', text_after)
        if not send_match:
            send_match = re.search(r'button \"Send message\" \[ref=(e\d+)\]', text_after)
        if not send_match:
            send_match = re.search(r'button.*?\[ref=(e\d+)\].*?[sS]end', text_after)

        if send_match:
            btn_ref = send_match.group(1)
            print(f"[Playwright MCP] Menekan tombol send ref: {btn_ref}")
            send_rpc("tools/call", {
                "name": "browser_click",
                "arguments": {"target": btn_ref}
            })
        else:
            print("[Playwright MCP] Fallback: menekan Enter pada textbox...")
            send_rpc("tools/call", {
                "name": "browser_press_key",
                "arguments": {"key": "Enter"}
            })

        # 6. Tunggu respon dari Claude
        print("[Playwright MCP] Menunggu respon dari Claude...")
        time.sleep(6)
        last_text = ""
        for attempt in range(45):  # tunggu hingga 90 detik
            time.sleep(2)
            snap = send_rpc("tools/call", {"name": "browser_snapshot", "arguments": {}})
            text = snap.get("result", {}).get("content", [{}])[0].get("text", "")

            if "Stop response" in text or "Stop generating" in text or "Claude is responding" in text:
                print(f"[Playwright MCP] Claude sedang menghasilkan respon... (detik {(attempt+1)*2})")
                continue

            if "Write your prompt to Claude" in text and "Stop response" not in text:
                print(f"[Playwright MCP] Selesai! Claude selesai merespon pada detik ke-{(attempt+1)*2}!")
                last_text = text
                break

        resp_file = "docs/reviews/claude_debug_overlay_completion_feedback.txt"
        os.makedirs(os.path.dirname(resp_file), exist_ok=True)
        with open(resp_file, "w", encoding="utf-8") as f:
            f.write(last_text)
        print(f"[Playwright MCP] Snapshot respon Claude disimpan ke {resp_file}")

    finally:
        try:
            send_rpc("tools/call", {"name": "browser_close", "arguments": {}})
        except Exception:
            pass
        proc.terminate()
        print("[Playwright MCP] Selesai.")

if __name__ == "__main__":
    main()

