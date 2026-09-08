"""
Debug overlay for visualizing pathfinding results.

Displays visited nodes, path nodes, and expansion info.
Toggle layers with keys 1 (visited), 2 (path), 3 (info).
"""
import pygame

from utils import game_pos


class DebugOverlay:
    """Manages debug visualization layers for pathfinding."""

    def __init__(self):
        """Initialize all debug layers as visible."""
        self.show_visited = True
        self.show_path = True
        self.show_info = True

    def toggle(self, key):
        """Toggle a debug layer based on the key pressed.

        Keys:
            K_1: Toggle visited nodes
            K_2: Toggle path nodes
            K_3: Toggle info panel
        """
        if key == pygame.K_1:
            self.show_visited = not self.show_visited
        elif key == pygame.K_2:
            self.show_path = not self.show_path
        elif key == pygame.K_3:
            self.show_info = not self.show_info

    def draw_scaled(self, screen, player, font, viewport, hide_visited=False):
        """Draw all active debug layers onto the screen.

        Args:
            screen: pygame surface to draw on
            player: player object with debug_visited, debug_path, etc.
            font: pygame font for text rendering
            viewport: viewport for coordinate mapping
            hide_visited: if True, skip drawing visited nodes (used in edit mode)
        """
        # Draw visited nodes (blue dots)
        if self.show_visited and not hide_visited:
            for r, c in player.debug_visited:
                if (r, c) not in player.debug_path and (r, c) != (player.row, player.col):
                    x, y = game_pos(r, c, viewport)
                    size = max(3, int(9 * viewport.scale))
                    s = pygame.Surface((size, size), pygame.SRCALPHA)
                    s.fill((70, 140, 255, 120))
                    screen.blit(s, (x - size // 2, y - size // 2))

        # Draw path nodes (red squares)
        if self.show_path:
            for r, c in player.debug_path:
                x, y = game_pos(r, c, viewport)
                pygame.draw.rect(screen, (255, 70, 90), (x - 3, y - 3, 6, 6))

        # Draw info text
        if self.show_info:
            info = font.render(
                f"Expanded: {player.total_expanded} | Heuristic: {player.heuristic}",
                True,
                (255, 255, 255),
            )
            screen.blit(info, (18, 42))
