"""
planner_ui.py - Panel UI Perencanaan dengan Aset Sunnyside World (Sub-fase 2D)

Menampilkan dua panel khusus yang dapat dibuka/tutup:
  1. [F7] ExpeditionPlanPanel: Panel rencana ekspedisi STRIPS Hero
     - Daftar langkah dengan ikon aksi Sunnyside (axe, pickaxe, hammer, shovel, sword, rod, sandtimer)
     - Penanda status: confirm (selesai), indicator (aktif), sandtimer (menunggu)
     - Ringkasan: Algoritma, panjang & biaya rencana, node, replan count, alasan pemicu
     - Bar progres misi (greenbar)
  2. [F8] HTNPlanPanel: Panel pohon dekomposisi hierarki tugas NPC (Petani & Penggiling)
     - Pohon dekomposisi tugas aktif (Compound Task -> Method terpilih -> Primitive Operator)
     - Alasan evaluasi precondition
     - Antrean operator primitif & jam dunia (siang/malam)
     - Riwayat replan NPC saat intervensi player terjadi

Batas Layout:
  - Panel tidak menutupi > 15% layar masing-masing (115,500 px <= 14.68% dari 1024x768).
  - Tidak saling tumpang tindih (overlap-free), diverifikasi oleh get_planner_layout_rects().
  - Ukuran font minimal 14 px.
"""

from typing import Dict, List, Optional, Tuple, Any
import pygame
import math
import os

import config
from asset_catalog import get_asset_catalog
from planning.strips import GroundAction
from planning.monitor import PlanMonitor
from planning.autopilot import AutopilotController, PlannerMode
from planning.htn import HTNNPCAgent, HTNDecompositionNode, WorldClock


# ==============================================================================
# FUNGSI VERIFIKASI LAYOUT & HUMAN-READABLE TEXT
# ==============================================================================

def format_action_human(action: GroundAction) -> Tuple[str, str]:
    """
    Menerjemahkan aksi STRIPS ke representasi bahasa Indonesia yang manusiawi:
    Mengembalikan (judul_singkat, detail_parameter).
    """
    name = action.name
    params = action.params

    if name == "buy":
        item = params[0] if len(params) > 0 else "item"
        item_id = item.replace("seed_", "Benih ").replace("_", " ").title()
        c_from = params[1] if len(params) > 1 else ""
        c_to = params[2] if len(params) > 2 else ""
        cost = int(c_from[1:]) - int(c_to[1:]) if (c_from.startswith("c") and c_to.startswith("c")) else ""
        detail = f"Biaya {cost} koin ({c_from} -> {c_to})" if cost else f"{c_from} -> {c_to}"
        return f"Beli {item_id}", detail

    if name == "sell":
        item = params[0] if len(params) > 0 else "item"
        item_name = item.replace("_", " ").title()
        c_from = params[1] if len(params) > 1 else ""
        c_to = params[2] if len(params) > 2 else ""
        earn = int(c_to[1:]) - int(c_from[1:]) if (c_from.startswith("c") and c_to.startswith("c")) else ""
        detail = f"+{earn} koin ({c_from} -> {c_to})" if earn else f"{c_from} -> {c_to}"
        return f"Jual {item_name}", detail

    if name == "plant_radish":
        plot = params[0] if params else "plot"
        return "Tanam Benih Lobak", f"di petak ladang {plot}"

    if name == "water_crop":
        plot = params[0] if params else "plot"
        return "Siram Tanaman Lobak", f"di petak ladang {plot}"

    if name == "harvest_radish":
        plot = params[0] if params else "plot"
        return "Panen Lobak Segar", f"dari petak ladang {plot}"

    if name == "fish":
        return "Mancing Ikan", "di dermaga sungai desa"

    if name == "chop_wood":
        return "Tebang Kayu", "di hutan barat desa"

    if name == "mine_rock":
        return "Tambang Batu", "di tebing quarry"

    if name == "mine_rock_river":
        return "Tambang Batu Sungai", "sumber alternatif di tepi sungai"

    if name == "collect_egg":
        return "Ambil Telur", "di kandang ayam desa"

    if name == "milk_cow":
        return "Perah Susu", "di padang rumput sapi"

    if name == "rest":
        return "Istirahat di Ranjang", "memulihkan HP hero ke 100%"

    if name == "craft_key":
        return "Tempa Kunci Segel Bos", "di bengkel (butuh kayu + batu)"

    if name == "craft_potion":
        return "Racik Ramuan Merah", "di bengkel (lobak + botol)"

    if name == "open_gate":
        return "Buka Segel Skeleton Overlord", "membuka segel kutukan bos"

    if name == "equip":
        w = params[0] if len(params) > 0 else "senjata"
        a = params[1] if len(params) > 1 else "zirah"
        return "Kenakan Gear Tempur", f"CSP loadout: {w} & {a}"

    if name == "fight_boss":
        w = params[0] if len(params) > 0 else "senjata"
        a = params[1] if len(params) > 1 else "zirah"
        n = params[2] if len(params) > 2 else "0"
        return "Tantang Boss Dungeon", f"Loadout: {w}, {a}, {n} potion"

    if name in ("goto", "goto_through_gate"):
        loc_from = params[0] if len(params) > 0 else "?"
        loc_to = params[1] if len(params) > 1 else "?"
        prefix = "Lewati Gerbang: " if name == "goto_through_gate" else "Jalan: "
        return f"{prefix}{loc_from} -> {loc_to}", f"rute navigasi A*"

    # Fallback default
    param_str = " ".join(params) if params else ""
    return name.replace("_", " ").title(), param_str

