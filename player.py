"""Player movement with deliberately slower keyboard and A* movement."""
import pygame
from pathfinding import astar
from npc import draw_sprite, game_pos, draw_circle_debug

class Player:
    def __init__(self, row, col, sprite=None):
        self.start_pos = (row, col)
        self.row, self.col = row, col
        self.sprite = sprite
        self.manual_timer = 0.0
        self.auto_timer = 0.0
        self.manual_interval = 0.04   # ~25 moves/sec
        self.auto_interval = 0.08     # ~12 cells/sec
        self.facing = 1
        self.heuristic = "manhattan"
        self.target = None
        self.path = []
        self.path_index = 0
        self.debug_visited = []
        self.debug_path = []
        self.total_expanded = 0

    def snap_to_walkable(self, game_map):
        if game_map.is_walkable(self.row, self.col):
            self.start_pos = (self.row, self.col)
            return
        from collections import deque
        start = (self.row, self.col)
        seen = {start}
        queue = deque([start])
        while queue:
            r, c = queue.popleft()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = r + dr, c + dc
                if not game_map.is_valid(nr, nc) or (nr, nc) in seen:
                    continue
                seen.add((nr, nc))
                if game_map.is_walkable(nr, nc):
                    self.row, self.col = self.start_pos = (nr, nc)
                    return
                queue.append((nr, nc))

    def set_target(self, row, col, game_map):
        if not game_map.is_walkable(row, col):
            self.target = None; self.path = []; self.path_index = 0
            return False
        result = astar(game_map.get_grid(), (self.row, self.col), (row, col),
                       heuristic_name=self.heuristic, allow_diagonal=False)
        self.debug_visited = result["visited"]
        self.debug_path = result["path"]
        self.total_expanded = result["total_expanded"]
        if not result["found"]:
            self.target = None; self.path = []; self.path_index = 0
            return False
        self.target = (row, col)
        self.path = result["path"]
        self.path_index = 0
        self.auto_timer = self.auto_interval
        return True

    def handle_input(self, keys, game_map, dt):
        self.manual_timer = max(0.0, self.manual_timer - dt)
        if self.manual_timer > 0:
            return
        dr = dc = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]: dr = -1
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]: dr = 1
        elif keys[pygame.K_a] or keys[pygame.K_LEFT]: dc = -1
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]: dc = 1
        if dr or dc:
            self.target = None; self.path = []; self.path_index = 0
            nr, nc = self.row + dr, self.col + dc
            if game_map.is_walkable(nr, nc):
                if dc: self.facing = 1 if dc > 0 else -1
                self.row, self.col = nr, nc
            self.manual_timer = self.manual_interval

    def update(self, game_map, dt):
        if self.target is None or not self.path:
            return
        self.auto_timer -= dt
        if self.auto_timer > 0:
            return
        self.auto_timer = self.auto_interval
        if self.path_index >= len(self.path):
            self.target = None; return
        nr, nc = self.path[self.path_index]
        if not game_map.is_walkable(nr, nc):
            old_target = self.target
            self.target = None
            self.path = []
            self.path_index = 0
            self.set_target(*old_target, game_map)
            return
        if nc != self.col: self.facing = 1 if nc > self.col else -1
        self.row, self.col = nr, nc
        self.path_index += 1
        if (self.row, self.col) == self.target:
            self.target = None; self.path = []; self.path_index = 0

    def reset(self):
        self.row, self.col = self.start_pos
        self.target = None; self.path = []; self.path_index = 0
        self.debug_visited = []; self.debug_path = []; self.total_expanded = 0

    def get_pos(self): return self.row, self.col

    def draw(self, screen, viewport):
        draw_sprite(screen, self.sprite, self.row, self.col, viewport, self.facing)

    def draw_debug(self, screen, cell_size):
        draw_circle_debug(screen, self.row, self.col, cell_size, (0, 200, 0))

    def draw_target(self, screen, viewport):
        if self.target is None: return
        x, y = game_pos(*self.target, viewport)
        pygame.draw.circle(screen, (255,235,70), (x,y), max(5,int(8*viewport.scale)), max(2,int(2*viewport.scale)))

    def draw_target_debug(self, screen, cell_size):
        if self.target is None: return
        r, c = self.target
        cx = c * cell_size + cell_size // 2
        cy = r * cell_size + cell_size // 2
        pygame.draw.circle(screen, (255, 235, 70), (cx, cy), cell_size // 3, 3)
