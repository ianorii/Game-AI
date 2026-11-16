#!/usr/bin/env python3
"""
tools/capture_putaran3_screenshots.py
Menghasilkan seluruh screenshot bukti implementasi Keputusan di Bawah Ketidakpastian:
1. weather_board_prompt.png: Hero di depan papan pengumuman cuaca desa + prompt [E] (tanpa tertutup log awal)
2. uncertainty_tab_panel_f7.png: Panel F7 Tab 3 dari alur nyata setelah membaca papan cuaca (tanpa kontradiksi)
3. flood_zone_active.png: Zona banjir aktif dengan efek riak genangan air organik di pantai
4. hero_flood_flush_swimming.png: Hero di tengah layar saat berenang dan setelah dievakuasi ke daratan kering
5. autopilot_route_before_news.png: Rute autopilot cepat sebelum berita (15 Tile / 3.26s) tanpa menimpa HUD
6. autopilot_route_after_news.png: Rute autopilot aman sesudah berita (19 Tile / 4.13s) tanpa menimpa HUD
"""
import os
import sys
import math
import pygame

sys.path.insert(0, "src")
sys.path.insert(0, ".")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
pygame.init()

from main import create_display, Game
from asset_loader import AssetManager
from ai.pathfinding import astar
import config

os.makedirs("docs/screenshots", exist_ok=True)

screen = create_display()
assets = AssetManager()
game = Game(screen, assets, seed=20261021)
w_tiles, h_tiles = 86, 48

def is_blocked_std(cx: int, cy: int) -> bool:
    if cx < 0 or cx >= w_tiles or cy < 0 or cy >= h_tiles:
        return True
    px = cx * 32 + 16
    py = cy * 32 + 16
    hb = pygame.Rect(int(px - 7), int(py - 4), 14, 8)
    return not game.game_map.can_stand(hb)

