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
import random
import sys

from collections import deque

import pygame

from adversarial_ai import MAX_HP
from battle_system import BattleSystem
from debug_overlay import DebugOverlay
from game.map import CELL_SIZE, COLS, ROWS, GameMap, Viewport
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
PLAYER_START = (10, 5)
NPC_START = (12, 3)

# --- Parameter mode Battle Duel ---
BATTLE_TRIGGER_DIST = 1      # Jarak Manhattan <= 1 ubin memicu duel
ENEMY_SPAWN_DELAY = 1.4      # Detik sebelum musuh muncul (awalnya hanya player)
ENEMY_MIN_SPAWN_DIST = 8     # Jarak minimum spawn musuh dari player (ubin)
ENEMY_MAX_SPAWN_DIST = 34    # Jarak maksimum agar musuh tetap mudah ditemukan


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

def _style_blocked_cell(surface, x, y, w, h):
    """Gambar satu cell blocked dengan gaya menarik (merah + arsir + border).

    Args:
        surface: Surface overlay tujuan
        x, y: Posisi kiri-atas cell (pixel)
        w, h: Ukuran cell (pixel)
    """
    if w <= 0 or h <= 0:
        return

    tmp = pygame.Surface((w, h), pygame.SRCALPHA)
    # Isi merah transparan dengan sudut membulat
    pygame.draw.rect(tmp, (216, 56, 72, 95), (0, 0, w, h), border_radius=3)

    # Arsir diagonal halus sebagai tekstur "obstacle"
    step = max(5, w // 4)
    hatch = (255, 150, 160, 55)
    for i in range(-h, w, step):
        pygame.draw.line(tmp, hatch, (i, h), (i + h, 0), 1)

    # Border terang
    pygame.draw.rect(tmp, (255, 110, 120, 175), (0, 0, w, h),
                     max(1, w // 12), border_radius=3)
    surface.blit(tmp, (x, y))


def build_edit_surface(game_map, viewport):
    """Membangun overlay transparan untuk menampilkan cell yang diblokir.

    Cell yang diblokir (grid value = 1) ditampilkan dengan gaya merah
    transparan (isi + arsir + border) untuk memudahkan visualisasi obstacle.

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
                _style_blocked_cell(surf, x, y, w, h)

    return surf


def paint_edit_cell(surface, game_map, viewport, r, c):
    """Mengecat satu cell pada overlay edit mode.

    Memperbarui tampilan satu cell: merah berarsir jika blocked,
    transparan jika walkable.

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

    # Bersihkan cell lalu gambar ulang sesuai status
    surface.fill((0, 0, 0, 0), (x, y, w, h))
    if game_map.get_grid()[r][c] == 1:
        _style_blocked_cell(surface, x, y, w, h)


# ---------------------------------------------------------------------------
# Widget & Notifikasi (toast)
# ---------------------------------------------------------------------------

def _draw_chip(screen, x, y, label, color, font):
    """Gambar chip/pill kecil berlabel dengan border berwarna.

    Args:
        screen: Surface utama
        x, y: Posisi kiri-atas chip
        label: Teks chip
        color: Warna aksen (R, G, B)
        font: pygame Font

    Returns:
        Lebar chip yang digambar (pixel)
    """
    pad_x, pad_y = 9, 4
    text = font.render(label, True, (238, 243, 250))
    w = text.get_width() + pad_x * 2
    h = text.get_height() + pad_y * 2
    chip = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(chip, (*color, 55), chip.get_rect(), border_radius=8)
    pygame.draw.rect(chip, (*color, 235), chip.get_rect(), 1, border_radius=8)
    screen.blit(chip, (int(x), int(y)))
    screen.blit(text, (int(x) + pad_x, int(y) + pad_y))
    return w


def show_toast(state, text, ok=True, ttl=2.4):
    """Tampilkan notifikasi singkat (toast) di layar.

    Args:
        state: Dict mutable berisi state game
        text: Pesan yang ditampilkan
        ok: True = sukses (hijau), False = gagal (merah)
        ttl: Durasi tampil dalam detik
    """
    state["toast"] = {"text": text, "ok": ok, "ttl": ttl, "max": ttl}


def update_toast(state, dt):
    """Kurangi durasi toast dan hilangkan saat habis.

    Args:
        state: Dict mutable berisi state game
        dt: Delta time dalam detik
    """
    toast = state.get("toast")
    if toast is not None:
        toast["ttl"] -= dt
        if toast["ttl"] <= 0:
            state["toast"] = None


def draw_toast(screen, font, state):
    """Gambar toast notifikasi di bagian tengah atas layar.

    Args:
        screen: Surface utama
        font: pygame Font
        state: Dict mutable berisi state game
    """
    toast = state.get("toast")
    if toast is None:
        return

    alpha = max(0.0, min(1.0, toast["ttl"] / 0.5))
    ok = toast["ok"]
    accent = (96, 224, 140) if ok else (240, 96, 96)
    icon = "✓" if ok else "!"

    text = font.render(toast["text"], True, (240, 245, 252))
    pad_x, pad_y = 14, 9
    box_w = text.get_width() + pad_x * 2 + 26
    box_h = text.get_height() + pad_y * 2
    box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    pygame.draw.rect(box, (14, 20, 30, 232), box.get_rect(), border_radius=12)
    pygame.draw.rect(box, (*accent, 235), box.get_rect(), 2, border_radius=12)
    # Lingkaran ikon
    pygame.draw.circle(box, (*accent, 235), (pad_x + 8, box_h // 2), 11)
    icon_surf = font.render(icon, True, (16, 22, 30))
    box.blit(icon_surf, (pad_x + 8 - icon_surf.get_width() // 2,
                         box_h // 2 - icon_surf.get_height() // 2))
    box.blit(text, (pad_x + 26, pad_y))

    box.set_alpha(int(255 * alpha))

    base_y = 96 if state.get("edit_mode") else 24
    y = base_y - int((1.0 - alpha) * 8)
    screen.blit(box, ((screen.get_width() - box_w) // 2, y))


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

    # Saat Battle Mode, semua input ditangani oleh BattleSystem
    if state.get("mode") == "BATTLE" and state.get("battle") is not None:
        battle = state["battle"]
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.VIDEORESIZE and not state["fullscreen"]:
                handle_resize(event, game_map, state)
                continue
            battle.handle_event(event)
        return True

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
                npc.follow = False
                state["mode"] = "OVERWORLD"
                state["battle"] = None
                state["enemy_spawned"] = False
                state["spawn_timer"] = ENEMY_SPAWN_DELAY
                state["player_hp"] = MAX_HP
                state["status"] = "Player dan musuh di-reset."
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
            # Tombol pada info panel debug (✕ hide / ▶ restore) diprioritaskan
            if not overlay.handle_click(event.pos) and not state["edit_mode"]:
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
        try:
            game_map.save_grid_override()
            show_toast(state, "Grid berhasil disimpan ke grid_override.txt", ok=True)
            state["status"] = "Grid disimpan ke grid_override.txt"
        except Exception:
            show_toast(state, "Gagal menyimpan grid_override.txt", ok=False)
            state["status"] = "Gagal menyimpan grid_override.txt"

    elif key == pygame.K_l:
        ok = game_map.load_grid_override()
        if state["edit_mode"]:
            state["edit_surface"] = build_edit_surface(game_map, state["viewport"])
        if ok:
            show_toast(state, "Grid berhasil dimuat dari grid_override.txt", ok=True)
            state["status"] = "Grid dimuat dari grid_override.txt"
        else:
            show_toast(state, "Gagal memuat: file tidak ada / format salah", ok=False)
            state["status"] = "Gagal memuat grid_override.txt"

    elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
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
        npc.follow = False
        state["mode"] = "OVERWORLD"
        state["battle"] = None
        state["enemy_spawned"] = False
        state["spawn_timer"] = ENEMY_SPAWN_DELAY
        state["player_hp"] = MAX_HP
        state["status"] = "Player dan musuh di-reset. Musuh akan muncul lagi."

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
    """Menggambar UI grid editor yang menarik.

    Menampilkan:
    - Banner "MODE EDIT GRID" di atas dengan chip kontrol
    - Crosshair (sudut siku) pada cell yang di-hover
    - Bottom bar berisi koordinat, status cell, dan chip tombol

    Args:
        screen: Surface utama
        game_map: Objek GameMap
        viewport: Objek Viewport
        font: pygame Font untuk rendering teks
    """
    from game.map.utils import game_pos

    sw, sh = screen.get_size()
    hover = game_map.screen_to_grid(pygame.mouse.get_pos(), viewport)

    # ---- Crosshair pada cell yang di-hover ----
    if hover:
        r, c = hover
        gv = game_map.get_grid()[r][c]
        blocked = gv == 1
        cell = max(2, int(CELL_SIZE * viewport.scale))
        hx, hy = game_pos(r, c, viewport)
        rect = pygame.Rect(hx - cell // 2, hy - cell // 2, cell, cell)
        col = (255, 120, 130) if blocked else (120, 240, 150)

        # Highlight tipis di dalam cell
        glow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glow, (*col, 45), glow.get_rect(), border_radius=3)
        screen.blit(glow, rect.topleft)

        # Empat sudut siku (bracket)
        seg = max(5, cell // 3)
        thick = max(2, cell // 10)
        corners = [
            (rect.left, rect.top, 1, 1),
            (rect.right - 1, rect.top, -1, 1),
            (rect.left, rect.bottom - 1, 1, -1),
            (rect.right - 1, rect.bottom - 1, -1, -1),
        ]
        for cx, cy, dx, dy in corners:
            pygame.draw.line(screen, col, (cx, cy), (cx + dx * seg, cy), thick)
            pygame.draw.line(screen, col, (cx, cy), (cx, cy + dy * seg), thick)

    # ---- Banner atas ----
    title = font.render("MODE EDIT GRID", True, (235, 245, 255))
    chip_defs = [
        ("Klik kiri: BLOKIR", (240, 96, 96)),
        ("Klik kanan: BUKA", (96, 208, 240)),
        ("P: Simpan", (120, 220, 140)),
        ("L: Muat", (200, 160, 250)),
        ("M: Keluar", (230, 190, 90)),
    ]
    chip_w = [font.size(label)[0] + 18 for label, _ in chip_defs]
    chips_total = sum(chip_w) + 8 * (len(chip_defs) - 1)

    banner_h = 62
    banner_w = min(sw - 20, 16 + title.get_width() + 24 + chips_total + 16)
    banner = pygame.Surface((banner_w, banner_h), pygame.SRCALPHA)
    pygame.draw.rect(banner, (14, 20, 30, 224), banner.get_rect(), border_radius=14)
    pygame.draw.rect(banner, (240, 190, 90, 235), banner.get_rect(), 2, border_radius=14)
    banner.blit(title, (16, banner_h // 2 - title.get_height() // 2))

    # Chip kontrol (di kanan judul)
    chip_x = 16 + title.get_width() + 24
    chip_y = banner_h // 2 - 13
    for label, color in chip_defs:
        chip_x += _draw_chip(banner, chip_x, chip_y, label, color, font) + 8

    screen.blit(banner, ((sw - banner_w) // 2, 14))

    # ---- Bottom bar ----
    chip_left = "Klik kiri = blokir (1)"
    chip_right = "Klik kanan = buka (0)"
    chips_row_w = font.size(chip_left)[0] + 18 + 8 + font.size(chip_right)[0] + 18
    bar_w = max(360, sw // 3, chips_row_w + 28)
    bar_h = 76
    bar_x, bar_y = 14, sh - bar_h - 14
    bar = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
    pygame.draw.rect(bar, (10, 16, 24, 210), bar.get_rect(), border_radius=12)
    pygame.draw.rect(bar, (70, 86, 110, 220), bar.get_rect(), 1, border_radius=12)

    if hover:
        r, c = hover
        gv = game_map.get_grid()[r][c]
        blocked = gv == 1
        state_color = (255, 130, 140) if blocked else (130, 240, 165)
        info = font.render(f"Cell ({c}, {r})", True, (235, 240, 250))
        status = font.render("BLOKIR" if blocked else "LEWAT", True, state_color)
        bar.blit(info, (14, 10))
        swatch_x = 14 + info.get_width() + 14
        bar.blit(status, (swatch_x, 10))
        pygame.draw.rect(bar, state_color, (swatch_x + status.get_width() + 8, 12, 14, 14),
                         border_radius=3)
    else:
        hint = font.render("Arahkan kursor ke cell untuk melihat koordinat", True, (170, 180, 200))
        bar.blit(hint, (14, 10))

    w1 = _draw_chip(bar, 14, 36, chip_left, (240, 96, 96), font)
    _draw_chip(bar, 14 + w1 + 8, 36, chip_right, (96, 208, 240), font)

    screen.blit(bar, (bar_x, bar_y))


def draw_hud(screen, player, npc, overlay, font, state):
    """Menggambar heads-up display (HUD) dengan info player/NPC.

    Panel kanan: Info player, NPC, dan path
    (Info panel utama dihandle oleh DebugOverlay)

    Args:
        screen: Surface utama
        player: Objek Player
        npc: Objek NPC
        overlay: Objek DebugOverlay
        font: pygame Font
        state: Dict mutable berisi state game
    """
    return


# ---------------------------------------------------------------------------
# Battle Duel Integration (Overworld <-> Battle Mode)
# ---------------------------------------------------------------------------

def reachable_cells(game_map, start):
    """Himpunan cell walkable yang dapat dicapai dari `start` via BFS.

    Dipakai agar musuh hanya muncul di tempat yang benar-benar bisa dihampiri
    player (tidak terjebak di kantong walkable terisolasi).

    Args:
        game_map: Objek GameMap
        start: Tuple (row, col) posisi awal

    Returns:
        Set berisi tuple (row, col) yang reachable (termasuk start)
    """
    grid = game_map.get_grid()
    seen = {start}
    queue = deque([start])
    while queue:
        r, c = queue.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in seen and grid[nr][nc] == 0:
                seen.add((nr, nc))
                queue.append((nr, nc))
    return seen


def random_spawn_cell(game_map, player, min_dist=ENEMY_MIN_SPAWN_DIST, max_dist=ENEMY_MAX_SPAWN_DIST):
    """Pilih cell walkable acak yang terlihat di map dan dapat dilewati player.

    Kriteria:
    - Walkable (grid == 0) dan reachable dari posisi player (BFS).
    - Jarak Manhattan dalam rentang [min_dist, max_dist] dari player.

    Args:
        game_map: Objek GameMap
        player: Objek Player
        min_dist: Jarak minimum dari player
        max_dist: Jarak maksimum dari player

    Returns:
        Tuple (row, col) atau None jika tidak ada kandidat
    """
    reachable = reachable_cells(game_map, (player.row, player.col))
    bucket = [
        (r, c)
        for (r, c) in reachable
        if min_dist <= abs(r - player.row) + abs(c - player.col) <= max_dist
    ]
    if not bucket:
        bucket = [cell for cell in reachable if cell != (player.row, player.col)]
    if not bucket:
        return None
    return random.choice(bucket)


def spawn_enemy(game_map, player, npc, state, announce=True):
    """Munculkan musuh di lokasi walkable acak yang jauh namun dapat dihampiri.

    Args:
        game_map: Objek GameMap
        player: Objek Player (titik jauhi)
        npc: Objek NPC yang akan dipindahkan
        state: Dict mutable state game
        announce: Tampilkan toast saat musuh muncul
    """
    cell = random_spawn_cell(game_map, player)
    if cell is None:
        cell = (npc.row, npc.col)

    npc.row, npc.col = cell
    npc.start_pos = cell
    npc.smooth_r, npc.smooth_c = float(cell[0]), float(cell[1])
    npc.path = []
    npc.path_index = 0
    npc.recompute_timer = 0.0
    npc.follow = False  # Musuh diam di tempat; player yang menghampiri
    npc.snap_to_walkable(game_map)

    state["enemy_spawned"] = True
    if announce:
        show_toast(state, "Musuh muncul! Dekati dia untuk memulai duel.", ok=False)
        state["status"] = "Musuh muncul! Dekati untuk memulai duel."


def build_battle_background(game_map, cell, size=(720, 460)):
    """Ambil snapshot terrain di sekitar lokasi duel untuk latar bertema map.

    Memotong region dari gambar map overworld di sekitar cell pertemuan, lalu
    dipakai BattleSystem sebagai background agar duel terasa berada di tempat
    yang sama dengan lokasi overworld.

    Args:
        game_map: Objek GameMap (punya atribut .background)
        cell: Tuple (row, col) pusat pertemuan
        size: Ukuran region yang diambil (world pixel)

    Returns:
        pygame.Surface snapshot terrain, atau None jika background tak tersedia
    """
    bg = getattr(game_map, "background", None)
    if bg is None:
        return None
    bw, bh = bg.get_size()
    w = min(size[0], bw)
    h = min(size[1], bh)
    cx = int((cell[1] + 0.5) * CELL_SIZE)
    cy = int((cell[0] + 0.5) * CELL_SIZE)
    x = max(0, min(bw - w, cx - w // 2))
    y = max(0, min(bh - h, cy - h // 2))
    region = pygame.Surface((w, h))
    region.blit(bg, (0, 0), pygame.Rect(x, y, w, h))
    return region


def start_battle(state, player, npc, game_map):
    """Inisialisasi BattleSystem dan pindah ke BATTLE_MODE.

    Args:
        state: Dict mutable state game
        player: Objek Player
        npc: Objek NPC
        game_map: Objek GameMap (untuk latar bertema lokasi)
    """
    mid = ((player.row + npc.row) // 2, (player.col + npc.col) // 2)
    # Latar duel: pakai artwork map_battle.png; fallback ke snapshot terrain map
    battle_bg = game_map.get_asset("map_battle") or build_battle_background(game_map, mid)
    state["battle"] = BattleSystem(
        player_sprite=player.sprite,
        npc_sprite=npc.sprite,
        player_hp=state.get("player_hp", MAX_HP),
        player_name="Player",
        npc_name=npc.name,
        background=battle_bg,
    )
    state["mode"] = "BATTLE"
    state["edit_mode"] = False
    npc.follow = False
    npc.path = []
    state["status"] = "BATTLE MODE - pilih aksi (1-4), D untuk debug overlay"


def exit_battle(state, player, npc, game_map):
    """Kembali dari BATTLE_MODE ke OVERWORLD dan respawn musuh baru.

    Args:
        state: Dict mutable state game
        player: Objek Player
        npc: Objek NPC
        game_map: Objek GameMap
    """
    battle = state.get("battle")
    if battle is not None:
        hp = battle.state.player_hp
        winner = battle.winner
        if winner == "player":
            state["wins"] = state.get("wins", 0) + 1
            state["player_hp"] = max(1, hp)
            show_toast(state, "Kamu menang! Musuh mundur.", ok=True)
        elif winner == "npc":
            state["losses"] = state.get("losses", 0) + 1
            state["player_hp"] = MAX_HP
            show_toast(state, "Kamu kalah. HP dipulihkan penuh.", ok=False)
        else:
            state["player_hp"] = MAX_HP if hp <= 0 else hp
            show_toast(state, "Duel berakhir seri.", ok=True)

    state["battle"] = None
    state["mode"] = "OVERWORLD"
    state["edit_mode"] = False

    # Musuh baru muncul di lokasi acak lain agar permainan berlanjut
    spawn_enemy(game_map, player, npc, state, announce=False)
    state["status"] = "Kembali ke overworld. Cari musuh berikutnya."


def update_overworld_enemy(game_map, player, npc, state, dt):
    """Kelola spawn musuh bertahap dan transisi ke Battle Mode.

    Alur:
    1. Selama musuh belum muncul, hitung mundur spawn timer (hanya player tampil).
    2. Setelah muncul, cek jarak Manhattan player-musuh; jika <= radius interaksi,
       mulai duel dan pause update pergerakan overworld.

    Args:
        game_map: Objek GameMap
        player: Objek Player
        npc: Objek NPC
        state: Dict mutable state game
        dt: Delta time (detik)

    Returns:
        True jika duel baru saja dimulai
    """
    # Fase spawn: awalnya hanya player yang tampil di map
    if not state["enemy_spawned"]:
        state["spawn_timer"] -= dt
        if state["spawn_timer"] <= 0:
            spawn_enemy(game_map, player, npc, state)
        return False

    if state["mode"] != "OVERWORLD":
        return False
    if state["settings_menu"].visible or state["edit_mode"]:
        return False

    dist = abs(player.row - npc.row) + abs(player.col - npc.col)
    if dist <= BATTLE_TRIGGER_DIST:
        start_battle(state, player, npc, game_map)
        return True
    return False


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
    npc.follow = False  # Musuh menunggu sampai muncul di lokasi random

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
        "settings_menu": SettingsMenu(),
        "toast": None,            # Notifikasi singkat (simpan/muat grid, dll)
        # --- Battle Duel state ---
        "mode": "OVERWORLD",      # "OVERWORLD" atau "BATTLE"
        "battle": None,           # Instance BattleSystem saat BATTLE_MODE
        "enemy_spawned": False,   # Musuh belum tampil di awal (hanya player)
        "spawn_timer": ENEMY_SPAWN_DELAY,
        "player_hp": MAX_HP,      # HP player dibawa antar duel
        "wins": 0,
        "losses": 0,
    }

    # ---- Game Loop Utama ----
    running = True
    while running:
        # Hitung delta time untuk frame-rate independent movement
        dt = clock.get_time() / 1000.0

        # Handle semua events (battle punya jalur input sendiri)
        running = handle_events(game_map, viewport, player, npc, overlay, state)

        # Update referensi dari state (bisa berubah saat resize/fullscreen)
        screen = state["screen"]
        viewport = state["viewport"]
        fullscreen = state["fullscreen"]

        # Update durasi notifikasi toast
        update_toast(state, dt)

        # =================================================================
        # BATTLE MODE
        # =================================================================
        if state["mode"] == "BATTLE" and state["battle"] is not None:
            battle = state["battle"]
            battle.update(dt)

            screen.fill((8, 10, 16))
            battle.draw(screen, small)

            if battle.finished:
                exit_battle(state, player, npc, game_map)

            pygame.display.flip()
            await asyncio.sleep(0)  # Required untuk pygbag/web
            clock.tick(FPS)
            continue

        # =================================================================
        # OVERWORLD
        # =================================================================
        # Handle input grid editor (jika edit mode aktif)
        if state["edit_mode"]:
            handle_edit_input(game_map, viewport, state)

        # Update player (manual + A* pathfinding)
        player.handle_input(pygame.key.get_pressed(), game_map, dt)
        player.update(game_map, dt)

        # Spawn musuh bertahap + cek trigger duel (pause overworld saat battle)
        update_overworld_enemy(game_map, player, npc, state, dt)

        # NPC hanya bergerak setelah muncul dan tidak saat mode battle
        if state["enemy_spawned"] and state["mode"] == "OVERWORLD":
            npc.update(game_map, player, dt)

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
        overlay.draw_scaled(
            screen, player, small, viewport,
            hide_visited=state["edit_mode"],
            status=state.get("status", ""),
        )

        # Gambar target indicator untuk player
        player.draw_target(screen, viewport)

        # Gambar edit mode hover info (jika aktif)
        if state["edit_mode"]:
            draw_edit_mode_info(screen, game_map, viewport, small)

        # Gambar player dan musuh (musuh hanya muncul setelah spawn)
        player.draw(screen, viewport)
        if state["enemy_spawned"]:
            npc.draw(screen, viewport)

            # Gambar dialogue NPC (jika dekat dengan player)
            npc.draw_dialogue(screen, viewport, dialogue, player)

        # Gambar HUD
        draw_hud(screen, player, npc, overlay, small, state)

        # Gambar settings menu (di atas semua lainnya)
        state["settings_menu"].draw(screen, small)

        # Gambar notifikasi toast (paling atas)
        draw_toast(screen, small, state)

        # Update display
        pygame.display.flip()
        await asyncio.sleep(0)  # Required untuk pygbag/web
        clock.tick(FPS)

    # Cleanup
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
