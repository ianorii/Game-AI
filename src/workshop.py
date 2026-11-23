"""
workshop.py - Antarmuka Visual Bengkel Tempa & Perlengkapan (Workshop UI).
Menyediakan modal interaktif untuk:
1. Pasang Perlengkapan Tempur (Equip Loadout: Pedang & Zirah)
2. Tempa Kunci Segel Bos (1 Kayu + 1 Batu)
3. Racik Health Potion (1 Lobak + 1 Botol Kosong)
"""
from typing import Optional, Tuple, Dict, Any
import pygame
import config
from asset_catalog import get_asset_catalog
import world_actions


class WorkshopUI:
    """Modal UI interaktif Bengkel Tempa & Perlengkapan."""

    def __init__(self):
        self.is_open: bool = False
        self.status_msg: str = "Pilih aksi yang ingin dilakukan di bengkel."
        self.status_color: Tuple[int, int, int] = config.CYAN

        # Font
        self.font_title = pygame.font.Font(None, 24)
        self.font_card_title = pygame.font.Font(None, 20)
        self.font_body = pygame.font.Font(None, 16)
        self.font_xs = pygame.font.Font(None, 14)
        self.font_btn = pygame.font.Font(None, 16)

        # Geometri Modal Ukuran 640 x 460 (Center 1024x768)
        self.modal_rect = pygame.Rect((1024 - 640) // 2, (768 - 460) // 2, 640, 460)
        self.close_btn_rect = pygame.Rect(self.modal_rect.right - 36, self.modal_rect.y + 16, 22, 22)

        # 3 Card Aksi
        self.card_gear_rect = pygame.Rect(self.modal_rect.x + 20, self.modal_rect.y + 68, self.modal_rect.width - 40, 100)
        self.card_key_rect = pygame.Rect(self.modal_rect.x + 20, self.modal_rect.y + 180, self.modal_rect.width - 40, 100)
        self.card_potion_rect = pygame.Rect(self.modal_rect.x + 20, self.modal_rect.y + 292, self.modal_rect.width - 40, 100)

        # Tombol Aksi per Card
        self.btn_gear_rect = pygame.Rect(self.card_gear_rect.right - 146, self.card_gear_rect.y + 32, 130, 36)
        self.btn_key_rect = pygame.Rect(self.card_key_rect.right - 146, self.card_key_rect.y + 32, 130, 36)
        self.btn_potion_rect = pygame.Rect(self.card_potion_rect.right - 146, self.card_potion_rect.y + 32, 130, 36)

    @property
    def visible(self) -> bool:
        return self.is_open

    def open(self):
        self.is_open = True
        self.status_msg = "Pilih aksi yang ingin dilakukan di bengkel."
        self.status_color = config.CYAN

    def close(self):
        self.is_open = False

    def toggle(self):
        if self.is_open:
            self.close()
        else:
            self.open()

    def equip_best_gear(self, world_state: Any) -> Tuple[bool, str]:
        """Memasang perlengkapan tempur terbaik yang dimiliki hero di tas."""
        inv = getattr(world_state, "inventory", None)
        if not inv:
            return False, "Inventori tidak ditemukan!"

        # Prioritas Senjata
        weapon_priority = ["Tongkat Api", "Kapak Berat", "Belati Cepat", "Pedang Biasa"]
        selected_weapon = None
        for w in weapon_priority:
            if inv.has_item(w, 1):
                selected_weapon = w
                break
        if not selected_weapon:
            selected_weapon = "Pedang Biasa"
            inv.add_item("Pedang Biasa", 1)

        # Prioritas Zirah
        armor_priority = ["Besi", "Kulit", "Kain"]
        selected_armor = None
        for a in armor_priority:
            if inv.has_item(a, 1):
                selected_armor = a
                break
        if not selected_armor:
            selected_armor = "Kain"
            inv.add_item("Kain", 1)

        loadout = {
            "weapon": selected_weapon,
            "armor": selected_armor,
            "shield": None,
            "accessory": None
        }

        res = world_actions.equip_loadout(world_state, loadout)
        if res.success:
            pddl_map = {
                "Pedang Biasa": "sword_basic", "Belati Cepat": "weapon_dagger",
                "Kapak Berat": "weapon_axe", "Tongkat Api": "fire_staff",
                "Kain": "cloth_armor", "Kulit": "armor_leather", "Besi": "armor_iron"
            }
            world_state.equipped_weapon = pddl_map.get(selected_weapon, "sword_basic")
            world_state.equipped_armor = pddl_map.get(selected_armor, "cloth_armor")
            world_state.equipped_ok = True
            return True, f"Loadout berhasil dipasang: {selected_weapon} & {selected_armor}!"
        return False, res.message

    def handle_event(self, event: pygame.event.Event, world_state: Any) -> Tuple[bool, Optional[str]]:
        """
        Menangani interaksi keyboard dan mouse pada jendela bengkel.
        Mengembalikan (handled, log_message).
        """
        if not self.is_open:
            return False, None

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_e):
                self.close()
                return True, None
            elif event.key == pygame.K_1:
                ok, msg = self.equip_best_gear(world_state)
                self.status_msg = msg
                self.status_color = config.GREEN if ok else config.RED
                return True, msg
            elif event.key == pygame.K_2:
                res = world_actions.craft_key(world_state)
                self.status_msg = res.message
                self.status_color = config.GREEN if res.success else config.YELLOW
                return True, res.message
            elif event.key == pygame.K_3:
                res = world_actions.craft_potion(world_state)
                self.status_msg = res.message
                self.status_color = config.GREEN if res.success else config.YELLOW
                return True, res.message

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mx, my = event.pos
                if self.close_btn_rect.collidepoint(mx, my):
                    self.close()
                    return True, None

                # Klik Pasang Gear
                if self.btn_gear_rect.collidepoint(mx, my):
                    ok, msg = self.equip_best_gear(world_state)
                    self.status_msg = msg
                    self.status_color = config.GREEN if ok else config.RED
                    return True, msg

                # Klik Tempa Kunci
                if self.btn_key_rect.collidepoint(mx, my):
                    res = world_actions.craft_key(world_state)
                    self.status_msg = res.message
                    self.status_color = config.GREEN if res.success else config.YELLOW
                    return True, res.message

                # Klik Racik Potion
                if self.btn_potion_rect.collidepoint(mx, my):
                    res = world_actions.craft_potion(world_state)
                    self.status_msg = res.message
                    self.status_color = config.GREEN if res.success else config.YELLOW
                    return True, res.message

        return True, None

    def draw(self, screen: pygame.Surface, world_state: Any):
        """Merender jendela modal bengkel tempa dan crafting."""
        if not self.is_open:
            return

        inv = getattr(world_state, "inventory", None)
        equipped = getattr(inv, "equipped", {}) if inv else {}
        is_equipped = bool(equipped.get("weapon") or getattr(world_state, "equipped_ok", False))
        curr_weapon = equipped.get("weapon") or "Pedang Biasa"
        curr_armor = equipped.get("armor") or "Kain"

        # Dimmer background
        dimmer = pygame.Surface((1024, 768), pygame.SRCALPHA)
        dimmer.fill((0, 0, 0, 160))
        screen.blit(dimmer, (0, 0))

        # Panel Utama
        pygame.draw.rect(screen, (34, 34, 56), self.modal_rect, border_radius=10)
        pygame.draw.rect(screen, config.GOLD, self.modal_rect, 2, border_radius=10)

        # Header Title & Close Button
        title_txt = self.font_title.render("BENGKEL TEMPA & PERLENGKAPAN", True, config.GOLD)
        screen.blit(title_txt, (self.modal_rect.x + 24, self.modal_rect.y + 16))
        sub_txt = self.font_xs.render("Tempa Kunci Segel, Racik Ramuan, & Pasang Perlengkapan Tempur", True, (160, 175, 200))
        screen.blit(sub_txt, (self.modal_rect.x + 24, self.modal_rect.y + 40))

        # Close [X] Button
        pygame.draw.rect(screen, (54, 40, 50), self.close_btn_rect, border_radius=4)
        pygame.draw.rect(screen, (220, 100, 100), self.close_btn_rect, 1, border_radius=4)
        x_surf = self.font_body.render("X", True, (240, 140, 140))
        screen.blit(x_surf, x_surf.get_rect(center=self.close_btn_rect.center))

        # Koin Hero di pojok kanan atas
        coins = getattr(world_state, "coins", 0)
        coin_icon = get_asset_catalog().get_generated_icon("coin", scale=1)
        cx = self.modal_rect.right - 150
        cy = self.modal_rect.y + 18
        screen.blit(coin_icon, (cx, cy))
        screen.blit(self.font_body.render(f": {coins} Koin", True, config.GOLD), (cx + 20, cy))

        # ======================================================================
        # CARD 1: PASANG PERLENGKAPAN TEMPUR (GEAR)
        # ======================================================================
        pygame.draw.rect(screen, (44, 48, 72), self.card_gear_rect, border_radius=8)
        pygame.draw.rect(screen, (80, 180, 240) if is_equipped else (240, 180, 60), self.card_gear_rect, 1, border_radius=8)

        sw_icon = get_asset_catalog().get_generated_icon("sword", scale=1)
        screen.blit(sw_icon, (self.card_gear_rect.x + 14, self.card_gear_rect.y + 18))
        screen.blit(self.font_card_title.render("[1] Pasang Gear (Loadout Tempur)", True, (255, 255, 255)), (self.card_gear_rect.x + 40, self.card_gear_rect.y + 16))

        if is_equipped:
            eq_desc = f"Terpasang: {curr_weapon} (Senjata) + {curr_armor} (Zirah)"
            eq_col = (130, 245, 170)
        else:
            eq_desc = f"Tersedia di Tas: {curr_weapon} & {curr_armor} (Belum Terpasang)"
            eq_col = (255, 200, 100)
        screen.blit(self.font_body.render(eq_desc, True, eq_col), (self.card_gear_rect.x + 40, self.card_gear_rect.y + 40))
        screen.blit(self.font_xs.render("Wajib dipasang sebelum ekspedisi tempur menghadapi boss", True, (160, 175, 195)), (self.card_gear_rect.x + 40, self.card_gear_rect.y + 64))

        # Tombol Card 1
        btn_g_bg = (24, 70, 40) if is_equipped else (30, 80, 120)
        btn_g_border = (70, 220, 130) if is_equipped else (100, 200, 255)
        btn_g_txt = "[PASANG ULANG]" if is_equipped else "[PASANG GEAR]"
        pygame.draw.rect(screen, btn_g_bg, self.btn_gear_rect, border_radius=6)
        pygame.draw.rect(screen, btn_g_border, self.btn_gear_rect, 1, border_radius=6)
        bg_t = self.font_btn.render(btn_g_txt, True, btn_g_border)
        screen.blit(bg_t, bg_t.get_rect(center=self.btn_gear_rect.center))

        # ======================================================================
        # CARD 2: TEMPA KUNCI SEGEL BOS
        # ======================================================================
        pygame.draw.rect(screen, (44, 48, 72), self.card_key_rect, border_radius=8)
        wood_c = inv.get_item_count("wood") if inv else 0
        rock_c = inv.get_item_count("rock") if inv else 0
        has_key = inv.has_item("key", 1) or inv.has_item("gate_key", 1) if inv else False
        gate_open = getattr(getattr(world_state, "gate", None), "is_open", False)
        can_craft_key = (wood_c >= 1 and rock_c >= 1 and not has_key and not gate_open)

        pygame.draw.rect(screen, (70, 220, 130) if can_craft_key else (70, 75, 110), self.card_key_rect, 1, border_radius=8)
        hm_icon = get_asset_catalog().get_generated_icon("hammer", scale=1)
        screen.blit(hm_icon, (self.card_key_rect.x + 14, self.card_key_rect.y + 18))
        screen.blit(self.font_card_title.render("[2] Tempa Kunci Segel Bos", True, (255, 255, 255)), (self.card_key_rect.x + 40, self.card_key_rect.y + 16))

        if has_key or gate_open:
            k_desc = "Kunci Segel sudah siap / Gerbang Reruntuhan telah terbuka!"
            k_col = (130, 245, 170)
        else:
            k_desc = f"Bahan: 1x Kayu ({wood_c}/1) + 1x Batu ({rock_c}/1)"
            k_col = (130, 245, 170) if (wood_c >= 1 and rock_c >= 1) else (255, 140, 140)
        screen.blit(self.font_body.render(k_desc, True, k_col), (self.card_key_rect.x + 40, self.card_key_rect.y + 40))
        screen.blit(self.font_xs.render("Dibutuhkan untuk membuka gerbang batu Reruntuhan Obsidian", True, (160, 175, 195)), (self.card_key_rect.x + 40, self.card_key_rect.y + 64))

        # Tombol Card 2
        btn_k_bg = (30, 70, 45) if can_craft_key else (35, 38, 52)
        btn_k_border = (70, 220, 130) if can_craft_key else (80, 85, 105)
        btn_k_txt = "[SUDAH ADA]" if (has_key or gate_open) else ("[TEMPA KUNCI]" if can_craft_key else "[BAHAN KURANG]")
        pygame.draw.rect(screen, btn_k_bg, self.btn_key_rect, border_radius=6)
        pygame.draw.rect(screen, btn_k_border, self.btn_key_rect, 1, border_radius=6)
        bk_t = self.font_btn.render(btn_k_txt, True, btn_k_border)
        screen.blit(bk_t, bk_t.get_rect(center=self.btn_key_rect.center))

        # ======================================================================
        # CARD 3: RACIK HEALTH POTION
        # ======================================================================
        pygame.draw.rect(screen, (44, 48, 72), self.card_potion_rect, border_radius=8)
        radish_c = inv.get_item_count("radish") if inv else 0
        bottle_c = inv.get_item_count("bottle_empty") if inv else 0
        potion_c = inv.get_item_count("potion_red") if inv else 0
        can_craft_potion = (radish_c >= 1 and bottle_c >= 1)

        pygame.draw.rect(screen, (70, 220, 130) if can_craft_potion else (70, 75, 110), self.card_potion_rect, 1, border_radius=8)
        pt_icon = get_asset_catalog().get_generated_icon("sandtimer", scale=1)
        screen.blit(pt_icon, (self.card_potion_rect.x + 14, self.card_potion_rect.y + 18))
        screen.blit(self.font_card_title.render("[3] Racik Health Potion", True, (255, 255, 255)), (self.card_potion_rect.x + 40, self.card_potion_rect.y + 16))

        p_desc = f"Bahan: 1x Lobak ({radish_c}/1) + 1x Botol Kosong ({bottle_c}/1) | Potion di Tas: {potion_c}"
        p_col = (130, 245, 170) if can_craft_potion else (255, 140, 140)
        screen.blit(self.font_body.render(p_desc, True, p_col), (self.card_potion_rect.x + 40, self.card_potion_rect.y + 40))
        screen.blit(self.font_xs.render("Memulihkan HP hero saat bertarung melawan musuh atau boss", True, (160, 175, 195)), (self.card_potion_rect.x + 40, self.card_potion_rect.y + 64))

        # Tombol Card 3
        btn_p_bg = (30, 70, 45) if can_craft_potion else (35, 38, 52)
        btn_p_border = (70, 220, 130) if can_craft_potion else (80, 85, 105)
        btn_p_txt = "[RACIK POTION]" if can_craft_potion else "[BAHAN KURANG]"
        pygame.draw.rect(screen, btn_p_bg, self.btn_potion_rect, border_radius=6)
        pygame.draw.rect(screen, btn_p_border, self.btn_potion_rect, 1, border_radius=6)
        bp_t = self.font_btn.render(btn_p_txt, True, btn_p_border)
        screen.blit(bp_t, bp_t.get_rect(center=self.btn_potion_rect.center))

        # ======================================================================
        # FOOTER: STATUS PESAN & PETUNJUK
        # ======================================================================
        msg_s = self.font_body.render(self.status_msg, True, self.status_color)
        screen.blit(msg_s, (self.modal_rect.x + 24, self.modal_rect.bottom - 42))

        hint_s = self.font_xs.render("Gunakan tombol [1..3] atau Klik Mouse · Tekan [E] atau [ESC] untuk Tutup", True, (160, 175, 200))
        screen.blit(hint_s, (self.modal_rect.x + 24, self.modal_rect.bottom - 22))

