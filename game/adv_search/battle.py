"""
Battle overlay module - UI untuk pertarungan turn-based.

Modul ini menghandle:
1. Battle overlay dengan dark theme
2. HP bar dengan animasi
3. Action buttons (Attack, Defend, Potion)
4. Battle log
5. Turn indicator
6. Win/Lose screen
"""
import pygame

from .core import GameState, get_npc_action, create_battle_state


# ---------------------------------------------------------------------------
# Color Palette (Dark Battle Theme)
# ---------------------------------------------------------------------------

BG_DARK = (10, 12, 18)
BG_PANEL = (18, 22, 32)
BG_PANEL_LIGHT = (28, 35, 50)

BORDER = (50, 60, 80)
BORDER_LIGHT = (70, 85, 110)

TEXT_WHITE = (230, 235, 245)
TEXT_DIM = (140, 150, 170)
TEXT_HIGHLIGHT = (255, 230, 120)

HP_GREEN = (60, 200, 100)
HP_YELLOW = (230, 200, 50)
HP_RED = (220, 60, 60)
HP_BG = (40, 45, 55)

POTION_PURPLE = (160, 80, 220)
DEFEND_BLUE = (60, 140, 230)
ATTACK_RED = (220, 70, 60)

ACCENT = (80, 140, 220)
ACCENT_HOVER = (100, 160, 240)

WIN_GREEN = (80, 220, 120)
LOSE_RED = (220, 70, 60)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _hp_color(ratio):
    """Return warna HP berdasarkan rasio 0.0 - 1.0."""
    if ratio > 0.5:
        return HP_GREEN
    elif ratio > 0.25:
        return HP_YELLOW
    return HP_RED


def _draw_pixel_border(surface, rect, border_color=BORDER, inner_color=BG_PANEL):
    """Gambar pixel-art double border."""
    outer = rect.inflate(6, 6)
    pygame.draw.rect(surface, border_color, outer, border_radius=3)
    pygame.draw.rect(surface, BORDER_LIGHT, rect, border_radius=2)
    inner = rect.inflate(-4, -4)
    pygame.draw.rect(surface, inner_color, inner, border_radius=2)


