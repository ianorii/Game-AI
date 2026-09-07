"""
NPC - Bergerak ke target (posisi klik) menggunakan A*
"""

import pygame
from pathfinding import astar
from map import CELL_SIZE


class NPC:
    def __init__(self, row, col, heuristic="manhattan", color=(200, 50, 50)):
        self.row = row
        self.col = col
        self.color = color
        self.heuristic = heuristic
        self.path = []
        self.path_index = 0
        self.move_timer = 0
        self.move_delay = 8  # frame delay antar langkah

        # Target
        self.target = None

        # Debug info
        self.debug_visited = []
        self.debug_path = []
        self.total_expanded = 0

    def set_target(self, row, col):
        """Set target baru. Pathfinding akan diulang."""
        if (row, col) == (self.row, self.col):
            return
        self.target = (row, col)
        self.path = []
        self.path_index = 0

    def update(self, game_map):
        if self.target is None:
            return

        self.move_timer += 1
        if self.move_timer < self.move_delay:
            return
        self.move_timer = 0

        # Sudah sampai di target
        if (self.row, self.col) == self.target:
            return

        # Re-pathfinding jika path habis
        if not self.path or self.path_index >= len(self.path):
            grid = game_map.get_grid()
            result = astar(
                grid,
                (self.row, self.col),
                self.target,
                heuristic_name=self.heuristic,
            )
            self.debug_visited = result["visited"]
            self.debug_path = result["path"]
            self.total_expanded = result["total_expanded"]

            if result["found"]:
                self.path = result["path"]
                self.path_index = 0
            else:
                self.path = []
                return

        # Bergerak ke node berikutnya
        next_row, next_col = self.path[self.path_index]
        self.row = next_row
        self.col = next_col
        self.path_index += 1

    def get_pos(self):
        return (self.row, self.col)

    def draw(self, screen):
        rect = pygame.Rect(
            self.col * CELL_SIZE + 4,
            self.row * CELL_SIZE + 4,
            CELL_SIZE - 8,
            CELL_SIZE - 8,
        )
        pygame.draw.rect(screen, self.color, rect, border_radius=4)

    def draw_target(self, screen):
        """Gambar marker target."""
        if self.target is None:
            return
        r, c = self.target
        rect = pygame.Rect(
            c * CELL_SIZE + 6,
            r * CELL_SIZE + 6,
            CELL_SIZE - 12,
            CELL_SIZE - 12,
        )
        pygame.draw.rect(screen, (255, 255, 0), rect, 3, border_radius=4)
