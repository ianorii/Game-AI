"""game/ambush/ui/battle_hud.py - HUD konfigurasi duel (tombol H).

Dua panel simetris: kiri PLAYER (HP + loadout + efek angka), kanan NPC
(HP + squad + buff angka). Murni membaca Buff yang SAMA dengan battle
(tidak menghitung ulang sendiri) sehingga angka HUD == angka battle.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from game.ambush.buff import Buff

PANEL_BG = (20, 26, 38, 225)
PANEL_EDGE = (58, 72, 98)
TEXT = (232, 238, 248)
DIM = (150, 165, 190)
GREEN = (140, 240, 170)
RED = (240, 120, 120)
GOLD = (240, 196, 96)


def buff_lines_short(buff: Buff, who: str) -> List[Tuple[str, tuple]]:
    """Baris efek buff dalam angka untuk HUD (maks 4 baris)."""
    out: List[Tuple[str, tuple]] = []

    def signed(v: int) -> str:
        return f"{v:+d}"

    if buff.hp:
        out.append((f"{signed(buff.hp)} Max HP", GREEN))
    if buff.atk or buff.spec:
        out.append((f"{signed(buff.atk)} ATK / {signed(buff.spec)} SPEC",
                    GREEN))
    if buff.armor:
        out.append((f"-{buff.armor * 100:.0f}% dmg diterima", GREEN))
    if buff.regen:
        out.append((f"+{buff.regen} HP/giliran", GREEN))
    if buff.chip:
        out.append((f"{buff.chip} chip dmg/ronde", RED if who == "npc"
                    else GREEN))
    if buff.weaken:
        out.append((f"heal musuh -{buff.weaken * 100:.0f}%", RED if who == "npc"
                    else GREEN))
    return out[:4] or [("tanpa buff", DIM)]


class BattleConfigHUD:
    """HUD lipat (tombol H) untuk konfigurasi duel."""

    def __init__(self) -> None:
        self.visible = True
        self.flash_player = 0.0
        self.flash_npc = 0.0

    def toggle(self) -> None:
        """Tampilkan/sembunyikan HUD."""
        self.visible = not self.visible

    def ping(self, side: str) -> None:
        """Highlight sesaat saat buff sisi itu terpicu (dari battle log)."""
        if side == "player":
            self.flash_player = 0.6
        else:
            self.flash_npc = 0.6

    def tick(self, dt: float) -> None:
        """Kurangi timer highlight."""
        self.flash_player = max(0.0, self.flash_player - dt)
        self.flash_npc = max(0.0, self.flash_npc - dt)

    def draw(self, screen: pygame.Surface, font: pygame.font.Font,
             player_items: List[str], npc_members: List[Tuple[str, str]],
             player_buff: Optional[Buff], npc_buff: Optional[Buff],
             turn_no: int, target: float, sim_rate: str,
             queue_view: Optional[dict] = None,
             duel_label: str = "", y_top: Optional[int] = None) -> None:
        """Strip info umum + strip antrean (ramping, tak menutupi menu).

        Rincian anggota/buff menyatu di dua panel stat simetris
        (BattleSystem._draw_stats_panel). H toggle semua info tahap 3.
        y_top = bawah blok judul (default warisan 10.5% tinggi).
        """
        if not self.visible:
            return
        w, h = screen.get_size()
        info = font.render(
            f"Giliran {turn_no} | target {target:.2f} (menang ~separuh duel)"
            f" | sim {sim_rate or '-'} | [H] info buff", True, GOLD)
        y_info = int(h * 0.105) if y_top is None else y_top
        screen.blit(info, ((w - info.get_width()) // 2, y_info))
        if queue_view is not None:
            self._strip(screen, font, queue_view, duel_label,
                        y_info + info.get_height() + 4, w)

    def _strip(self, screen: pygame.Surface, font: pygame.font.Font,
               view: dict, duel_label: str, y: int, w: int) -> None:
        """Strip antrean tengah-atas: selesai v | tampil > | tunggu ...."""
        order = view.get("order", [])
        idx = view.get("idx", 0)
        done = view.get("done", [])
        bits = []
        for i, (role, _item) in enumerate(order):
            if i < len(done) and done[i]:
                mark = "v"
            elif i == idx:
                mark = ">"
            else:
                mark = "..."
            bits.append(f"{i + 1} {mark} {role}")
        text = " | ".join(bits)
        if duel_label:
            text = f"{duel_label}   {text}"
        surf = font.render(text, True, TEXT)
        max_w = min(w - 40, surf.get_width())
        if surf.get_width() > max_w:  # ellipsis agar tak terpotong layar
            txt = text
            while txt and font.size(txt + "...")[0] > max_w:
                txt = txt[:-1]
            surf = font.render(txt + "...", True, TEXT)
        bg = pygame.Surface((surf.get_width() + 24, surf.get_height() + 10),
                            pygame.SRCALPHA)
        pygame.draw.rect(bg, PANEL_BG, bg.get_rect(), border_radius=9)
        pygame.draw.rect(bg, PANEL_EDGE, bg.get_rect(), 1, border_radius=9)
        screen.blit(bg, ((w - bg.get_width()) // 2, y))
        screen.blit(surf, ((w - surf.get_width()) // 2, y + 5))

    def _panel(self, screen: pygame.Surface, font: pygame.font.Font,
               x: int, y: int, pw: int, ph: int, title: str, edge: tuple,
               rows: List[str], buff: Optional[Buff], flash: bool) -> None:
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.rect(panel, PANEL_BG, panel.get_rect(), border_radius=12)
        pygame.draw.rect(panel, (*((255, 255, 160) if flash else edge), 235),
                         panel.get_rect(), 3 if flash else 2,
                         border_radius=12)
        pad = 12
        head = font.render(title, True, edge)
        panel.blit(head, (pad, 8))
        cy = 8 + head.get_height() + 4
        for row in rows[:3]:
            surf = font.render(str(row)[:38], True, TEXT)
            panel.blit(surf, (pad, cy))
            cy += surf.get_height() + 2
        if buff is not None:
            for line, col in buff_lines_short(buff, "x"):
                surf = font.render(line[:38], True, col)
                panel.blit(surf, (pad, cy))
                cy += surf.get_height() + 2
                if cy > ph - 16:
                    break
        screen.blit(panel, (x, y))
