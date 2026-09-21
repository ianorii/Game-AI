"""
Map module - Map, viewport, dan pixel-based collision untuk 2D RPG map.

Modul ini menghandle:
1. Loading dan scaling background map image
2. Pixel-level obstacle detection menggunakan color analysis
3. Grid-based collision system untuk pathfinding
4. Viewport calculations untuk camera/scrolling
5. Grid save/load ke file

Pixel-level Color Detection:
- Menggunakan RGB color analysis untuk mendeteksi obstacle
- Water: biru (b > 130, b > r * 1.2)
- Roof: merah (r > 165, r >= g + 60)
- Stone/fence: abu-abu (sat < 25)
- Vegetasi gelap: hijau gelap (g > r * 1.8)

Grid Collision System:
- Cell size: 8x8 pixels
- Grid size: 96x64 cells
- Value 0 = walkable, 1 = obstacle
- Menggunakan connected components untuk memastikan connectivity
"""
import math
import os
from collections import deque

import pygame

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Path direktori (project root = parent of game/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMAGE_DIR = os.path.join(BASE_DIR, "assets", "images")
FULL_MAP_PATH = os.path.join(IMAGE_DIR, "full map.png")
GRID_OVERRIDE_PATH = os.path.join(BASE_DIR, "grid_override.txt")

# Ukuran map dan cell
MAP_WIDTH = 1536  # pixel
MAP_HEIGHT = 1024  # pixel
CELL_SIZE = 16  # pixel per cell
COLS = MAP_WIDTH // CELL_SIZE  # 96 columns
ROWS = (MAP_HEIGHT + CELL_SIZE - 1) // CELL_SIZE  # 64 rows

# Area spesial yang membutuhkan collision handling khusus
BRIDGE_RECT = pygame.Rect(1290, 770, 270, 185)  # Jembatan utama
RIVER_BRIDGE_RECT = pygame.Rect(864, 448, 160, 64)  # Jembatan sungai
BRIDGE_RECTS = (BRIDGE_RECT, RIVER_BRIDGE_RECT)
GARDEN_RECT = pygame.Rect(80, 1360, 330, 280)  # Area taman


# ---------------------------------------------------------------------------
# Pixel-level Color Detection Functions
# ---------------------------------------------------------------------------

def _is_obstacle(r, g, b):
    """Deteksi apakah pixel merupakan obstacle berdasarkan warna RGB.

    Menggunakan beberapa heuristic warna untuk mendeteksi:
    - Air (biru)
    - Atap (merah)
    - Stone/fence (abu-abu)
    - Vegetasi gelap

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True jika pixel merupakan obstacle
    """
    mx, mn = max(r, g, b), min(r, g, b)
    sat = mx - mn  # Saturasi
    bri = (r + g + b) / 3.0  # Brightness

    # Deteksi berbagai jenis obstacle
    water = b > 130 and b > r * 1.2 and b > g * 0.98 and r < 120
    cyan = b > 105 and b >= g and g >= r * 1.0 and r < 110 and bri < 175
    roof = r > 165 and r >= g + 60 and sat > 80 and b < 150
    stone = sat < 25 and 95 < bri < 235
    fence = sat < 20 and bri > 155
    dark = bri < 30
    slate = sat < 22 and 50 < bri < 115 and b >= g and b > r
    canopy = g > r * 1.8 and g >= b and g < 150 and r < 45

    return water or cyan or roof or stone or fence or dark or slate or canopy


def _is_road(r, g, b):
    """Deteksi apakah pixel merupakan jalan.

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True jika pixel merupakan jalan
    """
    bright = r > 215 and g > 160 and g < 200 and b > 90 and b < 135 and (r - b) > 90
    shaded = (
        (190 <= r < 215)
        and 168 < g < 205
        and 75 < b < 115
        and g > r * 0.93
        and (g - b) > 60
    )
    return bright or shaded


def _is_dirtish(r, g, b):
    """Deteksi apakah pixel merupakan tanah/dirt.

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True jika pixel merupakan tanah
    """
    if r <= g or g <= b:
        return False
    if (r - b) < 25:
        return False
    if g <= r * 0.5:
        return False
    bri = (r + g + b) / 3.0
    return 45 < bri < 195 and (r - g) < 145


def _is_water(r, g, b):
    """Deteksi pixel air dalam.

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True jika pixel merupakan air dalam
    """
    return b > 130 and b > r * 1.2 and b > g * 0.98 and r < 120


def _is_water_shallow(r, g, b):
    """Deteksi pixel air dangkal.

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        True jika pixel merupakan air dangkal
    """
    return b > 105 and b >= g and g >= r * 1.0 and r < 110 and (r + g + b) / 3 < 175


# ---------------------------------------------------------------------------
# GameMap Class
# ---------------------------------------------------------------------------

class GameMap:
    """Kelas utama untuk map, assets, dan collision grid.

    Attributes:
        background: pygame.Surface background map
        assets: Dict berisi semua assets yang diload
        pixel_obstacles: 2D boolean mask untuk pixel obstacles
        grid: 2D list collision grid (0 = walkable, 1 = obstacle)
    """

    def __init__(self):
        """Inisialisasi GameMap: load image, assets, dan build collision grid."""
        # Load background map
        self.background = pygame.image.load(FULL_MAP_PATH).convert()
        if self.background.get_size() != (MAP_WIDTH, MAP_HEIGHT):
            self.background = pygame.transform.scale(
                self.background, (MAP_WIDTH, MAP_HEIGHT)
            )

        # Load semua assets
        self.assets = self._load_all_assets()

        # Build pixel obstacle mask
        self.pixel_obstacles = self._build_pixel_mask()

        # Build collision grid
        self.grid = self._build_collision_grid()

        # Load grid override jika ada
        self.load_grid_override()

    # -----------------------------------------------------------------------
    # Asset Loading
    # -----------------------------------------------------------------------

    def _load_all_assets(self):
        """Walk direktori assets dan load semua image ke dict.

        Key: relative path tanpa extension (contoh: "08_karakter/karakter_pemain")
        Value: pygame.Surface

        Returns:
            Dict berisi semua assets
        """
        assets = {}
        for root, _, files in os.walk(IMAGE_DIR):
            for filename in files:
                if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                    # Skip background map
                    if filename == "full map.png":
                        continue
                    path = os.path.join(root, filename)
                    # Buat key dari relative path
                    key = os.path.splitext(
                        os.path.relpath(path, IMAGE_DIR)
                    )[0].replace("\\", "/")
                    assets[key] = pygame.image.load(path).convert_alpha()
        return assets

    def get_asset(self, name):
        """Return asset berdasarkan nama.

        Args:
            name: Nama asset (contoh: "08_karakter/karakter_pemain")

        Returns:
            pygame.Surface atau None jika tidak ditemukan
        """
        return self.assets.get(name)

    # -----------------------------------------------------------------------
    # Pixel Obstacle Mask
    # -----------------------------------------------------------------------

    def _build_pixel_mask(self):
        """Build 2D boolean mask: True jika pixel merupakan obstacle.

        Proses:
        1. Iterasi semua pixel di background map
        2. Cek warna menggunakan _is_obstacle()
        3. Simpan hasil di 2D list

        Returns:
            2D list of boolean (True = obstacle)
        """
        mask = [[False] * MAP_WIDTH for _ in range(MAP_HEIGHT)]
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                r, g, b = self.background.get_at((x, y))[:3]
                mask[y][x] = _is_obstacle(r, g, b)
        return mask

    # -----------------------------------------------------------------------
    # Cell Statistics Helpers
    # -----------------------------------------------------------------------

    def _cell_fraction_obstacle(self, row, col):
        """Hitung fraksi pixel yang merupakan obstacle di cell.

        Args:
            row: Baris cell
            col: Kolom cell

        Returns:
            Float 0.0 - 1.0 (fraksi obstacle)
        """
        x0, y0 = col * CELL_SIZE, row * CELL_SIZE
        x1 = min(x0 + CELL_SIZE, MAP_WIDTH)
        y1 = min(y0 + CELL_SIZE, MAP_HEIGHT)

        if x0 >= MAP_WIDTH or y0 >= MAP_HEIGHT:
            return 1.0

        obs = 0
        total = 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                total += 1
                if self.pixel_obstacles[y][x]:
                    obs += 1

        return obs / total if total else 0.0

    def _cell_stats(self, row, col):
        """Hitung statistik cell: obstacle fraction, luminance stddev, road fraction, avg RGB.

        Args:
            row: Baris cell
            col: Kolom cell

        Returns:
            Tuple (obstacle_frac, lum_stddev, road_frac, avg_r, avg_g, avg_b)
        """
        x0, y0 = col * CELL_SIZE, row * CELL_SIZE
        x1 = min(x0 + CELL_SIZE, MAP_WIDTH)
        y1 = min(y0 + CELL_SIZE, MAP_HEIGHT)

        if x0 >= MAP_WIDTH or y0 >= MAP_HEIGHT:
            return 1.0, 99.0, 0.0, 0, 0, 0

        obs = 0
        road = 0
        total = 0
        sr = sg = sb = 0
        lums = [0.0] * (CELL_SIZE * CELL_SIZE)
        i = 0

        for y in range(y0, y1):
            for x in range(x0, x1):
                r, g, b = self.background.get_at((x, y))[:3]
                total += 1
                if self.pixel_obstacles[y][x]:
                    obs += 1
                if _is_road(r, g, b):
                    road += 1
                sr += r
                sg += g
                sb += b
                lums[i] = (r + g + b) / 3.0
                i += 1

        lmean = sum(lums) / total
        lvar = sum((v - lmean) ** 2 for v in lums) / total

        return (
            obs / total if total else 0.0,
            math.sqrt(lvar),
            road / total if total else 0.0,
            sr // total,
            sg // total,
            sb // total,
        )

    def _cell_deck_fraction(self, row, col):
        """Hitung fraksi pixel yang merupakan dirt/deck di cell.

        Args:
            row: Baris cell
            col: Kolom cell

        Returns:
            Float 0.0 - 1.0 (fraksi dirt)
        """
        x0, y0 = col * CELL_SIZE, row * CELL_SIZE
        x1 = min(x0 + CELL_SIZE, MAP_WIDTH)
        y1 = min(y0 + CELL_SIZE, MAP_HEIGHT)

        if x0 >= MAP_WIDTH or y0 >= MAP_HEIGHT:
            return 0.0

        d = 0
        total = 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                total += 1
                r, g, b = self.background.get_at((x, y))[:3]
                if _is_dirtish(r, g, b):
                    d += 1

        return d / total if total else 0.0

    def _cell_water_fraction(self, row, col):
        """Hitung fraksi pixel yang merupakan air di cell.

        Args:
            row: Baris cell
            col: Kolom cell

        Returns:
            Float 0.0 - 1.0 (fraksi air)
        """
        x0, y0 = col * CELL_SIZE, row * CELL_SIZE
        x1 = min(x0 + CELL_SIZE, MAP_WIDTH)
        y1 = min(y0 + CELL_SIZE, MAP_HEIGHT)

        if x0 >= MAP_WIDTH or y0 >= MAP_HEIGHT:
            return 1.0

        w = 0
        total = 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                if not (0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT):
                    continue
                total += 1
                r, g, b = self.background.get_at((x, y))[:3]
                if _is_water(r, g, b) or _is_water_shallow(r, g, b):
                    w += 1

        return w / total if total else 0.0

    def _is_water_pixel(self, x, y):
        """Cek apakah pixel merupakan air.

        Args:
            x: Koordinat x pixel
            y: Koordinat y pixel

        Returns:
            True jika pixel merupakan air
        """
        if not (0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT):
            return True
        r, g, b = self.background.get_at((x, y))[:3]
        return _is_water(r, g, b) or _is_water_shallow(r, g, b)

    # -----------------------------------------------------------------------
    # Collision Grid Building
    # -----------------------------------------------------------------------

    def _cell_hits_obstacle(self, row, col):
        """Tentukan apakah cell harus diblokir berdasarkan pixel stats.

        Kriteria cell diblokir:
        - Fraksi obstacle > 6%
        - Luminance stddev > 16 (tidak uniform) dan bukan bright green
        - Fraksi obstacle > 3% dan stddev > 8

        Args:
            row: Baris cell
            col: Kolom cell

        Returns:
            True jika cell harus diblokir
        """
        obj, lsd, road_frac, mr, mg, mb = self._cell_stats(row, col)

        if obj > 0.06:
            return True

        bright_green = mg - mr > 25 and mg - mb > 55 and (mr + mg + mb) / 3.0 > 70
        if lsd > 16 and not bright_green and road_frac < 0.30:
            return True
        if obj > 0.03 and lsd > 8 and not bright_green:
            return True

        return False

    def _build_collision_grid(self):
        """Build full collision grid dari pixel analysis.

        Langkah:
        1. Tandai cell sebagai obstacle berdasarkan pixel stats
        2. Bersihkan cell di jembatan
        3. Bersihkan cell di area taman (kecuali air)
        4. Bersihkan road cells yang membentuk connected components
        5. Bersihkan dirt cells yang membentuk sparse components
        6. Pastikan connectivity dengan hanya menyimpan largest component

        Returns:
            2D list of int (0 = walkable, 1 = obstacle)
        """
        grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]

        # Langkah 1: Tandai cell obstacle
        for r in range(ROWS):
            for c in range(COLS):
                if self._cell_hits_obstacle(r, c):
                    grid[r][c] = 1

        # Langkah 2: Bersihkan cell jembatan
        for r in range(ROWS):
            for c in range(COLS):
                cx = c * CELL_SIZE + CELL_SIZE // 2
                cy = r * CELL_SIZE + CELL_SIZE // 2
                if any(rect.collidepoint(cx, cy) for rect in BRIDGE_RECTS):
                    obj, lsd, road_frac, mr, mg, mb = self._cell_stats(r, c)
                    if (
                        self._cell_deck_fraction(r, c) > 0.30
                        and obj < 0.10
                        and not (mr > 165 and mr >= mg + 60 and mb < 150)
                    ):
                        grid[r][c] = 0

        # Langkah 3: Bersihkan cell taman
        for r in range(ROWS):
            for c in range(COLS):
                cx = c * CELL_SIZE + CELL_SIZE // 2
                cy = r * CELL_SIZE + CELL_SIZE // 2
                if GARDEN_RECT.collidepoint(cx, cy):
                    if not self._is_water_pixel(cx, cy):
                        grid[r][c] = 0

        # Langkah 4: Bersihkan road cells (connected components >= 4)
        road_cells = self._find_cells_by_type(_is_road, threshold=0.30)
        self._clear_connected_components(grid, road_cells, min_size=4)

        # Langkah 5: Bersihkan dirt cells (sparse components)
        dirt_cells = self._find_cells_by_type(_is_dirtish, threshold=0.30)
        self._clear_sparse_components(grid, dirt_cells)

        # Langkah 6: Pastikan single connected component
        self._ensure_connectivity(grid)

        return grid

    def _find_cells_by_type(self, color_func, threshold=0.30):
        """Cari cells yang lebih dari threshold fraksinya sesuai color_func.

        Args:
            color_func: Fungsi deteksi warna (r, g, b) -> bool
            threshold: Threshold fraksi (default 0.30)

        Returns:
            Set of (row, col) cells yang memenuhi kriteria
        """
        cells = set()
        for r in range(ROWS):
            for c in range(COLS):
                count = 0
                total = 0
                for py in range(r * CELL_SIZE, min((r + 1) * CELL_SIZE, MAP_HEIGHT)):
                    for px in range(c * CELL_SIZE, min((c + 1) * CELL_SIZE, MAP_WIDTH)):
                        cr, cg, cb = self.background.get_at((px, py))[:3]
                        total += 1
                        if color_func(cr, cg, cb):
                            count += 1
                if total > 0 and count / total > threshold:
                    cells.add((r, c))
        return cells

    def _clear_connected_components(self, grid, cells, min_size=4):
        """Bersihkan cells (grid=0) yang merupakan connected components >= min_size.

        Menggunakan BFS untuk mencari connected components.

        Args:
            grid: 2D collision grid (di-modify in-place)
            cells: Set of (row, col) cells yang akan dicek
            min_size: Ukuran minimum component untuk dibersihkan
        """
        seen = set()
        for r, c in cells:
            if (r, c) in seen:
                continue
            component = []
            queue = deque([(r, c)])
            seen.add((r, c))
            while queue:
                cr, cc = queue.popleft()
                component.append((cr, cc))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = cr + dr, cc + dc
                    if (nr, nc) in cells and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        queue.append((nr, nc))
            if len(component) >= min_size:
                for cr, cc in component:
                    grid[cr][cc] = 0

    def _clear_sparse_components(self, grid, cells):
        """Bersihkan dirt components yang sparse (low fill ratio di bounding box).

        Args:
            grid: 2D collision grid (di-modify in-place)
            cells: Set of (row, col) dirt cells
        """
        seen = set()
        for r, c in cells:
            if (r, c) in seen:
                continue
            component = []
            queue = deque([(r, c)])
            seen.add((r, c))
            while queue:
                cr, cc = queue.popleft()
                component.append((cr, cc))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = cr + dr, cc + dc
                    if (nr, nc) in cells and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        queue.append((nr, nc))

            if len(component) < 3:
                continue

            # Hitung bounding box fill ratio
            min_r = min(p[0] for p in component)
            max_r = max(p[0] for p in component)
            min_c = min(p[1] for p in component)
            max_c = max(p[1] for p in component)
            bbox = (max_r - min_r + 1) * (max_c - min_c + 1)

            if bbox > 0 and len(component) / bbox < 0.70:
                for cr, cc in component:
                    obj, lsd, road_frac, mr, mg, mb = self._cell_stats(cr, cc)
                    bright_green = (
                        mg - mr > 25 and mg - mb > 55 and (mr + mg + mb) / 3.0 > 70
                    )
                    solid_obstacle = obj > 0.10 or (
                        lsd > 16 and not bright_green and road_frac < 0.30
                    )
                    if not solid_obstacle:
                        grid[cr][cc] = 0

    def _ensure_connectivity(self, grid):
        """Pastikan hanya ada satu connected component dengan memblokir lainnya.

        Args:
            grid: 2D collision grid (di-modify in-place)
        """
        best = []
        seen = set()
        for r in range(ROWS):
            for c in range(COLS):
                if grid[r][c] != 0 or (r, c) in seen:
                    continue
                comp = []
                queue = deque([(r, c)])
                seen.add((r, c))
                while queue:
                    cr, cc = queue.popleft()
                    comp.append((cr, cc))
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nr, nc = cr + dr, cc + dc
                        if (
                            0 <= nr < ROWS
                            and 0 <= nc < COLS
                            and (nr, nc) not in seen
                            and grid[nr][nc] == 0
                        ):
                            seen.add((nr, nc))
                            queue.append((nr, nc))
                if len(comp) > len(best):
                    best = comp

        keep = set(best)
        for r in range(ROWS):
            for c in range(COLS):
                if grid[r][c] == 0 and (r, c) not in keep:
                    grid[r][c] = 1

    # -----------------------------------------------------------------------
    # Public Grid Helpers
    # -----------------------------------------------------------------------

    def is_walkable(self, row, col):
        """Cek apakah cell bisa dilewati (walkable dan dalam bounds).

        Args:
            row: Baris cell
            col: Kolom cell

        Returns:
            True jika cell walkable
        """
        return 0 <= row < ROWS and 0 <= col < COLS and self.grid[row][col] == 0

    def is_valid(self, row, col):
        """Cek apakah koordinat cell valid (dalam bounds).

        Args:
            row: Baris cell
            col: Kolom cell

        Returns:
            True jika valid
        """
        return 0 <= row < ROWS and 0 <= col < COLS

    def get_grid(self):
        """Return collision grid.

        Returns:
            2D list of int (0 = walkable, 1 = obstacle)
        """
        return self.grid

    def toggle_cell(self, row, col):
        """Toggle cell antara walkable (0) dan blocked (1).

        Args:
            row: Baris cell
            col: Kolom cell

        Returns:
            True jika berhasil
        """
        if not self.is_valid(row, col):
            return False
        self.grid[row][col] = 0 if self.grid[row][col] else 1
        return True

    def set_cell(self, row, col, value):
        """Set cell ke blocked (1) atau walkable (0).

        Args:
            row: Baris cell
            col: Kolom cell
            value: 1 untuk blocked, 0 untuk walkable

        Returns:
            True jika berhasil
        """
        if not self.is_valid(row, col):
            return False
        self.grid[row][col] = 1 if value else 0
        return True

    def get_cell(self, row, col):
        """Return nilai cell (0 atau 1), atau None jika invalid.

        Args:
            row: Baris cell
            col: Kolom cell

        Returns:
            0, 1, atau None
        """
        return self.grid[row][col] if self.is_valid(row, col) else None

    # -----------------------------------------------------------------------
    # Grid Save/Load
    # -----------------------------------------------------------------------

    def save_grid_override(self, path=GRID_OVERRIDE_PATH):
        """Simpan collision grid ke text file.

        Format: 96 karakter per baris (0 atau 1), 64 baris.

        Args:
            path: Path file output

        Returns:
            True jika berhasil
        """
        with open(path, "w", encoding="ascii") as f:
            for r in range(ROWS):
                line = "".join("1" if self.grid[r][c] else "0" for c in range(COLS))
                f.write(line + "\n")
        return True

    def load_grid_override(self, path=GRID_OVERRIDE_PATH):
        """Muat collision grid dari text file.

        Args:
            path: Path file input

        Returns:
            True jika berhasil, False jika gagal
        """
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="ascii") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            if not lines:
                return False
            if len(lines) > ROWS or any(len(ln) != COLS for ln in lines):
                return False
            for r, ln in enumerate(lines):
                for c, ch in enumerate(ln):
                    self.grid[r][c] = 1 if ch == "1" else 0
            return True
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Drawing and Coordinate Conversion
    # -----------------------------------------------------------------------

    def draw(self, screen, viewport):
        """Gambar background map yang sudah di-scale ke layar.

        Args:
            screen: Surface utama
            viewport: Objek Viewport
        """
        scaled = pygame.transform.scale(self.background, viewport.map_rect.size)
        screen.blit(scaled, viewport.map_rect.topleft)

    def screen_to_grid(self, pos, viewport):
        """Konversi posisi screen pixel ke grid (row, col).

        Args:
            pos: Tuple (x, y) koordinat screen
            viewport: Objek Viewport

        Returns:
            Tuple (row, col) atau None jika di luar bounds
        """
        if not viewport.map_rect.collidepoint(pos):
            return None
        world_x = (pos[0] - viewport.map_rect.x) / viewport.scale
        world_y = (pos[1] - viewport.map_rect.y) / viewport.scale
        col = int(world_x // CELL_SIZE)
        row = int(world_y // CELL_SIZE)
        return (row, col) if self.is_valid(row, col) else None


# ---------------------------------------------------------------------------
# Viewport Class
# ---------------------------------------------------------------------------

class Viewport:
    """Handles screen-to-world mapping dan scaling untuk map.

    Attributes:
        screen_size: Ukuran layar (width, height)
        scale: Factor scaling dari world ke screen
        map_rect: Rect posisi map di layar (centered)
    """

    def __init__(self, screen_size):
        """Inisialisasi viewport: hitung scale dan posisi map.

        Map di-center di layar dengan aspect ratio yang dipertahankan.

        Args:
            screen_size: Tuple (width, height) ukuran layar
        """
        self.screen_size = screen_size
        sw, sh = screen_size
        # Hitung scale untuk fit map di layar
        self.scale = min(sw / MAP_WIDTH, sh / MAP_HEIGHT)
        width = int(MAP_WIDTH * self.scale)
        height = int(MAP_HEIGHT * self.scale)
        # Center map di layar
        self.map_rect = pygame.Rect(
            (sw - width) // 2, (sh - height) // 2, width, height
        )
