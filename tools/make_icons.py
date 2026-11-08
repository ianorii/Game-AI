#!/usr/bin/env python3
"""
tools/make_icons.py - Generator Ikon Pixel Art 16x16 Otentik Sunnyside

Menghasilkan ikon-ikon pelengkap yang tidak terdapat di aset dasar Sunnyside:
  1. coin.png         - Koin emas dengan rim tebal dan highlight
  2. key.png          - Kunci gerbang kuno dengan kepala bulat dan gerigi
  3. bottle_empty.png - Botol kaca transparan dengan tutup gabus (cork)
  4. potion_red.png   - Botol ramuan penyembuh berisi cairan merah menyala
  5. gate_icon.png    - Gerbang besi berkunci (tertutup)
  6. gate_open.png    - Gerbang besi terbuka
Disimpan secara statis di assets/generated/ (bukan prosedural runtime).
"""

import os
import pygame

pygame.init()

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(ROOT_DIR, "assets", "generated")
os.makedirs(OUT_DIR, exist_ok=True)

# Palet Otentik Sunnyside World
DARK_OUTLINE = (38, 25, 45, 255)       # Outline gelap Sunnyside #26192d
GOLD_BRIGHT  = (255, 230, 110, 255)     # Highlight emas
GOLD_BASE    = (242, 178, 36, 255)      # Badan koin emas
GOLD_SHADOW  = (194, 114, 23, 255)      # Bayangan koin
GOLD_DARK    = (138, 72, 16, 255)       # Dasar bayangan koin

CORK_BASE    = (175, 115, 65, 255)      # Tutup botol gabus
CORK_DARK    = (125, 75, 40, 255)
GLASS_SHINE  = (230, 245, 255, 220)     # Kilau kaca
GLASS_BODY   = (160, 205, 230, 140)     # Kaca botol
POTION_RED   = (228, 59, 68, 240)       # Cairan ramuan merah
POTION_DARK  = (162, 38, 51, 255)
POTION_GLINT = (255, 140, 150, 255)

IRON_LIGHT   = (170, 175, 195, 255)     # Besi gerbang
IRON_BASE    = (110, 115, 135, 255)
IRON_DARK    = (65, 68, 85, 255)


def make_coin() -> pygame.Surface:
    surf = pygame.Surface((16, 16), pygame.SRCALPHA)
    # 12x12 circle on 16x16
    pixels = [
        # Outline
        (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2),
        (4, 3), (11, 3),
        (3, 4), (12, 4),
        (2, 5), (2, 6), (2, 7), (2, 8), (2, 9), (2, 10),
        (13, 5), (13, 6), (13, 7), (13, 8), (13, 9), (13, 10),
        (3, 11), (12, 11),
        (4, 12), (11, 12),
        (5, 13), (6, 13), (7, 13), (8, 13), (9, 13), (10, 13),
    ]
    for px, py in pixels:
        surf.set_at((px, py), DARK_OUTLINE)

    # Base fill
    for y in range(3, 13):
        for x in range(3, 13):
            if surf.get_at((x, y))[3] == 0:
                surf.set_at((x, y), GOLD_BASE)

    # Highlights & shadows
    for x in range(5, 10):
        surf.set_at((x, 3), GOLD_BRIGHT)
        surf.set_at((x, 4), GOLD_BRIGHT)
    surf.set_at((3, 5), GOLD_BRIGHT)
    surf.set_at((4, 5), GOLD_BRIGHT)
    surf.set_at((3, 6), GOLD_BRIGHT)

    # Bottom shadow
    for x in range(5, 11):
        surf.set_at((x, 11), GOLD_SHADOW)
        surf.set_at((x, 12), GOLD_DARK)
    surf.set_at((11, 9), GOLD_SHADOW)
    surf.set_at((12, 9), GOLD_DARK)
    surf.set_at((11, 10), GOLD_DARK)

    # Inner symbol (Star / Diamond)
    surf.set_at((7, 6), GOLD_BRIGHT)
    surf.set_at((8, 6), GOLD_BRIGHT)
    surf.set_at((6, 7), GOLD_BRIGHT)
    surf.set_at((7, 7), GOLD_DARK)
    surf.set_at((8, 7), GOLD_DARK)
    surf.set_at((9, 7), GOLD_BRIGHT)
    surf.set_at((6, 8), GOLD_BRIGHT)
    surf.set_at((7, 8), GOLD_DARK)
    surf.set_at((8, 8), GOLD_DARK)
    surf.set_at((9, 8), GOLD_BRIGHT)
    surf.set_at((7, 9), GOLD_SHADOW)
    surf.set_at((8, 9), GOLD_SHADOW)
    return surf


