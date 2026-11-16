"""
bandit_ui.py - Antarmuka Visual HUD & Analisis Multi-Armed Bandit
Sunnyside Isle - Top-down RPG Pygame Engine

Fitur Panel Interaktif:
  - Tombol Shortcut: [B] untuk buka/tutup "Jurnal Nelayan & MAB Analyzer".
  - Tri-Mode Display:
      1. Mode PEMAIN  : Hanya data empiris yang diamati (n, s, mu_hat, bar posterior).
      2. Mode ANALYST : Mode god-view/dosen (true theta, kurva regret live 5 algoritma vs pemain, Lai-Robbins bound).
      3. Mode REVEAL  : Ringkasan hasil musim saat horizon tercapai.
  - 4 Kuadran Analisis:
      * Kuadran A: Tabel 5 Spot Pancingan (n, s, mu_hat, 95% Credible Interval, penanda advisor).
      * Kuadran B: Grafik Garis Cumulative Regret (Pemain/AI vs 5 Ghost Agents vs Lai-Robbins).
      * Kuadran C: Metrik Ekonomi Nelayan (Rare Catch, Net Gold, Sisa Umpan/Horizon).
      * Kuadran D: Grafik % Pemilihan Arm Optimal (Moving Window 20 lemparan).
"""

import math
import pygame
from typing import Dict, List, Tuple, Any, Optional
from decision.bandit import BanditDirector, BanditAgent, BANDIT_PRESETS


