#!/usr/bin/env python3
"""
tools/submit_claude_ui_map_review.py
Mengirimkan konsultasi desain peta, reposisi gerbang, pembersihan bangunan pantai,
dan perbaikan tata letak UI ke Claude AI di room chat
https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980 via Playwright MCP.
"""
import sys
import os
import json
import time
import re
import subprocess

ROOM_URL = "https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980"

PROMPT_TEXT = """Halo Claude! Kami membutuhkan saran arsitektur desain visual dan UI/UX darimu. 
User/pemain baru saja mencoba game secara langsung dan memberikan kritik visual & estetika yang sangat valid mengenai lingkungan dan UI permainan:

### KRITIK & MASALAH YANG DITEMUKAN USER:

1. **Posisi Pintu Gerbang Sangat Aneh ("kenapa pintu ada di tempat aneh seperti ini")**:
   - Gerbang reruntuhan berkunci (`LockedGate`) saat ini berdiri di koordinat (2368, 832) di atas pasir pantai.
   - Secara visual tampak sangat janggal dan konyol: sebuah pintu gerbang kastil/batu-besi megah berdiri tepat di atas tumpukan peti/krat kayu di pasir pantai, persis di bibir saluran air dan di samping tangga tebing. Tidak ada dinding batu pengapit di kiri-kanan pintu yang menjelaskan mengapa pintu itu ada di sana (karakter seharusnya bisa melangkah lewat samping jika tidak ada dinding).

2. **Bangunan di Pantai Mengotori Suasana ("bagian pantai lebih baik dikosongin aja gausah ada bangunan")**:
   - Di pasir pantai selatan tebing terdapat bangunan gubuk kayu beratap hijau (tile 70, 26 / piksel 2240, 832) serta tumpukan peti/krat kayu.
   - User meminta area pantai ini dikosongkan total dari bangunan agar menjadi pantai alami yang lapang, bersih, dan estetik (hanya pasir, ombak air, dan zona pasang surut banjir).

3. **Rumah di Ujung Tebing Perlu Dihapus ("rumah di ujung itu juga lebih baik dihapus aja jadi lahan kosong")**:
   - Di atas tebing timur (di atas tangga kayu, tile 72, 15 / piksel 2304, 480) terdapat lantai rumah kayu terbuka dengan ranjang, meja, dan kebun labu.
   - User meminta rumah di ujung ini dihapus dan diubah menjadi lahan kosong alami / arena tebing terbuka sebelum arena bos.

4. **Tata Letak UI di Game Sangat Aneh & Berantakan ("banyak UI yang aneh di game ini tolong perbaiki susunannya")**:
   - Di pojok kiri atas muncul teks terpotong aneh bertuliskan `ON OVERSEER` (sisa peninggalan header lama).
   - Prompt interaksi mengambang seperti `Butuh Kunci Gerbang [E]` bertumpuk canggung.
   - HUD bawah, banner advisor autopilot di atas, dan panel AI F7 terasa bertumpuk dan tidak memiliki keselarasan visual (layout hierarchy).

---

### PERTANYAAN KONSULTASI KEPADA CLAUDE:

1. **Rekomendasi Reposisi & Desain Gerbang**:
   - Ke mana gerbang berkunci sebaiknya diposisikan agar logis secara arsitektural dan visual? Apakah ditaruh di celah tebing batu menuju arena bos (misalnya di atas tangga tebing di antara dinding tebing batu alami), atau di mana?
   - Bagaimana memastikan reposisi gerbang tetap menjaga logika STRIPS planning (`gate_unlocked` untuk ekspedisi P2 & P4), deteksi tabrakan A*, dan visual prompt [E]?

2. **Strategi Pembersihan Bangunan Pantai & Rumah Tebing**:
   - Peta pulau dibakar dalam `island_map.png` (dari GameMaker `Room1.yy`). Bagaimana strategi terbaik untuk mengosongkan gubuk pantai dan rumah tebing (misalnya menimpa / blit tile pasir pantai dan rumput tebing alami di atas `map_surface` saat inisialisasi) tanpa harus menggambar ulang seluruh kanvas 2752x1536 secara manual?
   - Bagaimana penyesuaian yang aman terhadap `building_footprints.json` dan mask tabrakan `walkable_mask.png` agar 213 unit test repositori tetap lulus 100%?

3. **Rancangan Tata Letak UI/UX yang Rapi, Bersih, dan Profesional**:
   - Bagaimana struktur hierarki UI yang ideal untuk layar 1024x768 ini?
     • Header / Top Bar: Info apa saja yang layak ditampilkan (jam dunia, cuaca, indikator mode manual/auto)?
     • Prompt Interaksi Aksi: Bagaimana format banner/toast aksi interaksi `[E]` yang elegan agar tidak mengambang canggung di atas objek?
     • HUD Status Bawah: Bagaimana menyusun HP hero, koin, perlengkapan, dan petunjuk tombol fungsional agar rapi dan tidak memakan terlalu banyak ruang?
     • Pembersihan teks aneh seperti `ON OVERSEER`.

Mohon arahan dan arsitektur desain solusinya sebelum kami mengeksekusi perombakan visual dan UI ini!"""


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

    # 3. Tunggu dan cari target textbox (dengan retry hingga 30 detik)
    print("[Playwright MCP] Menunggu halaman dan textbox siap...")
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
        print("[Playwright MCP] ERROR: Textbox tidak ditemukan di snapshot setelah 30 detik.")
        proc.terminate()
        return None

    # 4. Ketik prompt laporan
    print("[Playwright MCP] Mengetik prompt konsultasi UI & Map ke Claude...")
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
    print("[Playwright MCP] Menunggu respons rekomendasi desain dari Claude...")
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
            print(f"[Playwright MCP] Claude sedang menghasilkan arahan desain... ({waited}s)")
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
    print("HASIL REKOMENDASI DESAIN DARI CLAUDE:")
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
    with open("docs/report_data/claude_ui_map_design_review.txt", "w", encoding="utf-8") as f:
        f.write(last_article)

    # 8. Tutup browser dengan aman
    proc.terminate()
    print("[Playwright MCP] Browser ditutup dengan aman.")
    return last_article


if __name__ == "__main__":
    main()
