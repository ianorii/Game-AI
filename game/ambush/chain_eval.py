"""game/ambush/chain_eval.py - Evaluator rantai duel berurutan (Fase 3).

Tiga tingkat, satu interface (QueueEvaluator.evaluate(queue) -> difficulty
dalam [0,1] = 1 - P(player menang SEMUA duel), target 0.5 = imbang):

SEMANTIK TARGET (keputusan gate): target pada objektif progres = RATA-RATA
FRAKSI duel yang dimenangkan player (mis. target progres 0.5 berarti menang
~separuh duel), BUKAN peluang menang antrean. Menang/kalah biner tetap
dicatat terpisah (clear_rate) untuk governor dan battle_result.csv.

1. ChainHeuristic: atrisi mekanistik (HP terbawa eksplisit -> urutan
   memengaruhi skor) dengan bobot FIT dari fit_queue.py (JSON, bukan
   kode). Puluhan mikrodetik - satu-satunya yang boleh di inner-loop LS.
2. ChainLightSim: greedy 1-ply kedua sisi, N kecil. Default MATI
   (config.light_sim_enabled); eksperimen/validasi tengah saja.
3. ChainSim: duel penuh berseed (aturan buff_ai yang sama dengan duel
   nyata) berantai k duel, HP + potion player terbawa. Rerank top-M +
   angka kedua overlay. DILARANG di inner-loop.

Satu-satunya angka buff: slot_to_buff (tak ada paralel). Cache kunci
(loadout, queue, N, seed). Seed tetap = reproducible.
"""
from __future__ import annotations

import json
import math
import os
import random
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from adversarial_ai import ATTACK_MAX, ATTACK_MIN, MAX_HP
from game.ambush.buff import Buff
from game.ambush.buff_ai import BuffAwareAI, BuffBattleState, apply_chip_hook
from game.ambush.config import AmbushConfig
from game.ambush.enemy_queue import (EnemyQueue, enemy_max_hp,
                                       slot_to_buff)
from game.ambush.player_loadout import PlayerLoadout, loadout_to_buff

WEIGHTS_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "data",
    "queue_weights.json")

#: Bobot darurat bila JSON belum ada (fit_queue.py menimpanya; JANGAN
#: pakai untuk klaim kalibrasi - metrik sah hanya dari file JSON).
FALLBACK_WEIGHTS = {
    "v_atk": 1.0, "w_atk": 1.0, "w_spec": 0.5, "spec_freq": 0.25,
    "w_chip": 1.0, "v0": 2.0, "slope": 0.12, "base_dmg": 17.5,
    # Koreksi kalibrasi ronde-2 (fit): potion = ayunan HP terbesar yang
    # tak ditangkap atrisi murni (player ~75 pool duel-1, musuh ~75/duel).
    "w_pot_p": 0.5, "w_pot_e": 0.5,
    # Koreksi level antrean (order-free, inti atrisi tetap peka-urutan).
    "w_k": 0.0, "w_heal": 0.0, "w_min": 0.0,
    # Ronde-6: DEFEND kedua pihak (redaman flat, frekuensi terfit) dan
    # weaken Mage (memotong pool potion player).
    "w_def": 0.2, "w_weaken": 0.5,
}


def config_fingerprint(cfg: AmbushConfig) -> str:
    """Hash stabil atas SEMUA parameter yang memengaruhi hasil sim/heuristik.

    Meliputi: stat tabel (peran/Minion/item), skala musuh, bonus potion,
    rest, carry potion NPC, mode, N default, seed tidak (per-eval), depth
    sim, plies, lookahead. Kunci cache = (sidik ini, loadout, queue, N,
    seed) sehingga eksperimen beda konfigurasi tak pernah berbagi cache.
    """
    import hashlib
    from game.ambush.types import stat_fingerprint
    fields = (cfg.mode, cfg.enemy_stat_scale, cfg.potion_bonus_per_duel,
              cfg.rest_heal_pct, cfg.npc_potions_carry,
              cfg.npc_starting_potions, cfg.enemy_base_hp,
              cfg.refill_potions_each_duel, cfg.sim_games,
              cfg.sim_max_plies, cfg.sim_npc_depth, cfg.sim_player_depth,
              cfg.bew_rounds, cfg.diminish, cfg.armor_max, cfg.weaken_max,
              stat_fingerprint())
    return hashlib.sha1(repr(fields).encode()).hexdigest()[:16]


