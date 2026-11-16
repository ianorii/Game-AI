#!/usr/bin/env python3
"""
tools/capture_beach_gate_screenshots.py
Menghasilkan tangkapan layar gerbang chokepoint menuju Boss:
  1. gate_closeup_closed.png: Hero di depan gerbang tertutup, kamera terpusat pada gerbang, F1 Mati.
  2. gate_closeup_open.png: Hero di depan gerbang terbuka, kamera terpusat pada gerbang, F1 Mati.
  3. beach_gate_closed_normal.png: Area pantai & gerbang tertutup, kamera clamped tanpa bilah hitam, F1 Mati.
  4. beach_gate_open_normal.png: Area pantai & gerbang terbuka, F1 Mati.
  5. beach_gate_f1_debug.png: Dinding koridor kiri/kanan, obstacle gerbang, dan jalur A* saat terbuka.
"""
import os
import sys
sys.path.insert(0, "src")
sys.path.insert(0, ".")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame
pygame.init()

from main import create_display, Game
from asset_loader import AssetManager
from world_state import LockedGate
from ai.pathfinding import astar
import config

os.makedirs("docs/screenshots", exist_ok=True)

screen = create_display()
assets = AssetManager()
game = Game(screen, assets, seed=20261021)

# Pastikan kamera clamped tepat (map 2752x1536, view 1024x768 -> max_x = 1728, max_y = 768)
gate_x = game.world_state.gate.x
gate_y = game.world_state.gate.y
gate_w = game.world_state.gate.w
gate_h = game.world_state.gate.h

