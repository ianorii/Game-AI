"""game/ambush/ui/battle_hud.py - HUD konfigurasi duel (tombol H).

Dua panel simetris: kiri PLAYER (HP + loadout + efek angka), kanan NPC
(HP + squad + buff angka). Murni membaca Buff yang SAMA dengan battle
(tidak menghitung ulang sendiri) sehingga angka HUD == angka battle.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pygame

from game.ambush.buff import Buff
from game.ambush.types import display_role

PANEL_BG = (20, 26, 38, 225)
PANEL_EDGE = (58, 72, 98)
TEXT = (232, 238, 248)
DIM = (150, 165, 190)
GREEN = (140, 240, 170)
RED = (240, 120, 120)
GOLD = (240, 196, 96)


def buff_lines_short(buff: Buff, who: str) -> List[Tuple[str, tuple]]:
    """Baris efek buff dengan kalimat ringkas untuk HUD (maks 4 baris).

    Ditulis dengan bahasa pemain, bukan istilah teknis: "Tahan damage 10%"
    (bukan "-10% dmg diterima"), "Damage pasti 1 tiap ronde" (bukan "chip").
    who="npc" mewarnai MERAH efek yang menyerang pemain (chip/weaken);
    efek netral/positif tetap hijau, "tanpa efek khusus" abu-abu.
    """
    out: List[Tuple[str, tuple]] = []

    def signed(v: int) -> str:
        return f"{v:+d}"

    if buff.hp:
        out.append((f"Darah maks {signed(buff.hp)}", GREEN))
    if buff.atk and buff.spec:
        out.append((f"Serangan {signed(buff.atk)}, spesial {signed(buff.spec)}",
                    GREEN))
    elif buff.atk:
        out.append((f"Serangan {signed(buff.atk)}", GREEN))
    elif buff.spec:
        out.append((f"Spesial {signed(buff.spec)}", GREEN))
    if buff.armor:
        out.append((f"Tahan damage {buff.armor * 100:.0f}%", GREEN))
    if buff.regen:
        out.append((f"Pulih {buff.regen} HP tiap giliran", GREEN))
    if buff.chip:
        out.append((f"Damage pasti {buff.chip} tiap ronde",
                    RED if who == "npc" else GREEN))
    if buff.weaken:
        target = "kamu" if who == "npc" else "musuh"
        out.append((f"Heal {target} -{buff.weaken * 100:.0f}%",
                    RED if who == "npc" else GREEN))
    return out[:4] or [("tanpa efek khusus", DIM)]


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
             duel_label: str = "", y_top: Optional[int] = None,
             item_sprites: Optional[Dict[str, pygame.Surface]] = None) -> None:
        """Info umum + baris antrean (ramping, tak menutupi menu).

        Baris antrean ditulis sebagai kalimat: "Sekarang melawan: X |
        Berikutnya: Y | Sudah kalah: ..." agar pemain langsung paham.
        Rincian anggota/buff menyatu di dua panel stat simetris
        (BattleSystem._draw_stats_panel). H toggle semua info tahap 3.
        y_top = bawah blok judul (default warisan 10.5% tinggi).
        """
        if not self.visible:
            return
        w, h = screen.get_size()
        info = font.render(
            f"Giliran {turn_no} | target {target:.2f} (menang ~separuh duel)"
            f" | prediksi {sim_rate or '-'} | [H] info efek", True, GOLD)
        y_info = int(h * 0.105) if y_top is None else y_top
        screen.blit(info, ((w - info.get_width()) // 2, y_info))
        bottom = y_info + info.get_height()
        if queue_view is not None:
            # Baris kalimat: sekarang melawan siapa, berikutnya siapa (rapi
            # dan mudah dipahami; pengganti strip bertanda v/>/...).
            line_y = y_info + info.get_height() + 6
            self._queue_line(screen, font, queue_view, line_y, w)
            bottom = line_y + font.get_height() + 2
        # content_bottom dipakai BattleSystem agar panel HP (kiri/kanan)
        # dimulai di bawah sidebar tengah, tidak menabrak teks tengah.
        self.content_bottom = bottom

    def _queue_line(self, screen: pygame.Surface, font: pygame.font.Font,
                    view: dict, y: int, w: int) -> None:
        """Baris tengah antrean: 'Sekarang melawan: X | Berikutnya: Y'.

        Nama role memakai nama aset 08_karakter; item berwarna emas. Bila
        terlalu lebar, bagian riwayat "Sudah kalah" (lalu "Berikutnya")
        dilepas agar tetap rapi di layar sempit.
        """
        order = view.get("order", [])
        idx = view.get("idx", 0)
        done = view.get("done", [])
        if not order or idx >= len(order):
            return
        groups: List[List[Tuple[str, tuple]]] = []
        role, item = order[idx]
        now: List[Tuple[str, tuple]] = [("Sekarang melawan: ", DIM),
                                        (display_role(role), TEXT)]
        if item and item != "NONE":
            now.append((f" [{item}]", GOLD))
        groups.append(now)
        if idx + 1 < len(order):
            nxt_role, nxt_item = order[idx + 1]
            nxt: List[Tuple[str, tuple]] = [("   |   Berikutnya: ", DIM),
                                            (display_role(nxt_role), TEXT)]
            if nxt_item and nxt_item != "NONE":
                nxt.append((f" [{nxt_item}]", GOLD))
            groups.append(nxt)
        else:
            groups.append([("   |   ini musuh terakhir di antrean", DIM)])
        beaten = [display_role(order[i][0])
                  for i, d in enumerate(done[:len(order)]) if d]
        if beaten:
            groups.append([("   |   Sudah kalah: ", DIM),
                           (", ".join(beaten), TEXT)])
        limit = w - 40

        def total_width(gs) -> int:
            return sum(font.size(t)[0] for g in gs for t, _c in g)

        while len(groups) > 1 and total_width(groups) > limit:
            groups.pop()
        segs = [seg for g in groups for seg in g]
        x = max(12, (w - total_width(groups)) // 2)
        for text, col in segs:
            surf = font.render(text, True, col)
            screen.blit(surf, (x, y))
            x += surf.get_width()

    def _panel(self, screen: pygame.Surface, font: pygame.font.Font,
               x: int, y: int, pw: int, ph: int, title: str, edge: tuple,
               rows: List[str], buff: Optional[Buff], flash: bool,
               item_sprites: Optional[Dict[str, pygame.Surface]] = None) -> None:
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
            # Ambil item name dari row (format: "Role [Item]")
            item_name = None
            row_text = str(row)[:38]
            if "[" in row_text and "]" in row_text:
                item_name = row_text.split("[")[1].split("]")[0]
            # Gambar ikon item di sebelah kiri teks
            icon_x = pad
            if item_sprites and item_name and item_name in item_sprites:
                icon = item_sprites[item_name]
                icon_rect = icon.get_rect()
                icon_rect.topleft = (icon_x, cy - 1)
                panel.blit(icon, icon_rect)
                icon_x += icon_rect.width + 6
            surf = font.render(row_text, True, TEXT)
            panel.blit(surf, (icon_x, cy))
            cy += surf.get_height() + 2
        if buff is not None:
            for line, col in buff_lines_short(buff, "x"):
                surf = font.render(line[:38], True, col)
                panel.blit(surf, (pad, cy))
                cy += surf.get_height() + 2
                if cy > ph - 16:
                    break
        screen.blit(panel, (x, y))
