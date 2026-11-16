#!/usr/bin/env python3
"""
capture_entity_wall_screenshots.py
Mengambil 3 screenshot in-game sesuai instruksi:
1. Sapi berjalan di samping dinding rumah tanpa menembus (F1 OFF dan side-by-side F1 ON)
2. Domba berjalan di samping dinding rumah tanpa menembus (F1 OFF dan side-by-side F1 ON)
3. NPC berjalan di samping dinding rumah tanpa menembus (F1 OFF dan side-by-side F1 ON)

Semua screenshot diambil dengan kamera berpusat pada subjek yang dibahas,
tanpa overlay penutup.
"""
import os
import sys
import pygame

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("src"))
os.environ["SDL_VIDEODRIVER"] = "dummy"

import config
from asset_loader import AssetManager
from main import Game


def create_side_by_side(surf_normal: pygame.Surface, surf_f1: pygame.Surface,
                        cx: int, cy: int, crop_w: int = 480, crop_h: int = 360,
                        title: str = "") -> pygame.Surface:
    """Memotong area berpusat pada subjek dan menyandingkan F1 OFF (kiri) vs F1 ON (kanan)."""
    # Koordinat crop pada screen 1024x768
    crop_x = max(0, min(1024 - crop_w, cx - crop_w // 2))
    crop_y = max(0, min(768 - crop_h, cy - crop_h // 2))
    crop_rect = pygame.Rect(crop_x, crop_y, crop_w, crop_h)

    sub_norm = surf_normal.subsurface(crop_rect).copy()
    sub_f1 = surf_f1.subsurface(crop_rect).copy()

    # Kanvas side by side: (crop_w * 2 + 30, crop_h + 50)
    total_w = crop_w * 2 + 30
    total_h = crop_h + 50
    composite = pygame.Surface((total_w, total_h))
    composite.fill((22, 24, 32))

    font_t = pygame.font.Font(None, 24)
    font_lbl = pygame.font.Font(None, 20)

    # Header judul
    t_surf = font_t.render(title, True, (240, 240, 250))
    composite.blit(t_surf, (15, 10))

    # Kiri: F1 OFF
    lbl_off = font_lbl.render("F1 OFF (Normal Gameplay)", True, (120, 220, 140))
    composite.blit(lbl_off, (15, 30))
    composite.blit(sub_norm, (15, 45))
    pygame.draw.rect(composite, (60, 70, 90), (15, 45, crop_w, crop_h), 2)

    # Kanan: F1 ON
    lbl_on = font_lbl.render("F1 ON (Hitbox & Footprint Validasi)", True, (240, 140, 100))
    composite.blit(lbl_on, (crop_w + 20, 30))
    composite.blit(sub_f1, (crop_w + 20, 45))
    pygame.draw.rect(composite, (180, 80, 60), (crop_w + 20, 45, crop_w, crop_h), 2)

    return composite


def main():
    pygame.init()
    config.VERBOSE_SPRITE_LOGS = False
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    assets = AssetManager()
    game = Game(screen, assets)
    game.paused = False

    os.makedirs("docs/screenshots", exist_ok=True)

    # =========================================================================
    # 1. SAPI DI SAMPING DINDING RUMAH (building_22_17 pada 704, 544)
    # =========================================================================
    cow = next((a for a in game.tile_map.animals if a.kind == "cow"), None)
    if cow:
        # Posisikan sapi persis di samping dinding barat building_22_17 (footprint di x=720, y=601)
        cow.px = 690.0
        cow.py = 600.0
        cow.gx = int(cow.px // config.TILE_SIZE)
        cow.gy = int(cow.py // config.TILE_SIZE)
        cow.facing_left = False
        cow.state = "WALK"
        # Gerakkan kamera berpusat tepat pada sapi (690, 600)
        game.cam_x, game.cam_y = game.game_map.clamp_camera(cow.px - 512, cow.py - 384)

        # F1 OFF
        game.debug_map_collision = False
        game.render()
        surf_norm = game.screen.copy()
        cow_path = "docs/screenshots/cow_wall_collision.png"
        pygame.image.save(surf_norm, cow_path)
        print(f"Saved: {cow_path}")

        # F1 ON
        game.debug_map_collision = True
        game.render()
        surf_f1 = game.screen.copy()

        # Side by side
        cow_scr_x = int(cow.px - game.cam_x)
        cow_scr_y = int(cow.py - game.cam_y)
        comp = create_side_by_side(surf_norm, surf_f1, cow_scr_x, cow_scr_y,
                                   title="Sapi Berjalan di Samping Dinding building_22_17 (Hitbox Kaki Valid)")
        sbs_path = "docs/screenshots/cow_wall_collision_side_by_side.png"
        pygame.image.save(comp, sbs_path)
        print(f"Saved: {sbs_path}")

    # =========================================================================
    # 2. DOMBA DI SAMPING DINDING RUMAH (building_55_31 pada 1760, 992)
    # =========================================================================
    sheep = next((a for a in game.tile_map.animals if a.kind == "sheep"), None)
    if sheep:
        # Posisikan domba di samping dinding barat building_55_31 (footprint di x=1776, y=1068)
        sheep.px = 1746.0
        sheep.py = 1066.0
        sheep.gx = int(sheep.px // config.TILE_SIZE)
        sheep.gy = int(sheep.py // config.TILE_SIZE)
        sheep.facing_left = False
        sheep.state = "WALK"
        game.cam_x, game.cam_y = game.game_map.clamp_camera(sheep.px - 512, sheep.py - 384)

        # F1 OFF
        game.debug_map_collision = False
        game.render()
        surf_norm = game.screen.copy()
        sheep_path = "docs/screenshots/sheep_wall_collision.png"
        pygame.image.save(surf_norm, sheep_path)
        print(f"Saved: {sheep_path}")

        # F1 ON
        game.debug_map_collision = True
        game.render()
        surf_f1 = game.screen.copy()

        sheep_scr_x = int(sheep.px - game.cam_x)
        sheep_scr_y = int(sheep.py - game.cam_y)
        comp = create_side_by_side(surf_norm, surf_f1, sheep_scr_x, sheep_scr_y,
                                   title="Domba Berjalan di Samping Dinding building_55_31 (Hitbox Kaki Valid)")
        sbs_path = "docs/screenshots/sheep_wall_collision_side_by_side.png"
        pygame.image.save(comp, sbs_path)
        print(f"Saved: {sbs_path}")

    # =========================================================================
    # 3. NPC (PAK TANI) DI SAMPING DINDING RUMAH (building_32_19 pada 1024, 608)
    # =========================================================================
    if game.npcs:
        npc = game.npcs[0]  # Pak Tani
        # Posisikan NPC di samping dinding barat building_32_19 (footprint di x=1040, y=704)
        npc.px = 1012.0
        npc.py = 704.0
        npc.sort_y = npc.py
        game.cam_x, game.cam_y = game.game_map.clamp_camera(npc.px - 512, npc.py - 384)

        # F1 OFF
        game.debug_map_collision = False
        game.render()
        surf_norm = game.screen.copy()
        npc_path = "docs/screenshots/npc_wall_collision.png"
        pygame.image.save(surf_norm, npc_path)
        print(f"Saved: {npc_path}")

        # F1 ON
        game.debug_map_collision = True
        game.render()
        surf_f1 = game.screen.copy()

        npc_scr_x = int(npc.px - game.cam_x)
        npc_scr_y = int(npc.py - game.cam_y)
        comp = create_side_by_side(surf_norm, surf_f1, npc_scr_x, npc_scr_y,
                                   title="NPC Pak Tani di Samping Dinding building_32_19 (Hitbox Kaki Valid)")
        sbs_path = "docs/screenshots/npc_wall_collision_side_by_side.png"
        pygame.image.save(comp, sbs_path)
        print(f"Saved: {sbs_path}")

    # =========================================================================
    # 4. NPC (KANG PENGGILING) DI SAMPING DINDING KINCIR (building_40_33 pada 1280, 1056)
    # =========================================================================
    if len(game.npcs) > 1:
        miller = game.npcs[1]  # Kang Penggiling
        # Posisikan miller di samping barat pondasi kincir angin (footprint x=1312, y=1136)
        miller.px = 1290.0
        miller.py = 1136.0
        miller.sort_y = miller.py
        game.cam_x, game.cam_y = game.game_map.clamp_camera(miller.px - 512, miller.py - 384)

        game.debug_map_collision = False
        game.render()
        surf_norm = game.screen.copy()

        game.debug_map_collision = True
        game.render()
        surf_f1 = game.screen.copy()

        m_scr_x = int(miller.px - game.cam_x)
        m_scr_y = int(miller.py - game.cam_y)
        comp_m = create_side_by_side(surf_norm, surf_f1, m_scr_x, m_scr_y,
                                     title="Kang Penggiling di Samping Dinding building_40_33 (Hitbox Kaki Valid)")
        miller_sbs_path = "docs/screenshots/miller_wall_collision_side_by_side.png"
        pygame.image.save(comp_m, miller_sbs_path)
        print(f"Saved: {miller_sbs_path}")

    # =========================================================================
    # 5. EXPLORASI BERSIH NORMAL (F1 OFF, t=6.0s TANPA OVERLAY)
    # =========================================================================
    game.debug_map_collision = False
    game.messages.clear()
    game.time = 6.0
    game.hero.px = 1440.0
    game.hero.py = 1056.0
    game.cam_x, game.cam_y = game.game_map.clamp_camera(game.hero.px - 512, game.hero.py - 384)
    game.render()
    clean_path = "docs/screenshots/clean_exploration_5s.png"
    pygame.image.save(game.screen, clean_path)
    print(f"Saved: {clean_path}")

    # =========================================================================
    # 6. OKLUSI ATAP 2.5D: ENTITAS BERJALAN DI BELAKANG RUMAH (building_45_15)
    # =========================================================================
    # building_45_15 di (1440, 480). Footprint di y=556..640.
    # Area utara (y=500..550) adalah koridor walkable di belakang atap rumah.
    game.hero.px = 1500.0
    game.hero.py = 520.0
    game.hero.direction = "right"
    game.cam_x, game.cam_y = game.game_map.clamp_camera(game.hero.px - 512, game.hero.py - 384)

    game.debug_map_collision = False
    game.render()
    surf_norm = game.screen.copy()

    game.debug_map_collision = True
    game.render()
    surf_f1 = game.screen.copy()

    h_scr_x = int(game.hero.px - game.cam_x)
    h_scr_y = int(game.hero.py - game.cam_y)
    comp_roof = create_side_by_side(surf_norm, surf_f1, h_scr_x, h_scr_y,
                                    title="Kebijakan Atap 2.5D: Hero Melintas di Belakang Atap building_45_15 (Y-Sort)")
    roof_sbs_path = "docs/screenshots/roof_occlusion_behind_house.png"
    pygame.image.save(comp_roof, roof_sbs_path)
    print(f"Saved: {roof_sbs_path}")


if __name__ == "__main__":
    main()
