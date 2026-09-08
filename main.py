"""
NPC Pathfinding Game - Main Entry Point
Pygame + Pygbag (browser)

Controls:
  Click petak        : Set target NPC
  1                  : Toggle tampilan visited nodes
  2                  : Toggle tampilan path
  3                  : Toggle info text
  Q / E              : Ganti heuristic NPC (sebelumnya/selanjutnya)
  R                  : Reset posisi NPC
"""

import asyncio
import pygame
import sys

from map import GameMap, CELL_SIZE, ROWS, COLS
from npc import NPC
from debug_overlay import DebugOverlay
from player import Player

SCREEN_WIDTH = COLS * CELL_SIZE
SCREEN_HEIGHT = ROWS * CELL_SIZE

FPS = 120

HEURISTICS = ["manhattan", "euclidean", "chebyshev", "octile", "ucs"]

async def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("NPC Pathfinding - A* Click to Move")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 14)

    game_map = GameMap()
    npc = NPC(0, 0, heuristic="manhattan")
    overlay = DebugOverlay()

    player = Player(5, 5)

    heuristic_index = 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_1:
                    overlay.toggle(pygame.K_1)
                elif event.key == pygame.K_2:
                    overlay.toggle(pygame.K_2)
                elif event.key == pygame.K_3:
                    overlay.toggle(pygame.K_3)
                elif event.key == pygame.K_q:
                    heuristic_index = (heuristic_index - 1) % len(HEURISTICS)
                    npc.heuristic = HEURISTICS[heuristic_index]
                    npc.path = []
                    npc.path_index = 0
                elif event.key == pygame.K_e:
                    heuristic_index = (heuristic_index + 1) % len(HEURISTICS)
                    npc.heuristic = HEURISTICS[heuristic_index]
                    npc.path = []
                    npc.path_index = 0
                elif event.key == pygame.K_r:
                    npc.row, npc.col = 0, 0
                    npc.target = None
                    npc.path = []
                    npc.path_index = 0
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                col = mx // CELL_SIZE
                row = my // CELL_SIZE
                if game_map.is_walkable(row, col):
                    npc.set_target(row, col)

        keys = pygame.key.get_pressed()
        player.handle_input(keys, game_map)

        player_pos = player.get_pos()
        if player_pos != npc.target:
            npc.target = player_pos
            npc.path = []

        # Update
        npc.update(game_map)

        # Draw
        # screen.fill((30, 30, 30))
        game_map.draw(screen)
        overlay.draw(screen, npc, font)
        npc.draw_target(screen)
        npc.draw(screen)
        player.draw(screen)

        pygame.display.flip()
        await asyncio.sleep(0)
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
