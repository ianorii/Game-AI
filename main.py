"""
Game AI 2D - Main entry point.

A 2D RPG-style map with:
- Player controlled by WASD/Arrow keys or mouse click (A* pathfinding)
- NPC that follows the player using A* with configurable heuristics
- Grid editor for modifying the collision map
- Debug overlay for visualizing pathfinding
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
# Constants
# ---------------------------------------------------------------------------

FPS = 120
HEURISTICS = ["manhattan", "euclidean", "chebyshev", "octile", "ucs"]

# Default positions
PLAYER_START = (16, 9)
NPC_START = (20, 5)


# ---------------------------------------------------------------------------
# Window management
# ---------------------------------------------------------------------------

def make_window(fullscreen=True):
    """Create the game window (fullscreen or resizable)."""
    info = pygame.display.Info()
    if fullscreen:
        return pygame.display.set_mode(
            (info.current_w, info.current_h), pygame.FULLSCREEN
        )
    return pygame.display.set_mode((1280, 720), pygame.RESIZABLE)


# ---------------------------------------------------------------------------
# Grid editor helpers
# ---------------------------------------------------------------------------

def build_edit_surface(game_map, viewport):
    """Build a transparent overlay surface showing blocked cells in red."""
    surf = pygame.Surface(viewport.map_rect.size, pygame.SRCALPHA)
    grid = game_map.get_grid()
    cellw = CELL_SIZE * viewport.scale

    for r in range(ROWS):
        for c in range(COLS):
            if grid[r][c] == 1:
                x = int(c * cellw)
                y = int(r * cellw)
                w = int((c + 1) * cellw) - x
                h = int((r + 1) * cellw) - y
                surf.fill((230, 45, 55, 80), (x, y, w, h))

    return surf


def paint_edit_cell(surface, game_map, viewport, r, c):
    """Paint a single cell on the edit overlay (red for blocked, clear for walkable)."""
    if not game_map.is_valid(r, c):
        return

    cellw = CELL_SIZE * viewport.scale
    x = int(c * cellw)
    y = int(r * cellw)
    w = int((c + 1) * cellw) - x
    h = int((r + 1) * cellw) - y

    if game_map.get_grid()[r][c] == 1:
        surface.fill((230, 45, 55, 80), (x, y, w, h))
    else:
        surface.fill((0, 0, 0, 0), (x, y, w, h))


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------

def handle_events(game_map, viewport, player, npc, overlay, state):
    """Process all pygame events and update game state.

    Returns:
        False if the game should quit, True otherwise.
    """
    settings_menu = state.get("settings_menu")

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False

        # Settings menu gets priority when visible
        if settings_menu and settings_menu.visible:
            action = settings_menu.handle_event(event)
            if action == "reset":
                player.reset()
                npc.reset()
                state["status"] = "Player dan NPC di-reset."
            elif action == "save_grid":
                game_map.save_grid_override()
                state["status"] = "Grid disimpan ke grid_override.txt"
            elif action == "load_grid":
                ok = game_map.load_grid_override()
                if state["edit_mode"]:
                    state["edit_surface"] = build_edit_surface(game_map, state["viewport"])
                state["status"] = "Grid dimuat dari grid_override.txt" if ok else "Gagal memuat grid_override.txt"
            elif action == "fullscreen":
                toggle_fullscreen(game_map, state)
            elif action == "quit":
                return False
            _apply_settings(settings_menu, player, npc, overlay, state)
            continue

        elif event.type == pygame.VIDEORESIZE and not state["fullscreen"]:
            handle_resize(event, game_map, state)

        elif event.type == pygame.KEYDOWN:
            result = handle_key_event(
                event, game_map, player, npc, overlay, state
            )
            if result is False:
                return False

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not state["edit_mode"]:
                handle_mouse_click(event, game_map, viewport, player, state)

    return True


def handle_resize(event, game_map, state):
    """Handle window resize event."""
    state["screen"] = pygame.display.set_mode(event.size, pygame.RESIZABLE)
    state["viewport"] = Viewport(state["screen"].get_size())
    state["cellw"] = CELL_SIZE * state["viewport"].scale
    if state["edit_mode"]:
        state["edit_surface"] = build_edit_surface(game_map, state["viewport"])


def handle_key_event(event, game_map, player, npc, overlay, state):
    """Handle keyboard input. Returns False to quit, None otherwise."""
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
    """Toggle between fullscreen and windowed mode."""
    state["fullscreen"] = not state["fullscreen"]
    state["screen"] = make_window(state["fullscreen"])
    state["viewport"] = Viewport(state["screen"].get_size())
    state["cellw"] = CELL_SIZE * state["viewport"].scale
    if state["edit_mode"]:
        state["edit_surface"] = build_edit_surface(game_map, state["viewport"])


def toggle_edit_mode(game_map, state):
    """Toggle grid edit mode on/off."""
    state["edit_mode"] = not state["edit_mode"]
    if state["edit_mode"]:
        state["edit_surface"] = build_edit_surface(game_map, state["viewport"])
    state["status"] = (
        f"Edit Grid: {'ON (klik kiri=tutup 1, kanan=buka 0)' if state['edit_mode'] else 'OFF'}"
    )


def cycle_heuristic_player(player, state, direction=1):
    """Cycle through heuristics for the player."""
    state["hi"] = (state["hi"] + direction) % len(HEURISTICS)
    player.heuristic = HEURISTICS[state["hi"]]
    state["status"] = f"Heuristic Player A*: {player.heuristic}"


def cycle_heuristic_npc(npc, state, direction=1):
    """Cycle through heuristics for the NPC."""
    state["hi"] = (state["hi"] + direction) % len(HEURISTICS)
    npc.set_heuristic(HEURISTICS[state["hi"]])
    state["status"] = f"Algoritma NPC: {npc.heuristic}"


def handle_mouse_click(event, game_map, viewport, player, state):
    """Handle mouse click to set player A* target."""
    cell = game_map.screen_to_grid(event.pos, viewport)
    if cell:
        r, c = cell
        if player.set_target(r, c, game_map):
            state["status"] = f"Target Player A*: ({c},{r})"
        else:
            state["status"] = "Target tidak bisa dilewati atau tidak ada jalur."


def _apply_settings(settings_menu, player, npc, overlay, state):
    """Apply current settings values from the menu to game objects."""
    vals = settings_menu.get_values()
    state["show_hud"] = vals.get("show_hud", True)
    debug_on = vals.get("debug_overlay", True)
    overlay.show_visited = debug_on
    overlay.show_path = debug_on
    npc.follow = vals.get("npc_follow", True)
    player.heuristic = vals.get("player_heuristic", "manhattan")
    npc.set_heuristic(vals.get("npc_heuristic", "ucs"))


# ---------------------------------------------------------------------------
# Grid editor input
# ---------------------------------------------------------------------------

def handle_edit_input(game_map, viewport, state):
    """Handle mouse input for grid editing (left click = block, right click = unblock)."""
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
    """Draw grid editor UI: hover highlight and info bar."""
    hover = game_map.screen_to_grid(pygame.mouse.get_pos(), viewport)
    if not hover:
        return

    r, c = hover
    gv = game_map.get_grid()[r][c]

    # Hover highlight
    cell_size = max(2, int(CELL_SIZE * viewport.scale))
    hs = pygame.Rect(0, 0, cell_size, cell_size)
    hs.center = (r, c)  # placeholder, will be corrected below
    from utils import game_pos
    hs.center = game_pos(r, c, viewport)
    pygame.draw.rect(screen, (255, 235, 90), hs, 2)

    # Info bar at bottom
    bar_width = max(320, screen.get_width() // 3)
    bar = pygame.Surface((bar_width, 84), pygame.SRCALPHA)
    bar.fill((10, 20, 20, 200))
    screen.blit(bar, (14, screen.get_height() - 96))

    lines = [
        f"Cell ({r},{c}) grid={gv}  {'BLOKIR' if gv == 1 else 'LEWAT'}",
        "Klik kiri=tutup(1)  |  Klik kanan=buka(0)  |  M=keluar  P=simpan  L=muat",
    ]
    for i, text in enumerate(lines):
        rendered = font.render(text, True, (240, 240, 240))
        screen.blit(rendered, (26, screen.get_height() - 86 + i * 22))


def draw_hud(screen, player, npc, overlay, font, state):
    """Draw the heads-up display with controls and status info."""
    if not state.get("show_hud", True):
        return
    if not overlay.show_info:
        return

    screen_width = screen.get_width()

    # Left panel: controls and status
    left_width = min(570, screen_width // 2)
    left = pygame.Surface((left_width, 160), pygame.SRCALPHA)
    left.fill((10, 20, 20, 185))
    screen.blit(left, (12, 12))

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

    # Right panel: player/NPC info
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

    panel_width = 275
    panel_height = 145
    panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
    panel.fill((10, 20, 20, 185))
    x = screen_width - panel_width - 12
    screen.blit(panel, (x, 12))

    for i, text in enumerate(info):
        rendered = font.render(text, True, (240, 240, 240))
        screen.blit(rendered, (x + 10, 20 + i * 21))


# ---------------------------------------------------------------------------
# Main game loop
# ---------------------------------------------------------------------------

async def main():
    """Main game loop: initialize, run, and cleanup."""
    pygame.init()

    # Create window and basic objects
    fullscreen = True
    screen = make_window(fullscreen)
    pygame.display.set_caption("Game AI - Player A* + NPC")
    clock = pygame.time.Clock()

    # Fonts
    small = pygame.font.SysFont("consolas", max(14, screen.get_width() // 115))
    dialogue = pygame.font.SysFont("consolas", max(13, screen.get_width() // 125))

    # Game objects
    game_map = GameMap()
    viewport = Viewport(screen.get_size())

    player_sprite = game_map.get_asset("08_karakter/karakter_pemain")
    npc_sprite = game_map.get_asset("08_karakter/karakter_npc")

    TARGET_H = 60  # match current sprite height (karakter 61x89)
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

    player = Player(*PLAYER_START, player_sprite)
    player.snap_to_walkable(game_map)

    npc = NPC(*NPC_START, npc_sprite, "jaka")
    npc.snap_to_walkable(game_map)

    overlay = DebugOverlay()

    # Mutable game state (passed to event handlers)
    state = {
        "screen": screen,
        "viewport": viewport,
        "fullscreen": fullscreen,
        "edit_mode": False,
        "edit_surface": None,
        "cellw": CELL_SIZE * viewport.scale,
        "hi": 0,
        "status": "WASD/Arrow = Player | Klik map = Player A* | ESC = Settings",
        "show_hud": True,
        "settings_menu": SettingsMenu(),
    }

    # ---- Main loop ----
    running = True
    while running:
        dt = clock.get_time() / 1000.0

        # Handle events
        running = handle_events(game_map, viewport, player, npc, overlay, state)

        # Update state from event handlers
        screen = state["screen"]
        viewport = state["viewport"]
        fullscreen = state["fullscreen"]

        # Grid editor input
        if state["edit_mode"]:
            handle_edit_input(game_map, viewport, state)

        # Update game objects
        player.handle_input(pygame.key.get_pressed(), game_map, dt)
        player.update(game_map, dt)
        npc.update(game_map, player, dt)

        # Apply settings from menu (only while visible so hotkeys keep working)
        if state["settings_menu"].visible:
            _apply_settings(state["settings_menu"], player, npc, overlay, state)
        else:
            state["settings_menu"].sync_from_game(player, npc, overlay, state)

        # ---- Rendering ----
        screen.fill((12, 14, 18))
        game_map.draw(screen, viewport)

        # Edit mode overlay
        if state["edit_mode"] and state["edit_surface"] is not None:
            screen.blit(state["edit_surface"], viewport.map_rect.topleft)

        # Debug overlay and player target
        overlay.draw_scaled(screen, player, small, viewport, hide_visited=state["edit_mode"])
        player.draw_target(screen, viewport)

        # Edit mode hover info
        if state["edit_mode"]:
            draw_edit_mode_info(screen, game_map, viewport, small)

        # Draw entities
        player.draw(screen, viewport)
        npc.draw(screen, viewport)
        npc.draw_dialogue(screen, viewport, dialogue, player)

        # HUD
        draw_hud(screen, player, npc, overlay, small, state)

        # Settings menu on top
        state["settings_menu"].draw(screen, small)

        # Flip and tick
        pygame.display.flip()
        await asyncio.sleep(0)
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
