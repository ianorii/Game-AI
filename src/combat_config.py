"""
combat_config.py - Konfigurasi Terpusat untuk Sistem Real-Time Combat.

Semua parameter stat, jarak, cooldown, hitbox, durasi animasi,
dan kontrol tombol didefinisikan di sini tanpa angka ajaib.
"""

import os
from pathlib import Path
import pygame

# Direktori proyek
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
MAPS_DIR = ASSETS_DIR / "maps"

# File Data Spawn Musuh
ENEMIES_JSON_PATH = str(MAPS_DIR / "enemies.json")

# ==============================================================================
# STAT & PERILAKU GOBLIN (MINION)
# ==============================================================================
GOB_MAX_HP = 3                     # Hit Point awal goblin
GOB_PATROL_SPEED = 35.0            # Kecepatan saat patroli santai (px/detik)
GOB_CHASE_SPEED = 90.0             # Kecepatan saat mengejar player (px/detik)
GOB_CHASE_RADIUS = 220.0           # Jarak deteksi player untuk mulai mengejar (px)
GOB_DELEASH_RADIUS = 340.0         # Jarak batas lepas pengejaran / hysteresis (px)
GOB_ATTACK_RANGE = 30.0            # Jarak serang ke player (px)
GOB_ATTACK_WINDUP_SEC = 0.35       # Jeda persiapan serang sebelum damage diaplikasikan
GOB_ATTACK_COOLDOWN_SEC = 1.25     # Cooldown jeda antar serangan goblin (detik)
GOB_DAMAGE = 3                     # Damage kecil yang dihasilkan goblin ke player (minion musuh kecil)
GOB_HURT_STUN_SEC = 0.28           # Durasi terhenti saat kena serangan (hit-stun)
GOB_KNOCKBACK_SPEED = 140.0        # Kecepatan dorongan knockback saat terkena hit (px/s)
GOB_KNOCKBACK_DECAY = 8.0          # Laju perlambatan knockback per detik
GOB_FEET_HITBOX_W = 12             # Lebar hitbox kaki goblin untuk walkable mask
GOB_FEET_HITBOX_H = 8              # Tinggi hitbox kaki goblin untuk walkable mask
GOB_DEATH_ANIM_SPEED = 0.05        # Detik per frame animasi mati goblin (mati & hilang cepat)

# ==============================================================================
# STAT & MEKANIK SERANGAN PLAYER
# ==============================================================================
PLAYER_MAX_HP = 100                # HP maksimal player (100 HP)
PLAYER_ATTACK_DAMAGE = 1           # Damage serangan player per ayunan (goblin mati dalam 3x serangan)
PLAYER_ATTACK_RANGE = 52.0         # Jarak serangan otomatis mengenai goblin (px, ~1.6 tile)
PLAYER_ATTACK_COOLDOWN_SEC = 0.45  # Cooldown antar serangan (detik)
PLAYER_ATTACK_DURATION_SEC = 0.35  # Total durasi animasi ayunan serangan (detik)
PLAYER_ATTACK_ACTIVE_START = 0.30  # Progres animasi saat hitbox serang mulai aktif (0.0 - 1.0)
PLAYER_ATTACK_ACTIVE_END = 0.80    # Progres animasi saat hitbox serang berakhir
PLAYER_ATTACK_RANGE_OFFSET = 18    # Jarak jangkauan hitbox di depan player (px)
PLAYER_ATTACK_HITBOX_W = 32        # Lebar hitbox serangan player (px)
PLAYER_ATTACK_HITBOX_H = 32        # Tinggi hitbox serangan player (px)
PLAYER_ATTACK_SPEED_MULT = 0.3     # Multiplier kecepatan jalan saat mengayunkan senjata
PLAYER_INVULN_SEC = 0.8            # Durasi kebal (i-frame) setelah terkena damage
PLAYER_HIT_FLASH_SEC = 0.35        # Durasi berkedip putih saat terkena hit
PLAYER_KNOCKBACK_FORCE = 120.0     # Dorongan ke player saat terkena hit (px/s)
PLAYER_FEET_HITBOX_W = 14          # Lebar hitbox kaki player untuk walkable mask
PLAYER_FEET_HITBOX_H = 8           # Tinggi hitbox kaki player untuk walkable mask

# Kontrol Tombol Serang
ATTACK_KEY = pygame.K_SPACE        # Tombol keyboard untuk menyerang
ATTACK_MOUSE_BUTTON = 1            # Tombol mouse untuk menyerang (1 = Left Click)

# ==============================================================================
# SCREEN SHAKE & EFEK VISUAL
# ==============================================================================
SCREEN_SHAKE_ENABLED = True        # Aktifkan getaran layar ringan saat serangan mendarat
SCREEN_SHAKE_DURATION = 0.12       # Durasi getar (detik)
SCREEN_SHAKE_INTENSITY = 3.0       # Intensitas simpangan getar (piksel)