def _draw_hp_bar(surface, x, y, width, height, current, maximum, label=""):
    """Gambar HP bar dengan gradient effect.

    Args:
        surface: Surface untuk drawing
        x, y: Posisi kiri atas
        width, height: Ukuran bar
        current: HP saat ini
        maximum: HP maksimum
        label: Teks label (opsional)
    """
    ratio = max(0, current / maximum) if maximum > 0 else 0

    # Background bar
    bg_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, HP_BG, bg_rect, border_radius=3)

    # HP fill
    fill_w = int(width * ratio)
    if fill_w > 0:
        fill_rect = pygame.Rect(x, y, fill_w, height)
        color = _hp_color(ratio)
        pygame.draw.rect(surface, color, fill_rect, border_radius=3)

        # Highlight effect (gradient)
        highlight = pygame.Surface((fill_w, height // 2), pygame.SRCALPHA)
        highlight.fill((255, 255, 255, 30))
        surface.blit(highlight, (x, y))

    # Border
    pygame.draw.rect(surface, BORDER_LIGHT, bg_rect, 1, border_radius=3)

    # HP text
    font = pygame.font.SysFont("consolas", max(12, height - 4))
    hp_text = f"{current}/{maximum}"
    rendered = font.render(hp_text, True, TEXT_WHITE)
    text_x = x + width // 2 - rendered.get_width() // 2
    text_y = y + height // 2 - rendered.get_height() // 2
    surface.blit(rendered, (text_x, text_y))

    # Label
    if label:
        lbl = font.render(label, True, TEXT_DIM)
        surface.blit(lbl, (x, y - lbl.get_height() - 2))


# ---------------------------------------------------------------------------
# Battle Overlay
# ---------------------------------------------------------------------------

class BattleOverlay:
    """Battle UI overlay untuk pertarungan turn-based.

    Attributes:
        state: GameState saat ini
        player: Objek Player
        npc: Objek NPC
        selected_action: Index aksi yang dipilih (0=attack, 1=defend, 2=potion)
        battle_log: List pesan battle
        phase: "select" (pilih aksi), "anim" (animasi), "result" (hasil)
        result_timer: Timer untuk delay hasil
    """

    def __init__(self):
        """Inisialisasi battle overlay."""
        self.state = None
        self.player = None
        self.npc = None
        self.selected_action = 0
        self.battle_log = []
        self.phase = "select"
        self.result_timer = 0.0
        self.winner = None
        self._panel_cache = None
        self._panel_size = (0, 0)

    def start_battle(self, player, npc):
        """Mulai pertarungan baru.

        Args:
            player: Objek Player
            npc: Objek NPC
        """
        self.player = player
        self.npc = npc
        self.state = create_battle_state(player, npc)
        self.selected_action = 0
        self.battle_log = []
        self.phase = "select"
        self.result_timer = 0.0
        self.winner = None

        # Inisialisasi battle stats di player dan NPC
        player.battle_hp = player.battle_max_hp
        npc.battle_hp = npc.battle_max_hp

        self.battle_log.append("Battle started!")
        self.battle_log.append(f"  Player: {player.battle_hp} HP, {player.battle_atk} ATK")
        self.battle_log.append(f"  {npc.name}: {npc.battle_hp} HP, {npc.battle_atk} ATK")

    def handle_event(self, event):
        """Handle input events saat battle aktif.

        Keyboard:
        - Left/Right: Pilih aksi
        - Enter/Space: Konfirmasi aksi
        - 1/2/3: Shortcut aksi (Attack/Defend/Potion)

        Args:
            event: pygame event

        Returns:
            "done" jika battle selesai, None jika belum
        """
        if self.state is None or self.state.finished:
            return None

        if self.phase == "result":
            return None

        if self.phase != "select":
            return None

        if self.state.whose_turn != "player":
            return None

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                actions = self.state.get_legal_actions("player")
                self.selected_action = (self.selected_action - 1) % len(actions)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                actions = self.state.get_legal_actions("player")
                self.selected_action = (self.selected_action + 1) % len(actions)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._execute_player_action()
            elif event.key == pygame.K_1:
                self.selected_action = 0
                self._execute_player_action()
            elif event.key == pygame.K_2:
                self.selected_action = 1
                self._execute_player_action()
            elif event.key == pygame.K_3:
                actions = self.state.get_legal_actions("player")
                if len(actions) > 2:
                    self.selected_action = 2
                    self._execute_player_action()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse_click(event.pos)

        return None

    def _handle_mouse_click(self, pos):
        """Handle mouse click pada action buttons.

        Args:
            pos: Tuple (x, y) posisi click
        """
        if self.state.whose_turn != "player":
            return

        sw, sh = pygame.display.get_surface().get_size()
        actions = self.state.get_legal_actions("player")

        # Hitung posisi buttons
        btn_w = 140
        btn_h = 45
        btn_gap = 20
        total_w = len(actions) * btn_w + (len(actions) - 1) * btn_gap
        start_x = (sw - total_w) // 2
        btn_y = sh // 2 + 80

        for i, action in enumerate(actions):
            bx = start_x + i * (btn_w + btn_gap)
            btn_rect = pygame.Rect(bx, btn_y, btn_w, btn_h)
            if btn_rect.collidepoint(pos):
                self.selected_action = i
                self._execute_player_action()
                return

    def _execute_player_action(self):
        """Eksekusi aksi player dan trigger NPC turn."""
        actions = self.state.get_legal_actions("player")
        if not actions:
            return

        action = actions[self.selected_action]
        result = self.state.apply_action("player", action)

        # Tambah ke battle log
        if action == "attack":
            self.battle_log.append(
                f"Player attacks! -{result['damage']} HP to {self.npc.name}"
            )
        elif action == "defend":
            self.battle_log.append("Player defends!")
        elif action == "potion":
            self.battle_log.append(f"Player uses potion! +{result['heal']} HP")

        # Cek selesai
        if self.state.finished:
            self.winner = self.state.winner
            self.phase = "result"
            self.result_timer = 0.0
            if self.winner == "player":
                self.battle_log.append(f"{self.npc.name} defeated!")
            else:
                self.battle_log.append("You lost!")
            return

        # NPC turn
        self.state.next_turn()
        self._execute_npc_action()

    def _execute_npc_action(self):
        """Eksekusi aksi NPC menggunakan Min-Max."""
        action, score = get_npc_action(self.state)
        result = self.state.apply_action("npc", action)

        # Tambah ke battle log
        if action == "attack":
            self.battle_log.append(
                f"{self.npc.name} attacks! -{result['damage']} HP to Player"
            )
        elif action == "defend":
            self.battle_log.append(f"{self.npc.name} defends!")
        elif action == "potion":
            self.battle_log.append(
                f"{self.npc.name} uses potion! +{result['heal']} HP"
            )

        # Cek selesai
        if self.state.finished:
            self.winner = self.state.winner
            self.phase = "result"
            self.result_timer = 0.0
            if self.winner == "player":
                self.battle_log.append(f"{self.npc.name} defeated!")
            else:
                self.battle_log.append("You lost!")
            return

        # Balik ke player turn
        self.state.next_turn()
        self.phase = "select"
        self.selected_action = 0

    def update(self, dt):
        """Update battle state.

        Args:
            dt: Delta time dalam detik
        """
        if self.phase == "result":
            self.result_timer += dt

    def draw(self, screen, font):
        """Gambar battle overlay ke layar.

        Args:
            screen: Surface utama
            font: pygame Font untuk rendering teks
        """
        if self.state is None:
            return

        sw, sh = screen.get_size()

        # Dim background
        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 200))
        screen.blit(dim, (0, 0))

        # Hitung panel dimensions
        panel_w = min(700, sw - 60)
        panel_h = min(500, sh - 60)
        panel_x = (sw - panel_w) // 2
        panel_y = (sh - panel_h) // 2
        panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        # Main panel
        _draw_pixel_border(screen, panel, BORDER, BG_PANEL)

        # ---- Header: Turn info ----
        header_h = 45
        header = pygame.Rect(panel_x + 3, panel_y + 3, panel_w - 6, header_h)
        pygame.draw.rect(screen, BG_PANEL_LIGHT, header, border_radius=2)

        turn_text = f"Turn {self.state.turn}"
        if self.state.whose_turn == "player":
            turn_text += " - YOUR TURN"
            turn_color = TEXT_HIGHLIGHT
        else:
            turn_text += " - ENEMY TURN"
            turn_color = ATTACK_RED
        rendered = font.render(turn_text, True, turn_color)
        screen.blit(rendered, (panel.centerx - rendered.get_width() // 2, panel_y + 15))

        # ---- Player & NPC Stats ----
        stats_y = panel_y + header_h + 15
        col_w = panel_w // 2 - 20

        # Player panel
        p_x = panel_x + 15
        self._draw_character_stats(
            screen, font, p_x, stats_y, col_w,
            "PLAYER",
            self.state.player_hp, self.state.player_max_hp,
            self.state.player_atk, self.state.player_def,
            self.state.player_potions, self.player.battle_heal,
            is_player=True,
        )

        # NPC panel
        n_x = panel_x + panel_w // 2 + 5
        self._draw_character_stats(
            screen, font, n_x, stats_y, col_w,
            self.npc.name.upper(),
            self.state.npc_hp, self.state.npc_max_hp,
            self.state.npc_atk, self.state.npc_def,
            self.state.npc_potions, self.npc.battle_heal,
            is_player=False,
        )

        # ---- VS text ----
        vs_font = pygame.font.SysFont("consolas", 28, bold=True)
        vs_text = vs_font.render("VS", True, TEXT_HIGHLIGHT)
        vs_x = panel.centerx - vs_text.get_width() // 2
        vs_y = stats_y + 50
        screen.blit(vs_text, (vs_x, vs_y))

        # ---- Action Buttons (hanya saat player turn) ----
        if self.state.whose_turn == "player" and self.phase == "select":
            self._draw_action_buttons(screen, font, panel)

        # ---- Battle Log ----
        log_y = panel_y + panel_h - 130
        log_h = 110
        log_rect = pygame.Rect(panel_x + 15, log_y, panel_w - 30, log_h)
        pygame.draw.rect(screen, (8, 10, 16), log_rect, border_radius=3)
        pygame.draw.rect(screen, BORDER, log_rect, 1, border_radius=3)

        # Log title
        log_title = font.render("BATTLE LOG", True, TEXT_DIM)
        screen.blit(log_title, (log_rect.x + 5, log_y + 3))

        # Log entries (tampilkan 4 terakhir)
        visible_logs = self.battle_log[-4:]
        for i, msg in enumerate(visible_logs):
            entry = font.render(msg, True, TEXT_DIM if i < len(visible_logs) - 1 else TEXT_WHITE)
            screen.blit(entry, (log_rect.x + 10, log_y + 22 + i * 20))

        # ---- Result Screen ----
        if self.phase == "result" and self.result_timer > 0.5:
            self._draw_result(screen, font, panel)

    def _draw_character_stats(self, screen, font, x, y, width, name,
                               hp, max_hp, atk, defense, potions, heal,
                               is_player=True):
        """Gambar stats satu karakter."""
        # Name
        name_color = ACCENT if is_player else ATTACK_RED
        name_surf = font.render(name, True, name_color)
        screen.blit(name_surf, (x, y))

        # HP Bar
        _draw_hp_bar(screen, x, y + 22, width, 20, hp, max_hp, "HP")

        # Stats
        stats = [
            f"DEF: {defense}",
            f"Potion: {potions} (+{heal}HP)",
        ]
        for i, text in enumerate(stats):
            color = TEXT_DIM
            surf = font.render(text, True, color)
            screen.blit(surf, (x, y + 50 + i * 18))

    def _draw_action_buttons(self, screen, font, panel):
        """Gambar action buttons.

        Args:
            screen: Surface utama
            font: pygame Font
            panel: pygame.Rect panel utama
        """
        actions = self.state.get_legal_actions("player")
        btn_w = 140
        btn_h = 45
        btn_gap = 20
        total_w = len(actions) * btn_w + (len(actions) - 1) * btn_gap
        start_x = panel.centerx - total_w // 2
        btn_y = panel.centery + 60

        colors = {
            "attack": (ATTACK_RED, (180, 50, 40)),
            "defend": (DEFEND_BLUE, (40, 100, 180)),
            "potion": (POTION_PURPLE, (120, 50, 170)),
        }
        icons = {
            "attack": "ATK",
            "defend": "DEF",
            "potion": "POT",
        }

        for i, action in enumerate(actions):
            bx = start_x + i * (btn_w + btn_gap)
            btn_rect = pygame.Rect(bx, btn_y, btn_w, btn_h)
            is_selected = i == self.selected_action

            # Button background
            color, hover_color = colors.get(action, (ACCENT, ACCENT_HOVER))
            bg_color = hover_color if is_selected else color
            pygame.draw.rect(screen, bg_color, btn_rect, border_radius=5)

            # Border
            border_color = TEXT_HIGHLIGHT if is_selected else BORDER_LIGHT
            pygame.draw.rect(screen, border_color, btn_rect, 2, border_radius=5)

            # Icon + Label
            icon = icons.get(action, "?")
            label = action.upper()

            icon_surf = font.render(icon, True, TEXT_WHITE)
            label_surf = font.render(label, True, TEXT_WHITE)

            screen.blit(
                icon_surf,
                (btn_rect.centerx - icon_surf.get_width() // 2, btn_y + 5),
            )
            screen.blit(
                label_surf,
                (btn_rect.centerx - label_surf.get_width() // 2, btn_y + 23),
            )

        # Hint
        hint = font.render("← → select | ENTER confirm", True, TEXT_DIM)
        screen.blit(
            hint,
            (panel.centerx - hint.get_width() // 2, btn_y + btn_h + 10),
        )

    def _draw_result(self, screen, font, panel):
        """Gambar win/lose screen.

        Args:
            screen: Surface utama
            font: pygame Font
            panel: pygame.Rect panel utama
        """
        # Overlay transparan
        overlay = pygame.Surface(
            (panel.width - 30, 80), pygame.SRCALPHA
        )
        overlay.fill((10, 12, 18, 220))
        screen.blit(overlay, (panel.x + 15, panel.centery - 40))

        if self.winner == "player":
            text = "VICTORY!"
            color = WIN_GREEN
            sub = "Press ENTER to continue"
        else:
            text = "DEFEATED..."
            color = LOSE_RED
            sub = "Press ENTER to retry"

        # Main text
        big_font = pygame.font.SysFont("consolas", 36, bold=True)
        result_surf = big_font.render(text, True, color)
        screen.blit(
            result_surf,
            (panel.centerx - result_surf.get_width() // 2, panel.centery - 25),
        )

        # Sub text
        sub_surf = font.render(sub, True, TEXT_DIM)
        screen.blit(
            sub_surf,
            (panel.centerx - sub_surf.get_width() // 2, panel.centery + 15),
        )
