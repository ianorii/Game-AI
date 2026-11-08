#!/usr/bin/env python3
"""
import_sunnyside.py - Impor aset "Sunnyside World Asset Pack V2.1" ke assets/.

Script ini MENGGANTI isi folder assets/ (tileset, sprite karakter, VFX, prop)
tetapi mempertahankan STRUKTUR dan POLA NAMA yang sudah dibaca oleh
src/asset_loader.py, sehingga konsep game tidak berubah:

    assets/
    ├── tilesets/
    │   ├── sunnyside_world.png     # atlas utama 1280x1280 (64x64 sel)
    │   ├── sunnyside_forest.png    # atlas hutan 468x504
    │   └── CREDITS_sunnyside_world.txt
    ├── sprites/
    │   ├── hero/                   # hero_idle / hero_run / hero_attack / ...
    │   └── monsters/               # zombie_* , ice_zombie_* , big_demon_*
    ├── props/                      # pohon, batu, jamur, hewan (y-sort)
    └── vfx/                        # api, kilau, ikon hati

Jalankan:  python tools/import_sunnyside.py --pack /path/ke/Sunnyside_World_ASSET_PACK_V2.1
(Paket sumber tidak disimpan di dalam proyek; folder assets/ sudah berisi hasil impor.)
Aman dijalankan berulang (idempoten).
"""

from __future__ import annotations

import colorsys
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ROOT = Path(__file__).resolve().parent.parent


def _resolve_pack():
    """
    Lokasi paket sumber Sunnyside (TIDAK disimpan di repo).

    Prioritas:
      1. argumen CLI  : python tools/import_sunnyside.py --pack /path/ke/paket
      2. env var      : SUNNYSIDE_PACK=/path/ke/paket
      3. default lama : new_aset/Sunnyside_World_ASSET_PACK_V2.1
    """
    argv = sys.argv[1:]
    if "--pack" in argv:
        i = argv.index("--pack")
        if i + 1 < len(argv):
            return Path(argv[i + 1]).expanduser().resolve()
    env = os.environ.get("SUNNYSIDE_PACK")
    if env:
        return Path(env).expanduser().resolve()
    return ROOT / "new_aset" / "Sunnyside_World_ASSET_PACK_V2.1"


PACK = _resolve_pack()
ASSETS = ROOT / "assets"

CHARS = PACK / "Sunnyside_World_Assets" / "Characters"
ELEMS = PACK / "Sunnyside_World_Assets" / "Elements"
GM = PACK / "Sunnyside_World_Gamemaker"

#: kanvas karakter (px sumber). Hero/monster diskalakan x2 -> 48x48 di layar,
#: Boss diskalakan x3 -> 72x72 (lebih besar dari satu tile 32 px).
CHAR_CANVAS = 24


# ==============================================================================
# UTILITAS
# ==============================================================================
def load(path):
    img = pygame.image.load(str(path)).convert_alpha()
    return img


def save(surf, rel):
    """Simpan surface ke assets/<rel>."""
    out = ASSETS / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(out))


def split_strip(path, count):
    """Potong sprite-strip horizontal menjadi `count` frame."""
    sheet = load(path)
    fw = sheet.get_width() // count
    return [sheet.subsurface((i * fw, 0, fw, sheet.get_height())).copy()
            for i in range(count)]


