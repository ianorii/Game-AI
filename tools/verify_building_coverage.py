#!/usr/bin/env python3
"""
verify_building_coverage.py
Menghitung persentase piksel opak pada pita dasar tembok (40% bawah sprite)
yang berada di dalam gabungan footprint untuk seluruh 22 bangunan.
Juga menghasilkan contact sheet dan gambar per bangunan di docs/figures/footprints/.
"""
import os
import re
import json
import pygame

os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()

GM = "assets/sunnyside_world/Sunnyside_World_Gamemaker"
room_file = os.path.join(GM, "rooms/Room1/Room1.yy")
with open(room_file, "r", encoding="utf-8") as f:
    content = f.read()

tileset_path = "assets/sunnyside_world/Tileset/sunnyside_world.png"
tileset = pygame.image.load(tileset_path)

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
            out.extend(data_list[i:i + count])
            i += count
    return out

pattern = r'\"resourceType\":\"GMRTileLayer\"[^\}]*?\"name\":\"([^\"]+)\".*?\"SerialiseWidth\":(\d+),\"SerialiseHeight\":(\d+),\"TileCompressedData\":\[(.*?)\]'
matches = re.findall(pattern, content, re.DOTALL)
layer_dict = {m[0]: m for m in matches}

W_TILES = 86
H_TILES = 48

def get_layer(name):
    if name not in layer_dict:
        return [0] * (W_TILES * H_TILES)
    m = layer_dict[name]
    nums = [int(x.strip()) for x in m[3].split(",") if x.strip()]
    return decompress(nums)

# Render building + walls + deco3 pada kanvas transparan 1x (1376 x 768)
surf_1x = pygame.Surface((W_TILES * 16, H_TILES * 16), pygame.SRCALPHA)
surf_1x.fill((0, 0, 0, 0))

for lname in ["walls", "building", "decoration_03"]:
    tiles = get_layer(lname)
    for idx, raw in enumerate(tiles):
        if raw == -2147483648 or raw == 0:
            continue
        gx = idx % W_TILES
        gy = idx // W_TILES
        if (gx >= 70 and gy >= 38) or (gx <= 6 and 20 <= gy <= 36):
            continue
        flip_x = bool(raw & 0x10000000)
        flip_y = bool(raw & 0x20000000)
        tid = raw & 0x0FFFFFFF
        col, row = tid % 64, tid // 64
        rect = pygame.Rect(col * 20 + 2, row * 20 + 2, 16, 16)
        if tileset.get_rect().contains(rect):
            t_surf = tileset.subsurface(rect)
            if flip_x or flip_y:
                t_surf = pygame.transform.flip(t_surf, flip_x, flip_y)
            surf_1x.blit(t_surf, (gx * 16, gy * 16))

# Skala 2x ke resolusi peta game HD (2752 x 1536)
surf_2x = pygame.transform.scale(surf_1x, (W_TILES * 32, H_TILES * 32))

with open("assets/maps/collision.json") as f:
    coll_data = json.load(f)
houses = [item for item in coll_data if item.get("type") in ("house", "building")]

os.makedirs("docs/figures/footprints", exist_ok=True)

print(f"====================================================================================================")
print(f" EVALUASI CAKUPAN FOOTPRINT PADA PITA DASAR TEMBOK & METRIK PRESISI (WASTED <= 15%)")
print(f"====================================================================================================")
print(f"{'No':<3} | {'Nama Bangunan':<18} | {'Pos (2x)':<14} | {'Ukuran (2x)':<12} | {'Opaque':<8} | {'Covered':<8} | {'Coverage %':<10} | {'Wasted %':<9} | {'Status'}")
print(f"-" * 105)

results = []
building_images = []

