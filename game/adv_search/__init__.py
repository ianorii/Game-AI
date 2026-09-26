"""
game/adv_search/__init__.py - Adversarial Search, Tubes Tahap 2.

Minimax, alpha-beta pruning, early stop, move ordering, dan Expectimax untuk
duel turn-based dengan NPC. Implementasi di ``game.adv_search.core``, yang
sendirinya facade dari modul root ``adversarial_ai.py``.
"""
from .core import (
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
