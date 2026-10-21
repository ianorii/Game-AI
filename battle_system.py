"""
battle_system.py - Turn-Based Battle Duel (Player vs NPC) berbasis Pygame.

Modul ini mengorkestrasi duel giliran antara Player (dikendalikan manusia) dan
NPC (dikendalikan AdversarialAI). Sistem ini menangani:

1. Fase pertandingan: giliran Player -> giliran NPC (AI berpikir) -> hasil.
2. Resolusi aksi memakai aturan BattleState.apply_action (sumber kebenaran sama
   dengan yang dipakai mesin pencarian, agar AI dan gameplay konsisten).
3. Rendering UI duel: panel HP, sprite, menu aksi, battle log, damage popup.
4. Integrasi debug overlay adversarial search (toggle tombol 'D').

Saat duel selesai, layar hasil (menang/kalah/seri) tampil dan ``finished``
baru bernilai True setelah pemain menekan **Enter** (atau ESC) — main loop
tidak keluar dari Battle Mode sendirian, lalu game kembali ke OVERWORLD.
"""
from __future__ import annotations

import math
import os
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
from game.ambush.buff import Buff, summarize_squad
from game.ambush.buff_ai import BuffAwareAI, BuffBattleState, apply_chip_hook
from game.ambush.config import AmbushConfig
from game.ambush.enemy_queue import ENEMY_BASE_HP, enemy_max_hp
from game.ambush.types import display_role


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
# Lama animasi masuk layar hasil (layar hasil tidak ditutup otomatis:
# pemain menekan Enter untuk kembali ke overworld)
RESULT_DELAY = 2.4

