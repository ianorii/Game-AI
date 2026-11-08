#!/usr/bin/env python3
"""
tools/generate_figures.py
Menghasilkan gambar PNG resolusi tinggi dan bergaya akademis untuk docs/figures/:
1. architecture.png     : Diagram arsitektur modular src/planning/ dan alur data siklus tertutup.
2. benchmark_nodes.png  : Grafik batang perbandingan node diekspansi (P1 s/d P4).
3. benchmark_time.png   : Grafik batang perbandingan waktu pencarian dalam ms (P1 s/d P4).
"""

import os
import sys
import pygame
import math

os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()

FIGURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "figures"))
os.makedirs(FIGURES_DIR, exist_ok=True)

# Palet Warna Akademis
BG_COLOR = (248, 250, 252)          # Slate 50
CARD_BG = (255, 255, 255)           # White
CARD_BORDER = (226, 232, 240)       # Slate 200
HEADER_BG = (241, 245, 249)         # Slate 100
TEXT_MAIN = (15, 23, 42)            # Slate 900
TEXT_MUTED = (100, 116, 139)        # Slate 500
ACCENT_BLUE = (37, 99, 235)         # Blue 600
ACCENT_CYAN = (8, 145, 178)         # Cyan 600
ACCENT_GREEN = (22, 163, 74)        # Green 600
ACCENT_AMBER = (217, 119, 6)        # Amber 600
ACCENT_PURPLE = (147, 51, 234)      # Purple 600
ACCENT_RED = (220, 38, 38)          # Red 600
GRID_COLOR = (226, 232, 240)


def get_fonts():
    # Gunakan font sistem Sans yang bersih
    f_title = pygame.font.SysFont("dejavusans", 22, bold=True)
    f_sub = pygame.font.SysFont("dejavusans", 13, italic=True)
    f_card_hdr = pygame.font.SysFont("dejavusans", 15, bold=True)
    f_body_b = pygame.font.SysFont("dejavusans", 12, bold=True)
    f_body = pygame.font.SysFont("dejavusans", 11)
    f_small = pygame.font.SysFont("dejavusans", 10)
    return f_title, f_sub, f_card_hdr, f_body_b, f_body, f_small


