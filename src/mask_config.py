"""
mask_config.py - Konfigurasi sentral Walkable Mask & Collision Constraints.

Semua parameter toleransi warna, margin tepi, ukuran hitbox, titik sampling,
dan noise filter didefinisikan di sini agar mudah disesuaikan tanpa menyentuh kode runtime.
"""

import os
from pathlib import Path

# Direktori dasar
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
MAPS_DIR = ASSETS_DIR / "maps"

# File Paths
MAP_IMAGE_PATH = str(MAPS_DIR / "island_map.png")
WALKABLE_MASK_PATH = str(MAPS_DIR / "walkable_mask.png")
OVERRIDES_PATH = str(MAPS_DIR / "overrides.json")
DEBUG_PREVIEW_PATH = str(MAPS_DIR / "debug_mask_preview.png")

# Dimensi Peta HD
MAP_W = 2752
MAP_H = 1536

# Margin Tepi (Dilation)
EDGE_MARGIN_PIXELS = 2             # Lebar pelebaran (dilate) mask blocked air dan tebing (piksel)

# Noise Filter (Morphology)
MIN_WALKABLE_ISLAND_PIXELS = 25    # Hapus pulau walkable terisolasi yang lebih kecil dari N piksel
MAX_BLOCKED_HOLE_PIXELS = 12       # Tutup lubang blocked kecil di tengah jalan

# Hitbox Kaki Player & Sampling Runtime
PLAYER_FEET_HITBOX_W = 14          # Lebar kotak kaki player (piksel di koordinat map)
PLAYER_FEET_HITBOX_H = 8           # Tinggi kotak kaki player (piksel di koordinat map)
SUBSTEP_MAX_PIXELS = 2.0           # Langkah maksimum per sub-step gerakan (mencegah tunneling)

# Ambang Batas Warna (Generator)
# 1. Air (Laut, Sungai, Air Terjun)
WATER_B_MIN = 115                  # Blue minimal untuk air
WATER_B_DIFF = 20                  # Blue harus lebih besar dari Red + diff
WATER_G_MIN = 50                   # Green minimal untuk air
WATER_DEEP_B_MIN = 140             # Blue air dalam
WATER_DEEP_R_MAX = 100             # Red air dalam maksimal

# 2. Tebing / Tepi Tanah Vertikal (Coklat Tua / Kemerahan di bawah rumput / tepi air)
CLIFF_R_MIN = 95
CLIFF_R_MAX = 185
CLIFF_G_MIN = 45
CLIFF_G_MAX = 108
CLIFF_B_MIN = 35
CLIFF_B_MAX = 85

# 3. Jalan Tanah (Coklat Muda / Oranye-Krem datar)
PATH_R_MIN = 175
PATH_G_MIN = 110
PATH_B_MIN = 70

# 4. Pasir Pantai (Kuning / Beige Terang)
SAND_R_MIN = 195
SAND_G_MIN = 175
SAND_B_MIN = 95

# 5. Rumput / Padang Hijau
GRASS_G_MIN = 110

# Spawn Point Default (Alun-alun Desa Meadowbrook)
DEFAULT_SPAWN_X = 1440
DEFAULT_SPAWN_Y = 1056
