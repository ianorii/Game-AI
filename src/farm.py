"""
farm.py - Sistem Ladang Bertahap & Pertanian Desa Sunnyside (Fase 1A)

Fitur:
  1. Petak Ladang (Crop Plots): Menggunakan tile tanah asli Sunnyside (soil_01 kering, soil_04 basah).
  2. 6 Tahap Tumbuh: _00 (benih) sampai _05 (matang siap panen).
  3. Aksi Bertani:
     - Plant: Tanam benih (membutuhkan seeds_radish/wheat di inventori).
     - Water: Siram petak untuk melipatgandakan kecepatan tumbuh (mengubah tanah ke soil_04).
     - Harvest: Panen hasil saat tahap 5 tercapai.
  4. Durasi Singkat: Konfigurasi waktu per tahap (default 10 detik, 5 detik jika disiram).
  5. Serialisasi: to_dict() dan from_dict().
"""

from typing import Dict, List, Optional, Tuple, Any
import pygame

import config
from asset_catalog import get_asset_catalog
from inventory import Inventory


class CropPlot:
    """Satu petak tanah ladang individual."""

    def __init__(self, x: int, y: int, plot_id: int):
        self.plot_id = plot_id
        self.x = int(x)
        self.y = int(y)
        self.crop_type: Optional[str] = None   # "radish" atau "wheat"
        self.stage: int = 0                    # 0..5 (5 = matang)
        self.growth_timer: float = 0.0
        self.base_stage_duration: float = getattr(config, "FARM_BASE_STAGE_DURATION", 5.0) # Detik per tahap
        self.is_watered: bool = False
        self.w = 32
        self.h = 32

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.w, self.h)

    @property
    def is_mature(self) -> bool:
        return self.crop_type is not None and self.stage >= 5

    def update(self, dt: float):
        if self.crop_type is None or self.stage >= 5:
            return

        # Kecepatan tumbuh 2x lebih cepat jika sudah disiram
        speed_mult = 2.0 if self.is_watered else 1.0
        self.growth_timer += dt * speed_mult

        if self.growth_timer >= self.base_stage_duration:
            self.growth_timer = 0.0
            self.stage = min(5, self.stage + 1)
            # Tanah kembali mengering setelah naik 1 tahap
            if self.stage < 5:
                self.is_watered = False

    def plant(self, crop_type: str, inventory: Inventory) -> Tuple[bool, str]:
        if self.crop_type is not None:
            return False, "Petak ladang ini sudah ditanami!"

        seed_id = f"seeds_{crop_type.lower()}"
        if not inventory.has_item(seed_id, 1):
            return False, f"Tidak memiliki {seed_id} di inventori tas!"

        inventory.remove_item(seed_id, 1)
        self.crop_type = crop_type.lower()
        self.stage = 0
        self.growth_timer = 0.0
        return True, f"Berhasil menanam {crop_type} pada petak #{self.plot_id + 1}!"

    def water(self) -> Tuple[bool, str]:
        if self.crop_type is None:
            return False, "Tidak ada tanaman di petak ini untuk disiram!"
        if self.is_watered:
            return False, "Tanah pada petak ini sudah basah disiram!"
        if self.is_mature:
            return False, "Tanaman sudah matang, siap dipanen!"

        self.is_watered = True
        return True, f"Petak #{self.plot_id + 1} telah disiram air segar (+100% kecepatan tumbuh)!"

    def harvest(self, inventory: Inventory) -> Tuple[bool, str]:
        if self.crop_type is None:
            return False, "Tidak ada tanaman di petak ini!"
        if self.stage < 5:
            return False, f"Tanaman belum matang (tahap {self.stage}/5)!"
        if inventory.is_full() and not inventory.has_item(self.crop_type, 1):
            return False, "Inventori tas hero penuh, tidak dapat menampung hasil panen!"

        crop = self.crop_type
        inventory.add_item(crop, 1)
        self.crop_type = None
        self.stage = 0
        self.growth_timer = 0.0
        self.is_watered = False
        return True, f"Berhasil memanen 1x {crop.capitalize()} dari petak #{self.plot_id + 1}!"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plot_id": self.plot_id,
            "x": self.x,
            "y": self.y,
            "crop_type": self.crop_type,
            "stage": self.stage,
            "growth_timer": self.growth_timer,
            "is_watered": self.is_watered,
        }

    def from_dict(self, data: Dict[str, Any]):
        self.crop_type = data.get("crop_type")
        self.stage = data.get("stage", 0)
        self.growth_timer = data.get("growth_timer", 0.0)
        self.is_watered = data.get("is_watered", False)


