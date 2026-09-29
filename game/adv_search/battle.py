"""
Battle overlay module - UI untuk pertarungan turn-based.

Modul ini menghandle:
1. Battle overlay dengan dark theme
2. HP bar dengan animasi
3. Action buttons (Attack, Defend, Potion, Charge)
4. Battle log + statistik pencarian Min-Max AI
5. Turn indicator + delay aksi NPC (supaya pemain sempat membaca log)
6. Hint pemain (tekan H) -> search dari sisi pemain
7. Debug overlay keputusan AI (tekan F3): skor per aksi, peluang menang,
   rincian evaluation function, principal variation, statistik battle
8. Win/Lose screen

Aksi mengikuti ACTIONS di core (attack, defend, potion, charge), jadi
tombol keyboard 1/2/3/4 dan layout tombol selalu disesuaikan dengan
daftar aksi legal saat ini.
"""
import textwrap

import pygame

from .core import (
    ACTIONS,
    ACTION_INFO,
    TIME_BUDGET,
    create_battle_state,
    evaluate_terms,
    get_npc_action,
    get_player_hint,
    win_probability,
)


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
CHARGE_GOLD = (230, 170, 50)

ACCENT = (80, 140, 220)
ACCENT_HOVER = (100, 160, 240)

WIN_GREEN = (80, 220, 120)
LOSE_RED = (220, 70, 60)

# Jeda sebelum aksi NPC dieksekusi (detik) - pemain sempat membaca log
NPC_DELAY = 0.40

# Jumlah entri battle log yang ditampilkan
LOG_VISIBLE = 4

# Panel debug keputusan AI
DEBUG_PANEL_WIDTH = 270
DEBUG_ROW_GAP = 8

# Label aksi pendek (untuk principal variation & statistik)
SHORT_ACTION = {
    "attack": "ATK",
    "defend": "DEF",
    "potion": "POT",
    "charge": "CHG",
}
SHORT_ACTOR = {"npc": "NPC", "player": "PLY"}

