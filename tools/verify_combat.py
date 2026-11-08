"""
verify_combat.py - Script Verifikasi Lengkap Sistem Combat Real-Time

Memeriksa secara otomatis dan headless:
1. Validasi titik spawn musuh di enemies.json (100% walkable).
2. Perilaku deteksi Goblin (IDLE -> CHASE -> IDLE saat lepas radius).
3. Pengecekan Walkable Mask: simulasi 600 frame chase & knockback (target: 0 frame blocked).
4. Mekanik serangan player: arah hadap, jangkauan, dan pencegahan multi-hit per ayunan.
5. Animasi kematian goblin dan penghapusan dari game.
6. Damage ke player, i-frames, game over, dan restart [R].
"""

import os
import sys
import math
from pathlib import Path

# Setup headless SDL driver
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pygame
pygame.init()
pygame.display.set_mode((1024, 768))

import config
config.WORLD_GOBLINS_ACTIVE = True  # Aktifkan goblin khusus pengujian combat verification
import combat_config as ccfg
from asset_loader import AssetManager
from world.game_map import GameMap
from core.entity import Hero
from entities.goblin import Goblin
from entities.vfx import VisualEffect
from main import Game, create_display


def test_1_spawn_walkable():
    print("--- [TEST 1] Validasi Titik Spawn Walkable ---")
    gmap = GameMap(scale=config.MAP_SCALE)
    assets = AssetManager()
    screen = pygame.display.get_surface()
    game = Game(screen, assets)
    
    assert len(game.goblins) > 0, "Goblin harus ada yang dimuat dari enemies.json"
    print(f"Berhasil memuat {len(game.goblins)} goblin dari assets/maps/enemies.json.")
    
    for i, gob in enumerate(game.goblins):
        hb = gob.feet_hitbox()
        solid = gmap.is_solid(hb)
        print(f"  Goblin #{i+1} pos=({gob.x:.1f}, {gob.y:.1f}) feet_hitbox={hb} solid={solid}")
        assert not solid, f"Goblin #{i+1} spawn di area blocked!"
    print("[TEST 1 PASSED] Semua titik spawn goblin 100% walkable!\n")


def test_2_detection_and_deleash():
    print("--- [TEST 2] Deteksi dan Deleash (Hysteresis) ---")
    gmap = GameMap(scale=config.MAP_SCALE)
    assets = AssetManager()
    hero = Hero(10, 10, assets)
    gob = Goblin(500.0, 500.0, assets.goblin_anims)
    
    # 1. Jauh di luar radius deteksi (misal 400px > 220px)
    hero.px = 500.0 + ccfg.GOB_CHASE_RADIUS + 80.0
    hero.py = 500.0
    gob.update(0.1, hero, gmap)
    assert gob.state == Goblin.STATE_IDLE, f"Harusnya IDLE, tapi {gob.state}"
    print(f"  Jarak {ccfg.GOB_CHASE_RADIUS + 80.0:.1f}px (> deteksi {ccfg.GOB_CHASE_RADIUS}px) -> State: {gob.state}")
    
    # 2. Mendekat ke dalam radius deteksi (misal 150px <= 220px)
    hero.px = 500.0 + ccfg.GOB_CHASE_RADIUS - 50.0
    gob.update(0.1, hero, gmap)
    assert gob.state == Goblin.STATE_CHASE, f"Harusnya CHASE, tapi {gob.state}"
    print(f"  Jarak {ccfg.GOB_CHASE_RADIUS - 50.0:.1f}px (<= deteksi) -> State: {gob.state}")
    
    # 3. Menjauh ke zona hysteresis (antara chase radius dan deleash radius, misal 260px)
    # Harus TETAP mengejar karena belum melewati deleash radius
    hero.px = 500.0 + 260.0
    gob.update(0.1, hero, gmap)
    assert gob.state == Goblin.STATE_CHASE, f"Harusnya TETAP CHASE di zona hysteresis, tapi {gob.state}"
    print(f"  Jarak 260.0px (antara deteksi & lepas {ccfg.GOB_DELEASH_RADIUS}px) -> State TETAP: {gob.state} (Hysteresis OK)")
    
    # 4. Menjauh melewati batas lepas (misal 360px > deleash 340px)
    hero.px = 500.0 + ccfg.GOB_DELEASH_RADIUS + 20.0
    gob.update(0.1, hero, gmap)
    assert gob.state == Goblin.STATE_IDLE, f"Harusnya lepas ke IDLE, tapi {gob.state}"
    print(f"  Jarak {ccfg.GOB_DELEASH_RADIUS + 20.0:.1f}px (> lepas) -> State: {gob.state}")
    print("[TEST 2 PASSED] Deteksi & Deleash hysteresis bekerja sempurna!\n")


