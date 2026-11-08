"""
inventory.py - Sistem Inventori & Item Slot Terbatas (Fase 1A)

Fitur:
  1. Slot Terbatas: Tepat 12 slot penyimpanan.
  2. Tumpukan Item (Stackable): Tanaman, benih, potion, kayu, dan batu (maks 99),
     senjata/armor/charm (maks 1).
  3. Integrasi Aset Visual: Menggunakan asset_catalog (Crops, UI icons, Generated icons).
  4. Antarmuka Modal [I]: Render 12 slot dengan itemdisc_01/02 dan panel Sunnyside.
  5. Serialisasi Save/Load: to_dict() dan from_dict().
"""

import os
from typing import Dict, List, Optional, Tuple, Any
import pygame

import config
from asset_catalog import get_asset_catalog

# Registry Definisi Item di Seluruh Game
ITEM_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    # Tanaman & Hasil Tani
    "radish": {"name": "Lobak (Radish)", "category": "crop", "max_stack": 99, "icon_type": "crop", "icon_param": ("radish", 5), "desc": "Hasil panen lobak segar untuk bahan potion."},
    "wheat": {"name": "Gandum (Wheat)", "category": "crop", "max_stack": 99, "icon_type": "crop", "icon_param": ("wheat", 5), "desc": "Gandum matang bergizi tinggi untuk dijual."},
    "egg": {"name": "Telur Ayam", "category": "material", "max_stack": 99, "icon_type": "crop_item", "icon_param": "egg", "desc": "Telur segar dari kandang ayam desa."},
    "milk": {"name": "Susu Sapi", "category": "material", "max_stack": 99, "icon_type": "crop_item", "icon_param": "milk", "desc": "Susu murni dari sapi perah padang rumput."},
    "fish": {"name": "Ikan Sungai", "category": "material", "max_stack": 99, "icon_type": "crop_item", "icon_param": "fish", "desc": "Ikan segar hasil pancingan di dermaga sungai."},

    # Benih
    "seeds_radish": {"name": "Benih Lobak", "category": "seed", "max_stack": 99, "icon_type": "crop_item", "icon_param": "seeds_generic", "desc": "Benih lobak siap tanam di petak ladang."},
    "seeds_wheat": {"name": "Benih Gandum", "category": "seed", "max_stack": 99, "icon_type": "crop_item", "icon_param": "seeds_generic", "desc": "Benih gandum siap tanam di petak ladang."},

    # Material & Perkakas
    "wood": {"name": "Kayu (Wood)", "category": "material", "max_stack": 99, "icon_type": "crop_item", "icon_param": "wood", "desc": "Kayu gelondongan hasil tebang pohon desa."},
    "rock": {"name": "Batu (Rock)", "category": "material", "max_stack": 99, "icon_type": "crop_item", "icon_param": "rock", "desc": "Batu tambang dari tebing reruntuhan."},
    "bottle_empty": {"name": "Botol Kosong", "category": "material", "max_stack": 99, "icon_type": "gen", "icon_param": "bottle_empty", "desc": "Botol kaca kosong untuk meracik ramuan."},
    "potion_red": {"name": "Health Potion", "category": "consumable", "max_stack": 99, "icon_type": "gen", "icon_param": "potion_red", "desc": "Ramuan pemulih 30 HP di pertempuran boss."},
    "key": {"name": "Kunci Gerbang", "category": "key", "max_stack": 1, "icon_type": "gen", "icon_param": "key", "desc": "Kunci besi pembuka gerbang menuju sarang Boss."},

    # Perlengkapan Tempur (CSP Loadout Domain)
    "Pedang Biasa": {"name": "Pedang Biasa", "category": "weapon", "max_stack": 1, "icon_type": "ui", "icon_param": "sword.png", "desc": "Pedang standar seimbang (+0 DMG)."},
    "Kapak Berat": {"name": "Kapak Berat", "category": "weapon", "max_stack": 1, "icon_type": "ui", "icon_param": "axe.png", "desc": "Kapak penghancur perkasa (+6 DMG)."},
    "Belati Cepat": {"name": "Belati Cepat", "category": "weapon", "max_stack": 1, "icon_type": "ui", "icon_param": "sword.png", "desc": "Belati lincah tebasan cepat (+3 DMG)."},
    "Tongkat Api": {"name": "Tongkat Api", "category": "weapon", "max_stack": 1, "icon_type": "ui", "icon_param": "hammer.png", "desc": "Tongkat magis pelempar api (+4 DMG)."},
    "Kain": {"name": "Jubah Kain", "category": "armor", "max_stack": 1, "icon_type": "ui", "icon_param": "basket.png", "desc": "Pakaian kain tipis starter (+0 HP)."},
    "Kulit": {"name": "Zirah Kulit", "category": "armor", "max_stack": 1, "icon_type": "ui", "icon_param": "basket.png", "desc": "Zirah kulit lentur berpelindung (+15 HP)."},
    "Besi": {"name": "Zirah Besi", "category": "armor", "max_stack": 1, "icon_type": "ui", "icon_param": "basket.png", "desc": "Zirah lempeng besi kokoh (+30 HP)."},
    "Jimat Vitalitas": {"name": "Jimat Vitalitas", "category": "charm", "max_stack": 1, "icon_type": "ui", "icon_param": "itemdisc_01.png", "desc": "Jimat peningkat vitalitas (+15 HP)."},
    "Jimat Ketahanan": {"name": "Jimat Ketahanan", "category": "charm", "max_stack": 1, "icon_type": "ui", "icon_param": "itemdisc_01.png", "desc": "Jimat pertahanan baja lawan serang."},
    "Jimat Keberuntungan": {"name": "Jimat Keberuntungan", "category": "charm", "max_stack": 1, "icon_type": "ui", "icon_param": "itemdisc_01.png", "desc": "Jimat pembawa keberuntungan di pertempuran."},
}