def make_key() -> pygame.Surface:
    surf = pygame.Surface((16, 16), pygame.SRCALPHA)
    # Kepala kunci bundar di kiri atas, batang miring ke kanan bawah
    # Ring
    outline = [
        (4, 2), (5, 2), (6, 2),
        (3, 3), (7, 3),
        (2, 4), (4, 4), (5, 4), (8, 4),
        (2, 5), (4, 5), (5, 5), (8, 5),
        (3, 6), (7, 6),
        (4, 7), (5, 7), (6, 7),
        # Batang
        (7, 8), (8, 8),
        (8, 9), (9, 9),
        (9, 10), (10, 10),
        (10, 11), (11, 11),
        (11, 12), (12, 12),
        (12, 13), (13, 13),
        # Gerigi kunci
        (12, 10), (13, 10), (13, 11),
        (14, 12), (14, 13)
    ]
    for x, y in outline:
        surf.set_at((x, y), DARK_OUTLINE)

    # Isi emas
    gold_fill = [
        (4, 3), (5, 3), (6, 3),
        (3, 4), (7, 4),
        (3, 5), (7, 5),
        (4, 6), (5, 6), (6, 6),
        (7, 7),
        (8, 8), (9, 9), (10, 10), (11, 11), (12, 12),
        (12, 10), (13, 11), (13, 12)
    ]
    for x, y in gold_fill:
        surf.set_at((x, y), GOLD_BASE)

    # Highlight
    surf.set_at((4, 3), GOLD_BRIGHT)
    surf.set_at((3, 4), GOLD_BRIGHT)
    surf.set_at((8, 8), GOLD_BRIGHT)
    surf.set_at((10, 10), GOLD_BRIGHT)
    return surf


def make_bottle(has_potion: bool = False) -> pygame.Surface:
    surf = pygame.Surface((16, 16), pygame.SRCALPHA)
    # Gabus di atas
    surf.set_at((7, 2), CORK_BASE)
    surf.set_at((8, 2), CORK_BASE)
    surf.set_at((7, 3), CORK_DARK)
    surf.set_at((8, 3), CORK_DARK)

    # Leher botol
    surf.set_at((6, 4), DARK_OUTLINE)
    surf.set_at((7, 4), GLASS_BODY)
    surf.set_at((8, 4), GLASS_SHINE)
    surf.set_at((9, 4), DARK_OUTLINE)

    surf.set_at((6, 5), DARK_OUTLINE)
    surf.set_at((7, 5), GLASS_BODY)
    surf.set_at((8, 5), GLASS_SHINE)
    surf.set_at((9, 5), DARK_OUTLINE)

    # Badan labu membulat (y=6..13)
    outline = [
        (5, 6), (10, 6),
        (4, 7), (11, 7),
        (3, 8), (12, 8),
        (3, 9), (12, 9),
        (3, 10), (12, 10),
        (3, 11), (12, 11),
        (4, 12), (11, 12),
        (5, 13), (6, 13), (7, 13), (8, 13), (9, 13), (10, 13)
    ]
    for x, y in outline:
        surf.set_at((x, y), DARK_OUTLINE)

    # Isi botol
    for y in range(7, 13):
        min_x = 4 if y in [7, 12] else 4
        max_x = 11 if y in [7, 12] else 11
        for x in range(min_x, max_x + 1):
            if surf.get_at((x, y))[3] == 0:
                if has_potion and y >= 8:
                    if x == 5 and y in [9, 10]:
                        surf.set_at((x, y), POTION_GLINT)
                    elif y >= 11:
                        surf.set_at((x, y), POTION_DARK)
                    else:
                        surf.set_at((x, y), POTION_RED)
                else:
                    surf.set_at((x, y), GLASS_BODY)

    # Kilau kaca sisi kiri
    surf.set_at((5, 7), GLASS_SHINE)
    surf.set_at((4, 8), GLASS_SHINE)
    surf.set_at((4, 9), GLASS_SHINE)
    return surf


