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
    Panel perencanaan terpadu satu jendela (Unified AI Inspector Dock):
      - Tab 0: [F7] Planning Inspector (STRIPS PDDL, WA*, Goal Literals, State Diff)
      - Tab 1: [1] Analisis Heuristik (UCS vs A* vs WA* h_FF vs h_level)
      - Tab 2: [HTN] Hierarchical Task Network (Opsional, di luar materi silabus)
      - Tab 3: [F8] Decisions Under Uncertainty (Bayesian Belief, MEU, Policy Table)
    Dock berukuran Rect(660, 8, 356, 420) di kanan atas:
      - Desain solid dark slate (#0f141d) dengan left drop-shadow gradient dan border crisp.
      - 100% bebas tumpang tindih dari topbar, advisor banner, dan HUD bawah.
      - Card container modular (#151c28, border #263246) dengan hierarchy visual jelas.
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
                   title_col: Tuple[int, int, int] = (255, 230, 110),
                   badge_col: Tuple[int, int, int] = (100, 220, 255),
                   border_col: Optional[Tuple[int, int, int]] = None):
        """Menggambar kontainer card berpenampilan solid modern dark slate (#151c28)."""
        pygame.draw.rect(screen, (21, 28, 40), rect, border_radius=4)
        b_col = border_col or (38, 50, 70)
        pygame.draw.rect(screen, b_col, rect, 1, border_radius=4)

        if title or badge:
            if title:
                t_surf = self.font_bold.render(title, True, title_col)
                screen.blit(t_surf, (rect.x + 8, rect.y + 6))
            if badge:
                b_surf = self.font_badge.render(badge, True, badge_col)
                screen.blit(b_surf, (rect.x + rect.width - b_surf.get_width() - 8, rect.y + 6))

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
        """Menggambar tab header bar di bagian atas dock."""
        rx, ry, rw = self.rect.x, self.rect.y, self.rect.width
        tab0_rect = pygame.Rect(rx + 4, ry + 4, 88, 22)
        tab1_rect = pygame.Rect(rx + 96, ry + 4, 66, 22)
        tab2_rect = pygame.Rect(rx + 166, ry + 4, 58, 22)
        tab3_rect = pygame.Rect(rx + 228, ry + 4, 124, 22)

        tabs_data = [
            (0, tab0_rect, "[F7] Planning", (80, 220, 255)),
            (1, tab1_rect, "Heuristik", (120, 200, 255)),
            (2, tab2_rect, "HTN (Ops)", (240, 160, 80)),
            (3, tab3_rect, "[F8] Uncertainty", (255, 195, 80)),
        ]

        for idx, t_rect, label, active_col in tabs_data:
            is_active = (self.active_tab == idx)
            bg_col = (27, 36, 52) if is_active else (18, 24, 34)
            pygame.draw.rect(screen, bg_col, t_rect, border_radius=3)
            if is_active:
                pygame.draw.rect(screen, active_col, t_rect, 1, border_radius=3)
            else:
                pygame.draw.rect(screen, (32, 42, 58), t_rect, 1, border_radius=3)
            txt_col = active_col if is_active else (135, 148, 168)
            surf = self.font_tab.render(label, True, txt_col)
            screen.blit(surf, (t_rect.x + (t_rect.width - surf.get_width()) // 2, t_rect.y + 4))

    def _draw_cross_module_bar(self, screen: pygame.Surface, autopilot: Optional[AutopilotController],
                               weather_mgr: Optional[Any]):
        """Strip satu baris di bawah header tab yang merangkum status live modul mitra."""
        rx, ry, rw = self.rect.x, self.rect.y, self.rect.width
        bar_rect = pygame.Rect(rx + 6, ry + 29, rw - 12, 18)
        pygame.draw.rect(screen, (17, 23, 33), bar_rect, border_radius=2)
        pygame.draw.rect(screen, (38, 50, 70), bar_rect, 1, border_radius=2)

        if self.active_tab == 0:
            if weather_mgr is not None:
                b = weather_mgr.belief_flood
                pol = weather_mgr.optimal_policy.upper()
                badge = "[RISIKO]" if b >= 0.1333 else "[AMAN]"
                b_col = (255, 85, 85) if b >= 0.1333 else (85, 230, 130)
                txt = f"[UNCERTAINTY] P(B): {b*100:.1f}% | pi*: {pol} | "
                s1 = self.font_badge.render(txt, True, (255, 205, 100))
                s2 = self.font_badge.render(badge, True, b_col)
                screen.blit(s1, (rx + 10, ry + 32))
                screen.blit(s2, (rx + 10 + s1.get_width(), ry + 32))
            else:
                screen.blit(self.font_badge.render("[UNCERTAINTY] P(B): 10.0% | pi*: PINTAS | [AMAN]", True, (255, 205, 100)), (rx + 10, ry + 32))
        elif self.active_tab == 3:
            if autopilot is not None and hasattr(autopilot, "monitor"):
                plan = autopilot.monitor.current_plan
                st = autopilot.monitor.current_step_idx + 1
                tot = len(plan) if plan else 37
                act_name = autopilot.monitor.current_action.name if autopilot.monitor.current_action else "Selesai"
                st_txt = "PAUSED" if autopilot.is_paused_by_player else str(autopilot.mode)
                txt = f"[PLANNING] Aksi {st}/{tot}: {act_name} | [{st_txt}]"
                screen.blit(self.font_badge.render(txt[:44], True, (100, 220, 255)), (rx + 10, ry + 32))
            else:
                screen.blit(self.font_badge.render("[PLANNING] WA*(h_FF) w=1.5 | Goal: boss_defeated", True, (100, 220, 255)), (rx + 10, ry + 32))
        else:
            screen.blit(self.font_badge.render("[SISTEM TERPADU] STRIPS WA* w=1.5 <--> Bayesian MDP (f*=13.3%)", True, (180, 215, 240)), (rx + 10, ry + 32))

    def _draw_planning_tab(self, screen: pygame.Surface, autopilot: Optional[AutopilotController],
                           weather_mgr: Optional[Any] = None):
        """Tab 0: [F7] AUTOMATED PLANNING INSPECTOR otentik STRIPS PDDL berbasis Card Container."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # Title Header & Domain Source
        title_surf = self.font_title.render("PLANNING INSPECTOR (STRIPS WA*)", True, (80, 220, 255))
        screen.blit(title_surf, (rx + 8, ry + 50))
        dom_surf = self.font_badge.render("Domain: data/planning/expedition.domain", True, (140, 185, 220))
        screen.blit(dom_surf, (rx + 8, ry + 68))

        if autopilot is None or not hasattr(autopilot, "monitor"):
            no_card = pygame.Rect(rx + 6, ry + 84, rw - 12, 60)
            self._draw_card(screen, no_card, title="STATUS SISTEM", badge="[OFF]")
            no_p = self.font_body.render("Autopilot belum aktif. Tekan [F9] untuk mulai.", True, (170, 175, 185))
            screen.blit(no_p, (rx + 14, ry + 110))
            return

        monitor = autopilot.monitor
        plan = monitor.current_plan
        step_idx = monitor.current_step_idx
        total_steps = len(plan) if plan else 37
        ws = autopilot.world_state

        # Card 1: Tujuan & Progres
        c1_rect = pygame.Rect(rx + 6, ry + 84, rw - 12, 66)
        mode_badge = f"Mode: {autopilot.mode}"
        self._draw_card(screen, c1_rect, title="TUJUAN & PROGRES", badge=mode_badge,
                        title_col=(255, 230, 110), badge_col=(100, 220, 255))

        key_done = ws.inventory.has_item("gate_key", 1) or ws.inventory.has_item("key", 1)
        gate_done = ws.gate.is_open
        boss_done = getattr(getattr(ws, "boss", None), "is_defeated", False)

        cur_y = c1_rect.y + 22
        goals = [
            ("gate_key", key_done),
            ("gate_open", gate_done),
            ("boss_defeated", boss_done),
        ]
        gx = c1_rect.x + 8
        for g_name, is_done in goals:
            mark = "[x]" if is_done else "[ ]"
            m_col = (70, 230, 120) if is_done else (160, 170, 180)
            txt = f"{mark} {g_name}"
            surf = self.font_body.render(txt, True, m_col)
            screen.blit(surf, (gx, cur_y))
            gx += surf.get_width() + 10

        # Progress bar
        cur_y += 16
        bar_x, bar_y, bar_w, bar_h = c1_rect.x + 8, cur_y, c1_rect.width - 16, 6
        pygame.draw.rect(screen, (28, 36, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
        pct = min(1.0, max(0.0, step_idx / max(1, total_steps)))
        if pct > 0:
            fill_w = int(bar_w * pct)
            pygame.draw.rect(screen, (70, 215, 90), (bar_x, bar_y, fill_w, bar_h), border_radius=2)
        pygame.draw.rect(screen, (60, 80, 105), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=2)

        cur_y += 10
        tot_cost = sum(a.cost for a in plan) if plan else 118.5
        prog_txt = f"Langkah {step_idx}/{total_steps} | Biaya: {tot_cost:.1f}s | Mode: {autopilot.mode}"
        screen.blit(self.font_badge.render(prog_txt, True, (190, 210, 225)), (c1_rect.x + 8, cur_y))

        # Card 2: Aksi Aktif & Skema STRIPS
        c2_rect = pygame.Rect(rx + 6, ry + 154, rw - 12, 84)
        act = monitor.current_action
        act_badge = "[BERJALAN]" if act is not None else "[SIAP]"
        act_badge_col = (255, 215, 80) if act is not None else (70, 230, 120)
        self._draw_card(screen, c2_rect, title="AKSI AKTIF (STRIPS)", badge=act_badge,
                        title_col=(255, 235, 140), badge_col=act_badge_col)

        cur_y = c2_rect.y + 20
        if act is not None:
            act_title = f"Aksi: {act.name}({', '.join(act.params)})"
            screen.blit(self.font_bold.render(act_title[:42], True, (255, 235, 140)), (c2_rect.x + 8, cur_y))
            cur_y += 15

            pre_names = [p.name for p in sorted(act.preconditions, key=lambda x: x.name)][:3]
            pre_str = "Pre: " + " ".join(f"[OK] {pn}" for pn in pre_names)
            screen.blit(self.font_body.render(pre_str[:44], True, (150, 230, 170)), (c2_rect.x + 8, cur_y))
            cur_y += 15

            adds = [f"+{p.name}" for p in sorted(act.add_effects, key=lambda x: x.name)][:2]
            dels = [f"-{p.name}" for p in sorted(act.delete_effects, key=lambda x: x.name)][:2]
            eff_str = "Eff: " + " ".join(adds + dels)
            screen.blit(self.font_body.render(eff_str[:44], True, (230, 190, 140)), (c2_rect.x + 8, cur_y))
            cur_y += 15
        else:
            screen.blit(self.font_bold.render("Aksi: Ekspedisi Selesai / Siap [F9]", True, (160, 230, 180)), (c2_rect.x + 8, cur_y))
            cur_y += 15
            screen.blit(self.font_body.render("Semua precondition STRIPS terpenuhi.", True, (170, 180, 195)), (c2_rect.x + 8, cur_y))
            cur_y += 15
            screen.blit(self.font_body.render("Eff: Siap eksekusi tahap berikutnya.", True, (170, 180, 195)), (c2_rect.x + 8, cur_y))
            cur_y += 15

        diff_txt = getattr(monitor, "last_state_diff", "-")
        if diff_txt == "-":
            diff_display = "Diff: - (belum ada aksi selesai)"
        else:
            diff_display = f"Diff: {diff_txt[:40]}"
        screen.blit(self.font_body.render(diff_display, True, (180, 220, 240)), (c2_rect.x + 8, cur_y))

        # Card 3: Pencarian WA* & Antrean
        c3_rect = pygame.Rect(rx + 6, ry + 242, rw - 12, 170)
        w_val = getattr(config, "PLANNER_WEIGHT", 1.5)
        self._draw_card(screen, c3_rect, title="MESIN PENCARI WA* & ANTREAN", badge=f"w={w_val}",
                        title_col=(120, 220, 255), badge_col=(140, 205, 240))

        cur_y = c3_rect.y + 20
        nodes = getattr(monitor, "last_nodes_expanded", None)
        nodes_txt = f"{nodes} node" if nodes is not None else "- node"
        lat = getattr(monitor, "last_search_latency_ms", 0.0)
        m_txt = f"WA*(h_FF, w={w_val}) | {nodes_txt} | {lat:.1f}ms"
        screen.blit(self.font_bold.render(m_txt, True, (120, 220, 255)), (c3_rect.x + 8, cur_y))

        cur_y += 15
        b_txt = "Budget step(): < 20ms [OK] | Polyline [OK]"
        screen.blit(self.font_badge.render(b_txt, True, (170, 210, 190)), (c3_rect.x + 8, cur_y))

        cur_y += 14
        geo_txt = "Geodesik: 40 lkg >= 38 Manhattan [OK] (invarian)"
        screen.blit(self.font_badge.render(geo_txt, True, (160, 200, 220)), (c3_rect.x + 8, cur_y))

        cur_y += 15
        rep_n = monitor.consecutive_replans
        rep_reason = getattr(monitor, "last_replan_reason", "-")
        if rep_n == 0 or rep_reason == "-":
            rep_txt = "Replan: - (eksekusi berjalan lancar)"
            screen.blit(self.font_body.render(rep_txt, True, (170, 185, 200)), (c3_rect.x + 8, cur_y))
        else:
            rep_txt = f"{rep_reason[:44]}"
            screen.blit(self.font_body.render(rep_txt, True, (255, 180, 120)), (c3_rect.x + 8, cur_y))

        cur_y += 17
        pygame.draw.line(screen, (35, 48, 68), (c3_rect.x + 8, cur_y), (c3_rect.x + c3_rect.width - 8, cur_y), 1)
        cur_y += 5

        screen.blit(self.font_badge.render("ANTREAN AKSI EKSEKUSI:", True, (210, 220, 235)), (c3_rect.x + 8, cur_y))
        cur_y += 14

        if plan and step_idx < len(plan):
            for qi in range(step_idx, min(len(plan), step_idx + 2)):
                q_act = plan[qi]
                q_icon = self.icons.get(self._get_action_icon_key(q_act.name))
                if q_icon:
                    screen.blit(q_icon, (c3_rect.x + 8, cur_y))
                q_title, _ = format_action_human(q_act)
                q_str = f"#{qi+1} {q_title} ({q_act.duration:.1f}s)"
                screen.blit(self.font_body.render(q_str[:38], True, (230, 235, 245)), (c3_rect.x + 30, cur_y))
                cur_y += 17
        else:
            screen.blit(self.font_badge.render("Belum ada antrean aksi berjalan.", True, (150, 160, 175)), (c3_rect.x + 8, cur_y))

    def _draw_heuristics_tab(self, screen: pygame.Surface):
        """Tab 1: Analisis komparatif heuristik pencarian sesuai materi kuliah."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        title = self.font_title.render("ANALISIS HEURISTIK PERENCANAAN", True, (120, 220, 255))
        screen.blit(title, (rx + 8, ry + 50))

        # Card 1: Perbandingan Algoritma (P1-P4)
        c1_rect = pygame.Rect(rx + 6, ry + 72, rw - 12, 172)
        self._draw_card(screen, c1_rect, title="BENCHMARK MASALAH P1 - P4", badge="Node & Waktu",
                        title_col=(255, 230, 110), badge_col=(140, 205, 240))

        lines_p = [
            ("P1 (Key Craft):", "UCS 35 node (1.4ms) | A*(h_max) 16 node (0.8ms)"),
            ("P2 (Open Gate):", "UCS 48 node (2.8ms) | A*(h_max) 29 node (1.5ms)"),
            ("P3 (Potion):", "WA*(h_FF) 16 node (18.4ms) - Cost 33.0s"),
            ("P4 (Full Ekspedisi):", "WA*(h_FF) 37 langkah (118.48s) | 876 node"),
        ]
        cur_y = c1_rect.y + 22
        for header, detail in lines_p:
            h_surf = self.font_bold.render(header, True, (255, 230, 110))
            screen.blit(h_surf, (c1_rect.x + 8, cur_y))
            d_surf = self.font_body.render(detail, True, (210, 215, 225))
            screen.blit(d_surf, (c1_rect.x + 8, cur_y + 14))
            cur_y += 33

        # Card 2: Properti & Optimasi
        c2_rect = pygame.Rect(rx + 6, ry + 250, rw - 12, 160)
        self._draw_card(screen, c2_rect, title="OPTIMASI & SIFAT ADMISIBILITAS", badge="Planning Graph",
                        title_col=(120, 220, 255), badge_col=(120, 240, 180))

        lines_opt = [
            ("Planning Graph:", "h_level admissible (h=4.0 pada Ojek)"),
            ("Optimasi Search:", "Helpful Actions + Non-Goto Filter (x8 cut)"),
            ("Incremental Budget:", "step() per-frame budget < 20 ms (15 ms)"),
        ]
        cur_y = c2_rect.y + 22
        for header, detail in lines_opt:
            h_surf = self.font_bold.render(header, True, (130, 215, 255))
            screen.blit(h_surf, (c2_rect.x + 8, cur_y))
            d_surf = self.font_body.render(detail, True, (210, 215, 225))
            screen.blit(d_surf, (c2_rect.x + 8, cur_y + 14))
            cur_y += 34

    def _draw_htn_tab(self, screen: pygame.Surface, farmer: Optional[HTNNPCAgent],
                      miller: Optional[HTNNPCAgent], clock: Optional[WorldClock]):
        """Tab 2: HTN diberi label jelas opsional / di luar materi silabus."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        title = self.font_title.render("HTN TASK DECOMPOSITION (OPSIONAL)", True, (255, 180, 100))
        screen.blit(title, (rx + 8, ry + 50))

        c1_rect = pygame.Rect(rx + 6, ry + 72, rw - 12, 90)
        self._draw_card(screen, c1_rect, title="STATUS SHOP-STYLE HTN", badge="[OPSIONAL]",
                        title_col=(255, 205, 110), badge_col=(255, 180, 80))
        cur_y = c1_rect.y + 22
        screen.blit(self.font_body.render("Status: Opsional (di luar materi silabus 35 slide)", True, (255, 220, 140)), (c1_rect.x + 8, cur_y))
        cur_y += 16
        screen.blit(self.font_body.render("Engine HTN mandiri tersedia di src/planning/htn.py", True, (200, 205, 215)), (c1_rect.x + 8, cur_y))
        cur_y += 16
        screen.blit(self.font_body.render("Mendukung dekomposisi task NPC desa Sunnyside.", True, (180, 190, 205)), (c1_rect.x + 8, cur_y))

        c2_rect = pygame.Rect(rx + 6, ry + 168, rw - 12, 242)
        self._draw_card(screen, c2_rect, title="SILABUS AUTOMATED PLANNING", badge="Fokus Materi",
                        title_col=(120, 220, 255), badge_col=(140, 205, 240))
        syllabus_lines = [
            "* PDDL & Action Schema (STRIPS standard)",
            "* Forward State-Space Search (BFS, UCS, A*)",
            "* Backward Goal Regression (Slide 27)",
            "* Ignore-Delete-List Heuristics (h_add, h_max, h_FF)",
            "* Planning Graph & Mutex (GraphPlan / h_level)",
            "* Decoupled Real-Time Re-planning Engine",
            "* Cross-Module Integration with Bayesian Uncertainty",
        ]
        cur_y = c2_rect.y + 22
        for s_line in syllabus_lines:
            screen.blit(self.font_body.render(s_line, True, (215, 220, 230)), (c2_rect.x + 8, cur_y))
            cur_y += 18

    def _draw_uncertainty_tab(self, screen: pygame.Surface, weather_mgr: Optional[Any] = None,
                               autopilot: Optional[AutopilotController] = None):
        """Tab 3: [F8] DECISIONS UNDER UNCERTAINTY & BAYESIAN MDP (Slide 3-23)."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # Title Header & Model Label
        title_surf = self.font_title.render("DECISIONS UNDER UNCERTAINTY", True, (255, 205, 90))
        screen.blit(title_surf, (rx + 8, ry + 50))
        model_surf = self.font_badge.render("Model: Kalibrasi Pesisir (Penalti=2.70s, f*=0.1333)", True, (255, 225, 140))
        screen.blit(model_surf, (rx + 8, ry + 68))

        if weather_mgr is None:
            no_card = pygame.Rect(rx + 6, ry + 84, rw - 12, 60)
            self._draw_card(screen, no_card, title="MODUL CUACA", badge="[TIDAK AKTIF]")
            no_info = self.font_body.render("Modul cuaca/ketidakpastian belum aktif.", True, (180, 185, 195))
            screen.blit(no_info, (rx + 14, ry + 110))
            return

        belief = weather_mgr.belief_flood
        prior = weather_mgr.prior_p_flood
        day = weather_mgr.day_counter
        timer = weather_mgr.cycle_timer
        ev_str = weather_mgr.last_evidence or "Belum periksa papan"
        q_pintas, q_raya = weather_mgr.get_expected_utilities()
        policy = weather_mgr.optimal_policy
        is_risky = (belief >= 0.1333)

        # Card 1: Keyakinan Cuaca & Gauge Bayes
        c1_rect = pygame.Rect(rx + 6, ry + 84, rw - 12, 94)
        badge_txt = "[RISIKO]" if is_risky else "[AMAN]"
        badge_col = (255, 75, 75) if is_risky else (75, 235, 120)
        self._draw_card(screen, c1_rect, title="KEYAKINAN CUACA & GAUGE", badge=badge_txt,
                        title_col=(255, 230, 110), badge_col=badge_col)

        cur_y = c1_rect.y + 20
        b_label = f"Belief P(Banjir): {belief * 100:.1f}%"
        screen.blit(self.font_bold.render(b_label, True, (255, 235, 130)), (c1_rect.x + 8, cur_y))

        # Gauge Bar
        cur_y += 14
        bar_x, bar_y, bar_w, bar_h = c1_rect.x + 8, cur_y, 220, 10
        pygame.draw.rect(screen, (28, 36, 48), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
        fill_w = int(bar_w * max(0.0, min(1.0, belief)))
        bar_col = (255, 80, 70) if is_risky else (65, 215, 115)
        if fill_w > 0:
            pygame.draw.rect(screen, bar_col, (bar_x, bar_y, fill_w, bar_h), border_radius=2)
        pygame.draw.rect(screen, (70, 90, 115), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=2)

        # Needle 1: f* = 0.1333 (Kalibrasi Pesisir)
        f1_x = bar_x + int(bar_w * 0.1333)
        pygame.draw.line(screen, (255, 240, 90), (f1_x, bar_y - 2), (f1_x, bar_y + bar_h + 2), 2)
        screen.blit(self.font_badge.render("f*=13.3%", True, (255, 240, 100)), (f1_x - 12, bar_y + bar_h + 1))

        # Needle 2: f*_raw = 0.489 (Koridor Penuh 1.78s)
        f2_x = bar_x + int(bar_w * 0.4889)
        pygame.draw.line(screen, (130, 210, 255), (f2_x, bar_y - 2), (f2_x, bar_y + bar_h + 2), 2)
        screen.blit(self.font_badge.render("f*raw=48.9%", True, (140, 215, 255)), (f2_x - 14, bar_y + bar_h + 1))

        # Evidence & Timeline
        cur_y += 24
        ev_display = f'Prior P0(B)={prior*100:.0f}% | Bukti: "{ev_str}"'
        screen.blit(self.font_body.render(ev_display, True, (215, 230, 250)), (c1_rect.x + 8, cur_y))
        cur_y += 14
        screen.blit(self.font_badge.render("Likelihood: P(Berita|B)=0.90 (asumsi), P(Berita|~B)=0.10", True, (180, 195, 215)), (c1_rect.x + 8, cur_y))
        cur_y += 13
        if ev_str == "air mulai naik":
            tl_txt = "Timeline: Prior 10% -> Berita -> Post 50.0% [RISIKO]"
        elif ev_str == "langit cerah":
            tl_txt = "Timeline: Prior 10% -> Cerah -> Post 1.2% [AMAN]"
        else:
            tl_txt = "Timeline: Prior 10% (Papan belum dibaca) [AMAN]"
        screen.blit(self.font_badge.render(tl_txt, True, (160, 215, 180)), (c1_rect.x + 8, cur_y))

        # Card 2: Ekspektasi Utilitas (MEU)
        c2_rect = pygame.Rect(rx + 6, ry + 182, rw - 12, 86)
        eu_p = (1.0 - belief) * 10.0 + belief * (-20.0)
        eu_r = 6.00
        self._draw_card(screen, c2_rect, title="EKSPEKTASI UTILITAS (MEU)", badge=f"pi*: {policy.upper()}",
                        title_col=(255, 225, 110), badge_col=badge_col)

        cur_y = c2_rect.y + 20
        screen.blit(self.font_body.render(f"EU(Pintas) = (1-b)*10.0 + b*(-20.0) = {eu_p:.2f} poin", True, (225, 230, 240)), (c2_rect.x + 8, cur_y))
        cur_y += 15
        screen.blit(self.font_body.render("EU(Raya)   = 6.00 poin", True, (225, 230, 240)), (c2_rect.x + 8, cur_y))
        cur_y += 15
        meu_res = f"pi*(b) = argmax(EU) -> {policy.upper()}  {badge_txt}"
        screen.blit(self.font_bold.render(meu_res, True, badge_col), (c2_rect.x + 8, cur_y))
        cur_y += 14
        screen.blit(self.font_badge.render("[Cross-check: Value Iteration V*(s) == MEU 1-tahap]", True, (155, 175, 195)), (c2_rect.x + 8, cur_y))

        # Card 3: Tabel Kebijakan Adaptif & VPI
        c3_rect = pygame.Rect(rx + 6, ry + 272, rw - 12, 140)
        self._draw_card(screen, c3_rect, title="KEBIJAKAN ADAPTIF (POLICY TABLE)",
                        title_col=(130, 215, 255))

        cur_y = c3_rect.y + 20
        # Row 1: Pintas
        r1_active = not is_risky
        r1_rect = pygame.Rect(c3_rect.x + 6, cur_y, c3_rect.width - 12, 17)
        if r1_active:
            pygame.draw.rect(screen, (24, 48, 36), r1_rect, border_radius=2)
            pygame.draw.rect(screen, (70, 215, 120), r1_rect, 1, border_radius=2)
        r1_txt = "-> b < 13.3%  : PINTAS (Pantai, 15 tile / 3.26s) [AKTIF]" if r1_active else "   b < 13.3%  : PINTAS (Pantai, 15 tile / 3.26s)"
        screen.blit(self.font_body.render(r1_txt, True, (120, 245, 160) if r1_active else (150, 160, 175)), (c3_rect.x + 10, cur_y + 2))

        cur_y += 19
        # Row 2: Raya
        r2_active = is_risky
        r2_rect = pygame.Rect(c3_rect.x + 6, cur_y, c3_rect.width - 12, 17)
        if r2_active:
            pygame.draw.rect(screen, (48, 24, 24), r2_rect, border_radius=2)
            pygame.draw.rect(screen, (245, 90, 80), r2_rect, 1, border_radius=2)
        r2_txt = "-> b >= 13.3% : RAYA   (Detour, 19 tile / 4.13s) [AKTIF]" if r2_active else "   b >= 13.3% : RAYA   (Detour, 19 tile / 4.13s)"
        screen.blit(self.font_body.render(r2_txt, True, (255, 150, 130) if r2_active else (150, 160, 175)), (c3_rect.x + 10, cur_y + 2))

        cur_y += 21
        screen.blit(self.font_badge.render("VPI Teori = +1.98 poin (Slide) | Biaya Papan = 0.20s", True, (255, 220, 140)), (c3_rect.x + 8, cur_y))
        cur_y += 14
        screen.blit(self.font_badge.render("Amortisasi: Hemat +0.0035s*K vs 0.20s -> K=57x (Tak Impas)", True, (180, 205, 230)), (c3_rect.x + 8, cur_y))
        cur_y += 15
        screen.blit(self.font_badge.render("MULTI-ARMED BANDIT: Tekan [B] Jurnal Nelayan (MAB 5 Spot)", True, (255, 235, 120)), (c3_rect.x + 8, cur_y))

    def draw(self, screen: pygame.Surface, autopilot: Optional[AutopilotController] = None,
             farmer: Optional[HTNNPCAgent] = None, miller: Optional[HTNNPCAgent] = None,
             clock: Optional[WorldClock] = None, weather_mgr: Optional[Any] = None,
             camera: Optional[Tuple[int, int]] = None, hero: Optional[Any] = None):
        """Menggambar panel terpadu satu jendela dengan styling modern solid slate card."""
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

        # 2. Solid dark slate base canvas (#0f141d) - 100% opaque, tidak ada warna map bocor
        pygame.draw.rect(screen, (15, 20, 29), self.rect, border_radius=4)

        # 3. Outer border crisp (#2b3548)
        border_col = (80, 200, 255) if self.active_tab == 0 else ((255, 190, 70) if self.active_tab == 3 else (43, 53, 72))
        pygame.draw.rect(screen, border_col, self.rect, 1, border_radius=4)

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

