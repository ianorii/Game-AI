"""Game AI 2D - fullscreen pixel map, keyboard/click Player, stationary NPC."""
import asyncio, sys, pygame
from map import GameMap, Viewport, CELL_SIZE, ROWS, COLS
from npc import NPC, game_pos
from player import Player
from debug_overlay import DebugOverlay

FPS=120
HEURISTICS=["manhattan","euclidean","chebyshev","octile","ucs"]

def make_window(fullscreen=True):
    info=pygame.display.Info()
    return pygame.display.set_mode((info.current_w,info.current_h), pygame.FULLSCREEN) if fullscreen else pygame.display.set_mode((1280,720),pygame.RESIZABLE)

def build_edit_surface(game_map, viewport):
    """Full-map translucent overlay: blocked cells shown in red, walkable transparent."""
    surf=pygame.Surface(viewport.map_rect.size, pygame.SRCALPHA)
    grid=game_map.get_grid(); cellw=CELL_SIZE*viewport.scale
    for r in range(ROWS):
        for c in range(COLS):
            if grid[r][c]==1:
                x=int(c*cellw); y=int(r*cellw)
                w=int((c+1)*cellw)-x; h=int((r+1)*cellw)-y
                surf.fill((230,45,55,80),(x,y,w,h))
    return surf