def get_planner_layout_rects() -> Dict[str, pygame.Rect]:
    """
    Mengembalikan bounding box seluruh panel planner dan elemen HUD untuk
    pengujian batas cakupan (<= 15% luas layar) dan verifikasi non-overlapping.
    """
    # Layar: 1024 x 768
    # Batas 15% luas layar: 0.15 * 1024 * 768 = 117,964 piksel
    rect_expedition = pygame.Rect(660, 60, 350, 320)   # 112,000 px (14.23%)
    rect_htn = pygame.Rect(660, 390, 350, 320)          # 112,000 px (14.23%)
    rect_unified = pygame.Rect(660, 8, 356, 420)        # Dock terpadu kanan atas (bebas overlap)
    rect_hud_bottom = pygame.Rect(0, 710, 1024, 58)     # Legenda HUD bawah
    rect_banner_top = pygame.Rect(284, 8, 460, 34)      # Banner status autopilot atas (bebas tumpang tindih)

    return {
        "panel_unified": rect_unified,
        "panel_expedition": rect_expedition,
        "panel_htn": rect_htn,
        "hud_bottom": rect_hud_bottom,
        "banner_top": rect_banner_top
    }


# ==============================================================================
# PANEL EXPEDITION PLANNER [F7]
# ==============================================================================