def make_gate_icon(open_state: bool = False) -> pygame.Surface:
    surf = pygame.Surface((16, 16), pygame.SRCALPHA)
    # Tiang batu kiri & kanan
    for y in range(2, 15):
        surf.set_at((2, y), DARK_OUTLINE)
        surf.set_at((3, y), IRON_BASE)
        surf.set_at((12, y), IRON_BASE)
        surf.set_at((13, y), DARK_OUTLINE)

    # Balok atas
    for x in range(2, 14):
        surf.set_at((x, 2), DARK_OUTLINE)
        surf.set_at((x, 3), IRON_LIGHT)

    if not open_state:
        # Jeruji besi tertutup
        for y in range(4, 14):
            surf.set_at((5, y), IRON_BASE)
            surf.set_at((7, y), IRON_BASE)
            surf.set_at((8, y), IRON_BASE)
            surf.set_at((10, y), IRON_BASE)
        for x in range(4, 12):
            surf.set_at((x, 8), IRON_DARK)
            surf.set_at((x, 13), IRON_DARK)

        # Gembok emas di tengah
        for gx in [7, 8]:
            for gy in [7, 8, 9]:
                surf.set_at((gx, gy), GOLD_BASE)
        surf.set_at((7, 6), DARK_OUTLINE)
        surf.set_at((8, 6), DARK_OUTLINE)
    else:
        # Pintu besi terbuka ke samping
        for y in range(4, 14):
            surf.set_at((4, y), IRON_LIGHT)
            surf.set_at((11, y), IRON_LIGHT)
    return surf


def main():
    icons = {
        "coin.png": make_coin(),
        "key.png": make_key(),
        "bottle_empty.png": make_bottle(has_potion=False),
        "potion_red.png": make_bottle(has_potion=True),
        "gate_locked.png": make_gate_icon(open_state=False),
        "gate_open.png": make_gate_icon(open_state=True),
    }

    print(f"Menyimpan ikon ke {OUT_DIR}:")
    for fname, img in icons.items():
        path = os.path.join(OUT_DIR, fname)
        pygame.image.save(img, path)
        print(f"  -> {fname} (16x16 RGBA)")

    # Catat ke docs/ASSET_NOTES.md
    notes_path = os.path.join(ROOT_DIR, "docs", "ASSET_NOTES.md")
    os.makedirs(os.path.dirname(notes_path), exist_ok=True)
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("# Catatan Aset Khusus & Generated - Sunnyside World\n\n")
        f.write("Aset di bawah ini dibuat menggunakan `tools/make_icons.py` untuk melengkapi kebutuhan gameplay Fase 1A yang tidak tersedia secara native di bundle Sunnyside World.\n\n")
        f.write("## Ikon 16x16 (assets/generated/)\n\n")
        f.write("| File | Deskripsi | Ukuran | Sumber Palet |\n")
        f.write("|:-----|:----------|:------:|:-------------|\n")
        f.write("| `coin.png` | Koin emas ekonomi desa dengan rim gelap & bintang | 16x16 | Sunnyside Gold/UI |\n")
        f.write("| `key.png` | Kunci gerbang reruntuhan boss | 16x16 | Sunnyside Gold/Dark Outline |\n")
        f.write("| `bottle_empty.png` | Botol ramuan kaca kosong bertutup gabus | 16x16 | Sunnyside Glass/Wood |\n")
        f.write("| `potion_red.png` | Ramuan penyembuh (HP Potion) merah menyala | 16x16 | Sunnyside Redbar/Glass |\n")
        f.write("| `gate_locked.png` | Ikon gerbang besi berkunci (tertutup) | 16x16 | Sunnyside Iron/Gold |\n")
        f.write("| `gate_open.png` | Ikon gerbang besi terbuka | 16x16 | Sunnyside Iron |\n\n")
        f.write("Semua file disimpan statis di `assets/generated/` dan dimuat via `src/asset_catalog.py`.\n")

    print(f"[OK] Dokumentasi dicatat di: {notes_path}")


if __name__ == "__main__":
    main()
