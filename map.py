"""Map, viewport and pixel-based collision for the 2D RPG map (no numpy)."""
import os, json
import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "assets", "images")
FULL_MAP_PATH = os.path.join(IMAGE_DIR, "full map.png")
MATRIX_FILE = os.path.join(BASE_DIR, "map_matrix.json")

MAP_WIDTH = 1536
MAP_HEIGHT = 1024
CELL_SIZE = 32
COLS = MAP_WIDTH // CELL_SIZE          # 72
ROWS = (MAP_HEIGHT + CELL_SIZE - 1) // CELL_SIZE  # 58

BRIDGE_RECT = pygame.Rect(1290, 770, 270, 185)
RIVER_BRIDGE_RECT = pygame.Rect(864, 448, 160, 64)
BRIDGE_RECTS = (BRIDGE_RECT, RIVER_BRIDGE_RECT)
GARDEN_RECT = pygame.Rect(80, 1360, 330, 280)

COLOR_WALKABLE = (230, 230, 230)
COLOR_OBSTACLE = (30, 30, 30)
COLOR_GRID = (180, 180, 180)


def _is_obstacle(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    water = b > 145 and b > r * 1.55 and b > g * 1.18 and r < 100
    gray = (mx - mn < 55) and 65 < r < 190 and 55 < g < 190
    roofs = r > 105 and r > g * 1.30 and r > b * 1.18 and g < 170
    trees = g > r * 1.15 and g > b * 1.05 and g < 145 and r < 82 and b < 105
    brown = r > 48 and r > g * 1.12 and g > b * 1.08 and r < 190 and g < 155 and b < 115
    buildings = r > 125 and g > 105 and g < 205 and b < 150 and (r - b) > 25 and (g - b) > 15
    return water or gray or roofs or trees or brown or buildings


def _is_road(r, g, b):
    bright = r > 215 and g > 160 and g < 200 and b > 90 and b < 135 and (r - b) > 90
    shaded = (190 <= r < 215) and 168 < g < 205 and 75 < b < 115 \
             and g > r * 0.93 and (g - b) > 60
    return bright or shaded


def _is_water(r, g, b):
    return b > 145 and b > r * 1.55 and b > g * 1.18 and r < 100


class GameMap:
    def __init__(self):
        self.background = pygame.image.load(FULL_MAP_PATH).convert()
        if self.background.get_size() != (MAP_WIDTH, MAP_HEIGHT):
            self.background = pygame.transform.scale(self.background, (MAP_WIDTH, MAP_HEIGHT))
        self.assets = self._load_all_assets()
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
        xs = range(x0 + 5, x1, 7)
        ys = range(y0 + 5, y1, 7)
        for y in ys:
            for x in xs:
                r, g, b = self.background.get_at((x, y))[:3]
                if _is_obstacle(r, g, b):
                    return True
        return False

    def _build_collision_grid(self):
        grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
        for r in range(ROWS):
            for c in range(COLS):
                if self._cell_hits_obstacle(r, c):
                    grid[r][c] = 1

        for r in range(ROWS):
            for c in range(COLS):
                cx = c * CELL_SIZE + CELL_SIZE // 2
                cy = r * CELL_SIZE + CELL_SIZE // 2
                if any(rect.collidepoint(cx, cy) for rect in BRIDGE_RECTS):
                    grid[r][c] = 0

        for r in range(ROWS):
            for c in range(COLS):
                cx = c * CELL_SIZE + CELL_SIZE // 2
                cy = r * CELL_SIZE + CELL_SIZE // 2
                if GARDEN_RECT.collidepoint(cx, cy):
                    cr, cg, cb = self.background.get_at((cx, cy))[:3]
                    if not (_is_obstacle(cr, cg, cb) and _is_water(cr, cg, cb)):
                        grid[r][c] = 0

        road_cells = set()
        for r in range(ROWS):
            for c in range(COLS):
                count = 0
                total = 0
                for py in range(r * CELL_SIZE, min((r + 1) * CELL_SIZE, MAP_HEIGHT)):
                    for px in range(c * CELL_SIZE, min((c + 1) * CELL_SIZE, MAP_WIDTH)):
                        cr, cg, cb = self.background.get_at((px, py))[:3]
                        total += 1
                        if _is_road(cr, cg, cb):
                            count += 1
                if total > 0 and count / total > 0.30:
                    road_cells.add((r, c))

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

    def is_walkable(self, row, col):
        return 0 <= row < ROWS and 0 <= col < COLS and self.grid[row][col] == 0

    def is_valid(self, row, col):
        return 0 <= row < ROWS and 0 <= col < COLS

    def get_grid(self):
        return self.grid

    def toggle_cell(self, row, col):
        if self.is_valid(row, col):
            self.grid[row][col] = 1 - self.grid[row][col]

    def save_matrix(self):
        with open(MATRIX_FILE, "w") as f:
            json.dump(self.grid, f)

    def load_matrix(self):
        if not os.path.exists(MATRIX_FILE):
            return False
        with open(MATRIX_FILE, "r") as f:
            self.grid = json.load(f)
        return True

    def draw(self, screen, viewport):
        scaled = pygame.transform.scale(self.background, viewport.map_rect.size)
        screen.blit(scaled, viewport.map_rect.topleft)

    def draw_debug(self, screen, cell_size):
        for r in range(ROWS):
            for c in range(COLS):
                rect = pygame.Rect(c * cell_size, r * cell_size, cell_size, cell_size)
                color = COLOR_WALKABLE if self.grid[r][c] == 0 else COLOR_OBSTACLE
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, COLOR_GRID, rect, 1)

    def screen_to_grid(self, pos, viewport):
        if not viewport.map_rect.collidepoint(pos):
            return None
        world_x = (pos[0] - viewport.map_rect.x) / viewport.scale
        world_y = (pos[1] - viewport.map_rect.y) / viewport.scale
        col = int(world_x // CELL_SIZE)
        row = int(world_y // CELL_SIZE)
        return (row, col) if self.is_valid(row, col) else None

    def screen_to_grid_debug(self, pos, cell_size):
        c = pos[0] // cell_size
        r = pos[1] // cell_size
        return (r, c) if self.is_valid(r, c) else None


class Viewport:
    def __init__(self, screen_size):
        self.screen_size = screen_size
        sw, sh = screen_size
        self.scale = min(sw / MAP_WIDTH, sh / MAP_HEIGHT)
        width = int(MAP_WIDTH * self.scale)
        height = int(MAP_HEIGHT * self.scale)
        self.map_rect = pygame.Rect((sw - width) // 2, (sh - height) // 2, width, height)
