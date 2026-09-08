"""
Map, viewport and pixel-based collision for the 2D RPG map.

This module handles:
- Loading and scaling the background map image
- Pixel-level obstacle detection using color analysis
- Grid-based collision system for pathfinding
- Viewport calculations for camera/scrolling
"""
import math
import os
from collections import deque

import pygame

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "assets", "images")
FULL_MAP_PATH = os.path.join(IMAGE_DIR, "full map.png")
GRID_OVERRIDE_PATH = os.path.join(BASE_DIR, "grid_override.txt")

MAP_WIDTH = 1536
MAP_HEIGHT = 1024
CELL_SIZE = 8
COLS = MAP_WIDTH // CELL_SIZE
ROWS = (MAP_HEIGHT + CELL_SIZE - 1) // CELL_SIZE

# Special regions that need special collision handling
BRIDGE_RECT = pygame.Rect(1290, 770, 270, 185)
RIVER_BRIDGE_RECT = pygame.Rect(864, 448, 160, 64)
BRIDGE_RECTS = (BRIDGE_RECT, RIVER_BRIDGE_RECT)
GARDEN_RECT = pygame.Rect(80, 1360, 330, 280)


# ---------------------------------------------------------------------------
# Pixel-level color detection functions
# ---------------------------------------------------------------------------

def _is_obstacle(r, g, b):
    """Detect if a pixel color represents an obstacle (water, roof, stone, etc.)."""
    mx, mn = max(r, g, b), min(r, g, b)
    sat = mx - mn
    bri = (r + g + b) / 3.0

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
    """Detect if a pixel color represents a road surface."""
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
    """Detect if a pixel color represents dirt/ground."""
    if r <= g or g <= b:
        return False
    if (r - b) < 25:
        return False
    if g <= r * 0.5:
        return False
    bri = (r + g + b) / 3.0
    return 45 < bri < 195 and (r - g) < 145


def _is_water(r, g, b):
    """Detect deep water pixels."""
    return b > 130 and b > r * 1.2 and b > g * 0.98 and r < 120


def _is_water_shallow(r, g, b):
    """Detect shallow water pixels."""
    return b > 105 and b >= g and g >= r * 1.0 and r < 110 and (r + g + b) / 3 < 175


# ---------------------------------------------------------------------------
# GameMap class
# ---------------------------------------------------------------------------

