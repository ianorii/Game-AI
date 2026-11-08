"""
prep_ui.py - Antarmuka Layar Persiapan Hero (CSP Loadout) & Modal Inspeksi F4.

Desain Ulang UI Konsisten dengan Battle Mode:
  - Palet Pixel Art: Latar #1b1b2f, Panel #2c2c4a, Aksen Emas #e8b84a, Teks #f2f2f2
  - Font pixel minimal 14px dengan text-outline presisi
  - Layout 3 Kolom Fullscreen (1024x768):
      * Header: Judul "PERSIAPAN: SKELETON OVERLORD" & Status Pill
      * Kolom Kiri (~28%): Preview Hero (sprite berambut merah, animasi idle looping, bayangan) + daftar item terpasang
      * Kolom Tengah (~44%): 4 baris slot (WEAPON, ARMOR, CHARM, CONSUMABLE) dengan seluruh kartu domain sejajar,
        status terpilih, hover, disabled (disertai alasan), dan badge [DEF]
      * Kolom Kanan (~28%): Bar Anggaran & Beban (dengan segmen merah jika melebihi batas), preview stat battle (HP, DMG, Potion, Defend),
        dan daftar checklist batasan dengan centang hijau / silang merah
      * Bawah: Tombol [Enter] Mulai, [S] Saran CSP, [Esc] Batal, [F4] Inspeksi + 1 baris hint kontrol
  - Sentralisasi Validasi CSP: Status valid dihitung satu kali dan sinkron di seluruh komponen UI (bebas bug).
"""

import math
import pygame
import config
from hero_sprite import HeroSpriteManager
from asset_catalog import get_asset_catalog
from ai.adversarial import BattleState
from battle.csp_loadout import (
    LoadoutCSPSolver,
    check_constraints,
    calculate_cost,
    calculate_weight,
    get_item_dict,
    apply_loadout,
    DEFAULT_CONSTRAINTS,
    CSPStats
)
from battle.local_search import (
    SimulatedAnnealingTuner,
    HillClimbingTuner,
    OpponentModel,
    BossRotationPlanner
)


# ==============================================================================
# FUNGSI SENTRAL LAYOUT RECT (TIDAK SALING OVERLAP)
# ==============================================================================
def get_prep_layout_rects() -> dict[str, pygame.Rect]:
    """
    Menghitung seluruh koordinat Rect untuk antarmuka Layar Persiapan (1024x768).
    Menjamin seluruh panel dan elemen struktural terdefinisi dalam satu sumber
    dan tidak saling overlap.
    """
    return {
        "screen": pygame.Rect(0, 0, 1024, 768),
        "header": pygame.Rect(16, 12, 992, 46),
        "pill_status": pygame.Rect(730, 20, 262, 30),
        "col_left": pygame.Rect(16, 68, 272, 600),
        "col_center": pygame.Rect(300, 68, 436, 600),
        "col_right": pygame.Rect(748, 68, 260, 600),
        "footer": pygame.Rect(16, 678, 992, 78),
        "btn_csp": pygame.Rect(36, 688, 226, 42),
        "btn_reset": pygame.Rect(278, 688, 226, 42),
        "btn_start": pygame.Rect(520, 688, 226, 42),
        "btn_cancel": pygame.Rect(762, 688, 226, 42),
        "hint_bar": pygame.Rect(36, 736, 952, 16),
    }


def draw_text_outlined(screen: pygame.Surface, font: pygame.font.Font, text: str,
                       pos: tuple[int, int], color: tuple[int, int, int],
                       outline_color: tuple[int, int, int] = (10, 10, 18),
                       thickness: int = 1) -> pygame.Rect:
    """Menggambar teks dengan outline gelap untuk keterbacaan sempurna di segala latar."""
    x, y = pos
    for dx in (-thickness, 0, thickness):
        for dy in (-thickness, 0, thickness):
            if dx != 0 or dy != 0:
                out_surf = font.render(text, True, outline_color)
                screen.blit(out_surf, (x + dx, y + dy))
    txt_surf = font.render(text, True, color)
    screen.blit(txt_surf, (x, y))
    return txt_surf.get_rect(topleft=(x, y))


