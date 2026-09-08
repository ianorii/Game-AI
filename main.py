"""Game AI 2D - fullscreen pixel map, keyboard/click Player, stationary NPC."""
import asyncio, sys, pygame
from map import GameMap, Viewport
from npc import NPC
from player import Player
from debug_overlay import DebugOverlay

FPS=120
HEURISTICS=["manhattan","euclidean","chebyshev","octile","ucs"]

def make_window(fullscreen=True):
    info=pygame.display.Info()
    return pygame.display.set_mode((info.current_w,info.current_h), pygame.FULLSCREEN) if fullscreen else pygame.display.set_mode((1280,720),pygame.RESIZABLE)

async def main():
    pygame.init(); fullscreen=True; screen=make_window(True)
    pygame.display.set_caption("Game AI - Player A* + NPC")
    clock=pygame.time.Clock()
    small=pygame.font.SysFont("consolas",max(14,screen.get_width()//115))
    dialogue=pygame.font.SysFont("consolas",max(13,screen.get_width()//125))
    game_map=GameMap(); viewport=Viewport(screen.get_size())
    player_sprite=game_map.get_asset("08_karakter/karakter_pemain")
    npc_sprite=game_map.get_asset("08_karakter/karakter_npc")

    # Valid walkable starting cells on the visible path.
    player=Player(16,9,player_sprite); player.snap_to_walkable(game_map)
    npc=NPC(20,5,npc_sprite,"Niko")
    overlay=DebugOverlay(); hi=0; status="WASD/Arrow = Player | Klik map = Player A*"
    running=True
    while running:
        for event in pygame.event.get():
            if event.type==pygame.QUIT: running=False
            elif event.type==pygame.VIDEORESIZE and not fullscreen:
                screen=pygame.display.set_mode(event.size,pygame.RESIZABLE); viewport=Viewport(screen.get_size())
            elif event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE: running=False
                elif event.key==pygame.K_F11:
                    fullscreen=not fullscreen; screen=make_window(fullscreen); viewport=Viewport(screen.get_size())
                elif event.key in (pygame.K_1,pygame.K_2,pygame.K_3): overlay.toggle(event.key)
                elif event.key==pygame.K_q:
                    hi=(hi-1)%len(HEURISTICS); player.heuristic=HEURISTICS[hi]; status=f"Heuristic Player A*: {player.heuristic}"
                elif event.key==pygame.K_e:
                    hi=(hi+1)%len(HEURISTICS); player.heuristic=HEURISTICS[hi]; status=f"Heuristic Player A*: {player.heuristic}"
                elif event.key==pygame.K_t:
                    hi=(hi-1)%len(HEURISTICS); npc.set_heuristic(HEURISTICS[hi]); status=f"Algoritma NPC: {npc.heuristic}"
                elif event.key==pygame.K_g:
                    hi=(hi+1)%len(HEURISTICS); npc.set_heuristic(HEURISTICS[hi]); status=f"Algoritma NPC: {npc.heuristic}"
                elif event.key==pygame.K_f:
                    npc.follow=not npc.follow; status=f"NPC ikuti player: {'ON' if npc.follow else 'OFF'}"
                elif event.key==pygame.K_r:
                    player.reset(); npc.reset(); status="Player dan NPC di-reset."
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                cell=game_map.screen_to_grid(event.pos,viewport)
                if cell:
                    r,c=cell
                    if player.set_target(r,c,game_map): status=f"Target Player A*: ({c},{r})"
                    else: status="Target tidak bisa dilewati atau tidak ada jalur."

        keys=pygame.key.get_pressed(); dt = clock.get_time() / 1000.0
        player.handle_input(keys, game_map, dt); player.update(game_map, dt)
        npc.update(game_map, player, dt)
        screen.fill((12,14,18)); game_map.draw(screen,viewport)
        overlay.draw_scaled(screen,player,small,viewport); player.draw_target(screen,viewport)
        # Player first, NPC second: they are visually and logically distinct.
        player.draw(screen,viewport); npc.draw(screen,viewport); npc.draw_dialogue(screen,viewport,dialogue,player)

        if overlay.show_info:
            left=pygame.Surface((min(570,screen.get_width()//2),160),pygame.SRCALPHA); left.fill((10,20,20,185)); screen.blit(left,(12,12))
            lines=["Klik map : Player menuju target dengan A*","WASD / Arrow : Gerak Player","Q / E : Ganti heuristic Player","T / G : Ganti algoritma NPC (UCS/A*)","F : NPC ikuti player ON/OFF","1 : Node   2 : Jalur A*   3 : Info","R : Reset    F11 : Fullscreen    ESC : Keluar",status]
            for i,t in enumerate(lines): screen.blit(small.render(t,True,(240,240,240)),(22,20+i*22))
            p=player.get_pos(); n=npc.get_pos(); t=player.target if player.target else ("-","-")
            info=[f"Player : ({p[1]}, {p[0]})",f"NPC    : ({n[1]}, {n[0]})",f"Target : ({t[1]}, {t[0]})",f"Path   : {len(player.path)} node",f"Heuristic Player: {player.heuristic}",f"NPC {npc.heuristic.upper()} | {"ikut" if npc.follow else "diam"} | path {len(npc.path)}"]
            w=275; h=145; panel=pygame.Surface((w,h),pygame.SRCALPHA); panel.fill((10,20,20,185)); x=screen.get_width()-w-12; screen.blit(panel,(x,12))
            for i,t in enumerate(info): screen.blit(small.render(t,True,(240,240,240)),(x+10,20+i*21))
        pygame.display.flip(); await asyncio.sleep(0); clock.tick(FPS)
    pygame.quit(); sys.exit()

if __name__=="__main__": asyncio.run(main())
