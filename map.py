"""Map, viewport and pixel-based collision for the 2D RPG map."""
import os
import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "assets", "images")
FULL_MAP_PATH = os.path.join(IMAGE_DIR, "full map.png")

# The supplied map is 
MAP_WIDTH = 1536
MAP_HEIGHT = 1024
CELL_SIZE = 32
COLS = MAP_WIDTH // CELL_SIZE          # 72
ROWS = (MAP_HEIGHT + CELL_SIZE - 1) // CELL_SIZE  # 58

# Wooden bridge deck inside the big lake (lower-right).
BRIDGE_RECT = pygame.Rect(1290, 770, 270, 185)
# Wooden bridge carrying the painted road across the river (rows 14-15).
RIVER_BRIDGE_RECT = pygame.Rect(864, 448, 160, 64)
BRIDGE_RECTS = (BRIDGE_RECT, RIVER_BRIDGE_RECT)
# The crop/garden at the lower-left is intentionally walkable.
GARDEN_RECT = pygame.Rect(80, 1360, 330, 280)


def _rgb_masks(surface):
    """Build a conservative obstacle mask from the actual map pixels."""
    import numpy as np
    a = pygame.surfarray.array3d(surface).astype(np.int16)
    # pygame array is [x,y,channel]; convert to [y,x,channel]
    a = np.transpose(a, (1, 0, 2))
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]

    # River/lake: strong blue/cyan.
    water = (b > 145) & (b > r * 1.55) & (b > g * 1.18) & (r < 100)

    # Mountains/rocks: relatively low saturation and mid/high brightness.
    mx, mn = a.max(axis=2), a.min(axis=2)
    gray = (mx - mn < 55) & (r > 65) & (r < 190) & (g > 55) & (g < 190)

    # Red/orange roofs.
    roofs = (r > 105) & (r > g * 1.30) & (r > b * 1.18) & (g < 170)

    # Dark tree crowns and trunks. Grass is much brighter, so this threshold
    # avoids turning the entire grass field into an obstacle.
    trees = (g > r * 1.15) & (g > b * 1.05) & (g < 145) & (r < 82) & (b < 105)

    # Dark brown cliffs, fences, bridge sides, rocks and object outlines.
    brown = (r > 48) & (r > g * 1.12) & (g > b * 1.08) & (r < 190) & (g < 155) & (b < 115)

    # Light building walls are blocked too, but exclude the beige road.
    buildings = (r > 125) & (g > 105) & (g < 205) & (b < 150) & ((r - b) > 25) & ((g - b) > 15)

    obstacle = water | gray | roofs | trees | brown | buildings
    return obstacle


def _road_mask(surface):
    """Detect the beige/yellow paved road painted on the map.

    The road shares its colour with the light building walls, so it is
    otherwise picked up by the ``buildings`` mask and becomes un-walkable.
    """
    import numpy as np
    a = np.transpose(pygame.surfarray.array3d(surface), (1, 0, 2)).astype(np.int16)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    bright = (r > 215) & (g > 160) & (g < 200) & (b > 90) & (b < 135) & ((r - b) > 90)
    shaded = (r >= 190) & (r < 215) & (g > 168) & (g < 205) & (b > 75) & (b < 115) \
             & (g > r * 0.93) & ((g - b) > 60)
    return bright | shaded


