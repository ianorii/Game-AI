"""game/ambush/ui/transition.py - Layar transisi antar-duel (Fase 5).

"MUSUH #n MAJU - HP x/y - Potion z". Murni menggambar; timer/Enter
ditangani main.py (durasi di config transition_hold_s).
"""
from __future__ import annotations

import pygame

EDGE = (240, 196, 96)
TEXT = (232, 238, 248)
DIM = (150, 165, 190)


def draw_transition(screen: pygame.Surface, font: pygame.font.Font,
                    duel_no: int, k: int, role: str, item: str, hp: int,
                    cap: int, potions: int, hold_s: float) -> None:
    """Gambar panel tengah transisi di atas adegan beku."""
    w, h = screen.get_size()
    veil = pygame.Surface((w, h), pygame.SRCALPHA)
    veil.fill((4, 6, 12, 150))
    screen.blit(veil, (0, 0))
    pw, ph = min(520, w - 80), 170
    panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pygame.draw.rect(panel, (20, 26, 38, 238), panel.get_rect(),
                     border_radius=14)
    pygame.draw.rect(panel, (*EDGE, 235), panel.get_rect(), 2,
                     border_radius=14)
    pad = 18
    title = font.render(f"MUSUH #{duel_no} MAJU  ({duel_no}/{k})", True, EDGE)
    panel.blit(title, (pad, pad))
    y = pad + title.get_height() + 6
    foe = font.render(f"{role} [{item}]", True, TEXT)
    panel.blit(foe, (pad, y))
    y += foe.get_height() + 6
    me = font.render(f"HP kamu: {hp}/{cap} - Potion {potions}", True, TEXT)
    panel.blit(me, (pad, y))
    y += me.get_height() + 8
    hint = font.render(f"Enter = lanjut (otomatis {hold_s:g} dtk)", True, DIM)
    panel.blit(hint, (pad, ph - hint.get_height() - 12))
    screen.blit(panel, ((w - pw) // 2, (h - ph) // 2))