for idx, h in enumerate(houses):
    bx = h["x"] * 2
    by = h["y"] * 2
    bw = h["w"] * 2
    bh = h["h"] * 2
    b_name = h["name"]
    fps = [pygame.Rect(fp["x"], fp["y"], fp["w"], fp["h"]) for fp in h.get("footprints", [])]

    # Ambil sub-surface bangunan
    b_surf = surf_2x.subsurface(pygame.Rect(bx, by, bw, bh)).copy()

    # Pita dasar tembok (40% bawah bangunan)
    split_y = int(bh * 0.60)
    door_row_y = bh - 24

    # Hitung metrik presisi footprint
    fp_pixels = set()
    for fp in fps:
        for y in range(fp.top, fp.bottom):
            for x in range(fp.left, fp.right):
                fp_pixels.add((x, y))

    fp_area = len(fp_pixels)
    if fp_area == 0:
        pct_wall = 100.0
        pct_all = 100.0
        wasted_pct = 0.0
        status = "LULUS (Phantom 0/0)"
        opaque_wall = 0
        covered_wall = 0
    else:
        empty_in_fp = sum(1 for (x, y) in fp_pixels if (x < 0 or x >= surf_2x.get_width() or y < 0 or y >= surf_2x.get_height() or surf_2x.get_at((x, y))[3] <= 20))
        wasted_pct = (empty_in_fp / fp_area) * 100.0

        opaque_all = 0
        covered_all = 0
        opaque_wall = 0
        covered_wall = 0

        for py in range(split_y, bh):
            world_y = by + py
            is_door_row = (py >= door_row_y)

            for px in range(bw):
                world_x = bx + px
                alpha = b_surf.get_at((px, py))[3]
                if alpha > 20:  # Opaque pixel
                    opaque_all += 1
                    in_fp = any(fp.collidepoint(world_x, world_y) for fp in fps)
                    if in_fp:
                        covered_all += 1

                    if not is_door_row:
                        opaque_wall += 1
                        if in_fp:
                            covered_wall += 1

        pct_all = (covered_all / opaque_all * 100.0) if opaque_all > 0 else 100.0
        pct_wall = (covered_wall / opaque_wall * 100.0) if opaque_wall > 0 else 100.0
        is_ok = (pct_wall >= 95.0 and wasted_pct <= 15.0)
        status = "LULUS" if is_ok else "DI BAWAH TARGET"

    results.append({
        "no": idx + 1,
        "name": b_name,
        "pos": f"({bx}, {by})",
        "size": f"{bw}x{bh}",
        "opaque": opaque_wall,
        "covered": covered_wall,
        "coverage": pct_wall,
        "coverage_raw": pct_all,
        "wasted_pct": wasted_pct,
        "fp_area": fp_area,
        "status": status,
        "footprints": len(fps)
    })
    print(f"{idx+1:<3} | {b_name:<18} | {f'({bx},{by})':<14} | {f'{bw}x{bh}':<12} | {opaque_wall:<8} | {covered_wall:<8} | {pct_wall:>8.2f} % | {wasted_pct:>7.2f} % | {status}")

    # Buat visualisasi gambar overlay F1 di atas sprite bangunan
    vis_w = bw + 40
    vis_h = bh + 60
    vis = pygame.Surface((vis_w, vis_h), pygame.SRCALPHA)
    vis.fill((28, 32, 42, 255))

    # Judul / nama bangunan di atas
    font = pygame.font.Font(None, 20)
    title = font.render(f"#{idx+1:02d} {b_name} (Cov: {pct_wall:.1f}%, Waste: {wasted_pct:.1f}%)", True, (240, 240, 245))
    vis.blit(title, (12, 10))

    # Gambar sprite bangunan
    vis.blit(b_surf, (20, 36))

    # Tumpuk footprint F1 (merah transparan + border merah)
    for fp in fps:
        local_x = fp.x - bx + 20
        local_y = fp.y - by + 36
        fp_surf = pygame.Surface((fp.w, fp.h), pygame.SRCALPHA)
        fp_surf.fill((220, 40, 40, 110))
        pygame.draw.rect(fp_surf, (255, 60, 60), (0, 0, fp.w, fp.h), 2)
        vis.blit(fp_surf, (local_x, local_y))

    # Simpan gambar individu
    single_path = f"docs/figures/footprints/{b_name}.png"
    pygame.image.save(vis, single_path)
    building_images.append((b_name, vis))

# Buat Contact Sheet gambar seluruh 22 bangunan
# Grid 4 kolom x 6 baris
cols = 4
rows = 6
cell_w = 400
cell_h = 320
sheet_w = cols * cell_w
sheet_h = rows * cell_h
sheet = pygame.Surface((sheet_w, sheet_h))
sheet.fill((20, 22, 30))

font_sheet_title = pygame.font.Font(None, 28)
font_lbl = pygame.font.Font(None, 20)

for i, (b_name, img) in enumerate(building_images):
    c = i % cols
    r = i // cols
    dest_x = c * cell_w + 10
    dest_y = r * cell_h + 10

    # Draw border slot
    pygame.draw.rect(sheet, (45, 50, 65), (c * cell_w + 4, r * cell_h + 4, cell_w - 8, cell_h - 8), 1, border_radius=4)
    # Blit building visualization
    scaled_img = img
    if img.get_width() > cell_w - 20 or img.get_height() > cell_h - 20:
        scale_fac = min((cell_w - 24) / img.get_width(), (cell_h - 24) / img.get_height())
        nw = int(img.get_width() * scale_fac)
        nh = int(img.get_height() * scale_fac)
        scaled_img = pygame.transform.smoothscale(img, (nw, nh))

    off_x = dest_x + (cell_w - 20 - scaled_img.get_width()) // 2
    off_y = dest_y + (cell_h - 20 - scaled_img.get_height()) // 2
    sheet.blit(scaled_img, (off_x, off_y))

sheet_path = "docs/figures/footprints/contact_sheet_footprints.png"
pygame.image.save(sheet, sheet_path)
print(f"-" * 95)
print(f"Berhasil menyimpan contact sheet ke: {sheet_path}")
print(f"Berhasil menyimpan 22 visualisasi individual ke: docs/figures/footprints/*.png")

below_target = [r for r in results if r["coverage"] < 95.0 or r["wasted_pct"] > 15.0]
avg_cov = sum(r["coverage"] for r in results) / len(results)
avg_waste = sum(r["wasted_pct"] for r in results) / len(results)

print(f"\nRingkasan Kepatuhan (Target: Coverage >= 95% & Wasted Area <= 15%):")
print(f"  Total Bangunan       : {len(results)}")
print(f"  Rata-rata Coverage  : {avg_cov:.2f}%")
print(f"  Rata-rata Wasted    : {avg_waste:.2f}%")
print(f"  Mencapai Target     : {len(results) - len(below_target)} bangunan")
print(f"  Di Bawah Target     : {len(below_target)} bangunan")
if below_target:
    print(f"  Daftar di bawah target:")
    for b in below_target:
        print(f"    - {b['name']}: Cov={b['coverage']:.2f}%, Wasted={b['wasted_pct']:.2f}%")
else:
    print(f"  SEMUA BANGUNAN MEMENUHI TARGET (Coverage >= 95% & Wasted <= 15%)!")
