#!/usr/bin/env python3
"""
extract_sunnyside_assets.py - Ekstraktor lengkap aset Sunnyside World.
Mengekstrak rumah, prop desa/danau, prop interaktif, dan sprite UI Sunnyside
ke assets/props/ dan assets/ui/.
"""

import colorsys
import os
import re
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "new_aset" / "Sunnyside_World_ASSET_PACK_V2.1"
ASSETS = ROOT / "assets"
PROPS = ASSETS / "props"
UI_DIR = ASSETS / "ui"
TILESETS = ASSETS / "tilesets"

PROPS.mkdir(parents=True, exist_ok=True)
UI_DIR.mkdir(parents=True, exist_ok=True)

def decompress(data_list):
    out = []
    i = 0
    while i < len(data_list):
        count = data_list[i]
        i += 1
        if count < 0:
            val = data_list[i]
            i += 1
            out.extend([val] * (-count))
        else:
            out.extend(data_list[i:i+count])
            i += count
    return out

def extract_houses():
    print("[extract] mengekstrak rumah dari Room1 & atlas...")
    room_path = PACK / "Sunnyside_World_Gamemaker" / "rooms" / "Room1" / "Room1.yy"
    if not room_path.exists():
        print(f"[extract] {room_path} tidak ditemukan!")
        return

    content = room_path.read_text(encoding="utf-8")
    tileset_img = pygame.image.load(str(TILESETS / "sunnyside_world.png")).convert_alpha()

    pattern = r'\"resourceType\":\"GMRTileLayer\"[^\}]*?\"name\":\"([^\"]+)\".*?\"SerialiseWidth\":(\d+),\"SerialiseHeight\":(\d+),\"TileCompressedData\":\[(.*?)\]'
    matches = re.findall(pattern, content, re.DOTALL)
    layer_dict = {m[0]: m for m in matches}

    W, H = 86, 48
    house_layers = ['building', 'decoration_01', 'decoration_02', 'decoration_03']

    surf = pygame.Surface((W * 16, H * 16), pygame.SRCALPHA)
    for lname in house_layers:
        if lname not in layer_dict:
            continue
        m = layer_dict[lname]
        lw, lh = int(m[1]), int(m[2])
        nums = [int(x.strip()) for x in m[3].split(',') if x.strip()]
        tiles = decompress(nums)
        for idx, raw in enumerate(tiles):
            if raw == -2147483648 or raw == 0:
                continue
            flip_x = bool(raw & 0x10000000)
            flip_y = bool(raw & 0x20000000)
            tile_id = raw & 0x0FFFFFFF
            col = tile_id % 64
            row = tile_id // 64
            rect = pygame.Rect(col * 20 + 2, row * 20 + 2, 16, 16)
            if tileset_img.get_rect().contains(rect):
                t_surf = tileset_img.subsurface(rect).copy()
                if flip_x or flip_y:
                    t_surf = pygame.transform.flip(t_surf, flip_x, flip_y)
                gx = idx % lw
                gy = idx // lw
                surf.blit(t_surf, (gx * 16, gy * 16))

    # Helper untuk memotong, membersihkan dan menyimpan
    def crop_clean_save(rx, ry, rw, rh, out_name, recolor_blue=False):
        sub = surf.subsurface((rx * 16, ry * 16, rw * 16, rh * 16)).copy()
        # Bersihkan piksel terisolasi di sudut (mis. artefak tebing abu-abu)
        for y in range(sub.get_height()):
            for x in range(sub.get_width()):
                c = sub.get_at((x, y))
                if c.a > 0:
                    # Hapus piksel abu-abu/tanah di tepi atas/kiri yang tidak terhubung ke atap
                    if c.r == c.g == c.b and c.r > 150 and y < 16 and (x < 16 or x > sub.get_width() - 16):
                        sub.set_at((x, y), (0, 0, 0, 0))

        if recolor_blue:
            # Ubah atap ungu menjadi atap biru Sunnyside
            for y in range(sub.get_height()):
                for x in range(sub.get_width()):
                    c = sub.get_at((x, y))
                    if c.a > 0 and c.r > 90 and c.b > 115 and c.r > c.g + 18 and c.b > c.g + 18:
                        lum = (c.r * 0.299 + c.g * 0.587 + c.b * 0.114) / 255.0
                        nr = int(max(0, min(255, 30 + lum * 45)))
                        ng = int(max(0, min(255, 115 + lum * 85)))
                        nb = int(max(0, min(255, 185 + lum * 70)))
                        sub.set_at((x, y), (nr, ng, nb, c.a))

        bbox = sub.get_bounding_rect()
        if bbox.w > 0 and bbox.h > 0:
            final = sub.subsurface(bbox).copy()
            # Skala x2 untuk tampilan pixel-art tajam di tile 32 px
            scaled = pygame.transform.scale(final, (final.get_width() * 2, final.get_height() * 2))
            out_file = PROPS / f"{out_name}_f0.png"
            pygame.image.save(scaled, str(out_file))
            print(f"  [saved] {out_file.name} ({scaled.get_size()})")

    # 1. Rumah pondok biru Sunnyside
    crop_clean_save(13, 26, 6, 6, "house_blue", recolor_blue=True)

    # 2. Rumah desa atap merah/oranye
    crop_clean_save(54, 23, 7, 6, "house_red")

    # 3. Rumah bertingkat kayu / Manor estate
    crop_clean_save(28, 2, 8, 12, "house_manor")

    # 4. Gudang / lumbung kayu desa
    crop_clean_save(17, 33, 11, 6, "house_barn")

    # 5. Pondok kabin kayu hutan kecil
    crop_clean_save(32, 19, 5, 5, "house_cabin")

    # 6. Toko pandai besi / bengkel tempa
    crop_clean_save(72, 15, 14, 11, "house_forge", recolor_blue=True)


