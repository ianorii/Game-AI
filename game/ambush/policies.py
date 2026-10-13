"""game/ambush/policies.py - SATU sumber kebijakan pemain (Langkah 0).

Semua kebijakan pemain di kode (autoplay, sim ringan, sim penuh, skrip
ukur balance, run_all) WAJIB lewat sini agar tidak ada pola serupa typo
``key < key`` yang membuat greedy selalu ATTACK.

Kebijakan:
- greedy: 1-ply, NPC memaksimumkan eval, player meminimumkan.
- hemat (baru, BERBEDA dari greedy): greedy + veto potion. Potion hanya
  bila HP < 40% DAN (duel terakhir ATAU potion tersisa > sisa duel).
  Cadangan untuk sisa antrean -> veto benar-benar mengikat di duel
  awal antrean panjang, longgar di duel terakhir / duel tunggal.
- depth4: minimax depth-4 kedua sisi (think, root_is_npc sesuai giliran).
"""
from __future__ import annotations

from typing import Optional

HEMAT_HP_FRAC = 0.40


def greedy_action(ai, state, is_npc: bool) -> Optional[str]:
    """Greedy 1-ply: pilih aksi dengan eval terbaik pihak yang giliran."""
    best, best_key = None, None
    for a in state.legal_actions(is_npc):
        child = state.apply_action(is_npc, a)
        key = ai.evaluate_state(child)
        if best_key is None or (key > best_key if is_npc
                                else key < best_key):
            best, best_key = a, key
    return best


def hemat_veto(state, duel_last: bool, duels_left: int, max_hp: int) -> bool:
    """True bila veto hemat MELARANG potion (paksa ATTACK/DEFEND).

    Potion diizinkan hanya bila HP < 40% DAN (duel terakhir ATAU
    potion tersisa melebihi sisa duel). Selain itu -> veto mengikat.
    """
    if not (state.player_hp < HEMAT_HP_FRAC * max_hp):
        return True
    if duel_last or state.player_potions > duels_left:
        return False
    return True


def think_policy(ai, state, is_npc: bool, policy: str,
                 duel_last: bool = True, duels_left: int = 0,
                 max_hp: int = 100) -> Optional[str]:
    """Pilih aksi untuk satu giliran: greedy / hemat-baru / depth4."""
    if policy == "depth4":
        return ai.think(state, run_baseline=False,
                        root_is_npc=is_npc)["best_action"]
    a = greedy_action(ai, state, is_npc)
    if (policy in ("conserve", "hemat") and not is_npc and a == "POTION"
            and hemat_veto(state, duel_last, duels_left, max_hp)):
        legal = state.legal_actions(False)
        return "ATTACK" if "ATTACK" in legal else "DEFEND"
    return a