class GameMap:
    """Main map class handling background, assets, and collision grid."""

    def __init__(self):
        """Load the map image, assets, and build the collision grid."""
        self.background = pygame.image.load(FULL_MAP_PATH).convert()
        if self.background.get_size() != (MAP_WIDTH, MAP_HEIGHT):
            self.background = pygame.transform.scale(
                self.background, (MAP_WIDTH, MAP_HEIGHT)
            )
        self.assets = self._load_all_assets()
        self.pixel_obstacles = self._build_pixel_mask()
        self.grid = self._build_collision_grid()
        self.load_grid_override()

    # -----------------------------------------------------------------------
    # Asset loading
    # -----------------------------------------------------------------------

    def _load_all_assets(self):
        """Walk the assets directory and load all images into a dict."""
        assets = {}
        for root, _, files in os.walk(IMAGE_DIR):
            for filename in files:
                if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                    if filename == "full map.png":
                        continue
                    path = os.path.join(root, filename)
                    key = os.path.splitext(
                        os.path.relpath(path, IMAGE_DIR)
                    )[0].replace("\\", "/")
                    assets[key] = pygame.image.load(path).convert_alpha()
        return assets

    def get_asset(self, name):
        """Return a loaded asset by its relative path name."""
        return self.assets.get(name)

    # -----------------------------------------------------------------------
    # Pixel obstacle mask
    # -----------------------------------------------------------------------

    def _build_pixel_mask(self):
        """Build a 2D boolean mask: True if pixel is an obstacle."""
        mask = [[False] * MAP_WIDTH for _ in range(MAP_HEIGHT)]
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                r, g, b = self.background.get_at((x, y))[:3]
                mask[y][x] = _is_obstacle(r, g, b)
        return mask

    # -----------------------------------------------------------------------
    # Cell statistics helpers
    # -----------------------------------------------------------------------

    def _cell_fraction_obstacle(self, row, col):
        """Return the fraction of pixels in a cell that are obstacles."""
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
        """Return (obstacle_frac, lum_stddev, road_frac, avg_r, avg_g, avg_b) for a cell."""
        x0, y0 = col * CELL_SIZE, row * CELL_SIZE
        x1 = min(x0 + CELL_SIZE, MAP_WIDTH)
        y1 = min(y0 + CELL_SIZE, MAP_HEIGHT)

        if x0 >= MAP_WIDTH or y0 >= MAP_HEIGHT:
            return 1.0, 99.0, 0.0, 0, 0, 0

        obs = 0
        road = 0
        total = 0
        sr = sg = sb = 0
        lums = [0.0] * 64
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
        """Return the fraction of dirt-like pixels in a cell."""
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
        """Return the fraction of water pixels in a cell."""
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
        """Check if a single pixel is water."""
        if not (0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT):
            return True
        r, g, b = self.background.get_at((x, y))[:3]
        return _is_water(r, g, b) or _is_water_shallow(r, g, b)

    # -----------------------------------------------------------------------
    # Collision grid building
    # -----------------------------------------------------------------------

    def _cell_hits_obstacle(self, row, col):
        """Determine if a cell should be marked as blocked based on pixel stats."""
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
        """Build the full collision grid from pixel analysis.

        Steps:
        1. Mark cells as obstacles based on pixel statistics
        2. Clear cells that are on bridges
        3. Clear cells in the garden area (except water)
        4. Clear road cells that form connected components
        5. Clear dirt cells that form sparse connected components
        6. Ensure connectivity by keeping only the largest walkable component
        """
        grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]

        # Step 1: Mark obstacle cells
        for r in range(ROWS):
            for c in range(COLS):
                if self._cell_hits_obstacle(r, c):
                    grid[r][c] = 1

        # Step 2: Clear bridge cells
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

        # Step 3: Clear garden cells
        for r in range(ROWS):
            for c in range(COLS):
                cx = c * CELL_SIZE + CELL_SIZE // 2
                cy = r * CELL_SIZE + CELL_SIZE // 2
                if GARDEN_RECT.collidepoint(cx, cy):
                    if not self._is_water_pixel(cx, cy):
                        grid[r][c] = 0

        # Step 4: Clear road cells that form connected components >= 4 cells
        road_cells = self._find_cells_by_type(_is_road, threshold=0.30)
        self._clear_connected_components(grid, road_cells, min_size=4)

        # Step 5: Clear dirt cells that form sparse connected components
        dirt_cells = self._find_cells_by_type(_is_dirtish, threshold=0.30)
        self._clear_sparse_components(grid, dirt_cells)

        # Step 6: Ensure single connected component
        self._ensure_connectivity(grid)

        return grid

    def _find_cells_by_type(self, color_func, threshold=0.30):
        """Find cells where more than threshold fraction of pixels match color_func."""
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
        """Set grid=0 for all cells in connected components with size >= min_size."""
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
        """Clear dirt components that are sparse (low fill ratio in bounding box)."""
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

            # Calculate bounding box fill ratio
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
        """Keep only the largest connected component, block all others."""
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
    # Public grid helpers
    # -----------------------------------------------------------------------

    def is_walkable(self, row, col):
        """Return True if the cell is within bounds and walkable."""
        return 0 <= row < ROWS and 0 <= col < COLS and self.grid[row][col] == 0

    def is_valid(self, row, col):
        """Return True if the cell coordinates are within bounds."""
        return 0 <= row < ROWS and 0 <= col < COLS

    def get_grid(self):
        """Return the collision grid (list of lists of 0/1)."""
        return self.grid

    def toggle_cell(self, row, col):
        """Toggle a cell between walkable (0) and blocked (1)."""
        if not self.is_valid(row, col):
            return False
        self.grid[row][col] = 0 if self.grid[row][col] else 1
        return True

    def set_cell(self, row, col, value):
        """Set a cell to blocked (1) or walkable (0)."""
        if not self.is_valid(row, col):
            return False
        self.grid[row][col] = 1 if value else 0
        return True

    def get_cell(self, row, col):
        """Return the grid value (0 or 1) for a cell, or None if invalid."""
        return self.grid[row][col] if self.is_valid(row, col) else None

    # -----------------------------------------------------------------------
    # Grid save/load
    # -----------------------------------------------------------------------

    def save_grid_override(self, path=GRID_OVERRIDE_PATH):
        """Save the current collision grid to a text file."""
        with open(path, "w", encoding="ascii") as f:
            for r in range(ROWS):
                line = "".join("1" if self.grid[r][c] else "0" for c in range(COLS))
                f.write(line + "\n")
        return True

    def load_grid_override(self, path=GRID_OVERRIDE_PATH):
        """Load collision grid from a text file. Returns True on success."""
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
    # Drawing and coordinate conversion
    # -----------------------------------------------------------------------

    def draw(self, screen, viewport):
        """Draw the scaled background map onto the screen."""
        scaled = pygame.transform.scale(self.background, viewport.map_rect.size)
        screen.blit(scaled, viewport.map_rect.topleft)

    def screen_to_grid(self, pos, viewport):
        """Convert a screen pixel position to grid (row, col), or None if out of bounds."""
        if not viewport.map_rect.collidepoint(pos):
            return None
        world_x = (pos[0] - viewport.map_rect.x) / viewport.scale
        world_y = (pos[1] - viewport.map_rect.y) / viewport.scale
        col = int(world_x // CELL_SIZE)
        row = int(world_y // CELL_SIZE)
        return (row, col) if self.is_valid(row, col) else None


# ---------------------------------------------------------------------------
# Viewport class
# ---------------------------------------------------------------------------

class Viewport:
    """Handles screen-to-world mapping and scaling for the map."""

    def __init__(self, screen_size):
        """Calculate scale and position to fit the map on screen."""
        self.screen_size = screen_size
        sw, sh = screen_size
        self.scale = min(sw / MAP_WIDTH, sh / MAP_HEIGHT)
        width = int(MAP_WIDTH * self.scale)
        height = int(MAP_HEIGHT * self.scale)
        self.map_rect = pygame.Rect(
            (sw - width) // 2, (sh - height) // 2, width, height
        )
