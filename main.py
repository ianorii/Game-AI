"""
Game AI 2D - Main entry point.

Aplikasi utama yang menginisialisasi game loop, mengelola input,
rendering, dan koordinasi antar modul.

Alur utama:
1. Inisialisasi pygame, window, dan game objects
2. Game loop: handle events → update → render
3. Cleanup saat keluar

Modul yang digunakan:
- player.py: Player movement (manual + A* pathfinding)
- npc.py: NPC follow behavior (A* recompute periodically)
- pathfinding.py: Core A* & UCS implementation
- map.py: Grid system, collision detection, viewport
- debug_overlay.py: Visualisasi visited nodes & path
- settings_menu.py: Konfigurasi heuristic & parameter game
"""
import asyncio
import sys

import pygame

from debug_overlay import DebugOverlay
from map import CELL_SIZE, COLS, ROWS, GameMap, Viewport
from npc import NPC
from player import Player
from settings_menu import SettingsMenu


# ---------------------------------------------------------------------------
# Konstanta Global
# ---------------------------------------------------------------------------

# Frame rate target: 120 FPS untuk animasi smooth
FPS = 120

# Daftar heuristic yang tersedia untuk dipilih
# Digunakan untuk cycling heuristic player/NPC
HEURISTICS = ["manhattan", "euclidean", "ucs"]

# Posisi awal player dan NPC dalam grid (row, col)
PLAYER_START = (16, 9)
NPC_START = (20, 5)


# ---------------------------------------------------------------------------
# Window Management
# ---------------------------------------------------------------------------

def make_window(fullscreen=True):
    """Membuat window game (fullscreen atau resizable).

    Args:
        fullscreen: True untuk fullscreen, False untuk windowed mode (1280x720)

    Returns:
        pygame.Surface: Surface utama untuk rendering
    """
    info = pygame.display.Info()
    if fullscreen:
        return pygame.display.set_mode(
            (info.current_w, info.current_h), pygame.FULLSCREEN
        )
    return pygame.display.set_mode((1280, 720), pygame.RESIZABLE)


# ---------------------------------------------------------------------------
# Grid Editor Helpers
# ---------------------------------------------------------------------------

def build_edit_surface(game_map, viewport):
    """Membangun overlay transparan untuk menampilkan cell yang diblokir.

    Cell yang diblokir (grid value = 1) ditampilkan dengan warna merah
    transparan untuk memudahkan visualisasi obstacle.

    Args:
        game_map: Objek GameMap yang berisi collision grid
        viewport: Objek Viewport untuk koordinat screen

    Returns:
        pygame.Surface: Surface overlay dengan cell merah
    """
    surf = pygame.Surface(viewport.map_rect.size, pygame.SRCALPHA)
    grid = game_map.get_grid()
    cellw = CELL_SIZE * viewport.scale

    # Iterasi semua cell, warnai yang blocked (value = 1)
    for r in range(ROWS):
        for c in range(COLS):
            if grid[r][c] == 1:
                x = int(c * cellw)
                y = int(r * cellw)
                w = int((c + 1) * cellw) - x
                h = int((r + 1) * cellw) - y
                # Merah transparan untuk cell obstacle
                surf.fill((230, 45, 55, 80), (x, y, w, h))

    return surf


def paint_edit_cell(surface, game_map, viewport, r, c):
    """Mengecat satu cell pada overlay edit mode.

    Memperbarui tampilan satu cell: merah jika blocked, transparan jika walkable.

    Args:
        surface: Surface overlay yang akan diupdate
        game_map: Objek GameMap
        viewport: Objek Viewport
        r: Row cell
        c: Column cell
    """
    if not game_map.is_valid(r, c):
        return

    cellw = CELL_SIZE * viewport.scale
    x = int(c * cellw)
    y = int(r * cellw)
    w = int((c + 1) * cellw) - x
    h = int((r + 1) * cellw) - y

    # Warna merah jika blocked, transparan jika walkable
    if game_map.get_grid()[r][c] == 1:
        surface.fill((230, 45, 55, 80), (x, y, w, h))
    else:
        surface.fill((0, 0, 0, 0), (x, y, w, h))