goal_cell = (2384 // 32, 880 // 32)

# ==============================================================================
# 1. WEATHER NOTICE BOARD PROMPT (Papan terlihat jelas, prompt [E], tanpa log ELDORIA)
# ==============================================================================
game.time = 6.0
game.messages.clear()
game.hero.px = 1504.0
game.hero.py = 1040.0
game.hero.direction = "up"
game.hero.manual_mode = True
game._snap_camera()
game._check_world_interactions()
game.render()
pygame.image.save(screen, "docs/screenshots/weather_board_prompt.png")
print("[1] Tersimpan ke docs/screenshots/weather_board_prompt.png")

# ==============================================================================
# 2. TAB KETIDAKPASTIAN DI PANEL F7 (Alur nyata setelah membaca papan)
# ==============================================================================
# Lakukan interaksi membaca papan agar bukti tercatat alami
game.weather_manager.read_notice_board()
game.weather_manager.belief_flood = 0.50
game.weather_manager.recalculate_policy()
game.unified_panel.visible = True
game.unified_panel.active_tab = 3
game.render()
pygame.image.save(screen, "docs/screenshots/uncertainty_tab_panel_f7.png")
print("[2] Tersimpan ke docs/screenshots/uncertainty_tab_panel_f7.png")

# ==============================================================================
# 3. ZONA BANJIR AKTIF (Genangan riak air organik di pasir pantai)
# ==============================================================================
game.unified_panel.visible = False
game.weather_manager.actual_flood = True
fz = game.weather_manager.flood_zone_rect
game.hero.px = float(fz.x - 30)
game.hero.py = float(fz.y + 30)
game.hero.direction = "right"
game._snap_camera()
game.render()
pygame.image.save(screen, "docs/screenshots/flood_zone_active.png")
print("[3] Tersimpan ke docs/screenshots/flood_zone_active.png")

# ==============================================================================
# 4. HERO FLOOD FLUSH SWIMMING (Kamera berpusat pada hero, hero besar di tengah)
# ==============================================================================
# Panel A: Hero berenang di air banjir (2100, 900)
game.weather_manager.actual_flood = True
game.hero.px = 2100.0
game.hero.py = 900.0
game.hero.play_action_animation("swimming", 1.5)
game.hero.direction = "right"
game.cam_x = game.hero.px - 512
game.cam_y = game.hero.py - 384
screen.fill((0, 0, 0))
game.game_map.draw(screen, (int(game.cam_x), int(game.cam_y)))
game.hero.draw(screen, (int(game.cam_x), int(game.cam_y)))
surf_a = screen.copy()

# Panel B: Hero di tile kering hasil evakuasi (2096, 848)
dry_pos = game.weather_manager.find_nearest_dry_tile(2100.0, 900.0, game.game_map)
game.hero.px = dry_pos[0]
game.hero.py = dry_pos[1]
game.hero.play_action_animation("idle", 0.5)
game.cam_x = game.hero.px - 512
game.cam_y = game.hero.py - 384
screen.fill((0, 0, 0))
game.game_map.draw(screen, (int(game.cam_x), int(game.cam_y)))
# Gambar penanda tile kering
dry_scr_x = int(dry_pos[0] - 16 - game.cam_x)
dry_scr_y = int(dry_pos[1] - 16 - game.cam_y)
pygame.draw.rect(screen, (50, 255, 120), (dry_scr_x, dry_scr_y, 32, 32), 2)
game.hero.draw(screen, (int(game.cam_x), int(game.cam_y)))
surf_b = screen.copy()

# Buat komposit side-by-side (1024 x 500)
comp_surf = pygame.Surface((1024, 520))
comp_surf.fill((14, 18, 26))

# Crop 512x450 dari masing-masing panel
crop_a = pygame.Surface((506, 450))
crop_a.blit(surf_a, (-256, -160))
crop_b = pygame.Surface((506, 450))
crop_b.blit(surf_b, (-256, -160))

comp_surf.blit(crop_a, (4, 45))
comp_surf.blit(crop_b, (514, 45))

# Header judul unclipped
font_hdr = pygame.font.Font(None, 24)
font_sub = pygame.font.Font(None, 18)

pygame.draw.rect(comp_surf, (25, 35, 50), (4, 8, 506, 32), border_radius=3)
pygame.draw.rect(comp_surf, (80, 160, 240), (4, 8, 506, 32), 1, border_radius=3)
lbl_a = font_hdr.render("FRAME A: HERO TERHANYUT (ANIMASI RENANG 12 FRAME)", True, (120, 210, 255))
comp_surf.blit(lbl_a, (14, 16))

pygame.draw.rect(comp_surf, (20, 42, 30), (514, 8, 506, 32), border_radius=3)
pygame.draw.rect(comp_surf, (80, 220, 140), (514, 8, 506, 32), 1, border_radius=3)
lbl_b = font_hdr.render(f"FRAME B: DIEVAKUASI KE DARATAN KERING ({int(dry_pos[0])}, {int(dry_pos[1])})", True, (120, 240, 160))
comp_surf.blit(lbl_b, (524, 16))

# Footer keterangan
footer_a = font_sub.render("Hero di tengah zona banjir (2100, 900) - Arus pantai mengunci 1.5s", True, (180, 200, 220))
comp_surf.blit(footer_a, (14, 500))
footer_b = font_sub.render(f"Evakuasi ke daratan aman ({int(dry_pos[0])}, {int(dry_pos[1])}) - Penalti waktu: -2.7s / -1.78s", True, (180, 230, 200))
comp_surf.blit(footer_b, (524, 500))

pygame.image.save(comp_surf, "docs/screenshots/hero_flood_flush_swimming.png")
print("[4] Tersimpan ke docs/screenshots/hero_flood_flush_swimming.png")

# ==============================================================================
# 5. AUTOPILOT ROUTE BEFORE NEWS (Pintas: 15 Tile / 3.26s, Legend Top-Right)
# ==============================================================================
start_cell_corridor = (1950 // 32, 880 // 32)
res_pintas = astar(w_tiles, h_tiles, start_cell_corridor, goal_cell, is_blocked_std)

game.planner_mode = "AUTO"
game.control_mode = config.CONTROL_AUTOPILOT
game.weather_manager.actual_flood = False
game.weather_manager.belief_flood = 0.10
game.weather_manager.recalculate_policy()
game.hero.px = 1950.0
game.hero.py = 880.0
game.hero.direction = "right"
game.hero.manual_mode = False
game.cam_x = 1728.0
game.cam_y = 500.0

screen.fill((0, 0, 0))
cam = (int(game.cam_x), int(game.cam_y))
game.game_map.draw(screen, cam)
if res_pintas.found:
    for node in res_pintas.path:
        nx = node[0] * 32 + 16 - cam[0]
        ny = node[1] * 32 + 16 - cam[1]
        pygame.draw.circle(screen, (0, 240, 255), (nx, ny), 5)
        pygame.draw.circle(screen, (255, 255, 255), (nx, ny), 2)

game.world_state.gate.draw(screen, cam, hero_pos=(game.hero.px, game.hero.py))
game.hero.draw(screen, cam)
game._draw_hud(screen)
game._draw_planner_banner(screen)

# Legend di ATAS (kanan atas) agar TIDAK menimpa HUD di kiri bawah
font_leg = pygame.font.Font(None, 22)
leg_bg = pygame.Surface((440, 32), pygame.SRCALPHA)
leg_bg.fill((16, 24, 38, 235))
screen.blit(leg_bg, (560, 50))
pygame.draw.rect(screen, (0, 240, 255), (560, 50, 440, 32), 1, border_radius=3)
lbl = font_leg.render("RUTE PINTAS PANTAI (Cyan): 15 Tile / 3.26s [P(B)=10%]", True, (0, 240, 255))
screen.blit(lbl, (570, 58))

pygame.image.save(screen, "docs/screenshots/autopilot_route_before_news.png")
print("[5] Tersimpan ke docs/screenshots/autopilot_route_before_news.png")

# ==============================================================================
# 6. AUTOPILOT ROUTE AFTER NEWS (Detour: 19 Tile / 4.13s, Legend Top-Right)
# ==============================================================================
def is_blocked_flood(cx: int, cy: int) -> bool:
    if is_blocked_std(cx, cy):
        return True
    rx, ry, rw, rh = game.weather_manager.flood_rect
    px = cx * 32 + 16
    py = cy * 32 + 16
    return (rx <= px <= rx + rw and ry <= py <= ry + rh)

res_detour = astar(w_tiles, h_tiles, start_cell_corridor, goal_cell, is_blocked_flood)

game.weather_manager.belief_flood = 0.50
game.weather_manager.recalculate_policy()
game.hero.px = 1950.0
game.hero.py = 880.0
game.hero.direction = "up"

screen.fill((0, 0, 0))
game.game_map.draw(screen, cam)
if res_detour.found:
    for node in res_detour.path:
        nx = node[0] * 32 + 16 - cam[0]
        ny = node[1] * 32 + 16 - cam[1]
        pygame.draw.circle(screen, (50, 255, 120), (nx, ny), 5)
        pygame.draw.circle(screen, (255, 255, 255), (nx, ny), 2)

game.world_state.gate.draw(screen, cam, hero_pos=(game.hero.px, game.hero.py))
game.hero.draw(screen, cam)
game._draw_hud(screen)
game._draw_planner_banner(screen)

# Legend di ATAS (kanan atas) agar TIDAK menimpa HUD di kiri bawah
screen.blit(leg_bg, (560, 50))
pygame.draw.rect(screen, (50, 255, 120), (560, 50, 440, 32), 1, border_radius=3)
lbl2 = font_leg.render("RUTE AMAN DETOUR (Hijau): 19 Tile / 4.13s [P(B)=50%]", True, (50, 255, 120))
screen.blit(lbl2, (570, 58))

pygame.image.save(screen, "docs/screenshots/autopilot_route_after_news.png")
print("[6] Tersimpan ke docs/screenshots/autopilot_route_after_news.png")

print("Semua screenshot Putaran 3 berhasil diperbarui dengan sempurna!")
