import pygame
from npc import game_pos

class DebugOverlay:
    def __init__(self):
        self.show_visited = True
        self.show_path = True
        self.show_info = True

    def toggle(self, key):
        if key == pygame.K_1: self.show_visited = not self.show_visited
        elif key == pygame.K_2: self.show_path = not self.show_path
        elif key == pygame.K_3: self.show_info = not self.show_info

    def draw_scaled(self, screen, player, font, viewport):
        if self.show_visited:
            for r,c in player.debug_visited:
                if (r,c) not in player.debug_path and (r,c)!=(player.row,player.col):
                    x,y=game_pos(r,c,viewport); size=max(3,int(9*viewport.scale))
                    s=pygame.Surface((size,size),pygame.SRCALPHA); s.fill((70,140,255,120)); screen.blit(s,(x-size//2,y-size//2))
        if self.show_path:
            for r,c in player.debug_path:
                x,y=game_pos(r,c,viewport); pygame.draw.rect(screen,(255,70,90),(x-3,y-3,6,6))
        if self.show_info:
            info=font.render(f"Expanded: {player.total_expanded} | Heuristic: {player.heuristic}",True,(255,255,255))
            screen.blit(info,(18,42))
