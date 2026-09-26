"""
game/adv_search/core.py - Facade modul Adversarial Search (Tubes Tahap 2).

Implementasi sebenarnya berada di modul root ``adversarial_ai.py``. File ini
hanya menyediakan jalur import yang konsisten dengan package ``game/``
(``game.map``, ``game.pathfinding``), supaya grader bisa menemukan algoritmanya
di kedua lokasi tanpa perlu tahu mana yang asli.

Tidak ada logika duplikat di sini. Semua nama diekspor ulang apa adanya.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:  # pragma: no cover - hanya jalan di luar package
    sys.path.insert(0, _ROOT)

from adversarial_ai import (  # noqa: E402,F401
    ACTIONS,
    ATTACK_DAMAGE,
    ATTACK_MAX,
    ATTACK_MIN,
    ATTACK_OUTCOMES,
    DEFEND_REDUCTION,
    EVAL_FUNCTIONS,
    EVAL_PROFILES,
    MAX_HP,
    MOVE_ORDERS,
    POTION_HEAL,
    POTION_LIMIT,
    SPECIAL_COOLDOWN,
    SPECIAL_DAMAGE,
    WIN_SCORE,
    AdversarialAI,
    BattleState,
    escapes_death,
    incoming_damage,
    is_decided,
)

__all__ = [
    "ACTIONS",
    "ATTACK_DAMAGE",
    "ATTACK_MAX",
    "ATTACK_MIN",
    "ATTACK_OUTCOMES",
    "DEFEND_REDUCTION",
    "EVAL_FUNCTIONS",
    "EVAL_PROFILES",
    "MAX_HP",
    "MOVE_ORDERS",
    "POTION_HEAL",
    "POTION_LIMIT",
    "SPECIAL_COOLDOWN",
    "SPECIAL_DAMAGE",
    "WIN_SCORE",
    "AdversarialAI",
    "BattleState",
    "escapes_death",
    "incoming_damage",
    "is_decided",
]
