#!/usr/bin/env python3
"""
tools/poll_claude_response.py
Menunggu streaming respon Claude selesai di room chat dan menyimpan transkrip lengkapnya.
"""
import sys
import os
import json
import time
import re
import subprocess

ROOM_URL = "https://claude.ai/chat/995bb95c-74e3-4ae9-ae06-bcc22d5ec980"

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
        "clientInfo": {"name": "claude-poller", "version": "1.0.0"}
    })
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()

    # 2. Navigate
    print(f"[Playwright MCP] Navigasi ke {ROOM_URL} ...")
    send_rpc("tools/call", {
        "name": "browser_navigate",
        "arguments": {"url": ROOM_URL}
    })

    # 3. Poll sampai selesai
    print("[Playwright MCP] Menunggu respon selesai streaming...")
    last_text = ""
    for attempt in range(45):  # hingga 90 detik
        time.sleep(2)
        snap = send_rpc("tools/call", {"name": "browser_snapshot", "arguments": {}})
        text = snap.get("result", {}).get("content", [{}])[0].get("text", "")

        if "Stop response" in text or "Stop generating" in text or "Claude is responding" in text:
            print(f"[Playwright MCP] Claude masih berpikir / streaming... (detik {(attempt+1)*2})")
            continue

        if "Write your prompt to Claude" in text and "Stop response" not in text:
            print(f"[Playwright MCP] Selesai! Claude selesai merespon pada detik ke-{(attempt+1)*2}!")
            last_text = text
            break

    out_path = "/mnt/kuliah/smt3/AI/Game AI/docs/reviews/claude_final_signoff_verified.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(last_text)
    print(f"[Playwright MCP] Snapshot respon Claude tersimpan di {out_path}.")

    proc.terminate()

if __name__ == "__main__":
    main()

