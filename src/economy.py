"""
economy.py - Sistem Ekonomi, Koin, dan Toko Desa Sunnyside (Fase 1A)

Fitur:
  1. Dompet Koin (Coin Wallet): Koin awal hero dikonfigurasi (default 50 koin).
  2. Toko Desa: Bangunan toko desa dengan barang beli & jual.
     - Jual: Hasil panen (radish, wheat), egg, milk, fish, wood, rock.
     - Beli: Benih (seeds_radish, seeds_wheat), botol kosong (bottle_empty),
             senjata/zirah/jimat (domain CSP: Kapak Berat, Belati Cepat, Tongkat Api, Kulit, Besi, Jimat).
  3. UI Toko [E]: Antarmuka jual-beli interaktif dengan tab BELI & JUAL.
  4. Serialisasi: to_dict() dan from_dict() untuk save/load state.
"""

from typing import Dict, List, Optional, Tuple, Any
import pygame

import config
from asset_catalog import get_asset_catalog
from inventory import Inventory, ITEM_DEFINITIONS


DEFAULT_SHOP_CATALOG: Dict[str, Dict[str, Any]] = {
    # Barang yang Dijual Toko ke Hero (Hero Membeli)
    "seeds_radish": {"price": 5, "stock": 20, "name": "Benih Lobak", "type": "seed"},
    "seeds_wheat": {"price": 4, "stock": 20, "name": "Benih Gandum", "type": "seed"},
    "bottle_empty": {"price": 8, "stock": 15, "name": "Botol Kosong", "type": "material"},

    # Peralatan Tempur CSP Loadout
    "Kapak Berat": {"price": 35, "stock": 1, "name": "Kapak Berat (+6 DMG)", "type": "weapon"},
    "Belati Cepat": {"price": 25, "stock": 1, "name": "Belati Cepat (+3 DMG)", "type": "weapon"},
    "Tongkat Api": {"price": 40, "stock": 1, "name": "Tongkat Api (+4 DMG)", "type": "weapon"},
    "Kulit": {"price": 20, "stock": 1, "name": "Zirah Kulit (+15 HP)", "type": "armor"},
    "Besi": {"price": 45, "stock": 1, "name": "Zirah Besi (+30 HP)", "type": "armor"},
    "Jimat Vitalitas": {"price": 30, "stock": 1, "name": "Jimat Vitalitas (+15 HP)", "type": "charm"},
    "Jimat Ketahanan": {"price": 30, "stock": 1, "name": "Jimat Ketahanan (Defend)", "type": "charm"},
    "Jimat Keberuntungan": {"price": 35, "stock": 1, "name": "Jimat Keberuntungan", "type": "charm"},
}

DEFAULT_SELL_PRICES: Dict[str, int] = {
    "radish": 10,
    "wheat": 8,
    "egg": 6,
    "milk": 12,
    "fish": 15,
    "wood": 5,
    "rock": 5,
    "potion_red": 18,
}


