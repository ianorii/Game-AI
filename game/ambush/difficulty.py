"""game/ambush/difficulty.py - Interface evaluasi difficulty + dua implementasi.

difficulty(config) dalam [0,1]: 0 = squad sepele, 1 = squad mematikan.
Objective local search: minimalkan |difficulty - target|.

- HeuristicEvaluator: AFFINE yang difit ke data simulasi
  (w·buff + bias, dijepit [0,1]). Cepat untuk inner-loop LS. Bobot di
  AmbushConfig beserta provenance fit (lihat experiments/fit_heuristic.py).
  Bila loadout player ditempel, difficulty = kekuatan NPC dikurangi
  kekuatan player (satu skala) sehingga LS menyetel MELAWAN loadout.
- SimulationEvaluator: margin sisa HP atas N duel berseed tetap antara
  BuffAwareAI (NPC ter-buff) vs BuffAwareAI (player + loadout) di atas
  BuffBattleState. Simetri otak membuat BUFF yang memutuskan hasil.

Aturan buff hanya ada di buff_ai (satu sumber); file ini hanya memakai.
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Dict

from adversarial_ai import (
    ATTACK_MAX,
    ATTACK_MIN,
    MAX_HP,
)
from game.ambush.buff import Buff, squad_to_buff
from game.ambush.buff_ai import BuffAwareAI, BuffBattleState, apply_chip_hook
from game.ambush.config import AmbushConfig
from game.ambush.types import SquadConfig


def difficulty_gap(difficulty: float, target: float) -> float:
    """Objective local search: jarak ke target (makin kecil makin baik)."""
    return abs(difficulty - target)


class SquadEvaluator(ABC):
    """Satu interface untuk kedua mode evaluasi (bisa dipertukarkan)."""

    @abstractmethod
    def evaluate(self, squad: SquadConfig, player=None) -> float:
        """Kembalikan difficulty squad dalam [0,1]."""
        raise NotImplementedError


class HeuristicEvaluator(SquadEvaluator):
    """Fungsi cepat: affine buff yang difit ke simulasi, dijepit [0,1]."""

    def __init__(self, cfg: AmbushConfig):
        self.cfg = cfg
        self._player = None

    def set_player(self, player) -> None:
        """Tempel loadout player untuk evaluasi berikutnya (None = abaikan)."""
        self._player = player

    def _npc_strength(self, buff: Buff) -> float:
        cfg = self.cfg
        return (
            cfg.w_hp * buff.hp
            + cfg.w_atk * buff.atk
            + cfg.w_spec * buff.spec
            + cfg.w_regen * buff.regen
            + cfg.w_armor * buff.armor
            + cfg.w_chip * buff.chip
            + cfg.w_weaken * buff.weaken
            + cfg.w_bias
        )

    def evaluate(self, squad: SquadConfig, player=None) -> float:
        from game.ambush.player_loadout import loadout_to_buff
        buff = squad_to_buff(squad, self.cfg)
        strength = self._npc_strength(buff)
        pl = player if player is not None else self._player
        if pl is not None:
            # Kekuatan player dihitung dengan bobot SAMA agar satu skala;
            # dikurangi 80% (player manusia tak seoptimal AI, jadi buff
            # player didiskon sedikit agar duel tetap menantang).
            pbuff = loadout_to_buff(pl, self.cfg)
            pstrength = self._npc_strength(pbuff) - self.cfg.w_bias
            strength -= 0.8 * pstrength
        return min(1.0, max(0.0, strength))


class SimulationEvaluator(SquadEvaluator):
    """Difficulty = rata-rata margin sisa HP atas duel berseed tetap.

    Skor satu duel = (frac_HP_NPC - frac_HP_player + 1) / 2: menang telak
    ~1.0, menang tipis ~0.5, kalah < 0.5. Kedua pihak memakai depth SAMA
    (config) sehingga selisih skor murni berasal dari buff.
    Terlalu mahal untuk inner-loop LS: re-ranking/validasi + fitting.
    """

    def __init__(self, cfg: AmbushConfig, seed: int = 0, player=None):
        self.cfg = cfg
        self.seed = seed
        self._cache: Dict[tuple, float] = {}
        self._player = player

    def set_player(self, player) -> None:
        """Tempel loadout player; cache di-reset karena skala berubah."""
        self._player = player
        self._cache.clear()

    def evaluate(self, squad: SquadConfig, player=None) -> float:
        pl = player if player is not None else self._player
        key = (squad.key(), pl.key() if pl is not None else None)
        if key not in self._cache:
            self._cache[key] = self._simulate(squad, pl)
        return self._cache[key]

    def _simulate(self, squad: SquadConfig, player=None) -> float:
        from game.ambush.player_loadout import loadout_to_buff
        buff = squad_to_buff(squad, self.cfg)
        pbuff = loadout_to_buff(player, self.cfg) if player is not None else None
        rng = random.Random(self.seed)
        total = 0.0
        for _ in range(self.cfg.sim_games):
            total += self._play_margin(buff, rng, pbuff)
        return total / max(1, self.cfg.sim_games)

    def _play_margin(self, buff: Buff, rng: random.Random,
                     pbuff: Buff = None) -> float:
        from game.ambush.enemy_queue import enemy_max_hp
        npc_max = enemy_max_hp(buff, self.cfg.enemy_base_hp)
        player_max = MAX_HP + (pbuff.hp if pbuff else 0)
        state = BuffBattleState(player_hp=player_max, npc_hp=npc_max, turn=0,
                                buff=buff, player_buff=pbuff)
        npc_ai = BuffAwareAI(depth=self.cfg.sim_npc_depth,
                             algorithm="alphabeta", buff=buff,
                             player_buff=pbuff,
                             lookahead=self.cfg.bew_rounds)
        player_ai = BuffAwareAI(depth=self.cfg.sim_player_depth,
                                algorithm="alphabeta", buff=buff,
                                player_buff=pbuff,
                                lookahead=self.cfg.bew_rounds)
        for _ in range(self.cfg.sim_max_plies):
            if state.is_terminal():
                break
            is_npc = state.turn == 1
            if is_npc:
                action = npc_ai.think(state, run_baseline=False)["best_action"]
                if action is None:
                    break
            else:
                # Sisi MIN: evaluasi tetap berorientasi NPC (tahap 2).
                action = player_ai.think(state, run_baseline=False,
                                         root_is_npc=False)["best_action"]
                if action is None:
                    break
            if action == "ATTACK":
                state = state.apply_action(
                    is_npc, action,
                    attack_damage=rng.randint(ATTACK_MIN, ATTACK_MAX))
            else:
                state = state.apply_action(is_npc, action)
            apply_chip_hook(state, buff)
        return (state.npc_hp / npc_max - state.player_hp / player_max
                + 1.0) / 2.0
