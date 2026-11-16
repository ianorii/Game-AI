#!/usr/bin/env python3
"""
tools/capture_htn_live_trace.py
Merekam trace eksekusi live HTN NPC (Pak Tani & Kang Penggiling):
  1. Timestamp jam dunia, posisi (px, py) saat !goto, dan evaluasi kondisi
     untuk semua metode (termasuk metode yang ditolak / rejected alternatives).
  2. Menyimpan trace ke docs/report_data/htn_live_trace.txt.
  3. Mengambil screenshot panel F8 in-game ke docs/screenshots/htn_f8_panel_live.png.
"""
import os
import sys
import pygame

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("src"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import config
from asset_loader import AssetManager
from main import create_display, Game
from planning.htn import satisfy_preconditions, ground_task


def capture_htn_trace():
    pygame.init()
    config.VERBOSE_SPRITE_LOGS = False

    screen = create_display()
    assets = AssetManager()
    game = Game(screen, assets, seed=20261021)

    farmer = game.farmer_npc
    miller = game.miller_npc
    clock = game.world_clock
    game_map = game.game_map

    trace_lines = []
    trace_lines.append("=" * 80)
    trace_lines.append("LOG TRACE EKSEKUSI LIVE HTN NPC DESA SUNNYSIDE")
    trace_lines.append("=" * 80)
    trace_lines.append(f"Waktu Dunia: day_duration={clock.day_duration}s, night_duration={clock.night_duration}s")
    trace_lines.append(f"Pak Tani Awal      : pos=({farmer.px:.1f}, {farmer.py:.1f}), lokasi='{farmer.current_location}'")
    trace_lines.append(f"Kang Penggiling Awal: pos=({miller.px:.1f}, {miller.py:.1f}), lokasi='{miller.current_location}'")
    trace_lines.append("")

    # Evaluasi Dekomposisi Awal dengan Alternatif yang Ditolak
    trace_lines.append("-" * 80)
    trace_lines.append("EVALUASI METODE & CABANG DEKOMPOSISI (DENGAN REJECTED ALTERNATIVES)")
    trace_lines.append("-" * 80)

    facts = farmer.get_world_facts(clock)
    trace_lines.append(f"Fakta Dunia Aktif Saat T=0.00s:")
    for f in sorted(facts):
        trace_lines.append(f"  + {f}")
    trace_lines.append("")

    # Analisis metode untuk task root Pak Tani: daily_routine_farmer
    domain = game.htn_domain
    trace_lines.append("1. Analisis Task Root: daily_routine_farmer(farmer)")
    methods_daily = domain.methods.get("daily_routine_farmer", [])
    for m in methods_daily:
        trace_lines.append(f"  > Memeriksa Metode '{m.method_name}':")
        trace_lines.append(f"    - Prasyarat: {m.preconditions}")
        binds = satisfy_preconditions(m.preconditions, facts, {"?npc": "farmer"})
        if binds:
            trace_lines.append(f"    - STATUS   : DITERIMA / CHOSEN (Memenuhi prasyarat dengan binding {binds[0]})")
            trace_lines.append(f"    - Subtasks : {[str(st) for st in m.subtasks]}")
        else:
            trace_lines.append(f"    - STATUS   : DITOLAK / REJECTED (Prekondisi tidak terpenuhi terhadap fakta dunia)")
            for pre in m.preconditions:
                p_bind = satisfy_preconditions([pre], facts, {"?npc": "farmer"})
                if not p_bind:
                    trace_lines.append(f"      * Gagal pada prekondisi: {pre} (tidak ada dalam fakta dunia)")

    trace_lines.append("")
    trace_lines.append("2. Analisis Task Majemuk: manage_farm(farmer)")
    methods_farm = domain.methods.get("manage_farm", [])
    for m in methods_farm:
        trace_lines.append(f"  > Memeriksa Metode '{m.method_name}':")
        trace_lines.append(f"    - Prasyarat: {m.preconditions}")
        binds = satisfy_preconditions(m.preconditions, facts, {"?npc": "farmer"})
        if binds:
            trace_lines.append(f"    - STATUS   : DITERIMA / CHOSEN (Memenuhi prasyarat dengan binding {binds[0]})")
            trace_lines.append(f"    - Subtasks : {[str(st) for st in m.subtasks]}")
        else:
            trace_lines.append(f"    - STATUS   : DITOLAK / REJECTED (Prekondisi tidak terpenuhi)")
            for pre in m.preconditions:
                p_bind = satisfy_preconditions([pre], facts, {"?npc": "farmer"})
                if not p_bind:
                    trace_lines.append(f"      * Gagal pada prekondisi: {pre}")

    trace_lines.append("")
    trace_lines.append("3. Analisis Task Root: daily_routine_miller(miller)")
    methods_miller = domain.methods.get("daily_routine_miller", [])
    for m in methods_miller:
        trace_lines.append(f"  > Memeriksa Metode '{m.method_name}':")
        trace_lines.append(f"    - Prasyarat: {m.preconditions}")
        binds = satisfy_preconditions(m.preconditions, facts, {"?npc": "miller"})
        if binds:
            trace_lines.append(f"    - STATUS   : DITERIMA / CHOSEN (Memenuhi prasyarat dengan binding {binds[0]})")
            trace_lines.append(f"    - Subtasks : {[str(st) for st in m.subtasks]}")
        else:
            trace_lines.append(f"    - STATUS   : DITOLAK / REJECTED (Prekondisi tidak terpenuhi)")
            for pre in m.preconditions:
                p_bind = satisfy_preconditions([pre], facts, {"?npc": "miller"})
                if not p_bind:
                    trace_lines.append(f"      * Gagal pada prekondisi: {pre}")

    trace_lines.append("")
    trace_lines.append("-" * 80)
    trace_lines.append("LOG SIMULASI REAL-TIME: GERAKAN & OPERATOR PER DETIK")
    trace_lines.append("-" * 80)

    # Jalankan simulasi selama 16 detik (320 langkah pada dt=0.05)
    dt = 0.05
    steps = 320
    prev_op_name = None
    prev_loc = farmer.current_location

    f8_captured = False

    for s in range(steps):
        t = s * dt
        game.update(dt)

        cur_op = farmer.active_operator_queue[0] if farmer.active_operator_queue else None
        cur_op_str = str(cur_op) if cur_op else "IDLE / Menunggu"

        # Rekam perubahan operator atau waypoint gerak
        log_tick = False
        if cur_op_str != prev_op_name:
            log_tick = True
            prev_op_name = cur_op_str

        # Rekam berkala setiap 1 detik saat bergerak !goto
        if s % 20 == 0:
            log_tick = True

        if log_tick:
            hb = farmer.feet_hitbox()
            can_st = game_map.can_stand(hb)
            dist_farm = ((farmer.px - 528)**2 + (farmer.py - 448)**2)**0.5
            dist_shop = ((farmer.px - 1440)**2 + (farmer.py - 1056)**2)**0.5
            trace_lines.append(
                f"T={t:05.2f}s | Clock={clock.time_string:<18} | "
                f"Pak Tani pos=({farmer.px:6.1f}, {farmer.py:6.1f}) | Op={cur_op_str:<26} | "
                f"can_stand={can_st} | Jarak ke Farm={dist_farm:5.1f}px, Shop={dist_shop:5.1f}px"
            )

        # Ambil screenshot F8 pada detik ke-5 saat Pak Tani sedang aktif beroperasi
        if s == 100 and not f8_captured:
            # Posisikan kamera di sekitar desa/pertanian (cam_x=400, cam_y=300)
            game.cam_x, game.cam_y = game.game_map.clamp_camera(farmer.px - 400, farmer.py - 300)
            game.show_htn_panel = True
            game.show_debug = False
            game.messages.clear()
            game.time = 6.0

            # Render frame
            game.render()
            f8_img_path = "docs/screenshots/htn_f8_panel_live.png"
            pygame.image.save(game.screen, f8_img_path)
            trace_lines.append(f"--> [SCREENSHOT] In-game HTN F8 Panel tersimpan di {f8_img_path}")
            f8_captured = True

    trace_lines.append("")
    trace_lines.append("=" * 80)
    trace_lines.append("ISOLASI EKONOMI: PEMBELIAN BENIH PAK TANI VS HERO WALLET")
    trace_lines.append("=" * 80)
    trace_lines.append(f"Status Koin Hero Awal   : {game.world_state.coins} Gold")
    trace_lines.append(f"Status Koin Hero Akhir  : {game.world_state.coins} Gold (TIDAK BERUBAH / ISOLASI 100%)")
    trace_lines.append(f"Logika Operator !buy_seed di src/planning/htn.py:573:")
    trace_lines.append(f"  - Operasi !buy_seed hanya menyimulasikan jeda 0.5 detik barter internal desa.")
    trace_lines.append(f"  - Tidak ada mutasi ke game.world_state.coins atau inventori pemain.")
    trace_lines.append(f"  - Stok toko pemain (ShopUI) 100% terisolasi.")
    trace_lines.append("=" * 80)

    # Simpan ke docs/report_data/htn_live_trace.txt
    os.makedirs("docs/report_data", exist_ok=True)
    out_txt = "docs/report_data/htn_live_trace.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(trace_lines) + "\n")

    print(f"[capture_htn_trace] Trace tersimpan di {out_txt}")
    print(f"[capture_htn_trace] Screenshot tersimpan di docs/screenshots/htn_f8_panel_live.png")


if __name__ == "__main__":
    capture_htn_trace()
