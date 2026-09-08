"""NPC rendering, interaction and pursuit of the player with A*/UCS."""
import pygame
from map import CELL_SIZE
from pathfinding import astar

def game_pos(row, col, viewport):
    return (viewport.map_rect.x + int((col + 0.5) * CELL_SIZE * viewport.scale),
            viewport.map_rect.y + int((row + 0.5) * CELL_SIZE * viewport.scale))

def draw_sprite(screen, sprite, row, col, viewport, facing=1):
    if sprite is None: return
    width = max(28, int(sprite.get_width() * viewport.scale))
    height = max(42, int(sprite.get_height() * viewport.scale))
    scaled = pygame.transform.scale(sprite, (width, height))
    if facing < 0: scaled = pygame.transform.flip(scaled, True, False)
    x, y = game_pos(row, col, viewport)
    screen.blit(scaled, (x - width // 2, y - height + max(2, int(4 * viewport.scale))))

class NPC:
    def __init__(self, row, col, sprite=None, name="Niko"):
        self.start_pos = (row, col); self.row, self.col = row, col
        self.sprite = sprite; self.name = name; self.facing = -1
        self.follow = True
        self.heuristic = "ucs"
        self.move_interval = 0.18      # ~5.5 cells/sec
        self.recompute_interval = 0.35 # re-plan path to the player
        self.path = []
        self.path_index = 0
        self.timer = 0.0
        self.recompute_timer = 0.0
        self.debug_visited = []
        self.debug_path = []
        self.total_expanded = 0

    def reset(self):
        self.row, self.col = self.start_pos; self.facing = -1
        self.path = []; self.path_index = 0
        self.timer = 0.0; self.recompute_timer = 0.0
        self.debug_visited = []; self.debug_path = []; self.total_expanded = 0

    def set_heuristic(self, heuristic):
        self.heuristic = heuristic

    def get_pos(self): return self.row, self.col
    def is_near(self, player): return abs(self.row - player.row) + abs(self.col - player.col) <= 1

    def update(self, game_map, player, dt):
        if not self.follow:
            return
        # Re-plan whenever the target/path may be stale.
        self.recompute_timer -= dt
        if self.recompute_timer <= 0:
            self.recompute_timer = self.recompute_interval
            result = astar(game_map.get_grid(), (self.row, self.col),
                           (player.row, player.col), heuristic_name=self.heuristic,
                           allow_diagonal=False)
            self.debug_visited = result["visited"]
            self.debug_path = result["path"]
            self.total_expanded = result["total_expanded"]
            if result["found"]:
                # Stop one cell short so the NPC never overlaps the player.
                self.path = result["path"][:-1]
            else:
                self.path = []
            self.path_index = 0
        self.timer -= dt
        if self.timer > 0 or not self.path or self.path_index >= len(self.path):
            return
        self.timer = self.move_interval
        nr, nc = self.path[self.path_index]
        if game_map.is_walkable(nr, nc):
            if nc != self.col: self.facing = 1 if nc > self.col else -1
            self.row, self.col = nr, nc
        self.path_index += 1

    def draw(self, screen, viewport):
        draw_sprite(screen, self.sprite, self.row, self.col, viewport, self.facing)
    def draw_dialogue(self, screen, viewport, font, player):
        if not self.is_near(player): return
        x, y = game_pos(self.row, self.col, viewport)
        text = f"{self.name}: Halo!"
        surf = font.render(text, True, (255,255,255))
        box = surf.get_rect(midbottom=(x, y-int(62*viewport.scale)))
        panel = pygame.Surface((box.width+18, box.height+12), pygame.SRCALPHA)
        panel.fill((15,20,30,225)); screen.blit(panel,(box.x-9,box.y-6)); screen.blit(surf,box)