# Tempatkan Hero persis di depan gerbang (di selatan gerbang, misal x = gate_x + gate_w//2, y = gate_y + gate_h + 30)
hero_gate_x = float(gate_x + gate_w // 2)
hero_gate_y = float(gate_y + gate_h + 36)
game.hero.px = hero_gate_x
game.hero.py = hero_gate_y
game.hero.direction = "up"

# 1. Close-up Gerbang Tertutup (Kamera berpusat pada gerbang)
# Viewport 1024x768, target center = (gate_x + gate_w//2, gate_y + gate_h//2)
cam_gate = game.game_map.clamp_camera(
    int(gate_x + gate_w // 2 - 512),
    int(gate_y + gate_h // 2 - 384)
)

game.world_state.gate.is_open = False
game.show_debug = False

# Render closed closeup
screen.fill((0, 0, 0))
game.game_map.draw(screen, cam_gate)
# Draw entities
game.world_state.gate.draw(screen, cam_gate, hero_pos=(game.hero.px, game.hero.py))
game.hero.draw(screen, cam_gate)
# Crop close-up 400x320 centered on gate
gate_screen_x = int(gate_x - cam_gate[0])
gate_screen_y = int(gate_y - cam_gate[1])
closeup_rect = pygame.Rect(gate_screen_x - 152, gate_screen_y - 120, 400, 320)
closeup_closed = screen.subsurface(closeup_rect).copy()
pygame.image.save(closeup_closed, "docs/screenshots/gate_closeup_closed.png")
print("[gate_screenshots] Saved docs/screenshots/gate_closeup_closed.png")

# 2. Close-up Gerbang Terbuka (Kamera sama, Hero sama, gerbang terbuka)
game.world_state.gate.is_open = True
screen.fill((0, 0, 0))
game.game_map.draw(screen, cam_gate)
game.world_state.gate.draw(screen, cam_gate, hero_pos=(game.hero.px, game.hero.py))
game.hero.draw(screen, cam_gate)
closeup_open = screen.subsurface(closeup_rect).copy()
pygame.image.save(closeup_open, "docs/screenshots/gate_closeup_open.png")
print("[gate_screenshots] Saved docs/screenshots/gate_closeup_open.png")

# 2b. Close-up Berdampingan (Side-by-side dengan label)
side_surf = pygame.Surface((920, 360))
side_surf.fill((20, 24, 32))
side_surf.blit(closeup_closed, (20, 32))
side_surf.blit(closeup_open, (460, 32))

font_side = pygame.font.Font(None, 24)
lbl_c = font_side.render("GERBANG TERTUTUP (SOLID & GEMBOK)", True, (255, 215, 100))
lbl_o = font_side.render("GERBANG TERBUKA (LORONG BEBAS)", True, (100, 255, 180))
side_surf.blit(lbl_c, (30, 8))
side_surf.blit(lbl_o, (470, 8))

pygame.image.save(side_surf, "docs/screenshots/gate_closeup_side_by_side.png")
print("[gate_screenshots] Saved docs/screenshots/gate_closeup_side_by_side.png")

# 3. Beach Area Clamped Views (Full Screen 1024x768, camera clamped to map edge)
# cam_x = 1728 (tepi timur pulau), cam_y = 500 (area koridor pantai)
cam_beach = (1728, 500)

# 3a. Beach Gate Closed Normal (F1 OFF)
game.world_state.gate.is_open = False
game.show_debug = False
game.messages.clear()
game.time = 6.0  # Log pembuka sudah hilang

# Render full screen
screen.fill((0, 0, 0))
game.game_map.draw(screen, cam_beach)
game.world_state.gate.draw(screen, cam_beach, hero_pos=(game.hero.px, game.hero.py))
game.hero.draw(screen, cam_beach)
pygame.image.save(screen, "docs/screenshots/beach_gate_closed_normal.png")
print("[gate_screenshots] Saved docs/screenshots/beach_gate_closed_normal.png")

# 3b. Beach Gate Open Normal (F1 OFF)
game.world_state.gate.is_open = True
screen.fill((0, 0, 0))
game.game_map.draw(screen, cam_beach)
game.world_state.gate.draw(screen, cam_beach, hero_pos=(game.hero.px, game.hero.py))
game.hero.draw(screen, cam_beach)
pygame.image.save(screen, "docs/screenshots/beach_gate_open_normal.png")
print("[gate_screenshots] Saved docs/screenshots/beach_gate_open_normal.png")

# 4. Beach Gate F1 Debug (Overlay Walkable Mask, Dinding Koridor Kiri/Kanan, Obstacle Gerbang, dan Jalur A* saat terbuka)
game.show_debug = True
screen.fill((0, 0, 0))
game.game_map.draw(screen, cam_beach)
# Gambar debug walkable mask & footprints
game.game_map.draw_debug(screen, cam_beach, cursor_screen_pos=(0, 0))
# Gambar obstacle gerbang
obs = game.world_state.gate.collision_rect
obs_screen = pygame.Rect(obs.x - cam_beach[0], obs.y - cam_beach[1], obs.w, obs.h)
obs_surf = pygame.Surface((obs.w, obs.h), pygame.SRCALPHA)
obs_surf.fill((255, 140, 20, 160))
pygame.draw.rect(obs_surf, (255, 200, 40), (0, 0, obs.w, obs.h), 3)
screen.blit(obs_surf, (obs_screen.x, obs_screen.y))

# Hitung jalur A* menuju Boss saat gerbang terbuka
w_tiles = game.game_map.width // 16
h_tiles = game.game_map.height // 16
start_cell = (int(game.hero.px // 16), int(game.hero.py // 16))
boss_cell = (config.LOCATIONS["boss"][0] // 16, config.LOCATIONS["boss"][1] // 16)

def is_blocked(cx, cy):
    foot = pygame.Rect(cx * 16 + 4, cy * 16 + 4, 8, 8)
    return not game.game_map.can_stand(foot)

astar_res = astar(w_tiles, h_tiles, start_cell, boss_cell, is_blocked)
if astar_res.found and astar_res.path:
    pts = [(c[0] * 16 + 8 - cam_beach[0], c[1] * 16 + 8 - cam_beach[1]) for c in astar_res.path]
    if len(pts) >= 2:
        # Gambar jalur A* dengan garis toska terang
        pygame.draw.lines(screen, (0, 255, 230), False, pts, 4)
        for pt in pts[::4]:
            pygame.draw.circle(screen, (255, 255, 100), pt, 3)

# Label keterangan debug di atas layar
font_dbg = pygame.font.Font(None, 22)
lbl_dbg = font_dbg.render("DEBUG F1: Dinding Koridor [Merah], Tapak Gerbang 96px [Oranye], Jalur A* Menuju Boss [Toska]", True, (255, 255, 255))
dbg_bg = pygame.Surface((lbl_dbg.get_width() + 16, lbl_dbg.get_height() + 8), pygame.SRCALPHA)
dbg_bg.fill((16, 20, 30, 220))
screen.blit(dbg_bg, (10, 10))
screen.blit(lbl_dbg, (18, 14))

pygame.image.save(screen, "docs/screenshots/beach_gate_f1_debug.png")
print("[gate_screenshots] Saved docs/screenshots/beach_gate_f1_debug.png")
print("Semua tangkapan layar gerbang berhasil diperbarui!")