def extract_props():
    print("[extract] mengekstrak prop Sunnyside (kincir, perahu, bebek, apel, dll)...")
    ELEMS = PACK / "Sunnyside_World_Assets" / "Elements"
    GM_SPRITES = PACK / "Sunnyside_World_Gamemaker" / "sprites"

    # 1. Kincir angin beranimasi (9 frame)
    windmill_path = ELEMS / "Other" / "spr_deco_windmill_strip9.png"
    if windmill_path.exists():
        sheet = pygame.image.load(str(windmill_path)).convert_alpha()
        fw = sheet.get_width() // 9
        fh = sheet.get_height()
        for i in range(9):
            frame = sheet.subsurface((i * fw, 0, fw, fh)).copy()
            scaled = pygame.transform.scale(frame, (fw * 2, fh * 2))
            pygame.image.save(scaled, str(PROPS / f"windmill_f{i}.png"))
        print(f"  [saved] windmill_f0..f8.png ({fw*2}x{fh*2})")

    # 2. Bebek danau (4 frame)
    duck_path = ELEMS / "Animals" / "spr_deco_duck_01_strip4.png"
    if duck_path.exists():
        sheet = pygame.image.load(str(duck_path)).convert_alpha()
        fw = sheet.get_width() // 4
        fh = sheet.get_height()
        for i in range(4):
            frame = sheet.subsurface((i * fw, 0, fw, fh)).copy()
            scaled = pygame.transform.scale(frame, (fw * 2, fh * 2))
            pygame.image.save(scaled, str(PROPS / f"duck_f{i}.png"))
        print(f"  [saved] duck_f0..f3.png ({fw*2}x{fh*2})")

    # 3. Perahu kayu di air (4 frame)
    boat_path = ELEMS / "Other" / "spr_deco_coracle_strip4.png"
    if boat_path.exists():
        sheet = pygame.image.load(str(boat_path)).convert_alpha()
        fw = sheet.get_width() // 4
        fh = sheet.get_height()
        for i in range(4):
            frame = sheet.subsurface((i * fw, 0, fw, fh)).copy()
            scaled = pygame.transform.scale(frame, (fw * 2, fh * 2))
            pygame.image.save(scaled, str(PROPS / f"boat_f{i}.png"))
        print(f"  [saved] boat_f0..f3.png ({fw*2}x{fh*2})")

    # 4. Pohon apel Sunnyside (pohon oak dengan apel merah matang)
    oak_frames = [PROPS / f"tree_oak_f{i}.png" for i in range(4)]
    if all(p.exists() for p in oak_frames):
        for i, p in enumerate(oak_frames):
            img = pygame.image.load(str(p)).convert_alpha()
            # Gambar apel merah di dedaunan
            apple_img = img.copy()
            w, h = apple_img.get_size()
            # Bintik apel merah
            apple_coords = [(w//2 - 14, 18), (w//2 + 10, 14), (w//2 - 6, 28),
                            (w//2 + 16, 26), (w//2 - 18, 34), (w//2 + 4, 38)]
            for ax, ay in apple_coords:
                if 0 <= ax < w - 4 and 0 <= ay < h - 4:
                    pygame.draw.circle(apple_img, (230, 48, 48), (ax, ay), 3)
                    apple_img.set_at((ax - 1, ay - 1), (255, 160, 160))
            pygame.image.save(apple_img, str(PROPS / f"tree_apple_f{i}.png"))
        print("  [saved] tree_apple_f0..f3.png")

    # 5. Sumur Sunnyside dari GM sprites
    well_dir = GM_SPRITES / "spr_deco_well"
    if well_dir.exists():
        pngs = [p for p in well_dir.glob("*.png") if not p.is_dir() and "layers" not in str(p)]
        if pngs:
            wimg = pygame.image.load(str(pngs[0])).convert_alpha()
            scaled = pygame.transform.scale(wimg, (wimg.get_width() * 2, wimg.get_height() * 2))
            pygame.image.save(scaled, str(PROPS / "well_f0.png"))
            print("  [saved] well_f0.png")

    # 6. Landasan tempa / anvil
    anvil_dir = GM_SPRITES / "spr_deco_anvil"
    if anvil_dir.exists():
        pngs = [p for p in anvil_dir.glob("*.png") if not p.is_dir() and "layers" not in str(p)]
        if pngs:
            aimg = pygame.image.load(str(pngs[0])).convert_alpha()
            scaled = pygame.transform.scale(aimg, (aimg.get_width() * 2, aimg.get_height() * 2))
            pygame.image.save(scaled, str(PROPS / "anvil_f0.png"))
            print("  [saved] anvil_f0.png")

    # 7. Palung makan hewan (trough)
    trough_dir = GM_SPRITES / "spr_deco_trough"
    if trough_dir.exists():
        pngs = [p for p in trough_dir.glob("*.png") if not p.is_dir() and "layers" not in str(p)]
        if pngs:
            timg = pygame.image.load(str(pngs[0])).convert_alpha()
            scaled = pygame.transform.scale(timg, (timg.get_width() * 2, timg.get_height() * 2))
            pygame.image.save(scaled, str(PROPS / "trough_f0.png"))
            print("  [saved] trough_f0.png")

    # 8. Asap cerobong rumah (5 frame)
    smoke_dir = GM_SPRITES / "chimneysmoke_01"
    if smoke_dir.exists():
        pngs = sorted([p for p in smoke_dir.glob("*.png") if not p.is_dir() and "layers" not in str(p)])[:5]
        for i, p in enumerate(pngs):
            simg = pygame.image.load(str(p)).convert_alpha()
            scaled = pygame.transform.scale(simg, (simg.get_width() * 2, simg.get_height() * 2))
            pygame.image.save(scaled, str(PROPS / f"smoke_f{i}.png"))
        if pngs:
            print("  [saved] smoke_f0..f4.png")

    # 9. Api unggun (campfire)
    camp_dir = GM_SPRITES / "spr_deco_campfire"
    if camp_dir.exists():
        pngs = [p for p in camp_dir.glob("*.png") if not p.is_dir() and "layers" not in str(p)]
        if pngs:
            cimg = pygame.image.load(str(pngs[0])).convert_alpha()
            scaled = pygame.transform.scale(cimg, (cimg.get_width() * 2, cimg.get_height() * 2))
            pygame.image.save(scaled, str(PROPS / "campfire_f0.png"))
            print("  [saved] campfire_f0.png")

    # 10. Patung kesatria batu (statue) dari Room1
    room_path = PACK / "Sunnyside_World_Gamemaker" / "rooms" / "Room1" / "Room1.yy"
    if room_path.exists():
        content = room_path.read_text(encoding="utf-8")
        tileset_img = pygame.image.load(str(TILESETS / "sunnyside_world.png")).convert_alpha()
        pattern = r'\"resourceType\":\"GMRTileLayer\"[^\}]*?\"name\":\"([^\"]+)\".*?\"SerialiseWidth\":(\d+),\"SerialiseHeight\":(\d+),\"TileCompressedData\":\[(.*?)\]'
        matches = re.findall(pattern, content, re.DOTALL)
        layer_dict = {m[0]: m for m in matches}
        W, H = 86, 48
        statue_surf = pygame.Surface((W * 16, H * 16), pygame.SRCALPHA)
        for lname in ['building', 'decoration_01', 'decoration_02']:
            if lname not in layer_dict: continue
            m = layer_dict[lname]
            lw, lh = int(m[1]), int(m[2])
            tiles = decompress([int(x.strip()) for x in m[3].split(',') if x.strip()])
            for idx, raw in enumerate(tiles):
                if raw == -2147483648 or raw == 0: continue
                tile_id = raw & 0x0FFFFFFF
                col = tile_id % 64
                row = tile_id // 64
                rect = pygame.Rect(col * 20 + 2, row * 20 + 2, 16, 16)
                if tileset_img.get_rect().contains(rect):
                    t_surf = tileset_img.subsurface(rect).copy()
                    gx, gy = idx % lw, idx // lw
                    statue_surf.blit(t_surf, (gx * 16, gy * 16))
        # Patung ada di sekitar (7, 5) di Room1
        sub_statue = statue_surf.subsurface((7 * 16, 5 * 16, 4 * 16, 5 * 16)).copy()
        bbox = sub_statue.get_bounding_rect()
        if bbox.w > 0 and bbox.h > 0:
            final_statue = sub_statue.subsurface(bbox).copy()
            scaled = pygame.transform.scale(final_statue, (final_statue.get_width() * 2, final_statue.get_height() * 2))
            pygame.image.save(scaled, str(PROPS / "statue_f0.png"))
            print("  [saved] statue_f0.png")

    # 11. Potongan batang pohon (tree stump & logs)
    stump_surf = pygame.Surface((32, 28), pygame.SRCALPHA)
    # Tunggul kayu dengan cincin usia pohon
    pygame.draw.ellipse(stump_surf, (82, 54, 32), (2, 8, 28, 18))
    pygame.draw.ellipse(stump_surf, (158, 114, 76), (4, 9, 24, 14))
    pygame.draw.ellipse(stump_surf, (186, 142, 100), (8, 11, 16, 10))
    stump_surf.set_at((15, 15), (108, 74, 46))
    pygame.image.save(stump_surf, str(PROPS / "tree_stump_f0.png"))

    log_surf = pygame.Surface((36, 20), pygame.SRCALPHA)
    pygame.draw.rect(log_surf, (88, 58, 36), (4, 4, 28, 12), border_radius=4)
    pygame.draw.rect(log_surf, (142, 98, 62), (6, 5, 24, 9))
    pygame.draw.ellipse(log_surf, (186, 142, 100), (2, 4, 8, 12))
    pygame.image.save(log_surf, str(PROPS / "log_f0.png"))
    print("  [saved] tree_stump_f0.png, log_f0.png")


def extract_ui():
    print("[extract] mengekstrak aset UI Sunnyside...")
    UI_SRC = PACK / "Sunnyside_World_Assets" / "UI"
    if not UI_SRC.exists():
        print(f"[extract] {UI_SRC} tidak ditemukan!")
        return

    # Salin sprite UI penting
    wanted_ui = [
        "sword.png", "itemdisc_01.png", "itemdisc_02.png",
        "label_left.png", "label_middle.png", "label_right.png",
        "expression_alerted.png", "expression_attack.png", "expression_chat.png", "expression_love.png",
    ]
    # Bar progress
    for color in ["red", "blue", "green"]:
        for i in range(7):
            wanted_ui.append(f"{color}bar_0{i}.png")
    # 9-slice box
    for prefix in ["dt_box_9slice", "w_box_9slice", "lt_box_9slice"]:
        for part in ["tl", "tc", "tr", "lc", "c", "rc", "bl", "bc", "br"]:
            wanted_ui.append(f"{prefix}_{part}.png")

    copied = 0
    for name in wanted_ui:
        src = UI_SRC / name
        if src.exists():
            img = pygame.image.load(str(src)).convert_alpha()
            pygame.image.save(img, str(UI_DIR / name))
            copied += 1
    print(f"  [saved] {copied} berkas UI ke {UI_DIR}")


def main():
    pygame.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    extract_houses()
    extract_props()
    extract_ui()
    print("[extract] Selesai!")


if __name__ == "__main__":
    main()