# Rentang kedalaman pencarian yang bisa diubah pemain saat duel (tombol - / =).
# Batas atas 7 mengikuti rentang eksperimen E1/E4 di experiments.py, supaya
# angka node di debug overlay bisa langsung dibandingkan dengan laporan.
DEPTH_MIN = 1
DEPTH_MAX = 7

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
        npc_buff: Optional[Buff] = None,
        npc_squad=None,
        player_buff: Optional[Buff] = None,
        player_loadout=None,
        target: float = 0.5,
        sim_rate: str = "",
        player_potions: Optional[int] = None,
        npc_potions: Optional[int] = None,
        duel_label: str = "",
        queue_view: Optional[dict] = None,
        enemy_base_hp: int = ENEMY_BASE_HP,
        # --- Aset Tahap 3 (semua optional, fallback aman) ---
        item_sprites: Optional[Dict[str, pygame.Surface]] = None,
        custom_font: Optional[pygame.font.Font] = None,
        custom_font_path: Optional[str] = None,
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
            npc_buff: Buff Tahap 3 dari Ambush Director (None = duel polos
                tahap 2, perilaku tidak berubah sama sekali)
            npc_squad: SquadConfig asal buff (untuk tampilan HUD saja)
            item_sprites: Dict nama item -> surface ikon (untuk HUD item)
            custom_font: Font kustom TTF (None = fallback system font)
            custom_font_path: Path file TTF untuk membuat font berukuran bervariasi
        """
        depth = max(DEPTH_MIN, min(DEPTH_MAX, int(depth)))
        self.depth = depth
        self.npc_buff = npc_buff
        self.player_buff = player_buff
        self.duel_label = duel_label  # mis. "DUEL 2 DARI 3" (Fase 5 antrean)
        self.queue_view = queue_view  # info antrean (Fase 6) / None
        self.npc_squad = npc_squad
        self.player_loadout = player_loadout
        self.target = target
        self.sim_rate = sim_rate
        # --- Aset Tahap 3 ---
        self.item_sprites = item_sprites or {}
        self.custom_font = custom_font
        self._custom_font_path = custom_font_path
        self.turn_no = 1
        self.npc_max_hp = enemy_max_hp(
            npc_buff if npc_buff else Buff(), enemy_base_hp)
        self.player_max_hp = MAX_HP + (player_buff.hp if player_buff else 0)
        if npc_buff is not None or player_buff is not None:
            # Duel ber-buff: transisi (BuffBattleState) + otak (BuffAwareAI)
            # sama-sama kenal buff; duel polos memakai kelas tahap 2 asli.
            self.state = BuffBattleState(
                player_hp=max(1, min(self.player_max_hp, player_hp)),
                npc_hp=self.npc_max_hp, buff=npc_buff,
                player_buff=player_buff)
            if player_potions is not None:  # potion terbawa antar-duel
                self.state.player_potions = max(0, player_potions)
            if npc_potions is not None:  # musuh segar / terbawa (config)
                self.state.npc_potions = max(0, npc_potions)
            self.ai = BuffAwareAI(depth=depth, buff=npc_buff,
                                   player_buff=player_buff)
        else:
            self.ai = AdversarialAI(depth=depth)
            self.state = BattleState(
                player_hp=max(1, min(MAX_HP, player_hp)),
                npc_hp=enemy_base_hp)
            if player_potions is not None:
                self.state.player_potions = max(0, player_potions)
            if npc_potions is not None:
                self.state.npc_potions = max(0, npc_potions)
        from game.ambush.ui.battle_hud import BattleConfigHUD
        self.hud = BattleConfigHUD()
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
        self.fled = False  # True kalau player keluar (ESC) sebelum duel selesai
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
        if npc_buff is not None and npc_squad is not None:
            # Tampilkan buff aktif agar pengaruh squad terverifikasi di HUD.
            # Summary dihitung dengan config default (sama dengan yang
            # dipakai director di main.py); bila config di-custom, thread
            # config sebagai ganti menghitung ulang di sini.
            for line in summarize_squad(npc_squad, AmbushConfig()).lines()[:4]:
                self._add_log(f"Buff: {line}", GOLD)

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
        """Font cache agar tidak membuat Font baru tiap frame.

        Pakai custom_font (Tahap 3) bila tersedia, else fallback system font.
        """
        size = max(11, int(size))
        if size not in self._fonts:
            if self.custom_font is not None:
                path = getattr(self, "_custom_font_path", None)
                if path and os.path.exists(path):
                    self._fonts[size] = pygame.font.Font(path, size)
                else:
                    self._fonts[size] = self.custom_font
            else:
                name = "consolas" if pygame.font.match_font("consolas") else None
                self._fonts[size] = pygame.font.SysFont(name, size)
        return self._fonts[size]

    def _fit_text(
        self,
        font: pygame.font.Font,
        text: str,
        color: Tuple[int, int, int],
        max_w: int,
    ) -> pygame.Surface:
        """Render teks dan potong dengan ellipsis bila melebihi ``max_w``.

        Dipakai agar teks panjang (nama panjang, log panjang) tidak pernah
        menimpa elemen lain di panelnya.

        Args:
            font: Font untuk merender
            text: Teks asal
            color: Warna teks
            max_w: Lebar maksimum piksel yang boleh dipakai

        Returns:
            Surface teks yang lebarnya dijamin <= ``max_w``
        """
        surf = font.render(text, True, color)
        if surf.get_width() <= max_w:
            return surf
        ell = "..."
        trimmed = text
        while trimmed and font.size(trimmed + ell)[0] > max_w:
            trimmed = trimmed[:-1]
        return font.render(trimmed + ell if trimmed else ell, True, color)

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
        - - / =     : kurangi / tambah kedalaman pencarian AI (1..7)
        - ESC       : keluar dari Battle Mode walaupun duel belum selesai
        - Enter/Space (saat RESULT): tutup layar hasil dan kembali ke overworld
        - Tombol lain saat RESULT: diabaikan (layar hasil tidak keluar otomatis)
        """
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_d:
            self.debug.visible = not self.debug.visible
            return

        if event.key == pygame.K_h:
            self.hud.toggle()
            return

        if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._set_depth(-1)
            return

        if event.key in (
            pygame.K_EQUALS, pygame.K_PLUS,
            pygame.K_KP_EQUALS, pygame.K_KP_PLUS,
        ):
            self._set_depth(+1)
            return

        if event.key == pygame.K_ESCAPE:
            self._flee()
            return

        if self.phase == "RESULT":
            # Layar hasil tidak ditutup otomatis: hanya Enter/Space (atau ESC)
            # yang mengembalikan pemain ke overworld, jadi menang/kalah bisa
            # dibaca dulu tanpa terburu-buru.
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
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

    def _set_depth(self, delta: int) -> None:
        """Ubah kedalaman pencarian AI (tombol ``-`` / ``=``) lalu hitung ulang.

        Debug overlay dihitung ulang **pada state yang sama** dengan kedalaman
        baru, sehingga angka node minimax vs alpha-beta, pruning, cutoff, dan
        waktu bisa langsung dibandingkan antar kedalaman tanpa perlu menunggu
        giliran NPC berikutnya.

        Args:
            delta: +1 untuk menambah, -1 untuk mengurangi kedalaman
        """
        new_depth = max(DEPTH_MIN, min(DEPTH_MAX, self.depth + delta))
        if new_depth == self.depth:
            self._add_log(
                f"Kedalaman sudah di batas ({DEPTH_MIN}..{DEPTH_MAX}).", TEXT_DIM
            )
            return

        self.depth = new_depth
        self.ai.depth = new_depth

        # Hitung ulang untuk state sekarang agar overlay langsung berubah.
        # Perspektif selalu NPC (root MAX) supaya angka antar kedalaman
        # sebanding langsung; label di overlay ikut menuliskannya.
        if not self.state.is_terminal():
            self.ai_stats = self.ai.think(self.state, depth=self.depth)
            self.debug.update(self.ai_stats)

        self._add_log(
            f"Kedalaman pencarian -> {self.depth} (analisis NPC dihitung ulang)",
            TEXT,
        )

    def _flee(self) -> None:
        """Akhiri duel lebih awal & keluar dari Battle Mode (tombol ESC).

        Berlaku di semua fase (PLAYER_INPUT / NPC_THINK) sehingga player bisa
        kabur walaupun pertarungan belum selesai. Saat layar hasil (RESULT)
        sudah tampil, ESC hanya menutup layar hasil — sama seperti Enter —
        dan hasil menang/kalah tetap dihitung.

        Tidak menghitung menang/kalah; ``exit_battle()`` yang menangani
        status overworld (termasuk reset darah ke 100).
        """
        if self.phase == "RESULT":
            self.finished = True
            return
        self.fled = True
        self.winner = None
        self._add_log("Kamu meninggalkan duel.", TEXT_DIM)
        self.finished = True

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

        # ATTACK memakai damage acak 15-20 saat resolusi nyata.
        # State ber-buff (BuffBattleState) menerapkan bonus/cap/regen/armor/
        # weaken di dalam apply_action; chip lewat hook akhir giliran NPC.
        # Player dan NPC polos memakai aturan tahap 2 asli.
        if action == "ATTACK":
            dmg = random.randint(ATTACK_MIN, ATTACK_MAX)
            self.state = self.state.apply_action(
                is_npc, action, attack_damage=dmg)
        else:
            dmg = None
            self.state = self.state.apply_action(is_npc, action)
        # Visibilitas loadout player: bonus serangan & redaman per-hit
        # dicatat agar efek Sword/Shield terbaca (bukan angka misterius).
        if not is_npc and action in ("ATTACK", "SPECIAL") \
                and self.player_buff is not None:
            bonus = (self.player_buff.atk if action == "ATTACK"
                     else self.player_buff.spec)
            if bonus > 0:
                names = ", ".join(self.player_loadout.items
                                  ) if self.player_loadout is not None else ""
                self._add_log(f"Loadout +{bonus} dmg ({names}).", HEAL_COL)
                self.hud.ping("player")
        if is_npc and action in ("ATTACK", "SPECIAL") \
                and self.player_buff is not None \
                and self.player_buff.armor > 0:
            base = dmg if dmg is not None else SPECIAL_DAMAGE
            ditahan = base - int(math.ceil(base * (1.0 - self.player_buff.armor)))
            if ditahan > 0:
                self._add_log(f"Shield menahan {ditahan} dmg.", HEAL_COL)
                self.hud.ping("player")
        if is_npc:
            before_chip = self.state.player_hp
            apply_chip_hook(self.state, self.npc_buff)
            if self.state.player_hp < before_chip and self.npc_buff is not None:
                self._add_log(
                    f"Damage pasti musuh: {before_chip - self.state.player_hp}"
                    f" ke kamu.", (240, 200, 120))
                self.hud.ping("npc")
        else:
            before_chip = self.state.npc_hp
            apply_chip_hook(self.state, self.npc_buff)
            if self.state.npc_hp < before_chip:
                self._add_log(
                    f"Damage pasti item-mu: {before_chip - self.state.npc_hp}"
                    f" ke musuh.", (140, 240, 170))
                self.hud.ping("player")
            self.turn_no += 1

        if is_npc and self.npc_buff is not None and self.npc_buff.regen > 0:
            self._add_log(f"Musuh memulihkan {self.npc_buff.regen} HP "
                          f"tiap giliran (Spellcaster/Charm).", HEAL_COL)
            self.hud.ping("npc")
        if not is_npc and self.player_buff is not None \
                and self.player_buff.regen > 0:
            self._add_log(f"Loadout-mu memulihkan {self.player_buff.regen} HP.",
                          HEAL_COL)
            self.hud.ping("player")
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

        # Catatan: TIDAK ada lagi clamp "HP NPC minimum 80". Clamp lama
        # membuat HP musuh membeku di 80 setiap giliran NPC sehingga musuh
        # praktis tidak bisa dikalahkan. HP musuh kini bebas turun sampai 0.
        # HP MAKS tiap lawan baru = ENEMY_BASE_HP + buff.hp (AMANDEMEN-5:
        # base 70 + bonus HP peran; tak ada musuh yang 100 seperti player).

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
        self.hud.tick(dt)
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
            # Layar hasil sengaja TIDAK ditutup otomatis: duel baru berakhir
            # di overworld setelah pemain menekan Enter (lihat handle_event).
            # Timer tetap ditarik ke nol dipakai sebagai animasi fade-in.
            self.result_timer = max(0.0, self.result_timer - dt)

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

        # Data anggota untuk panel konfigurasi (HUD)
        npc_members = ([(r, it) for r, it in
                        zip(self.npc_squad.roles, self.npc_squad.items)]
                       if self.npc_squad is not None
                       else self._queue_member())
        player_items = (list(self.player_loadout.items)
                        if self.player_loadout is not None else [])

        # --- Sidebar tengah: info duel + strip antrean (pusat, rapi) ---
        # Digambar SEBELUM panel HP agar panel HP tidak menabrak teks tengah.
        self.hud.draw(canvas, font or self._get_font(w // 90),
                      player_items, npc_members,
                      self.player_buff, self.npc_buff,
                      self.turn_no, self.target, self.sim_rate,
                      queue_view=self.queue_view,
                      duel_label=self.duel_label,
                      y_top=getattr(self, "_hud_y", None),
                      item_sprites=self.item_sprites)
        hud_bottom = getattr(self.hud, "content_bottom",
                             getattr(self, "_hud_y", int(h * 0.14)))

        # Panel HP/stok/konfigurasi (di bawah sidebar tengah, simetris kiri
        # = PLAYER dan kanan = NPC). y_start diambil dari bawah HUD tengah
        # supaya tidak menabrak teks pesan/enem/item di tengah layar.
        self._draw_stats_panel(canvas, w, h, "npc", y_start=hud_bottom + 14)
        self._draw_stats_panel(canvas, w, h, "player", y_start=hud_bottom + 14)

        self._draw_action_menu(canvas, w, h)
        self._draw_log(canvas, w, h)
        self._draw_popups(canvas, w, h)

        # Layar hasil duel (tutup seluruh adegan, tak bisa dilewati otomatis).
        if self.phase == "RESULT":
            self._draw_result(canvas, w, h)

        # Debug overlay adversarial search di sisi kanan layar,
        # di bawah panel status NPC, di atas battle log, dan mulai dari luar
        # sprite NPC supaya tidak menutupi karakter maupun menu aksi.
        margin = 12
        top = 20 + int(h * 0.16) + margin
        bottom = h - 20 - int(h * 0.30) - margin
        left = int(w * 0.70) + 100
        right = w - 20
        safe = pygame.Rect(left, top, max(0, right - left), max(0, bottom - top))
        self.debug.draw(canvas, font or self._get_font(w // 90), safe)

    def _queue_member(self):
        """[(role, item)] musuh aktif antrean, else [] (panel + HUD)."""
        try:
            order = self.queue_view["order"]
            i = self.queue_view.get("idx", 0)
            return [tuple(order[i])]
        except (TypeError, IndexError, KeyError):
            return []

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

        # Surface latar dibuat dengan SRCALPHA: layar X11/window punya channel
        # alpha, dan bila latar dibuat tanpa SRCALPHA maka pikselnya bocor ke
        # layar dengan alpha 0. Akibatnya blit berikutnya (sprite, judul) hanya
        # di-copy alih-alih di-blend -> kotak hitam di balik sprite dan kotak
        # putih/hijau di balik judul. Fill dulu dengan warna opaque agar semua
        # piksel latar ber-alpha 255.
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        out.fill(BG_BOTTOM)
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
        """Gambar judul duel dan info turn di bagian tengah atas."""
        title_font = self._get_font(w // 40)
        turn_font = self._get_font(w // 70)
        buffered = self.npc_buff is not None or self.player_buff is not None

        # Indikator BOSS: tampilkan judul khusus jika lawan adalah Boss
        is_boss = "Boss" in self.npc_name
        if is_boss:
            title_text = "⚔️ BOSS BATTLE ⚔️"
            title_col = (240, 96, 96)
        else:
            title_text = "BATTLE DUEL (BUFF)" if buffered else "BATTLE DUEL"
            if self.duel_label:
                title_text += f" - {self.duel_label}"
            title_col = GOLD if buffered else TEXT
        title = title_font.render(title_text, True, title_col)
        title_y = int(h * 0.025)
        screen.blit(title, (w // 2 - title.get_width() // 2, title_y))

        # Label turn di bawah judul
        if self.phase == "PLAYER_INPUT":
            label, col = "GILIRANMU - pilih aksi", (140, 240, 170)
        elif self.phase == "NPC_THINK":
            label, col = f"{self.npc_name} BERPIKIR...", (240, 170, 120)
        else:
            label, col = "DUEL SELESAI", GOLD
        surf = turn_font.render(label, True, col)
        turn_y = title_y + title.get_height() + 8
        screen.blit(surf, (w // 2 - surf.get_width() // 2, turn_y))

        # Garis pemisah horizontal di bawah info judul
        line_y = turn_y + surf.get_height() + 10
        pygame.draw.line(
            screen, (60, 70, 90),
            (int(w * 0.15), line_y), (int(w * 0.85), line_y), 2
        )
        # _hud_y = batas bawah area judul; HUD sidebar tengah dimulai di sini.
        self._hud_y = line_y + 26

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

    def _icon_small(self, item_name: str, size: int = 20
                    ) -> Optional[pygame.Surface]:
        """Ikon item ukuran kecil untuk baris anggota panel HP (cache).

        Dipakai supaya baris peran/item rapi (ikon 20px di kolom kanan)
        tanpa memanggil smoothscale ulang tiap frame.
        """
        cache = getattr(self, "_icon_small_cache", None)
        if cache is None:
            cache = self._icon_small_cache = {}
        key = (item_name, size)
        if key not in cache:
            src = self.item_sprites.get(item_name)
            cache[key] = (pygame.transform.smoothscale(src, (size, size))
                          if src is not None else None)
        return cache[key]

    def _draw_stats_panel(self, screen: pygame.Surface, w: int, h: int, side: str,
                          y_start: Optional[int] = None) -> None:
        """Panel HP/stok potion/cooldown + (H) konfigurasi buff tahap 3.

        Dua panel ini simetris kiri (PLAYER) vs kanan (NPC) sesuai spek HUD:
        baris buff dibaca dari Buff yang SAMA dengan battle (bukan hitungan
        kedua), dan border menyala sesaat saat buff sisi itu terpicu.

        Args:
            y_start: Posisi Y atas panel. Jika None, pakai _hud_y + 12.
                     Digunakan agar panel HP tidak menabrak sidebar tengah.
        """
        is_npc = side == "npc"
        buff = self.npc_buff if is_npc else self.player_buff
        show_buff = self.hud.visible and buff is not None
        if is_npc and self.npc_squad is not None and self.hud.visible:
            members = [f"{r} [{it}]" for r, it in
                       zip(self.npc_squad.roles, self.npc_squad.items)
                       if r != "NONE"]
        elif is_npc and self.hud.visible:
            members = [f"{r} [{it}]" for r, it in self._queue_member()]
        elif not is_npc and self.player_loadout is not None \
                and self.hud.visible:
            members = [str(it) for it in self.player_loadout.items
                       if it != "NONE"] or ["tanpa item"]
        else:
            members = []
        from game.ambush.ui.battle_hud import buff_lines_short
        blines = buff_lines_short(buff, "npc" if is_npc else "player") \
            if show_buff else []
        small = self._get_font(w // 84)
        line_h = small.get_height() + 2
        # Baris anggota memuat ikon item 20px -> butuh tinggi ekstra agar
        # ikon dan teks tidak berdempetan.
        member_h = max(line_h, 24)
        n_mem = len(members[:2]) if self.hud.visible else 0
        n_buf = len(blines[:3])
        pw, ph = (int(w * 0.28),
                  int(h * 0.16) + n_mem * member_h + n_buf * line_h)
        x = int(w - 20 - pw) if is_npc else 20
        if y_start is not None:
            y = y_start
        else:
            y = getattr(self, "_hud_y", int(h * 0.14)) + 12
        rect = pygame.Rect(x, y, pw, ph)

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, PANEL_BG, panel.get_rect(), border_radius=14)
        flashing = (self.hud.flash_npc if is_npc else self.hud.flash_player) > 0
        edge = (255, 255, 160) if flashing else (
            (240, 130, 130) if is_npc else (120, 190, 255))
        pygame.draw.rect(panel, edge, panel.get_rect(),
                         3 if flashing else 2, border_radius=14)
        screen.blit(panel, rect.topleft)

        name_font = self._get_font(w // 62)

        title = (self.npc_name if is_npc else self.player_name)
        if show_buff:
            title += " (BUFF)"
        name = self._fit_text(name_font, title, edge, pw - 32)
        screen.blit(name, (x + 16, y + 12))

        # HP bar (cap memakai max-HP ter-buff tahap 3 di kedua sisi)
        hp = self.state.npc_hp if is_npc else self.state.player_hp
        cap = self.npc_max_hp if is_npc else self.player_max_hp
        bar_x, bar_y = x + 16, y + 12 + name.get_height() + 8
        bar_w, bar_h = pw - 32, max(14, ph // 7)
        ratio = max(0.0, min(1.0, hp / cap))
        col = HP_HIGH if ratio > 0.5 else (HP_MID if ratio > 0.25 else HP_LOW)

        pygame.draw.rect(screen, (16, 20, 30), (bar_x, bar_y, bar_w, bar_h), border_radius=bar_h // 2)
        if ratio > 0:
            pygame.draw.rect(
                screen, col, (bar_x, bar_y, int(bar_w * ratio), bar_h), border_radius=bar_h // 2
            )
        pygame.draw.rect(screen, PANEL_EDGE, (bar_x, bar_y, bar_w, bar_h), 1, border_radius=bar_h // 2)
        hp_txt = small.render(f"{hp}/{cap}", True, (12, 16, 24) if ratio > 0.5 else TEXT)
        screen.blit(hp_txt, (bar_x + bar_w // 2 - hp_txt.get_width() // 2, bar_y + bar_h // 2 - hp_txt.get_height() // 2))

        info_y = bar_y + bar_h + 8
        potions = self.state.npc_potions if is_npc else self.state.player_potions
        cd = self.state.npc_special_cd if is_npc else self.state.player_special_cd
        defending = self.state.npc_defending if is_npc else self.state.player_defending

        inner_l, inner_r = x + 16, x + pw - 16
        text_right = inner_r

        if defending:
            badge = small.render("DEFEND (1)", True, (10, 16, 24))
            chip_w, chip_h = badge.get_width() + 16, badge.get_height() + 6
            chip = pygame.Rect(inner_r - chip_w, info_y - 2, chip_w, chip_h)
            pygame.draw.rect(screen, (96, 190, 240), chip, border_radius=8)
            screen.blit(badge, (chip.x + 8, info_y + 1))
            text_right = chip.x - 10

        potion_txt = self._fit_text(
            small,
            f"Potion: {potions}/{POTION_LIMIT}",
            HEAL_COL if potions else TEXT_DIM,
            max(24, text_right - inner_l),
        )
        screen.blit(potion_txt, (inner_l, info_y))

        cd_label = "Special: siap" if cd == 0 else f"Special CD: {cd}"
        cd_x = inner_l + potion_txt.get_width() + 18
        if cd_x + 20 < text_right:
            cd_txt = self._fit_text(
                small, cd_label, GOLD if cd == 0 else TEXT_DIM, text_right - cd_x
            )
            screen.blit(cd_txt, (cd_x, info_y))

        # Baris konfigurasi tahap 3 (H): anggota + efek angka (maks 5 baris).
        # Layout dirapikan: SEMUA teks rata kiri sejajar dengan baris
        # Potion/efek; ikon item berdiri di kolom KANAN panel (lebar tetap)
        # sehingga baris peran/item tidak lagi tampak menjorok acak.
        by = info_y + small.get_height() + 6
        inner_w = pw - 32
        if self.hud.visible:
            for m in members[:2]:
                raw = str(m)
                if "[" in raw and "]" in raw:
                    # Sisi NPC: "Role [Item]" -> peran + item dipisah warna.
                    role_txt = display_role(raw.split("[")[0].strip())
                    item_txt = raw.split("[")[1].split("]")[0]
                    if item_txt == "NONE":
                        item_txt = ""
                elif raw.strip() == "tanpa item":
                    role_txt, item_txt = "tanpa item", ""
                else:
                    # Sisi player: daftar item loadout (tanpa peran).
                    role_txt, item_txt = "", raw.strip()
                icon = self._icon_small(item_txt) if item_txt else None
                icon_w = (icon.get_width() + 8) if icon is not None else 0
                avail = inner_w - icon_w
                parts = []
                if role_txt:
                    parts.append((role_txt,
                                  TEXT_DIM if role_txt == "tanpa item"
                                  else TEXT))
                if item_txt:
                    if role_txt and role_txt != "tanpa item":
                        parts.append((" - ", TEXT_DIM))
                    parts.append((item_txt, GOLD))
                plain = "".join(t for t, _c in parts)
                if small.size(plain)[0] <= avail:
                    x_acc = inner_l
                    for t, c in parts:
                        surf = small.render(t, True, c)
                        screen.blit(surf, (x_acc, by))
                        x_acc += surf.get_width()
                else:  # terlalu panjang: potong sebagai satu warna
                    screen.blit(self._fit_text(small, plain, TEXT, avail),
                                (inner_l, by))
                if icon is not None:
                    # Ikon item rata kanan (kolom tetap) di tengah baris,
                    # dengan alas lembut agar ikon gelap tetap terbaca.
                    icon_rect = icon.get_rect(
                        midright=(inner_r, by + small.get_height() // 2))
                    slot_bg = pygame.Surface(
                        (icon.get_width() + 8, icon.get_height() + 8),
                        pygame.SRCALPHA)
                    pygame.draw.rect(slot_bg, (255, 255, 255, 22),
                                     slot_bg.get_rect(), border_radius=6)
                    pygame.draw.rect(slot_bg, (255, 255, 255, 40),
                                     slot_bg.get_rect(), 1, border_radius=6)
                    screen.blit(slot_bg, (icon_rect.x - 4, icon_rect.y - 4))
                    screen.blit(icon, icon_rect)
                by += member_h
            for line, col in blines[:3]:
                surf = self._fit_text(small, line, col, inner_w)
                screen.blit(surf, (inner_l, by))
                by += line_h
            if buff is None and not members:
                surf = self._fit_text(small, "polos (tanpa buff) [H]",
                                      TEXT_DIM, inner_w)
                screen.blit(surf, (inner_l, by))

    def _draw_action_menu(self, screen: pygame.Surface, w: int, h: int) -> None:
        """Kotak menu aksi player di kiri bawah."""
        mw, mh = int(w * 0.34), int(h * 0.30)
        x, y = 20, h - 20 - mh
        rect = pygame.Rect(x, y, mw, mh)

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, PANEL_BG, panel.get_rect(), border_radius=14)
        pygame.draw.rect(panel, PANEL_EDGE, panel.get_rect(), 1, border_radius=14)
        screen.blit(panel, rect.topleft)

        pad = 14
        head_font = self._get_font(w // 70)
        head = self._fit_text(head_font, "AKSI  (1-4 / panah + Enter)", ACCENT, mw - pad * 2)
        screen.blit(head, (x + pad, y + 10))

        # Opsi keluar dari Battle Mode sebelum duel selesai
        esc_font = self._get_font(w // 86)
        esc_hint = self._fit_text(
            esc_font, "ESC: keluar dari duel (belum selesai)", GOLD, mw - pad * 2
        )
        screen.blit(esc_hint, (x + pad, y + 10 + head.get_height() + 4))

        key_font = self._get_font(w // 82)
        # Nilai depth sekarang ikut ditampilkan supaya pemain bisa memantau
        # perubahannya tanpa harus membuka debug overlay.
        hint = self._fit_text(
            key_font, f"D: debug overlay  |  depth {self.depth}", TEXT_DIM, mw - pad * 2
        )
        # Keterangan kontrol kedalaman pencarian AI: - menurunkan, + menaikkan.
        # Ditampilkan di menu aksi supaya pemain tahu tanpa harus membuka overlay.
        depth_hint = self._fit_text(
            key_font,
            f"[-] turunkan depth | [+] naikkan depth ({DEPTH_MIN}-{DEPTH_MAX})",
            GOLD,
            mw - pad * 2,
        )

        legal = set(self.legal_actions())
        label_font = self._get_font(w // 66)

        top = y + 10 + head.get_height() + esc_hint.get_height() + 12
        hint_y = y + mh - pad - (depth_hint.get_height() + 4 + hint.get_height())
        usable = hint_y - 8 - top
        item_h = max(22, usable // len(ACTIONS))

        for i, action in enumerate(ACTIONS):
            iy = top + i * item_h
            item = pygame.Rect(x + 12, iy, mw - 24, min(item_h - 6, hint_y - 8 - iy))
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

            # Info jumlah/efek aksi (mis. DMG 15-20, +25 HP, DMG 30)
            info = ACTION_INFO[action]
            if action == "POTION":
                info = f"{info}  x{self.state.player_potions}"
            elif action == "SPECIAL":
                cd = self.state.player_special_cd
                info = f"{info}  CD{cd}" if cd > 0 else f"{info}  siap"
            info_col = (120, 220, 140) if ok else (200, 120, 120)

            info = self._fit_text(key_font, info, info_col, max(24, item.width // 2))
            label = self._fit_text(
                label_font, ACTION_LABEL[action], col,
                item.right - 20 - info.get_width() - (chip.right + 12) - 10,
            )
            mid = item.centery
            screen.blit(label, (chip.right + 12, mid - label.get_height() // 2))
            screen.blit(info, (item.right - info.get_width() - 10, mid - info.get_height() // 2))

        screen.blit(depth_hint, (x + mw - depth_hint.get_width() - pad, hint_y))
        screen.blit(
            hint,
            (x + mw - hint.get_width() - pad, hint_y + depth_hint.get_height() + 4),
        )

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
        head = font.render("BATTLE LOG", True, GOLD)
        screen.blit(head, (x + 14, y + 10))

        line_h = font.get_height() + 4
        start_y = y + 10 + head.get_height() + 8
        max_w = lw - 28
        # Log singkat: maksimal 5 baris terakhir (spek Fase 6).
        max_lines = min(5, max(1, (y + lh - 12 - start_y) // line_h))
        for i, (text, color) in enumerate(self.log[-max_lines:]):
            surf = self._fit_text(font, text, color, max_w)
            screen.blit(surf, (x + 14, start_y + i * line_h))

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
        """Overlay layar hasil duel.

        Layar ini tidak pernah menutup sendiri: hasil menang/kalah/seri tetap
        terpasang sampai pemain menekan Enter (atau ESC). Di duel antrean,
        Enter membuka layar hasil + musuh berikutnya; di duel biasa, Enter
        kembali ke overworld. ``result_timer`` hanya animasi fade-in.
        """
        t = max(0.0, min(1.0, (RESULT_DELAY - self.result_timer) / 0.4))

        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((4, 6, 12, int(180 * t)))
        screen.blit(veil, (0, 0))

        big = self._get_font(w // 26)
        queue_mode = bool(self.duel_label)
        if self.fled:
            text, col = "KAMU KABUR", TEXT_DIM
            sub = "Meninggalkan duel sebelum selesai"
        elif self.winner == "player":
            text, col = "KAMU MENANG!", (140, 240, 170)
            sub = ("Musuh tumbang - lanjut ke musuh berikutnya" if queue_mode
                   else "Musuh tumbang - HP dipulihkan penuh")
        elif self.winner == "npc":
            text, col = "KAMU KALAH...", (240, 120, 120)
            sub = ("Kamu tumbang - pertemuan antrean berakhir" if queue_mode
                   else "HP dipulihkan penuh saat kembali")
        else:
            text, col = "SERI", GOLD
            sub = "Duel berakhir imbang"
        surf = big.render(text, True, col)
        surf.set_alpha(int(255 * t))
        screen.blit(surf, (w // 2 - surf.get_width() // 2, int(h * 0.38)))

        small = self._get_font(w // 70)
        s2 = small.render(sub, True, TEXT)
        s2.set_alpha(int(255 * t))
        screen.blit(s2, (w // 2 - s2.get_width() // 2, int(h * 0.38) + surf.get_height() + 10))

        hint = self._get_font(w // 84).render(
            "Tekan Enter untuk lihat hasil & lanjut" if queue_mode
            else "Tekan Enter untuk kembali ke overworld", True, TEXT_DIM
        )
        screen.blit(hint, (w // 2 - hint.get_width() // 2, int(h * 0.38) + surf.get_height() + s2.get_height() + 22))