def char_frame_count(path):
    """
    Hitung jumlah frame dari lebar strip.

    Semua strip karakter Sunnyside memakai kanvas frame 96x64 px. Beberapa
    nama file menuliskan angka yang keliru (mis. spr_idle_strip9.png ternyata
    hanya 768 px = 8 frame), jadi lebar strip adalah sumber kebenaran.
    """
    return max(1, load(path).get_width() // 96)


def strip_frames(path, count=None, canvas=CHAR_CANVAS, tint=None):
    """
    Potong strip karakter lalu ratakan ke kanvas persegi `canvas`.

    Semua frame memakai kotak potong (union bbox) yang SAMA supaya animasi
    tidak "bergoyang" saat berganti frame. Karakter diletakkan di tengah
    horizontal dan menapak 3 px dari dasar kanvas (ruang untuk bayangan).
    """
    count = count or char_frame_count(path)
    frames = split_strip(path, count)
    rects = [f.get_bounding_rect() for f in frames]
    x0 = min(r.x for r in rects)
    y0 = min(r.y for r in rects)
    x1 = max(r.right for r in rects)
    y1 = max(r.bottom for r in rects)
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    if w > canvas or h > canvas:
        canvas = max(canvas, w, h)
    out = []
    for f in frames:
        crop = f.subsurface((x0, y0, w, h)).copy()
        pad = pygame.Surface((canvas, canvas), pygame.SRCALPHA)
        pad.blit(crop, ((canvas - w) // 2, canvas - 3 - h))
        if tint:
            pad.fill(tuple(tint) + (0,), special_flags=pygame.BLEND_MULT)
        out.append(pad.convert_alpha())
    return out


def trim(surf):
    r = surf.get_bounding_rect()
    return surf.subsurface(r).copy() if r.w and r.h else surf


def tinted(surf, color):
    out = surf.copy().convert_alpha()
    out.fill(tuple(color) + (0,), special_flags=pygame.BLEND_MULT)
    return out


def recolor_green(surf, hue=0.98, hue_span=0.55):
    """
    Geser hue piksel hijau (daun/badan Goblin) ke merah tanpa menghitamkan
    shading. Dipakai untuk membuat "Hobgoblin Tyrant" dari sprite Goblin:
    hanya bagian hijau yang berubah, kulit & pakaian tetap.
    """
    out = surf.copy()
    for y in range(out.get_height()):
        for x in range(out.get_width()):
            c = out.get_at((x, y))
            if c.a == 0:
                continue
            hh, ll, ss = colorsys.rgb_to_hls(c.r / 255, c.g / 255, c.b / 255)
            deg = hh * 360
            if 65 <= deg <= 175 and ss > 0.16:
                nh = (hue + (deg - 120) / 720.0) % 1.0
                nr, ng, nb = colorsys.hls_to_rgb(nh, ll, min(1.0, ss * 1.25))
                out.set_at((x, y), (int(nr * 255), int(ng * 255),
                                    int(nb * 255), c.a))
    return out


def heart_icon(fill):
    """Ikon hati 16x16 (pixel art) untuk HUD."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    rows = [
        "..XXX..XXX..",
        ".XXXXX.XXXX.",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
        ".XXXXXXXXXX.",
        "..XXXXXXXX..",
        "...XXXXXX...",
        "....XXXX....",
        ".....XX.....",
    ]
    dark = tuple(max(0, c - 70) for c in fill)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "X":
                s.set_at((x + 2, y + 3), fill + (255,))
                if y in (0, 1) and x in (0, 1, 7, 8):
                    continue
    # garis tepi bawah untuk memberi bentuk
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "X" and (y + 1 >= len(rows) or rows[y + 1][x] != "X"):
                s.set_at((x + 2, y + 3), dark + (255,))
    return s


# ==============================================================================
# 1. BERSIHKAN & SALIN TILESET
# ==============================================================================
def copy_tilesets():
    for entry in ASSETS.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    (ASSETS / "tilesets").mkdir(parents=True, exist_ok=True)

    shutil.copy2(GM / "tilesets" / "tileset_sunnysideworld" / "output_tileset.png",
                 ASSETS / "tilesets" / "sunnyside_world.png")
    shutil.copy2(GM / "tilesets" / "tileset_forest" / "output_tileset.png",
                 ASSETS / "tilesets" / "sunnyside_forest.png")
    (ASSETS / "tilesets" / "CREDITS_sunnyside_world.txt").write_text(
        "Sunnyside World Asset Pack V2.1\n"
        "https://sunnysideworld.com/  (Daniel Diggle / Pixel Boy)\n\n"
        "Dipakai untuk tilemap, karakter, dan prop game AI LABYRINTH.\n"
        "Arsip asli TIDAK menyertakan berkas lisensi; verifikasi ulang syarat\n"
        "penggunaan sebelum distribusi publik.\n",
        encoding="utf-8")


# ==============================================================================
# 2. HERO & MONSTER
# ==============================================================================
def import_characters():
    # ---- HERO: Human (base = tanpa rambut, paling netral) --------------------
    hero_sets = [
        ("IDLE", "base_idle_strip9.png", "hero_idle"),
        ("RUN", "base_run_strip8.png", "hero_run"),
        ("ATTACK", "base_attack_strip10.png", "hero_attack"),
        ("HURT", "base_hurt_strip8.png", "hero_hurt"),
        ("CASTING", "base_casting_strip15.png", "hero_cast"),
    ]
    for folder, name, out in hero_sets:
        frames = strip_frames(CHARS / "Human" / folder / name)
        for i, fr in enumerate(frames):
            save(fr, f"sprites/hero/{out}_f{i}.png")

    # ---- MONSTER: Goblin (hijau) & Skeleton (tulang, tint es) ---------------
    goblin_run = strip_frames(CHARS / "Goblin" / "PNG" / "spr_run_strip8.png")
    goblin_idle = strip_frames(CHARS / "Goblin" / "PNG" / "spr_idle_strip9.png")
    for i, fr in enumerate(goblin_run):
        save(fr, f"sprites/monsters/zombie_anim_f{i}.png")
    for i, fr in enumerate(goblin_idle):
        save(fr, f"sprites/monsters/zombie_idle_f{i}.png")

    skel_walk = strip_frames(CHARS / "Skeleton" / "PNG" / "skeleton_walk_strip8.png",
                             tint=(170, 215, 255))
    skel_idle = strip_frames(CHARS / "Skeleton" / "PNG" / "skeleton_idle_strip6.png",
                             tint=(170, 215, 255))
    for i, fr in enumerate(skel_walk):
        save(fr, f"sprites/monsters/ice_zombie_anim_f{i}.png")
    for i, fr in enumerate(skel_idle):
        save(fr, f"sprites/monsters/ice_zombie_idle_f{i}.png")

    # ---- BOSS: Goblin "Hobgoblin Tyrant" (hijau -> merah, skala x3) ---------
    for i, fr in enumerate(goblin_idle):
        save(recolor_green(fr), f"sprites/monsters/big_demon_idle_f{i}.png")
    for i, fr in enumerate(goblin_run):
        save(recolor_green(fr), f"sprites/monsters/big_demon_run_f{i}.png")


# ==============================================================================
# 3. VFX & IKON HUD
# ==============================================================================
def import_vfx():
    fire = split_strip(ELEMS / "VFX" / "Fire" / "spr_deco_fire_02_strip4.png", 4)
    for i, fr in enumerate(fire):
        canvas = pygame.Surface((16, 16), pygame.SRCALPHA)
        f = pygame.transform.scale(fr, (8, 12))
        canvas.blit(f, (4, 4))
        save(canvas.convert_alpha(), f"vfx/fire_f{i}.png")

    glint = split_strip(ELEMS / "VFX" / "Glint" / "spr_deco_glint_01_strip6.png", 6)
    for i, fr in enumerate(glint):
        canvas = pygame.Surface((16, 16), pygame.SRCALPHA)
        g = pygame.transform.scale(fr, (10, 10))
        canvas.blit(g, (3, 3))
        save(canvas.convert_alpha(), f"vfx/glint_f{i}.png")

    save(heart_icon((226, 78, 92)), "vfx/ui_heart_full.png")
    save(heart_icon((150, 150, 160)), "vfx/ui_heart_empty.png")
    half = heart_icon((226, 78, 92)).copy()
    half.fill((0, 0, 0, 0), (8, 0, 8, 16))
    half.blit(heart_icon((150, 150, 160)).subsurface((8, 0, 8, 16)), (8, 0))
    save(half, "vfx/ui_heart_half.png")


# ==============================================================================
# 4. PROP (pohon, batu, jamur, hewan)
# ==============================================================================
def import_props():
    jobs = [
        (ELEMS / "Plants" / "spr_deco_tree_01_strip4.png", 4, "tree_oak"),
        (ELEMS / "Plants" / "spr_deco_tree_02_strip4.png", 4, "tree_birch"),
        (ELEMS / "Plants" / "spr_deco_mushroom_red_01_strip4.png", 4, "mushroom_red"),
        (ELEMS / "Plants" / "spr_deco_mushroom_blue_01_strip4.png", 4, "mushroom_blue"),
        (ELEMS / "Animals" / "spr_deco_cow_strip4.png", 4, "cow"),
        (ELEMS / "Animals" / "spr_deco_sheep_01_strip4.png", 4, "sheep"),
        (ELEMS / "Animals" / "spr_deco_pig_01_strip4.png", 4, "pig"),
        (ELEMS / "Animals" / "spr_deco_chicken_01_strip4.png", 4, "chicken"),
    ]
    for path, count, name in jobs:
        for i, fr in enumerate(split_strip(path, count)):
            save(trim(fr).convert_alpha(), f"props/{name}_f{i}.png")

    # batu & peti dari folder Crops (satu frame)
    save(trim(load(ELEMS / "Crops" / "rock.png")).convert_alpha(), "props/rock_f0.png")
    save(trim(load(ELEMS / "Crops" / "crate_base.png")).convert_alpha(),
         "props/crate_f0.png")

    # tanaman matang untuk ladang desa (satu frame per jenis)
    for crop in ("wheat", "sunflower", "cabbage", "pumpkin", "carrot"):
        save(trim(load(ELEMS / "Crops" / f"{crop}_05.png")).convert_alpha(),
             f"props/crop_{crop}_f0.png")


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    if not PACK.exists():
        sys.exit(f"[import] paket tidak ditemukan: {PACK}\n"
                 "[import] jalankan dengan --pack /path/ke/Sunnyside_World_ASSET_PACK_V2.1\n"
                 "[import] atau set env SUNNYSIDE_PACK ke folder paket.")
    ASSETS.mkdir(parents=True, exist_ok=True)

    copy_tilesets()
    import_characters()
    import_vfx()
    import_props()

    total = sum(1 for _ in ASSETS.rglob("*.png"))
    print(f"[import] selesai - {total} PNG di {ASSETS}")
    print("[import] tileset  : sunnyside_world.png (64x64 sel, tile 16 px, pitch 20)")
    print("[import] karakter : hero 5 set, monster 2 jenis, boss 1")
    print("[import] vfx      : fire (4), glint (6), ikon hati (3)")
    print("[import] prop     : 2 pohon, 2 jamur, 4 hewan, batu, peti, 5 tanaman")


if __name__ == "__main__":
    main()
