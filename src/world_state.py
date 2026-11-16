"""
world_state.py - Pengelola State Dunia Tunggal (Fase 1A Minimal Game System)

Menyatukan seluruh subsistem logika gameplay yang dipakai bersama oleh:
  1. Player manual (kontrol keyboard & [E] interaksi)
  2. Automated Expedition Planner (STRIPS classical planning)
  3. HTN Planner (NPC desa)

Fitur Terpusat:
  - Inventori (12 slot) & Dompet Koin
  - Toko Desa (Beli & Jual)
  - Ladang Pertanian (6 petak, 6 tahap tumbuh)
  - Crafting Workshop (Potion & Kunci Gerbang)
  - Gerbang Berkunci Menuju Boss (Dynamic obstacle collision integration)
  - Sumber Daya Alam (Ayam, Sapi, Pancingan, Pohon, Tambang)
  - Rest di Rumah (Pemulihan HP Penuh)
  - Save/Load Atomik (.bak) dengan Validasi Hash/Dimensi
"""

import os
import json
import time
import math
from typing import Dict, List, Optional, Tuple, Any
import pygame

import config
from asset_catalog import get_asset_catalog
from inventory import Inventory
from economy import Shop
from farm import FarmManager


class LockedGate:
    """
    Gerbang kayu & pilar batu Sunnyside berkunci di koridor chokepoint tunggal.
    Lebar 96px (persis 3 tile: x=2368..2464 / 2352..2448), tinggi tapak 32-48px.
    Berdiri 100% di atas tanah padat (walkable mask = 1 saat terbuka, 0% di air).
    Dua sprite Sunnyside:
      - Tertutup: Daun pintu kayu ganda solid rapat, berpalang besi horizontal & engsel,
                  gembok emas di kait tengah, menutup penuh lorong.
      - Terbuka : Daun pintu terlipat rapi ke pilar samping, lorong tengah terbuka bebas
                  dan tembus pandang ke tanah di bawahnya (selisih > 1000 piksel).
    Mendukung y-sort depth sorting bersama entitas lainnya.
    """

    def __init__(self, x: int = 2496, y: int = 512, w: int = 96, h: int = 32):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.is_open: bool = False
        self.open_progress: float = 0.0  # 0.0 (tertutup) -> 1.0 (terbuka)
        self.collision_rect = pygame.Rect(self.x, self.y, self.w, self.h)
        # Visual sprite digambar sedikit lebih tinggi agar pilar & lengkung batu menjulang
        self.visual_y_offset = 32
        self.visual_pos = (self.x, self.y - self.visual_y_offset)
        self.surf_closed = None
        self.surf_open = None
        self._init_sprites()

    @property
    def sort_y(self) -> float:
        """Kunci kedalaman rendering y-sort (diukur di dasar tapak gerbang)."""
        return float(self.y + self.h)

    def collidepoint(self, px: float, py: float) -> bool:
        """Pemeriksaan tabrakan titik terhadap gerbang berkunci."""
        if self.is_open:
            return False
        return self.collision_rect.collidepoint(px, py)

    def _init_sprites(self):
        """Membuat dua sprite otentik Sunnyside yang terbaca sangat jelas: Tertutup dan Terbuka."""
        sw = self.w
        sh = self.h + self.visual_y_offset + 8  # 96 x 72 px kanvas
        self.surf_closed = pygame.Surface((sw, sh), pygame.SRCALPHA)
        self.surf_open = pygame.Surface((sw, sh), pygame.SRCALPHA)

        # Palet resmi Sunnyside World
        C_STONE_OUTLINE = (28, 26, 36)
        C_STONE_DARK    = (50, 48, 62)
        C_STONE_MID     = (82, 80, 98)
        C_STONE_LIGHT   = (122, 120, 142)
        C_STONE_TOP     = (158, 156, 178)

        C_WOOD_OUTLINE  = (40, 24, 16)
        C_WOOD_DARK     = (78, 48, 30)
        C_WOOD_MID      = (128, 80, 50)
        C_WOOD_LIGHT    = (168, 110, 70)

        C_IRON_DARK     = (30, 32, 40)
        C_IRON_MID      = (65, 70, 82)
        C_IRON_LIGHT    = (120, 125, 140)

        C_GOLD_DARK     = (150, 100, 15)
        C_GOLD_MID      = (220, 165, 35)
        C_GOLD_LIGHT    = (255, 225, 90)

        for surf, is_op in [(self.surf_closed, False), (self.surf_open, True)]:
            # 1. Pilar Kiri (x=2..22, y=10..68)
            pygame.draw.rect(surf, C_STONE_OUTLINE, (2, 10, 20, 58), border_radius=3)
            pygame.draw.rect(surf, C_STONE_DARK, (4, 12, 16, 54), border_radius=2)
            pygame.draw.rect(surf, C_STONE_MID, (6, 14, 12, 50))
            # Capital block / mahkota atas pilar kiri
            pygame.draw.rect(surf, C_STONE_OUTLINE, (0, 8, 24, 8), border_radius=2)
            pygame.draw.rect(surf, C_STONE_TOP, (2, 9, 20, 3))
            pygame.draw.rect(surf, C_STONE_MID, (2, 12, 20, 3))
            # Garis batu bata pilar kiri
            for py in [24, 38, 52]:
                pygame.draw.line(surf, C_STONE_OUTLINE, (4, py), (19, py), 1)
                pygame.draw.line(surf, C_STONE_LIGHT, (4, py + 1), (19, py + 1), 1)

            # 2. Pilar Kanan (x=74..94, y=10..68)
            pygame.draw.rect(surf, C_STONE_OUTLINE, (74, 10, 20, 58), border_radius=3)
            pygame.draw.rect(surf, C_STONE_DARK, (76, 12, 16, 54), border_radius=2)
            pygame.draw.rect(surf, C_STONE_MID, (78, 14, 12, 50))
            # Capital block / mahkota atas pilar kanan
            pygame.draw.rect(surf, C_STONE_OUTLINE, (72, 8, 24, 8), border_radius=2)
            pygame.draw.rect(surf, C_STONE_TOP, (74, 9, 20, 3))
            pygame.draw.rect(surf, C_STONE_MID, (74, 12, 20, 3))
            # Garis batu bata pilar kanan
            for py in [24, 38, 52]:
                pygame.draw.line(surf, C_STONE_OUTLINE, (76, py), (91, py), 1)
                pygame.draw.line(surf, C_STONE_LIGHT, (76, py + 1), (91, py + 1), 1)

            # 3. Lengkung Batu Atas / Stone Arch Lintel (x=18..78, y=4..18)
            pygame.draw.rect(surf, C_STONE_OUTLINE, (18, 4, 60, 14), border_radius=4)
            pygame.draw.rect(surf, C_STONE_DARK, (20, 6, 56, 10), border_radius=2)
            pygame.draw.rect(surf, C_STONE_TOP, (22, 6, 52, 3))
            pygame.draw.rect(surf, C_STONE_MID, (22, 9, 52, 6))
            # Keystone di tengah atas arch (x=42..54, y=2..18)
            pygame.draw.polygon(surf, C_STONE_OUTLINE, [(44, 2), (52, 2), (55, 18), (41, 18)])
            pygame.draw.polygon(surf, C_STONE_TOP, [(45, 3), (51, 3), (53, 7), (43, 7)])
            pygame.draw.polygon(surf, C_STONE_MID, [(43, 7), (53, 7), (54, 17), (42, 17)])

            # 4. Daun Pintu Kayu (Wooden Gate Leaves)
            if not is_op:
                # TERTUTUP: Daun pintu ganda kayu oak solid (x=22..74, y=20..68)
                # Daun pintu kiri
                pygame.draw.rect(surf, C_WOOD_OUTLINE, (22, 20, 26, 48))
                pygame.draw.rect(surf, C_WOOD_MID, (24, 22, 22, 44))
                for px in [28, 34, 40]:
                    pygame.draw.line(surf, C_WOOD_OUTLINE, (px, 22), (px, 65), 1)
                    pygame.draw.line(surf, C_WOOD_LIGHT, (px + 1, 22), (px + 1, 65), 1)

                # Daun pintu kanan
                pygame.draw.rect(surf, C_WOOD_OUTLINE, (48, 20, 26, 48))
                pygame.draw.rect(surf, C_WOOD_MID, (50, 22, 22, 44))
                for px in [54, 60, 66]:
                    pygame.draw.line(surf, C_WOOD_OUTLINE, (px, 22), (px, 65), 1)
                    pygame.draw.line(surf, C_WOOD_LIGHT, (px + 1, 22), (px + 1, 65), 1)

                # Celah tengah pintu
                pygame.draw.line(surf, C_WOOD_OUTLINE, (48, 20), (48, 67), 2)

                # Engsel besi di tiang pilar kiri & kanan
                for hy in [28, 56]:
                    pygame.draw.rect(surf, C_IRON_DARK, (18, hy, 12, 5), border_radius=1)
                    pygame.draw.rect(surf, C_IRON_LIGHT, (19, hy + 1, 10, 2))
                    pygame.draw.circle(surf, (200, 205, 220), (20, hy + 2), 1)

                    pygame.draw.rect(surf, C_IRON_DARK, (66, hy, 12, 5), border_radius=1)
                    pygame.draw.rect(surf, C_IRON_LIGHT, (67, hy + 1, 10, 2))
                    pygame.draw.circle(surf, (200, 205, 220), (76, hy + 2), 1)

                # Palang besi penguat horizontal
                for by in [34, 52]:
                    pygame.draw.rect(surf, C_IRON_DARK, (23, by, 50, 5))
                    pygame.draw.rect(surf, C_IRON_MID, (24, by + 1, 48, 3))
                    pygame.draw.line(surf, C_IRON_LIGHT, (24, by + 1), (71, by + 1), 1)
                    for bx in [26, 36, 60, 70]:
                        pygame.draw.circle(surf, (220, 225, 240), (bx, by + 2), 1)

                # Palang Pengunci & Gembok Emas di kait tengah
                pygame.draw.rect(surf, C_IRON_DARK, (42, 41, 12, 6), border_radius=1)
                pygame.draw.rect(surf, C_IRON_LIGHT, (43, 42, 10, 2))
                pygame.draw.arc(surf, (190, 195, 210), (45, 43, 6, 7), 0, 3.1415, 2)
                pygame.draw.rect(surf, C_GOLD_DARK, (44, 47, 8, 8), border_radius=2)
                pygame.draw.rect(surf, C_GOLD_MID, (45, 48, 6, 6))
                pygame.draw.rect(surf, C_GOLD_LIGHT, (45, 48, 2, 2))
                pygame.draw.circle(surf, (30, 20, 5), (48, 51), 1)

            else:
                # TERBUKA: Daun pintu kayu terlipat lebar ke sisi pilar batu
                # Daun kiri terlipat
                pygame.draw.polygon(surf, C_WOOD_OUTLINE, [(18, 20), (26, 23), (26, 65), (18, 68)])
                pygame.draw.polygon(surf, C_WOOD_MID, [(19, 21), (25, 24), (25, 64), (19, 67)])
                pygame.draw.line(surf, C_WOOD_LIGHT, (20, 22), (20, 66), 2)
                pygame.draw.rect(surf, C_IRON_DARK, (16, 28, 6, 4))
                pygame.draw.rect(surf, C_IRON_DARK, (16, 56, 6, 4))

                # Daun kanan terlipat
                pygame.draw.polygon(surf, C_WOOD_OUTLINE, [(78, 20), (70, 23), (70, 65), (78, 68)])
                pygame.draw.polygon(surf, C_WOOD_MID, [(77, 21), (71, 24), (71, 64), (77, 67)])
                pygame.draw.line(surf, C_WOOD_LIGHT, (76, 22), (76, 66), 2)
                pygame.draw.rect(surf, C_IRON_DARK, (74, 28, 6, 4))
                pygame.draw.rect(surf, C_IRON_DARK, (74, 56, 6, 4))

                # Garis ambang batu dasar di tanah (y=64..66)
                pygame.draw.line(surf, C_STONE_DARK, (26, 65), (70, 65), 2)
                pygame.draw.line(surf, C_STONE_LIGHT, (26, 66), (70, 66), 1)



    def unlock(self, inventory: Inventory) -> Tuple[bool, str]:
        if self.is_open:
            return False, "Segel Skeleton Overlord sudah terbuka!"
        has_key = inventory.has_item("key", 1) or inventory.has_item("gate_key", 1)
        if not has_key:
            return False, "Skeleton Overlord tersegel! Butuh 'Kunci Segel Bos' (1 Kayu + 1 Batu di Bengkel) untuk membukanya."

        if inventory.has_item("key", 1):
            inventory.remove_item("key", 1)
        elif inventory.has_item("gate_key", 1):
            inventory.remove_item("gate_key", 1)
        self.is_open = True
        self.open_progress = 1.0
        return True, "Kunci Segel digunakan... KLIK! Segel Skeleton Overlord hancur!"

    def update(self, dt: float):
        if self.is_open and self.open_progress < 1.0:
            self.open_progress = min(1.0, self.open_progress + dt * 2.5)

    def get_obstacle_rect(self) -> Optional[pygame.Rect]:
        """Mengembalikan obstacle rect jika tertutup, None jika terbuka."""
        return None if self.is_open else self.collision_rect

    def draw(self, screen: pygame.Surface, camera: Tuple[int, int],
             hero_pos: Optional[Tuple[float, float]] = None, *args, **kwargs):
        cam_x, cam_y = camera
        draw_x = int(self.x - cam_x)
        draw_y = int(self.y - self.visual_y_offset - cam_y)

        # Culling di luar layar
        if not (-self.w <= draw_x <= 1024 + 64 and -64 <= draw_y <= 768 + 64):
            return

        if self.surf_closed is None or self.surf_open is None:
            self._init_sprites()

        active_surf = self.surf_open if self.is_open else self.surf_closed
        screen.blit(active_surf, (draw_x, draw_y))


