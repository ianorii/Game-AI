"""
Debug Overlay - Visualisasi node yang di-expand dan path
"""

import pygame
from map import CELL_SIZE


class DebugOverlay:
    def __init__(self):
        self.show_visited = True
        self.show_path = True
        self.show_info = True

    def toggle(self, key):
        if key == pygame.K_1:
            self.show_visited = not self.show_visited
        elif key == pygame.K_2:
            self.show_path = not self.show_path
        elif key == pygame.K_3:
            self.show_info = not self.show_info

    def draw(self, screen, npc, font):
        visited_color = (255, 200, 100, 128)  # kuning transparan
        path_color = (100, 255, 100, 200)     # hijau

        # Draw visited nodes
        if self.show_visited:
            for r, c in npc.debug_visited:
                if (r, c) != (npc.row, npc.col) and (r, c) not in npc.debug_path:
                    rect = pygame.Rect(
                        c * CELL_SIZE + 2,
                        r * CELL_SIZE + 2,
                        CELL_SIZE - 4,
                        CELL_SIZE - 4,
                    )
                    s = pygame.Surface((CELL_SIZE - 4, CELL_SIZE - 4), pygame.SRCALPHA)
                    s.fill((255, 200, 100, 60))
                    screen.blit(s, rect.topleft)

        # Draw path
        if self.show_path:
            for i, (r, c) in enumerate(npc.debug_path):
                rect = pygame.Rect(
                    c * CELL_SIZE + 6,
                    r * CELL_SIZE + 6,
                    CELL_SIZE - 12,
                    CELL_SIZE - 12,
                )
                s = pygame.Surface((CELL_SIZE - 12, CELL_SIZE - 12), pygame.SRCALPHA)
                s.fill((100, 255, 100, 150))
                screen.blit(s, rect.topleft)

        # Draw info text
        if self.show_info and font:
            info_text = f"Expanded: {npc.total_expanded} | Heuristic: {npc.heuristic}"
            text_surface = font.render(info_text, True, (255, 255, 255))
            screen.blit(text_surface, (10, 10))

            controls = "Controls: WASD=Move | 1=Toggle Visited | 2=Toggle Path | 3=Toggle Info"
            ctrl_surface = font.render(controls, True, (200, 200, 200))
            screen.blit(ctrl_surface, (10, 30))
