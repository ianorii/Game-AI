"""
capture_prep_screenshots.py - Mengambil 5 screenshot Layar Persiapan sesuai spesifikasi Bagian 1:
1. prep_screen_valid.png: loadout valid (kartu terpilih emas, bar hijau/kuning, checklist semua hijau, status SIAP)
2. prep_screen_budget_over.png: loadout melebihi budget (bar budget merah meluap, checklist merah, status DITOLAK)
3. prep_screen_disabled_reasons.png: item-item disabled menampilkan alasan singkat di kartu
4. prep_screen_csp_suggestion.png: setelah menekan [S] menampilkan loadout optimal hasil solver
5. prep_screen_hover.png: saat mouse hover di salah satu kartu item
"""

import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pygame
import config
from battle.prep_ui import PrepUI, get_prep_layout_rects

def capture_all():
    pygame.init()
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    screenshots_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "screenshots"))
    os.makedirs(screenshots_dir, exist_ok=True)

    ui = PrepUI()

    # 1. Valid Loadout
    ui.set_loadout({
        "WEAPON": "Pedang Biasa",
        "ARMOR": "Kulit",
        "CHARM": "Jimat Vitalitas",
        "CONSUMABLE": "Potion Ekstra"
    })
    ui.hovered_card = None
    ui.draw(screen)
    valid_path = os.path.join(screenshots_dir, "prep_screen_valid.png")
    pygame.image.save(screen, valid_path)
    print(f"[OK] Saved: {valid_path}")

    # 2. Budget Over Loadout
    ui.set_loadout({
        "WEAPON": "Tongkat Api",     # cost 5
        "ARMOR": "Besi",             # cost 5
        "CHARM": "Jimat Kritikal",   # cost 4
        "CONSUMABLE": "Bom Asap"     # cost 3 -> total 17 > 10
    })
    ui.hovered_card = None
    ui.draw(screen)
    budget_path = os.path.join(screenshots_dir, "prep_screen_budget_over.png")
    pygame.image.save(screen, budget_path)
    print(f"[OK] Saved: {budget_path}")

    # 3. Disabled Reasons
    # Kapak Berat terpilih -> Jimat Kritikal disabled (! Bentrok)
    # Besi terpilih -> Tongkat Api disabled (! Butuh Kain)
    # Total cost/weight mendekati batas sehingga item lain menunjukkan alasan ! Budget / ! Beban
    ui.set_loadout({
        "WEAPON": "Kapak Berat",
        "ARMOR": "Besi",
        "CHARM": "Jimat Vitalitas",
        "CONSUMABLE": "Kosong"
    })
    ui.hovered_card = None
    ui.draw(screen)
    reasons_path = os.path.join(screenshots_dir, "prep_screen_disabled_reasons.png")
    pygame.image.save(screen, reasons_path)
    print(f"[OK] Saved: {reasons_path}")

    # 4. CSP Suggestion
    ui.apply_csp_recommendation()
    # Langsung selesaikan animasi jika ada
    ui.is_animating_csp = False
    best_loadout, stats = ui.solver.best_loadout()
    ui.set_loadout(best_loadout)
    ui.hovered_card = None
    ui.draw(screen)
    csp_path = os.path.join(screenshots_dir, "prep_screen_csp_suggestion.png")
    pygame.image.save(screen, csp_path)
    print(f"[OK] Saved: {csp_path}")

    # 5. Mouse Hover Effect
    rects = get_prep_layout_rects()
    col_c = rects["col_center"]
    hover_x = col_c.x + 330
    hover_y = col_c.y + 60
    ui.hovered_card = ("WEAPON", "Tongkat Api")
    ui.mouse_pos = (hover_x, hover_y)
    ui.draw(screen)
    hover_path = os.path.join(screenshots_dir, "prep_screen_hover.png")
    pygame.image.save(screen, hover_path)
    print(f"[OK] Saved: {hover_path}")

    pygame.quit()
    print("Semua 5 screenshot Layar Persiapan berhasil diambil!")

if __name__ == "__main__":
    capture_all()