def test_3_walkable_mask_collision():
    print("--- [TEST 3] Walkable Mask: Simulasi 600 Frame Chase & Knockback ---")
    gmap = GameMap(scale=config.MAP_SCALE)
    assets = AssetManager()
    hero = Hero(10, 10, assets)
    
    # Letakkan goblin di dekat dinding/tebing (area NW Farm: 544, 384)
    gob = Goblin(544.0, 384.0, assets.goblin_anims)
    
    # Simulasi player bergerak di berbagai titik rintangan (di seberang dinding, air, dll)
    player_target_points = [
        (450.0, 300.0),  # Di sudut tebing
        (600.0, 200.0),  # Di balik rumah/dinding
        (300.0, 500.0),  # Dekat air
        (700.0, 450.0),  # Melintasi semak
    ]
    
    blocked_frames = 0
    total_frames = 0
    
    for target in player_target_points:
        hero.px, hero.py = target
        for _ in range(150):
            total_frames += 1
            gob.update(1.0 / 60.0, hero, gmap)
            hb = gob.feet_hitbox()
            if gmap.is_solid(hb):
                blocked_frames += 1
    
    print(f"  Simulasi Pengejaran: {total_frames} frame dijalankan. Frame blocked: {blocked_frames}")
    assert blocked_frames == 0, f"Goblin masuk ke area blocked sebanyak {blocked_frames} frame!"
    
    # Tes Knockback mendorong goblin ke arah tebing/dinding
    kb_blocked_frames = 0
    kb_tests = 0
    angles = [0, 45, 90, 135, 180, 225, 270, 315]
    import math
    for ang in angles:
        rad = math.radians(ang)
        kb_vec = (math.cos(rad), math.sin(rad))
        gob.take_damage(1, kb_vec)
        for _ in range(30):
            kb_tests += 1
            gob.update(1.0 / 60.0, hero, gmap)
            hb = gob.feet_hitbox()
            if gmap.is_solid(hb):
                kb_blocked_frames += 1
    
    print(f"  Simulasi Knockback: {kb_tests} frame dorongan ke berbagai arah. Frame blocked: {kb_blocked_frames}")
    assert kb_blocked_frames == 0, f"Knockback mendorong goblin masuk area blocked ({kb_blocked_frames} frame)!"
    print("[TEST 3 PASSED] Goblin tidak pernah menembus dinding/air (0 frame blocked)!\n")