def load_weights(path: str = WEIGHTS_PATH) -> Dict:
    """Baca bobot fit (IOError bila berkas tak ada - sengaja)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_weights(cfg: AmbushConfig, path: str = WEIGHTS_PATH):
    """Kembalikan (weights, calibrated). Pengaman runtime (Fase 3).

    calibrated=True hanya bila berkas ada DAN metriknya memenuhi ambang
    config. Bila tidak: overlay WAJIB tampil 'UNCALIBRATED'; bobot darurat
    hanya dipakai bila cfg.allow_fallback_weights eksplisit True, jika
    tidak -> RuntimeError (jangan diam-diam memakai angka tak terkalibrasi).
    """
    try:
        doc = load_weights(path)
    except (OSError, ValueError):
        doc = None
    if doc is not None:
        m = doc.get("metrics", {})
        ok = (doc.get("calibrated", False)
              and doc.get("config_hash") == config_fingerprint(cfg)
              and m.get("pearson_test", 0) >= cfg.corr_pearson_min
              and m.get("spearman_test", 0) >= cfg.corr_spearman_min
              and m.get("rmse_test", 99) <= cfg.rmse_max)
        if ok:
            return doc, True
    if cfg.allow_fallback_weights:
        return {"weights": FALLBACK_WEIGHTS, "calibrated": False}, False
    raise RuntimeError(
        "bobot heuristik rantai belum terkalibrasi (lihat "
        "data/queue_weights.json); jalankan experiments/fit_queue.py atau "
        "set allow_fallback_weights=True eksplisit")


class QueueEvaluator(ABC):
    """Satu interface evaluator antrean (bisa dipertukarkan)."""

    @abstractmethod
    def evaluate(self, queue: EnemyQueue) -> float:
        """Difficulty antrean dalam [0,1] (0.5 = imbang)."""
        raise NotImplementedError


def apply_rest(hp: int, cap: int, pct: float) -> int:
    """Pulihkan HP antar-duel (satu implementasi untuk sim + battle nyata).

    Dipakai sim rantai kini dan driver BATTLE berurutan Fase 5 nanti,
    sehingga angka persiapan == angka duel. pct=0 (default) = tak ada.
    HP 0 (gugur) tidak dipulihkan.
    """
    if pct <= 0 or hp <= 0:
        return hp
    return min(cap, int(hp + pct * cap))


def carry_potions(pot_after: int, cfg: AmbushConfig) -> int:
    """Potion player untuk duel berikutnya dalam antrean (satu-satunya jalur).

    refill_potions_each_duel=True (default): isi penuh POTION_LIMIT tiap ganti
    lawan agar skill heal selalu bisa dipakai lagi. False: murni terbawa.
    Dipakai driver (QueueRun) DAN sim rantai agar angka game == simulasi.
    """
    from adversarial_ai import POTION_LIMIT
    if cfg.refill_potions_each_duel:
        return POTION_LIMIT
    return max(0, pot_after)


def scaled_enemy_buff(slot, cfg: AmbushConfig) -> Buff:
    """Stat musuh untuk RANTAI: slot_to_buff x enemy_stat_scale.

    Skala HANYA berlaku bila mode=SEQUENTIAL (mode BUFF memakai
    squad_to_buff tanpa skala - stat tahap 2/BUFF tak tersentuh).
    Satu-satunya pemakaian skala; HUD/battle Fase 5 wajib lewat sini.
    """
    base = slot_to_buff(slot, cfg)
    if cfg.mode != "SEQUENTIAL" or cfg.enemy_stat_scale == 1.0:
        return base
    f = cfg.enemy_stat_scale
    return Buff(hp=int(base.hp * f), atk=int(base.atk * f),
                spec=int(base.spec * f), regen=int(base.regen * f),
                armor=min(cfg.armor_max, base.armor * f),
                chip=int(base.chip * f),
                weaken=min(cfg.weaken_max, base.weaken * f))


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class ChainHeuristic(QueueEvaluator):
    """Atrisi mekanistik + bobot fit: HP terbawa eksplisit per duel.

    Memprediksi difficulty PROGRES yang sama dengan ChainSim.evaluate
    (bukan peluang biner). Overlay menampilkan keduanya berdampingan.

    Per duel i: ronde = ceil(hp_musuh / dmg_player); cost = ronde ×
    (dmg_musuh × (1-armor_player) − regen_player); hp_masuk[i+1] =
    hp_masuk[i] − cost + rest. p_win_i = sigmoid(hp_keluar). P_all = Π.
    Musuh keras di AWAL menggerus HP -> p_win berikutnya turun: itulah
    mengapa URUTAN memengaruhi skor (dibuktikan 3 contoh di gerbang).
    """

    def __init__(self, cfg: AmbushConfig, player: Optional[PlayerLoadout],
                 weights: Optional[Dict] = None):
        self.cfg = cfg
        self.player = player
        w = dict(weights["weights"] if weights and "weights" in weights
                 else (weights or FALLBACK_WEIGHTS))
        self.w = w
        self.meta = weights

    def per_duel(self, queue: EnemyQueue) -> List[Tuple[float, float, float]]:
        """Rincian per posisi: (hp_masuk, p_win, hp_keluar). Untuk overlay."""
        pbuff = (loadout_to_buff(self.player, self.cfg)
                 if self.player is not None else Buff())
        hp_full = MAX_HP + pbuff.hp
        # Pool potion player (~75): BUKAN overheal di depan (itu jenuh oleh
        # cap dan menghapus sinyal urutan duel-1), melainkan penyerap damage
        # yang terkuras: duel mahal di awal menghabiskannya.
        weaken_q = sum(slot_to_buff(s, self.cfg).weaken for s in queue.slots)
        weaken_q /= max(1, len(queue.slots))
        pool = 75.0 * self.w["w_pot_p"] * (1.0 - self.w["w_weaken"] * weaken_q)
        hp = float(hp_full)
        out = []
        for slot in queue.slots:
            eb = scaled_enemy_buff(slot, self.cfg)
            p_dmg = max(1.0, self.w["base_dmg"] + self.w["v_atk"] * pbuff.atk
                        + 0.3 * self.w["v_atk"] * pbuff.spec)
            p_dmg_eff = p_dmg * (1.0 - self.w["w_def"])
            # Tiap musuh membawa potion sendiri (pool efektif di bawah).
            e_hp = (enemy_max_hp(eb, self.cfg.enemy_base_hp)
                    + 75.0 * self.w["w_pot_e"])
            # Lomba regen (diagnosis bias Healer -0.55): bila damage bersih
            # per ronde tak positif, musuh tak bisa dibunuh -> duel kalah.
            net = p_dmg_eff - eb.regen
            if net <= 0:
                out.append((hp, 0.0, 0.0))
                hp = 0.0
                continue
            rounds = max(1, math.ceil(e_hp / p_dmg_eff))
            e_dmg = (self.w["w_atk"] * eb.atk
                     + self.w["w_spec"] * eb.spec * self.w["spec_freq"]
                     + self.w["w_chip"] * eb.chip) * (1.0 - self.w["w_def"])
            # Regen musuh memperpanjang duel: tambah ronde proporsional.
            if eb.regen > 0:
                rounds = max(1, math.ceil(
                    (e_hp + eb.regen * rounds) / p_dmg_eff))
            raw = (rounds * e_dmg * (1.0 - pbuff.armor)
                   - rounds * pbuff.regen - self.w["v0"])
            heal = min(pool, max(0.0, raw))
            pool -= heal
            taken = max(0.0, raw - heal)
            hp_out = hp - taken + self.cfg.rest_heal_pct * hp_full
            p_win = _sigmoid(self.w["slope"] * (hp_out - 0.05 * hp_full))
            out.append((hp, p_win, max(0.0, min(hp_full, hp_out))))
            hp = max(0.0, min(hp_full, hp_out))
        return out

    def evaluate(self, queue: EnemyQueue) -> float:
        """Difficulty progres (OPSI-D): 1 - E[duel_menang/k].

        E[duel_menang/k] = (1/k) x jumlah peluang mencapai tiap duel:
        duel i dimenangkan bila semua duel s/d i dimenangkan. Urutan
        memengaruhi lewat rantai HP (lihat per_duel).
        """
        reach = 1.0
        total = 0.0
        for _, p_win, _ in self.per_duel(queue):
            reach *= p_win
            total += reach
        k = max(1, len(queue.slots))
        diff = 1.0 - total / k
        # Koreksi level: jumlah musuh, kehadiran Healer, jumlah Minion.
        roles = [s.role for s in queue.slots]
        diff += (self.w["w_k"] * k + self.w["w_heal"] * roles.count("Healer")
                 + self.w["w_min"] * roles.count("Minion"))
        return min(1.0, max(0.0, diff))


class ChainLightSim(QueueEvaluator):
    """Sim ringan: greedy 1-ply kedua sisi (default MATI di config)."""

    def __init__(self, cfg: AmbushConfig, player: Optional[PlayerLoadout],
                 seed: int = 0, games: int = 4):
        self.cfg = cfg
        self.player = player
        self.seed = seed
        self.games = games
        self._cache: Dict[tuple, float] = {}

    def evaluate(self, queue: EnemyQueue) -> float:
        """Difficulty progres (OPSI-D). Biner via clear_rate()."""
        return self._run(queue)[0]

    def clear_rate(self, queue: EnemyQueue) -> float:
        """P(menang SEMUA duel): untuk governor dan battle_result.csv."""
        return self._run(queue)[1]

    def _run(self, queue: EnemyQueue) -> Tuple[float, float]:
        key = (config_fingerprint(self.cfg),
               (self.player.key() if self.player else None),
               queue.key(), self.games, self.seed)
        if key not in self._cache:
            self._cache[key] = self._simulate(queue)
        return self._cache[key]

    def _greedy(self, ai: BuffAwareAI, state: BuffBattleState,
                is_npc: bool) -> Optional[str]:
        from game.ambush.policies import greedy_action as _g
        return _g(ai, state, is_npc)

    def _simulate(self, queue: EnemyQueue) -> Tuple[float, float]:
        from game.ambush.player_loadout import loadout_to_buff as _l2b
        pbuff = _l2b(self.player, self.cfg) if self.player else Buff()
        rng = random.Random(self.seed)
        wins, tot = 0, 0.0
        self.last_entries = []
        for _ in range(max(1, self.games)):
            hp, potions = MAX_HP + pbuff.hp, 3
            alive, won = True, 0
            for slot in queue.slots:
                self.last_entries.append((hp, potions))
                eb = scaled_enemy_buff(slot, self.cfg)
                state = BuffBattleState(player_hp=hp,
                                        npc_hp=enemy_max_hp(
                                            eb, self.cfg.enemy_base_hp),
                                        turn=0, buff=eb, player_buff=pbuff)
                state.player_potions = potions
                state.npc_potions = self.cfg.npc_starting_potions
                ai_n = BuffAwareAI(depth=1, buff=eb, player_buff=pbuff)
                ai_p = BuffAwareAI(depth=1, buff=eb, player_buff=pbuff)
                for _ in range(self.cfg.sim_max_plies):
                    if state.is_terminal():
                        break
                    is_npc = state.turn == 1
                    a = self._greedy(ai_n if is_npc else ai_p, state, is_npc)
                    if a is None:
                        break
                    dmg = (rng.randint(ATTACK_MIN, ATTACK_MAX)
                           if a == "ATTACK" else None)
                    kw = {"attack_damage": dmg} if dmg is not None else {}
                    state = state.apply_action(is_npc, a, **kw)
                    apply_chip_hook(state, eb)
                if state.npc_hp > 0:
                    alive = False
                    break
                won += 1
                hp = state.player_hp
                potions = carry_potions(state.player_potions, self.cfg)
                if self.cfg.potion_bonus_per_duel > 0:
                    from adversarial_ai import POTION_LIMIT
                    potions = min(POTION_LIMIT,
                                  potions + self.cfg.potion_bonus_per_duel)
                # Syarat menang sudah lolos di atas (npc tumbang), jadi
                # rest selalu diterapkan di sini bila pct > 0.
                cap = MAX_HP + pbuff.hp
                hp = apply_rest(hp, cap, self.cfg.rest_heal_pct)
            tot += won / max(1, queue.k())
            wins += alive
        n = max(1, self.games)
        return 1.0 - tot / n, 1.0 - wins / n


class ChainSim(QueueEvaluator):
    """Sim penuh rantai: AI depth produksi, HP + potion terbawa. Rerank saja.

    evaluate() = difficulty PROGRES (1 - rata-rata fraksi duel dimenangkan;
    label overlay: "target progres 0.5 (menang ~separuh duel)"). Menang/
    kalah BINER antrean ada di clear_rate() untuk governor dan
    battle_result.csv (Fase 5+).
    """

    def __init__(self, cfg: AmbushConfig, player: Optional[PlayerLoadout],
                 seed: int = 0, games: Optional[int] = None):
        self.cfg = cfg
        self.player = player
        self.seed = seed
        self.games = games if games is not None else cfg.sim_games
        self._cache: Dict[tuple, float] = {}

    def evaluate(self, queue: EnemyQueue) -> float:
        """Difficulty progres (OPSI-D). Biner via clear_rate()."""
        return self._run(queue)[0]

    def clear_rate(self, queue: EnemyQueue) -> float:
        """P(menang SEMUA duel): untuk governor dan battle_result.csv."""
        return self._run(queue)[1]

    def _run(self, queue: EnemyQueue) -> Tuple[float, float]:
        key = (config_fingerprint(self.cfg),
               (self.player.key() if self.player else None),
               queue.key(), self.games, self.seed)
        if key not in self._cache:
            self._cache[key] = self._simulate(queue)
        return self._cache[key]

    def _simulate(self, queue: EnemyQueue) -> Tuple[float, float]:
        pbuff = (loadout_to_buff(self.player, self.cfg)
                 if self.player else Buff())
        rng = random.Random(self.seed)
        wins, tot = 0, 0.0
        self.last_entries = []
        for _ in range(max(1, self.games)):
            hp, potions = MAX_HP + pbuff.hp, 3
            alive, won = True, 0
            for slot in queue.slots:
                self.last_entries.append((hp, potions))
                eb = scaled_enemy_buff(slot, self.cfg)
                state = BuffBattleState(player_hp=hp,
                                        npc_hp=enemy_max_hp(
                                            eb, self.cfg.enemy_base_hp),
                                        turn=0, buff=eb, player_buff=pbuff)
                state.player_potions = potions
                state.npc_potions = self.cfg.npc_starting_potions
                ai_n = BuffAwareAI(depth=self.cfg.sim_npc_depth, buff=eb,
                                   player_buff=pbuff,
                                   lookahead=self.cfg.bew_rounds)
                ai_p = BuffAwareAI(depth=self.cfg.sim_player_depth, buff=eb,
                                   player_buff=pbuff,
                                   lookahead=self.cfg.bew_rounds)
                for _ in range(self.cfg.sim_max_plies):
                    if state.is_terminal():
                        break
                    is_npc = state.turn == 1
                    ai = ai_n if is_npc else ai_p
                    a = ai.think(state, run_baseline=False,
                                 root_is_npc=is_npc)["best_action"]
                    if a is None:
                        break
                    dmg = (rng.randint(ATTACK_MIN, ATTACK_MAX)
                           if a == "ATTACK" else None)
                    kw = {"attack_damage": dmg} if dmg is not None else {}
                    state = state.apply_action(is_npc, a, **kw)
                    apply_chip_hook(state, eb)
                if state.npc_hp > 0:
                    alive = False
                    break
                won += 1
                hp = state.player_hp
                potions = carry_potions(state.player_potions, self.cfg)
                if self.cfg.potion_bonus_per_duel > 0:
                    from adversarial_ai import POTION_LIMIT
                    potions = min(POTION_LIMIT,
                                  potions + self.cfg.potion_bonus_per_duel)
                # Syarat menang sudah lolos di atas (npc tumbang), jadi
                # rest selalu diterapkan di sini bila pct > 0.
                cap = MAX_HP + pbuff.hp
                hp = apply_rest(hp, cap, self.cfg.rest_heal_pct)
            tot += won / max(1, queue.k())
            wins += alive
        n = max(1, self.games)
        return 1.0 - tot / n, 1.0 - wins / n


def time_eval(ev: QueueEvaluator, queue: EnemyQueue,
              repeats: int = 5) -> Tuple[float, float]:
    """Waktu rata-rata per evaluasi (ms). Ukur, jangan kira-kira."""
    ev.evaluate(queue)  # pemanasan (cache)
    if hasattr(ev, "_cache"):
        ev._cache.clear()
    t0 = time.perf_counter()
    for _ in range(repeats):
        if hasattr(ev, "_cache"):
            ev._cache.clear()
        ev.evaluate(queue)
    return ((time.perf_counter() - t0) / repeats * 1000.0, 0.0)
