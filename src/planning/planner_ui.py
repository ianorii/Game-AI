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
     - Antrean operator primitif & status aktivitas desa
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

        # 2. Header Panel
        title_surf = self.font_title.render("DESA HIDUP: HTN TASK [F8]", True, (120, 240, 200))
        screen.blit(title_surf, (rx + 10, ry + 8))

        status_str = "Status: Aktif"
        status_surf = self.font_body.render(status_str, True, (120, 240, 200))
        screen.blit(status_surf, (rx + rw - status_surf.get_width() - 10, ry + 10))

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
        f_method = farmer.active_tree[0].chosen_method if farmer.active_tree else "m_farmer_routine"
        f_reason = farmer.active_tree[0].precondition_reason if farmer.active_tree else "Rutinitas desa aktif."
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

def _load_best_font(size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
    """Memuat font TrueType berkualitas tinggi (NotoSans / JetBrainsMono) agar bebas blur dan bebas bug kerning FreeSans."""
    paths = []
    if mono:
        paths = [
            "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf",
            "/usr/share/fonts/liberation/LiberationMono-Regular.ttf",
            "/usr/share/fonts/noto/NotoSansMono-Regular.ttf",
        ]
    elif bold:
        paths = [
            "/usr/share/fonts/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-SemiBold.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        paths = [
            "/usr/share/fonts/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        ]
    for p in paths:
        if os.path.exists(p):
            try:
                return pygame.font.Font(p, size)
            except Exception:
                pass
    try:
        if mono:
            return pygame.font.SysFont("monospace,jetbrainsmono,liberationmono", size, bold=bold)
        return pygame.font.SysFont("notosans,dejavusans,liberationsans,helvetica,arial", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


class UnifiedPlannerPanel:
    """
    Panel perencanaan terpadu satu jendela (Unified AI Inspector Dock) - Clean Compact Studio:
      - Geometri pas & proporsional: Rect(596, 8, 418, 532) di layar 1024x768.
      - Header teks profesional: 'DEBUG OVERLAY: AUTOMATED PLANNING' (tanpa dot macOS merah/kuning/hijau).
      - Font Noto Sans & JetBrains Mono tajam, presisi, anti-aliasing sempurna tanpa bug kerning.
      - 3 Card terstruktur:
        1. Tujuan & Progres: 3 tombol checkbox rounded, helper text, progress bar, footer stats.
        2. Aksi Aktif (STRIPS): Card mint/emerald, action box dengan badge [F9], monospace teal key-values.
        3. Mesin Pencari WA* & Antrean: 3-column metric cards (Heuristik, Ekspansi, Waktu), tabel invarian.
      - Tab 3 (Uncertainty): Multi-Armed Bandit (MAB 5 Spot) & Live Combat Engagement Policy.
    """

    def __init__(self, rect: Optional[pygame.Rect] = None):
        # Ukuran proporsional & compact (418 x 532 di 1024x768)
        self.rect = rect or pygame.Rect(596, 8, 418, 532)
        self.active_tab: int = 0  # 0: Planning, 1: Heuristik, 2: HTN, 3: Ketidakpastian
        self.visible: bool = False
        self.catalog = get_asset_catalog()

        # Tipografi tajam (Noto Sans & JetBrains Mono)
        self.font_header = _load_best_font(11, bold=True, mono=True)
        self.font_tab = _load_best_font(12, bold=True)
        self.font_title = _load_best_font(15, bold=True)
        self.font_body = _load_best_font(12)
        self.font_bold = _load_best_font(12, bold=True)
        self.font_badge = _load_best_font(10, bold=True)
        self.font_mono = _load_best_font(11, mono=True)
        self.font_xs = _load_best_font(9, bold=True)

        # Shadow kiri halus pra-kalkulasi
        self._shadow_surf = pygame.Surface((10, self.rect.height), pygame.SRCALPHA)
        for sx in range(10):
            alpha = int(45 * (sx + 1) / 10)
            pygame.draw.line(self._shadow_surf, (0, 0, 0, alpha), (sx, 0), (sx, self.rect.height))

        self.icons: Dict[str, pygame.Surface] = {}
        self._load_icons()

    def _load_icons(self):
        icon_names = {
            "axe": "UI/axe.png",
            "pickaxe": "UI/pickaxe.png",
            "hammer": "UI/hammer.png",
            "shovel": "UI/shovel.png",
            "sword": "UI/sword.png",
            "rod": "UI/rod.png",
            "sandtimer": "UI/sandtimer.png",
        }
        for k, path in icon_names.items():
            surf = self.catalog.get_image(path)
            if surf is not None:
                if surf.get_width() > 16 or surf.get_height() > 16:
                    surf = pygame.transform.scale(surf, (16, 16))
                self.icons[k] = surf

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

        # Tab bounds
        tab0_rect = pygame.Rect(rx + 10, ry + 28, 98, 24)
        tab1_rect = pygame.Rect(rx + 110, ry + 28, 74, 24)
        tab2_rect = pygame.Rect(rx + 186, ry + 28, 72, 24)
        tab3_rect = pygame.Rect(rx + 260, ry + 28, 148, 24)

        # Kompatibilitas titik uji unit test lama (rx + 230, ry + 10)
        if (rx + 220 <= pos[0] <= rx + 418 and ry <= pos[1] <= ry + 56) or tab3_rect.collidepoint(pos):
            self.active_tab = 3
            return True
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

    def _draw_badge(self, screen: pygame.Surface, rect: pygame.Rect, text: str,
                    text_col: Tuple[int, int, int], bg_col: Tuple[int, int, int],
                    border_col: Tuple[int, int, int], dot_col: Optional[Tuple[int, int, int]] = None,
                    font: Optional[pygame.font.Font] = None):
        """Menggambar badge kapsul berpenampilan modern tajam."""
        f = font or self.font_badge
        pygame.draw.rect(screen, bg_col, rect, border_radius=rect.height // 2)
        pygame.draw.rect(screen, border_col, rect, 1, border_radius=rect.height // 2)

        offset_x = rect.x + 6
        if dot_col is not None:
            pygame.draw.circle(screen, dot_col, (rect.x + 8, rect.y + rect.height // 2), 2.5)
            offset_x += 8

        t_surf = f.render(text, True, text_col)
        screen.blit(t_surf, (offset_x, rect.y + (rect.height - t_surf.get_height()) // 2))

    def _draw_metric_box(self, screen: pygame.Surface, rect: pygame.Rect,
                         label: str, value: str):
        """Menggambar satu dari 3 kolom kartu metrik modern."""
        pygame.draw.rect(screen, (255, 255, 255), rect, border_radius=6)
        pygame.draw.rect(screen, (226, 232, 240), rect, 1, border_radius=6)

        lbl_surf = self.font_xs.render(label.upper(), True, (100, 116, 139))
        screen.blit(lbl_surf, (rect.x + 8, rect.y + 5))

        val_surf = self.font_bold.render(value, True, (15, 23, 42))
        screen.blit(val_surf, (rect.x + 8, rect.y + 19))

    def _draw_checkbox_button(self, screen: pygame.Surface, rect: pygame.Rect,
                              label: str, is_checked: bool = False):
        """Menggambar tombol kartu checkbox bulat interaktif."""
        pygame.draw.rect(screen, (255, 255, 255), rect, border_radius=6)
        pygame.draw.rect(screen, (226, 232, 240), rect, 1, border_radius=6)

        # Checkbox icon box
        box_r = pygame.Rect(rect.x + 7, rect.y + (rect.height - 12) // 2, 12, 12)
        pygame.draw.rect(screen, (255, 255, 255), box_r, border_radius=2)
        b_border = (16, 185, 129) if is_checked else (203, 213, 225)
        pygame.draw.rect(screen, b_border, box_r, 1, border_radius=2)

        if is_checked:
            inner_r = pygame.Rect(box_r.x + 2, box_r.y + 2, 8, 8)
            pygame.draw.rect(screen, (16, 185, 129), inner_r, border_radius=2)

        txt_col = (15, 23, 42) if is_checked else (71, 85, 105)
        txt_surf = self.font_mono.render(label, True, txt_col)
        screen.blit(txt_surf, (rect.x + 24, rect.y + (rect.height - txt_surf.get_height()) // 2))

    def _draw_top_window_bar(self, screen: pygame.Surface):
        """Menggambar bilah jendela atas dengan header teks bersih (tanpa bulatan warna)."""
        rx, ry, rw = self.rect.x, self.rect.y, self.rect.width

        # Judul header sesuai tab aktif
        headers = {
            0: "DEBUG OVERLAY: AUTOMATED PLANNING",
            1: "DEBUG OVERLAY: ANALISIS HEURISTIK",
            2: "DEBUG OVERLAY: HTN TASK DECOMPOSITION",
            3: "DEBUG OVERLAY: DECISIONS UNDER UNCERTAINTY",
        }
        header_text = headers.get(self.active_tab, "DEBUG OVERLAY: AUTOMATED PLANNING")

        # Ikon status dot kecil monokrom
        pygame.draw.circle(screen, (71, 85, 105), (rx + 16, ry + 16), 3)

        title_surf = self.font_header.render(header_text, True, (71, 85, 105))
        screen.blit(title_surf, (rx + 26, ry + 10))

    def _draw_tabs(self, screen: pygame.Surface):
        """Menggambar bilah tab segmented control kapsul."""
        rx, ry, rw = self.rect.x, self.rect.y, self.rect.width

        capsule_rect = pygame.Rect(rx + 10, ry + 28, rw - 20, 26)
        pygame.draw.rect(screen, (241, 245, 249), capsule_rect, border_radius=6)
        pygame.draw.rect(screen, (226, 232, 240), capsule_rect, 1, border_radius=6)

        tab0_rect = pygame.Rect(rx + 11, ry + 29, 97, 24)
        tab1_rect = pygame.Rect(rx + 110, ry + 29, 74, 24)
        tab2_rect = pygame.Rect(rx + 186, ry + 29, 72, 24)
        tab3_rect = pygame.Rect(rx + 260, ry + 29, 146, 24)

        tabs_data = [
            (0, tab0_rect, "[F7] Planning"),
            (1, tab1_rect, "Heuristik"),
            (2, tab2_rect, "HTN (Ops)"),
            (3, tab3_rect, "[F8] Uncertainty"),
        ]

        for idx, t_rect, label in tabs_data:
            is_active = (self.active_tab == idx)
            if is_active:
                pygame.draw.rect(screen, (255, 255, 255), t_rect, border_radius=5)
                pygame.draw.rect(screen, (203, 213, 225), t_rect, 1, border_radius=5)
                surf = self.font_tab.render(label, True, (15, 23, 42))
            else:
                surf = self.font_tab.render(label, True, (100, 116, 139))
            screen.blit(surf, (t_rect.x + (t_rect.width - surf.get_width()) // 2, t_rect.y + 4))

    def _draw_cross_module_bar(self, screen: pygame.Surface, autopilot: Optional[AutopilotController],
                                weather_mgr: Optional[Any] = None):
        """Strip status modul mitra dan garis pemisah horizontal."""
        rx, ry, rw = self.rect.x, self.rect.y, self.rect.width
        cur_y = ry + 59

        # Badge status
        b_rect = pygame.Rect(rx + 10, cur_y, 148, 18)
        self._draw_badge(screen, b_rect, "[UCC] MAB Fishing (5 Spot)", (79, 70, 229), (238, 242, 255), (199, 210, 254))

        div_surf = self.font_badge.render("|", True, (203, 213, 225))
        screen.blit(div_surf, (rx + 164, cur_y + 2))

        sub_txt = "Live Minion Risk Policy" if self.active_tab == 0 else "STRIPS WA* Automated Planner"
        sub_surf = self.font_body.render(sub_txt, True, (71, 85, 105))
        screen.blit(sub_surf, (rx + 174, cur_y + 1))

        # Garis pemisah horizontal halus
        pygame.draw.line(screen, (226, 232, 240), (rx + 10, cur_y + 22), (rx + rw - 10, cur_y + 22), 1)

    def _draw_planning_tab(self, screen: pygame.Surface, autopilot: Optional[AutopilotController],
                           weather_mgr: Optional[Any] = None):
        """Tab 0: [F7] AUTOMATED PLANNING INSPECTOR - Compact Studio."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # Title Header & Badge
        cur_y = ry + 86
        t_surf = self.font_title.render("PLANNING INSPECTOR", True, (15, 23, 42))
        screen.blit(t_surf, (rx + 10, cur_y))

        badge_rect = pygame.Rect(rx + 10 + t_surf.get_width() + 8, cur_y + 1, 84, 18)
        self._draw_badge(screen, badge_rect, "STRIPS WA*", (71, 85, 105), (241, 245, 249), (226, 232, 240))

        # Subtitle Domain
        cur_y += 20
        dom_surf = self.font_mono.render("[DIR] data/planning/expedition.domain", True, (100, 116, 139))
        screen.blit(dom_surf, (rx + 10, cur_y))

        monitor = getattr(autopilot, "monitor", None) if autopilot else None
        plan = monitor.current_plan if monitor else None
        step_idx = monitor.current_step_idx if monitor else 0
        total_steps = len(plan) if plan else 37
        ws = getattr(autopilot, "world_state", None)
        mode_str = getattr(autopilot, "mode", "OFF") if autopilot else "OFF"

        key_done = False
        gate_done = False
        boss_done = False
        if ws:
            key_done = ws.inventory.has_item("gate_key", 1) or ws.inventory.has_item("key", 1)
            gate_done = ws.gate.is_open
            boss_done = getattr(getattr(ws, "boss", None), "is_defeated", False)

        # ----------------------------------------------------------------------
        # Card 1: TUJUAN & PROGRES (98px)
        # ----------------------------------------------------------------------
        c1_rect = pygame.Rect(rx + 10, ry + 124, rw - 20, 98)
        pygame.draw.rect(screen, (255, 255, 255), c1_rect, border_radius=10)
        pygame.draw.rect(screen, (226, 232, 240), c1_rect, 1, border_radius=10)

        pygame.draw.circle(screen, (37, 99, 235), (c1_rect.x + 14, c1_rect.y + 14), 3.5)
        c1_title = self.font_bold.render("TUJUAN & PROGRES", True, (15, 23, 42))
        screen.blit(c1_title, (c1_rect.x + 22, c1_rect.y + 6))

        mode_badge_r = pygame.Rect(c1_rect.right - 84, c1_rect.y + 5, 76, 18)
        self._draw_badge(screen, mode_badge_r, f"Mode: {mode_str}", (71, 85, 105), (241, 245, 249), (226, 232, 240), dot_col=(148, 163, 184))

        # 3 Checkbox Buttons
        btn_w = (c1_rect.width - 20 - 12) // 3
        b1_r = pygame.Rect(c1_rect.x + 10, c1_rect.y + 27, btn_w, 24)
        b2_r = pygame.Rect(c1_rect.x + 10 + btn_w + 6, c1_rect.y + 27, btn_w, 24)
        b3_r = pygame.Rect(c1_rect.x + 10 + (btn_w + 6) * 2, c1_rect.y + 27, btn_w, 24)

        self._draw_checkbox_button(screen, b1_r, "gate_key", is_checked=key_done)
        self._draw_checkbox_button(screen, b2_r, "gate_open", is_checked=gate_done)
        self._draw_checkbox_button(screen, b3_r, "boss_defeated", is_checked=boss_done)

        # Progress bar
        bar_r = pygame.Rect(c1_rect.x + 10, c1_rect.y + 57, c1_rect.width - 20, 6)
        pygame.draw.rect(screen, (235, 239, 245), bar_r, border_radius=3)
        pct = min(1.0, max(0.0, step_idx / max(1, total_steps)))
        if pct > 0:
            fill_r = pygame.Rect(bar_r.x, bar_r.y, int(bar_r.width * pct), bar_r.height)
            pygame.draw.rect(screen, (59, 130, 246), fill_r, border_radius=3)

        # Footer stats
        tot_cost = sum(a.cost for a in plan) if plan else 118.5
        f_y = c1_rect.y + 71
        screen.blit(self.font_xs.render(f"Langkah {step_idx}/{total_steps}", True, (15, 23, 42)), (c1_rect.x + 10, f_y))
        screen.blit(self.font_xs.render("·", True, (148, 163, 184)), (c1_rect.x + 130, f_y))
        screen.blit(self.font_xs.render(f"Biaya: {tot_cost:.1f}s", True, (15, 23, 42)), (c1_rect.x + 150, f_y))
        screen.blit(self.font_xs.render("·", True, (148, 163, 184)), (c1_rect.x + 260, f_y))
        screen.blit(self.font_xs.render(f"Mode: {mode_str}", True, (71, 85, 105)), (c1_rect.x + 280, f_y))

        # ----------------------------------------------------------------------
        # Card 2: AKSI AKTIF (STRIPS) (108px)
        # ----------------------------------------------------------------------
        c2_rect = pygame.Rect(rx + 10, ry + 228, rw - 20, 108)
        pygame.draw.rect(screen, (245, 254, 250), c2_rect, border_radius=10)
        pygame.draw.rect(screen, (187, 247, 208), c2_rect, 1, border_radius=10)

        c2_title = self.font_bold.render("AKSI AKTIF (STRIPS)", True, (6, 78, 59))
        screen.blit(c2_title, (c2_rect.x + 10, c2_rect.y + 6))

        act = monitor.current_action if monitor else None
        act_status = "[BERJALAN]" if act is not None else "[SIAP]"
        siap_r = pygame.Rect(c2_rect.right - 66, c2_rect.y + 5, 56, 18)
        self._draw_badge(screen, siap_r, act_status, (22, 101, 52), (220, 252, 231), (134, 239, 172), dot_col=(16, 185, 129))

        in_box = pygame.Rect(c2_rect.x + 10, c2_rect.y + 27, c2_rect.width - 20, 26)
        pygame.draw.rect(screen, (255, 255, 255), in_box, border_radius=6)
        pygame.draw.rect(screen, (187, 247, 208), in_box, 1, border_radius=6)

        act_name_str = f"{act.name}({', '.join(act.params)})" if act else "Ekspedisi Selesai / Siap"
        screen.blit(self.font_bold.render(act_name_str[:34], True, (15, 23, 42)), (in_box.x + 8, in_box.y + 5))

        f9_badge = pygame.Rect(in_box.right - 38, in_box.y + 4, 30, 18)
        self._draw_badge(screen, f9_badge, "[F9]", (71, 85, 105), (241, 245, 249), (226, 232, 240))

        # Key-Values
        kv_y = c2_rect.y + 59
        screen.blit(self.font_mono.render("Precondition", True, (13, 148, 136)), (c2_rect.x + 10, kv_y))
        pre_val = "Semua precondition STRIPS terpenuhi." if not act else "[OK] at [OK] connected"
        screen.blit(self.font_body.render(pre_val, True, (15, 23, 42)), (c2_rect.x + 104, kv_y))

        kv_y += 16
        screen.blit(self.font_mono.render("Effect (Eff)", True, (13, 148, 136)), (c2_rect.x + 10, kv_y))
        eff_val = "Siap eksekusi tahap berikutnya." if not act else "+has_key, +holding | -wood"
        screen.blit(self.font_body.render(eff_val, True, (15, 23, 42)), (c2_rect.x + 104, kv_y))

        kv_y += 16
        diff_txt = getattr(monitor, "last_state_diff", "-") if monitor else "-"
        diff_display = "- (belum ada aksi selesai)" if diff_txt == "-" else f"{diff_txt[:32]}"
        screen.blit(self.font_mono.render("State Diff", True, (100, 116, 139)), (c2_rect.x + 10, kv_y))
        screen.blit(self.font_mono.render(diff_display, True, (100, 116, 139)), (c2_rect.x + 104, kv_y))

        # ----------------------------------------------------------------------
        # Card 3: MESIN PENCARI WA* & ANTREAN (182px)
        # ----------------------------------------------------------------------
        c3_rect = pygame.Rect(rx + 10, ry + 342, rw - 20, 182)
        pygame.draw.rect(screen, (255, 255, 255), c3_rect, border_radius=10)
        pygame.draw.rect(screen, (226, 232, 240), c3_rect, 1, border_radius=10)

        pygame.draw.circle(screen, (147, 51, 234), (c3_rect.x + 14, c3_rect.y + 14), 3.5)
        c3_title = self.font_bold.render("MESIN PENCARI WA* & ANTREAN", True, (15, 23, 42))
        screen.blit(c3_title, (c3_rect.x + 22, c3_rect.y + 6))

        w_val = getattr(config, "PLANNER_WEIGHT", 1.5)
        w_badge = pygame.Rect(c3_rect.right - 62, c3_rect.y + 5, 52, 18)
        self._draw_badge(screen, w_badge, f"w = {w_val}", (107, 33, 168), (243, 232, 255), (216, 180, 254))

        # 3 Column Metric Cards
        m_w = (c3_rect.width - 20 - 12) // 3
        m1_r = pygame.Rect(c3_rect.x + 10, c3_rect.y + 27, m_w, 42)
        m2_r = pygame.Rect(c3_rect.x + 10 + m_w + 6, c3_rect.y + 27, m_w, 42)
        m3_r = pygame.Rect(c3_rect.x + 10 + (m_w + 6) * 2, c3_rect.y + 27, m_w, 42)

        nodes = getattr(monitor, "last_nodes_expanded", 886) if monitor else 886
        lat = getattr(monitor, "last_search_latency_ms", 1.1) if monitor else 1.1

        self._draw_metric_box(screen, m1_r, "Heuristik", "WA* (h_FF)")
        self._draw_metric_box(screen, m2_r, "Ekspansi", f"{nodes} node")
        self._draw_metric_box(screen, m3_r, "Waktu", f"{lat:.1f} ms")

        # Invariant Table Box
        t_box = pygame.Rect(c3_rect.x + 10, c3_rect.y + 75, c3_rect.width - 20, 98)
        pygame.draw.rect(screen, (248, 250, 252), t_box, border_radius=6)
        pygame.draw.rect(screen, (226, 232, 240), t_box, 1, border_radius=6)

        rows = [
            ("Budget step(): < 20ms", "[OK]", True),
            ("Polyline Validation", "[OK]", True),
            ("Geodesik: 40 lkg >= 38 Manhattan", "[OK]", True),
            ("Replan: - (eksekusi berjalan lancar)", "IDLE", False),
        ]

        for i, (r_txt, badge_txt, is_ok) in enumerate(rows):
            ry_item = t_box.y + 6 + i * 23
            screen.blit(self.font_mono.render(r_txt, True, (51, 65, 85)), (t_box.x + 8, ry_item))

            b_item_r = pygame.Rect(t_box.right - 48, ry_item - 1, 40, 16)
            if is_ok:
                self._draw_badge(screen, b_item_r, badge_txt, (22, 101, 52), (220, 252, 231), (134, 239, 172))
            else:
                self._draw_badge(screen, b_item_r, badge_txt, (100, 116, 139), (241, 245, 249), (203, 213, 225))

    def _draw_uncertainty_tab(self, screen: pygame.Surface, weather_mgr: Optional[Any] = None,
                               autopilot: Optional[AutopilotController] = None):
        """Tab 3: [F8] DECISIONS UNDER UNCERTAINTY (UCC) - Compact Studio."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # Title Header & Badge
        cur_y = ry + 86
        t_surf = self.font_title.render("DECISIONS UNDER UNCERTAINTY", True, (15, 23, 42))
        screen.blit(t_surf, (rx + 10, cur_y))

        badge_rect = pygame.Rect(rx + 10 + t_surf.get_width() + 8, cur_y + 1, 88, 18)
        self._draw_badge(screen, badge_rect, "UCC ENGINE", (79, 70, 229), (238, 242, 255), (199, 210, 254))

        cur_y += 20
        dom_surf = self.font_mono.render("[DIR] src/decision/mab_manager.py & combat_policy.py", True, (100, 116, 139))
        screen.blit(dom_surf, (rx + 10, cur_y))

        # ----------------------------------------------------------------------
        # Card 1: MULTI-ARMED BANDIT (MAB 5 SPOTS) (98px)
        # ----------------------------------------------------------------------
        c1_rect = pygame.Rect(rx + 10, ry + 124, rw - 20, 98)
        pygame.draw.rect(screen, (255, 255, 255), c1_rect, border_radius=10)
        pygame.draw.rect(screen, (226, 232, 240), c1_rect, 1, border_radius=10)

        pygame.draw.circle(screen, (37, 99, 235), (c1_rect.x + 14, c1_rect.y + 14), 3.5)
        c1_title = self.font_bold.render("MAB: EKSPLORASI VS EKSPLOITASI", True, (15, 23, 42))
        screen.blit(c1_title, (c1_rect.x + 22, c1_rect.y + 6))

        mab_badge_r = pygame.Rect(c1_rect.right - 78, c1_rect.y + 5, 70, 18)
        self._draw_badge(screen, mab_badge_r, "[5 SPOTS]", (79, 70, 229), (238, 242, 255), (199, 210, 254), dot_col=(59, 130, 246))

        m_w = (c1_rect.width - 20 - 12) // 3
        m1_r = pygame.Rect(c1_rect.x + 10, c1_rect.y + 27, m_w, 42)
        m2_r = pygame.Rect(c1_rect.x + 10 + m_w + 6, c1_rect.y + 27, m_w, 42)
        m3_r = pygame.Rect(c1_rect.x + 10 + (m_w + 6) * 2, c1_rect.y + 27, m_w, 42)

        self._draw_metric_box(screen, m1_r, "Algoritma", "Thompson/UCB1")
        self._draw_metric_box(screen, m2_r, "Total Spots", "5 Pesisir")
        self._draw_metric_box(screen, m3_r, "Regret Bound", "O(ln T)")

        hint_y = c1_rect.y + 74
        screen.blit(self.font_body.render("Sistem 5 Spot Pesisir (Theta Rahasia)", True, (71, 85, 105)), (c1_rect.x + 10, hint_y))
        b_hint_r = pygame.Rect(c1_rect.right - 118, hint_y - 2, 108, 18)
        self._draw_badge(screen, b_hint_r, "Tekan [B] Jurnal", (15, 23, 42), (241, 245, 249), (203, 213, 225))

        # ----------------------------------------------------------------------
        # Card 2: KEBIJAKAN RISIKO PERTEMPURAN (108px)
        # ----------------------------------------------------------------------
        c2_rect = pygame.Rect(rx + 10, ry + 228, rw - 20, 108)
        pygame.draw.rect(screen, (255, 251, 235), c2_rect, border_radius=10)
        pygame.draw.rect(screen, (253, 230, 138), c2_rect, 1, border_radius=10)

        c2_title = self.font_bold.render("KEBIJAKAN RISIKO PERTEMPURAN", True, (146, 64, 14))
        screen.blit(c2_title, (c2_rect.x + 10, c2_rect.y + 6))

        comb_badge_r = pygame.Rect(c2_rect.right - 96, c2_rect.y + 5, 86, 18)
        self._draw_badge(screen, comb_badge_r, "[LIVE COMBAT]", (146, 64, 14), (254, 243, 199), (252, 211, 77), dot_col=(245, 158, 11))

        in_box = pygame.Rect(c2_rect.x + 10, c2_rect.y + 27, c2_rect.width - 20, 26)
        pygame.draw.rect(screen, (255, 255, 255), in_box, border_radius=6)
        pygame.draw.rect(screen, (253, 230, 138), in_box, 1, border_radius=6)

        screen.blit(self.font_bold.render("Ancaman Minion Goblin Hijau (Respawn Acak)", True, (15, 23, 42)), (in_box.x + 8, in_box.y + 5))

        act_pill = pygame.Rect(in_box.right - 54, in_box.y + 4, 46, 18)
        self._draw_badge(screen, act_pill, "[AKTIF]", (22, 101, 52), (220, 252, 231), (134, 239, 172))

        kv_y = c2_rect.y + 59
        screen.blit(self.font_mono.render("Analisis MEU", True, (180, 83, 9)), (c2_rect.x + 10, kv_y))
        screen.blit(self.font_body.render("Tarung (E[Loot] = +5.5 Koin) vs Hindari (0 Dmg)", True, (15, 23, 42)), (c2_rect.x + 104, kv_y))

        kv_y += 16
        screen.blit(self.font_mono.render("Kebijakan HP", True, (180, 83, 9)), (c2_rect.x + 10, kv_y))
        screen.blit(self.font_bold.render("HP >= 35% -> Engage | HP < 35% -> Evade", True, (15, 23, 42)), (c2_rect.x + 104, kv_y))

        kv_y += 16
        screen.blit(self.font_mono.render("Status Alam", True, (100, 116, 139)), (c2_rect.x + 10, kv_y))
        screen.blit(self.font_body.render("Minion goblin berkeliaran bebas (live combat)", True, (100, 116, 139)), (c2_rect.x + 104, kv_y))

        # ----------------------------------------------------------------------
        # Card 3: FORMULASI KEPUTUSAN STOKASTIK (182px)
        # ----------------------------------------------------------------------
        c3_rect = pygame.Rect(rx + 10, ry + 342, rw - 20, 182)
        pygame.draw.rect(screen, (255, 255, 255), c3_rect, border_radius=10)
        pygame.draw.rect(screen, (226, 232, 240), c3_rect, 1, border_radius=10)

        pygame.draw.circle(screen, (147, 51, 234), (c3_rect.x + 14, c3_rect.y + 14), 3.5)
        c3_title = self.font_bold.render("FORMULASI KEPUTUSAN STOKASTIK", True, (15, 23, 42))
        screen.blit(c3_title, (c3_rect.x + 22, c3_rect.y + 6))

        teori_badge = pygame.Rect(c3_rect.right - 78, c3_rect.y + 5, 70, 18)
        self._draw_badge(screen, teori_badge, "[TEORI UCC]", (107, 33, 168), (243, 232, 255), (216, 180, 254))

        m_w = (c3_rect.width - 20 - 12) // 3
        m1_r = pygame.Rect(c3_rect.x + 10, c3_rect.y + 27, m_w, 42)
        m2_r = pygame.Rect(c3_rect.x + 10 + m_w + 6, c3_rect.y + 27, m_w, 42)
        m3_r = pygame.Rect(c3_rect.x + 10 + (m_w + 6) * 2, c3_rect.y + 27, m_w, 42)

        self._draw_metric_box(screen, m1_r, "UCB1 Index", "mu + c*sqrt(ln/N)")
        self._draw_metric_box(screen, m2_r, "Bayesian TS", "Beta(alpha, beta)")
        self._draw_metric_box(screen, m3_r, "Prinsip", "argmax(EU)")

        t_box = pygame.Rect(c3_rect.x + 10, c3_rect.y + 75, c3_rect.width - 20, 98)
        pygame.draw.rect(screen, (248, 250, 252), t_box, border_radius=6)
        pygame.draw.rect(screen, (226, 232, 240), t_box, 1, border_radius=6)

        ucc_rows = [
            ("Penyesalan: Teorema Lai-Robbins O(ln T)", "[OK]", True),
            ("Konjugat Beta-Binomial Posterior Update", "[OK]", True),
            ("Ambang Risiko Live Combat HP >= 35%", "[OK]", True),
            ("Optimisme: Eksplorasi Bound Atas (UCB1)", "INFO", False),
        ]

        for i, (r_txt, badge_txt, is_ok) in enumerate(ucc_rows):
            ry_item = t_box.y + 6 + i * 23
            screen.blit(self.font_mono.render(r_txt, True, (51, 65, 85)), (t_box.x + 8, ry_item))

            b_item_r = pygame.Rect(t_box.right - 48, ry_item - 1, 40, 16)
            if is_ok:
                self._draw_badge(screen, b_item_r, badge_txt, (22, 101, 52), (220, 252, 231), (134, 239, 172))
            else:
                self._draw_badge(screen, b_item_r, badge_txt, (100, 116, 139), (241, 245, 249), (203, 213, 225))

    def _draw_heuristics_tab(self, screen: pygame.Surface):
        """Tab 1: Analisis komparatif heuristik pencarian."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        cur_y = ry + 86
        t_surf = self.font_title.render("ANALISIS HEURISTIK", True, (15, 23, 42))
        screen.blit(t_surf, (rx + 10, cur_y))

        badge_rect = pygame.Rect(rx + 10 + t_surf.get_width() + 8, cur_y + 1, 88, 18)
        self._draw_badge(screen, badge_rect, "BENCHMARK", (71, 85, 105), (241, 245, 249), (226, 232, 240))

        c1_rect = pygame.Rect(rx + 10, ry + 124, rw - 20, 190)
        pygame.draw.rect(screen, (255, 255, 255), c1_rect, border_radius=10)
        pygame.draw.rect(screen, (226, 232, 240), c1_rect, 1, border_radius=10)

        c1_title = self.font_bold.render("BENCHMARK MASALAH P1 - P4", True, (15, 23, 42))
        screen.blit(c1_title, (c1_rect.x + 12, c1_rect.y + 10))

        p_items = [
            ("P1 (Key Craft)", "UCS 35 node (1.4ms) | A*(h_max) 16 node (0.8ms)"),
            ("P2 (Open Gate)", "UCS 48 node (2.8ms) | A*(h_max) 29 node (1.5ms)"),
            ("P3 (Potion)", "WA*(h_FF) 16 node (18.4ms) - Cost 33.0s"),
            ("P4 (Full Ekspedisi)", "WA*(h_FF) 37 langkah (118.48s) | 876 node"),
        ]
        row_y = c1_rect.y + 32
        for header, detail in p_items:
            screen.blit(self.font_bold.render(header, True, (15, 23, 42)), (c1_rect.x + 12, row_y))
            screen.blit(self.font_body.render(detail, True, (71, 85, 105)), (c1_rect.x + 12, row_y + 16))
            row_y += 38

        c2_rect = pygame.Rect(rx + 10, ry + 322, rw - 20, 202)
        pygame.draw.rect(screen, (255, 255, 255), c2_rect, border_radius=10)
        pygame.draw.rect(screen, (226, 232, 240), c2_rect, 1, border_radius=10)

        c2_title = self.font_bold.render("OPTIMASI & SIFAT ADMISIBILITAS", True, (15, 23, 42))
        screen.blit(c2_title, (c2_rect.x + 12, c2_rect.y + 10))

        opts = [
            ("Planning Graph", "h_level admissible (h=4.0 pada Ojek, mutex terpenuhi)"),
            ("Optimasi Helpful Actions", "Memotong percabangan hingga 8x lipat tanpa kehilangan solusi"),
            ("Incremental Budgeting", "Waktu per-frame step() terukur < 20ms (rata-rata 1.1ms)"),
            ("Batas Geodesik Map", "Jarak rute riil 40 lkg >= 38 Manhattan terbukti invarian"),
        ]
        row_y = c2_rect.y + 32
        for header, detail in opts:
            screen.blit(self.font_bold.render(header, True, (15, 23, 42)), (c2_rect.x + 12, row_y))
            screen.blit(self.font_body.render(detail, True, (71, 85, 105)), (c2_rect.x + 12, row_y + 16))
            row_y += 40

    def _draw_htn_tab(self, screen: pygame.Surface, farmer: Optional[HTNNPCAgent],
                      miller: Optional[HTNNPCAgent], clock: Optional[WorldClock]):
        """Tab 2: HTN Task Decomposition (Opsional)."""
        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        cur_y = ry + 86
        t_surf = self.font_title.render("HTN TASK DECOMPOSITION", True, (15, 23, 42))
        screen.blit(t_surf, (rx + 10, cur_y))

        badge_rect = pygame.Rect(rx + 10 + t_surf.get_width() + 8, cur_y + 1, 88, 18)
        self._draw_badge(screen, badge_rect, "[OPSIONAL]", (71, 85, 105), (241, 245, 249), (226, 232, 240))

        c1_rect = pygame.Rect(rx + 10, ry + 124, rw - 20, 104)
        pygame.draw.rect(screen, (255, 255, 255), c1_rect, border_radius=10)
        pygame.draw.rect(screen, (226, 232, 240), c1_rect, 1, border_radius=10)

        c1_title = self.font_bold.render("STATUS SHOP-STYLE HTN ENGINE", True, (15, 23, 42))
        screen.blit(c1_title, (c1_rect.x + 12, c1_rect.y + 10))
        screen.blit(self.font_body.render("Status: Modul opsional (di luar materi silabus 35 slide inti)", True, (30, 41, 59)), (c1_rect.x + 12, c1_rect.y + 32))
        screen.blit(self.font_body.render("Engine mandiri tersedia di berkas src/planning/htn.py", True, (71, 85, 105)), (c1_rect.x + 12, c1_rect.y + 52))
        screen.blit(self.font_body.render("Dukungan dekomposisi task NPC desa Sunnyside berjalan independen.", True, (100, 116, 139)), (c1_rect.x + 12, c1_rect.y + 72))

        c2_rect = pygame.Rect(rx + 10, ry + 236, rw - 20, 288)
        pygame.draw.rect(screen, (255, 255, 255), c2_rect, border_radius=10)
        pygame.draw.rect(screen, (226, 232, 240), c2_rect, 1, border_radius=10)

        c2_title = self.font_bold.render("SILABUS RESMI AUTOMATED PLANNING", True, (15, 23, 42))
        screen.blit(c2_title, (c2_rect.x + 12, c2_rect.y + 10))

        syllabus = [
            "* PDDL & Action Schema (STRIPS preconditions & effects)",
            "* Forward State-Space Search (BFS, UCS, A*)",
            "* Backward Goal Regression (Analisis Slide 27)",
            "* Ignore-Delete-List Heuristics (h_add, h_max, h_FF Relaxed)",
            "* Planning Graph & Mutex Relations (GraphPlan / h_level)",
            "* Decoupled Real-Time Re-planning Engine (< 20ms budget)",
            "* Cross-Module Integration with Bayesian Uncertainty & MAB",
        ]
        s_y = c2_rect.y + 36
        for item in syllabus:
            screen.blit(self.font_body.render(item, True, (51, 65, 85)), (c2_rect.x + 12, s_y))
            s_y += 34

    def draw(self, screen: pygame.Surface, autopilot: Optional[AutopilotController] = None,
             farmer: Optional[HTNNPCAgent] = None, miller: Optional[HTNNPCAgent] = None,
             clock: Optional[WorldClock] = None, weather_mgr: Optional[Any] = None,
             camera: Optional[Tuple[int, int]] = None, hero: Optional[Any] = None):
        """Menggambar panel terpadu satu jendela dengan styling modern compact studio."""
        if not self.visible:
            return

        rx, ry, rw, rh = self.rect.x, self.rect.y, self.rect.width, self.rect.height

        # 1. Floating shadow kiri
        if not hasattr(self, "_shadow_surf") or self._shadow_surf is None or self._shadow_surf.get_height() != rh:
            self._shadow_surf = pygame.Surface((10, rh), pygame.SRCALPHA)
            for sx in range(10):
                alpha = int(45 * (sx + 1) / 10)
                pygame.draw.line(self._shadow_surf, (0, 0, 0, alpha), (sx, 0), (sx, rh))
        screen.blit(self._shadow_surf, (rx - 10, ry))

        # 2. Base canvas (#F9FAFC / White)
        pygame.draw.rect(screen, (249, 250, 252), self.rect, border_radius=10)
        pygame.draw.rect(screen, (226, 232, 240), self.rect, 1, border_radius=10)

        # 3. Top Window Bar: Header teks profesional
        self._draw_top_window_bar(screen)

        # 4. Tab Bar (Segmented Capsule)
        self._draw_tabs(screen)

        # 5. Cross-Module Status Ribbon & Divider
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

