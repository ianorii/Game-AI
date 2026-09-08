"""
Player movement with smooth interpolation for consistent speed.

The player can be controlled via keyboard (WASD/Arrow keys) for manual movement,
or via mouse click for A* pathfinding to a target position.
"""
import math

import pygame

from map import CELL_SIZE
from pathfinding import astar
from utils import (
    draw_circle_debug,
    draw_sprite_smooth,
    game_pos,
    snap_to_walkable,
)


class Player:
    """Player character with manual movement and A* pathfinding."""

    def __init__(self, row, col, sprite=None):
        """Initialize player at grid position (row, col) with a sprite."""
        self.start_pos = (row, col)
        self.row, self.col = row, col
        self.sprite = sprite
        self.facing = 1  # -1 = left, 1 = right

        # Pathfinding
        self.heuristic = "manhattan"
        self.target = None
        self.path = []
        self.path_index = 0

        # Debug info
        self.debug_visited = []
        self.debug_path = []
        self.total_expanded = 0

        # Movement
        self.move_speed = 1000.0  # pixels per second
        self.manual_interval = 0.012  # seconds between manual moves
        self.manual_timer = 0.0

        # Smooth movement interpolation
        self.smooth_r = float(row)
        self.smooth_c = float(col)

    def snap_to_walkable(self, game_map):
        """Find the nearest walkable cell if current position is blocked."""
        snap_to_walkable(self, game_map)

    def set_target(self, row, col, game_map):
        """Set a target position and compute A* path to it.

        Returns True if a valid path was found, False otherwise.
        """
        if not game_map.is_walkable(row, col):
            self.target = None
            self.path = []
            self.path_index = 0
            return False

        result = astar(
            game_map.get_grid(),
            (self.row, self.col),
            (row, col),
            heuristic_name=self.heuristic,
            allow_diagonal=False,
        )
        self.debug_visited = result["visited"]
        self.debug_path = result["path"]
        self.total_expanded = result["total_expanded"]

        if not result["found"]:
            self.target = None
            self.path = []
            self.path_index = 0
            return False

        self.target = (row, col)
        self.path = result["path"]
        self.path_index = 0
        self.smooth_r = float(self.row)
        self.smooth_c = float(self.col)
        return True

    def handle_input(self, keys, game_map, dt):
        """Process keyboard input for manual movement (WASD / Arrow keys)."""
        self.manual_timer = max(0.0, self.manual_timer - dt)
        if self.manual_timer > 0:
            return

        dr = dc = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dr = -1
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dr = 1
        elif keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dc = -1
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dc = 1

        if dr or dc:
            # Cancel any active pathfinding
            self.target = None
            self.path = []
            self.path_index = 0

            nr, nc = self.row + dr, self.col + dc
            if game_map.is_walkable(nr, nc):
                if dc:
                    self.facing = 1 if dc > 0 else -1
                self.row, self.col = nr, nc
                self.smooth_r, self.smooth_c = float(nr), float(nc)

            self.manual_timer = self.manual_interval

    def update(self, game_map, dt):
        """Update player movement along the A* path with smooth interpolation."""
        if self.target is None or not self.path:
            return

        if self.path_index >= len(self.path):
            self.target = None
            return

        # Smooth interpolation towards current grid position
        dr = self.row - self.smooth_r
        dc = self.col - self.smooth_c
        pixel_dist = math.sqrt(dr * dr + dc * dc) * CELL_SIZE
        max_move = self.move_speed * dt

        if pixel_dist <= max_move:
            # Snap to current grid position
            self.smooth_r = float(self.row)
            self.smooth_c = float(self.col)
        else:
            # Interpolate towards current position
            ratio = max_move / pixel_dist
            self.smooth_r += dr * ratio
            self.smooth_c += dc * ratio
            return

        # Move to next path node
        nr, nc = self.path[self.path_index]
        if not game_map.is_walkable(nr, nc):
            # Path blocked, try to recompute
            old_target = self.target
            self.target = None
            self.path = []
            self.path_index = 0
            self.set_target(*old_target, game_map)
            return

        if nc != self.col:
            self.facing = 1 if nc > self.col else -1
        self.row, self.col = nr, nc
        self.path_index += 1

        # Check if reached target
        if (self.row, self.col) == self.target:
            self.target = None
            self.path = []
            self.path_index = 0

    def reset(self):
        """Reset player to starting position and clear all state."""
        self.row, self.col = self.start_pos
        self.smooth_r, self.smooth_c = float(self.row), float(self.col)
        self.target = None
        self.path = []
        self.path_index = 0
        self.debug_visited = []
        self.debug_path = []
        self.total_expanded = 0

    def get_pos(self):
        """Return the current grid position as (row, col)."""
        return self.row, self.col

    def draw(self, screen, viewport):
        """Draw the player sprite at its current smooth position."""
        draw_sprite_smooth(
            screen, self.sprite, self.smooth_r, self.smooth_c, viewport, self.facing
        )

    def draw_debug(self, screen, cell_size):
        """Draw a debug circle at the player's grid position."""
        draw_circle_debug(screen, self.row, self.col, cell_size, (0, 200, 0))

    def draw_target(self, screen, viewport):
        """Draw a target indicator circle at the A* goal position."""
        if self.target is None:
            return
        x, y = game_pos(*self.target, viewport)
        pygame.draw.circle(
            screen,
            (255, 235, 70),
            (x, y),
            max(5, int(8 * viewport.scale)),
            max(2, int(2 * viewport.scale)),
        )

    def draw_target_debug(self, screen, cell_size):
        """Draw a debug target indicator at the goal grid position."""
        if self.target is None:
            return
        r, c = self.target
        cx = c * cell_size + cell_size // 2
        cy = r * cell_size + cell_size // 2
        pygame.draw.circle(screen, (255, 235, 70), (cx, cy), cell_size // 3, 3)
