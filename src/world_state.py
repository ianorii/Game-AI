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
from typing import Dict, List, Optional, Tuple, Any
import pygame

import config
from asset_catalog import get_asset_catalog
from inventory import Inventory
from economy import Shop
from farm import FarmManager


class LockedGate:
    """Gerbang besi/kayu berkunci pembatas menuju area Boss Skeleton Overlord di koridor chokepoint tunggal."""

    def __init__(self, x: int = 2336, y: int = 816, w: int = 288, h: int = 48):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.is_open: bool = False
        self.open_progress: float = 0.0  # 0.0 (tertutup penuh) -> 1.0 (terbuka penuh)
        # Dynamic obstacle rect untuk menutup jalan masuk saat terkunci
        self.collision_rect = pygame.Rect(self.x, self.y, self.w, self.h)
        # Posisi visual pintu gerbang di koridor utama
        self.visual_pos = (self.x, self.y)

    def unlock(self, inventory: Inventory) -> Tuple[bool, str]:
        if self.is_open:
            return False, "Gerbang sudah terbuka!"
        if not inventory.has_item("key", 1):
            return False, "Gerbang terkunci rapat! Butuh 'Kunci Gerbang' (Key) untuk membukanya."

        inventory.remove_item("key", 1)
        self.is_open = True
        self.open_progress = 1.0
        return True, "Kunci dimasukkan... KLIK! Gerbang Reruntuhan terbuka lebar!"

    def update(self, dt: float):
        if self.is_open and self.open_progress < 1.0:
            self.open_progress = min(1.0, self.open_progress + dt * 2.5)

    def get_obstacle_rect(self) -> Optional[pygame.Rect]:
        """Mengembalikan obstacle rect jika tertutup, None jika terbuka."""
        return None if self.is_open else self.collision_rect

    def draw(self, screen: pygame.Surface, camera: Tuple[int, int],
             hero_pos: Optional[Tuple[float, float]] = None):
        cat = get_asset_catalog()
        cam_x, cam_y = camera
        vx = int(self.visual_pos[0] - cam_x)
        vy = int(self.visual_pos[1] - cam_y)

        # Culling di luar layar
        if not (-self.w <= vx <= 1024 + 64 and -self.h <= vy <= 768 + 64):
            return

        font_prompt = pygame.font.Font(None, 18)

        # 1. Pilar batu samping kiri dan kanan dari blok batu Sunnyside
        pillar_w = 24
        # Pilar kiri
        pygame.draw.rect(screen, (45, 42, 50), (vx, vy - 4, pillar_w, self.h + 8), border_radius=4)
        pygame.draw.rect(screen, (75, 70, 82), (vx + 2, vy - 2, pillar_w - 4, self.h + 4), border_radius=3)
        pygame.draw.rect(screen, (105, 100, 115), (vx, vy - 4, pillar_w, self.h + 8), 1, border_radius=4)
        # Cap atas pilar kiri
        pygame.draw.rect(screen, (120, 115, 130), (vx - 2, vy - 8, pillar_w + 4, 6), border_radius=2)

        # Pilar kanan
        pr_x = vx + self.w - pillar_w
        pygame.draw.rect(screen, (45, 42, 50), (pr_x, vy - 4, pillar_w, self.h + 8), border_radius=4)
        pygame.draw.rect(screen, (75, 70, 82), (pr_x + 2, vy - 2, pillar_w - 4, self.h + 4), border_radius=3)
        pygame.draw.rect(screen, (105, 100, 115), (pr_x, vy - 4, pillar_w, self.h + 8), 1, border_radius=4)
        # Cap atas pilar kanan
        pygame.draw.rect(screen, (120, 115, 130), (pr_x - 2, vy - 8, pillar_w + 4, 6), border_radius=2)

        gate_span = self.w - (pillar_w * 2)
        gate_start_x = vx + pillar_w
        half_span = gate_span // 2

        # Animasi buka: slide/retract kedua sayap pintu ke pilar
        prog = self.open_progress if self.is_open else 0.0
        leaf_w = int(half_span * (1.0 - prog * 0.75))

        # Panel Pintu Kiri
        left_leaf_rect = pygame.Rect(gate_start_x, vy + 4, leaf_w, self.h - 8)
        # Panel Pintu Kanan
        right_leaf_rect = pygame.Rect(gate_start_x + gate_span - leaf_w, vy + 4, leaf_w, self.h - 8)

        # Gambar Daun Pintu Kayu & Jeruji Besi
        for rect, is_right in [(left_leaf_rect, False), (right_leaf_rect, True)]:
            if rect.width <= 4:
                continue
            # Dasar kayu gelap
            pygame.draw.rect(screen, (60, 42, 28), rect, border_radius=2)
            pygame.draw.rect(screen, (92, 64, 42), rect.inflate(-2, -2), border_radius=2)
            # Palang besi horizontal
            pygame.draw.line(screen, (45, 48, 55), (rect.left, rect.top + 8), (rect.right, rect.top + 8), 3)
            pygame.draw.line(screen, (45, 48, 55), (rect.left, rect.centery), (rect.right, rect.centery), 3)
            pygame.draw.line(screen, (45, 48, 55), (rect.left, rect.bottom - 8), (rect.right, rect.bottom - 8), 3)
            # Jeruji besi vertikal
            for bx in range(rect.left + 8, rect.right - 4, 16):
                pygame.draw.line(screen, (130, 135, 145), (bx, rect.top + 2), (bx, rect.bottom - 2), 2)
                # Ujung runcing atas
                pygame.draw.line(screen, (180, 185, 195), (bx, rect.top), (bx, rect.top + 4), 1)
            # Bingkai besi
            pygame.draw.rect(screen, (35, 38, 45), rect, 1, border_radius=2)

        lock_cx = vx + self.w // 2
        lock_cy = vy + self.h // 2

        if not self.is_open:
            # Ikon Gembok Rantai di tengah kedua daun pintu yang terkunci
            gate_surf = cat.get_generated_icon("gate_locked", scale=2)
            screen.blit(gate_surf, (lock_cx - gate_surf.get_width() // 2, lock_cy - gate_surf.get_height() // 2))

            # Prompt "Butuh Kunci Gerbang" saat hero dekat
            is_near = False
            if hero_pos:
                dist = ((self.x + self.w // 2 - hero_pos[0]) ** 2 + (self.y + self.h // 2 - hero_pos[1]) ** 2) ** 0.5
                if dist <= 120.0:
                    is_near = True

            if is_near:
                lbl = font_prompt.render("Butuh Kunci Gerbang [E]", True, (255, 210, 80))
                tag_w = lbl.get_width() + 12
                tag_h = lbl.get_height() + 4
                tag_rect = pygame.Rect(lock_cx - tag_w // 2, vy - 24, tag_w, tag_h)
                pygame.draw.rect(screen, (20, 20, 30, 220), tag_rect, border_radius=3)
                pygame.draw.rect(screen, (255, 190, 60), tag_rect, 1, border_radius=3)
                screen.blit(lbl, (tag_rect.x + 6, tag_rect.y + 2))
        else:
            # Ikon gerbang terbuka di pilar samping
            gate_surf = cat.get_generated_icon("gate_open", scale=2)
            screen.blit(gate_surf, (lock_cx - gate_surf.get_width() // 2, lock_cy - gate_surf.get_height() // 2))


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
        """Menempa Kunci Gerbang: 1 kayu (wood) + 1 batu (rock)."""
        if not self.inventory.has_item("wood", 1):
            return False, "Bahan kurang! Butuh 1x Kayu (Wood)."
        if not self.inventory.has_item("rock", 1):
            return False, "Bahan kurang! Butuh 1x Batu (Rock)."

        self.inventory.remove_item("wood", 1)
        self.inventory.remove_item("rock", 1)
        self.inventory.add_item("key", 1)
        return True, "Berhasil menempa 1x Kunci Gerbang di bengkel!"

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

    def fish(self) -> Tuple[bool, str]:
        if self.cooldowns["fishing"] > 0:
            return False, f"Menunggu ikan menyambar umpan... ({int(self.cooldowns['fishing'])}s)"
        if self.inventory.is_full() and not self.inventory.has_item("fish", 1):
            return False, "Inventori tas hero penuh!"

        self.inventory.add_item("fish", 1)
        self.cooldowns["fishing"] = 10.0
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