# ---------------------------------------------------------------------------
# Event Handling
# ---------------------------------------------------------------------------

def handle_events(game_map, viewport, player, npc, overlay, state):
    """Memproses semua event pygame dan memperbarui state game.

    Urutan prioritas:
    1. Quit event → keluar
    2. Settings menu visible → handle menu events
    3. Window resize → update viewport
    4. Keyboard input → handle key event
    5. Mouse click → set player A* target

    Args:
        game_map: Objek GameMap
        viewport: Objek Viewport
        player: Objek Player
        npc: Objek NPC
        overlay: Objek DebugOverlay
        state: Dict mutable berisi state game

    Returns:
        False jika game harus quit, True jika lanjut
    """
    settings_menu = state.get("settings_menu")

    for event in pygame.event.get():
        # Event keluar
        if event.type == pygame.QUIT:
            return False

        # Settings menu mendapat prioritas saat visible
        if settings_menu and settings_menu.visible:
            action = settings_menu.handle_event(event)
            if action == "reset":
                # Reset posisi player dan NPC
                player.reset()
                npc.reset()
                state["status"] = "Player dan NPC di-reset."
            elif action == "save_grid":
                # Simpan collision grid ke file
                game_map.save_grid_override()
                state["status"] = "Grid disimpan ke grid_override.txt"
            elif action == "load_grid":
                # Muat collision grid dari file
                ok = game_map.load_grid_override()
                if state["edit_mode"]:
                    state["edit_surface"] = build_edit_surface(game_map, state["viewport"])
                state["status"] = "Grid dimuat dari grid_override.txt" if ok else "Gagal memuat grid_override.txt"
            elif action == "fullscreen":
                toggle_fullscreen(game_map, state)
            elif action == "quit":
                return False
            # Apply perubahan dari menu ke game objects
            _apply_settings(settings_menu, player, npc, overlay, state)
            continue

        # Handle window resize (hanya saat windowed mode)
        elif event.type == pygame.VIDEORESIZE and not state["fullscreen"]:
            handle_resize(event, game_map, state)

        # Handle keyboard input
        elif event.type == pygame.KEYDOWN:
            result = handle_key_event(
                event, game_map, player, npc, overlay, state
            )
            if result is False:
                return False

        # Handle mouse click untuk A* pathfinding (klik kiri saja)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not state["edit_mode"]:
                handle_mouse_click(event, game_map, viewport, player, state)

    return True


def handle_resize(event, game_map, state):
    """Menangani event resize window.

    Membuat ulang viewport dan edit surface dengan ukuran baru.

    Args:
        event: pygame.VIDEORESIZE event
        game_map: Objek GameMap
        state: Dict mutable berisi state game
    """
    state["screen"] = pygame.display.set_mode(event.size, pygame.RESIZABLE)
    state["viewport"] = Viewport(state["screen"].get_size())
    state["cellw"] = CELL_SIZE * state["viewport"].scale
    state["_hud_left"] = None
    state["_hud_panel"] = None
    if state["edit_mode"]:
        state["edit_surface"] = build_edit_surface(game_map, state["viewport"])