def draw_arrow(surf, start, end, color=ACCENT_BLUE, width=2, arrow_size=8):
    pygame.draw.line(surf, color, start, end, width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    p1 = (end[0] - arrow_size * math.cos(angle - math.pi / 6),
          end[1] - arrow_size * math.sin(angle - math.pi / 6))
    p2 = (end[0] - arrow_size * math.cos(angle + math.pi / 6),
          end[1] - arrow_size * math.sin(angle + math.pi / 6))
    pygame.draw.polygon(surf, color, [end, p1, p2])


def draw_card(surf, rect, title, badge_color, items, f_hdr, f_item_b, f_item):
    x, y, w, h = rect
    pygame.draw.rect(surf, CARD_BG, (x, y, w, h), border_radius=8)
    pygame.draw.rect(surf, CARD_BORDER, (x, y, w, h), width=2, border_radius=8)

    # Header strip
    pygame.draw.rect(surf, HEADER_BG, (x + 2, y + 2, w - 4, 34), border_top_left_radius=7, border_top_right_radius=7)
    pygame.draw.rect(surf, badge_color, (x + 10, y + 8, 6, 20), border_radius=3)
    t_surf = f_hdr.render(title, True, TEXT_MAIN)
    surf.blit(t_surf, (x + 24, y + 10))

    # Items
    cy = y + 44
    for key, desc in items:
        k_surf = f_item_b.render(f"• {key}: ", True, TEXT_MAIN)
        surf.blit(k_surf, (x + 12, cy))
        kw = k_surf.get_width()
        d_surf = f_item.render(desc, True, TEXT_MUTED)
        surf.blit(d_surf, (x + 12 + kw, cy))
        cy += 20


def generate_architecture_figure():
    W, H = 1200, 720
    surf = pygame.Surface((W, H))
    surf.fill(BG_COLOR)
    f_title, f_sub, f_hdr, f_bb, f_b, f_sm = get_fonts()

    # Header Dokumen
    title = f_title.render("Gambar 1. Arsitektur Modular Engine Automated Planning (src/planning/)", True, TEXT_MAIN)
    surf.blit(title, (40, 25))
    subtitle = f_sub.render(
        "Alur Data Siklus Tertutup (Closed-Loop): State Dunia -> Generator Problem -> Algoritma Perencana -> Eksekutor -> Monitor -> Replan",
        True, TEXT_MUTED
    )
    surf.blit(subtitle, (40, 55))

    # Garis pemisah atas
    pygame.draw.line(surf, CARD_BORDER, (40, 80), (W - 40, 80), 2)

    # 1. Baris Atas: Input & Pengetahuan Dasar
    draw_card(
        surf, (40, 95, 350, 175),
        "1. Pengetahuan & Data Statis", ACCENT_BLUE,
        [
            ("expedition.domain", "PDDL skema aksi, tipe & predikat"),
            ("catalog.json", "Katalog harga, status jual/beli toko"),
            ("readiness.json", "Matriks empiris kesiapan boss (Minimax)"),
            ("walkable_mask.png", "Topologi grid 2D penyeberangan & obstacle"),
        ], f_hdr, f_bb, f_b
    )

    draw_card(
        surf, (425, 95, 350, 175),
        "2. Grounding & Metrik Nyata", ACCENT_CYAN,
        [
            ("pddl_parser.py", "Parser AST domain & problem PDDL"),
            ("distance_matrix.py", "A* rute nyata dibagi kecepatan hero (cost s)"),
            ("problem_generator.py", "Kompilasi s0 & tangga koin dinamis"),
            ("grounding.py", "Backward Relevance Pruning (322 -> 116 aksi)"),
        ], f_hdr, f_bb, f_b
    )

    draw_card(
        surf, (810, 95, 350, 175),
        "3. Mesin Heuristik & Graf", ACCENT_PURPLE,
        [
            ("heuristics.py", "Relaksasi ignore-delete (h_max, h_add, h_FF)"),
            ("planning_graph.py", "Graf berlapis, action/fact mutex, GraphPlan"),
            ("regression.py", "Pencarian mundur (Subgoal Regression, Dual Goal)"),
            ("htn.py", "Dekomposisi hierarkis SHOP (Task & Method NPC)"),
        ], f_hdr, f_bb, f_b
    )

    # 2. Baris Tengah: Inti Perencana
    draw_card(
        surf, (40, 310, 540, 180),
        "4. Algoritma Perencanaan Maju (planner.py)", ACCENT_AMBER,
        [
            ("Pencarian Buta (Blind)", "BFS (optimal langkah) & UCS (optimal biaya nyata)"),
            ("Pencarian Terarah (A*)", "A*(h_max) [Admissible] & A*(h_add) [Satisficing]"),
            ("Weighted A* (h_FF)", "Rencana santai + Helpful Actions (Solusi Cepat P4)"),
            ("Planning Graph A*", "A*(h_level dinamis) vs Static Level dari s0"),
            ("IncrementalPlanner", "Pemecah frame-budget (<= 20 ms) agar game 50 FPS"),
        ], f_hdr, f_bb, f_b
    )

    draw_card(
        surf, (620, 310, 540, 180),
        "5. Eksekusi & Pengendalian Otonom", ACCENT_GREEN,
        [
            ("executor.py", "Penerjemah PDDL ke fungsi dunia nyata (world_actions)"),
            ("autopilot.py", "Kendali F7/F9/F10: Mode OFF, ADVISOR, dan AUTO"),
            ("Pause / Resume WASD", "Jeda otomatis saat pemain menggerakkan hero"),
            ("planner_ui.py", "Overlay F7, banner unclipped, waypoints & sorotan"),
            ("WorldActions", "A* Navigasi, Mine, Fish, Craft, Farm, Boss Battle"),
        ], f_hdr, f_bb, f_b
    )

    # 3. Baris Bawah: Monitoring & Loop Replan
    draw_card(
        surf, (40, 530, 1120, 150),
        "6. Pengawasan Reaktif & Deteksi Anomali Tertutup (monitor.py)", ACCENT_RED,
        [
            ("Penyimpangan State", "Mendeteksi jika hero digerakkan manual atau aksi gagal di lingkungan"),
            ("Deteksi Rintangan Rute", "Detour koridor alternatif; bila terputus total -> Menyerah (Surrender)"),
            ("Evaluasi Kekalahan Tempur", "Kalah di boss (0 potion) -> Otomatis replan bercocok tanam & racik ramuan baru"),
            ("Siklus Replan Otonom", "Pemicu replan -> Panggil problem_generator -> Cari rencana baru via WA* (14.8 ms)"),
        ], f_hdr, f_bb, f_b
    )

    # Panah Alur Data
    draw_arrow(surf, (390, 180), (425, 180), ACCENT_BLUE, 3)
    draw_arrow(surf, (775, 180), (810, 180), ACCENT_CYAN, 3)
    draw_arrow(surf, (600, 270), (310, 310), ACCENT_BLUE, 3)
    draw_arrow(surf, (985, 270), (890, 310), ACCENT_PURPLE, 3)
    draw_arrow(surf, (580, 400), (620, 400), ACCENT_AMBER, 3)
    draw_arrow(surf, (890, 490), (890, 530), ACCENT_GREEN, 3)

    # Panah Loop Replan (Balik dari Bawah ke Atas Kiri)
    draw_arrow(surf, (150, 530), (150, 490), ACCENT_RED, 3)
    lbl_replan = f_sm.render("[REPLAN LOOP]", True, ACCENT_RED)
    surf.blit(lbl_replan, (160, 505))

    out_path = os.path.join(FIGURES_DIR, "architecture.png")
    pygame.image.save(surf, out_path)
    print(f"  -> {out_path} berhasil dibuat.")


def generate_benchmark_nodes_figure():
    W, H = 1000, 600
    surf = pygame.Surface((W, H))
    surf.fill(BG_COLOR)
    f_title, f_sub, f_card_hdr, f_body_b, f_body, f_sm = get_fonts()

    title = f_title.render("Gambar 2. Perbandingan Node Diekspansi Algoritma Perencanaan (P1 s/d P4)", True, TEXT_MAIN)
    surf.blit(title, (40, 25))
    subtitle = f_sub.render(
        "Skala Logaritmik: Evaluasi Efisiensi Pencarian dan Pencegahan Ledakan Kombinatorial (Sumber: docs/report_data/benchmark.json)",
        True, TEXT_MUTED
    )
    surf.blit(subtitle, (40, 55))
    pygame.draw.line(surf, CARD_BORDER, (40, 80), (W - 40, 80), 2)

    # Area Plot
    px, py, pw, ph = 100, 120, 840, 400
    pygame.draw.rect(surf, CARD_BG, (px, py, pw, ph), border_radius=6)
    pygame.draw.rect(surf, CARD_BORDER, (px, py, pw, ph), width=1, border_radius=6)

    # Y-axis Skala Log (1 s/d 100,000)
    # y = py + ph - math.log10(val) / 5 * ph
    y_ticks = [1, 10, 100, 1000, 10000]
    for yv in y_ticks:
        ly = py + ph - (math.log10(yv) / 4.0) * ph
        pygame.draw.line(surf, GRID_COLOR, (px, ly), (px + pw, ly), 1)
        lbl = f_sm.render(f"{yv:,}", True, TEXT_MUTED)
        surf.blit(lbl, (px - 50, ly - 7))

    # Label Sumbu Y
    lbl_y = f_body_b.render("Node (Skala Log)", True, TEXT_MAIN)
    surf.blit(lbl_y, (px - 60, py - 25))

    # Data
    # P1: Simple Key, P2: Open Gate, P3: Potion Craft, P4: Final Game
    categories = ["P1: Simple Key", "P2: Open Gate", "P3: Potion Craft", "P4: Final Game"]
    algos = [
        ("BFS", (59, 130, 246)),         # Blue 500
        ("UCS", (16, 185, 129)),         # Emerald 500
        ("A* (h_max)", (245, 158, 11)),   # Amber 500
        ("A* (h_add)", (168, 85, 247)),   # Purple 500
        ("WA* (h_FF)", (239, 68, 68)),    # Red 500
    ]

    # Node data dari benchmark empiris
    data = {
        "P1: Simple Key": [44, 35, 16, 9, 7],
        "P2: Open Gate": [48, 48, 29, 13, 12],
        "P3: Potion Craft": [3899, 3888, 526, 24, 14],
        "P4: Final Game": [10000, 10000, 2396, 1408, 939],  # BFS/UCS kena batas node (10,000)
    }

    group_w = pw / len(categories)
    bar_w = 26

    for ci, cat in enumerate(categories):
        gx = px + ci * group_w
        vals = data[cat]

        # Label kategori
        lbl_cat = f_card_hdr.render(cat, True, TEXT_MAIN)
        surf.blit(lbl_cat, (gx + group_w / 2 - lbl_cat.get_width() / 2, py + ph + 12))

        # Gambar bar per algoritma
        start_bx = gx + (group_w - (len(algos) * bar_w + (len(algos) - 1) * 6)) / 2
        for ai, (aname, acolor) in enumerate(algos):
            val = vals[ai]
            bx = start_bx + ai * (bar_w + 6)
            log_h = (math.log10(max(1, val)) / 4.0) * ph
            by = py + ph - log_h
            pygame.draw.rect(surf, acolor, (bx, by, bar_w, log_h), border_top_left_radius=4, border_top_right_radius=4)

            # Angka nilai di atas bar
            val_txt = f"{val:,}" if val < 10000 else "10k*"
            lbl_v = f_sm.render(val_txt, True, TEXT_MAIN)
            surf.blit(lbl_v, (bx + bar_w / 2 - lbl_v.get_width() / 2, by - 14))

    # Legend
    leg_x = px + pw - 430
    leg_y = py - 30
    for aname, acolor in algos:
        pygame.draw.rect(surf, acolor, (leg_x, leg_y + 3, 12, 12), border_radius=2)
        lbl_a = f_sm.render(aname, True, TEXT_MAIN)
        surf.blit(lbl_a, (leg_x + 18, leg_y + 2))
        leg_x += lbl_a.get_width() + 28

    out_path = os.path.join(FIGURES_DIR, "benchmark_nodes.png")
    pygame.image.save(surf, out_path)
    print(f"  -> {out_path} berhasil dibuat.")


def generate_benchmark_time_figure():
    W, H = 1000, 600
    surf = pygame.Surface((W, H))
    surf.fill(BG_COLOR)
    f_title, f_sub, f_card_hdr, f_body_b, f_body, f_sm = get_fonts()

    title = f_title.render("Gambar 3. Perbandingan Waktu Komputasi Algoritma Perencanaan (P1 s/d P4)", True, TEXT_MAIN)
    surf.blit(title, (40, 25))
    subtitle = f_sub.render(
        "Trade-off Evaluasi Heuristik: Waktu Pencarian dalam Milidetik (Sumber: docs/report_data/benchmark.json)",
        True, TEXT_MUTED
    )
    surf.blit(subtitle, (40, 55))
    pygame.draw.line(surf, CARD_BORDER, (40, 80), (W - 40, 80), 2)

    px, py, pw, ph = 100, 120, 840, 400
    pygame.draw.rect(surf, CARD_BG, (px, py, pw, ph), border_radius=6)
    pygame.draw.rect(surf, CARD_BORDER, (px, py, pw, ph), width=1, border_radius=6)

    # Y-axis Skala Log (1 ms s/d 10,000 ms)
    y_ticks = [1, 10, 100, 1000, 5000]
    for yv in y_ticks:
        ly = py + ph - (math.log10(yv) / math.log10(5000)) * ph
        pygame.draw.line(surf, GRID_COLOR, (px, ly), (px + pw, ly), 1)
        lbl = f_sm.render(f"{yv:,} ms", True, TEXT_MUTED)
        surf.blit(lbl, (px - 65, ly - 7))

    lbl_y = f_body_b.render("Waktu (ms)", True, TEXT_MAIN)
    surf.blit(lbl_y, (px - 60, py - 25))

    categories = ["P1: Simple Key", "P2: Open Gate", "P3: Potion Craft", "P4: Final Game"]
    algos = [
        ("BFS", (59, 130, 246)),
        ("UCS", (16, 185, 129)),
        ("A* (h_max)", (245, 158, 11)),
        ("A* (h_add)", (168, 85, 247)),
        ("WA* (h_FF)", (239, 68, 68)),
    ]

    # Data waktu dalam milidetik
    data = {
        "P1: Simple Key": [24.63, 19.32, 47.36, 38.85, 11.62],
        "P2: Open Gate": [29.05, 29.41, 66.48, 37.81, 11.50],
        "P3: Potion Craft": [3000.36, 3000.35, 3006.50, 181.29, 15.50],
        "P4: Final Game": [5000.0, 5000.0, 5000.0, 5000.0, 1458.86],  # yang timeout dipatok di 5000ms
    }

    group_w = pw / len(categories)
    bar_w = 26

    for ci, cat in enumerate(categories):
        gx = px + ci * group_w
        vals = data[cat]

        lbl_cat = f_card_hdr.render(cat, True, TEXT_MAIN)
        surf.blit(lbl_cat, (gx + group_w / 2 - lbl_cat.get_width() / 2, py + ph + 12))

        start_bx = gx + (group_w - (len(algos) * bar_w + (len(algos) - 1) * 6)) / 2
        for ai, (aname, acolor) in enumerate(algos):
            val = vals[ai]
            bx = start_bx + ai * (bar_w + 6)
            log_h = (math.log10(max(1, val)) / math.log10(5000)) * ph
            by = py + ph - log_h
            pygame.draw.rect(surf, acolor, (bx, by, bar_w, log_h), border_top_left_radius=4, border_top_right_radius=4)

            val_txt = f"{val:.0f}ms" if val < 5000 else "T/O"
            lbl_v = f_sm.render(val_txt, True, TEXT_MAIN)
            surf.blit(lbl_v, (bx + bar_w / 2 - lbl_v.get_width() / 2, by - 14))

    # Legend
    leg_x = px + pw - 430
    leg_y = py - 30
    for aname, acolor in algos:
        pygame.draw.rect(surf, acolor, (leg_x, leg_y + 3, 12, 12), border_radius=2)
        lbl_a = f_sm.render(aname, True, TEXT_MAIN)
        surf.blit(lbl_a, (leg_x + 18, leg_y + 2))
        leg_x += lbl_a.get_width() + 28

    out_path = os.path.join(FIGURES_DIR, "benchmark_time.png")
    pygame.image.save(surf, out_path)
    print(f"  -> {out_path} berhasil dibuat.")


def main():
    print("================================================================================")
    print("GENERATE FIGURES: Menghasilkan Diagram & Grafik PNG di docs/figures/")
    print("================================================================================")
    generate_architecture_figure()
    generate_benchmark_nodes_figure()
    generate_benchmark_time_figure()
    print("================================================================================")
    print("SELESAI! Seluruh gambar tersimpan di docs/figures/.")


if __name__ == "__main__":
    main()
