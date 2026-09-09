"""
Settings menu with pixel-art brown theme.
Opens with the ESC key and provides a clean in-game settings overlay.
"""
import pygame

# ---------------------------------------------------------------------------
# Color palette (brown pixel theme)
# ---------------------------------------------------------------------------
BG_DARK = (40, 26, 13)
BG_MID = (62, 40, 20)
BG_LIGHT = (85, 55, 28)
BORDER_OUTER = (30, 18, 8)
BORDER_INNER = (110, 72, 36)
TEXT_NORMAL = (220, 195, 160)
TEXT_DIM = (150, 120, 85)
TEXT_HIGHLIGHT = (255, 230, 170)
ACCENT = (180, 100, 30)
ACCENT_HOVER = (210, 130, 50)
TOGGLE_ON = (120, 180, 70)
TOGGLE_OFF = (160, 60, 40)
DIVIDER = (90, 58, 30)


def _draw_pixel_border(surface, rect):
    """Draw a pixel-art style double border."""
    outer = rect.inflate(6, 6)
    pygame.draw.rect(surface, BORDER_OUTER, outer, border_radius=2)
    pygame.draw.rect(surface, BORDER_INNER, rect, border_radius=2)
    inner = rect.inflate(-2, -2)
    pygame.draw.rect(surface, BG_MID, inner, border_radius=1)


def _draw_checkbox(surface, x, y, checked, size=14):
    """Draw a pixel-art checkbox."""
    box = pygame.Rect(x, y, size, size)
    pygame.draw.rect(surface, BORDER_OUTER, box, border_radius=1)
    inner = box.inflate(-4, -4)
    color = TOGGLE_ON if checked else BG_LIGHT
    pygame.draw.rect(surface, color, inner, border_radius=1)
    if checked:
        pygame.draw.line(
            surface, (255, 255, 255),
            (inner.x + 2, inner.centery),
            (inner.centerx - 1, inner.bottom - 3), 2,
        )
        pygame.draw.line(
            surface, (255, 255, 255),
            (inner.centerx, inner.bottom - 3),
            (inner.right - 2, inner.y + 2), 2,
        )