def handle_key_event(event, game_map, player, npc, overlay, state):
    """Menangani keyboard input.

    Mapping keyboard:
    - ESC: Toggle settings menu
    - F11: Toggle fullscreen
    - M: Toggle grid edit mode
    - P: Simpan grid
    - L: Muat grid
    - 1/2/3: Toggle debug layers
    - Q/E: Cycle heuristic player
    - T/G: Cycle heuristic NPC
    - F: Toggle NPC follow
    - R: Reset posisi

    Args:
        event: pygame.KEYDOWN event
        game_map: Objek GameMap
        player: Objek Player
        npc: Objek NPC
        overlay: Objek DebugOverlay
        state: Dict mutable berisi state game

    Returns:
        False untuk quit, None untuk lanjut
    """
    key = event.key

    if key == pygame.K_ESCAPE:
        state["settings_menu"].toggle()
        return None

    elif key == pygame.K_F11:
        toggle_fullscreen(game_map, state)

    elif key == pygame.K_m:
        toggle_edit_mode(game_map, state)

    elif key == pygame.K_p:
        game_map.save_grid_override()
        state["status"] = "Grid disimpan ke grid_override.txt"

    elif key == pygame.K_l:
        ok = game_map.load_grid_override()
        if state["edit_mode"]:
            state["edit_surface"] = build_edit_surface(game_map, state["viewport"])
        state["status"] = (
            "Grid dimuat dari grid_override.txt" if ok else "Gagal memuat grid_override.txt"
        )

    elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
        overlay.toggle(key)

    elif key == pygame.K_q:
        cycle_heuristic_player(player, state, direction=-1)

    elif key == pygame.K_e:
        cycle_heuristic_player(player, state, direction=1)

    elif key == pygame.K_t:
        cycle_heuristic_npc(npc, state, direction=-1)

    elif key == pygame.K_g:
        cycle_heuristic_npc(npc, state, direction=1)

    elif key == pygame.K_f:
        npc.follow = not npc.follow
        state["status"] = f"NPC ikuti player: {'ON' if npc.follow else 'OFF'}"

    elif key == pygame.K_r:
        player.reset()
        npc.reset()
        state["status"] = "Player dan NPC di-reset."

    return None


def toggle_fullscreen(game_map, state):
    """Toggle antara fullscreen dan windowed mode.

    Args:
        game_map: Objek GameMap
        state: Dict mutable berisi state game
    """
    state["fullscreen"] = not state["fullscreen"]
    state["screen"] = make_window(state["fullscreen"])
    state["viewport"] = Viewport(state["screen"].get_size())
    state["cellw"] = CELL_SIZE * state["viewport"].scale
    state["_hud_left"] = None
    state["_hud_panel"] = None
    if state["edit_mode"]:
        state["edit_surface"] = build_edit_surface(game_map, state["viewport"])


def toggle_edit_mode(game_map, state):
    """Toggle grid edit mode on/off.

    Saat edit mode aktif, overlay merah ditampilkan untuk cell obstacle.
    User bisa klik untuk memblokir/membuka cell.

    Args:
        game_map: Objek GameMap
        state: Dict mutable berisi state game
    """
    state["edit_mode"] = not state["edit_mode"]
    if state["edit_mode"]:
        state["edit_surface"] = build_edit_surface(game_map, state["viewport"])
    state["status"] = (
        f"Edit Grid: {'ON (klik kiri=tutup 1, kanan=buka 0)' if state['edit_mode'] else 'OFF'}"
    )


def cycle_heuristic_player(player, state, direction=1):
    """Mengganti heuristic player secara circular (cycle).

    Args:
        player: Objek Player
        state: Dict mutable berisi state game
        direction: 1 untuk maju, -1 untuk mundur
    """
    state["hi"] = (state["hi"] + direction) % len(HEURISTICS)
    player.heuristic = HEURISTICS[state["hi"]]
    state["status"] = f"Heuristic Player A*: {player.heuristic}"


def cycle_heuristic_npc(npc, state, direction=1):
    """Mengganti heuristic NPC secara circular (cycle).

    Args:
        npc: Objek NPC
        state: Dict mutable berisi state game
        direction: 1 untuk maju, -1 untuk mundur
    """
    state["hi"] = (state["hi"] + direction) % len(HEURISTICS)
    npc.set_heuristic(HEURISTICS[state["hi"]])
    state["status"] = f"Algoritma NPC: {npc.heuristic}"


def handle_mouse_click(event, game_map, viewport, player, state):
    """Menangani mouse click untuk set target A* player.

    Konversi posisi mouse ke grid, lalu hitung jalur A* ke target.

    Args:
        event: pygame.MOUSEBUTTONDOWN event
        game_map: Objek GameMap
        viewport: Objek Viewport
        player: Objek Player
        state: Dict mutable berisi state game
    """
    cell = game_map.screen_to_grid(event.pos, viewport)
    if cell:
        r, c = cell
        if player.set_target(r, c, game_map):
            state["status"] = f"Target Player A*: ({c},{r})"
        else:
            state["status"] = "Target tidak bisa dilewati atau tidak ada jalur."