def paint_edit_cell(surface, game_map, viewport, r, c):
    """Redraw a single grid cell on the overlay after a manual edit."""
    if not game_map.is_valid(r,c): return
    cellw=CELL_SIZE*viewport.scale
    x=int(c*cellw); y=int(r*cellw)
    w=int((c+1)*cellw)-x; h=int((r+1)*cellw)-y
    surface.fill((230,45,55,80) if game_map.get_grid()[r][c]==1 else (0,0,0,0),(x,y,w,h))

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
    npc=NPC(20,5,npc_sprite,"Niko"); npc.snap_to_walkable(game_map)
    overlay=DebugOverlay(); hi=0; status="WASD/Arrow = Player | Klik map = Player A*"
    edit_mode=False; edit_surface=None; cellw=CELL_SIZE*viewport.scale
    running=True
    while running:
        for event in pygame.event.get():
            if event.type==pygame.QUIT: running=False
            elif event.type==pygame.VIDEORESIZE and not fullscreen:
                screen=pygame.display.set_mode(event.size,pygame.RESIZABLE); viewport=Viewport(screen.get_size())
                cellw=CELL_SIZE*viewport.scale
                if edit_mode: edit_surface=build_edit_surface(game_map,viewport)
            elif event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE: running=False
                elif event.key==pygame.K_F11:
                    fullscreen=not fullscreen; screen=make_window(fullscreen); viewport=Viewport(screen.get_size())
                    cellw=CELL_SIZE*viewport.scale
                    if edit_mode: edit_surface=build_edit_surface(game_map,viewport)
                elif event.key==pygame.K_m:
                    edit_mode=not edit_mode
                    if edit_mode: edit_surface=build_edit_surface(game_map,viewport)
                    status=f"Edit Grid: {'ON (klik kiri=tutup 1, kanan=buka 0)' if edit_mode else 'OFF'}"
                elif event.key==pygame.K_p:
                    game_map.save_grid_override(); status="Grid disimpan ke grid_override.txt"
                elif event.key==pygame.K_l:
                    ok=game_map.load_grid_override()
                    if edit_mode: edit_surface=build_edit_surface(game_map,viewport)
                    status="Grid dimuat dari grid_override.txt" if ok else "Gagal memuat grid_override.txt"
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
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and not edit_mode:
                cell=game_map.screen_to_grid(event.pos,viewport)
                if cell:
                    r,c=cell
                    if player.set_target(r,c,game_map): status=f"Target Player A*: ({c},{r})"
                    else: status="Target tidak bisa dilewati atau tidak ada jalur."

        keys=pygame.key.get_pressed(); dt = clock.get_time() / 1000.0
        if edit_mode:
            pressed=pygame.mouse.get_pressed()
            if pressed[0] or pressed[2]:
                cell=game_map.screen_to_grid(pygame.mouse.get_pos(),viewport)
                if cell and edit_surface is not None:
                    r,c=cell; val=1 if pressed[0] else 0
                    if game_map.get_grid()[r][c]!=val:
                        game_map.set_cell(r,c,val); paint_edit_cell(edit_surface,game_map,viewport,r,c)
        player.handle_input(keys, game_map, dt); player.update(game_map, dt)
        npc.update(game_map, player, dt)
        screen.fill((12,14,18)); game_map.draw(screen,viewport)
        if edit_mode and edit_surface is not None:
            screen.blit(edit_surface,viewport.map_rect.topleft)
        overlay.draw_scaled(screen,player,small,viewport,hide_visited=edit_mode); player.draw_target(screen,viewport)
        if edit_mode:
            hover=game_map.screen_to_grid(pygame.mouse.get_pos(),viewport)
            if hover:
                r,c=hover; gv=game_map.get_grid()[r][c]
                hs=pygame.Rect(0,0,max(2,int(CELL_SIZE*viewport.scale)),max(2,int(CELL_SIZE*viewport.scale)))
                hs.center=game_pos(r,c,viewport)
                pygame.draw.rect(screen,(255,235,90),hs,2)
                bar=pygame.Surface((max(320,screen.get_width()//3),84),pygame.SRCALPHA); bar.fill((10,20,20,200))
                screen.blit(bar,(14,screen.get_height()-96))
                for i,t in enumerate([f"Cell ({r},{c}) grid={gv}  {'BLOKIR' if gv==1 else 'LEWAT'}","Klik kiri=tutup(1)  |  Klik kanan=buka(0)  |  M=keluar  P=simpan  L=muat"]):
                    screen.blit(small.render(t,True,(240,240,240)),(26,screen.get_height()-86+i*22))
        # Player first, NPC second: they are visually and logically distinct.
        player.draw(screen,viewport); npc.draw(screen,viewport); npc.draw_dialogue(screen,viewport,dialogue,player)

        if overlay.show_info:
            left=pygame.Surface((min(570,screen.get_width()//2),160),pygame.SRCALPHA); left.fill((10,20,20,185)); screen.blit(left,(12,12))
            lines=["Klik map : Player menuju target dengan A*","WASD / Arrow : Gerak Player","Q / E : Ganti heuristic Player","T / G : Ganti algoritma NPC (UCS/A*)","F : NPC ikuti player ON/OFF","M : Edit Grid    P : Simpan Grid    L : Muat Grid","R : Reset    F11 : Fullscreen    ESC : Keluar",status]
            for i,t in enumerate(lines): screen.blit(small.render(t,True,(240,240,240)),(22,20+i*22))
            p=player.get_pos(); n=npc.get_pos(); t=player.target if player.target else ("-","-")
            info=[f"Player : ({p[1]}, {p[0]})",f"NPC    : ({n[1]}, {n[0]})",f"Target : ({t[1]}, {t[0]})",f"Path   : {len(player.path)} node",f"Heuristic Player: {player.heuristic}",f"NPC {npc.heuristic.upper()} | {"ikut" if npc.follow else "diam"} | path {len(npc.path)}"]
            w=275; h=145; panel=pygame.Surface((w,h),pygame.SRCALPHA); panel.fill((10,20,20,185)); x=screen.get_width()-w-12; screen.blit(panel,(x,12))
            for i,t in enumerate(info): screen.blit(small.render(t,True,(240,240,240)),(x+10,20+i*21))
        pygame.display.flip(); await asyncio.sleep(0); clock.tick(FPS)
    pygame.quit(); sys.exit()

if __name__=="__main__": asyncio.run(main())