class SettingsMenu:
    """A pixel-art brown themed settings overlay."""

    def __init__(self):
        self.visible = False
        self.selected = 0
        self.hover_row = -1
        self.items = [
            {"type": "toggle", "label": "Tampilkan HUD", "key": "show_hud", "default": True},
            {"type": "toggle", "label": "NPC Ikuti Player", "key": "npc_follow", "default": True},
            {"type": "toggle", "label": "Debug Overlay", "key": "debug_overlay", "default": True},
            {"type": "selector", "label": "Heuristic Player", "key": "player_heuristic",
             "options": ["manhattan", "euclidean", "chebyshev", "octile", "ucs"], "index": 0},
            {"type": "selector", "label": "Algoritma NPC", "key": "npc_heuristic",
             "options": ["ucs", "manhattan", "euclidean", "chebyshev", "octile"], "index": 0},
            {"type": "action", "label": "Reset Posisi", "key": "reset"},
            {"type": "action", "label": "Simpan Grid", "key": "save_grid"},
            {"type": "action", "label": "Muat Grid", "key": "load_grid"},
            {"type": "action", "label": "Fullscreen", "key": "fullscreen"},
            {"type": "danger", "label": "Keluar Game", "key": "quit"},
        ]

    def toggle(self):
        """Show or hide the menu."""
        self.visible = not self.visible

    def get_values(self):
        """Return current setting values as a dict."""
        out = {}
        for item in self.items:
            if item["type"] == "toggle":
                out[item["key"]] = item.get("value", item["default"])
            elif item["type"] == "selector":
                out[item["key"]] = item["options"][item["index"]]
        return out

    def sync_from_game(self, player, npc, overlay, state):
        """Update menu item values from the current game state."""
        for item in self.items:
            key = item["key"]
            if item["type"] == "toggle":
                if key == "show_hud":
                    item["value"] = state.get("show_hud", True)
                elif key == "npc_follow":
                    item["value"] = npc.follow
                elif key == "debug_overlay":
                    item["value"] = overlay.show_visited
            elif item["type"] == "selector":
                if key == "player_heuristic" and player.heuristic in item["options"]:
                    item["index"] = item["options"].index(player.heuristic)
                elif key == "npc_heuristic" and npc.heuristic in item["options"]:
                    item["index"] = item["options"].index(npc.heuristic)

    def handle_event(self, event):
        """Handle input events. Returns True if an action was triggered."""
        if not self.visible:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.visible = False
                return False
            elif event.key in (pygame.K_w, pygame.K_UP):
                self.selected = max(0, self.selected - 1)
            elif event.key in (pygame.K_s, pygame.K_DOWN):
                self.selected = min(len(self.items) - 1, self.selected + 1)
            elif event.key in (pygame.K_a, pygame.K_LEFT):
                self._decrement(self.items[self.selected])
            elif event.key in (pygame.K_d, pygame.K_RIGHT):
                self._increment(self.items[self.selected])
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                item = self.items[self.selected]
                if item["type"] == "toggle":
                    item["value"] = not item.get("value", item["default"])
                elif item["type"] in ("action", "danger"):
                    return item["key"]
            return True

        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_hover(event)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_mouse_click(event)

        return False

    def _increment(self, item):
        if item["type"] == "selector":
            item["index"] = (item["index"] + 1) % len(item["options"])
        elif item["type"] == "toggle":
            item["value"] = not item.get("value", item["default"])

    def _decrement(self, item):
        if item["type"] == "selector":
            item["index"] = (item["index"] - 1) % len(item["options"])
        elif item["type"] == "toggle":
            item["value"] = not item.get("value", item["default"])

    def _menu_rect(self):
        sw, sh = pygame.display.get_surface().get_size()
        menu_w = min(420, sw - 80)
        menu_h = min(520, sh - 80)
        return pygame.Rect((sw - menu_w) // 2, (sh - menu_h) // 2, menu_w, menu_h)

    def _row_rect(self, i):
        menu = self._menu_rect()
        item_h = 42
        start_y = menu.y + 65
        return pygame.Rect(menu.x + 20, start_y + i * item_h, menu.width - 40, item_h)

    def _handle_mouse_hover(self, event):
        self.hover_row = -1
        for i in range(len(self.items)):
            if self._row_rect(i).collidepoint(event.pos):
                self.hover_row = i
                break

    def _handle_mouse_click(self, event):
        menu = self._menu_rect()
        close_rect = pygame.Rect(menu.right - 36, menu.y + 10, 26, 26)
        if close_rect.collidepoint(event.pos):
            self.visible = False
            return False

        for i, item in enumerate(self.items):
            if not self._row_rect(i).collidepoint(event.pos):
                continue
            self.selected = i
            if item["type"] == "toggle":
                item["value"] = not item.get("value", item["default"])
                return True
            elif item["type"] == "selector":
                x = self._selector_click(event.pos, item)
                if x:
                    item["index"] = (item["index"] - 1 + len(item["options"])) % len(item["options"]) if x == -1 else (item["index"] + 1) % len(item["options"])
                return True
            elif item["type"] in ("action", "danger"):
                return item["key"]
        return True

    def _selector_click(self, pos, item):
        """Determine which arrow of a selector was clicked."""
        menu = self._menu_rect()
        font = pygame.font.SysFont("consolas", 16)
        lbl = font.render(item["label"], True, TEXT_NORMAL)
        sel_x = menu.x + 30 + lbl.get_width() + 30
        row = self._row_rect(self.items.index(item))
        arrow_l = pygame.Rect(sel_x, row.y + 12, 20, 20)
        arrow_r = pygame.Rect(sel_x + 160, row.y + 12, 20, 20)
        if arrow_l.collidepoint(pos):
            return -1
        if arrow_r.collidepoint(pos):
            return 1
        return 0

    def draw(self, screen, font):
        """Draw the settings menu overlay."""
        if not self.visible:
            return

        sw, sh = screen.get_size()
        menu = self._menu_rect()

        # Dim background
        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        screen.blit(dim, (0, 0))

        # Main panel
        _draw_pixel_border(screen, menu)

        # Header
        header = pygame.Rect(menu.x + 3, menu.y + 3, menu.width - 6, 50)
        pygame.draw.rect(screen, BG_LIGHT, header, border_radius=2)
        title = font.render("PENGATURAN", True, TEXT_HIGHLIGHT)
        screen.blit(title, (menu.centerx - title.get_width() // 2, menu.y + 16))

        # Close button
        close_rect = pygame.Rect(menu.right - 36, menu.y + 10, 26, 26)
        pygame.draw.rect(screen, TOGGLE_OFF, close_rect, border_radius=3)
        cx, cy = close_rect.center
        pygame.draw.line(screen, (255, 255, 255), (cx - 6, cy - 6), (cx + 6, cy + 6), 2)
        pygame.draw.line(screen, (255, 255, 255), (cx + 6, cy - 6), (cx - 6, cy + 6), 2)

        # Divider under header
        pygame.draw.line(screen, DIVIDER, (menu.x + 15, menu.y + 55), (menu.right - 15, menu.y + 55), 1)

        # Menu items
        item_h = 42
        start_y = menu.y + 65

        for i, item in enumerate(self.items):
            iy = start_y + i * item_h
            is_sel = i == self.selected
            is_hover = i == self.hover_row

            if is_sel:
                sel_bg = pygame.Rect(menu.x + 10, iy - 2, menu.width - 20, item_h)
                pygame.draw.rect(screen, (80, 52, 26, 190), sel_bg, border_radius=3)
                pygame.draw.rect(screen, ACCENT, (menu.x + 12, iy + 8, 4, item_h - 16), border_radius=1)

            lbl_x = menu.x + 30
            lbl_color = TEXT_HIGHLIGHT if is_sel else (TEXT_NORMAL if not is_hover else TEXT_HIGHLIGHT)
            lbl = font.render(item["label"], True, lbl_color)

            if item["type"] in ("action", "danger"):
                # Full-row button
                btn = pygame.Rect(lbl_x - 12, iy + 6, menu.width - 36, item_h - 12)
                color = TOGGLE_OFF if item["type"] == "danger" else (ACCENT_HOVER if is_sel else ACCENT)
                pygame.draw.rect(screen, color, btn, border_radius=3)
                screen.blit(lbl, (btn.centerx - lbl.get_width() // 2, btn.centery - lbl.get_height() // 2))
                continue

            screen.blit(lbl, (lbl_x, iy + 12))

            if item["type"] == "toggle":
                checked = item.get("value", item["default"])
                _draw_checkbox(screen, lbl_x + lbl.get_width() + 20, iy + 13, checked, 16)

            elif item["type"] == "selector":
                val = item["options"][item["index"]]
                sel_x = lbl_x + lbl.get_width() + 30
                al = font.render("<", True, ACCENT_HOVER if is_sel else ACCENT)
                vt = font.render(str(val), True, TEXT_HIGHLIGHT if is_sel else TEXT_NORMAL)
                ar = font.render(">", True, ACCENT_HOVER if is_sel else ACCENT)
                screen.blit(al, (sel_x, iy + 12))
                screen.blit(vt, (sel_x + al.get_width() + 8, iy + 12))
                screen.blit(ar, (sel_x + al.get_width() + 8 + vt.get_width() + 8, iy + 12))

        # Footer
        hint_y = start_y + len(self.items) * item_h + 8
        pygame.draw.line(screen, DIVIDER, (menu.x + 15, hint_y), (menu.right - 15, hint_y), 1)
        hint = font.render("W/S pilih | A/D ubah | ENTER ok | ESC tutup", True, TEXT_DIM)
        screen.blit(hint, (menu.centerx - hint.get_width() // 2, hint_y + 8))