def test_4_and_5_player_attack_mechanics():
    print("--- [TEST 4 & 5] Serangan Player & Anti Multi-Hit ---")
    gmap = GameMap(scale=config.MAP_SCALE)
    assets = AssetManager()
    screen = pygame.display.get_surface()
    game = Game(screen, assets)
    
    hero = game.hero
    hero.px = 600.0
    hero.py = 600.0
    hero.direction = "right"
    
    # 1. Goblin berada tepat di depan arah serang player (+20px X)
    gob_front = Goblin(620.0, 600.0, assets.goblin_anims)
    game.goblins = [gob_front]
    initial_hp = gob_front.hp
    
    # Trigger serangan
    hero.start_attack()
    assert hero.is_attacking, "Hero harus dalam status menyerang"
    
    # Jalankan loop serangan frame per frame sepanjang durasi ayunan
    dt = 1.0 / 60.0
    hits_recorded = 0
    total_time = 0.0
    
    while total_time <= ccfg.PLAYER_ATTACK_DURATION_SEC + 0.1:
        total_time += dt
        hero.update(dt)
        atk_hb = hero.get_attack_hitbox()
        if atk_hb is not None and atk_hb.colliderect(gob_front.body_rect()):
            if gob_front not in hero.attack_hit_enemies:
                hero.attack_hit_enemies.add(gob_front)
                gob_front.take_damage(ccfg.PLAYER_ATTACK_DAMAGE, (1, 0))
                hits_recorded += 1
        gob_front.update(dt, hero, gmap)
    
    print(f"  Goblin di depan: damage diterima = {initial_hp - gob_front.hp}, jumlah hit tercatat = {hits_recorded}")
    assert hits_recorded == 1, f"Harus tepat 1 hit per ayunan, tapi terjadi {hits_recorded} hit!"
    assert gob_front.hp == initial_hp - ccfg.PLAYER_ATTACK_DAMAGE, "HP goblin harus berkurang tepat sesuai damage serang!"
    
    # 2. Goblin di luar jarak jangkau (misal 90px > 52px)
    gob_far = Goblin(690.0, 600.0, assets.goblin_anims)
    game.goblins = [gob_far]
    init_hp_far = gob_far.hp
    
    hero.attack_cooldown = 0.0
    game._trigger_player_attack()
    total_time = 0.0
    while total_time <= ccfg.PLAYER_ATTACK_DURATION_SEC + 0.1:
        total_time += dt
        hero.update(dt)
        game.update_explore(dt)
        
    print(f"  Goblin di luar jarak ({math.hypot(gob_far.x - hero.px, gob_far.y - hero.py):.1f}px > {ccfg.PLAYER_ATTACK_RANGE}px): HP awal = {init_hp_far}, HP akhir = {gob_far.hp}")
    assert gob_far.hp == init_hp_far, "Serangan TIDAK boleh mengenai musuh yang di luar jarak!"

    # 3. Goblin mati setelah tepat 3 kali serangan
    gob_3hit = Goblin(635.0, 600.0, assets.goblin_anims)
    game.goblins = [gob_3hit]
    assert gob_3hit.hp == 3, "HP awal goblin harus 3"

    for attack_num in range(1, 4):
        hero.attack_cooldown = 0.0
        game._trigger_player_attack()
        total_time = 0.0
        while total_time <= ccfg.PLAYER_ATTACK_DURATION_SEC + 0.05:
            total_time += dt
            hero.update(dt)
            game.update_explore(dt)
        expected_hp = 3 - attack_num
        print(f"  Serangan ke-{attack_num}: Sisa HP goblin = {gob_3hit.hp} (diharapkan {expected_hp})")
        assert gob_3hit.hp == expected_hp, f"Setelah serangan ke-{attack_num}, HP goblin harus {expected_hp}, tapi {gob_3hit.hp}"

    assert gob_3hit.hp == 0 and gob_3hit.state == Goblin.STATE_DEAD, "Goblin harus mati pada serangan ke-3!"
    print("[TEST 4 & 5 PASSED] Auto-hit dalam jarak jangkau & goblin mati tepat 3 kali serangan!\n")


def test_6_goblin_death():
    print("--- [TEST 6] Kematian Goblin & Penghentian Serangan ---")
    gmap = GameMap(scale=config.MAP_SCALE)
    assets = AssetManager()
    hero = Hero(10, 10, assets)
    gob = Goblin(500.0, 500.0, assets.goblin_anims)
    
    # Beri damage mematikan
    gob.take_damage(ccfg.GOB_MAX_HP, (1, 0))
    assert gob.hp == 0, "HP goblin harus 0"
    assert gob.state == Goblin.STATE_DEAD, f"State harus DEAD, tapi {gob.state}"
    print(f"  Goblin terkena lethal damage -> State: {gob.state}, HP: {gob.hp}")
    
    # Majukan waktu selama animasi kematian
    dt = 0.05
    for _ in range(30):
        gob.update(dt, hero, gmap)
    
    assert not gob.alive, "Setelah animasi kematian selesai, gob.alive harus False"
    print(f"  Animasi selesai -> gob.alive = {gob.alive} (siap diabaikan/dihapus)")
    print("[TEST 6 PASSED] Kematian goblin terverifikasi bersih!\n")