class Shop:
    """Logika perdagangan toko desa dengan manajemen stok dan koin."""

    def __init__(self, stock: Optional[Dict[str, int]] = None):
        self.catalog = dict(DEFAULT_SHOP_CATALOG)
        self.sell_prices = dict(DEFAULT_SELL_PRICES)
        self.stock: Dict[str, int] = {}
        for item_id, info in self.catalog.items():
            init_stk = stock.get(item_id, info["stock"]) if stock else info["stock"]
            self.stock[item_id] = init_stk

    def get_buy_price(self, item_id: str) -> int:
        return self.catalog.get(item_id, {}).get("price", 999)

    def get_sell_price(self, item_id: str) -> int:
        return self.sell_prices.get(item_id, 0)

    def can_buy(self, item_id: str, count: int, coins: int, inventory: Inventory) -> Tuple[bool, str]:
        if item_id not in self.stock:
            return False, "Barang tidak tersedia di toko!"
        if self.stock[item_id] < count:
            return False, "Stok toko habis!"
        cost = self.get_buy_price(item_id) * count
        if coins < cost:
            return False, f"Koin tidak cukup! Butuh {cost} koin (punya {coins})."
        if inventory.is_full() and not inventory.has_item(item_id):
            return False, "Inventori tas hero sudah penuh!"
        return True, "Dapat dibeli."

    def buy_item(self, item_id: str, count: int, coins: int, inventory: Inventory) -> Tuple[bool, int, str]:
        """
        Membeli item dari toko.
        Mengembalikan (sukses, koin_sisa, pesan).
        """
        ok, reason = self.can_buy(item_id, count, coins, inventory)
        if not ok:
            return False, coins, reason

        cost = self.get_buy_price(item_id) * count
        leftover = inventory.add_item(item_id, count)
        if leftover > 0:
            # Revert partial add
            inventory.remove_item(item_id, count - leftover)
            return False, coins, "Gagal memasukkan semua item ke inventori!"

        self.stock[item_id] -= count
        new_coins = coins - cost
        item_name = ITEM_DEFINITIONS.get(item_id, {}).get("name", item_id)
        return True, new_coins, f"Berhasil membeli {count}x {item_name} seharga {cost} koin!"

    def can_sell(self, item_id: str, count: int, inventory: Inventory) -> Tuple[bool, str]:
        if item_id not in self.sell_prices:
            return False, "Toko tidak menerima barang ini!"
        if not inventory.has_item(item_id, count):
            return False, "Jumlah barang di tas tidak mencukupi!"
        return True, "Dapat dijual."

    def sell_item(self, item_id: str, count: int, coins: int, inventory: Inventory) -> Tuple[bool, int, str]:
        """
        Menjual item ke toko.
        Mengembalikan (sukses, koin_baru, pesan).
        """
        ok, reason = self.can_sell(item_id, count, inventory)
        if not ok:
            return False, coins, reason

        revenue = self.get_sell_price(item_id) * count
        if not inventory.remove_item(item_id, count):
            return False, coins, "Gagal mengeluarkan item dari tas!"

        new_coins = coins + revenue
        item_name = ITEM_DEFINITIONS.get(item_id, {}).get("name", item_id)
        return True, new_coins, f"Berhasil menjual {count}x {item_name} seharga {revenue} koin!"

    def to_dict(self) -> Dict[str, Any]:
        return {"stock": dict(self.stock)}

    def from_dict(self, data: Dict[str, Any]):
        self.stock = dict(data.get("stock", {}))


def _wrap_text(font: pygame.font.Font, text: str, max_width: int) -> List[str]:
    """Membagi teks ke beberapa baris rapi sesuai lebar piksel maksimal tanpa pemotongan canggung."""
    words = text.split()
    lines = []
    curr: List[str] = []
    for w in words:
        test = " ".join(curr + [w])
        if font.size(test)[0] <= max_width:
            curr.append(w)
        else:
            if curr:
                lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))
    return lines