class WorldState:
    """Kontainer utama seluruh state dunia yang terpisah dari rendering."""

    def __init__(self, seed: int = 42, starting_coins: Optional[int] = None):
        self.seed = seed
        self.coins = getattr(config, "STARTING_COINS", 20) if starting_coins is None else starting_coins
        self.inventory = Inventory(max_slots=12)
        self.shop = Shop()
        self.farm = FarmManager()
        self.gate = LockedGate()

        # Cooldown timer untuk interaksi sumber daya alam
        self.cooldowns: Dict[str, float] = {
            "chicken_egg": 0.0,
            "cow_milk": 0.0,
            "fishing": 0.0,
            "tree_wood": 0.0,
            "rock_mining": 0.0,
        }

        # Starter items hero Game Baru: HANYA Pedang Biasa & Jubah Kain (tidak ada bahan/benih/botol)
        self.inventory.add_item("Pedang Biasa", 1)
        self.inventory.add_item("Kain", 1)

        # Multi-Armed Bandit (Explore vs Exploit) Engine untuk 5 Spot Muara
        from decision.bandit import BanditDirector
        self.bandit_director = BanditDirector(preset_key="REALISTIC", seed=self.seed)

    def update(self, dt: float):
        """Update waktu pada seluruh komponen dunia."""
        self.farm.update(dt)
        self.gate.update(dt)
        for k in self.cooldowns:
            if self.cooldowns[k] > 0.0:
                self.cooldowns[k] = max(0.0, self.cooldowns[k] - dt)

    # ------------------------------------------------------------------ AKSI CRAFTING
    def craft_potion(self) -> Tuple[bool, str]:
        """Meracik Health Potion: 1 lobak (radish) + 1 botol kosong (bottle_empty)."""
        if not self.inventory.has_item("radish", 1):
            return False, "Bahan kurang! Butuh 1x Lobak (Radish)."
        if not self.inventory.has_item("bottle_empty", 1):
            return False, "Bahan kurang! Butuh 1x Botol Kosong (Bottle Empty)."

        self.inventory.remove_item("radish", 1)
        self.inventory.remove_item("bottle_empty", 1)
        self.inventory.add_item("potion_red", 1)
        return True, "Berhasil meracik 1x Health Potion di bengkel!"

    def craft_gate_key(self) -> Tuple[bool, str]:
        """Menempa Kunci Segel Bos: 1 kayu (wood) + 1 batu (rock)."""
        if not self.inventory.has_item("wood", 1):
            return False, "Bahan kurang! Butuh 1x Kayu (Wood)."
        if not self.inventory.has_item("rock", 1):
            return False, "Bahan kurang! Butuh 1x Batu (Rock)."

        self.inventory.remove_item("wood", 1)
        self.inventory.remove_item("rock", 1)
        self.inventory.add_item("key", 1)
        self.inventory.add_item("gate_key", 1)
        return True, "Berhasil menempa 1x Kunci Segel Bos di bengkel!"

    # ------------------------------------------------------------------ AKSI SUMBER DAYA
    def collect_egg(self) -> Tuple[bool, str]:
        if self.cooldowns["chicken_egg"] > 0:
            return False, f"Ayam sedang bertelur... tunggu {int(self.cooldowns['chicken_egg'])}s!"
        if self.inventory.is_full() and not self.inventory.has_item("egg", 1):
            return False, "Inventori tas hero penuh!"

        self.inventory.add_item("egg", 1)
        self.cooldowns["chicken_egg"] = 15.0
        return True, "Berhasil mengambil 1x Telur segar dari kandang ayam!"

    def collect_milk(self) -> Tuple[bool, str]:
        if self.cooldowns["cow_milk"] > 0:
            return False, f"Sapi sedang merumput... tunggu {int(self.cooldowns['cow_milk'])}s!"
        if self.inventory.is_full() and not self.inventory.has_item("milk", 1):
            return False, "Inventori tas hero penuh!"

        self.inventory.add_item("milk", 1)
        self.cooldowns["cow_milk"] = 15.0
        return True, "Berhasil memerah 1x Susu segar di padang rumput!"

    def fish(self, spot_id: Optional[int] = None) -> Tuple[bool, str]:
        if self.cooldowns["fishing"] > 0:
            return False, f"Menunggu ikan menyambar umpan... ({int(self.cooldowns['fishing'])}s)"
        if self.inventory.is_full() and not self.inventory.has_item("fish", 1):
            return False, "Inventori tas hero penuh!"

        is_rare = False
        if hasattr(self, "bandit_director") and self.bandit_director:
            sid = spot_id if spot_id is not None else 1
            is_rare, _ = self.bandit_director.resolve_cast(sid)

        self.inventory.add_item("fish", 1)
        if is_rare and not self.inventory.is_full():
            self.inventory.add_item("rare_fish", 1)

        self.cooldowns["fishing"] = 10.0
        if is_rare:
            return True, "JACKPOT EMAS! Berhasil memancing 1x Ikan Segar + 1x Ikan Emas Langka (Rare Fish)!"
        return True, "STRIKE! Berhasil memancing 1x Ikan segar dari sungai!"

    def chop_wood(self) -> Tuple[bool, str]:
        if self.cooldowns["tree_wood"] > 0:
            return False, f"Pohon sedang bertunas kembali... ({int(self.cooldowns['tree_wood'])}s)"
        if self.inventory.is_full() and not self.inventory.has_item("wood", 2):
            return False, "Inventori tas hero penuh!"

        self.inventory.add_item("wood", 2)
        self.cooldowns["tree_wood"] = 15.0
        return True, "KRAKK! Berhasil menebang 2x Kayu (Wood) dari pohon desa!"

    def mine_rock(self) -> Tuple[bool, str]:
        if self.cooldowns["rock_mining"] > 0:
            return False, f"Vena batu sedang memadat kembali... ({int(self.cooldowns['rock_mining'])}s)"
        if self.inventory.is_full() and not self.inventory.has_item("rock", 2):
            return False, "Inventori tas hero penuh!"

        self.inventory.add_item("rock", 2)
        self.cooldowns["rock_mining"] = 15.0
        return True, "KLANG! Berhasil menambang 2x Batu (Rock) dari tebing reruntuhan!"

    # ------------------------------------------------------------------ AKSI REST
    def rest_hero(self, hero) -> Tuple[bool, str]:
        """Istirahat di rumah untuk memulihkan HP hero ke 100% penuh."""
        if hero.hp >= hero.max_hp:
            return False, "Hero dalam kondisi prima, HP sudah penuh (100/100)!"

        hero.hp = hero.max_hp
        return True, "Hero tidur pulas di ranjang rumah... HP pulih penuh (100/100)!"

    # ------------------------------------------------------------------ SAVE / LOAD ATOMIK
    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "coins": self.coins,
            "inventory": self.inventory.to_dict(),
            "shop": self.shop.to_dict(),
            "farm": self.farm.to_dict(),
            "gate_open": self.gate.is_open,
            "cooldowns": dict(self.cooldowns),
            "timestamp": time.time(),
        }

    def from_dict(self, data: Dict[str, Any]):
        self.coins = data.get("coins", 50)
        self.inventory.from_dict(data.get("inventory", []))
        self.shop.from_dict(data.get("shop", {}))
        self.farm.from_dict(data.get("farm", []))
        self.gate.is_open = data.get("gate_open", False)
        self.cooldowns = dict(data.get("cooldowns", {}))

    def save_game(self, filepath: str = "data/savegame.json") -> bool:
        """Penyimpanan atomik dengan backup .bak."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        bak_path = filepath + ".bak"
        tmp_path = filepath + ".tmp"

        try:
            payload = self.to_dict()
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            if os.path.exists(filepath):
                if os.path.exists(bak_path):
                    os.remove(bak_path)
                os.rename(filepath, bak_path)

            os.rename(tmp_path, filepath)
            return True
        except Exception as e:
            print(f"[ERROR SAVEGAME] Gagal menyimpan game: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return False

    def load_game(self, filepath: str = "data/savegame.json") -> bool:
        """Memuat savegame dengan pemulihan otomatis dari .bak jika file utama korup."""
        target = filepath
        if not os.path.isfile(target):
            bak = filepath + ".bak"
            if os.path.isfile(bak):
                target = bak
            else:
                return False

        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.from_dict(data)
            return True
        except Exception as e:
            print(f"[ERROR SAVEGAME] File {target} korup ({e})! Mencoba memuat backup .bak...")
            bak = filepath + ".bak"
            if target != bak and os.path.isfile(bak):
                try:
                    with open(bak, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.from_dict(data)
                    return True
                except Exception as e2:
                    print(f"[ERROR SAVEGAME] Backup .bak juga korup: {e2}")
            return False