class FarmManager:
    """Mengelola petak-petak ladang pertanian di desa."""

    def __init__(self):
        # 6 petak ladang fungsional sejajar grid 32px di area ladang dekoratif barat laut (3 kolom x 2 baris)
        # Koordinat: x in [480, 512, 544], y in [384, 416]
        self.plots: List[CropPlot] = []
        plot_coords = [
            (480, 384), (512, 384), (544, 384),
            (480, 416), (512, 416), (544, 416),
        ]
        for i, (px, py) in enumerate(plot_coords):
            self.plots.append(CropPlot(px, py, i))

    def update(self, dt: float):
        for p in self.plots:
            p.update(dt)

    def get_plot_at(self, world_x: float, world_y: float) -> Optional[CropPlot]:
        for p in self.plots:
            if p.rect.collidepoint(world_x, world_y):
                return p
        return None

    def get_nearest_plot(self, px: float, py: float, max_dist: float = 48.0) -> Optional[CropPlot]:
        nearest = None
        min_d = max_dist
        for p in self.plots:
            cx = p.x + 16
            cy = p.y + 16
            dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
            if dist <= min_d:
                min_d = dist
                nearest = p
        return nearest

    def draw(self, screen: pygame.Surface, camera: Tuple[int, int],
             hero_pos: Optional[Tuple[float, float]] = None,
             debug_mode: bool = False):
        cat = get_asset_catalog()
        cam_x, cam_y = camera
        # Font min 14px terbaca jelas
        font_prompt = pygame.font.Font(None, 18)

        # Temukan satu petak terdekat dengan hero (hanya tampilkan 1 label dan 1 bar aktif)
        nearest_plot = None
        if hero_pos:
            nearest_plot = self.get_nearest_plot(hero_pos[0], hero_pos[1], max_dist=42.0)

        # Gambar batas ladang keliling HANYA pada mode debug F1
        if debug_mode:
            farm_screen_rect = pygame.Rect(474 - cam_x, 378 - cam_y, 108, 76)
            pygame.draw.rect(screen, (85, 55, 30), farm_screen_rect, width=2, border_radius=4)

        for p in self.plots:
            sx = int(p.x - cam_x)
            sy = int(p.y - cam_y)
            if -32 <= sx <= 1024 + 32 and -32 <= sy <= 768 + 32:
                # 1. Gambar tanah (soil_01 untuk tanah gembur kering, soil_04 untuk basah tersiram)
                soil_var = 4 if p.is_watered else 1
                soil_img = cat.get_soil(soil_var, scale=2)
                screen.blit(soil_img, (sx, sy))

                # 2. Gambar tanaman sesuai tahap tumbuh
                if p.crop_type:
                    crop_img = cat.get_crop(p.crop_type, stage=p.stage, scale=2)
                    screen.blit(crop_img, (sx, sy))

                # Debug box hanya jika F1 aktif
                if debug_mode:
                    pygame.draw.rect(screen, (40, 40, 40), (sx, sy, 32, 32), 1)

                # 3. Bar progres dan Label prompt HANYA untuk satu petak terdekat
                if p == nearest_plot:
                    # Progress bar kecil (28x4 px) di atas petak/kepala hero
                    if p.crop_type:
                        bar_w = 28
                        bar_h = 4
                        bar_x = sx + (32 - bar_w) // 2
                        bar_y = sy - 10
                        pct = (p.stage + p.growth_timer / p.base_stage_duration) / 5.0
                        pct = max(0.0, min(1.0, pct))

                        pygame.draw.rect(screen, (20, 20, 25), (bar_x, bar_y, bar_w, bar_h))
                        fill_col = config.GOLD if p.is_mature else ((80, 200, 240) if p.is_watered else (100, 220, 100))
                        fill_w = int((bar_w - 2) * pct)
                        if fill_w > 0:
                            pygame.draw.rect(screen, fill_col, (bar_x + 1, bar_y + 1, fill_w, bar_h - 2))
                        pygame.draw.rect(screen, (60, 60, 70), (bar_x, bar_y, bar_w, bar_h), 1)

                    # Prompt Tag
                    if p.is_mature:
                        lbl_text = "PANEN [E]"
                        lbl_col = config.GOLD
                    elif p.crop_type is None:
                        lbl_text = "TANAM [E]"
                        lbl_col = config.WHITE
                    elif not p.is_watered:
                        lbl_text = "SIRAM [E]"
                        lbl_col = (120, 210, 255)
                    else:
                        lbl_text = "TUMBUH..."
                        lbl_col = (180, 230, 180)

                    lbl = font_prompt.render(lbl_text, True, lbl_col)
                    tag_w = lbl.get_width() + 8
                    tag_h = lbl.get_height() + 2
                    tag_y = sy - 26 if p.crop_type else sy - 18
                    tag_rect = pygame.Rect(sx + (32 - tag_w) // 2, tag_y, tag_w, tag_h)
                    pygame.draw.rect(screen, (20, 20, 30, 220), tag_rect, border_radius=3)
                    pygame.draw.rect(screen, lbl_col, tag_rect, 1, border_radius=3)
                    screen.blit(lbl, (tag_rect.x + 4, tag_rect.y + 1))

    def to_dict(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.plots]

    def from_dict(self, data: List[Dict[str, Any]]):
        for i, p_data in enumerate(data[:len(self.plots)]):
            self.plots[i].from_dict(p_data)