# Label komponen evaluation function (untuk panel debug)
TERM_LABEL = {
    "hp": "HP diff",
    "lethal": "Lethal",
    "potion": "Potion",
    "charge": "Charge",
    "guard": "Guard",
    "open": "Open",
    "initiative": "Giliran",
}


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
    hp_text = f"{int(round(current))}/{int(round(maximum))}"
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
        selected_action: Index aksi yang dipilih (0=attack, 1=defend, ...)
        battle_log: List pesan battle
        phase: "select" (pilih aksi), "anim" (jeda aksi NPC),
               "result" (hasil)
        result_timer: Timer untuk delay hasil
        anim_timer: Timer jeda sebelum NPC bergerak
        hint_text: Saran Min-Max untuk pemain (None jika belum diminta)
        last_search: SearchStats hasil pencarian AI terakhir
        pending_action: Aksi yang sudah dipilih AI tapi belum dieksekusi
        thinking: True saat AI sedang menunggu resolusi aksinya
        debug_visible: Tampilkan panel debug keputusan AI (tombol F3)
        battle_stats: Akumulasi statistik pertarungan (damage, aksi, dll.)
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
        self.anim_timer = 0.0
        self.winner = None
        self.hint_text = None
        self.search_info = None
        self.last_search = None
        self.pending_action = None
        self.thinking = False
        self.debug_visible = True
        self.battle_stats = self._new_battle_stats()

    @staticmethod
    def _new_battle_stats():
        """Buat counter statistik pertarungan yang kosong."""
        return {
            "player": {
                "damage": 0, "heal": 0,
                "actions": {a: 0 for a in ACTIONS},
            },
            "npc": {
                "damage": 0, "heal": 0,
                "actions": {a: 0 for a in ACTIONS},
            },
        }

    # -- lifecycle ----------------------------------------------------------

    def start_battle(self, player, npc):
        """Mulai pertarungan baru.

        Args:
            player: Objek Player
            npc: Objek NPC
        """
        self.player = player
        self.npc = npc

        # Reset HP dulu, baru bangun GameState (urutan ini penting:
        # GameState dibaca dari battle_hp objek, jadi harus sudah benar)
        player.battle_hp = player.battle_max_hp
        npc.battle_hp = npc.battle_max_hp

        self.state = create_battle_state(player, npc)
        self.selected_action = 0
        self.battle_log = []
        self.phase = "select"
        self.result_timer = 0.0
        self.anim_timer = 0.0
        self.winner = None
        self.hint_text = None
        self.search_info = None
        self.last_search = None
        self.pending_action = None
        self.thinking = False
        self.battle_stats = self._new_battle_stats()

        arch = getattr(npc, "archetype_name", None)
        title = f"{npc.name} ({arch})" if arch else npc.name

        self.battle_log.append("Battle started!")
        self.battle_log.append(
            f"  Player: {player.battle_hp} HP, {player.battle_atk} ATK, "
            f"{player.battle_potions} potion"
        )
        self.battle_log.append(
            f"  {title}: {npc.battle_hp} HP, {npc.battle_atk} ATK, "
            f"{npc.battle_potions} potion"
        )

    def sync_stats(self):
        """Tulis kembali HP & potion dari GameState ke objek player/NPC.

        Dipanggil saat pertarungan selesai supaya resource (terutama potion)
        yang dipakai selama battle ikut terbawa ke battle berikutnya.
        """
        if self.state is None or self.player is None or self.npc is None:
            return
        self.player.battle_hp = max(0.0, self.state.player_hp)
        self.player.battle_potions = self.state.player_potions
        self.npc.battle_hp = max(0.0, self.state.npc_hp)
        self.npc.battle_potions = self.state.npc_potions

    # -- input ---------------------------------------------------------------

    def handle_event(self, event):
        """Handle input events saat battle aktif.

        Keyboard:
        - Left/Right (A/D): Pilih aksi
        - Enter/Space: Konfirmasi aksi / tutup layar hasil
        - 1/2/3/4: Shortcut aksi (Attack/Defend/Potion/Charge)
        - H: Minta saran Min-Max untuk pemain
        - F3: Toggle panel debug keputusan AI

        Args:
            event: pygame event

        Returns:
            "done" jika battle selesai dan siap ditutup, None jika belum
        """
        if self.state is None:
            return None

        # Panel debug bisa di-toggle kapan saja (semua phase)
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_F3, pygame.K_TAB):
            self.debug_visible = not self.debug_visible
            return None

        # Layar hasil: hanya menunggu konfirmasi pemain
        if self.phase == "result":
            if (
                event.type == pygame.KEYDOWN
                and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)
                and self.result_timer > 0.5
            ):
                return "done"
            return None

        # Masih jeda aksi NPC / state sudah selesai -> abaikan input
        if self.state.finished or self.phase != "select":
            return None

        if self.state.whose_turn != "player":
            return None

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._cycle_selection(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._cycle_selection(1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._execute_player_action()
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                # 1/2/3/4 -> urutan aksi di core.ACTIONS
                index = event.key - pygame.K_1
                if 0 <= index < len(ACTIONS):
                    self._try_action(ACTIONS[index])
            elif event.key == pygame.K_h:
                self._show_hint()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse_click(event.pos)

        return None

    def _cycle_selection(self, direction):
        """Geser pilihan tombol aksi ke kiri/kanan."""
        actions = self.state.get_legal_actions("player")
        if not actions:
            return
        self.selected_action = (self.selected_action + direction) % len(actions)

    def _try_action(self, action):
        """Pilih aksi berdasarkan nama lalu eksekusi (jika legal)."""
        actions = self.state.get_legal_actions("player")
        if action not in actions:
            return
        self.selected_action = actions.index(action)
        self._execute_player_action()

    def _handle_mouse_click(self, pos):
        """Handle mouse click pada action buttons.

        Menggunakan layout yang sama persis dengan yang digambar sehingga
        area klik selalu cocok dengan tombol di layar.

        Args:
            pos: Tuple (x, y) posisi click
        """
        if self.state is None or self.phase != "select":
            return
        if self.state.whose_turn != "player":
            return

        layout = self._layout(pygame.display.get_surface().get_size())
        for i, (_action, rect) in enumerate(layout["buttons"]):
            if rect.collidepoint(pos):
                self.selected_action = i
                self._execute_player_action()
                return

    def _show_hint(self):
        """Minta saran aksi untuk pemain dari algoritma yang sama."""
        action, score, stats, _line = get_player_hint(self.state)
        if action is None:
            return
        label = ACTION_INFO.get(action, {}).get("label", action.upper())
        self.hint_text = f"HINT: {label}  (skor {score:+.1f}, depth {stats.max_depth})"
        self.battle_log.append(
            f"Hint -> {label}: {stats.nodes} nodes, {stats.pruned} pruned, "
            f"{stats.ms:.1f} ms"
        )

    # -- turn resolution ------------------------------------------------------

    def _execute_player_action(self):
        """Eksekusi aksi player, lalu tunda giliran NPC (phase 'anim')."""
        if self.state is None or self.state.finished or self.phase != "select":
            return
        if self.state.whose_turn != "player":
            return

        actions = self.state.get_legal_actions("player")
        if not actions:
            return

        self.selected_action %= len(actions)
        action = actions[self.selected_action]
        result = self.state.apply_action("player", action)
        self.hint_text = None
        self._log_action("player", action, result)

        if self._finish_if_needed():
            return

        # Giliran NPC, tapi beri jeda supaya pemain sempat membaca log.
        # Pencarian dijalankan SEKARANG (bukan saat resolusi) supaya panel
        # debug langsung menampilkan proses keputusan AI selama jeda.
        self.state.next_turn()
        self.phase = "anim"
        self.anim_timer = 0.0
        self._think_npc()

    def _think_npc(self):
        """Jalankan Min-Max untuk giliran NPC dan simpan keputusannya."""
        action, score, stats, _line = get_npc_action(self.state)
        self.pending_action = (action, score)
        self.last_search = stats
        self.search_info = stats.as_dict()
        self.thinking = True

    def _execute_npc_action(self):
        """Terapkan aksi NPC yang sudah dipilih Min-Max saat 'think'."""
        if self.pending_action is None:
            # Cadangan: pencarian belum pernah jalan untuk giliran ini
            self._think_npc()

        action, score = self.pending_action
        self.pending_action = None
        self.thinking = False
        stats = self.last_search

        result = self.state.apply_action("npc", action)
        self._log_action("npc", action, result)
        if stats is not None:
            self.battle_log.append(
                f"  AI: depth {stats.max_depth} | {stats.nodes} nodes | "
                f"{stats.pruned} pruned | {stats.ms:.1f} ms | score {score:+.1f}"
            )

        if self._finish_if_needed():
            return

        # Balik ke pemain
        self.state.next_turn()
        self.phase = "select"
        self.selected_action = 0

    def _log_action(self, who, action, result):
        """Tambah pesan aksi ke battle log + akumulasi statistik."""
        # Akumulasi statistik pertarungan (untuk panel debug)
        side = self.battle_stats[who]
        side["actions"][action] = side["actions"].get(action, 0) + 1
        side["damage"] += int(result.get("damage", 0) or 0)
        side["heal"] += int(result.get("heal", 0) or 0)

        actor = "Player" if who == "player" else self.npc.name
        target = self.npc.name if who == "player" else "Player"

        if action == "attack":
            bonus = " CHARGED!" if result.get("bonus") else ""
            blocked = " (blocked!)" if result.get("blocked") else ""
            self.battle_log.append(
                f"{actor} attacks{bonus}! -{result['damage']} HP to {target}{blocked}"
            )
        elif action == "defend":
            self.battle_log.append(f"{actor} defends! (guard 1 hit)")
        elif action == "potion":
            self.battle_log.append(
                f"{actor} uses potion! +{result['heal']} HP (open: +80% dmg taken)"
            )
        elif action == "charge":
            self.battle_log.append(f"{actor} charges up! Next attack x2.4")

    def _finish_if_needed(self):
        """Cek apakah battle selesai; jika ya, masuk phase 'result'.

        Returns:
            True jika battle sudah selesai
        """
        if not self.state.finished:
            return False

        self.winner = self.state.winner
        self.phase = "result"
        self.result_timer = 0.0
        self.sync_stats()

        if self.winner == "player":
            self.battle_log.append(f"{self.npc.name} defeated!")
        else:
            self.battle_log.append("You lost!")
        return True

    # -- update / draw --------------------------------------------------------

    def update(self, dt):
        """Update battle state.

        Args:
            dt: Delta time dalam detik
        """
        if self.phase == "anim":
            self.anim_timer += dt
            if self.anim_timer >= NPC_DELAY:
                # NPC bergerak di sini (bukan di frame yang sama dengan
                # aksi pemain) supaya tidak terjadi hitch sekaligus log
                # tetap terbaca)
                self._execute_npc_action()
        elif self.phase == "result":
            self.result_timer += dt

    def _layout(self, screen_size):
        """Hitung geometri panel, log, tombol aksi, dan baris hint.

        Dipakai bersama oleh draw() dan _handle_mouse_click() supaya
        posisi klik selalu sama dengan tombol yang digambar.

        Args:
            screen_size: Tuple (width, height) layar

        Returns:
            Dict berisi rect panel, log, tombol, dan hint
        """
        sw, sh = screen_size
        panel_w = min(700, max(240, sw - 60))
        panel_h = min(500, max(300, sh - 60))
        panel = pygame.Rect(
            (sw - panel_w) // 2, (sh - panel_h) // 2, panel_w, panel_h
        )

        # Log menempel di dasar panel
        log_h = 110
        log = pygame.Rect(panel.x + 15, panel.y + panel_h - 130,
                          panel_w - 30, log_h)

        actions = self.state.get_legal_actions("player") if self.state else []
        count = max(1, len(actions))
        gap = 20
        btn_w = min(140, (panel_w - 40 - gap * (count - 1)) // count)
        btn_h = 45
        total_w = count * btn_w + (count - 1) * gap
        start_x = panel.centerx - total_w // 2
        btn_y = log.y - btn_h - 34
        # Jangan tumpang tindih dengan panel stats di layar sempit
        btn_y = max(btn_y, panel.y + 155)

        buttons = [
            (action, pygame.Rect(start_x + i * (btn_w + gap), btn_y, btn_w, btn_h))
            for i, action in enumerate(actions)
        ]
        hint = pygame.Rect(panel.x + 15, btn_y + btn_h + 8, panel_w - 30, 18)

        return {"panel": panel, "log": log, "buttons": buttons, "hint": hint}

    def draw(self, screen, font):
        """Gambar battle overlay ke layar.

        Args:
            screen: Surface utama
            font: pygame Font untuk rendering teks
        """
        if self.state is None:
            return

        sw, sh = screen.get_size()
        layout = self._layout((sw, sh))
        panel = layout["panel"]
        panel_x, panel_y = panel.x, panel.y
        panel_w, panel_h = panel.width, panel.height

        # Dim background
        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 200))
        screen.blit(dim, (0, 0))

        # Main panel
        _draw_pixel_border(screen, panel, BORDER, BG_PANEL)

        # ---- Header: Turn info ----
        header_h = 45
        header = pygame.Rect(panel_x + 3, panel_y + 3, panel_w - 6, header_h)
        pygame.draw.rect(screen, BG_PANEL_LIGHT, header, border_radius=2)

        turn_text = f"Turn {self.state.turn}"
        if self.phase == "anim":
            turn_text += " - ENEMY TURN"
            turn_color = ATTACK_RED
        elif self.state.whose_turn == "player":
            turn_text += " - YOUR TURN"
            turn_color = TEXT_HIGHLIGHT
        else:
            turn_text += " - ENEMY TURN"
            turn_color = ATTACK_RED
        rendered = font.render(turn_text, True, turn_color)
        screen.blit(rendered, (panel.centerx - rendered.get_width() // 2, panel_y + 15))

        # ---- Player & NPC Stats ----
        # Kolom dibuat lebih sempit dengan gutter di tengah supaya teks VS
        # tidak menimpa baris ATK/DEF
        stats_y = panel_y + header_h + 15
        col_w = panel_w // 2 - 45

        # Player panel (rata kiri)
        p_x = panel_x + 15
        self._draw_character_stats(
            screen, font, p_x, stats_y, col_w,
            "PLAYER",
            self.state.player_hp, self.state.player_max_hp,
            self.state.player_atk, self.state.player_def,
            self.state.player_potions, self.player.battle_heal,
            is_player=True,
        )

        # NPC panel (rata kanan)
        n_x = panel_x + panel_w - 15 - col_w
        self._draw_character_stats(
            screen, font, n_x, stats_y, col_w,
            self.npc.name.upper(),
            self.state.npc_hp, self.state.npc_max_hp,
            self.state.npc_atk, self.state.npc_def,
            self.state.npc_potions, self.npc.battle_heal,
            is_player=False,
        )

        # ---- VS text (di gutter tengah) ----
        vs_font = pygame.font.SysFont("consolas", 24, bold=True)
        vs_text = vs_font.render("VS", True, TEXT_HIGHLIGHT)
        vs_x = panel.centerx - vs_text.get_width() // 2
        vs_y = stats_y + 52
        screen.blit(vs_text, (vs_x, vs_y))

        # ---- Action Buttons (hanya saat giliran pemain) ----
        if self.state.whose_turn == "player" and self.phase == "select":
            self._draw_action_buttons(screen, font, layout)

        # ---- Battle Log ----
        self._draw_log(screen, font, layout)

        # ---- Result Screen ----
        if self.phase == "result" and self.result_timer > 0.5:
            self._draw_result(screen, font, panel)

        # ---- Debug panel: proses keputusan AI (F3) ----
        if self.debug_visible:
            self._draw_debug_panel(screen, font)

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
            f"ATK: {atk}   DEF: {defense}",
            f"Potion: {potions} (+{heal} HP)",
        ]
        for i, text in enumerate(stats):
            surf = font.render(text, True, TEXT_DIM)
            screen.blit(surf, (x, y + 50 + i * 18))

    def _draw_action_buttons(self, screen, font, layout):
        """Gambar action buttons + baris hint.

        Args:
            screen: Surface utama
            font: pygame Font
            layout: Hasil dari _layout()
        """
        panel = layout["panel"]

        colors = {
            "attack": (ATTACK_RED, (180, 50, 40)),
            "defend": (DEFEND_BLUE, (40, 100, 180)),
            "potion": (POTION_PURPLE, (120, 50, 170)),
            "charge": (CHARGE_GOLD, (190, 135, 30)),
        }
        icons = {
            "attack": "ATK",
            "defend": "DEF",
            "potion": "POT",
            "charge": "CHG",
        }

        for i, (action, btn_rect) in enumerate(layout["buttons"]):
            is_selected = i == self.selected_action

            # Button background (sumber warna: ACTION_INFO core -> UI sinkron)
            base = ACTION_INFO.get(action, {}).get("color")
            default, hover_color = colors.get(action, (ACCENT, ACCENT_HOVER))
            color = base or default
            bg_color = hover_color if is_selected else color
            pygame.draw.rect(screen, bg_color, btn_rect, border_radius=5)

            # Border
            border_color = TEXT_HIGHLIGHT if is_selected else BORDER_LIGHT
            pygame.draw.rect(screen, border_color, btn_rect, 2, border_radius=5)

            # Hotkey + Label
            hotkey = ACTION_INFO.get(action, {}).get("hotkey", str(i + 1))
            label = ACTION_INFO.get(action, {}).get("label", action.upper())

            hot_surf = font.render(hotkey, True, TEXT_HIGHLIGHT)
            label_surf = font.render(label, True, TEXT_WHITE)

            screen.blit(
                hot_surf,
                (btn_rect.centerx - hot_surf.get_width() // 2, btn_rect.y + 5),
            )
            screen.blit(
                label_surf,
                (btn_rect.centerx - label_surf.get_width() // 2, btn_rect.y + 23),
            )

        # Hint (saran Min-Max jika diminta, kontrol jika tidak)
        if self.hint_text:
            hint_surf = font.render(self.hint_text, True, TEXT_HIGHLIGHT)
        else:
            hint_surf = font.render(
                "<> select | ENTER confirm | 1-4 hotkey | H hint | F3 AI info",
                True, TEXT_DIM,
            )
        screen.blit(hint_surf, (
            panel.centerx - hint_surf.get_width() // 2,
            layout["hint"].y,
        ))

    def _draw_log(self, screen, font, layout):
        """Gambar battle log + statistik pencarian AI terakhir."""
        log_rect = layout["log"]
        pygame.draw.rect(screen, (8, 10, 16), log_rect, border_radius=3)
        pygame.draw.rect(screen, BORDER, log_rect, 1, border_radius=3)

        # Judul + statistik search di baris yang sama
        log_title = font.render("BATTLE LOG", True, TEXT_DIM)
        screen.blit(log_title, (log_rect.x + 5, log_rect.y + 3))

        if self.search_info:
            info = self.search_info
            stat_text = (
                f"AI search: depth {info['depth']} | {info['nodes']} nodes | "
                f"{info['pruned']} pruned | {info['ms']:.1f} ms"
            )
            stat_surf = font.render(stat_text, True, TEXT_DIM)
            screen.blit(
                stat_surf,
                (log_rect.right - stat_surf.get_width() - 8, log_rect.y + 3),
            )

        # Log entries (tampilkan beberapa terakhir)
        visible_logs = self.battle_log[-LOG_VISIBLE:]
        for i, msg in enumerate(visible_logs):
            entry = font.render(
                msg, True, TEXT_DIM if i < len(visible_logs) - 1 else TEXT_WHITE
            )
            screen.blit(entry, (log_rect.x + 10, log_rect.y + 22 + i * 20))

    # -----------------------------------------------------------------------
    # Debug overlay: proses pengambilan keputusan AI
    # -----------------------------------------------------------------------

    def _status_line(self):
        """Ringkasan status aktif kedua pihak, mis. "PLY:guard, NPC:charged"."""
        flags = []
        for who, tag in (("player", "PLY"), ("npc", "NPC")):
            for flag in ("guard", "charged", "open"):
                if getattr(self.state, f"{who}_{flag}"):
                    flags.append(f"{tag}:{flag}")
        return ", ".join(flags) if flags else "-"

    def _current_score_npc(self):
        """Skor evaluation state saat ini dari perspektif NPC."""
        if self.state.finished:
            return 1e9 if self.state.winner == "npc" else -1e9
        return sum(evaluate_terms(self.state).values())

    def _debug_sections(self):
        """Bangun data section untuk panel debug keputusan AI.

        Returns:
            List of dict {"header", "header_color", "rows"}
            Row kinds: ("text", teks, warna), ("split", pct),
            ("bar", label, pct, nilai, terpilih), ("term", label, nilai,
            skala, total?)
        """
        st = self.state
        sections = []

        # --- Status keputusan ---
        if self.thinking:
            status, color = "AI BERPIKIR...", TEXT_HIGHLIGHT
        elif self.last_search and self.last_search.action:
            chosen = ACTION_INFO.get(
                self.last_search.action, {}
            ).get("label", str(self.last_search.action).upper())
            status, color = f"AKSI: {chosen}", WIN_GREEN
        else:
            status, color = "BELUM ADA PENCARIAN", TEXT_DIM

        sections.append({
            "header": "MIN-MAX DEBUGGER",
            "header_color": TEXT_HIGHLIGHT,
            "rows": [
                ("text", f"Status : {status}", color),
                ("text",
                 f"Giliran: {st.whose_turn.upper()}   Ronde: {st.turn}",
                 TEXT_WHITE),
            ],
        })

        # --- Peluang menang (estimasi dari skor eval) ---
        npc_pct = win_probability(self._current_score_npc(), "npc")
        sections.append({
            "header": "PELUANG MENANG (estimasi)",
            "rows": [
                ("text",
                 f"NPC {npc_pct:3.0f}%   |   PLAYER {100 - npc_pct:3.0f}%",
                 TEXT_WHITE),
                ("split", npc_pct),
            ],
        })

        # --- Statistik pencarian ---
        s = self.last_search
        if s:
            pruned_pct = (100.0 * s.pruned / s.nodes) if s.nodes else 0.0
            sections.append({
                "header": "STATISTIK PENCARIAN",
                "rows": [
                    ("text", f"Depth  : {s.max_depth} / {st.max_depth}", TEXT_WHITE),
                    ("text", f"Nodes  : {s.nodes}", TEXT_WHITE),
                    ("text", f"Pruned : {s.pruned} ({pruned_pct:.1f}%)", TEXT_WHITE),
                    ("text", f"Waktu  : {s.ms:.1f} ms / budget {TIME_BUDGET * 1000:.0f} ms",
                     TEXT_WHITE),
                ],
            })

            # --- Skor minimax tiap aksi di root (inti keputusan) ---
            if s.root_scores:
                scores = s.scores_npc_view()
                rows = []
                for action in ACTIONS:
                    if action not in scores:
                        continue
                    value = scores[action]
                    pct = win_probability(value, "npc")
                    label = ACTION_INFO.get(action, {}).get(
                        "label", action.upper()
                    )
                    rows.append(("bar", label, pct, f"{pct:.0f}% {value:+.1f}",
                                 action == s.action))
                sections.append({
                    "header": "SKOR MIN-MAX PER AKSI (NPC)",
                    "rows": rows,
                })

            # --- Principal variation (jalur main terbaik) ---
            if s.line:
                pv = " > ".join(
                    f"{SHORT_ACTOR.get(a, a)}:{SHORT_ACTION.get(x, x)}"
                    for a, x in s.line[:8]
                )
                lines = textwrap.wrap(pv, 34) or [pv]
                sections.append({
                    "header": "PRINCIPAL VARIATION",
                    "rows": [("text", ln, ACCENT) for ln in lines],
                })

        # --- Rincian evaluation function (state saat ini, live) ---
        terms = {} if st.finished else evaluate_terms(st)
        if terms:
            scale = max([abs(v) for v in terms.values()] + [1.0])
            rows = [
                ("term", TERM_LABEL.get(k, k), v, scale)
                for k, v in terms.items()
            ]
            rows.append(("term", "TOTAL", sum(terms.values()), scale, True))
            sections.append({
                "header": "EVALUATION FUNCTION (live)",
                "rows": rows,
            })

        # --- Statistik pertarungan ---
        p_stats = self.battle_stats["player"]
        n_stats = self.battle_stats["npc"]

        def _acts(counter):
            return " ".join(f"{SHORT_ACTION[a]}:{counter[a]}" for a in ACTIONS)

        sections.append({
            "header": "STATISTIK PERTARUNGAN",
            "rows": [
                ("text",
                 f"Damage : {p_stats['damage']} keluar / {n_stats['damage']} masuk",
                 TEXT_WHITE),
                ("text",
                 f"Heal   : +{p_stats['heal']} / +{n_stats['heal']}", TEXT_DIM),
                ("text", f"Player : {_acts(p_stats['actions'])}", TEXT_DIM),
                ("text", f"Musuh  : {_acts(n_stats['actions'])}", TEXT_DIM),
                ("text", f"Status : {self._status_line()}", TEXT_DIM),
            ],
        })

        return sections

    def _debug_rect(self, screen_size, height):
        """Hitung posisi panel debug (di sisi panel battle yang kosong).

        Prioritas: kanan panel battle -> kiri panel battle -> overlay
        transparan kalau layar terlalu sempit.

        Args:
            screen_size: Tuple (width, height) layar
            height: Tinggi panel yang diminta

        Returns:
            pygame.Rect
        """
        sw, sh = screen_size
        battle = self._layout(screen_size)["panel"]
        width = min(DEBUG_PANEL_WIDTH, max(200, sw - 40))
        gap = 10

        if sw - battle.right >= width + gap:
            x = battle.right + gap
        elif battle.left >= width + gap:
            x = battle.left - width - gap
        else:
            x = max(8, sw - width - 8)

        h = min(height, sh - 20)
        return pygame.Rect(x, (sh - h) // 2, width, h)

    def _draw_debug_panel(self, screen, font):
        """Gambar panel debug proses keputusan AI.

        Args:
            screen: Surface utama
            font: pygame Font
        """
        if self.state is None:
            return

        sw, sh = screen.get_size()
        sections = self._debug_sections()
        pad = 10
        row_h = font.get_height() + 2
        header_h = row_h + 6

        height = pad * 2
        for section in sections:
            height += header_h + len(section["rows"]) * row_h + DEBUG_ROW_GAP
        height -= DEBUG_ROW_GAP

        rect = self._debug_rect((sw, sh), height)

        panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        panel.fill((12, 16, 24, 228))
        pygame.draw.rect(panel, (60, 70, 90), panel.get_rect(), 1)
        screen.blit(panel, rect.topleft)

        y = rect.y + pad
        for section in sections:
            if y + header_h > rect.bottom:
                break
            header = font.render(
                section["header"], True,
                section.get("header_color", (180, 190, 210)),
            )
            screen.blit(header, (rect.x + pad, y))
            y += header_h

            for row in section["rows"]:
                if y + row_h > rect.bottom:
                    break
                y += self._draw_debug_row(screen, font, rect, y, row_h, row)
            y += DEBUG_ROW_GAP

    def _draw_debug_row(self, screen, font, rect, y, row_h, row):
        """Gambar satu baris isi panel debug.

        Args:
            screen: Surface utama
            font: pygame Font
            rect: Rect panel debug
            y: Posisi y baris
            row_h: Tinggi baris
            row: Tuple deskripsi baris

        Returns:
            Tinggi baris yang dipakai
        """
        kind = row[0]
        pad = 10
        x = rect.x + pad
        inner_w = rect.w - pad * 2

        # --- Baris teks biasa ---
        if kind == "text":
            screen.blit(font.render(row[1], True, row[2]), (x, y))
            return row_h

        # --- Bar peluang menang (NPC vs PLAYER) ---
        if kind == "split":
            pct = max(0.0, min(100.0, row[1]))
            bar = pygame.Rect(x, y + 3, inner_w, row_h - 8)
            pygame.draw.rect(screen, HP_BG, bar, border_radius=3)
            fill_w = int(bar.w * pct / 100.0)
            if fill_w > 0:
                pygame.draw.rect(
                    screen, ATTACK_RED,
                    pygame.Rect(bar.x, bar.y, fill_w, bar.h),
                    border_radius=3,
                )
            pygame.draw.rect(screen, BORDER_LIGHT, bar, 1, border_radius=3)
            return row_h

        # --- Bar skor minimax per aksi ---
        if kind == "bar":
            _label, pct, right, chosen = row[1], row[2], row[3], row[4]
            label_w, value_w = 62, 74
            bar_x = x + label_w
            bar_w = max(30, inner_w - label_w - value_w)

            mark = "> " if chosen else "  "
            lbl_color = TEXT_HIGHLIGHT if chosen else TEXT_DIM
            screen.blit(
                font.render(mark + _label, True, lbl_color), (x, y)
            )

            bg = pygame.Rect(bar_x, y + 3, bar_w, row_h - 8)
            pygame.draw.rect(screen, HP_BG, bg, border_radius=2)
            fill_w = max(1, int(bg.w * max(0.0, pct) / 100.0))
            pygame.draw.rect(
                screen, _hp_color(pct / 100.0),
                pygame.Rect(bg.x, bg.y, fill_w, bg.h),
                border_radius=2,
            )
            border = TEXT_HIGHLIGHT if chosen else BORDER_LIGHT
            pygame.draw.rect(screen, border, bg, 1, border_radius=2)

            val_surf = font.render(right, True, lbl_color)
            screen.blit(val_surf, (rect.right - pad - val_surf.get_width(), y))
            return row_h

        # --- Bar komponen evaluation function (skala nol di tengah) ---
        if kind == "term":
            _label, value, scale = row[1], row[2], row[3]
            is_total = len(row) > 4 and row[4]
            label_w, value_w = 68, 56
            bar_x = x + label_w
            bar_w = max(24, inner_w - label_w - value_w)

            lbl_color = TEXT_HIGHLIGHT if is_total else TEXT_DIM
            screen.blit(font.render(_label, True, lbl_color), (x, y))

            if value > 0:
                v_color = HP_GREEN
            elif value < 0:
                v_color = HP_RED
            else:
                v_color = TEXT_DIM
            if is_total:
                v_color = TEXT_HIGHLIGHT
            val_surf = font.render(f"{value:+.1f}", True, v_color)
            screen.blit(val_surf, (rect.right - pad - val_surf.get_width(), y))

            zero = bar_x + bar_w // 2
            span = bar_w // 2
            width = max(1, int(span * min(1.0, abs(value) / scale)))
            bar = pygame.Rect(
                zero if value >= 0 else zero - width,
                y + 4, width, max(3, row_h - 10),
            )
            pygame.draw.rect(screen, v_color, bar, border_radius=1)
            pygame.draw.line(
                screen, BORDER_LIGHT, (zero, y + 2), (zero, y + row_h - 2), 1,
            )
            return row_h

        return row_h

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
