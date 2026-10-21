"""game/ambush/ui/transition.py - Layar hasil duel antar-antrean (Fase 5).

Isi panel (kalimat pemain, tanpa singkatan teknis):
  1. HASIL DUEL n/k + lencana MENANG / KALAH / KABUR.
  2. Lawan yang baru selesai + sisa HP/potion pemain.
  3. Musuh berikutnya (nama + item + HP + efek) ATAU penutup pertemuan.
  4. Petunjuk "Enter = ...".

PENTING: panel ini TIDAK lanjut otomatis (dulu jeda 1.5 dtk). Timer/Enter
ditangani main.py: Enter memulai duel berikutnya atau menutup pertemuan.

Catatan: baris "Kamu masuk duel berikutnya dengan HP ..." ditampilkan lagi
dengan hp_next/pot_next (lihat main.py). Darah MEMANG terbawa antar-duel
(start_queue_duel: player_hp=run.hp, hasil apply_rest di QueueRun.record),
jadi angka di baris itu nyata, bukan angka menyesatkan seperti dulu saat
tiap duel masih dipaksa mulai dengan darah penuh (player_hp=MAX_HP).
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import pygame

from game.ambush.types import display_role

EDGE = (240, 196, 96)
TEXT = (232, 238, 248)
DIM = (150, 165, 190)
GREEN = (140, 240, 170)
RED = (240, 120, 120)

Seg = Tuple[str, tuple]
Row = Tuple[int, List[Seg]]  # (indent piksel, potongan teks berwarna)
_SEP = ("sep", None)         # penanda baris pemisah


def _wrap_segments(text: str, font: pygame.font.Font, first_w: int,
                   rest_w: int) -> List[str]:
    """Pecah teks per kata: baris pertama <= first_w, lanjutan <= rest_w."""
    lines: List[str] = []
    cur = ""
    width = first_w
    for word in text.split():
        trial = f"{cur} {word}".strip() if cur else word
        if not cur or font.size(trial)[0] <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
            width = rest_w
    if cur:
        lines.append(cur)
    return lines or [""]


def draw_transition(
    screen: pygame.Surface,
    font: pygame.font.Font,
    *,
    duel_no: int,
    k: int,
    result: str = "menang",          # "menang" | "kalah" | "kabur"
    prev_role: Optional[str] = None,
    prev_item: Optional[str] = None,
    hp_after: Optional[int] = None,
    cap: int = 100,
    potions: int = 0,
    next_role: Optional[str] = None,
    next_item: Optional[str] = None,
    hp_next: Optional[int] = None,
    pot_next: Optional[int] = None,
    rest_heal: int = 0,
    foe_hp: Optional[int] = None,
    foe_lines: Optional[Sequence[str]] = None,
    finished: bool = False,
    hint: Optional[str] = None,
) -> None:
    """Gambar panel hasil duel + info musuh berikutnya di tengah layar.

    Args:
        duel_no: nomor duel yang BARU selesai (1..k).
        result: hasil duel terakhir ("menang"/"kalah"/"kabur") -> lencana.
        hp_after/potions: sisa HP/potion pemain setelah duel (dari catatan).
        hp_next/pot_next: HP & potion yang DIPAKAI duel berikutnya (terbawa
            lewat apply_rest); rest_heal = tambahan heal istirahat antar-duel.
        next_role/next_item: musuh berikutnya (None bila pertemuan berakhir).
        finished: True bila pertemuan berakhir (menang semua / kalah / kabur).
    """
    w, h = screen.get_size()
    veil = pygame.Surface((w, h), pygame.SRCALPHA)
    veil.fill((4, 6, 12, 150))
    screen.blit(veil, (0, 0))

    # Lebar panel mengikuti ukuran font agar teks tidak terpotong di
    # resolusi besar (620 px saat font tinggi 15, mis. 1280x720).
    pw = min(w - 60, max(620, int(620 * font.get_height() / 15)))
    pad = 20
    line_h = font.get_height() + 5
    sep_h = 12
    inner = pw - pad * 2

    rows: List[Row] = []
    badge = {"menang": ("MENANG", GREEN), "kalah": ("KALAH", RED),
             "kabur": ("KABUR", DIM)}.get(str(result).lower(),
                                          ("SELESAI", DIM))
    rows.append((0, [(f"HASIL DUEL {duel_no}/{k}", EDGE), ("    ", TEXT),
                     (badge[0], badge[1])]))
    if prev_role:
        segs: List[Seg] = [("Melawan tadi: ", DIM),
                           (display_role(prev_role), TEXT)]
        if prev_item and prev_item != "NONE":
            segs.append((f" [{prev_item}]", EDGE))
        rows.append((0, segs))
    if hp_after is not None:
        rows.append((0, [("Sisa HP kamu setelah duel: ", DIM),
                         (f"{hp_after}/{cap}", TEXT),
                         (f"    Potion {potions}", DIM)]))
    rows.append(_SEP)

    if next_role:
        segs = [(f"DUEL BERIKUTNYA ({duel_no + 1}/{k}): ", DIM),
                (display_role(next_role), TEXT)]
        if next_item and next_item != "NONE":
            segs.append((f" [{next_item}]", EDGE))
        rows.append((0, segs))
        if hp_next is not None:
            # HP terbawa: nyata dipakai di duel berikutnya (bukan angka
            # rekap saja), makanya baris ini boleh tampil lagi.
            nsegs: List[Seg] = [("Kamu masuk duel berikutnya dengan HP ", DIM),
                                (f"{hp_next}/{cap}", TEXT)]
            if rest_heal > 0:
                nsegs.append((f" (istirahat +{rest_heal})", GREEN))
            nsegs.append((f"    Potion "
                          f"{pot_next if pot_next is not None else potions}",
                          DIM))
            rows.append((0, nsegs))
        if foe_hp is not None:
            rows.append((0, [("HP musuh: ", DIM),
                             (f"{foe_hp}/{foe_hp}", TEXT),
                             (" (selalu mulai penuh)", DIM)]))
        if foe_lines:
            # Bungkus ke lebar panel: baris pertama setelah label "Efek
            # lawan: ", baris lanjutan menjorok sejajar setelah label.
            prefix_w = font.size("Efek lawan: ")[0]
            text = "; ".join(str(t) for t in foe_lines)
            for i, line in enumerate(_wrap_segments(
                    text, font, max(80, inner - prefix_w),
                    max(80, inner - prefix_w))):
                if i == 0:
                    rows.append((0, [("Efek lawan: ", DIM), (line, GREEN)]))
                else:
                    rows.append((prefix_w, [(line, GREEN)]))
    elif finished and str(result).lower() == "menang":
        rows.append((0, [("ANTREAN TUNTAS!", GREEN)]))
        rows.append((0, [("Semua musuh di antrean sudah dikalahkan.", TEXT)]))
    elif finished:
        kabur = str(result).lower() == "kabur"
        rows.append((0, [("PERTEMUAN BERAKHIR",
                          DIM if kabur else RED)]))
        rows.append((0, [("Kamu kabur dari duel - antrean dihentikan."
                          if kabur else
                          "Kamu kalah - darah dipulihkan saat kembali "
                          "ke peta.", TEXT)]))

    if hint is None:
        hint = ("Enter = kembali ke peta" if finished
                else "Enter = lanjut ke duel berikutnya")
    hint_surf = font.render(hint, True, DIM)

    total_rows_h = sum(sep_h if r is _SEP else line_h for r in rows)
    ph = pad * 2 + total_rows_h + hint_surf.get_height() + 10
    panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pygame.draw.rect(panel, (20, 26, 38, 240), panel.get_rect(),
                     border_radius=14)
    pygame.draw.rect(panel, (*EDGE, 235), panel.get_rect(), 2,
                     border_radius=14)

    y = pad
    for row in rows:
        if row is _SEP:
            pygame.draw.line(panel, (70, 84, 110),
                             (pad, y + sep_h // 2), (pw - pad, y + sep_h // 2))
            y += sep_h
            continue
        indent, segs = row
        x = pad + indent
        for text, col in segs:
            surf = font.render(text, True, col)
            panel.blit(surf, (x, y))
            x += surf.get_width()
        y += line_h

    panel.blit(hint_surf, (pw - pad - hint_surf.get_width(),
                           ph - hint_surf.get_height() - pad + 2))
    screen.blit(panel, ((w - pw) // 2, (h - ph) // 2))