def _apply_settings(settings_menu, player, npc, overlay, state):
    """Apply perubahan settings dari menu ke game objects.

    Args:
        settings_menu: Objek SettingsMenu
        player: Objek Player
        npc: Objek NPC
        overlay: Objek DebugOverlay
        state: Dict mutable berisi state game
    """
    vals = settings_menu.get_values()
    state["show_hud"] = vals.get("show_hud", True)
    debug_on = vals.get("debug_overlay", True)
    overlay.show_visited = debug_on
    overlay.show_path = debug_on
    npc.follow = vals.get("npc_follow", True)
    player.heuristic = vals.get("player_heuristic", "manhattan")
    npc.set_heuristic(vals.get("npc_heuristic", "ucs"))


# ---------------------------------------------------------------------------
# Grid Editor Input
# ---------------------------------------------------------------------------

def handle_edit_input(game_map, viewport, state):
    """Menangani mouse input untuk grid editing.

    Klik kiri = blokir cell (value = 1)
    Klik kanan = buka cell (value = 0)

    Args:
        game_map: Objek GameMap
        viewport: Objek Viewport
        state: Dict mutable berisi state game
    """
    pressed = pygame.mouse.get_pressed()
    if pressed[0] or pressed[2]:
        cell = game_map.screen_to_grid(pygame.mouse.get_pos(), viewport)
        if cell and state["edit_surface"] is not None:
            r, c = cell
            val = 1 if pressed[0] else 0
            if game_map.get_grid()[r][c] != val:
                game_map.set_cell(r, c, val)
                paint_edit_cell(state["edit_surface"], game_map, viewport, r, c)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def draw_edit_mode_info(screen, game_map, viewport, font):
    """Menggambar UI grid editor: hover highlight dan info bar.

    Menampilkan:
    - Highlight kuning pada cell yang di-hover
    - Info bar di bawah dengan koordinat dan status cell

    Args:
        screen: Surface utama
        game_map: Objek GameMap
        viewport: Objek Viewport
        font: pygame Font untuk rendering teks
    """
    hover = game_map.screen_to_grid(pygame.mouse.get_pos(), viewport)
    if not hover:
        return

    r, c = hover
    gv = game_map.get_grid()[r][c]

    # Highlight cell yang di-hover (kuning)
    cell_size = max(2, int(CELL_SIZE * viewport.scale))
    hs = pygame.Rect(0, 0, cell_size, cell_size)
    from utils import game_pos
    hs.center = game_pos(r, c, viewport)
    pygame.draw.rect(screen, (255, 235, 90), hs, 2)

    # Info bar di bawah
    bar_width = max(320, screen.get_width() // 3)
    bar = pygame.Surface((bar_width, 84), pygame.SRCALPHA)
    bar.fill((10, 20, 20, 200))
    screen.blit(bar, (14, screen.get_height() - 96))

    # Teks info
    lines = [
        f"Cell ({r},{c}) grid={gv}  {'BLOKIR' if gv == 1 else 'LEWAT'}",
        "Klik kiri=tutup(1)  |  Klik kanan=buka(0)  |  M=keluar  P=simpan  L=muat",
    ]
    for i, text in enumerate(lines):
        rendered = font.render(text, True, (240, 240, 240))
        screen.blit(rendered, (26, screen.get_height() - 86 + i * 22))


def draw_hud(screen, player, npc, overlay, font, state):
    """Menggambar heads-up display (HUD) dengan kontrol dan info.

    Panel kiri: Daftar kontrol dan status
    Panel kanan: Info player, NPC, dan path

    Args:
        screen: Surface utama
        player: Objek Player
        npc: Objek NPC
        overlay: Objek DebugOverlay
        font: pygame Font
        state: Dict mutable berisi state game
    """
    if not state.get("show_hud", True):
        return
    if not overlay.show_info:
        return

    screen_width = screen.get_width()

    # Panel kiri: Kontrol dan status
    left_width = min(570, screen_width // 2)
    left_size = (left_width, 160)
    if state["_hud_left"] is None or state["_hud_left_size"] != left_size:
        state["_hud_left"] = pygame.Surface((*left_size,), pygame.SRCALPHA)
        state["_hud_left_size"] = left_size
    left = state["_hud_left"]
    left.fill((10, 20, 20, 185))
    screen.blit(left, (12, 12))

    # Daftar kontrol
    lines = [
        "Klik map : Player menuju target dengan A*",
        "WASD / Arrow : Gerak Player",
        "Q / E : Ganti heuristic Player",
        "T / G : Ganti algoritma NPC (UCS/A*)",
        "F : NPC ikuti player ON/OFF",
        "M : Edit Grid    P : Simpan Grid    L : Muat Grid",
        "R : Reset    F11 : Fullscreen    ESC : Keluar",
        state["status"],
    ]
    for i, text in enumerate(lines):
        rendered = font.render(text, True, (240, 240, 240))
        screen.blit(rendered, (22, 20 + i * 22))

    # Panel kanan: Info player dan NPC
    p = player.get_pos()
    n = npc.get_pos()
    t = player.target if player.target else ("-", "-")

    info = [
        f"Player : ({p[1]}, {p[0]})",
        f"NPC    : ({n[1]}, {n[0]})",
        f"Target : ({t[1]}, {t[0]})",
        f"Path   : {len(player.path)} node",
        f"Heuristic Player: {player.heuristic}",
        f"NPC {npc.heuristic.upper()} | {'ikut' if npc.follow else 'diam'} | path {len(npc.path)}",
    ]

    # Gambar panel kanan
    panel_width = 275
    panel_height = 145
    panel_size = (panel_width, panel_height)
    if state["_hud_panel"] is None or state["_hud_panel_size"] != panel_size:
        state["_hud_panel"] = pygame.Surface((*panel_size,), pygame.SRCALPHA)
        state["_hud_panel_size"] = panel_size
    panel = state["_hud_panel"]
    panel.fill((10, 20, 20, 185))
    x = screen_width - panel_width - 12
    screen.blit(panel, (x, 12))

    for i, text in enumerate(info):
        rendered = font.render(text, True, (240, 240, 240))
        screen.blit(rendered, (x + 10, 20 + i * 21))


# ---------------------------------------------------------------------------
# Main Game Loop
# ---------------------------------------------------------------------------

async def main():
    """Main game loop: inisialisasi, run, dan cleanup.

    Alur:
    1. Init pygame, buat window, load assets
    2. Buat game objects (Player, NPC, DebugOverlay)
    3. Loop: handle_events → update → render
    4. Cleanup saat keluar
    """
    pygame.init()

    # Buat window (fullscreen)
    fullscreen = True
    screen = make_window(fullscreen)
    pygame.display.set_caption("Game AI - Player A* + NPC")
    clock = pygame.time.Clock()

    # Load font untuk HUD dan dialogue (fallback ke default jika consolas tidak ada)
    font_name = "consolas" if pygame.font.match_font("consolas") else None
    small = pygame.font.SysFont(font_name, max(14, screen.get_width() // 115))
    dialogue = pygame.font.SysFont(font_name, max(13, screen.get_width() // 125))

    # Inisialisasi game objects
    game_map = GameMap()
    viewport = Viewport(screen.get_size())

    # Load dan scale sprite karakter
    player_sprite = game_map.get_asset("08_karakter/karakter_pemain")
    npc_sprite = game_map.get_asset("08_karakter/karakter_npc")

    # Target height untuk sprite agar konsisten
    TARGET_H = 60  # match current sprite height
    if player_sprite:
        pw, ph = player_sprite.get_size()
        scale_p = TARGET_H / ph
        player_sprite = pygame.transform.smoothscale(
            player_sprite, (int(pw * scale_p), TARGET_H)
        )
    if npc_sprite:
        nw, nh = npc_sprite.get_size()
        scale_n = TARGET_H / nh
        npc_sprite = pygame.transform.smoothscale(
            npc_sprite, (int(nw * scale_n), TARGET_H)
        )

    # Buat player dan NPC
    player = Player(*PLAYER_START, player_sprite)
    player.snap_to_walkable(game_map)

    npc = NPC(*NPC_START, npc_sprite, "jaka")
    npc.snap_to_walkable(game_map)

    # Debug overlay untuk visualisasi pathfinding
    overlay = DebugOverlay()

    # Mutable game state (di-pass ke semua event handler)
    state = {
        "screen": screen,
        "viewport": viewport,
        "fullscreen": fullscreen,
        "edit_mode": False,       # Apakah edit mode aktif
        "edit_surface": None,     # Overlay surface untuk edit mode
        "cellw": CELL_SIZE * viewport.scale,  # Ukuran cell dalam pixel
        "hi": 0,                  # Index heuristic saat ini
        "status": "WASD/Arrow = Player | Klik map = Player A* | ESC = Settings",
        "show_hud": True,         # Apakah HUD ditampilkan
        "settings_menu": SettingsMenu(),
        "_hud_left": None,        # Cached HUD left panel surface
        "_hud_left_size": (0, 0),
        "_hud_panel": None,       # Cached HUD right panel surface
        "_hud_panel_size": (0, 0),
    }

    # ---- Game Loop Utama ----
    running = True
    while running:
        # Hitung delta time untuk frame-rate independent movement
        dt = clock.get_time() / 1000.0

        # Handle semua events
        running = handle_events(game_map, viewport, player, npc, overlay, state)

        # Update referensi dari state (bisa berubah saat resize/fullscreen)
        screen = state["screen"]
        viewport = state["viewport"]
        fullscreen = state["fullscreen"]

        # Handle input grid editor (jika edit mode aktif)
        if state["edit_mode"]:
            handle_edit_input(game_map, viewport, state)

        # Update game objects
        player.handle_input(pygame.key.get_pressed(), game_map, dt)  # Manual movement
        player.update(game_map, dt)  # A* pathfinding movement
        npc.update(game_map, player, dt)  # NPC follow player

        # Apply settings dari menu (hanya saat menu visible)
        if state["settings_menu"].visible:
            _apply_settings(state["settings_menu"], player, npc, overlay, state)
        else:
            # Sync menu dari game state (agar hotkeys tetap berfungsi)
            state["settings_menu"].sync_from_game(player, npc, overlay, state)

        # ---- Rendering ----
        # Bersihkan layar
        screen.fill((12, 14, 18))

        # Gambar map
        game_map.draw(screen, viewport)

        # Gambar edit mode overlay (jika aktif)
        if state["edit_mode"] and state["edit_surface"] is not None:
            screen.blit(state["edit_surface"], viewport.map_rect.topleft)

        # Gambar debug overlay (visited nodes, path, info)
        overlay.draw_scaled(screen, player, small, viewport, hide_visited=state["edit_mode"])

        # Gambar target indicator untuk player
        player.draw_target(screen, viewport)

        # Gambar edit mode hover info (jika aktif)
        if state["edit_mode"]:
            draw_edit_mode_info(screen, game_map, viewport, small)

        # Gambar player dan NPC
        player.draw(screen, viewport)
        npc.draw(screen, viewport)

        # Gambar dialogue NPC (jika dekat dengan player)
        npc.draw_dialogue(screen, viewport, dialogue, player)

        # Gambar HUD
        draw_hud(screen, player, npc, overlay, small, state)

        # Gambar settings menu (di atas semua lainnya)
        state["settings_menu"].draw(screen, small)

        # Update display
        pygame.display.flip()
        await asyncio.sleep(0)  # Required untuk pygbag/web
        clock.tick(FPS)

    # Cleanup
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