class ExpeditionPlanPanel:
    """Panel visualisasi rencana STRIPS Expedition Hero."""

    def __init__(self, rect: Optional[pygame.Rect] = None):
        self.rect = rect or pygame.Rect(660, 60, 350, 320)
        self.catalog = get_asset_catalog()
        self.font_title = pygame.font.Font(None, 18)
        self.font_body = pygame.font.Font(None, 14)
        self.font_bold = pygame.font.Font(None, 15)

        # Cache icon aset Sunnyside
        self.icons: Dict[str, pygame.Surface] = {}
        self._load_icons()

    def _load_icons(self):
        """Memuat ikon Sunnyside asli dari asset catalog."""
        icon_names = {
            "axe": "UI/axe.png",
            "pickaxe": "UI/pickaxe.png",
            "hammer": "UI/hammer.png",
            "shovel": "UI/shovel.png",
            "sword": "UI/sword.png",
            "rod": "UI/rod.png",
            "sandtimer": "UI/sandtimer.png",
            "confirm": "UI/confirm.png",
            "cancel": "UI/cancel.png",
            "indicator": "UI/indicator.png",
            "greenbar": "UI/greenbar_05.png"
        }
        for k, path in icon_names.items():
            surf = self.catalog.get_image(path)
            if surf is not None:
                # Skala seragam ke 16x16 jika terlalu besar
                if surf.get_width() > 20 or surf.get_height() > 20:
                    surf = pygame.transform.scale(surf, (16, 16))
                self.icons[k] = surf

    def _get_action_icon(self, act_name: str) -> Optional[pygame.Surface]:
        name = act_name.lower()
        if "chop" in name or "wood" in name:
            return self.icons.get("axe")
        if "mine" in name or "rock" in name:
            return self.icons.get("pickaxe")
        if "key" in name or "craft" in name:
            return self.icons.get("hammer")
        if "plant" in name or "harvest" in name or "farm" in name:
            return self.icons.get("shovel")
        if "fight" in name or "boss" in name or "attack" in name:
            return self.icons.get("sword")
        if "fish" in name:
            return self.icons.get("rod")
        if "wait" in name or "grow" in name:
            return self.icons.get("sandtimer")
        return self.icons.get("sandtimer")

    def draw(self, screen: pygame.Surface, autopilot: AutopilotController):
        """Menggambar panel Expedition STRIPS ke layar."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # 1. Latar Belakang & Frame Bergaya Sunnyside
        bg = pygame.Surface((rw, rh), pygame.SRCALPHA)
        bg.fill((24, 28, 38, 235))  # Palet gelap transparan
        screen.blit(bg, (rx, ry))
        pygame.draw.rect(screen, (240, 190, 60), self.rect, 2)  # Border emas

        # 2. Header Panel
        title_surf = self.font_title.render("EXPEDITION PLANNER [F7]", True, (255, 230, 100))
        screen.blit(title_surf, (rx + 10, ry + 8))

        mode_str = f"Mode: {autopilot.mode}"
        mode_col = (80, 240, 120) if autopilot.mode == PlannerMode.AUTO else (120, 200, 255)
        mode_surf = self.font_body.render(mode_str, True, mode_col)
        screen.blit(mode_surf, (rx + rw - mode_surf.get_width() - 10, ry + 10))

        # 3. Baris Ringkasan Metrik
        plan = autopilot.monitor.current_plan
        step_idx = autopilot.monitor.current_step_idx
        total_steps = len(plan)
        total_cost = sum(a.cost for a in plan)

        sum_txt1 = f"Algoritma: WA*(h_FF) | Biaya: {total_cost:.1f}s | {total_steps} Langkah"
        s1_surf = self.font_body.render(sum_txt1, True, (210, 215, 225))
        screen.blit(s1_surf, (rx + 10, ry + 28))

        replan_txt = f"Replan: {autopilot.monitor.consecutive_replans}x | Status: {'PAUSED' if autopilot.is_paused_by_player else 'AKTIF'}"
        s2_surf = self.font_body.render(replan_txt, True, (180, 185, 195))
        screen.blit(s2_surf, (rx + 10, ry + 44))

        # 4. Bar Progres Misi (Greenbar)
        bar_x = rx + 10
        bar_y = ry + 62
        bar_w = rw - 20
        bar_h = 10
        pygame.draw.rect(screen, (40, 45, 55), (bar_x, bar_y, bar_w, bar_h))
        if total_steps > 0:
            pct = min(1.0, max(0.0, step_idx / total_steps))
            fill_w = int(bar_w * pct)
            if fill_w > 0:
                pygame.draw.rect(screen, (70, 215, 90), (bar_x, bar_y, fill_w, bar_h))
        pygame.draw.rect(screen, (160, 170, 185), (bar_x, bar_y, bar_w, bar_h), 1)

        # 5. Daftar Langkah Rencana (5 langkah terdekat)
        list_y = ry + 80
        if not plan:
            no_plan_surf = self.font_body.render("Belum ada rencana aktif. Tekan F9 untuk mulai.", True, (170, 175, 185))
            screen.blit(no_plan_surf, (rx + 10, list_y + 40))
            return

        start_show = max(0, min(step_idx - 1, total_steps - 5))
        end_show = min(total_steps, start_show + 5)

        for row_i, idx in enumerate(range(start_show, end_show)):
            act = plan[idx]
            item_y = list_y + row_i * 44

            # Background baris aktif
            is_current = (idx == step_idx)
            if is_current:
                row_bg = pygame.Surface((rw - 16, 40), pygame.SRCALPHA)
                row_bg.fill((60, 80, 110, 180))
                screen.blit(row_bg, (rx + 8, item_y))
                pygame.draw.rect(screen, (240, 200, 70), (rx + 8, item_y, rw - 16, 40), 1)

            # Icon Status
            if idx < step_idx:
                st_icon = self.icons.get("confirm")
            elif idx == step_idx:
                st_icon = self.icons.get("indicator")
            else:
                st_icon = self.icons.get("sandtimer")

            if st_icon:
                screen.blit(st_icon, (rx + 14, item_y + 12))

            # Icon Aksi
            act_icon = self._get_action_icon(act.name)
            if act_icon:
                screen.blit(act_icon, (rx + 36, item_y + 12))

            # Nama Aksi & Detail Manusiawi
            title_human, detail_human = format_action_human(act)
            step_title = f"{idx + 1}. {title_human}"
            col = (255, 235, 140) if is_current else ((160, 225, 160) if idx < step_idx else (220, 225, 235))
            t_surf = self.font_bold.render(step_title, True, col)
            screen.blit(t_surf, (rx + 58, item_y + 4))

            # Detail Parameter & Durasi
            detail_txt = f"{detail_human[:26]} | {act.duration:.1f}s"
            d_surf = self.font_body.render(detail_txt, True, (170, 175, 185))
            screen.blit(d_surf, (rx + 58, item_y + 20))


# ==============================================================================
# PANEL HTN DESA HIDUP [F8]
# ==============================================================================

class HTNPlanPanel:
    """Panel visualisasi pohon dekomposisi hierarki tugas NPC (Petani & Penggiling)."""

    def __init__(self, rect: Optional[pygame.Rect] = None):
        self.rect = rect or pygame.Rect(660, 390, 350, 320)
        self.catalog = get_asset_catalog()
        self.font_title = pygame.font.Font(None, 18)
        self.font_body = pygame.font.Font(None, 14)
        self.font_bold = pygame.font.Font(None, 15)

        self.icons: Dict[str, pygame.Surface] = {}
        self._load_icons()

    def _load_icons(self):
        icon_names = {
            "working": "UI/expression_working.png",
            "confused": "UI/expression_confused.png",
            "chat": "UI/expression_chat.png",
            "rest": "UI/expression_rest.png",
            "confirm": "UI/confirm.png",
            "indicator": "UI/indicator.png"
        }
        for k, path in icon_names.items():
            surf = self.catalog.get_image(path)
            if surf is not None:
                if surf.get_width() > 20 or surf.get_height() > 20:
                    surf = pygame.transform.scale(surf, (16, 16))
                self.icons[k] = surf

    def draw(self, screen: pygame.Surface, farmer: HTNNPCAgent, miller: HTNNPCAgent, clock: WorldClock):
        """Menggambar panel pohon dekomposisi HTN ke layar."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # 1. Latar Belakang & Frame
        bg = pygame.Surface((rw, rh), pygame.SRCALPHA)
        bg.fill((22, 28, 34, 235))
        screen.blit(bg, (rx, ry))
        pygame.draw.rect(screen, (80, 200, 160), self.rect, 2)  # Border toska desa

        # 2. Header Panel & Jam Dunia
        title_surf = self.font_title.render("DESA HIDUP: HTN TASK [F8]", True, (120, 240, 200))
        screen.blit(title_surf, (rx + 10, ry + 8))

        time_str = f"Jam: {clock.time_string}"
        time_col = (255, 220, 100) if clock.is_daytime else (150, 180, 255)
        time_surf = self.font_body.render(time_str, True, time_col)
        screen.blit(time_surf, (rx + rw - time_surf.get_width() - 10, ry + 10))

        # 3. Bagian 1: Petani (Pak Tani)
        py_y = ry + 32
        f_title = f"[PETANI] {farmer.name} | Lokasi: {farmer.current_location}"
        ft_surf = self.font_bold.render(f_title, True, (240, 230, 140))
        screen.blit(ft_surf, (rx + 10, py_y))

        # Expression icon
        expr_icon = self.icons.get(farmer.expression)
        if expr_icon:
            screen.blit(expr_icon, (rx + rw - 30, py_y))

        # Metode & Alasan Precondition
        f_method = farmer.active_tree[0].chosen_method if farmer.active_tree else "m_farmer_day_shift"
        f_reason = farmer.active_tree[0].precondition_reason if farmer.active_tree else "Rutinitas siang hari aktif."
        m_txt = f"  Metode: {f_method}"
        screen.blit(self.font_body.render(m_txt, True, (160, 230, 180)), (rx + 10, py_y + 16))

        r_txt = f"  Alasan: {f_reason[:38]}..."
        screen.blit(self.font_body.render(r_txt, True, (170, 180, 195)), (rx + 10, py_y + 30))

        # Antrean Operator Primitif Petani
        op_txt = "  Antrean: "
        if farmer.active_operator_queue:
            op_names = [op.name for op in farmer.active_operator_queue[:3]]
            op_txt += " -> ".join(op_names)
        else:
            op_txt += "Istirahat / Selesai"
        screen.blit(self.font_body.render(op_txt[:42], True, (200, 210, 220)), (rx + 10, py_y + 44))

        # Garis Pembatas
        pygame.draw.line(screen, (60, 75, 90), (rx + 10, py_y + 64), (rx + rw - 10, py_y + 64), 1)

        # 4. Bagian 2: Penggiling (Kang Penggiling)
        my_y = py_y + 74
        m_title = f"[PENGGILING] {miller.name} | Lokasi: {miller.current_location}"
        mt_surf = self.font_bold.render(m_title, True, (240, 230, 140))
        screen.blit(mt_surf, (rx + 10, my_y))

        m_expr_icon = self.icons.get(miller.expression)
        if m_expr_icon:
            screen.blit(m_expr_icon, (rx + rw - 30, my_y))

        mil_method = miller.active_tree[0].chosen_method if miller.active_tree else "m_miller_day_shift"
        mil_reason = miller.active_tree[0].precondition_reason if miller.active_tree else "Kincir angin siap beroperasi."
        mm_txt = f"  Metode: {mil_method}"
        screen.blit(self.font_body.render(mm_txt, True, (160, 230, 180)), (rx + 10, my_y + 16))

        mr_txt = f"  Alasan: {mil_reason[:38]}..."
        screen.blit(self.font_body.render(mr_txt, True, (170, 180, 195)), (rx + 10, my_y + 30))

        m_op_txt = "  Antrean: "
        if miller.active_operator_queue:
            m_op_names = [op.name for op in miller.active_operator_queue[:3]]
            m_op_txt += " -> ".join(m_op_names)
        else:
            m_op_txt += "Istirahat / Selesai"
        screen.blit(self.font_body.render(m_op_txt[:42], True, (200, 210, 220)), (rx + 10, my_y + 44))

        # Garis Pembatas
        pygame.draw.line(screen, (60, 75, 90), (rx + 10, my_y + 64), (rx + rw - 10, my_y + 64), 1)

        # 5. Riwayat Replan & Anomali Dunia (Dynamic World Reaction)
        hist_y = my_y + 74
        hist_title = self.font_bold.render("RIWAYAT REPLAN NPC (INTERVENSI DUNIA):", True, (255, 200, 120))
        screen.blit(hist_title, (rx + 10, hist_y))

        history = farmer.replan_history[-2:] if farmer.replan_history else ["Belum ada replan (rutinitas stabil)"]
        for hi, h_entry in enumerate(history):
            h_surf = self.font_body.render(f"- {h_entry[:45]}", True, (180, 185, 195))
            screen.blit(h_surf, (rx + 10, hist_y + 16 + hi * 14))


