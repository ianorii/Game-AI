#!/usr/bin/env python3
"""
tools/submit_claude_debug_overlay_discussion.py
Mengirimkan usulan arsitektur dan desain debug overlay untuk Automated Planning
dan Decisions Under Uncertainty ke Claude AI di room chat
https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980 via Playwright MCP.
"""
import sys
import os
import json
import time
import re
import subprocess

ROOM_URL = "https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980"

DISCUSSION_PROMPT = """Halo Claude! Kami ingin meminta arahan dan berdiskusi denganmu mengenai perancangan **Debug Overlay yang Rapih, Elegan, dan Terpadu** untuk dua modul AI utama:
1. **Automated Planning** (STRIPS, WA* h_FF, Heuristik h_max/h_level, Re-planning real-time, Geodesic Polyline)
2. **Decisions Under Uncertainty** (Bayesian Belief Update P(Banjir), Ambang Kritis f* = 0.1333, Bellman MDP Q-values, Analisis VPI & Biaya Informasi)

### Latar Belakang & Kebutuhan UI:
Game berjalan pada resolusi 1024x768. Di layar saat ini terdapat:
- **Top Bar** di kiri atas: `Rect(8, 8, 260, 36)` (Mode Kontrol [AI AUTO / MANUAL] & Waktu/Cuaca).
- **Advisor Banner** di tengah atas: `Rect(280, 8, 360, 36)` (Instruksi saran otonom).
- **Centering Action Pill** di tengah bawah: `Rect(372, 594, 280, 38)` (Prompt tombol [E]).
- **Bottom HUD** di bawah: `Rect(0, 640, 1024, 128)` (Status Hero, Beban CSP, Key Hints 4 baris, Minimap).
- Area bebas yang optimal untuk Dock Panel Debug berada di kanan atas:
  `Rect(660, 8, 356, 420)` (bebas tumpang tindih 100% dari widget lain).

---

### Usulan Arsitektur & Desain Debug Overlay:

Kami mengusulkan konsep **Dual-Layer Debug System**:
1. **Layer 1: Unified AI Inspector Dock (Panel UI Informasi di Kanan Atas)**
   Satu jendela dock elegan berukuran `356 x 420` dengan 2 Tab Utama yang mudah dinavigasi:
   - **Tab 1: [F7] AUTOMATED PLANNING INSPECTOR**
     * **Goal & Problem**: Status goal PDDL aktif (mis. `boss_defeated`, `gate_open`), status koin & material.
     * **Search Engine & Heuristic**: Algoritma aktif (WA* $w=2.0$ dengan $h_{FF}$), jumlah node expanded, waktu pencarian (ms), nilai $g(n)$ dan $h(n)$.
     * **Live Plan Pipeline**: Menampilkan 5 aksi sekuensial (aksi selesai bertanda centang hijau, aksi aktif disorot emas dengan mini progress bar, aksi mendatang dengan durasi dalam detik).
     * **Re-planning Trigger**: Deteksi deviasi / rintangan dinamis (jika gerbang terkunci / jembatan putus) dan latensi re-plan ($< 20$ ms budget per frame).
     * **Geodesic Path Metrics**: Verifikasi invariansi jarak Manhattan vs langkah A* nyata ($40 + 5 = 45$ langkah, $9.78$s).

   - **Tab 2: [F8] DECISIONS UNDER UNCERTAINTY INSPECTOR**
     * **Bayesian Belief Gauge**: Visual bar $P(\text{banjir})$ real-time dengan penanda garis vertikal ambang batas analitik $f^* = 0.1333$ (13.33%). Bar berwarna hijau jika $P < f^*$ dan merah jika $P \ge f^*$.
     * **Bukti Papan Pengumuman & Bayes Update**: Status bukti terakhir (Cerah / Berita Banjir / Belum cek), Likelihood $P(E|B)$ vs $P(E|\neg B)$, serta Posterior terhitung: $P(B|\text{Berita}) = 50.0\%$, $P(B|\text{Cerah}) = 1.2\%$.
     * **Bellman MDP & Q-Values**: Nilai utilitas harapan $Q(\text{Pintas})$ vs $Q(\text{Raya})$, status kebijakan aktif $\pi^*(b) \in \{\text{Pintas}, \text{Raya}\}$.
     * **Ekonomi Informasi Formal**: VPI $= 1.98$, Biaya observasi papan (interaksi 0.20s), dan status impas $K \ge 56.7$ trip/hari.
     * **Konsep Inti Slide 12**: Komparasi eksplisit perbedaan *Plan* (sekuens statis) vs *Policy* (pemetaan adaptif).

2. **Layer 2: In-World Spatial Visualizer (Overlay Spasial pada Peta Dunia)**
   Ketika Debug Overlay aktif:
   - **Untuk Planning**: Menggambar garis polyline jalur A* yang sedang ditempuh hero di atas peta (garis cyan bercahaya tipis dengan titik waypoint) sehingga pemain/penguji melihat navigasi nyata secara spasial.
   - **Untuk Ketidakpastian**: Menyorot 26 tile zona banjir di pesisir pantai dengan arsiran semi-transparan (hazards tint biru-merah saat berisiko), serta menandai titik percabangan jalan pintas vs jalan memutar raya.

---

### Pertanyaan Diskusi untuk Claude:
1. Apakah pembagian dua tab terpadu (`[F7] Planning` dan `[F8] Uncertainty`) pada satu Dock Panel kanan atas (`356 x 420`) sudah ideal dari sudut pandang hierarki informasi sidang?
2. Informasi spesifik apa yang paling penting disorot di tab Planning agar dosen penguji langsung melihat bahwa sistem menggunakan formal PDDL / STRIPS dan bukan sekadar hardcode A* biasa?
3. Pada tab Ketidakpastian, apakah penyajian grafis gauge $P(\text{banjir})$ vs $f^*$ beserta nilai Q-Value Bellman sudah cukup representatif terhadap materi Slide 3-23?
4. Apakah ada rekomendasi tambahan untuk tata letak, skema warna (*color coding*), atau kontrol pintasan keyboard agar presentasi terlihat sangat profesional?

Mohon masukan dan arahannya!"""


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
        "clientInfo": {"name": "claude-debug-discussion", "version": "1.0.0"}
    })
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()
    print("[Playwright MCP] Terhubung ke Playwright MCP.")

    # 2. Navigate to room chat
    print(f"[Playwright MCP] Membuka room chat: {ROOM_URL} ...")
    send_rpc("tools/call", {
        "name": "browser_navigate",
        "arguments": {"url": ROOM_URL}
    })

    # 3. Cari target textbox
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

    # 4. Ketik prompt diskusi ke Claude
    print("[Playwright MCP] Mengetik prompt diskusi ke Claude...")
    send_rpc("tools/call", {
        "name": "browser_type",
        "arguments": {
            "target": tb_ref,
            "text": DISCUSSION_PROMPT
        }
    })
    time.sleep(1)

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
    time.sleep(5)
    last_text = ""
    for attempt in range(45):  # tunggu hingga 90 detik
        time.sleep(2)
        snap = send_rpc("tools/call", {"name": "browser_snapshot", "arguments": {}})
        text = snap.get("result", {}).get("content", [{}])[0].get("text", "")

        # Cek apakah Claude sedang mengetik atau sudah selesai
        if "Stop response" in text or "Stop generating" in text or "Claude is responding" in text:
            print(f"[Playwright MCP] Claude sedang menghasilkan respon... (detik {(attempt+1)*2})")
            continue

        if "Write your prompt to Claude" in text and "Stop response" not in text:
            # Respon sudah selesai!
            print(f"[Playwright MCP] Respon Claude selesai pada detik ke-{(attempt+1)*2}!")
            last_text = text
            break

    # Simpan snapshot respon ke docs/reviews/claude_debug_overlay_advice.txt
    out_path = os.path.join("/mnt/kuliah/smt3/AI/Game AI/docs/reviews/claude_debug_overlay_advice.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(last_text)
    print(f"[Playwright MCP] Snapshot respon Claude tersimpan di {out_path}.")

    proc.terminate()
    print("[Playwright MCP] Selesai!")
    return last_text


if __name__ == "__main__":
    main()