class ItemStack:
    """Tumpukan item di dalam satu slot inventori."""

    def __init__(self, item_id: str, count: int = 1):
        self.item_id = item_id
        defn = ITEM_DEFINITIONS.get(item_id, {})
        self.name = defn.get("name", item_id)
        self.category = defn.get("category", "misc")
        self.max_stack = defn.get("max_stack", 99)
        self.count = max(1, min(self.max_stack, count))

    def to_dict(self) -> Dict[str, Any]:
        return {"item_id": self.item_id, "count": self.count}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ItemStack":
        return cls(item_id=data["item_id"], count=data["count"])


class Inventory:
    """Pengelola inventori hero dengan batas tetap 12 slot."""

    def __init__(self, max_slots: int = 12):
        self.max_slots = max_slots
        self.slots: List[Optional[ItemStack]] = [None] * self.max_slots

    def add_item(self, item_id: str, count: int = 1) -> int:
        """
        Menambahkan item ke inventori.
        Mengembalikan sisa count yang tidak dapat masuk jika inventori penuh (0 jika semua masuk).
        """
        if count <= 0:
            return 0
        defn = ITEM_DEFINITIONS.get(item_id, {})
        max_stk = defn.get("max_stack", 99)
        remaining = count

        # 1. Coba tambahkan ke tumpukan yang sudah ada
        if max_stk > 1:
            for slot in self.slots:
                if slot is not None and slot.item_id == item_id and slot.count < max_stk:
                    space = max_stk - slot.count
                    added = min(space, remaining)
                    slot.count += added
                    remaining -= added
                    if remaining <= 0:
                        return 0

        # 2. Masukkan sisa ke slot kosong baru
        for i in range(self.max_slots):
            if self.slots[i] is None:
                added = min(max_stk, remaining)
                self.slots[i] = ItemStack(item_id, added)
                remaining -= added
                if remaining <= 0:
                    return 0

        return remaining

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        """Menghapus count item tertentu. Mengembalikan True jika berhasil, False jika kurang."""
        if not self.has_item(item_id, count):
            return False

        needed = count
        for i in range(self.max_slots):
            slot = self.slots[i]
            if slot is not None and slot.item_id == item_id:
                if slot.count <= needed:
                    needed -= slot.count
                    self.slots[i] = None
                else:
                    slot.count -= needed
                    needed = 0
                if needed <= 0:
                    break
        return True

    def has_item(self, item_id: str, count: int = 1) -> bool:
        """Memeriksa apakah inventori memiliki minimal count item tertentu."""
        return self.get_item_count(item_id) >= count

    def get_item_count(self, item_id: str) -> int:
        """Menghitung total item_id di seluruh slot inventori."""
        total = 0
        for slot in self.slots:
            if slot is not None and slot.item_id == item_id:
                total += slot.count
        return total

    def is_full(self) -> bool:
        """Cek apakah seluruh 12 slot terisi."""
        return all(s is not None for s in self.slots)

    def get_owned_items(self) -> List[str]:
        """Mengembalikan daftar unik ID item yang dimiliki saat ini."""
        owned = set()
        for slot in self.slots:
            if slot is not None:
                owned.add(slot.item_id)
        return list(owned)

    def to_dict(self) -> List[Optional[Dict[str, Any]]]:
        """Serialisasi untuk penyimpanan savegame."""
        return [s.to_dict() if s is not None else None for s in self.slots]

    def from_dict(self, data: List[Optional[Dict[str, Any]]]):
        """Deserialisasi dari savegame."""
        self.slots = [None] * self.max_slots
        for i, item_data in enumerate(data[:self.max_slots]):
            if item_data:
                self.slots[i] = ItemStack.from_dict(item_data)