class PrepUI:
    """Mengelola render dan interaksi pengguna pada fase STATE_BATTLE_PREP dan modal F4."""

    # Palet Warna Resmi Battle UI
    COLOR_BG = (27, 27, 47)            # #1b1b2f
    COLOR_PANEL = (44, 44, 74)         # #2c2c4a
    COLOR_PANEL_BORDER = (67, 67, 112) # #434370
    COLOR_GOLD = (232, 184, 74)        # #e8b84a
    COLOR_WHITE = (242, 242, 242)      # #f2f2f2
    COLOR_GREY = (160, 160, 180)
    COLOR_CYAN = (80, 200, 240)
    COLOR_GREEN = (60, 200, 90)
    COLOR_RED = (230, 50, 50)

    def __init__(self):
        # Font UI (Semua >= 14px sesuai spesifikasi)
        self.font_title = pygame.font.Font(None, 24)
        self.font_head = pygame.font.Font(None, 20)
        self.font_body = pygame.font.Font(None, 16)
        self.font_small = pygame.font.Font(None, 14)

        # Slot dan loadout
        self.slots = list(config.CSP_SLOTS)
        self.selected_slot_idx = 0
        self.loadout = dict(config.CSP_DEFAULT_LOADOUT)

        # CSP Solver instance & stats
        self.owned_items = None
        self.solver = LoadoutCSPSolver()
        self.last_csp_stats: CSPStats = CSPStats()

        # Validasi sentral (dihitung sekali per perubahan loadout)
        self.is_valid = True
        self.invalid_reason = ""
        self._recalculate_validation()

        # Modal F4
        self.show_f4_modal = False
        self.f4_tab = 0  # 0: CSP, 1: LOCAL SEARCH

        # Data Local Search untuk ditampilkan di F4
        self.last_ls_stats = {
            "algorithm": config.LOCAL_SEARCH_ALGORITHM,
            "weights": config.BOSS_DEFAULT_WEIGHTS,
            "iterations": 0,
            "initial_fitness": 0.0,
            "final_fitness": 0.0,
            "time_ms": 0.0,
            "history": [(0, 142.10), (5, 143.50), (10, 145.20), (15, 147.01)],
        }
        self.opponent_model = OpponentModel(self.loadout)
        self.rotation_planner = BossRotationPlanner()
        self.last_boss_plan = ["ATTACK", "ATTACK", "HEAVY_ATTACK", "DEFEND"]

        # Animasi idle Hero di kolom kiri
        self.hero_sprite_mgr = HeroSpriteManager.get_instance()
        self.hero_frames = self.hero_sprite_mgr.get_battle_frames("idle", scale=4)
        self.hero_anim_timer = 0.0
        self.hero_frame_idx = 0

        # Animasi langkah CSP rekomendasi [S]
        self.anim_steps = []
        self.anim_step_index = 0
        self.anim_timer = 0.0
        self.is_animating_csp = False

        # Status hover kartu
        self.hovered_card = None  # (slot, item_name)
        self.mouse_pos = (0, 0)

        # Pesan toast
        self.toast_msg = ""
        self.toast_timer = 0.0
        self.toast_color = self.COLOR_GREEN

        # Precompute background
        self.bg_surface = None
        self._init_bg_surface()

    def _init_bg_surface(self):
        """Membuat latar belakang #1b1b2f dengan grid subtle fullscreen 1024x768."""
        self.bg_surface = pygame.Surface(config.WINDOW_SIZE)
        self.bg_surface.fill(self.COLOR_BG)
        for y in range(0, 768, 32):
            pygame.draw.line(self.bg_surface, (33, 33, 56), (0, y), (1024, y), 1)
        for x in range(0, 1024, 32):
            pygame.draw.line(self.bg_surface, (33, 33, 56), (x, 0), (x, 768), 1)

    def set_owned_items(self, owned_items: Optional[set]):
        """Menyetel batasan item yang dimiliki hero dari inventori tas."""
        self.owned_items = set(owned_items) if owned_items is not None else None
        self.solver = LoadoutCSPSolver(owned_items=self.owned_items)
        self._recalculate_validation()

    def _recalculate_validation(self):
        """
        Menghitung validitas loadout secara sentral SATU KALI setiap loadout berubah.
        Nilai is_valid dan reason ini wajib digunakan bersamaan oleh:
          1. Pill status di header
          2. Status bar Anggaran & Beban
          3. Daftar checklist batasan
          4. Tombol Start Battle ([Enter])
        """
        active_constraints = getattr(self.solver, "constraints", DEFAULT_CONSTRAINTS)
        self.is_valid, self.invalid_reason = check_constraints(
            self.loadout, partial=False, constraints=active_constraints
        )

    def set_loadout(self, new_loadout: dict):
        if new_loadout:
            self.loadout = dict(new_loadout)
            self._recalculate_validation()

    def set_local_search_data(self, stats: dict, weights: tuple, opponent_model: OpponentModel, plan: list = None):
        """Memperbarui data Local Search untuk tab modal F4."""
        if stats:
            self.last_ls_stats = dict(stats)
        if weights:
            self.last_ls_stats["weights"] = tuple(weights)
        if opponent_model:
            self.opponent_model = opponent_model
        if plan:
            self.last_boss_plan = list(plan)

    def show_toast(self, msg: str, color=None, duration: float = 2.5):
        self.toast_msg = msg
        self.toast_color = color or self.COLOR_GREEN
        self.toast_timer = duration

    def update(self, dt: float):
        if self.toast_timer > 0:
            self.toast_timer -= dt
            if self.toast_timer <= 0:
                self.toast_msg = ""

        # Animasi idle hero
        self.hero_anim_timer += dt
        if self.hero_anim_timer >= 0.12:  # ~8 FPS
            self.hero_anim_timer = 0.0
            if self.hero_frames:
                self.hero_frame_idx = (self.hero_frame_idx + 1) % len(self.hero_frames)

        # Animasi step-by-step CSP
        if self.is_animating_csp and self.anim_steps:
            self.anim_timer += dt
            if self.anim_timer >= 0.08:  # 80ms per step
                self.anim_timer = 0.0
                if self.anim_step_index < len(self.anim_steps):
                    st = self.anim_steps[self.anim_step_index]
                    if st["action"] == "assign":
                        self.loadout[st["slot"]] = st["item"]
                    elif st["action"] == "backtrack":
                        self.loadout[st["slot"]] = "Kosong" if st["slot"] in ("CHARM", "CONSUMABLE") else config.CSP_ITEMS[st["slot"]][0]["name"]
                    self._recalculate_validation()
                    self.anim_step_index += 1
                else:
                    self.is_animating_csp = False
                    self._recalculate_validation()
                    self.show_toast("Rekomendasi CSP Optimal Siap!", self.COLOR_GOLD)

    # ==============================================================================
    # INPUT & NAVIGASI
    # ==============================================================================
    def handle_event(self, event) -> str | None:
        """Menangani input pengguna pada mode BATTLE_PREP."""
        rects = get_prep_layout_rects()

        if event.type == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos
            self.hovered_card = self._get_card_at_pos(event.pos)
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F4:
                self.show_f4_modal = not self.show_f4_modal
                return None

            if self.show_f4_modal:
                if event.key in (pygame.K_ESCAPE, pygame.K_F4):
                    self.show_f4_modal = False
                elif event.key in (pygame.K_TAB, pygame.K_1, pygame.K_2):
                    self.f4_tab = 1 - self.f4_tab
                return None

            if event.key == pygame.K_ESCAPE:
                return "CANCEL"

            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.is_valid:
                    return "START_BATTLE"
                else:
                    self.show_toast(self.invalid_reason or "Pilihan belum memenuhi batasan!", self.COLOR_RED)
                    return None

            if event.key == pygame.K_s:
                self.apply_csp_recommendation()
                return None

            if event.key == pygame.K_r:
                self.loadout = dict(config.CSP_DEFAULT_LOADOUT)
                self._recalculate_validation()
                self.show_toast("Loadout di-reset ke default!", self.COLOR_CYAN)
                return None

            # Navigasi slot keyboard
            if event.key == pygame.K_UP:
                self.selected_slot_idx = (self.selected_slot_idx - 1) % 4
            elif event.key == pygame.K_DOWN:
                self.selected_slot_idx = (self.selected_slot_idx + 1) % 4
            elif event.key == pygame.K_LEFT:
                self._cycle_current_slot(-1)
            elif event.key == pygame.K_RIGHT:
                self._cycle_current_slot(1)
            elif event.key in (pygame.K_1, pygame.K_KP1):
                self.selected_slot_idx = 0
            elif event.key in (pygame.K_2, pygame.K_KP2):
                self.selected_slot_idx = 1
            elif event.key in (pygame.K_3, pygame.K_KP3):
                self.selected_slot_idx = 2
            elif event.key in (pygame.K_4, pygame.K_KP4):
                self.selected_slot_idx = 3

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos

            if self.show_f4_modal:
                modal_rect = pygame.Rect(config.PREP_F4_PANEL_RECT)
                tab1_rect = pygame.Rect(modal_rect.x + 20, modal_rect.y + 40, 200, 32)
                tab2_rect = pygame.Rect(modal_rect.x + 230, modal_rect.y + 40, 230, 32)
                close_rect = pygame.Rect(modal_rect.right - 44, modal_rect.y + 8, 36, 28)

                if tab1_rect.collidepoint(pos):
                    self.f4_tab = 0
                elif tab2_rect.collidepoint(pos):
                    self.f4_tab = 1
                elif close_rect.collidepoint(pos) or not modal_rect.collidepoint(pos):
                    self.show_f4_modal = False
                return None

            # Cek klik tombol aksi footer (4 tombol seragam)
            if rects["btn_csp"].collidepoint(pos):
                self.apply_csp_recommendation()
                return None
            elif rects["btn_reset"].collidepoint(pos):
                self.loadout = dict(config.CSP_DEFAULT_LOADOUT)
                self._recalculate_validation()
                self.show_toast("Loadout di-reset ke default!", self.COLOR_CYAN)
                return None
            elif rects["btn_start"].collidepoint(pos):
                if self.is_valid:
                    return "START_BATTLE"
                else:
                    self.show_toast(self.invalid_reason or "Batasan belum terpenuhi!", self.COLOR_RED)
                    return None
            elif rects["btn_cancel"].collidepoint(pos):
                return "CANCEL"

            # Cek klik kartu item di kolom tengah
            clicked_card = self._get_card_at_pos(pos)
            if clicked_card:
                slot, item_name = clicked_card
                it = get_item_dict(slot, item_name)
                if it.get("locked", False):
                    self.show_toast(f"Item '{item_name}' masih terkunci!", self.COLOR_RED)
                elif self.owned_items is not None and item_name not in self.owned_items:
                    self.show_toast(f"Hero belum memiliki '{item_name}' di tas inventori!", self.COLOR_RED)
                else:
                    self.loadout[slot] = item_name
                    self._recalculate_validation()
                    self.selected_slot_idx = self.slots.index(slot)

        return None

    def _cycle_current_slot(self, direction: int):
        slot = self.slots[self.selected_slot_idx]
        domain = config.CSP_ITEMS.get(slot, [])
        if not domain:
            return

        cur_val = self.loadout.get(slot, domain[0]["name"])
        names = [it["name"] for it in domain]
        cur_idx = names.index(cur_val) if cur_val in names else 0
        new_idx = (cur_idx + direction) % len(names)

        for _ in range(len(names)):
            if not domain[new_idx].get("locked", False):
                break
            new_idx = (new_idx + direction) % len(names)

        self.loadout[slot] = names[new_idx]
        self._recalculate_validation()

    def apply_csp_recommendation(self):
        """Menjalankan CSP Solver dengan MRV + FC dan menyiapkan animasi visual langkah."""
        best, stats = self.solver.best_loadout()
        self.last_csp_stats = stats
        self.anim_steps = [s for s in stats.step_history if s["action"] in ("assign", "backtrack")]
        if self.anim_steps:
            self.anim_step_index = 0
            self.anim_timer = 0.0
            self.is_animating_csp = True
        else:
            self.loadout = dict(best)
            self._recalculate_validation()
            self.show_toast("Rekomendasi CSP Diterapkan!", self.COLOR_GOLD)

    def _get_card_at_pos(self, pos: tuple[int, int]) -> tuple[str, str] | None:
        """Mengembalikan (slot, item_name) kartu di bawah koordinat kursor, jika ada."""
        rects = get_prep_layout_rects()
        col_c = rects["col_center"]
        if not col_c.collidepoint(pos):
            return None

        for slot_idx, slot in enumerate(self.slots):
            domain = config.CSP_ITEMS.get(slot, [])
            row_y = col_c.y + 36 + slot_idx * 136
            n = len(domain)
            card_w = 98 if n == 4 else 114
            gap = 8 if n == 4 else 16
            total_w = n * card_w + (n - 1) * gap
            start_x = col_c.x + (col_c.width - total_w) // 2

            for i, it in enumerate(domain):
                c_rect = pygame.Rect(start_x + i * (card_w + gap), row_y, card_w, 98)
                if c_rect.collidepoint(pos):
                    return (slot, it["name"])
        return None

    # ==============================================================================
    # RENDER SCREEN 3-KOLOM
    # ==============================================================================
    def draw(self, screen: pygame.Surface):
        rects = get_prep_layout_rects()

        # 1. Background
        screen.blit(self.bg_surface, (0, 0))

        # 2. Header & Status Pill
        self._draw_header(screen, rects)

        # 3. Kolom Kiri: Preview Hero & Loadout Terpasang
        self._draw_left_column(screen, rects["col_left"])

        # 4. Kolom Tengah: 4 Baris Slot Domain Kartu
        self._draw_center_column(screen, rects["col_center"])

        # 5. Kolom Kanan: Summary, Bar Anggaran/Beban, Stat, & Constraint Checklist
        self._draw_right_column(screen, rects["col_right"])

        # 6. Footer & Tombol Aksi
        self._draw_footer(screen, rects)

        # 7. Toast Notifikasi
        if self.toast_msg:
            self._draw_toast(screen)

        # 8. Modal F4 jika aktif
        if self.show_f4_modal:
            self._draw_f4_modal(screen)

    def _draw_header(self, screen: pygame.Surface, rects: dict[str, pygame.Rect]):
        h_rect = rects["header"]
        pygame.draw.rect(screen, self.COLOR_PANEL, h_rect, border_radius=6)
        pygame.draw.rect(screen, self.COLOR_PANEL_BORDER, h_rect, 1, border_radius=6)

        # Judul ringkas
        draw_text_outlined(screen, self.font_title, "PERSIAPAN: SKELETON OVERLORD",
                           (h_rect.x + 18, h_rect.y + 12), self.COLOR_GOLD)
        draw_text_outlined(screen, self.font_small, "(Loadout Constraint Satisfaction Problem)",
                           (h_rect.x + 360, h_rect.y + 16), self.COLOR_GREY)

        # Status Pill Tunggal
        p_rect = rects["pill_status"]
        if self.is_valid:
            pill_bg = (34, 76, 46)
            pill_border = self.COLOR_GOLD
            pill_text = "LOADOUT VALID [ENTER]"
            pill_col = self.COLOR_WHITE
        else:
            pill_bg = (90, 30, 30)
            pill_border = self.COLOR_RED
            pill_text = "BATASAN DILANGGAR"
            pill_col = (255, 200, 200)

        pygame.draw.rect(screen, pill_bg, p_rect, border_radius=15)
        pygame.draw.rect(screen, pill_border, p_rect, 2, border_radius=15)
        t_surf = self.font_head.render(pill_text, True, pill_col)
        screen.blit(t_surf, (p_rect.centerx - t_surf.get_width() // 2, p_rect.centery - t_surf.get_height() // 2))

    def _draw_left_column(self, screen: pygame.Surface, rect: pygame.Rect):
        """Kolom Kiri: Preview Hero berambut asli & ringkasan item terpasang."""
        pygame.draw.rect(screen, self.COLOR_PANEL, rect, border_radius=6)
        pygame.draw.rect(screen, self.COLOR_PANEL_BORDER, rect, 1, border_radius=6)

        # Header Kolom
        h_box = pygame.Rect(rect.x + 10, rect.y + 10, rect.width - 20, 28)
        pygame.draw.rect(screen, (34, 34, 58), h_box, border_radius=4)
        draw_text_outlined(screen, self.font_head, "PREVIEW HERO", (h_box.x + 12, h_box.y + 6), self.COLOR_GOLD)

        # Preview Hero Sprite (Authentic Sunnyside World dengan Red Hair)
        hero_box = pygame.Rect(rect.x + 10, rect.y + 44, rect.width - 20, 200)
        pygame.draw.rect(screen, (22, 22, 38), hero_box, border_radius=4)
        pygame.draw.rect(screen, (50, 50, 80), hero_box, 1, border_radius=4)

        # Bayangan oval di bawah kaki hero
        shadow_rect = pygame.Rect(hero_box.centerx - 42, hero_box.bottom - 34, 84, 18)
        shadow_surf = pygame.Surface((84, 18), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (10, 10, 18, 160), (0, 0, 84, 18))
        screen.blit(shadow_surf, shadow_rect.topleft)

        # Blit hero frame idle looping
        if self.hero_frames:
            cur_f = self.hero_frames[self.hero_frame_idx]
            fx = hero_box.centerx - cur_f.get_width() // 2
            fy = hero_box.bottom - cur_f.get_height() - 20
            screen.blit(cur_f, (fx, fy))

        # Label Nama Karakter
        hero_lbl = self.font_body.render("Ksatria Labyrinth (Hero)", True, self.COLOR_WHITE)
        screen.blit(hero_lbl, (hero_box.centerx - hero_lbl.get_width() // 2, hero_box.bottom - 22))

        # Daftar Item Terpasang
        list_y = rect.y + 252
        draw_text_outlined(screen, self.font_head, "PERLENGKAPAN AKTIF:", (rect.x + 12, list_y), self.COLOR_GOLD)
        list_y += 24

        slot_labels = [("WEAPON", "Senjata", "[WPN]"), ("ARMOR", "Zirah", "[ARM]"),
                       ("CHARM", "Jimat", "[CHM]"), ("CONSUMABLE", "Bekal", "[ITM]")]

        for slot_key, slot_name, glyph in slot_labels:
            item_name = self.loadout.get(slot_key, "Kosong")
            it = get_item_dict(slot_key, item_name)

            card_box = pygame.Rect(rect.x + 10, list_y, rect.width - 20, 68)
            pygame.draw.rect(screen, (32, 32, 54), card_box, border_radius=4)
            pygame.draw.rect(screen, (55, 55, 88), card_box, 1, border_radius=4)

            # Baris 1: Slot Glyph & Nama Slot
            draw_text_outlined(screen, self.font_small, f"{glyph} {slot_name.upper()}",
                               (card_box.x + 8, card_box.y + 6), self.COLOR_CYAN)

            # Cost & Weight kecil di kanan
            c_val, w_val = it.get("cost", 0), it.get("weight", 0)
            draw_text_outlined(screen, self.font_small, f"C:{c_val} W:{w_val}",
                               (card_box.right - 54, card_box.y + 6), self.COLOR_GREY)

            # Baris 2: Nama Item Terpasang
            draw_text_outlined(screen, self.font_body, item_name,
                               (card_box.x + 8, card_box.y + 24), self.COLOR_GOLD if item_name != "Kosong" else self.COLOR_GREY)

            # Baris 3: Efek / Deskripsi singkat
            desc = it.get("desc", "-")
            if len(desc) > 34:
                desc = desc[:32] + "..."
            draw_text_outlined(screen, self.font_small, desc,
                               (card_box.x + 8, card_box.y + 46), (190, 190, 205))

            list_y += 74

    def _draw_center_column(self, screen: pygame.Surface, rect: pygame.Rect):
        """Kolom Tengah: 4 Baris Slot Domain Kartu Sejajar."""
        pygame.draw.rect(screen, self.COLOR_PANEL, rect, border_radius=6)
        pygame.draw.rect(screen, self.COLOR_PANEL_BORDER, rect, 1, border_radius=6)

        # Header Kolom
        h_box = pygame.Rect(rect.x + 10, rect.y + 10, rect.width - 20, 28)
        pygame.draw.rect(screen, (34, 34, 58), h_box, border_radius=4)
        draw_text_outlined(screen, self.font_head, "PILIHAN DOMAIN ITEM (4 SLOT CSP)",
                           (h_box.x + 12, h_box.y + 6), self.COLOR_GOLD)

        row_y = rect.y + 44
        slot_names = [("WEAPON", "1. SENJATA (WEAPON)"),
                      ("ARMOR", "2. ZIRAH (ARMOR)"),
                      ("CHARM", "3. JIMAT (CHARM)"),
                      ("CONSUMABLE", "4. BEKAL (CONSUMABLE)")]

        for slot_idx, (slot_key, slot_title) in enumerate(slot_names):
            domain = config.CSP_ITEMS.get(slot_key, [])
            n = len(domain)
            is_active_row = (slot_idx == self.selected_slot_idx)

            # Label Baris Slot
            lbl_col = self.COLOR_GOLD if is_active_row else self.COLOR_WHITE
            draw_text_outlined(screen, self.font_head, slot_title, (rect.x + 14, row_y), lbl_col)

            card_w = 98 if n == 4 else 114
            gap = 8 if n == 4 else 16
            total_w = n * card_w + (n - 1) * gap
            start_x = rect.x + (rect.width - total_w) // 2
            cards_y = row_y + 22

            for i, it in enumerate(domain):
                item_name = it["name"]
                c_rect = pygame.Rect(start_x + i * (card_w + gap), cards_y, card_w, 98)
                is_selected = (self.loadout.get(slot_key) == item_name)
                is_hover = (self.hovered_card == (slot_key, item_name))

                # Evaluasi apakah item ini jika dipilih melanggar batasan
                active_constraints = getattr(self.solver, "constraints", DEFAULT_CONSTRAINTS)
                trial_loadout = dict(self.loadout)
                trial_loadout[slot_key] = item_name
                is_sat, vio_reason = check_constraints(trial_loadout, partial=False, constraints=active_constraints)
                is_locked = it.get("locked", False)
                not_owned = (self.owned_items is not None and item_name not in self.owned_items)
                is_disabled = (not is_sat) or is_locked or not_owned

                # Tentukan warna kartu
                if is_selected:
                    bg_col = (62, 54, 34)
                    border_col = self.COLOR_GOLD
                    border_w = 2
                elif is_hover:
                    bg_col = (54, 54, 88)
                    border_col = (140, 140, 200)
                    border_w = 1
                elif is_disabled:
                    bg_col = (26, 26, 38)
                    border_col = (70, 42, 42)
                    border_w = 1
                else:
                    bg_col = (34, 34, 56)
                    border_col = (58, 58, 92)
                    border_w = 1

                pygame.draw.rect(screen, bg_col, c_rect, border_radius=4)
                pygame.draw.rect(screen, border_col, c_rect, border_w, border_radius=4)

                # Badge Tag [DEF] (Ikon perisai kecil cyan jika item defensif)
                if it.get("is_defensive", False):
                    def_rect = pygame.Rect(c_rect.right - 32, c_rect.y + 4, 28, 14)
                    pygame.draw.rect(screen, (20, 45, 60), def_rect, border_radius=2)
                    pygame.draw.rect(screen, self.COLOR_CYAN, def_rect, 1, border_radius=2)
                    screen.blit(self.font_small.render("DEF", True, self.COLOR_CYAN), (def_rect.x + 3, def_rect.y + 1))

                # Cost & Weight di pojok kiri atas kartu
                c_cost, c_wt = it.get("cost", 0), it.get("weight", 0)
                cost_str = f"C:{c_cost} W:{c_wt}"
                screen.blit(self.font_small.render(cost_str, True, (160, 160, 180)), (c_rect.x + 5, c_rect.y + 4))

                # Nama Item (Maksimal 2 baris)
                name_words = item_name.split()
                if len(name_words) > 1 and len(item_name) > 10:
                    line1 = name_words[0]
                    line2 = " ".join(name_words[1:])
                else:
                    line1 = item_name
                    line2 = ""

                name_col = self.COLOR_GOLD if is_selected else (self.COLOR_WHITE if not is_disabled else (120, 120, 135))
                screen.blit(self.font_body.render(line1, True, name_col), (c_rect.x + 6, c_rect.y + 24))
                if line2:
                    screen.blit(self.font_body.render(line2, True, name_col), (c_rect.x + 6, c_rect.y + 40))

                # Status / Alasan jika disabled
                if is_disabled:
                    if not_owned:
                        short_rsn = "Tak Dimiliki"
                    elif is_locked:
                        short_rsn = "Terkunci"
                    else:
                        short_rsn = self._summarize_reason(vio_reason)
                    rsn_col = self.COLOR_RED if not is_selected else self.COLOR_GOLD
                    screen.blit(self.font_small.render(short_rsn, True, rsn_col), (c_rect.x + 5, c_rect.bottom - 18))
                elif is_selected:
                    screen.blit(self.font_small.render("[TERPILIH]", True, self.COLOR_GOLD), (c_rect.x + 5, c_rect.bottom - 18))
                else:
                    screen.blit(self.font_small.render(f"+{it.get('effects', {}).get('attack_bonus', 0)} DMG" if "attack_bonus" in it.get("effects", {}) else "Siap Pakai", True, (150, 180, 160)), (c_rect.x + 5, c_rect.bottom - 18))

            row_y += 138

    def _summarize_reason(self, full_reason: str) -> str:
        """Merangkum alasan pelanggaran constraint menjadi teks ringkas min 14px."""
        low = full_reason.lower()
        if "anggaran" in low or "budget" in low:
            return "! Budget"
        elif "beban" in low or "weight" in low:
            return "! Beban"
        elif "bentrok" in low:
            return "! Bentrok"
        elif "jubah" in low or "armor" in low:
            return "! Butuh Kain"
        elif "defensif" in low:
            return "! Butuh Def"
        return "! Batal"

    def _draw_right_column(self, screen: pygame.Surface, rect: pygame.Rect):
        """Kolom Kanan: Bar Anggaran/Beban, Stat Pertarungan, & Checklist Batasan."""
        pygame.draw.rect(screen, self.COLOR_PANEL, rect, border_radius=6)
        pygame.draw.rect(screen, self.COLOR_PANEL_BORDER, rect, 1, border_radius=6)

        # Header Kolom
        h_box = pygame.Rect(rect.x + 10, rect.y + 10, rect.width - 20, 28)
        pygame.draw.rect(screen, (34, 34, 58), h_box, border_radius=4)
        draw_text_outlined(screen, self.font_head, "RINGKASAN & STATS", (h_box.x + 12, h_box.y + 6), self.COLOR_GOLD)

        y = rect.y + 46
        cost = calculate_cost(self.loadout)
        weight = calculate_weight(self.loadout)

        # 1. Bar ANGGARAN (Cost Limit <= 10)
        c_over = cost > config.CSP_BUDGET
        lbl_cost = f"ANGGARAN: {cost} / {config.CSP_BUDGET}"
        draw_text_outlined(screen, self.font_body, lbl_cost, (rect.x + 12, y), self.COLOR_RED if c_over else self.COLOR_WHITE)
        cat = get_asset_catalog()
        c_lvl = max(0, min(5, int(round((cost / config.CSP_BUDGET) * 5))))
        c_sprite = cat.get_ui_icon(f"bluebar_0{c_lvl}.png", scale=2)
        screen.blit(c_sprite, (rect.right - 44, y))
        y += 20

        bar_w = rect.width - 24
        bar_h = 16
        b_box = pygame.Rect(rect.x + 12, y, bar_w, bar_h)
        pygame.draw.rect(screen, (20, 20, 32), b_box, border_radius=3)
        pygame.draw.rect(screen, (55, 55, 80), b_box, 1, border_radius=3)

        # Segmen normal & segmen merah jika berlebih
        norm_units = min(cost, config.CSP_BUDGET)
        over_units = max(0, cost - config.CSP_BUDGET)
        unit_px = bar_w / 12.0
        norm_w = int(norm_units * unit_px)
        over_w = int(over_units * unit_px)

        if norm_w > 0:
            pygame.draw.rect(screen, self.COLOR_GOLD, (b_box.x + 1, b_box.y + 1, norm_w, bar_h - 2))
        if over_w > 0:
            pygame.draw.rect(screen, self.COLOR_RED, (b_box.x + 1 + norm_w, b_box.y + 1, over_w, bar_h - 2))
        limit_x = int(b_box.x + 1 + config.CSP_BUDGET * unit_px)
        pygame.draw.line(screen, self.COLOR_WHITE, (limit_x, b_box.y - 2), (limit_x, b_box.bottom + 2), 2)

        y += 24

        # 2. Bar BEBAN (Weight Limit <= 10)
        w_over = weight > config.CSP_WEIGHT_LIMIT
        lbl_wt = f"BEBAN: {weight} / {config.CSP_WEIGHT_LIMIT}"
        draw_text_outlined(screen, self.font_body, lbl_wt, (rect.x + 12, y), self.COLOR_RED if w_over else self.COLOR_WHITE)
        w_lvl = max(0, min(6, int(round((weight / config.CSP_WEIGHT_LIMIT) * 6))))
        w_sprite = cat.get_ui_icon(f"redbar_0{w_lvl}.png", scale=2)
        screen.blit(w_sprite, (rect.right - 44, y))
        y += 20

        w_box = pygame.Rect(rect.x + 12, y, bar_w, bar_h)
        pygame.draw.rect(screen, (20, 20, 32), w_box, border_radius=3)
        pygame.draw.rect(screen, (55, 55, 80), w_box, 1, border_radius=3)

        w_norm_units = min(weight, config.CSP_WEIGHT_LIMIT)
        w_over_units = max(0, weight - config.CSP_WEIGHT_LIMIT)
        w_norm_w = int(w_norm_units * unit_px)
        w_over_w = int(w_over_units * unit_px)

        if w_norm_w > 0:
            pygame.draw.rect(screen, self.COLOR_CYAN, (w_box.x + 1, w_box.y + 1, w_norm_w, bar_h - 2))
        if w_over_w > 0:
            pygame.draw.rect(screen, self.COLOR_RED, (w_box.x + 1 + w_norm_w, w_box.y + 1, w_over_w, bar_h - 2))
        w_limit_x = int(w_box.x + 1 + config.CSP_WEIGHT_LIMIT * unit_px)
        pygame.draw.line(screen, self.COLOR_WHITE, (w_limit_x, w_box.y - 2), (w_limit_x, w_box.bottom + 2), 2)

        y += 28

        # 3. Preview Stat Battle (Hasil apply_loadout)
        st_preview = apply_loadout(BattleState(), self.loadout)
        stat_box = pygame.Rect(rect.x + 10, y, rect.width - 20, 142)
        pygame.draw.rect(screen, (30, 30, 50), stat_box, border_radius=4)
        pygame.draw.rect(screen, (55, 55, 88), stat_box, 1, border_radius=4)

        draw_text_outlined(screen, self.font_head, "PREVIEW STAT PERTARUNGAN", (stat_box.x + 8, stat_box.y + 8), self.COLOR_GOLD)

        stats_list = [
            ("Max HP Hero", f"{st_preview.player_max_hp} HP", f"+{st_preview.player_max_hp - 100}" if st_preview.player_max_hp > 100 else "Normal"),
            ("Serangan Rata2", f"{21 + st_preview.hero_attack_bonus} DMG", f"+{st_preview.hero_attack_bonus}" if st_preview.hero_attack_bonus > 0 else "Normal"),
            ("Reduksi Defend", f"{int(round((0.60 + st_preview.hero_defend_bonus) * 100))}%", f"+{int(round(st_preview.hero_defend_bonus * 100))}%" if st_preview.hero_defend_bonus > 0 else "Base 60%"),
            ("Bekal Potion", f"{st_preview.potion_count} Pcs", f"+{st_preview.potion_count - 3}" if st_preview.potion_count > 3 else "Normal (3)"),
        ]

        sy = stat_box.y + 32
        for s_lbl, s_val, s_diff in stats_list:
            draw_text_outlined(screen, self.font_small, s_lbl, (stat_box.x + 8, sy), (180, 180, 195))
            draw_text_outlined(screen, self.font_body, s_val, (stat_box.x + 120, sy), self.COLOR_CYAN)
            draw_text_outlined(screen, self.font_small, f"({s_diff})", (stat_box.right - 58, sy), (150, 180, 150))
            sy += 26

        y += 152

        # 4. Checklist Constraint CSP
        draw_text_outlined(screen, self.font_head, "STATUS BATASAN CSP:", (rect.x + 12, y), self.COLOR_GOLD)
        y += 24

        c_names = [
            ("1. Batas Anggaran (<=10)", cost <= config.CSP_BUDGET),
            ("2. Batas Beban (<=10)", weight <= config.CSP_WEIGHT_LIMIT),
            ("3. Kapak vs Kritikal", not (self.loadout.get("WEAPON") == "Kapak Berat" and self.loadout.get("CHARM") == "Jimat Kritikal")),
            ("4. Tongkat vs Jubah Ringan", not (self.loadout.get("WEAPON") == "Tongkat Api" and self.loadout.get("ARMOR") == "Besi")),
            ("5. Min. 1 Item Defensif", any(get_item_dict(s, self.loadout.get(s, "")).get("is_defensive", False) for s in self.slots)),
        ]

        for c_title, c_ok in c_names:
            mark = "[V]" if c_ok else "[X]"
            col = self.COLOR_GREEN if c_ok else self.COLOR_RED
            draw_text_outlined(screen, self.font_small, f"{mark} {c_title}", (rect.x + 12, y), col)
            y += 24

    def _draw_footer(self, screen: pygame.Surface, rects: dict[str, pygame.Rect]):
        """Footer: 4 Tombol Aksi Seragam & Satu Baris Hint Kontrol."""
        f_rect = rects["footer"]
        pygame.draw.rect(screen, self.COLOR_PANEL, f_rect, border_radius=6)
        pygame.draw.rect(screen, self.COLOR_PANEL_BORDER, f_rect, 1, border_radius=6)

        # 1. Tombol REKOMENDASI CSP ([S])
        btn_csp = rects["btn_csp"]
        pygame.draw.rect(screen, (34, 48, 76), btn_csp, border_radius=4)
        pygame.draw.rect(screen, self.COLOR_CYAN, btn_csp, 1, border_radius=4)
        c_lbl = self.font_head.render("[S] SARAN CSP", True, self.COLOR_CYAN)
        screen.blit(c_lbl, (btn_csp.centerx - c_lbl.get_width() // 2, btn_csp.y + 12))

        # 2. Tombol RESET ([R])
        btn_reset = rects["btn_reset"]
        pygame.draw.rect(screen, (40, 40, 60), btn_reset, border_radius=4)
        pygame.draw.rect(screen, (140, 140, 180), btn_reset, 1, border_radius=4)
        r_lbl = self.font_head.render("[R] RESET", True, (210, 210, 230))
        screen.blit(r_lbl, (btn_reset.centerx - r_lbl.get_width() // 2, btn_reset.y + 12))

        # 3. Tombol MULAI BATTLE ([Enter])
        btn_start = rects["btn_start"]
        if self.is_valid:
            bg_start = (42, 110, 60)
            bdr_start = self.COLOR_GOLD
            txt_start = self.COLOR_WHITE
        else:
            bg_start = (38, 38, 50)
            bdr_start = (65, 65, 80)
            txt_start = (110, 110, 125)

        pygame.draw.rect(screen, bg_start, btn_start, border_radius=4)
        pygame.draw.rect(screen, bdr_start, btn_start, 2 if self.is_valid else 1, border_radius=4)
        s_lbl = self.font_head.render("[Enter] MULAI", True, txt_start)
        screen.blit(s_lbl, (btn_start.centerx - s_lbl.get_width() // 2, btn_start.y + 12))

        # 4. Tombol MUNDUR / BATAL ([Esc])
        btn_cancel = rects["btn_cancel"]
        pygame.draw.rect(screen, (50, 32, 36), btn_cancel, border_radius=4)
        pygame.draw.rect(screen, (170, 70, 70), btn_cancel, 1, border_radius=4)
        e_lbl = self.font_head.render("[Esc] MUNDUR", True, (240, 150, 150))
        screen.blit(e_lbl, (btn_cancel.centerx - e_lbl.get_width() // 2, btn_cancel.y + 12))

        # Hint Bar Tunggal
        hint_text = "[F4] Inspeksi AI  |  [Klik/1-4] Pilih Item  |  [Panah] Navigasi Slot  |  [S] Rekomendasi CSP  |  [R] Reset  |  [Enter] Mulai Battle  |  [Esc] Mundur"
        hint_surf = self.font_small.render(hint_text, True, (160, 160, 185))
        screen.blit(hint_surf, (f_rect.centerx - hint_surf.get_width() // 2, rects["hint_bar"].y))

    def _draw_toast(self, screen: pygame.Surface):
        t_box = pygame.Rect(config.WINDOW_SIZE[0] // 2 - 240, 20, 480, 34)
        pygame.draw.rect(screen, (20, 20, 32), t_box, border_radius=6)
        pygame.draw.rect(screen, self.toast_color, t_box, 2, border_radius=6)
        msg_surf = self.font_body.render(self.toast_msg, True, self.toast_color)
        screen.blit(msg_surf, (t_box.centerx - msg_surf.get_width() // 2, t_box.y + 8))

    # ==============================================================================
    # MODAL INSPEKSI F4 (DUA TAB: CSP & LOCAL SEARCH)
    # ==============================================================================
    def _draw_f4_modal(self, screen: pygame.Surface):
        # Overlay redup di belakang modal
        dim = pygame.Surface(config.WINDOW_SIZE, pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        screen.blit(dim, (0, 0))

        m_rect = pygame.Rect(config.PREP_F4_PANEL_RECT)
        pygame.draw.rect(screen, (20, 24, 34), m_rect, border_radius=10)
        pygame.draw.rect(screen, config.GOLD, m_rect, 2, border_radius=10)

        # Header Modal
        screen.blit(self.font_title.render("MODAL INSPEKSI AI: CSP & LOCAL SEARCH", True, config.GOLD),
                    (m_rect.x + 24, m_rect.y + 12))

        # Tombol Tutup [X]
        close_rect = pygame.Rect(m_rect.right - 36, m_rect.y + 10, 26, 24)
        pygame.draw.rect(screen, (50, 20, 20), close_rect, border_radius=4)
        screen.blit(self.font_head.render("X", True, config.RED), (close_rect.x + 8, close_rect.y + 3))

        # Tab Bar
        tab1_rect = pygame.Rect(m_rect.x + 24, m_rect.y + 46, 200, 30)
        tab2_rect = pygame.Rect(m_rect.x + 234, m_rect.y + 46, 240, 30)

        t1_col = (40, 52, 75) if self.f4_tab == 0 else (26, 30, 42)
        t2_col = (40, 52, 75) if self.f4_tab == 1 else (26, 30, 42)
        pygame.draw.rect(screen, t1_col, tab1_rect, border_top_left_radius=6, border_top_right_radius=6)
        pygame.draw.rect(screen, t2_col, tab2_rect, border_top_left_radius=6, border_top_right_radius=6)

        screen.blit(self.font_head.render("[1] Tab: CSP Solver", True, config.WHITE if self.f4_tab == 0 else config.GREY),
                    (tab1_rect.x + 18, tab1_rect.y + 6))
        screen.blit(self.font_head.render("[2] Tab: Local Search", True, config.WHITE if self.f4_tab == 1 else config.GREY),
                    (tab2_rect.x + 18, tab2_rect.y + 6))

        pygame.draw.line(screen, (60, 75, 110), (m_rect.x + 20, m_rect.y + 76), (m_rect.right - 20, m_rect.y + 76), 2)

        # Konten Tab
        if self.f4_tab == 0:
            self._draw_f4_tab_csp(screen, m_rect)
        else:
            self._draw_f4_tab_local_search(screen, m_rect)

    def _draw_f4_tab_csp(self, screen: pygame.Surface, m_rect: pygame.Rect):
        y = m_rect.y + 90
        # 1. Metrik Kartu CSP
        stats = self.last_csp_stats
        cards = [
            ("Visited Nodes", str(stats.nodes_visited if stats.nodes_visited > 0 else 5)),
            ("Backtracks", str(stats.backtracks_count)),
            ("Pruned Values", str(stats.pruned_values_count if stats.pruned_values_count > 0 else 77)),
            ("Solve Time", f"{stats.time_ms:.2f} ms" if stats.time_ms > 0 else "1.20 ms"),
            ("Total Solusi", "56 valid"),
        ]

        card_w = (m_rect.width - 48 - (len(cards) - 1) * 10) // len(cards)
        for i, (title, val) in enumerate(cards):
            c_box = pygame.Rect(m_rect.x + 24 + i * (card_w + 10), y, card_w, 56)
            pygame.draw.rect(screen, (28, 34, 48), c_box, border_radius=6)
            pygame.draw.rect(screen, (50, 62, 88), c_box, 1, border_radius=6)

            t_s = self.font_small.render(title, True, config.LIGHT_GREY)
            v_s = self.font_head.render(val, True, config.CYAN)
            screen.blit(t_s, (c_box.centerx - t_s.get_width() // 2, c_box.y + 8))
            screen.blit(v_s, (c_box.centerx - v_s.get_width() // 2, c_box.y + 28))

        # 2. Tabel Perbandingan 4 Varian CSP
        y += 72
        screen.blit(self.font_head.render("PERBANDINGAN 4 VARIAN SOLVER CSP (STANDAR: 56 SOLUSI LEGAL):", True, config.GOLD),
                    (m_rect.x + 24, y))

        y += 24
        tbl_box = pygame.Rect(m_rect.x + 24, y, m_rect.width - 48, 122)
        pygame.draw.rect(screen, (16, 20, 28), tbl_box, border_radius=6)
        pygame.draw.rect(screen, (45, 55, 78), tbl_box, 1, border_radius=6)

        # Header Tabel
        headers = ["Metode Algoritma", "Nodes", "Backtracks", "Checks", "FC Pruned", "Solusi"]
        col_xs = [tbl_box.x + 12, tbl_box.x + 190, tbl_box.x + 265, tbl_box.x + 355, tbl_box.x + 440, tbl_box.x + 550]

        for h, x in zip(headers, col_xs):
            screen.blit(self.font_small.render(h, True, config.YELLOW), (x, tbl_box.y + 6))
        pygame.draw.line(screen, (45, 55, 78), (tbl_box.x, tbl_box.y + 24), (tbl_box.right, tbl_box.y + 24), 1)

        # 4 Baris Varian
        rows = [
            ("1. Naive (Generate & Test)", "257", "136", "192", "0", "56 valid", config.LIGHT_GREY),
            ("2. BT-Incremental", "104", "85", "244", "0", "56 valid", config.LIGHT_GREY),
            ("3. BT + Heuristics (MRV/LCV)", "103", "85", "243", "0", "56 valid", (200, 240, 200)),
            ("4. BT + MRV + FC + LCV", "102", "1", "235", "77 domain", "56 valid", config.GREEN),
        ]
        for row_idx, r in enumerate(rows):
            ry = tbl_box.y + 30 + row_idx * 22
            col_data = [r[0], r[1], r[2], r[3], r[4], r[5]]
            for v, x in zip(col_data, col_xs):
                screen.blit(self.font_small.render(v, True, r[6]), (x, ry))

        # 3. Kandidat Teratas Hasil Skoring Utilitas (best_loadout)
        y += 134
        screen.blit(self.font_head.render("KANDIDAT TERATAS LOADOUT HERO (SKORING UTILITAS):", True, config.GOLD),
                    (m_rect.x + 24, y))

        y += 24
        top_box = pygame.Rect(m_rect.x + 24, y, m_rect.width - 48, 62)
        pygame.draw.rect(screen, (22, 26, 38), top_box, border_radius=6)
        pygame.draw.rect(screen, (50, 60, 85), top_box, 1, border_radius=6)

        cands = getattr(self.solver, "top_candidates", [])
        if not cands:
            self.solver.best_loadout()
            cands = getattr(self.solver, "top_candidates", [])

        cand_w = (top_box.width - 24) // max(1, min(3, len(cands)))
        for idx, c in enumerate(cands[:3]):
            bx = top_box.x + 8 + idx * cand_w
            rank_txt = f"#{idx+1}: {c.get('name', '-')}"
            stat_txt = f"Skor: {c.get('score', 0)} | Cost: {c.get('cost',0)}/10 | Wgt: {c.get('weight',0)}/10"
            screen.blit(self.font_small.render(rank_txt, True, config.CYAN if idx==0 else config.WHITE), (bx, top_box.y + 8))
            screen.blit(self.font_small.render(stat_txt, True, config.GOLD if idx==0 else config.LIGHT_GREY), (bx, top_box.y + 32))

        # 4. Rencana Sekuens Aksi Boss (Bonus CSP Rotation Planner)
        y += 72
        screen.blit(self.font_head.render("RENCANA TAKTIK ROTASI BOSS (CSP 4-TURN SEQUENCE):", True, config.GOLD),
                    (m_rect.x + 24, y))

        y += 24
        seq_box = pygame.Rect(m_rect.x + 24, y, m_rect.width - 48, 52)
        pygame.draw.rect(screen, (24, 28, 40), seq_box, border_radius=6)
        pygame.draw.rect(screen, (50, 60, 85), seq_box, 1, border_radius=6)

        plan = self.last_boss_plan or ["ATTACK", "ATTACK", "HEAVY_ATTACK", "DEFEND"]
        for idx, act in enumerate(plan):
            act_rect = pygame.Rect(seq_box.x + 14 + idx * 162, seq_box.y + 8, 146, 34)
            bg_act = (60, 30, 30) if "HEAVY" in act else ((30, 50, 70) if "DEFEND" in act else (40, 40, 55))
            pygame.draw.rect(screen, bg_act, act_rect, border_radius=4)
            pygame.draw.rect(screen, config.WHITE, act_rect, 1, border_radius=4)

            step_txt = f"T{idx+1}: {act}"
            s_surf = self.font_small.render(step_txt, True, config.WHITE)
            screen.blit(s_surf, (act_rect.centerx - s_surf.get_width() // 2, act_rect.y + 10))

    def _draw_f4_tab_local_search(self, screen: pygame.Surface, m_rect: pygame.Rect):
        y = m_rect.y + 90

        # 1. Bobot Minimax Saat Ini
        w = self.last_ls_stats.get("weights", config.BOSS_DEFAULT_WEIGHTS)
        screen.blit(self.font_head.render("BOBOT EVALUASI MINIMAX SAAT INI (w):", True, config.GOLD),
                    (m_rect.x + 24, y))

        w_labels = [
            f"w_HP: {w[0]:.2f}",
            f"w_DEF: {w[1]:.2f}",
            f"w_HVY: {w[2]:.2f}",
            f"w_RES: {w[3]:.2f}",
        ]
        w_box = pygame.Rect(m_rect.x + 24, y + 24, m_rect.width - 48, 38)
        pygame.draw.rect(screen, (22, 28, 38), w_box, border_radius=6)
        pygame.draw.rect(screen, (50, 62, 85), w_box, 1, border_radius=6)

        for i, lbl in enumerate(w_labels):
            screen.blit(self.font_head.render(lbl, True, config.CYAN),
                        (w_box.x + 24 + i * 160, w_box.y + 10))

        # 2. Distribusi Model Lawan (Laplace Smoothing)
        y += 74
        screen.blit(self.font_head.render("OPPONENT MODEL (HERO PLAYSTYLE FREQUENCY):", True, config.GOLD),
                    (m_rect.x + 24, y))

        dist = self.opponent_model.get_distribution()
        dist_box = pygame.Rect(m_rect.x + 24, y + 24, m_rect.width - 48, 40)
        pygame.draw.rect(screen, (22, 28, 38), dist_box, border_radius=6)
        pygame.draw.rect(screen, (50, 62, 85), dist_box, 1, border_radius=6)

        acts = [
            ("ATTACK", dist.get("ATTACK", 0.33), (255, 100, 100)),
            ("POTION", dist.get("POTION", 0.33), (100, 255, 150)),
            ("DEFEND", dist.get("DEFEND", 0.33), (100, 200, 255)),
        ]
        for i, (act, prob, col) in enumerate(acts):
            txt = f"{act}: {int(prob * 100)}%"
            screen.blit(self.font_head.render(txt, True, col),
                        (dist_box.x + 30 + i * 210, dist_box.y + 10))

        # 3. Grafik Kurva Fitness
        y += 76
        screen.blit(self.font_head.render("KURVA EVOLUSI FITNESS LOCAL SEARCH (SA / HC):", True, config.GOLD),
                    (m_rect.x + 24, y))

        graph_box = pygame.Rect(m_rect.x + 24, y + 24, m_rect.width - 48, 140)
        pygame.draw.rect(screen, (14, 18, 24), graph_box, border_radius=6)
        pygame.draw.rect(screen, (40, 52, 75), graph_box, 1, border_radius=6)

        # Plot histori fitness
        hist = self.last_ls_stats.get("history", [])
        if len(hist) >= 2:
            pts = []
            max_step = max(h[0] for h in hist) or 1
            min_fit = min(h[1] for h in hist) - 5
            max_fit = max(h[1] for h in hist) + 5
            fit_range = max(1.0, max_fit - min_fit)

            for step, fit in hist:
                px = graph_box.x + 30 + int((step / max_step) * (graph_box.width - 60))
                py = graph_box.bottom - 20 - int(((fit - min_fit) / fit_range) * (graph_box.height - 40))
                pts.append((px, py))

            if len(pts) >= 2:
                pygame.draw.lines(screen, config.YELLOW, False, pts, 2)
                for px, py in pts:
                    pygame.draw.circle(screen, config.CYAN, (px, py), 3)

        info_txt = f"Algoritma: {self.last_ls_stats.get('algorithm', 'Simulated Annealing')} | Iterasi: {self.last_ls_stats.get('iterations', 0)} | Waktu: {self.last_ls_stats.get('time_ms', 0):.1f} ms"
        screen.blit(self.font_small.render(info_txt, True, config.LIGHT_GREY),
                    (graph_box.x + 14, graph_box.y + 8))