def test_7_player_damage_iframe_and_gameover():
    print("--- [TEST 7] Player Damage, I-Frames, Game Over & Restart [R] ---")
    assets = AssetManager()
    screen = pygame.display.get_surface()
    game = Game(screen, assets)
    
    hero = game.hero
    init_hp = hero.hp
    assert hero.max_hp == 100, f"Player max HP harus 100, tapi {hero.max_hp}"
    assert hero.hp == 100, f"Player HP awal harus 100, tapi {hero.hp}"
    print(f"  Player HP awal: {hero.hp}/{hero.max_hp}")
    
    # 1. Goblin memberi damage ke player
    gob_dmg = ccfg.GOB_DAMAGE
    dmg = hero.take_combat_damage(gob_dmg, (1, 0))
    assert dmg == gob_dmg, f"Player harus menerima {gob_dmg} damage"
    assert hero.hp == init_hp - gob_dmg, f"HP player harus berkurang {gob_dmg}"
    assert hero.invuln > 0.0, "Player harus memiliki i-frame (> 0 detik)"
    print(f"  Player terkena hit ({gob_dmg} dmg) -> HP: {hero.hp}, i-frame timer: {hero.invuln:.2f}s")
    
    # 2. Serangan kedua saat i-frame aktif tidak boleh mengurangi HP
    dmg2 = hero.take_combat_damage(gob_dmg, (1, 0))
    assert dmg2 == 0, "Serangan saat i-frame aktif harus diabaikan (0 damage)"
    assert hero.hp == init_hp - gob_dmg, "HP tidak boleh berkurang saat i-frame"
    print("  Serangan kedua saat i-frame aktif berhasil ditangkis (0 damage)!")
    
    # 3. Kuras HP player sampai 0 -> Game Over
    hero.invuln = 0.0
    hero.take_combat_damage(hero.hp, (1, 0))
    assert hero.hp == 0 and not hero.alive, "Player harus mati saat HP habis"
    game.update_explore(0.01)
    assert game.state == config.STATE_GAME_OVER, f"Game state harus STATE_GAME_OVER, tapi {game.state}"
    print(f"  HP habis -> Game state: {game.state}")
    
    # 4. Tekan 'R' untuk restart
    game._on_key(pygame.K_r)
    assert game.hero.alive, "Setelah [R], player harus hidup kembali"
    assert game.hero.hp == game.hero.max_hp, "Setelah [R], HP player harus penuh"
    assert game.state == config.STATE_EXPLORATION, "Setelah [R], state harus kembali ke EXPLORATION"
    assert all(g.alive and g.hp == g.max_hp for g in game.goblins), "Semua goblin harus di-reset ke spawn & HP penuh"
    print("  Tekan [R] restart -> Player HP penuh di titik spawn & seluruh goblin di-reset!")
    print("[TEST 7 PASSED] Damage, I-frames, Game Over, dan Restart berfungsi sempurna!\n")


if __name__ == "__main__":
    print("==================================================================")
    print("MEMULAI SUITE VERIFIKASI LENGKAP COMBAT REAL-TIME")
    print("==================================================================")
    test_1_spawn_walkable()
    test_2_detection_and_deleash()
    test_3_walkable_mask_collision()
    test_4_and_5_player_attack_mechanics()
    test_6_goblin_death()
    test_7_player_damage_iframe_and_gameover()
    print("==================================================================")
    print("SELURUH 7 TEST CASE COMBAT BERHASIL 100% TANPA KESALAHAN!")
    print("==================================================================")
