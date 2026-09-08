"""
Shared utility functions for rendering sprites and finding walkable cells.
Used by both Player and NPC to avoid code duplication.
"""
import math
import pygame

from collections import deque
from map import CELL_SIZE


def snap_to_walkable(entity, game_map):
    """Find the nearest walkable cell to the entity's current position using BFS."""
    if game_map.is_walkable(entity.row, entity.col):
        entity.start_pos = (entity.row, entity.col)
        return

    start = (entity.row, entity.col)
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
                entity.row, entity.col = entity.start_pos = (nr, nc)
                entity.smooth_r, entity.smooth_c = float(nr), float(nc)
                return
            queue.append((nr, nc))


def game_pos(row, col, viewport):
    """Convert grid position (row, col) to screen pixel coordinates."""
    return (
        viewport.map_rect.x + int((col + 0.5) * CELL_SIZE * viewport.scale),
        viewport.map_rect.y + int((row + 0.5) * CELL_SIZE * viewport.scale),
    )


def draw_sprite(screen, sprite, row, col, viewport, facing=1):
    """Draw a sprite at a grid position (snapped to cell center)."""
    if sprite is None:
        return

    width = max(28, int(sprite.get_width() * viewport.scale))
    height = max(42, int(sprite.get_height() * viewport.scale))
    scaled = pygame.transform.scale(sprite, (width, height))

    if facing < 0:
        scaled = pygame.transform.flip(scaled, True, False)

    x, y = game_pos(row, col, viewport)
    screen.blit(scaled, (x - width // 2, y - height + max(2, int(4 * viewport.scale))))


def draw_sprite_smooth(screen, sprite, smooth_r, smooth_c, viewport, facing=1):
    """Draw a sprite at a smooth (floating-point) grid position for animation."""
    if sprite is None:
        return

    width = max(28, int(sprite.get_width() * viewport.scale))
    height = max(42, int(sprite.get_height() * viewport.scale))
    scaled = pygame.transform.scale(sprite, (width, height))

    if facing < 0:
        scaled = pygame.transform.flip(scaled, True, False)

    x = viewport.map_rect.x + int((smooth_c + 0.5) * CELL_SIZE * viewport.scale)
    y = viewport.map_rect.y + int((smooth_r + 0.5) * CELL_SIZE * viewport.scale)
    screen.blit(scaled, (x - width // 2, y - height + max(2, int(4 * viewport.scale))))


def draw_circle_debug(screen, row, col, cell_size, color):
    """Draw a debug circle at the center of a grid cell."""
    cx = col * cell_size + cell_size // 2
    cy = row * cell_size + cell_size // 2
    pygame.draw.circle(screen, color, (cx, cy), cell_size // 3)
