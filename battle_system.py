"""
battle_system.py - Turn-Based Battle Duel (Player vs NPC) berbasis Pygame.

Modul ini mengorkestrasi duel giliran antara Player (dikendalikan manusia) dan
NPC (dikendalikan AdversarialAI). Sistem ini menangani:

1. Fase pertandingan: giliran Player -> giliran NPC (AI berpikir) -> hasil.
2. Resolusi aksi memakai aturan BattleState.apply_action (sumber kebenaran sama
   dengan yang dipakai mesin pencarian, agar AI dan gameplay konsisten).
3. Rendering UI duel: panel HP, sprite, menu aksi, battle log, damage popup.
4. Integrasi debug overlay adversarial search (toggle tombol 'D').

Saat duel selesai, atribut ``finished`` bernilai True dan main loop akan
mengembalikan game ke OVERWORLD.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

import pygame

from adversarial_ai import (
    ACTION_LABEL,
    ACTIONS,
    ATTACK_MAX,
    ATTACK_MIN,
    DEFAULT_DEPTH,
    DEFEND_REDUCTION,
    MAX_HP,
    POTION_HEAL,
    POTION_LIMIT,
    SPECIAL_COOLDOWN,
    SPECIAL_DAMAGE,
    AdversarialAI,
    BattleState,
)
from debug_overlay import BattleDebugOverlay


# ---------------------------------------------------------------------------
# Palet warna
# ---------------------------------------------------------------------------
BG_TOP = (14, 18, 28)
BG_BOTTOM = (8, 10, 16)
PANEL_BG = (20, 26, 38, 235)
PANEL_EDGE = (58, 72, 98)
TEXT = (232, 238, 248)
TEXT_DIM = (138, 150, 174)
ACCENT = (118, 170, 255)
GOLD = (240, 196, 96)
HP_HIGH = (86, 214, 128)
HP_MID = (240, 198, 84)
HP_LOW = (238, 92, 92)
DAMAGE_COL = (255, 120, 120)
HEAL_COL = (140, 240, 170)

ACTION_COLOR = {
    "ATTACK": (240, 96, 96),
    "DEFEND": (96, 176, 240),
    "POTION": (120, 220, 140),
    "SPECIAL": (208, 150, 250),
}

# Keterangan jumlah/efek tiap aksi (ditampilkan di menu agar pemain tahu)
ACTION_INFO = {
    "ATTACK": f"DMG {ATTACK_MIN}-{ATTACK_MAX}",
    "DEFEND": f"-{int(DEFEND_REDUCTION * 100)}% damage",
    "POTION": f"+{POTION_HEAL} HP",
    "SPECIAL": f"DMG {SPECIAL_DAMAGE}",
}

# Waktu tunggu dramatis sebelum NPC bergerak (detik)
NPC_THINK_DELAY = 0.75
# Lama layar hasil ditampilkan sebelum kembali ke overworld
RESULT_DELAY = 2.4

KEY_TO_ACTION = {
    pygame.K_1: "ATTACK",
    pygame.K_2: "DEFEND",
    pygame.K_3: "POTION",
    pygame.K_4: "SPECIAL",
}


class BattleSystem:
    """Mengelola satu sesi duel turn-based.

    Attributes:
        state: BattleState aktif
        ai: AdversarialAI pengendali NPC
        finished: True saat duel selesai dan siap keluar ke overworld
        winner: "player" / "npc" / None
        phase: "PLAYER_INPUT" | "NPC_THINK" | "RESULT"
        ai_stats: Statistik pencarian AI terakhir (untuk debug overlay)
    """

    def __init__(
        self,
        player_sprite: Optional[pygame.Surface] = None,
        npc_sprite: Optional[pygame.Surface] = None,
        player_hp: int = MAX_HP,
        depth: int = DEFAULT_DEPTH,
        player_name: str = "Player",
        npc_name: str = "Musuh",
        background: Optional[pygame.Surface] = None,
    ):
        """
        Args:
            player_sprite: Sprite player (sudah di-scale overworld)
            npc_sprite: Sprite NPC
            player_hp: HP awal player (dibawa dari state overworld)
            depth: Kedalaman pencarian AI
            player_name: Nama tampilan player
            npc_name: Nama tampilan NPC
            background: Artwork latar duel (mis. map_battle.png) atau snapshot
                terrain dari map overworld. Di-cover + digelapkan agar UI terbaca
        """
        self.ai = AdversarialAI(depth=depth)
        self.depth = depth
        self.state = BattleState(player_hp=max(1, min(MAX_HP, player_hp)))
        self.state.turn = 0  # Player mulai lebih dulu

        self.player_name = player_name
        self.npc_name = npc_name
        self.player_sprite = self._fit_sprite(player_sprite)
        self.npc_sprite = self._fit_sprite(npc_sprite, flip=True)

        # Latar bertema lokasi duel (dari map overworld)
        self.background = background
        self._bg_cache: Optional[pygame.Surface] = None
        self._bg_size: Tuple[int, int] = (0, 0)

        self.debug = BattleDebugOverlay()
        self.ai_stats: Dict = {}

        self.finished = False
        self.winner: Optional[str] = None
        self.phase = "PLAYER_INPUT"
        self.timer = 0.0
        self.result_timer = 0.0
        self.selected = 0
        self.flash = 0.0
        self.shake = 0.0

        self.log: List[Tuple[str, Tuple[int, int, int]]] = []
        self.popups: List[Dict] = []
        self._fonts: Dict[int, pygame.font.Font] = {}

        self._add_log("Duel dimulai. Giliranmu menyerang!", TEXT)

    # ------------------------------------------------------------------
    # Util internal
    # ------------------------------------------------------------------
    def _fit_sprite(
        self, sprite: Optional[pygame.Surface], flip: bool = False
    ) -> Optional[pygame.Surface]:
        """Perbesar sprite agar tampil besar di layar duel."""
        if sprite is None:
            return None
        w, h = sprite.get_size()
        target_h = 176
        scale = target_h / h
        big = pygame.transform.smoothscale(sprite, (int(w * scale), target_h))
        if flip:
            big = pygame.transform.flip(big, True, False)
        return big

    def _get_font(self, size: int) -> pygame.font.Font:
        """Font cache agar tidak membuat Font baru tiap frame."""
        size = max(11, int(size))
        if size not in self._fonts:
            name = "consolas" if pygame.font.match_font("consolas") else None
            self._fonts[size] = pygame.font.SysFont(name, size)
        return self._fonts[size]

    def _add_log(self, text: str, color: Tuple[int, int, int] = TEXT) -> None:
        """Tambah baris ke battle log (maksimal 7 baris terakhir)."""
        self.log.append((text, color))
        if len(self.log) > 7:
            self.log.pop(0)

    def _push_popup(self, text: str, color: Tuple[int, int, int], side: str) -> None:
        """Tambahkan damage/heal popup yang mengambang lalu memudar."""
        self.popups.append(
            {
                "text": text,
                "color": color,
                "side": side,       # "player" / "npc"
                "t": 0.0,
                "life": 1.1,
            }
        )

    # ------------------------------------------------------------------
    # Query giliran
    # ------------------------------------------------------------------
    def _is_npc_turn(self) -> bool:
        return self.state.turn == 1

    def legal_actions(self) -> Tuple[str, ...]:
        """Aksi legal untuk pihak yang sedang giliran."""
        return self.state.legal_actions(self._is_npc_turn())

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        """Proses input keyboard duel.

        - 1..4      : pilih & langsung konfirmasi aksi
        - Panah/WS  : pindah pilihan
        - Enter/Space: konfirmasi aksi terpilih
        - D         : toggle debug overlay adversarial search
        - Tombol lain saat RESULT: lewati layar hasil
        """
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_d:
            self.debug.visible = not self.debug.visible
            return

        if self.phase == "RESULT":
            self.finished = True
            return

        if self.phase != "PLAYER_INPUT":
            return

        if event.key in KEY_TO_ACTION:
            self.selected = ACTIONS.index(KEY_TO_ACTION[event.key])
            self._confirm_selection()
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - 1) % len(ACTIONS)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + 1) % len(ACTIONS)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._confirm_selection()

    def _confirm_selection(self) -> None:
        """Konfirmasi aksi player yang dipilih (jika legal)."""
        action = ACTIONS[self.selected]
        if action not in self.legal_actions():
            self.flash = 0.4
            self._add_log(f"{ACTION_LABEL[action]}: tidak tersedia.", (240, 140, 140))
            return
        self._resolve(is_npc=False, action=action)
        if not self.state.is_terminal():
            self.phase = "NPC_THINK"
            self.timer = NPC_THINK_DELAY

    # ------------------------------------------------------------------
    # Resolusi aksi
    # ------------------------------------------------------------------
    def _resolve(self, is_npc: bool, action: str) -> None:
        """Terapkan aksi ke state dan catat efeknya untuk UI."""
        before_player = self.state.player_hp
        before_npc = self.state.npc_hp

        who_color = ACCENT if not is_npc else (240, 130, 130)
        who = self.player_name if not is_npc else self.npc_name
        self._add_log(f"{who} memakai {ACTION_LABEL[action]}.", who_color)

        # ATTACK memakai damage acak 15-20 saat resolusi nyata
        if action == "ATTACK":
            dmg = random.randint(ATTACK_MIN, ATTACK_MAX)
            self.state = self.state.apply_action(is_npc, action, attack_damage=dmg)
        else:
            self.state = self.state.apply_action(is_npc, action)

        # Popup damage/heal untuk kedua pihak
        d_player = self.state.player_hp - before_player
        d_npc = self.state.npc_hp - before_npc
        if d_npc != 0:
            self._push_popup(
                f"{d_npc:+d}", HEAL_COL if d_npc > 0 else DAMAGE_COL, "npc"
            )
            if d_npc < 0:
                self.shake = 0.25
        if d_player != 0:
            self._push_popup(
                f"{d_player:+d}", HEAL_COL if d_player > 0 else DAMAGE_COL, "player"
            )

        if self.state.is_terminal():
            self._enter_result()

    def _enter_result(self) -> None:
        """Tentukan pemenang dan masuk fase RESULT."""
        if self.state.npc_hp <= 0 and self.state.player_hp <= 0:
            self.winner = "draw"
            self._add_log("Duel berakhir seri!", GOLD)
        elif self.state.npc_hp <= 0:
            self.winner = "player"
            self._add_log("Musuh tumbang. Kamu menang!", (140, 240, 170))
        else:
            self.winner = "npc"
            self._add_log("Kamu tumbang. Musuh menang!", (240, 120, 120))
        self.phase = "RESULT"
        self.result_timer = RESULT_DELAY

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Update timer, popup, dan logika giliran NPC."""
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt)
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt)

        # Popup mengambang
        alive = []
        for p in self.popups:
            p["t"] += dt
            if p["t"] < p["life"]:
                alive.append(p)
        self.popups = alive

        if self.phase == "NPC_THINK":
            self.timer -= dt
            if self.timer <= 0:
                self.ai_stats = self.ai.think(self.state, depth=self.depth)
                self.debug.update(self.ai_stats)
                action = self.ai_stats.get("best_action")
                if action is None:
                    self._enter_result()
                else:
                    self._resolve(is_npc=True, action=action)
                    if not self.state.is_terminal():
                        self.phase = "PLAYER_INPUT"

        elif self.phase == "RESULT":
            self.result_timer -= dt
            if self.result_timer <= 0:
                self.finished = True

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def draw(self, screen: pygame.Surface, font: Optional[pygame.font.Font] = None) -> None:
        """Gambar seluruh adegan duel."""
        w, h = screen.get_size()

        # Geser sedikit saat shake untuk efek getaran
        ox = oy = 0
        if self.shake > 0:
            amp = int(6 * (self.shake / 0.25))
            ox = random.randint(-amp, amp)
            oy = random.randint(-amp, amp)

        canvas = screen
        # Latar duel bertema lokasi
        self._draw_background(canvas, w, h)

        self._draw_title(canvas, w, h)
        self._draw_character(canvas, w, h, "player", ox, oy)
        self._draw_character(canvas, w, h, "npc", ox, oy)
        self._draw_stats_panel(canvas, w, h, "npc")
        self._draw_stats_panel(canvas, w, h, "player")
        self._draw_action_menu(canvas, w, h)
        self._draw_log(canvas, w, h)
        self._draw_popups(canvas, w, h)

        if self.phase == "RESULT":
            self._draw_result(canvas, w, h)

        # Debug overlay adversarial search (di atas segalanya)
        self.debug.draw(canvas, font or self._get_font(w // 90))

    def _draw_background(self, screen: pygame.Surface, w: int, h: int) -> None:
        """Gambar latar duel.

        Jika ada artwork latar (mis. map_battle.png), dipakai sebagai background
        bertema (di-cover, digelapkan, dan diberi vignette). Jika tidak, fallback
        ke gradasi gelap vertikal.
        """
        if self.background is not None:
            if self._bg_cache is None or self._bg_size != (w, h):
                self._bg_cache = self._build_background_cache(w, h)
                self._bg_size = (w, h)
            screen.blit(self._bg_cache, (0, 0))
            return

        # Fallback: gradasi vertikal
        for i in range(h):
            t = i / max(1, h - 1)
            col = tuple(int(BG_TOP[j] + (BG_BOTTOM[j] - BG_TOP[j]) * t) for j in range(3))
            pygame.draw.line(screen, col, (0, i), (w, i))

    def _build_background_cache(self, w: int, h: int) -> pygame.Surface:
        """Buat sekali surface latar: terrain di-cover + lapisan gelap + vignette."""
        sw, sh = self.background.get_size()
        scale = max(w / sw, h / sh)
        nw, nh = max(1, int(sw * scale + 0.5)), max(1, int(sh * scale + 0.5))
        scaled = pygame.transform.smoothscale(self.background, (nw, nh))

        out = pygame.Surface((w, h))
        out.blit(scaled, ((w - nw) // 2, (h - nh) // 2))

        # Lapisan gelap bergradasi agar UI terbaca (lebih gelap di bawah)
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 4):
            t = y / max(1, h - 1)
            alpha = int(45 + 95 * t)
            pygame.draw.rect(veil, (6, 10, 20, alpha), (0, y, w, 4))
        out.blit(veil, (0, 0))

        # Vignette tepi
        vig = pygame.Surface((w, h), pygame.SRCALPHA)
        band = max(24, h // 8)
        for i in range(band):
            a = int(120 * (1 - i / band))
            pygame.draw.rect(vig, (0, 0, 0, a), (0, i, w, 1))
            pygame.draw.rect(vig, (0, 0, 0, a), (0, h - 1 - i, w, 1))
            pygame.draw.rect(vig, (0, 0, 0, a), (i, 0, 1, h))
            pygame.draw.rect(vig, (0, 0, 0, a), (w - 1 - i, 0, 1, h))
        out.blit(vig, (0, 0))
        return out

    def _draw_title(self, screen: pygame.Surface, w: int, h: int) -> None:
        font = self._get_font(w // 42)
        title = font.render("BATTLE DUEL", True, TEXT)
        screen.blit(title, (w // 2 - title.get_width() // 2, int(h * 0.015)))

        turn_font = self._get_font(w // 78)
        if self.phase == "PLAYER_INPUT":
            label, col = "Giliranmu - pilih aksi", (140, 240, 170)
        elif self.phase == "NPC_THINK":
            label, col = f"{self.npc_name} berpikir...", (240, 170, 120)
        else:
            label, col = "Duel selesai", GOLD
        surf = turn_font.render(label, True, col)
        screen.blit(surf, (w // 2 - surf.get_width() // 2, int(h * 0.015) + title.get_height() + 4))

    def _draw_character(self, screen: pygame.Surface, w: int, h: int, side: str, ox: int, oy: int) -> None:
        """Gambar sprite karakter dengan bayangan dan bobbing halus."""
        sprite = self.npc_sprite if side == "npc" else self.player_sprite
        cx = int(w * (0.70 if side == "npc" else 0.30)) + ox
        cy = int(h * 0.56) + oy

        # Lingkaran bayangan
        shadow = pygame.Surface((190, 46), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 110), shadow.get_rect())
        screen.blit(shadow, (cx - 95, cy + 66))

        if sprite is None:
            pygame.draw.circle(screen, (90, 100, 130), (cx, cy), 48)
            return
        rect = sprite.get_rect(midbottom=(cx, cy + 80))
        screen.blit(sprite, rect)

    def _draw_stats_panel(self, screen: pygame.Surface, w: int, h: int, side: str) -> None:
        """Panel HP/stok potion/cooldown untuk satu pihak."""
        is_npc = side == "npc"
        pw, ph = int(w * 0.30), int(h * 0.16)
        x = int(w - 20 - pw) if is_npc else 20
        y = 20
        rect = pygame.Rect(x, y, pw, ph)

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, PANEL_BG, panel.get_rect(), border_radius=14)
        edge = (240, 130, 130) if is_npc else (120, 190, 255)
        pygame.draw.rect(panel, edge, panel.get_rect(), 2, border_radius=14)
        screen.blit(panel, rect.topleft)

        name_font = self._get_font(w // 62)
        small = self._get_font(w // 84)

        name = name_font.render(self.npc_name if is_npc else self.player_name, True, edge)
        screen.blit(name, (x + 16, y + 12))

        # HP bar
        hp = self.state.npc_hp if is_npc else self.state.player_hp
        bar_x, bar_y = x + 16, y + 12 + name.get_height() + 8
        bar_w, bar_h = pw - 32, max(14, ph // 7)
        ratio = max(0.0, min(1.0, hp / MAX_HP))
        col = HP_HIGH if ratio > 0.5 else (HP_MID if ratio > 0.25 else HP_LOW)

        pygame.draw.rect(screen, (16, 20, 30), (bar_x, bar_y, bar_w, bar_h), border_radius=bar_h // 2)
        if ratio > 0:
            pygame.draw.rect(
                screen, col, (bar_x, bar_y, int(bar_w * ratio), bar_h), border_radius=bar_h // 2
            )
        pygame.draw.rect(screen, PANEL_EDGE, (bar_x, bar_y, bar_w, bar_h), 1, border_radius=bar_h // 2)
        hp_txt = small.render(f"{hp}/{MAX_HP}", True, (12, 16, 24) if ratio > 0.5 else TEXT)
        screen.blit(hp_txt, (bar_x + bar_w // 2 - hp_txt.get_width() // 2, bar_y + bar_h // 2 - hp_txt.get_height() // 2))

        info_y = bar_y + bar_h + 8
        potions = self.state.npc_potions if is_npc else self.state.player_potions
        cd = self.state.npc_special_cd if is_npc else self.state.player_special_cd
        defending = self.state.npc_defending if is_npc else self.state.player_defending

        potion_txt = small.render(f"Potion: {potions}/{POTION_LIMIT}", True, HEAL_COL if potions else TEXT_DIM)
        screen.blit(potion_txt, (x + 16, info_y))
        cd_txt = small.render(
            "Special: siap" if cd == 0 else f"Special CD: {cd}",
            True, GOLD if cd == 0 else TEXT_DIM,
        )
        screen.blit(cd_txt, (x + 16 + potion_txt.get_width() + 18, info_y))
        if defending:
            badge = small.render("DEFEND", True, (10, 16, 24))
            brect = badge.get_rect()
            pygame.draw.rect(screen, (96, 190, 240), (x + pw - brect.width - 28, info_y - 2, brect.width + 16, brect.height + 6), border_radius=8)
            screen.blit(badge, (x + pw - brect.width - 20, info_y + 1))

    def _draw_action_menu(self, screen: pygame.Surface, w: int, h: int) -> None:
        """Kotak menu aksi player di kiri bawah."""
        mw, mh = int(w * 0.34), int(h * 0.30)
        x, y = 20, h - 20 - mh
        rect = pygame.Rect(x, y, mw, mh)

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, PANEL_BG, panel.get_rect(), border_radius=14)
        pygame.draw.rect(panel, PANEL_EDGE, panel.get_rect(), 1, border_radius=14)
        screen.blit(panel, rect.topleft)

        head = self._get_font(w // 70).render("AKSI  (1-4 / panah + Enter)", True, ACCENT)
        screen.blit(head, (x + 14, y + 10))

        legal = set(self.legal_actions())
        item_h = (mh - 20 - head.get_height() - 8) // len(ACTIONS)
        label_font = self._get_font(w // 66)
        key_font = self._get_font(w // 82)

        for i, action in enumerate(ACTIONS):
            iy = y + 14 + head.get_height() + i * item_h
            item = pygame.Rect(x + 12, iy, mw - 24, item_h - 6)
            ok = action in legal
            selected = (i == self.selected) and self.phase == "PLAYER_INPUT"

            bg = (34, 44, 62) if ok else (22, 26, 34)
            if selected:
                bg = tuple(min(255, c + 26) for c in ACTION_COLOR[action])
            pygame.draw.rect(screen, bg, item, border_radius=9)
            border = ACTION_COLOR[action] if (ok and selected) else PANEL_EDGE
            pygame.draw.rect(screen, border, item, 2 if selected else 1, border_radius=9)

            # Chip nomor tombol
            chip = pygame.Rect(item.x + 8, item.centery - 12, 24, 24)
            pygame.draw.rect(screen, ACTION_COLOR[action] if ok else (60, 66, 80), chip, border_radius=6)
            kn = key_font.render(str(i + 1), True, (12, 16, 24))
            screen.blit(kn, (chip.centerx - kn.get_width() // 2, chip.centery - kn.get_height() // 2))

            col = TEXT if ok else TEXT_DIM
            screen.blit(label_font.render(ACTION_LABEL[action], True, col), (chip.right + 12, item.centery - label_font.get_height() // 2))

            # Info jumlah/efek aksi (mis. DMG 15-20, +25 HP, DMG 30)
            info = ACTION_INFO[action]
            if action == "POTION":
                info = f"{info}  x{self.state.player_potions}"
            elif action == "SPECIAL":
                cd = self.state.player_special_cd
                info = f"{info}  CD{cd}" if cd > 0 else f"{info}  siap"
            info_col = (120, 220, 140) if ok else (200, 120, 120)
            iw = key_font.size(info)[0]
            screen.blit(key_font.render(info, True, info_col), (item.right - iw - 10, item.centery - key_font.get_height() // 2))

        # Kill/skip hint
        hint = key_font.render("D: debug overlay", True, TEXT_DIM)
        screen.blit(hint, (x + mw - hint.get_width() - 14, y + mh - hint.get_height() - 8))

    def _draw_log(self, screen: pygame.Surface, w: int, h: int) -> None:
        """Panel battle log di kanan bawah."""
        lw, lh = int(w * 0.42), int(h * 0.30)
        x, y = w - 20 - lw, h - 20 - lh
        rect = pygame.Rect(x, y, lw, lh)

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, PANEL_BG, panel.get_rect(), border_radius=14)
        pygame.draw.rect(panel, PANEL_EDGE, panel.get_rect(), 1, border_radius=14)
        screen.blit(panel, rect.topleft)

        font = self._get_font(w // 78)
        screen.blit(font.render("BATTLE LOG", True, GOLD), (x + 14, y + 10))

        line_h = font.get_height() + 4
        start_y = y + 10 + font.get_height() + 8
        for i, (text, color) in enumerate(self.log[-6:]):
            screen.blit(font.render(text, True, color), (x + 14, start_y + i * line_h))

    def _draw_popups(self, screen: pygame.Surface, w: int, h: int) -> None:
        """Gambar damage/heal popup yang memudar naik."""
        font = self._get_font(w // 46)
        for p in self.popups:
            prog = p["t"] / p["life"]
            alpha = max(0, int(255 * (1 - prog)))
            cx = int(w * (0.70 if p["side"] == "npc" else 0.30))
            cy = int(h * 0.42) - int(prog * 60)
            surf = font.render(p["text"], True, p["color"])
            surf.set_alpha(alpha)
            screen.blit(surf, (cx - surf.get_width() // 2, cy))

    def _draw_result(self, screen: pygame.Surface, w: int, h: int) -> None:
        """Overlay layar hasil duel."""
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((4, 6, 12, 180))
        screen.blit(veil, (0, 0))

        big = self._get_font(w // 26)
        if self.winner == "player":
            text, col = "KAMU MENANG!", (140, 240, 170)
            sub = f"Musuh kalah - keluar dari Battle Mode"
        elif self.winner == "npc":
            text, col = "KAMU KALAH...", (240, 120, 120)
            sub = "HP dipulihkan - kembali ke overworld"
        else:
            text, col = "SERI", GOLD
            sub = "Kembali ke overworld"
        surf = big.render(text, True, col)
        screen.blit(surf, (w // 2 - surf.get_width() // 2, int(h * 0.38)))

        small = self._get_font(w // 70)
        s2 = small.render(sub, True, TEXT)
        screen.blit(s2, (w // 2 - s2.get_width() // 2, int(h * 0.38) + surf.get_height() + 10))
        hint = self._get_font(w // 84).render("Tekan tombol apa saja untuk melanjutkan", True, TEXT_DIM)
        screen.blit(hint, (w // 2 - hint.get_width() // 2, int(h * 0.38) + surf.get_height() + s2.get_height() + 22))
