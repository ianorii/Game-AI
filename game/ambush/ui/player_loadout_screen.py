"""game/ambush/ui/player_loadout_screen.py - Layar pilih loadout (PREP_PLAYER).

Panel tengah: 2 slot, navigasi Atas/Bawah pilih slot, Kiri/Kanan ganti item,
Enter konfirmasi, Esc batal. Murni menggambar + input; tanpa logika solver.
"""
from __future__ import annotations

from typing import List, Tuple

import pygame

from game.ambush.player_loadout import (
    AVAILABLE_ITEMS,
    LOADOUT_SLOTS,
    PlayerLoadout,
    describe_item,
    loadout_power,
)

PANEL_BG = (20, 26, 38, 238)
EDGE = (240, 196, 96)
TEXT = (232, 238, 248)
DIM = (150, 165, 190)
GREEN = (140, 240, 170)


class PlayerLoadoutScreen:
    """State layar pilihan loadout player."""

    def __init__(self, loadout: PlayerLoadout | None = None):
        items: List[str] = list(loadout.items) if loadout else ["NONE"] * LOADOUT_SLOTS
        # Slot mulai terisi contoh menarik (Sword + Shield) agar demo hidup.
        if all(i == "NONE" for i in items):
            defaults = ["Iron Sword", "Heavy Shield"]
            items = [defaults[i] if i < len(defaults)
                     and defaults[i] in AVAILABLE_ITEMS else "NONE"
                     for i in range(LOADOUT_SLOTS)]
        self.items = items
        self.slot = 0
        # Kursor item per slot (indeks ke [NONE + AVAILABLE]).
        self.options: List[List[str]] = [["NONE", *AVAILABLE_ITEMS]
                                         for _ in range(LOADOUT_SLOTS)]
        self.idx = [self.options[i].index(self.items[i]
                                          if self.items[i] in self.options[i]
                                          else "NONE")
                    for i in range(LOADOUT_SLOTS)]

    def handle_key(self, key: int) -> str | None:
        """Kembalikan 'confirm' / 'cancel' atau None."""
        if key in (pygame.K_UP, pygame.K_w):
            self.slot = (self.slot - 1) % LOADOUT_SLOTS
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.slot = (self.slot + 1) % LOADOUT_SLOTS
        elif key in (pygame.K_LEFT, pygame.K_a):
            self.idx[self.slot] = (self.idx[self.slot] - 1) % len(self.options[self.slot])
            self.items[self.slot] = self.options[self.slot][self.idx[self.slot]]
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.idx[self.slot] = (self.idx[self.slot] + 1) % len(self.options[self.slot])
            self.items[self.slot] = self.options[self.slot][self.idx[self.slot]]
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            return "confirm"
        elif key == pygame.K_ESCAPE:
            return "cancel"
        return None

    def result(self) -> PlayerLoadout:
        """Loadout hasil pilihan."""
        return PlayerLoadout(items=tuple(self.items))

    def power(self) -> float:
        """Kekuatan pilihan saat ini (untuk ringkasan)."""
        return loadout_power(self.result())

    def draw(self, screen: pygame.Surface, font: pygame.font.Font,
             target: float) -> None:
        """Gambar panel tengah di atas adegan beku."""
        w, h = screen.get_size()
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((4, 6, 12, 150))
        screen.blit(veil, (0, 0))
        pw, ph = min(560, w - 80), 300
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.rect(panel, PANEL_BG, panel.get_rect(), border_radius=14)
        pygame.draw.rect(panel, (*EDGE, 235), panel.get_rect(), 2,
                         border_radius=14)
        pad = 18
        y = pad
        title = font.render("PERSIAPAN DUEL — pilih loadout-mu (2 slot)",
                            True, EDGE)
        panel.blit(title, (pad, y))
        y += title.get_height() + 4
        sub = font.render(f"Target kesulitan NPC: {target:.2f} | "
                          f"Kekuatan: {self.power():.2f}", True, DIM)
        panel.blit(sub, (pad, y))
        y += sub.get_height() + 12
        for i in range(LOADOUT_SLOTS):
            sel = (i == self.slot)
            row = pygame.Rect(pad, y, pw - pad * 2, 64)
            bg = (34, 44, 62) if sel else (22, 26, 34)
            pygame.draw.rect(panel, bg, row, border_radius=9)
            pygame.draw.rect(panel, EDGE if sel else (60, 70, 90), row,
                             2 if sel else 1, border_radius=9)
            name = self.items[i]
            left = font.render(f"Slot {i + 1}: < {name} >", True,
                               TEXT if sel else DIM)
            panel.blit(left, (row.x + 12, row.y + 8))
            desc = font.render(describe_item(name), True, GREEN)
            panel.blit(desc, (row.x + 12, row.y + 8 + left.get_height() + 2))
            y += 72
        hint = font.render("Atas/Bawah slot | Kiri/Kanan item | "
                           "Enter mulai | Esc batal", True, DIM)
        panel.blit(hint, (pad, ph - hint.get_height() - 12))
        screen.blit(panel, ((w - pw) // 2, (h - ph) // 2))