class BanditHUD:
    """
    HUD Overlay untuk Jurnal Nelayan dan Analisis Algoritma Multi-Armed Bandit.
    """
    MODE_PLAYER = "PLAYER"
    MODE_ANALYST = "ANALYST"
    MODE_REVEAL = "REVEAL"

    def __init__(self, director: BanditDirector, screen_w: int = 1024, screen_h: int = 576):
        self.director = director
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.visible = False
        self.mode = self.MODE_PLAYER  # Default: Player view

        # Dimensi panel utama (tengah layar)
        self.panel_w = 900
        self.panel_h = 500
        self.panel_x = (screen_w - self.panel_w) // 2
        self.panel_y = (screen_h - self.panel_h) // 2
        self.rect = pygame.Rect(self.panel_x, self.panel_y, self.panel_w, self.panel_h)

        # Inisialisasi font (fallback aman Pygame)
        pygame.font.init()
        self.font_title = pygame.font.SysFont("Arial", 16, bold=True)
        self.font_bold = pygame.font.SysFont("Arial", 13, bold=True)
        self.font_text = pygame.font.SysFont("Arial", 12)
        self.font_small = pygame.font.SysFont("Arial", 11)

    def toggle(self):
        """Buka / tutup HUD overlay."""
        self.visible = not self.visible

    def cycle_mode(self):
        """Berganti mode: PEMAIN -> ANALYST -> REVEAL -> PEMAIN."""
        if self.mode == self.MODE_PLAYER:
            self.mode = self.MODE_ANALYST
        elif self.mode == self.MODE_ANALYST:
            self.mode = self.MODE_REVEAL
        else:
            self.mode = self.MODE_PLAYER

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Menangani input keyboard/mouse saat HUD aktif. Return True jika event dikonsumsi."""
        if not self.visible:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_b:
                self.visible = False
                return True
            elif event.key == pygame.K_m:
                self.cycle_mode()
                return True
            elif event.key == pygame.K_ESCAPE:
                self.visible = False
                return True
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                preset_map = {pygame.K_1: "EASY", pygame.K_2: "REALISTIC", pygame.K_3: "HARD"}
                self.director.start_session(preset_map[event.key], seed=self.director.seed + 1,
                                           primary_kind=self.director.primary_kind,
                                           primary_agent_name=self.director.primary_agent_name)
                return True

        return False

    def render(self, surface: pygame.Surface):
        """Menggambar seluruh panel HUD ke surface display game."""
        if not self.visible:
            return

        # 1. Overlay latar belakang semi-transparan
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((10, 14, 22, 210))
        surface.blit(overlay, (0, 0))

        # 2. Bingkai Panel Utama
        pygame.draw.rect(surface, (24, 30, 42), self.rect, border_radius=8)
        pygame.draw.rect(surface, (70, 90, 120), self.rect, 2, border_radius=8)

        # 3. Header Panel
        self._render_header(surface)

        # 4. Kuadran Konten (Grid 2x2)
        pad = 12
        top_y = self.panel_y + 44
        content_h = self.panel_h - 54 - pad
        half_w = (self.panel_w - pad * 3) // 2
        half_h = (content_h - pad) // 2

        rect_a = pygame.Rect(self.panel_x + pad, top_y, half_w, half_h)
        rect_b = pygame.Rect(self.panel_x + pad * 2 + half_w, top_y, half_w, half_h)
        rect_c = pygame.Rect(self.panel_x + pad, top_y + half_h + pad, half_w, half_h)
        rect_d = pygame.Rect(self.panel_x + pad * 2 + half_w, top_y + half_h + pad, half_w, half_h)

        # Render 4 Kuadran
        self._render_panel_a(surface, rect_a)
        self._render_panel_b(surface, rect_b)
        self._render_panel_c(surface, rect_c)
        self._render_panel_d(surface, rect_d)

    def _render_header(self, surface: pygame.Surface):
        """Header atas panel dengan judul, mode aktif, dan instruksi kontrol."""
        title_text = "JURNAL NELAYAN: ANALISIS MULTI-ARMED BANDIT (EXPLORE VS EXPLOIT)"
        title_surf = self.font_title.render(title_text, True, (240, 210, 80))
        surface.blit(title_surf, (self.panel_x + 14, self.panel_y + 12))

        # Badge Mode
        mode_colors = {
            self.MODE_PLAYER: (60, 160, 240),
            self.MODE_ANALYST: (240, 80, 80),
            self.MODE_REVEAL: (60, 210, 120)
        }
        mode_text = f"MODE: [{self.mode}] (Tekan [M] Ubah Mode)"
        mode_surf = self.font_bold.render(mode_text, True, mode_colors.get(self.mode, (200, 200, 200)))
        surface.blit(mode_surf, (self.panel_x + self.panel_w - mode_surf.get_width() - 14, self.panel_y + 13))

        # Garis pemisah
        pygame.draw.line(surface, (60, 75, 100),
                         (self.panel_x + 10, self.panel_y + 38),
                         (self.panel_x + self.panel_w - 10, self.panel_y + 38), 1)

    def _render_panel_a(self, surface: pygame.Surface, rect: pygame.Rect):
        """PANEL A: Tabel 5 Spot Pancingan (n, s, mu_hat, Credible Interval)."""
        pygame.draw.rect(surface, (18, 22, 30), rect, border_radius=6)
        pygame.draw.rect(surface, (50, 65, 85), rect, 1, border_radius=6)

        hdr = self.font_bold.render("PANEL A: TABEL 5 SPOT (OBSERVASI EMPIRIS)", True, (140, 190, 255))
        surface.blit(hdr, (rect.x + 8, rect.y + 6))

        # Header Kolom
        is_analyst = (self.mode in (self.MODE_ANALYST, self.MODE_REVEAL))
        cols = "Spot   | Tarikan(n) | Ikan Emas(s) |  μ̂ (Rate) "
        if is_analyst:
            cols += " | True θ "
        else:
            cols += " | 95% Posterior CI "
        cols_surf = self.font_small.render(cols, True, (160, 175, 190))
        surface.blit(cols_surf, (rect.x + 8, rect.y + 26))

        pygame.draw.line(surface, (45, 55, 75), (rect.x + 6, rect.y + 40), (rect.right - 6, rect.y + 40), 1)

        # Baris Spot (0 s/d 4)
        spot_names = ["Spot A", "Spot B", "Spot C", "Spot D", "Spot E"]
        advisor_pick = self.director.choose_spot()

        thompson_agent: Any = self.director.ghosts.get("Thompson", {}).get("agent")

        for i in range(self.director.K):
            row_y = rect.y + 46 + i * 28
            n_val = self.director.player_pulls[i]
            s_val = self.director.player_successes[i]
            mu_hat = s_val / n_val if n_val > 0 else 0.0

            # Indikator rekomendasi AI advisor
            marker = "► " if (i == advisor_pick) else "  "
            spot_lbl = f"{marker}{spot_names[i]}"

            # Warna baris
            txt_color = (255, 235, 120) if (i == advisor_pick) else (210, 220, 230)

            # Hitung credible interval jika agen Thompson tersedia
            ci_str = "[0.05, 0.95]"
            if thompson_agent and hasattr(thompson_agent, "credible_interval"):
                ci = thompson_agent.credible_interval(i)
                ci_str = f"[{ci[0]:.2f}, {ci[1]:.2f}]"

            if is_analyst:
                true_th = self.director.env.thetas[i]
                is_best = (i == self.director.env.best_arm)
                best_tag = " *" if is_best else ""
                row_str = f"{spot_lbl:<7} | {n_val:^10} | {s_val:^12} |  {mu_hat:^8.2f} |  {true_th:.2f}{best_tag}"
            else:
                row_str = f"{spot_lbl:<7} | {n_val:^10} | {s_val:^12} |  {mu_hat:^8.2f} |  {ci_str}"

            surface.blit(self.font_small.render(row_str, True, txt_color), (rect.x + 8, row_y))

            # Visual bar mu_hat
            bar_w = 60
            bar_rect = pygame.Rect(rect.right - bar_w - 10, row_y + 2, bar_w, 10)
            pygame.draw.rect(surface, (35, 45, 60), bar_rect)
            fill_w = int(bar_w * min(1.0, mu_hat))
            if fill_w > 0:
                fill_color = (60, 210, 120) if mu_hat >= 0.4 else (230, 140, 50)
                pygame.draw.rect(surface, fill_color, (bar_rect.x, bar_rect.y, fill_w, bar_rect.h))
            pygame.draw.rect(surface, (60, 75, 95), bar_rect, 1)

    def _render_panel_b(self, surface: pygame.Surface, rect: pygame.Rect):
        """PANEL B: Grafik Garis Cumulative Regret (Pemain & Ghost Agents)."""
        pygame.draw.rect(surface, (18, 22, 30), rect, border_radius=6)
        pygame.draw.rect(surface, (50, 65, 85), rect, 1, border_radius=6)

        hdr = self.font_bold.render("PANEL B: CUMULATIVE REGRET R(t) [GOD-VIEW]", True, (140, 190, 255))
        surface.blit(hdr, (rect.x + 8, rect.y + 6))

        # Hanya mode Analyst & Reveal yang menampilkan kurva regret lengkap
        if self.mode == self.MODE_PLAYER:
            lock_msg = "Terkunci dalam Mode Pemain (Informasi 'Mata Tuhan')."
            hint_msg = "Tekan tombol [M] untuk mengaktifkan Mode ANALYST."
            surface.blit(self.font_text.render(lock_msg, True, (180, 160, 140)), (rect.x + 20, rect.y + 60))
            surface.blit(self.font_small.render(hint_msg, True, (120, 140, 170)), (rect.x + 20, rect.y + 85))
            return

        # Area grafik di dalam kotak panel B
        chart_rect = pygame.Rect(rect.x + 36, rect.y + 28, rect.w - 48, rect.h - 52)
        pygame.draw.rect(surface, (14, 18, 24), chart_rect)
        pygame.draw.rect(surface, (40, 50, 65), chart_rect, 1)

        t_cur = max(1, self.director.t)
        t_max = max(10, self.director.T)

        # Cari nilai regret maksimum untuk skala vertikal
        max_regret = 1.0
        for g in self.director.ghosts.values():
            tracker = g["tracker"]
            if tracker.cum_regret:
                max_regret = max(max_regret, tracker.total_regret)
        if self.director.primary_tracker.cum_regret:
            max_regret = max(max_regret, self.director.primary_tracker.total_regret)
        max_regret = max(5.0, max_regret * 1.15)

        # Gambar garis kisi horizontal
        for k in range(1, 4):
            y_val = chart_rect.bottom - (k / 4.0) * chart_rect.h
            pygame.draw.line(surface, (25, 32, 44), (chart_rect.x, y_val), (chart_rect.right, y_val), 1)
            lbl = f"{max_regret * (k / 4.0):.1f}"
            surface.blit(self.font_small.render(lbl, True, (90, 105, 120)), (rect.x + 4, y_val - 6))

        # Gambar kurva 5 ghost agent
        for name, g in self.director.ghosts.items():
            ys = g["tracker"].cum_regret
            if len(ys) < 2:
                continue
            color = g["color"]
            pts = [
                (chart_rect.x + (idx / t_max) * chart_rect.w,
                 chart_rect.bottom - (min(y, max_regret) / max_regret) * chart_rect.h)
                for idx, y in enumerate(ys)
            ]
            if len(pts) >= 2:
                pygame.draw.lines(surface, color, False, pts, 1)

        # Gambar kurva referensi Lai-Robbins c*ln(t)
        lr_curve = self.director.get_lai_robbins_bound()
        if len(lr_curve) >= 2:
            lr_pts = [
                (chart_rect.x + (idx / t_max) * chart_rect.w,
                 chart_rect.bottom - (min(y, max_regret) / max_regret) * chart_rect.h)
                for idx, y in enumerate(lr_curve)
            ]
            if len(lr_pts) >= 2:
                pygame.draw.lines(surface, (120, 120, 180), False, lr_pts, 1)

        # Gambar kurva Pemain / Aktor Utama (Garis Tebal Emas)
        p_ys = self.director.primary_tracker.cum_regret
        if len(p_ys) >= 2:
            p_pts = [
                (chart_rect.x + (idx / t_max) * chart_rect.w,
                 chart_rect.bottom - (min(y, max_regret) / max_regret) * chart_rect.h)
                for idx, y in enumerate(p_ys)
            ]
            if len(p_pts) >= 2:
                pygame.draw.lines(surface, (255, 235, 100), False, p_pts, 3)

        # Legenda ringkas di bawah grafik
        leg_str = "Kuning: Pemain/AI | Abu: Random | Merah: Greedy | Oranye: ε-Greedy | Biru: UCB1 | Hijau: Thompson"
        surface.blit(self.font_small.render(leg_str, True, (150, 165, 180)), (rect.x + 8, rect.bottom - 18))

    def _render_panel_c(self, surface: pygame.Surface, rect: pygame.Rect):
        """PANEL C: Skor & Metrik Ekonomi Musim Memancing."""
        pygame.draw.rect(surface, (18, 22, 30), rect, border_radius=6)
        pygame.draw.rect(surface, (50, 65, 85), rect, 1, border_radius=6)

        hdr = self.font_bold.render("PANEL C: STATUS EKONOMI & HORIZON", True, (140, 190, 255))
        surface.blit(hdr, (rect.x + 8, rect.y + 6))

        total_catches = self.director.rare_fish_caught + self.director.common_fish_caught
        gross_gold = (self.director.rare_fish_caught * 60) + (self.director.common_fish_caught * 15)
        bait_cost = total_catches * 5  # Biaya umpan asumsi 5 koin per lemparan
        net_gold = gross_gold - bait_cost

        # Informasi Baris
        lines = [
            f"Preset Kesulitan  : {self.director.preset_key} ({BANDIT_PRESETS.get(self.director.preset_key, {}).get('name')})",
            f"Horizon Musim (T) : {self.director.t} / {self.director.T} Lemparan ({self.director.T - self.director.t} sisa)",
            f"Tangkapan Langka  : {self.director.rare_fish_caught} ekor Ikan Emas (Reward bernilai 60 koin)",
            f"Tangkapan Biasa   : {self.director.common_fish_caught} ekor Ikan Sungai (Reward bernilai 15 koin)",
            f"Estimasi Nilai    : +{gross_gold} Koin Kotor | Biaya Umpan: -{bait_cost} | Bersih: +{net_gold} Koin",
            "Ganti Preset      : [1] Mudah  [2] Realistis  [3] Sulit"
        ]

        for idx, line in enumerate(lines):
            color = (255, 215, 80) if idx == 4 else ((120, 200, 255) if idx == 5 else (210, 220, 230))
            surface.blit(self.font_small.render(line, True, color), (rect.x + 10, rect.y + 30 + idx * 24))

    def _render_panel_d(self, surface: pygame.Surface, rect: pygame.Rect):
        """PANEL D: % Pemilihan Arm Optimal (Moving Window 20 Lemparan)."""
        pygame.draw.rect(surface, (18, 22, 30), rect, border_radius=6)
        pygame.draw.rect(surface, (50, 65, 85), rect, 1, border_radius=6)

        hdr = self.font_bold.render("PANEL D: % AKURASI PEMILIHAN SPOT OPTIMAL", True, (140, 190, 255))
        surface.blit(hdr, (rect.x + 8, rect.y + 6))

        # Tabel persentase pemilihan optimal per algoritma vs pemain
        surface.blit(self.font_small.render("Algoritma / Aktor   | Kumulatif Regret | % Pilihan Optimal", True, (160, 175, 190)),
                     (rect.x + 8, rect.y + 26))
        pygame.draw.line(surface, (45, 55, 75), (rect.x + 6, rect.y + 40), (rect.right - 6, rect.y + 40), 1)

        # 1. Baris Pemain / Aktor Utama
        p_opt = self.director.primary_tracker.optimal_pick_ratio * 100.0
        p_regret = self.director.primary_tracker.total_regret
        p_str = f"Pemain / AI Aktif   |     {p_regret:>6.2f}     |       {p_opt:>5.1f}%"
        surface.blit(self.font_small.render(p_str, True, (255, 235, 100)), (rect.x + 8, rect.y + 48))

        # 2. Baris 5 Ghost Agents
        y_offset = 72
        for name, g in self.director.ghosts.items():
            agent_disp = f"{g['display_name']:<18}"
            reg_val = g["tracker"].total_regret
            opt_val = g["tracker"].optimal_pick_ratio * 100.0
            row_str = f"{agent_disp} |     {reg_val:>6.2f}     |       {opt_val:>5.1f}%"
            surface.blit(self.font_small.render(row_str, True, g["color"]), (rect.x + 8, rect.y + y_offset))
            y_offset += 22
