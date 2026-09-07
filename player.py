"""
Player - Dikontrol dengan keyboard (WASD / Arrow keys)
"""

import pygame
from map import CELL_SIZE, ROWS, COLS


class Player:
    def __init__(self, row, col):
        self.row = row
        self.col = col
        self.color = (0, 200, 0)

    def handle_input(self, keys, game_map):
        new_row, new_col = self.row, self.col

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            new_row -= 1
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            new_row += 1
        elif keys[pygame.K_a] or keys[pygame.K_LEFT]:
            new_col -= 1
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            new_col += 1

        if game_map.is_walkable(new_row, new_col):
            self.row = new_row
            self.col = new_col

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