class InventoryUI:
    """Antarmuka visual inventori [I] dengan panel Sunnyside bergrid 4x3."""

    def __init__(self):
        self.is_open = False
        self.hover_slot: Optional[int] = None
        self.font_title = pygame.font.Font(None, 24)
        self.font_body = pygame.font.Font(None, 18)
        self.font_num = pygame.font.Font(None, 16)

        # Layout Modal Ukuran 480 x 360 (di tengah layar 1024x768)
        self.modal_rect = pygame.Rect((1024 - 480) // 2, (768 - 360) // 2, 480, 360)
        self.slot_size = 56
        self.slot_pad = 12
        self.grid_cols = 4
        self.grid_rows = 3
        self.grid_start_x = self.modal_rect.x + 36
        self.grid_start_y = self.modal_rect.y + 60

    def toggle(self):
        self.is_open = not self.is_open

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Menangani klik atau tombol saat modal inventori aktif."""
        if not self.is_open:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_i, pygame.K_ESCAPE):
                self.is_open = False
                return True
        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self.hover_slot = None
            for idx in range(12):
                r = idx // self.grid_cols
                c = idx % self.grid_cols
                sx = self.grid_start_x + c * (self.slot_size + self.slot_pad)
                sy = self.grid_start_y + r * (self.slot_size + self.slot_pad)
                slot_rect = pygame.Rect(sx, sy, self.slot_size, self.slot_size)
                if slot_rect.collidepoint(mx, my):
                    self.hover_slot = idx
                    break
            return True
        return True

    def _render_item_icon(self, item_id: str, scale: int = 2) -> pygame.Surface:
        """Render ikon item dari asset_catalog."""
        cat = get_asset_catalog()
        defn = ITEM_DEFINITIONS.get(item_id, {})
        itype = defn.get("icon_type", "gen")
        iparam = defn.get("icon_param", item_id)

        if itype == "crop":
            cname, stg = iparam
            return cat.get_crop(cname, stage=stg, scale=scale)
        elif itype == "crop_item":
            return cat.get_crop_item(iparam, scale=scale)
        elif itype == "ui":
            return cat.get_ui_icon(iparam, scale=scale)
        elif itype == "gen":
            return cat.get_generated_icon(iparam, scale=scale)
        return cat.get_generated_icon("coin", scale=scale)

    def draw(self, screen: pygame.Surface, inventory: Inventory, coins: int = 0):
        if not self.is_open:
            return

        # Latar belakang gelap semi-transparan (dimmer)
        dimmer = pygame.Surface((1024, 768), pygame.SRCALPHA)
        dimmer.fill((0, 0, 0, 160))
        screen.blit(dimmer, (0, 0))

        # Kotak Modal Inventori
        pygame.draw.rect(screen, (36, 36, 60), self.modal_rect, border_radius=8)
        pygame.draw.rect(screen, config.GOLD, self.modal_rect, 2, border_radius=8)

        # Header Title
        title_surf = self.font_title.render("INVENTORI TAS HERO", True, config.GOLD)
        screen.blit(title_surf, (self.modal_rect.x + 24, self.modal_rect.y + 20))

        # Indikator Koin
        coin_icon = get_asset_catalog().get_generated_icon("coin", scale=1)
        cx = self.modal_rect.right - 140
        cy = self.modal_rect.y + 22
        screen.blit(coin_icon, (cx, cy))
        coin_txt = self.font_body.render(f": {coins} Koin", True, config.GOLD)
        screen.blit(coin_txt, (cx + 20, cy))

        # Close hint
        close_txt = self.font_num.render("[I / ESC] Tutup", True, (180, 180, 180))
        screen.blit(close_txt, (self.modal_rect.right - 90, self.modal_rect.y + 6))

        # Render 12 Slot Grid (4 kolom x 3 baris)
        for idx in range(inventory.max_slots):
            r = idx // self.grid_cols
            c = idx % self.grid_cols
            sx = self.grid_start_x + c * (self.slot_size + self.slot_pad)
            sy = self.grid_start_y + r * (self.slot_size + self.slot_pad)
            slot_rect = pygame.Rect(sx, sy, self.slot_size, self.slot_size)

            # Slot background disc
            bg_color = (55, 55, 85) if self.hover_slot == idx else (45, 45, 70)
            pygame.draw.rect(screen, bg_color, slot_rect, border_radius=6)
            border_col = config.CYAN if self.hover_slot == idx else (75, 75, 110)
            pygame.draw.rect(screen, border_col, slot_rect, 1, border_radius=6)

            # Gambar Item
            slot = inventory.slots[idx]
            if slot is not None:
                icon = self._render_item_icon(slot.item_id, scale=2)
                ix = sx + (self.slot_size - icon.get_width()) // 2
                iy = sy + (self.slot_size - icon.get_height()) // 2
                screen.blit(icon, (ix, iy))

                # Jumlah tumpukan (jika > 1)
                if slot.count > 1:
                    num_surf = self.font_num.render(str(slot.count), True, config.WHITE)
                    screen.blit(num_surf, (sx + self.slot_size - num_surf.get_width() - 4,
                                           sy + self.slot_size - num_surf.get_height() - 2))

        # Footer Description Box jika ada slot yang di-hover
        desc_rect = pygame.Rect(self.modal_rect.x + 24, self.modal_rect.bottom - 80, self.modal_rect.w - 48, 64)
        pygame.draw.rect(screen, (28, 28, 45), desc_rect, border_radius=4)
        pygame.draw.rect(screen, (60, 60, 90), desc_rect, 1, border_radius=4)

        if self.hover_slot is not None and self.hover_slot < len(inventory.slots):
            slot = inventory.slots[self.hover_slot]
            if slot is not None:
                defn = ITEM_DEFINITIONS.get(slot.item_id, {})
                d_name = self.font_body.render(f"{slot.name} ({slot.category.upper()})", True, config.CYAN)
                d_desc = self.font_num.render(defn.get("desc", ""), True, (220, 220, 220))
                d_cnt = self.font_num.render(f"Jumlah tersimpan: {slot.count} / {slot.max_stack}", True, config.GOLD)
                screen.blit(d_name, (desc_rect.x + 10, desc_rect.y + 8))
                screen.blit(d_desc, (desc_rect.x + 10, desc_rect.y + 26))
                screen.blit(d_cnt, (desc_rect.x + 10, desc_rect.y + 44))
            else:
                empty_txt = self.font_num.render(f"Slot #{self.hover_slot + 1}: Kosong", True, (140, 140, 140))
                screen.blit(empty_txt, (desc_rect.x + 10, desc_rect.y + 24))
        else:
            hint_txt = self.font_num.render("Arahkan kursor ke slot item untuk melihat rincian informasi.", True, (140, 140, 140))
            screen.blit(hint_txt, (desc_rect.x + 10, desc_rect.y + 24))
