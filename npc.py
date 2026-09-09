"""
NPC rendering, interaction and pursuit of the player.

The NPC uses A* pathfinding to follow the player with smooth interpolation.
Dialogue is shown when the NPC is near the player.
"""
import math

import pygame

from map import CELL_SIZE
from pathfinding import astar
from utils import (
    draw_sprite_smooth,
    game_pos,
    snap_to_walkable,
)


class NPC:
    """Non-player character that can follow the player using pathfinding."""

    def __init__(self, row, col, sprite=None, name="Niko"):
        """Initialize NPC at grid position (row, col) with a sprite and name."""
        self.start_pos = (row, col)
        self.row, self.col = row, col
        self.sprite = sprite
        self.name = name
        self.facing = -1  # -1 = left, 1 = right

        # Follow mode
        self.follow = True
        self.heuristic = "ucs"

        # Movement
        self.move_speed = 1000.0  # pixels per second
        self.recompute_interval = 0.10  # seconds between path recalculations

        # Pathfinding state
        self.path = []
        self.path_index = 0
        self.timer = 0.0
        self.recompute_timer = 0.0

        # Debug info
        self.debug_visited = []
        self.debug_path = []
        self.total_expanded = 0

        # Smooth movement interpolation
        self.smooth_r = float(row)
        self.smooth_c = float(col)

    def reset(self):
        """Reset NPC to its starting position and clear all state."""
        self.row, self.col = self.start_pos
        self.facing = -1
        self.smooth_r, self.smooth_c = float(self.row), float(self.col)
        self.path = []
        self.path_index = 0
        self.timer = 0.0
        self.recompute_timer = 0.0
        self.debug_visited = []
        self.debug_path = []
        self.total_expanded = 0

    def set_heuristic(self, heuristic):
        """Set the heuristic function for pathfinding."""
        self.heuristic = heuristic

    def snap_to_walkable(self, game_map):
        """Find the nearest walkable cell if current position is blocked."""
        snap_to_walkable(self, game_map)

    def get_pos(self):
        """Return the current grid position as (row, col)."""
        return self.row, self.col

    def is_near(self, player):
        """Check if the NPC is adjacent to the player (Manhattan distance <= 1)."""
        return abs(self.row - player.row) + abs(self.col - player.col) <= 1

    def update(self, game_map, player, dt):
        """Update NPC movement towards the player.

        Periodically recomputes the path using A* and moves along it
        with smooth interpolation.
        """
        if not self.follow:
            return

        # Recompute path periodically
        self.recompute_timer -= dt
        if self.recompute_timer <= 0:
            self.recompute_timer = self.recompute_interval
            result = astar(
                game_map.get_grid(),
                (self.row, self.col),
                (player.row, player.col),
                heuristic_name=self.heuristic,
                allow_diagonal=False,
            )
            self.debug_visited = result["visited"]
            self.debug_path = result["path"]
            self.total_expanded = result["total_expanded"]

            if result["found"]:
                self.path = result["path"][:-1]  # exclude goal (player position)
            else:
                self.path = []
            self.path_index = 0
            self.smooth_r = float(self.row)
            self.smooth_c = float(self.col)

        # Move along the path
        if not self.path or self.path_index >= len(self.path):
            return

        budget = self.move_speed * dt

        while budget > 0 and self.path_index < len(self.path):
            dr = self.row - self.smooth_r
            dc = self.col - self.smooth_c
            pixel_dist = math.sqrt(dr * dr + dc * dc) * CELL_SIZE

            if pixel_dist > budget:
                ratio = budget / pixel_dist
                self.smooth_r += dr * ratio
                self.smooth_c += dc * ratio
                budget = 0
            else:
                self.smooth_r = float(self.row)
                self.smooth_c = float(self.col)
                budget -= pixel_dist

                nr, nc = self.path[self.path_index]
                if game_map.is_walkable(nr, nc):
                    if nc != self.col:
                        self.facing = 1 if nc > self.col else -1
                    self.row, self.col = nr, nc
                self.path_index += 1

    def draw(self, screen, viewport):
        """Draw the NPC sprite at its current smooth position."""
        draw_sprite_smooth(
            screen, self.sprite, self.smooth_r, self.smooth_c, viewport, self.facing
        )

    def draw_debug(self, screen, cell_size):
        """Draw a debug circle at the NPC's grid position."""
        from utils import draw_circle_debug
        draw_circle_debug(screen, self.row, self.col, cell_size, (200, 50, 50))

    def draw_dialogue(self, screen, viewport, font, player):
        """Show a dialogue bubble when the NPC is near the player."""
        if not self.is_near(player):
            return

        x, y = game_pos(self.row, self.col, viewport)
        text = f"{self.name}: Halo!"
        surf = font.render(text, True, (255, 255, 255))
        box = surf.get_rect(midbottom=(x, y - int(62 * viewport.scale)))

        # Draw dialogue panel background
        panel = pygame.Surface(
            (box.width + 18, box.height + 12), pygame.SRCALPHA
        )
        panel.fill((15, 20, 30, 225))
        screen.blit(panel, (box.x - 9, box.y - 6))
        screen.blit(surf, box)