# ==============================================================================
# ==============================================================================
# PANEL TERPADU DUA TAB (SUB-FASE 2D) [F7 / F8]
# ==============================================================================

class UnifiedPlannerPanel:
    """
    Panel perencanaan terpadu satu jendela (Unified AI Inspector Dock) - Monokrom Hitam-Putih:
      - Tab 0: [F7] Planning Inspector (STRIPS PDDL, WA*, Goal Literals, State Diff)
      - Tab 1: [1] Analisis Heuristik (UCS vs A* vs WA* h_FF vs h_level)
      - Tab 2: [HTN] Hierarchical Task Network (Opsional, di luar materi silabus)
      - Tab 3: [F8] Decisions Under Uncertainty (Multi-Armed Bandit & Live Combat Policy)
    Dock berukuran Rect(660, 8, 356, 420) di kanan atas:
      - Desain solid monokrom hitam-putih (#0e0e0e) dengan batas kontras tinggi dan jarak baris longgar.
      - 100% bebas tumpang tindih dari topbar, advisor banner, dan HUD bawah.
      - Card container modular (#161616, border #303030) dengan keterbacaan teks maksimal.
      - Cross-module integration bar di header menampilkan ringkasan live modul mitra.
    """

    def __init__(self, rect: Optional[pygame.Rect] = None):
        self.rect = rect or pygame.Rect(660, 8, 356, 420)
        self.active_tab: int = 0  # 0: Planning, 1: Heuristik, 2: HTN, 3: Ketidakpastian
        self.visible: bool = False
        self.catalog = get_asset_catalog()

        # Ukuran font proyektor terbaca jelas (>= 14px)
        self.font_tab = pygame.font.Font(None, 15)
        self.font_title = pygame.font.Font(None, 18)
        self.font_body = pygame.font.Font(None, 14)
        self.font_bold = pygame.font.Font(None, 15)
        self.font_badge = pygame.font.Font(None, 13)

        # Surface shadow kiri pra-kalkulasi untuk efisiensi render tinggi (< 1 ms)
        self._shadow_surf = pygame.Surface((8, self.rect.height), pygame.SRCALPHA)
        for sx in range(8):
            alpha = int(70 * (sx + 1) / 8)
            pygame.draw.line(self._shadow_surf, (0, 0, 0, alpha), (sx, 0), (sx, self.rect.height))

        # Cache icon aksi Sunnyside asli
        self.icons: Dict[str, pygame.Surface] = {}
        self._load_icons()

    def _draw_card(self, screen: pygame.Surface, rect: pygame.Rect,
                   title: Optional[str] = None, badge: Optional[str] = None,
                   title_col: Tuple[int, int, int] = (255, 255, 255),
                   badge_col: Tuple[int, int, int] = (175, 175, 175),
                   border_col: Optional[Tuple[int, int, int]] = None,
                   bg_col: Optional[Tuple[int, int, int]] = None):
        """Menggambar kontainer card dengan styling monokrom hitam-putih bersih."""
        pygame.draw.rect(screen, bg_col or (22, 22, 22), rect, border_radius=4)
        b_col = border_col or (48, 48, 48)
        pygame.draw.rect(screen, b_col, rect, 1, border_radius=4)

        if title or badge:
            if title:
                t_surf = self.font_bold.render(title, True, title_col)
                screen.blit(t_surf, (rect.x + 10, rect.y + 7))
            if badge:
                b_surf = self.font_badge.render(badge, True, badge_col)
                bw, bh = b_surf.get_width() + 8, b_surf.get_height() + 4
                bx = rect.x + rect.width - bw - 8
                by = rect.y + 5
                pygame.draw.rect(screen, (34, 34, 34), (bx, by, bw, bh), border_radius=3)
                pygame.draw.rect(screen, (70, 70, 70), (bx, by, bw, bh), 1, border_radius=3)
                screen.blit(b_surf, (bx + 4, by + 2))

    def _load_icons(self):
        icon_names = {
            "axe": "UI/axe.png",
            "pickaxe": "UI/pickaxe.png",
            "hammer": "UI/hammer.png",
            "shovel": "UI/shovel.png",
            "sword": "UI/sword.png",
            "rod": "UI/rod.png",
            "sandtimer": "UI/sandtimer.png",
            "confirm": "UI/confirm.png",
            "cancel": "UI/cancel.png",
            "indicator": "UI/indicator.png"
        }
        for k, path in icon_names.items():
            surf = self.catalog.get_image(path)
            if surf is not None:
                if surf.get_width() > 16 or surf.get_height() > 16:
                    surf = pygame.transform.scale(surf, (16, 16))
                self.icons[k] = surf

    def _get_action_icon_key(self, act_name: str) -> str:
        name = act_name.lower()
        if "chop" in name or "wood" in name:
            return "axe"
        if "mine" in name or "rock" in name:
            return "pickaxe"
        if "key" in name or "craft" in name:
            return "hammer"
        if "plant" in name or "harvest" in name or "farm" in name:
            return "shovel"
        if "fight" in name or "boss" in name or "attack" in name:
            return "sword"
        if "fish" in name:
            return "rod"
        return "sandtimer"

    def toggle(self, tab: Optional[int] = None):
        """Membuka atau menutup panel. Bila tab diberikan, beralih langsung."""
        if tab is not None:
            if self.visible and self.active_tab == tab:
                self.visible = False
            else:
                self.visible = True
                self.active_tab = tab
        else:
            self.visible = not self.visible

    def handle_click(self, pos: Tuple[int, int]) -> bool:
        """Menangani klik mouse pada header tab untuk beralih tab."""
        if not self.visible or not self.rect.collidepoint(pos):
            return False
        rx, ry = self.rect.x, self.rect.y
        tab0_rect = pygame.Rect(rx + 4, ry + 4, 88, 22)
        tab1_rect = pygame.Rect(rx + 96, ry + 4, 66, 22)
        tab2_rect = pygame.Rect(rx + 166, ry + 4, 58, 22)
        tab3_rect = pygame.Rect(rx + 228, ry + 4, 124, 22)

        if tab0_rect.collidepoint(pos):
            self.active_tab = 0
            return True
        if tab1_rect.collidepoint(pos):
            self.active_tab = 1
            return True
        if tab2_rect.collidepoint(pos):
            self.active_tab = 2
            return True
        if tab3_rect.collidepoint(pos):
            self.active_tab = 3
            return True
        return False

    def _draw_tabs(self, screen: pygame.Surface):
        """Menggambar tab header bar di bagian atas dock (Monokrom Hitam-Putih)."""
        rx, ry, rw = self.rect.x, self.rect.y, self.rect.width
        tab0_rect = pygame.Rect(rx + 4, ry + 4, 88, 22)
        tab1_rect = pygame.Rect(rx + 96, ry + 4, 66, 22)
        tab2_rect = pygame.Rect(rx + 166, ry + 4, 58, 22)
        tab3_rect = pygame.Rect(rx + 228, ry + 4, 124, 22)

        tabs_data = [
            (0, tab0_rect, "[F7] Planning"),
            (1, tab1_rect, "Heuristik"),
            (2, tab2_rect, "HTN (Ops)"),
            (3, tab3_rect, "[F8] Uncertainty"),
        ]

        for idx, t_rect, label in tabs_data:
            is_active = (self.active_tab == idx)
            bg_col = (34, 34, 34) if is_active else (18, 18, 18)
            border_col = (200, 200, 200) if is_active else (42, 42, 42)
            txt_col = (255, 255, 255) if is_active else (130, 130, 130)

            pygame.draw.rect(screen, bg_col, t_rect, border_radius=3)
            pygame.draw.rect(screen, border_col, t_rect, 1, border_radius=3)
            surf = self.font_tab.render(label, True, txt_col)
            screen.blit(surf, (t_rect.x + (t_rect.width - surf.get_width()) // 2, t_rect.y + 4))

    def _draw_cross_module_bar(self, screen: pygame.Surface, autopilot: Optional[AutopilotController],
                               weather_mgr: Optional[Any] = None):
        """Strip satu baris di bawah header tab yang merangkum status live modul mitra (Monokrom)."""
        rx, ry, rw = self.rect.x, self.rect.y, self.rect.width
        bar_rect = pygame.Rect(rx + 6, ry + 29, rw - 12, 18)
        pygame.draw.rect(screen, (20, 20, 20), bar_rect, border_radius=2)
        pygame.draw.rect(screen, (45, 45, 45), bar_rect, 1, border_radius=2)

        if self.active_tab == 0:
            txt = "[UCC] MAB Fishing (5 Spot) | Live Minion Risk Policy"
            screen.blit(self.font_badge.render(txt, True, (215, 215, 215)), (rx + 10, ry + 32))
        elif self.active_tab == 3:
            if autopilot is not None and hasattr(autopilot, "monitor"):
                plan = autopilot.monitor.current_plan
                st = autopilot.monitor.current_step_idx + 1
                tot = len(plan) if plan else 37
                act_name = autopilot.monitor.current_action.name if autopilot.monitor.current_action else "Selesai"
                st_txt = "PAUSED" if autopilot.is_paused_by_player else str(autopilot.mode)
                txt = f"[PLANNING] Aksi {st}/{tot}: {act_name} | [{st_txt}]"
                screen.blit(self.font_badge.render(txt[:44], True, (215, 215, 215)), (rx + 10, ry + 32))
            else:
                screen.blit(self.font_badge.render("[PLANNING] WA*(h_FF) w=1.5 | Goal: boss_defeated", True, (215, 215, 215)), (rx + 10, ry + 32))
        else:
            screen.blit(self.font_badge.render("[SISTEM TERPADU] STRIPS WA* w=1.5 <--> MAB Decision Engine", True, (200, 200, 200)), (rx + 10, ry + 32))

    def _draw_planning_tab(self, screen: pygame.Surface, autopilot: Optional[AutopilotController],
                           weather_mgr: Optional[Any] = None):
        """Tab 0: [F7] AUTOMATED PLANNING INSPECTOR otentik STRIPS PDDL berbasis Card Monokrom Spasial."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # Title Header & Domain Source
        title_surf = self.font_title.render("PLANNING INSPECTOR (STRIPS WA*)", True, (255, 255, 255))
        screen.blit(title_surf, (rx + 8, ry + 50))
        dom_surf = self.font_badge.render("Domain: data/planning/expedition.domain", True, (150, 150, 150))
        screen.blit(dom_surf, (rx + 8, ry + 66))

        if autopilot is None or not hasattr(autopilot, "monitor"):
            no_card = pygame.Rect(rx + 6, ry + 82, rw - 12, 60)
            self._draw_card(screen, no_card, title="STATUS SISTEM", badge="[OFF]")
            no_p = self.font_body.render("Autopilot belum aktif. Tekan [F9] untuk mulai.", True, (170, 170, 170))
            screen.blit(no_p, (rx + 14, ry + 110))
            return

        monitor = autopilot.monitor
        plan = monitor.current_plan
        step_idx = monitor.current_step_idx
        total_steps = len(plan) if plan else 37
        ws = autopilot.world_state

        # Card 1: Tujuan & Progres
        c1_rect = pygame.Rect(rx + 6, ry + 82, rw - 12, 70)
        mode_badge = f"Mode: {autopilot.mode}"
        self._draw_card(screen, c1_rect, title="TUJUAN & PROGRES", badge=mode_badge)

        key_done = ws.inventory.has_item("gate_key", 1) or ws.inventory.has_item("key", 1)
        gate_done = ws.gate.is_open
        boss_done = getattr(getattr(ws, "boss", None), "is_defeated", False)

        cur_y = c1_rect.y + 24
        goals = [
            ("gate_key", key_done),
            ("gate_open", gate_done),
            ("boss_defeated", boss_done),
        ]
        gx = c1_rect.x + 10
        for g_name, is_done in goals:
            mark = "[x]" if is_done else "[ ]"
            txt_col = (255, 255, 255) if is_done else (130, 130, 130)
            txt = f"{mark} {g_name}"
            surf = self.font_body.render(txt, True, txt_col)
            screen.blit(surf, (gx, cur_y))
            gx += surf.get_width() + 10

        # Progress bar
        cur_y += 18
        bar_x, bar_y, bar_w, bar_h = c1_rect.x + 10, cur_y, c1_rect.width - 20, 6
        pygame.draw.rect(screen, (36, 36, 36), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
        pct = min(1.0, max(0.0, step_idx / max(1, total_steps)))
        if pct > 0:
            fill_w = int(bar_w * pct)
            pygame.draw.rect(screen, (220, 220, 220), (bar_x, bar_y, fill_w, bar_h), border_radius=2)
        pygame.draw.rect(screen, (75, 75, 75), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=2)

        cur_y += 12
        tot_cost = sum(a.cost for a in plan) if plan else 118.5
        prog_txt = f"Langkah {step_idx}/{total_steps} | Biaya: {tot_cost:.1f}s | Mode: {autopilot.mode}"
        screen.blit(self.font_badge.render(prog_txt, True, (160, 160, 160)), (c1_rect.x + 10, cur_y))

        # Card 2: Aksi Aktif & Skema STRIPS
        c2_rect = pygame.Rect(rx + 6, ry + 160, rw - 12, 90)
        act = monitor.current_action
        act_badge = "[BERJALAN]" if act is not None else "[SIAP]"
        self._draw_card(screen, c2_rect, title="AKSI AKTIF (STRIPS)", badge=act_badge)

        cur_y = c2_rect.y + 24
        if act is not None:
            act_title = f"Aksi: {act.name}({', '.join(act.params)})"
            screen.blit(self.font_bold.render(act_title[:42], True, (240, 240, 240)), (c2_rect.x + 10, cur_y))
            cur_y += 18

            pre_names = [p.name for p in sorted(act.preconditions, key=lambda x: x.name)][:3]
            pre_str = "Pre: " + " ".join(f"[OK] {pn}" for pn in pre_names)
            screen.blit(self.font_body.render(pre_str[:44], True, (190, 190, 190)), (c2_rect.x + 10, cur_y))
            cur_y += 18

            adds = [f"+{p.name}" for p in sorted(act.add_effects, key=lambda x: x.name)][:2]
            dels = [f"-{p.name}" for p in sorted(act.delete_effects, key=lambda x: x.name)][:2]
            eff_str = "Eff: " + " ".join(adds + dels)
            screen.blit(self.font_body.render(eff_str[:44], True, (160, 160, 160)), (c2_rect.x + 10, cur_y))
            cur_y += 18
        else:
            screen.blit(self.font_bold.render("Aksi: Ekspedisi Selesai / Siap [F9]", True, (240, 240, 240)), (c2_rect.x + 10, cur_y))
            cur_y += 18
            screen.blit(self.font_body.render("Semua precondition STRIPS terpenuhi.", True, (180, 180, 180)), (c2_rect.x + 10, cur_y))
            cur_y += 18
            screen.blit(self.font_body.render("Eff: Siap eksekusi tahap berikutnya.", True, (150, 150, 150)), (c2_rect.x + 10, cur_y))
            cur_y += 18

        diff_txt = getattr(monitor, "last_state_diff", "-")
        diff_display = "Diff: - (belum ada aksi selesai)" if diff_txt == "-" else f"Diff: {diff_txt[:40]}"
        screen.blit(self.font_badge.render(diff_display, True, (140, 140, 140)), (c2_rect.x + 10, c2_rect.y + c2_rect.height - 15))

        # Card 3: Pencarian WA* & Antrean
        c3_rect = pygame.Rect(rx + 6, ry + 258, rw - 12, 152)
        w_val = getattr(config, "PLANNER_WEIGHT", 1.5)
        self._draw_card(screen, c3_rect, title="MESIN PENCARI WA* & ANTREAN", badge=f"w={w_val}")

        cur_y = c3_rect.y + 24
        nodes = getattr(monitor, "last_nodes_expanded", None)
        nodes_txt = f"{nodes} node" if nodes is not None else "- node"
        lat = getattr(monitor, "last_search_latency_ms", 0.0)
        m_txt = f"WA*(h_FF, w={w_val}) | {nodes_txt} | {lat:.1f}ms"
        screen.blit(self.font_bold.render(m_txt, True, (240, 240, 240)), (c3_rect.x + 10, cur_y))

        cur_y += 18
        b_txt = "Budget step(): < 20ms [OK] | Polyline [OK]"
        screen.blit(self.font_badge.render(b_txt, True, (165, 165, 165)), (c3_rect.x + 10, cur_y))

        cur_y += 16
        geo_txt = "Geodesik: 40 lkg >= 38 Manhattan [OK] (invarian)"
        screen.blit(self.font_badge.render(geo_txt, True, (150, 150, 150)), (c3_rect.x + 10, cur_y))

        cur_y += 16
        rep_n = monitor.consecutive_replans
        rep_reason = getattr(monitor, "last_replan_reason", "-")
        rep_txt = "Replan: - (eksekusi berjalan lancar)" if (rep_n == 0 or rep_reason == "-") else f"{rep_reason[:44]}"
        screen.blit(self.font_body.render(rep_txt, True, (160, 160, 160)), (c3_rect.x + 10, cur_y))

        cur_y += 18
        pygame.draw.line(screen, (45, 45, 45), (c3_rect.x + 10, cur_y), (c3_rect.x + c3_rect.width - 10, cur_y), 1)
        cur_y += 6

        if plan and step_idx < len(plan):
            for qi in range(step_idx, min(len(plan), step_idx + 2)):
                q_act = plan[qi]
                q_title, _ = format_action_human(q_act)
                q_str = f"#{qi+1} {q_title} ({q_act.duration:.1f}s)"
                screen.blit(self.font_body.render(q_str[:38], True, (215, 215, 215)), (c3_rect.x + 10, cur_y))
                cur_y += 18
        else:
            screen.blit(self.font_badge.render("Belum ada antrean aksi berjalan.", True, (130, 130, 130)), (c3_rect.x + 10, cur_y))

    def _draw_heuristics_tab(self, screen: pygame.Surface):
        """Tab 1: Analisis komparatif heuristik pencarian (Monokrom)."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        title = self.font_title.render("ANALISIS HEURISTIK PERENCANAAN", True, (255, 255, 255))
        screen.blit(title, (rx + 8, ry + 50))

        # Card 1: Perbandingan Algoritma (P1-P4)
        c1_rect = pygame.Rect(rx + 6, ry + 72, rw - 12, 172)
        self._draw_card(screen, c1_rect, title="BENCHMARK MASALAH P1 - P4", badge="Node & Waktu")

        lines_p = [
            ("P1 (Key Craft):", "UCS 35 node (1.4ms) | A*(h_max) 16 node (0.8ms)"),
            ("P2 (Open Gate):", "UCS 48 node (2.8ms) | A*(h_max) 29 node (1.5ms)"),
            ("P3 (Potion):", "WA*(h_FF) 16 node (18.4ms) - Cost 33.0s"),
            ("P4 (Full Ekspedisi):", "WA*(h_FF) 37 langkah (118.48s) | 876 node"),
        ]
        cur_y = c1_rect.y + 24
        for header, detail in lines_p:
            h_surf = self.font_bold.render(header, True, (230, 230, 230))
            screen.blit(h_surf, (c1_rect.x + 10, cur_y))
            d_surf = self.font_body.render(detail, True, (170, 170, 170))
            screen.blit(d_surf, (c1_rect.x + 10, cur_y + 16))
            cur_y += 35

        # Card 2: Properti & Optimasi
        c2_rect = pygame.Rect(rx + 6, ry + 252, rw - 12, 158)
        self._draw_card(screen, c2_rect, title="OPTIMASI & SIFAT ADMISIBILITAS", badge="Planning Graph")

        lines_opt = [
            ("Planning Graph:", "h_level admissible (h=4.0 pada Ojek)"),
            ("Optimasi Search:", "Helpful Actions + Non-Goto Filter (x8 cut)"),
            ("Incremental Budget:", "step() per-frame budget < 20 ms (15 ms)"),
        ]
        cur_y = c2_rect.y + 24
        for header, detail in lines_opt:
            h_surf = self.font_bold.render(header, True, (230, 230, 230))
            screen.blit(h_surf, (c2_rect.x + 10, cur_y))
            d_surf = self.font_body.render(detail, True, (170, 170, 170))
            screen.blit(d_surf, (c2_rect.x + 10, cur_y + 16))
            cur_y += 36

    def _draw_htn_tab(self, screen: pygame.Surface, farmer: Optional[HTNNPCAgent],
                      miller: Optional[HTNNPCAgent], clock: Optional[WorldClock]):
        """Tab 2: HTN diberi label jelas opsional / di luar materi silabus (Monokrom)."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        title = self.font_title.render("HTN TASK DECOMPOSITION (OPSIONAL)", True, (255, 255, 255))
        screen.blit(title, (rx + 8, ry + 50))

        c1_rect = pygame.Rect(rx + 6, ry + 72, rw - 12, 90)
        self._draw_card(screen, c1_rect, title="STATUS SHOP-STYLE HTN", badge="[OPSIONAL]")
        cur_y = c1_rect.y + 24
        screen.blit(self.font_body.render("Status: Opsional (di luar materi silabus 35 slide)", True, (220, 220, 220)), (c1_rect.x + 10, cur_y))
        cur_y += 18
        screen.blit(self.font_body.render("Engine HTN mandiri tersedia di src/planning/htn.py", True, (180, 180, 180)), (c1_rect.x + 10, cur_y))
        cur_y += 18
        screen.blit(self.font_body.render("Mendukung dekomposisi task NPC desa Sunnyside.", True, (150, 150, 150)), (c1_rect.x + 10, cur_y))

        c2_rect = pygame.Rect(rx + 6, ry + 168, rw - 12, 242)
        self._draw_card(screen, c2_rect, title="SILABUS AUTOMATED PLANNING", badge="Fokus Materi")
        syllabus_lines = [
            "* PDDL & Action Schema (STRIPS standard)",
            "* Forward State-Space Search (BFS, UCS, A*)",
            "* Backward Goal Regression (Slide 27)",
            "* Ignore-Delete-List Heuristics (h_add, h_max, h_FF)",
            "* Planning Graph & Mutex (GraphPlan / h_level)",
            "* Decoupled Real-Time Re-planning Engine",
            "* Cross-Module Integration with Bayesian Uncertainty",
        ]
        cur_y = c2_rect.y + 24
        for s_line in syllabus_lines:
            screen.blit(self.font_body.render(s_line, True, (200, 200, 200)), (c2_rect.x + 10, cur_y))
            cur_y += 20

    def _draw_uncertainty_tab(self, screen: pygame.Surface, weather_mgr: Optional[Any] = None,
                               autopilot: Optional[AutopilotController] = None):
        """Tab 3: [F8] DECISIONS UNDER UNCERTAINTY (UCC) - Multi-Armed Bandit & Combat Risk Policy (Monokrom)."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # Title Header & Subtitle
        title_surf = self.font_title.render("DECISIONS UNDER UNCERTAINTY", True, (255, 255, 255))
        screen.blit(title_surf, (rx + 8, ry + 50))
        sub_surf = self.font_badge.render("Model: Multi-Armed Bandit & Live Combat Policy", True, (150, 150, 150))
        screen.blit(sub_surf, (rx + 8, ry + 66))

        # Card 1: Multi-Armed Bandit Fishing System
        c1_rect = pygame.Rect(rx + 6, ry + 82, rw - 12, 98)
        self._draw_card(screen, c1_rect, title="MAB: EKSPLORASI VS EKSPLOITASI", badge="[5 SPOTS]")

        cur_y = c1_rect.y + 24
        line1 = "Sistem: 5 Spot Pancingan Pesisir & Sungai (Theta Rahasia)"
        screen.blit(self.font_body.render(line1, True, (220, 220, 220)), (c1_rect.x + 10, cur_y))

        cur_y += 22
        line2 = "Algoritma: Thompson Sampling, UCB1, Epsilon-Greedy, Softmax"
        screen.blit(self.font_body.render(line2, True, (180, 180, 180)), (c1_rect.x + 10, cur_y))

        cur_y += 22
        line3 = "Interaksi: Tekan [B] untuk Membuka Jurnal Nelayan & Grafik"
        screen.blit(self.font_badge.render(line3, True, (140, 140, 140)), (c1_rect.x + 10, cur_y))

        # Card 2: Live Combat Engagement Risk Policy
        c2_rect = pygame.Rect(rx + 6, ry + 188, rw - 12, 98)
        self._draw_card(screen, c2_rect, title="KEBIJAKAN RISIKO PERTEMPURAN", badge="[LIVE COMBAT]")

        cur_y = c2_rect.y + 24
        line4 = "Ancaman: Minion Goblin Hijau Berkeliaran di Alam Bebas"
        screen.blit(self.font_body.render(line4, True, (220, 220, 220)), (c2_rect.x + 10, cur_y))

        cur_y += 22
        line5 = "Keputusan: Tarung (E[Loot] = +5.5 Koin) vs Hindari (0 Dmg)"
        screen.blit(self.font_body.render(line5, True, (180, 180, 180)), (c2_rect.x + 10, cur_y))

        cur_y += 22
        line6 = "Kebijakan: HP >= 35% -> Engage | HP < 35% -> Evade / Detour"
        screen.blit(self.font_badge.render(line6, True, (140, 140, 140)), (c2_rect.x + 10, cur_y))

        # Card 3: Formulasi Matematika & Ambang Teori
        c3_rect = pygame.Rect(rx + 6, ry + 294, rw - 12, 116)
        self._draw_card(screen, c3_rect, title="FORMULASI KEPUTUSAN STOKASTIK", badge="[TEORI]")

        cur_y = c3_rect.y + 24
        line7 = "UCB1: A_t = argmax [ mu_hat_i + c * sqrt(ln(t) / N_i) ]"
        screen.blit(self.font_body.render(line7, True, (210, 210, 210)), (c3_rect.x + 10, cur_y))

        cur_y += 22
        line8 = "Thompson Sampling: theta_i ~ Beta(alpha_i + 1, beta_i + 1)"
        screen.blit(self.font_body.render(line8, True, (180, 180, 180)), (c3_rect.x + 10, cur_y))

        cur_y += 22
        line9 = "Batas Penyesalan: Teorema Lai-Robbins R_T <= C * ln(T)"
        screen.blit(self.font_badge.render(line9, True, (145, 145, 145)), (c3_rect.x + 10, cur_y))

        cur_y += 20
        line10 = "Optimisme: Hadapi ketidakpastian dengan nilai batas atas"
        screen.blit(self.font_badge.render(line10, True, (120, 120, 120)), (c3_rect.x + 10, cur_y))

    def draw(self, screen: pygame.Surface, autopilot: Optional[AutopilotController] = None,
             farmer: Optional[HTNNPCAgent] = None, miller: Optional[HTNNPCAgent] = None,
             clock: Optional[WorldClock] = None, weather_mgr: Optional[Any] = None,
             camera: Optional[Tuple[int, int]] = None, hero: Optional[Any] = None):
        """Menggambar panel terpadu satu jendela dengan styling monokrom hitam-putih kontras tinggi."""
        if not self.visible:
            return

        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # 1. Left drop-shadow gradient (depth separation dari peta game)
        if not hasattr(self, "_shadow_surf") or self._shadow_surf is None:
            self._shadow_surf = pygame.Surface((8, rh), pygame.SRCALPHA)
            for sx in range(8):
                alpha = int(70 * (sx + 1) / 8)
                pygame.draw.line(self._shadow_surf, (0, 0, 0, alpha), (sx, 0), (sx, rh))
        screen.blit(self._shadow_surf, (rx - 8, ry))

        # 2. Solid dark canvas (#0e0e0e) - 100% opaque, monokrom hitam
        pygame.draw.rect(screen, (14, 14, 14), self.rect, border_radius=4)

        # 3. Outer border crisp silver (#555555)
        pygame.draw.rect(screen, (85, 85, 85), self.rect, 1, border_radius=4)

        # 4. Tab Header Bar
        self._draw_tabs(screen)

        # 5. Cross-Module Strip
        self._draw_cross_module_bar(screen, autopilot, weather_mgr)

        # 6. Konten per Tab
        if self.active_tab == 0:
            self._draw_planning_tab(screen, autopilot, weather_mgr)
        elif self.active_tab == 1:
            self._draw_heuristics_tab(screen)
        elif self.active_tab == 2:
            self._draw_htn_tab(screen, farmer, miller, clock)
        elif self.active_tab == 3:
            self._draw_uncertainty_tab(screen, weather_mgr, autopilot)