class ShopUI:
    """Modal UI interaktif Toko Desa dengan Tab Beli dan Jual."""

    def __init__(self):
        self.is_open = False
        self.active_tab = "BUY"  # "BUY" atau "SELL"
        self.selected_item: Optional[str] = None
        self.hover_idx: Optional[int] = None
        self.status_msg = "Selamat datang di Toko Desa Sunnyside!"
        self.status_color = config.WHITE

        self.font_title = pygame.font.Font(None, 24)
        self.font_tab = pygame.font.Font(None, 20)
        self.font_body = pygame.font.Font(None, 18)
        self.font_xs = pygame.font.Font(None, 15)

        self.modal_rect = pygame.Rect((1024 - 560) // 2, (768 - 440) // 2, 560, 440)
        self.tab_buy_rect = pygame.Rect(self.modal_rect.x + 24, self.modal_rect.y + 54, 120, 32)
        self.tab_sell_rect = pygame.Rect(self.modal_rect.x + 150, self.modal_rect.y + 54, 120, 32)
        self.action_btn_rect = pygame.Rect(self.modal_rect.right - 170, self.modal_rect.bottom - 50, 146, 36)

        # Pagination & Scrolling
        self.page: int = 0
        self.items_per_page: int = 6
        self.prev_btn_rect = pygame.Rect(self.modal_rect.x + 24, self.modal_rect.y + 348, 36, 26)
        self.next_btn_rect = pygame.Rect(self.modal_rect.x + 318, self.modal_rect.y + 348, 36, 26)

    def open(self):
        self.is_open = True
        self.selected_item = None
        self.page = 0
        self.status_msg = "Pilih barang yang ingin ditransaksikan."
        self.status_color = config.WHITE

    def close(self):
        self.is_open = False

    def handle_event(self, event: pygame.event.Event, shop: Shop, inventory: Inventory, coins: int) -> Tuple[bool, int]:
        """
        Menangani interaksi mouse dan keyboard di antarmuka toko.
        Mengembalikan (event_handled, new_coins).
        """
        if not self.is_open:
            return False, coins

        items = list(shop.catalog.keys()) if self.active_tab == "BUY" else [it for it in shop.sell_prices.keys() if inventory.has_item(it)]
        total_pages = max(1, (len(items) + self.items_per_page - 1) // self.items_per_page)

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_e):
                self.close()
                return True, coins
            elif event.key in (pygame.K_PAGEUP, pygame.K_LEFT):
                if self.page > 0:
                    self.page -= 1
                return True, coins
            elif event.key in (pygame.K_PAGEDOWN, pygame.K_RIGHT):
                if self.page < total_pages - 1:
                    self.page += 1
                return True, coins
            elif event.key == pygame.K_UP:
                start_idx = self.page * self.items_per_page
                page_items = items[start_idx : start_idx + self.items_per_page]
                if self.selected_item in page_items:
                    curr_i = page_items.index(self.selected_item)
                    if curr_i > 0:
                        self.selected_item = page_items[curr_i - 1]
                    elif self.page > 0:
                        self.page -= 1
                        prev_page_items = items[(self.page) * self.items_per_page : (self.page + 1) * self.items_per_page]
                        if prev_page_items:
                            self.selected_item = prev_page_items[-1]
                elif page_items:
                    self.selected_item = page_items[0]
                return True, coins
            elif event.key == pygame.K_DOWN:
                start_idx = self.page * self.items_per_page
                page_items = items[start_idx : start_idx + self.items_per_page]
                if self.selected_item in page_items:
                    curr_i = page_items.index(self.selected_item)
                    if curr_i < len(page_items) - 1:
                        self.selected_item = page_items[curr_i + 1]
                    elif self.page < total_pages - 1:
                        self.page += 1
                        next_page_items = items[(self.page) * self.items_per_page : (self.page + 1) * self.items_per_page]
                        if next_page_items:
                            self.selected_item = next_page_items[0]
                elif page_items:
                    self.selected_item = page_items[0]
                return True, coins

        elif event.type == pygame.MOUSEWHEEL:
            if event.y > 0 and self.page > 0:
                self.page -= 1
            elif event.y < 0 and self.page < total_pages - 1:
                self.page += 1
            return True, coins

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4 and self.page > 0:
                self.page -= 1
                return True, coins
            elif event.button == 5 and self.page < total_pages - 1:
                self.page += 1
                return True, coins
            elif event.button == 1:
                mx, my = event.pos
                if self.tab_buy_rect.collidepoint(mx, my):
                    self.active_tab = "BUY"
                    self.selected_item = None
                    self.page = 0
                    return True, coins
                elif self.tab_sell_rect.collidepoint(mx, my):
                    self.active_tab = "SELL"
                    self.selected_item = None
                    self.page = 0
                    return True, coins

                # Pagination buttons
                if self.prev_btn_rect.collidepoint(mx, my) and self.page > 0:
                    self.page -= 1
                    return True, coins
                if self.next_btn_rect.collidepoint(mx, my) and self.page < total_pages - 1:
                    self.page += 1
                    return True, coins

                # Cek klik pada item list halaman aktif
                start_idx = self.page * self.items_per_page
                page_items = items[start_idx : start_idx + self.items_per_page]
                list_y = self.modal_rect.y + 98
                for i, it in enumerate(page_items):
                    r = pygame.Rect(self.modal_rect.x + 24, list_y + i * 40, 330, 34)
                    if r.collidepoint(mx, my):
                        self.selected_item = it
                        return True, coins

                # Tombol aksi Beli/Jual
                if self.action_btn_rect.collidepoint(mx, my) and self.selected_item:
                    if self.active_tab == "BUY":
                        ok, new_c, msg = shop.buy_item(self.selected_item, 1, coins, inventory)
                        self.status_msg = msg
                        self.status_color = config.GREEN if ok else config.RED
                        return True, new_c
                    else:
                        ok, new_c, msg = shop.sell_item(self.selected_item, 1, coins, inventory)
                        self.status_msg = msg
                        self.status_color = config.GOLD if ok else config.RED
                        return True, new_c

        return True, coins

    def draw(self, screen: pygame.Surface, shop: Shop, inventory: Inventory, coins: int):
        if not self.is_open:
            return

        dimmer = pygame.Surface((1024, 768), pygame.SRCALPHA)
        dimmer.fill((0, 0, 0, 160))
        screen.blit(dimmer, (0, 0))

        # Panel Utama
        pygame.draw.rect(screen, (34, 34, 56), self.modal_rect, border_radius=8)
        pygame.draw.rect(screen, config.GOLD, self.modal_rect, 2, border_radius=8)

        # Header Title
        title_txt = self.font_title.render("TOKO DESA SUNNYSIDE", True, config.GOLD)
        screen.blit(title_txt, (self.modal_rect.x + 24, self.modal_rect.y + 18))

        # Koin Hero
        coin_icon = get_asset_catalog().get_generated_icon("coin", scale=1)
        cx = self.modal_rect.right - 140
        cy = self.modal_rect.y + 20
        screen.blit(coin_icon, (cx, cy))
        screen.blit(self.font_body.render(f": {coins} Koin", True, config.GOLD), (cx + 20, cy))

        # Tabs: BELI vs JUAL
        buy_col = (60, 60, 95) if self.active_tab == "BUY" else (40, 40, 65)
        sell_col = (60, 60, 95) if self.active_tab == "SELL" else (40, 40, 65)
        pygame.draw.rect(screen, buy_col, self.tab_buy_rect, border_radius=4)
        pygame.draw.rect(screen, sell_col, self.tab_sell_rect, border_radius=4)
        if self.active_tab == "BUY":
            pygame.draw.rect(screen, config.CYAN, self.tab_buy_rect, 2, border_radius=4)
        else:
            pygame.draw.rect(screen, config.GOLD, self.tab_sell_rect, 2, border_radius=4)

        screen.blit(self.font_tab.render("BELI BARANG", True, config.CYAN if self.active_tab == "BUY" else (160, 160, 160)), (self.tab_buy_rect.x + 12, self.tab_buy_rect.y + 8))
        screen.blit(self.font_tab.render("JUAL HASIL", True, config.GOLD if self.active_tab == "SELL" else (160, 160, 160)), (self.tab_sell_rect.x + 18, self.tab_sell_rect.y + 8))

        # Item List dengan Pagination
        list_y = self.modal_rect.y + 98
        items = list(shop.catalog.keys()) if self.active_tab == "BUY" else [it for it in shop.sell_prices.keys() if inventory.has_item(it)]
        total_pages = max(1, (len(items) + self.items_per_page - 1) // self.items_per_page)
        self.page = max(0, min(self.page, total_pages - 1))

        if not items and self.active_tab == "SELL":
            screen.blit(self.font_body.render("Tidak ada barang di tas yang dapat dijual.", True, (160, 160, 160)), (self.modal_rect.x + 28, list_y + 20))

        start_idx = self.page * self.items_per_page
        page_items = items[start_idx : start_idx + self.items_per_page]

        for i, it in enumerate(page_items):
            row_rect = pygame.Rect(self.modal_rect.x + 24, list_y + i * 40, 330, 34)
            is_sel = (it == self.selected_item)
            bg = (55, 55, 85) if is_sel else (42, 42, 65)
            pygame.draw.rect(screen, bg, row_rect, border_radius=4)
            if is_sel:
                pygame.draw.rect(screen, config.CYAN if self.active_tab == "BUY" else config.GOLD, row_rect, 1, border_radius=4)

            name = ITEM_DEFINITIONS.get(it, {}).get("name", it)
            if self.active_tab == "BUY":
                price = shop.get_buy_price(it)
                stk = shop.stock.get(it, 0)
                txt = self.font_body.render(f"{name}", True, config.WHITE)
                info = self.font_xs.render(f"{price} Koin (Stok: {stk})", True, config.GOLD)
            else:
                price = shop.get_sell_price(it)
                owned = inventory.get_item_count(it)
                txt = self.font_body.render(f"{name}", True, config.WHITE)
                info = self.font_xs.render(f"Harga: {price} Koin (Punya: {owned})", True, config.GOLD)

            screen.blit(txt, (row_rect.x + 8, row_rect.y + 8))
            screen.blit(info, (row_rect.right - info.get_width() - 8, row_rect.y + 10))

        # Kontrol Halaman (Pagination Bar)
        if total_pages > 1:
            # Prev Button
            prev_col = (60, 60, 95) if self.page > 0 else (35, 35, 50)
            pygame.draw.rect(screen, prev_col, self.prev_btn_rect, border_radius=4)
            pygame.draw.rect(screen, config.GOLD if self.page > 0 else (60, 60, 80), self.prev_btn_rect, 1, border_radius=4)
            p_txt = self.font_body.render("<", True, config.WHITE if self.page > 0 else (100, 100, 100))
            screen.blit(p_txt, (self.prev_btn_rect.centerx - p_txt.get_width() // 2, self.prev_btn_rect.centery - p_txt.get_height() // 2))

            # Page Indicator Text
            page_txt = self.font_xs.render(f"Halaman {self.page + 1}/{total_pages} (Gunakan Mouse Wheel / Panah)", True, config.GOLD)
            screen.blit(page_txt, (self.modal_rect.x + 68, self.prev_btn_rect.y + 6))

            # Next Button
            next_col = (60, 60, 95) if self.page < total_pages - 1 else (35, 35, 50)
            pygame.draw.rect(screen, next_col, self.next_btn_rect, border_radius=4)
            pygame.draw.rect(screen, config.GOLD if self.page < total_pages - 1 else (60, 60, 80), self.next_btn_rect, 1, border_radius=4)
            n_txt = self.font_body.render(">", True, config.WHITE if self.page < total_pages - 1 else (100, 100, 100))
            screen.blit(n_txt, (self.next_btn_rect.centerx - n_txt.get_width() // 2, self.next_btn_rect.centery - n_txt.get_height() // 2))

        # Detail Panel Kanan
        det_rect = pygame.Rect(self.modal_rect.x + 368, list_y, 168, 220)
        pygame.draw.rect(screen, (28, 28, 48), det_rect, border_radius=6)
        pygame.draw.rect(screen, (55, 55, 80), det_rect, 1, border_radius=6)

        if self.selected_item:
            defn = ITEM_DEFINITIONS.get(self.selected_item, {})
            screen.blit(self.font_body.render(defn.get("name", self.selected_item), True, config.CYAN), (det_rect.x + 10, det_rect.y + 12))
            screen.blit(self.font_xs.render(f"Kategori: {defn.get('category','').upper()}", True, (180, 180, 180)), (det_rect.x + 10, det_rect.y + 34))
            # Deskripsi terbungkus kata (word wrap) rapi tanpa terpotong
            desc_text = defn.get("desc", "")
            wrapped = _wrap_text(self.font_xs, desc_text, det_rect.width - 20)
            for li, line in enumerate(wrapped[:5]):
                screen.blit(self.font_xs.render(line, True, (210, 210, 210)), (det_rect.x + 10, det_rect.y + 54 + li * 15))

            price = shop.get_buy_price(self.selected_item) if self.active_tab == "BUY" else shop.get_sell_price(self.selected_item)
            screen.blit(self.font_body.render(f"Nilai: {price} Koin", True, config.GOLD), (det_rect.x + 10, det_rect.y + 140))
        else:
            screen.blit(self.font_xs.render("Pilih item untuk", True, (150, 150, 150)), (det_rect.x + 14, det_rect.y + 80))
            screen.blit(self.font_xs.render("melihat detailnya.", True, (150, 150, 150)), (det_rect.x + 14, det_rect.y + 100))

        # Tombol Aksi
        btn_col = (45, 110, 65) if self.selected_item else (45, 45, 65)
        pygame.draw.rect(screen, btn_col, self.action_btn_rect, border_radius=6)
        pygame.draw.rect(screen, config.GOLD if self.selected_item else (70, 70, 90), self.action_btn_rect, 1, border_radius=6)
        btn_label = "BELI (1x)" if self.active_tab == "BUY" else "JUAL (1x)"
        lbl = self.font_body.render(btn_label, True, config.WHITE if self.selected_item else (140, 140, 140))
        screen.blit(lbl, (self.action_btn_rect.centerx - lbl.get_width() // 2, self.action_btn_rect.centery - lbl.get_height() // 2))

        # Status Bar Bawah
        msg_surf = self.font_xs.render(self.status_msg, True, self.status_color)
        screen.blit(msg_surf, (self.modal_rect.x + 24, self.modal_rect.bottom - 36))