class GameMap:
    def __init__(self):
        self.background = pygame.image.load(FULL_MAP_PATH).convert()
        if self.background.get_size() != (MAP_WIDTH, MAP_HEIGHT):
            self.background = pygame.transform.scale(self.background, (MAP_WIDTH, MAP_HEIGHT))
        self.assets = self._load_all_assets()
        self.pixel_obstacles = _rgb_masks(self.background)
        self.grid = self._build_collision_grid()

    def _load_all_assets(self):
        assets = {}
        for root, _, files in os.walk(IMAGE_DIR):
            for filename in files:
                if filename.lower().endswith((".png", ".jpg", ".jpeg")) and filename != "full map.png":
                    path = os.path.join(root, filename)
                    key = os.path.splitext(os.path.relpath(path, IMAGE_DIR))[0].replace("\\", "/")
                    assets[key] = pygame.image.load(path).convert_alpha()
        return assets

    def get_asset(self, name):
        return self.assets.get(name)

    def _cell_hits_obstacle(self, row, col):
        x0, y0 = col * CELL_SIZE, row * CELL_SIZE
        x1, y1 = min(x0 + CELL_SIZE, MAP_WIDTH), min(y0 + CELL_SIZE, MAP_HEIGHT)
        if x0 >= MAP_WIDTH or y0 >= MAP_HEIGHT:
            return True

        # Use several samples instead of only the cell center. This prevents
        # the character from standing partly inside a tree/house/mountain.
        xs = range(x0 + 5, x1, 7)
        ys = range(y0 + 5, y1, 7)
        for y in ys:
            for x in xs:
                if self.pixel_obstacles[y, x]:
                    return True
        return False

    def _build_collision_grid(self):
        grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
        for r in range(ROWS):
            for c in range(COLS):
                if self._cell_hits_obstacle(r, c):
                    grid[r][c] = 1

        # The bridge decks are explicitly walkable. Their river banks remain blocked.
        for r in range(ROWS):
            for c in range(COLS):
                cx = c * CELL_SIZE + CELL_SIZE // 2
                cy = r * CELL_SIZE + CELL_SIZE // 2
                if any(rect.collidepoint(cx, cy) for rect in BRIDGE_RECTS):
                    grid[r][c] = 0

        # Garden/crop area is walkable; individual crop sprites are decoration.
        for r in range(ROWS):
            for c in range(COLS):
                cx = c * CELL_SIZE + CELL_SIZE // 2
                cy = r * CELL_SIZE + CELL_SIZE // 2
                if GARDEN_RECT.collidepoint(cx, cy):
                    # Keep the surrounding cliff/water protected.
                    if not self._is_water_pixel(cx, cy):
                        grid[r][c] = 0

        # The painted road is walkable. Keep only the real road corridors and
        # drop stray roof/wall fragments caught by the same colour band.
        road = _road_mask(self.background)
        road_cells = []
        for r in range(ROWS):
            for c in range(COLS):
                cell = road[r * CELL_SIZE:(r + 1) * CELL_SIZE,
                            c * CELL_SIZE:(c + 1) * CELL_SIZE]
                if cell.mean() > 0.30:
                    road_cells.append((r, c))
        from collections import deque
        seen = set()
        for r, c in road_cells:
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
                    if (nr, nc) in road_cells and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        queue.append((nr, nc))
            if len(component) >= 4:
                for cr, cc in component:
                    grid[cr][cc] = 0
        return grid

    def _is_water_pixel(self, x, y):
        if not (0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT):
            return True
        return bool(self.pixel_obstacles[y, x]) and self._water_like(x, y)

    def _water_like(self, x, y):
        # Re-read pixel for a reliable bridge/garden override.
        r, g, b = self.background.get_at((x, y))[:3]
        return b > 145 and b > r * 1.55 and b > g * 1.18 and r < 100

    def is_walkable(self, row, col):
        return 0 <= row < ROWS and 0 <= col < COLS and self.grid[row][col] == 0

    def is_valid(self, row, col):
        return 0 <= row < ROWS and 0 <= col < COLS

    def get_grid(self):
        return self.grid

    def draw(self, screen, viewport):
        scaled = pygame.transform.scale(self.background, viewport.map_rect.size)
        screen.blit(scaled, viewport.map_rect.topleft)

    def screen_to_grid(self, pos, viewport):
        if not viewport.map_rect.collidepoint(pos):
            return None
        world_x = (pos[0] - viewport.map_rect.x) / viewport.scale
        world_y = (pos[1] - viewport.map_rect.y) / viewport.scale
        col = int(world_x // CELL_SIZE)
        row = int(world_y // CELL_SIZE)
        return (row, col) if self.is_valid(row, col) else None


class Viewport:
    def __init__(self, screen_size):
        self.screen_size = screen_size
        sw, sh = screen_size
        self.scale = min(sw / MAP_WIDTH, sh / MAP_HEIGHT)
        width = int(MAP_WIDTH * self.scale)
        height = int(MAP_HEIGHT * self.scale)
        self.map_rect = pygame.Rect((sw - width) // 2, (sh - height) // 2, width, height)
