"""game/ambush/flow/prep_state_machine.py - State machine persiapan duel.

Urutan eksplisit (tak ada fase terlewat otomatis):
EXPLORE -> PREP_PLAYER -> PREP_NPC_CSP -> PREP_NPC_LS -> PREP_REVIEW
-> BATTLE -> EXPLORE.

PREP_NPC_CSP/LS adalah satu runtime director yang dipompa bertahap;
pemisahannya membuat fase terlihat (overlay + tes), bukan run terpisah.
BATTLE mencakup 1 duel (BUFF) atau antrean ENEMY_1..k (SEQUENTIAL,
digerakkan queue_driver + layar TRANSITION).
"""
from __future__ import annotations

from typing import Dict, List

EXPLORE = "EXPLORE"
PREP_PLAYER = "PREP_PLAYER"
PREP_NPC_CSP = "PREP_NPC_CSP"
PREP_NPC_LS = "PREP_NPC_LS"
PREP_REVIEW = "PREP_REVIEW"
BATTLE = "BATTLE"
TRANSITION = "TRANSITION"

#: Transisi legal antar fase (dipakai tes + assert di main.py).
LEGAL: Dict[str, List[str]] = {
    EXPLORE: [PREP_PLAYER],
    PREP_PLAYER: [PREP_NPC_CSP, EXPLORE],  # Esc bisa batal kembali
    PREP_NPC_CSP: [PREP_NPC_LS],
    PREP_NPC_LS: [PREP_REVIEW],
    PREP_REVIEW: [BATTLE, PREP_NPC_CSP],  # G = susun ulang
    BATTLE: [TRANSITION, EXPLORE],  # TRANSITION = duel berikut antrean
    TRANSITION: [BATTLE, EXPLORE],
}


def is_legal(frm: str, to: str) -> bool:
    """True bila transisi fase diizinkan."""
    return to in LEGAL.get(frm, [])


def check_sequence(phases: List[str]) -> List[str]:
    """Kembalikan daftar pelanggaran urutan (kosong = benar)."""
    bad = []
    for a, b in zip(phases, phases[1:]):
        if not is_legal(a, b):
            bad.append(f"{a} -> {b} ilegal")
    return bad
