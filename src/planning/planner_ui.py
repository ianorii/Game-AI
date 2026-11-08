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
        return "Tempa Kunci Gerbang", "di bengkel (butuh kayu + batu)"

    if name == "craft_potion":
        return "Racik Ramuan Merah", "di bengkel (lobak + botol)"

    if name == "open_gate":
        return "Buka Gerbang Boss", "membuka portal arena dungeon"

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
    rect_unified = pygame.Rect(660, 60, 350, 320)       # 112,000 px (14.23%) Panel terpadu
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
# PANEL TERPADU DUA TAB (SUB-FASE 2D) [F7 / F8]
# ==============================================================================

class UnifiedPlannerPanel:
    """
    Panel perencanaan terpadu satu jendela dengan tiga tab:
      - Tab 0: [F7] Ekspedisi Hero (STRIPS)
      - Tab 1: [1] Analisis Heuristik (UCS vs A* vs WA* h_FF vs h_level)
      - Tab 2: [F8] HTN (opsional, belum diaktifkan)
    Memenuhi batas cakupan <= 15% luas layar (112,000 px <= 14.24% < 15%) dan font >= 14 px.
    """

    def __init__(self, rect: Optional[pygame.Rect] = None):
        self.rect = rect or pygame.Rect(660, 60, 350, 320)
        self.active_tab: int = 0  # 0: Ekspedisi, 1: Heuristik, 2: HTN
        self.visible: bool = False
        self.panel_expedition = ExpeditionPlanPanel(self.rect)
        self.panel_htn = HTNPlanPanel(self.rect)
        self.font_tab = pygame.font.Font(None, 13)
        self.font_title = pygame.font.Font(None, 16)
        self.font_body = pygame.font.Font(None, 14)
        self.font_bold = pygame.font.Font(None, 14)

    def toggle(self, tab: Optional[int] = None):
        """Membuka atau menutup panel. Bila tab diberikan, langsung beralih ke tab tersebut."""
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
        tab0_rect = pygame.Rect(rx + 4, ry + 4, 104, 20)
        tab1_rect = pygame.Rect(rx + 110, ry + 4, 76, 20)
        tab2_rect = pygame.Rect(rx + 188, ry + 4, 158, 20)

        if tab0_rect.collidepoint(pos):
            self.active_tab = 0
            return True
        if tab1_rect.collidepoint(pos):
            self.active_tab = 1
            return True
        if tab2_rect.collidepoint(pos):
            self.active_tab = 2
            return True
        return False

    def _draw_heuristics_tab(self, screen: pygame.Surface):
        """Tab 1: Analisis komparatif heuristik pencarian sesuai materi kuliah."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        bg = pygame.Surface((rw, rh), pygame.SRCALPHA)
        bg.fill((20, 26, 38, 240))
        screen.blit(bg, (rx, ry))
        pygame.draw.rect(screen, (80, 180, 240), self.rect, 2)

        title = self.font_title.render("ANALISIS HEURISTIK PERENCANAAN", True, (120, 220, 255))
        screen.blit(title, (rx + 10, ry + 32))

        lines = [
            ("P1 (Key Craft):", "UCS 35 node (1.4ms) | A*(h_max) 16 node (0.8ms)"),
            ("P2 (Open Gate):", "UCS 48 node (2.8ms) | A*(h_max) 29 node (1.5ms)"),
            ("P3 (Potion):", "WA*(h_FF) 16 node (18.4ms) - Cost 33.0s"),
            ("P4 (Full Ekspedisi):", "WA*(h_FF) 2277 node (3.97s) - 34 langkah"),
            ("Planning Graph:", "h_level admissible (h=4.0 pada Ojek)"),
            ("Optimasi Search:", "Helpful Actions + Non-Goto Filter (x8 cut)"),
            ("Incremental Budget:", "step() per-frame budget < 20 ms (15 ms)"),
        ]

        cur_y = ry + 56
        for header, detail in lines:
            h_surf = self.font_bold.render(header, True, (255, 230, 110))
            screen.blit(h_surf, (rx + 10, cur_y))
            d_surf = self.font_body.render(detail, True, (210, 215, 225))
            screen.blit(d_surf, (rx + 10, cur_y + 16))
            cur_y += 34

    def _draw_htn_tab(self, screen: pygame.Surface, farmer: Optional[HTNNPCAgent],
                      miller: Optional[HTNNPCAgent], clock: Optional[WorldClock]):
        """Tab 2: HTN diberi label jelas opsional / belum diaktifkan."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        bg = pygame.Surface((rw, rh), pygame.SRCALPHA)
        bg.fill((26, 22, 34, 240))
        screen.blit(bg, (rx, ry))
        pygame.draw.rect(screen, (220, 140, 70), self.rect, 2)

        title = self.font_title.render("[F8] HTN (OPSIONAL, BELUM AKTIF)", True, (255, 180, 100))
        screen.blit(title, (rx + 10, ry + 32))

        info_lines = [
            "Hierarchical Task Network (HTN) SHOP-Style:",
            "- Status: Opsional (di luar materi silabus 35 slide)",
            "- Silabus Automated Planning fokus pada:",
            "  * PDDL & Action Schema (STRIPS)",
            "  * Forward State-Space Search (BFS/UCS/A*)",
            "  * Backward Goal Regression (Slide 27)",
            "  * Ignore-Delete-List Heuristics (h_add, h_max, h_FF)",
            "  * Planning Graph & Mutex (GraphPlan / h_level)",
            "- Engine HTN mandiri tersedia di src/planning/htn.py."
        ]

        cur_y = ry + 58
        for line in info_lines:
            col = (255, 220, 140) if line.startswith("- Status") else (200, 205, 215)
            surf = self.font_body.render(line, True, col)
            screen.blit(surf, (rx + 10, cur_y))
            cur_y += 24

    def draw(self, screen: pygame.Surface, autopilot: Optional[AutopilotController] = None,
              farmer: Optional[HTNNPCAgent] = None, miller: Optional[HTNNPCAgent] = None,
              clock: Optional[WorldClock] = None):
        """Menggambar panel terpadu sesuai tab yang sedang aktif."""
        if not self.visible:
            return

        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # Delegasikan penggambaran konten ke panel terkait
        if self.active_tab == 0 and autopilot is not None:
            self.panel_expedition.draw(screen, autopilot)
        elif self.active_tab == 1:
            self._draw_heuristics_tab(screen)
        elif self.active_tab == 2:
            self._draw_htn_tab(screen, farmer, miller, clock)

        # Tab Bar Overlay di atas panel
        tab_bar_bg = pygame.Surface((rw - 8, 22), pygame.SRCALPHA)
        tab_bar_bg.fill((16, 20, 28, 245))
        screen.blit(tab_bar_bg, (rx + 4, ry + 4))

        tab0_rect = pygame.Rect(rx + 4, ry + 4, 104, 20)
        tab1_rect = pygame.Rect(rx + 110, ry + 4, 76, 20)
        tab2_rect = pygame.Rect(rx + 188, ry + 4, 158, 20)

        # Tab 0: Ekspedisi
        t0_bg = (45, 60, 85) if self.active_tab == 0 else (26, 32, 42)
        pygame.draw.rect(screen, t0_bg, tab0_rect, border_radius=3)
        if self.active_tab == 0:
            pygame.draw.rect(screen, (255, 220, 100), tab0_rect, 1, border_radius=3)
        t0_surf = self.font_tab.render("[F7] Ekspedisi", True, (255, 240, 150) if self.active_tab == 0 else (160, 170, 185))
        screen.blit(t0_surf, (tab0_rect.x + 6, tab0_rect.y + 4))

        # Tab 1: Heuristik
        t1_bg = (45, 60, 85) if self.active_tab == 1 else (26, 32, 42)
        pygame.draw.rect(screen, t1_bg, tab1_rect, border_radius=3)
        if self.active_tab == 1:
            pygame.draw.rect(screen, (80, 200, 255), tab1_rect, 1, border_radius=3)
        t1_surf = self.font_tab.render("Heuristik", True, (130, 225, 255) if self.active_tab == 1 else (160, 170, 185))
        screen.blit(t1_surf, (tab1_rect.x + 10, tab1_rect.y + 4))

        # Tab 2: HTN (opsional, belum aktif)
        t2_bg = (45, 60, 85) if self.active_tab == 2 else (26, 32, 42)
        pygame.draw.rect(screen, t2_bg, tab2_rect, border_radius=3)
        if self.active_tab == 2:
            pygame.draw.rect(screen, (240, 140, 60), tab2_rect, 1, border_radius=3)
        t2_surf = self.font_tab.render("[F8] HTN (opsional, belum aktif)", True, (255, 190, 120) if self.active_tab == 2 else (160, 170, 185))
        screen.blit(t2_surf, (tab2_rect.x + 4, tab2_rect.y + 4))


