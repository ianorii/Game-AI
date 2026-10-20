"""game/ambush/director.py - Ambush Director: CSP -> LS -> verifikasi -> buff.

Alur: kumpulkan seed CSP valid -> pilih seed terbaik (gap heuristik) ->
local search menyetel ke target -> (opsional) re-rank simulasi ->
verifikasi complete+consistent -> ringkas jadi buff/plan untuk battle.

plan() blocking untuk gameplay instant + eksperimen. run_gen() generator
untuk mode slow/step: event CSP diteruskan satu per satu (dipompa per frame
atau per tombol) agar solver tidak membekukan game; LS heuristik cukup cepat
untuk satu potongan blocking.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Tuple

from game.ambush.buff import Buff, plan_duels
from game.ambush.config import AmbushConfig
from game.ambush.constraints import is_complete, is_consistent
from game.ambush.csp_solver import CSPSolver, squad_problem
from game.ambush.difficulty import (
    HeuristicEvaluator,
    SimulationEvaluator,
    SquadEvaluator,
    difficulty_gap,
)
from game.ambush.governor import DifficultyGovernor
from game.ambush.local_search import (
    genetic,
    hill_climb,
    random_restart,
    simulated_annealing,
)
from game.ambush.types import EMPTY, SquadConfig

LS_ALGOS = ("hill_climbing", "random_restart", "simulated_annealing",
            "genetic")


def _assign_of(squad: SquadConfig) -> Dict[str, str]:
    out = {}
    for i, (role, item) in enumerate(zip(squad.roles, squad.items), 1):
        out[f"ROLE_{i}"] = role
        out[f"ITEM_{i}"] = item
    return out


def _to_squad(assign: Dict[str, str], cfg: AmbushConfig) -> SquadConfig:
    return SquadConfig(
        roles=tuple(assign[f"ROLE_{i}"] for i in range(1, cfg.kmax + 1)),
        items=tuple(assign[f"ITEM_{i}"] for i in range(1, cfg.kmax + 1)),
    )


def _item_count(squad: "SquadConfig") -> int:
    """Jumlah item non-NONE (tie-break agar tampilan menarik)."""
    return sum(1 for it in squad.items if it != EMPTY)


def _fallback_squad(cfg: AmbushConfig) -> SquadConfig:
    """Cadangan bila CSP tak menemukan solusi: satu Warrior tanpa item."""
    n = cfg.kmax
    return SquadConfig(roles=("Warrior",) + (EMPTY,) * (n - 1),
                       items=(EMPTY,) * n)


# ---------------------------------------------------------------------------
# Jalur SEQUENTIAL (duel berurutan). Jalur BUFF di atas tak tersentuh.
# ---------------------------------------------------------------------------

from game.ambush.chain_eval import (  # noqa: E402
    ChainHeuristic,
    ChainLightSim,
    ChainSim,
)
from game.ambush.enemy_queue import (  # noqa: E402
    EnemyQueue,
    is_queue_valid,
    queue_from_assign,
    queue_to_buffs,
)
from game.ambush.queue_search import (  # noqa: E402
    drain,
    genetic_q,
    hill_climb_q,
    random_restart_q,
    simulated_annealing_q,
)


@dataclass
class QueueDirectorResult:
    """Hasil director antrean untuk battle + overlay + CSV."""

    queue: EnemyQueue
    buffs: list
    light: float          # difficulty sim-ringan (yang dioptimasi LS)
    gap: float            # |light - target|
    target: float
    budget: int
    wins: int
    verified: bool
    seed_gap: float
    seed_mode: str        # "BEST (gameplay)" | "RANDOM (demo)"
    ls_algo: str
    ls_stop: str
    ls_iters: int
    ls_evals: int
    ls_rejected: int
    sim_difficulty: Optional[float] = None  # rerank sim penuh
    sim_entries: Optional[list] = None  # (hp, potion) awal tiap duel (rerank)
    gap_full: float = 0.0             # |sim - target| pilihan final
    clear_rate: Optional[float] = None      # P(menang semua) utk governor
    per_duel: Optional[list] = None  # (hp_masuk, p_win, hp_keluar)/posisi
    capped: bool = False  # True bila target diminta > plafon (opsi C)
    requested_target: float = 0.0  # target asli sebelum dijepit plafon


def _queue_light(cfg: AmbushConfig, player, base_seed: int) -> ChainLightSim:
    """Sim ringan dengan seed pencarian (CRN: skenario sama tiap kandidat)."""
    return ChainLightSim(cfg, player, seed=base_seed,
                         games=cfg.light_sim_games)


def _queue_prefilter(cfg: AmbushConfig, player):
    """Heuristik pra-penyaring (None bila tak terkalibrasi & tak diizinkan)."""
    if not cfg.allow_heuristic_prefilter:
        return None
    try:
        from game.ambush.chain_eval import resolve_weights
        doc, _cal = resolve_weights(cfg)
        return ChainHeuristic(cfg, player, doc)
    except RuntimeError:
        return None


class QueueDirectorMixin:
    """Campuran orkestrasi antrean (dipakai AmbushDirector bila SEQUENTIAL)."""

    def _queue_seeds(self, wins: int, budget: int):
        cfg = self.cfg
        flags = cfg.csp_flags()
        problem = squad_problem(wins, budget, cfg,
                                avoid_roles=self.avoid_roles, **flags)
        squads: List[EnemyQueue] = []
        for s in range(cfg.dir_seeds):
            solver = CSPSolver(
                problem, seed=self.base_seed + s, tracer=self.tracer,
                time_limit=cfg.csp_time_limit, max_nodes=cfg.csp_max_nodes,
                **self.csp_options,
            )
            sol, _stats = solver.solve()
            if sol is not None:
                cand = queue_from_assign(sol, cfg)
                if all(c.key() != cand.key() for c in squads):
                    squads.append(cand)
        return squads

    def _queue_seeds_gen(self, wins: int, budget: int):
        """Versi generator (yield event CSP) untuk mode slow/step."""
        cfg = self.cfg
        flags = cfg.csp_flags()
        problem = squad_problem(wins, budget, cfg,
                                avoid_roles=self.avoid_roles, **flags)
        squads: List[EnemyQueue] = []
        for s in range(cfg.dir_seeds):
            solver = CSPSolver(
                problem, seed=self.base_seed + s, tracer=self.tracer,
                time_limit=cfg.csp_time_limit, max_nodes=cfg.csp_max_nodes,
                **self.csp_options,
            )
            for event in solver.run():
                yield {"phase": "csp", "seed": s, **event}
            if solver._solution is not None:
                cand = queue_from_assign(solver._solution, cfg)
                if all(c.key() != cand.key() for c in squads):
                    squads.append(cand)
            yield {"phase": "csp_seed_done", "seed": s,
                   "solutions": len(squads)}
        return squads

    def _uses_old_roles(self, queue: Optional[EnemyQueue]) -> bool:
        """True bila antrean masih memakai peran pertemuan sebelumnya."""
        if queue is None or not self.avoid_roles:
            return False
        return any(s.role in self.avoid_roles for s in queue.slots)

    def _avoid_winner(self, winner: EnemyQueue, wins: int,
                      budget: int) -> EnemyQueue:
        """Ganti pemenang LS bila ia mengulang peran pertemuan sebelumnya.

        Variasi antar-pertemuan bersifat best-effort (permintaan pemain):
        pemenang LS dipakai bila sudah bebas; kalau tidak, pakai start/seed
        CSP yang bebas; bila semuanya memakai peran lama, kandidat valid
        apa adanya tetap dipakai supaya duel tidak berubah jadi "duel
        polos".
        """
        if not self._uses_old_roles(winner):
            return winner
        for cand in (self.last_queue_start, *self.last_queue_seeds):
            if self._uses_old_roles(cand):
                continue
            if is_queue_valid(cand, wins, budget, self.cfg):
                return cand
        return winner

    def _emergency_queue(self, cfg: AmbushConfig) -> EnemyQueue:
        """Antrean darurat: peran termurah yang beda & belum dipakai.

        Dipakai bila CSP tak menemukan solusi sama sekali (tak terjadi di
        60/60 uji). Tetap menghormati aturan antrean: peran musuh saling
        berbeda dan tidak mengulang peran pertemuan sebelumnya.
        """
        from game.ambush.enemy_queue import EnemySlot
        picked: List[str] = []
        for avoid in (self.avoid_roles, ()):
            for role in ("Minion", "Warrior", "Archer", "Healer", "Mage",
                         "Tank"):
                if role in avoid or role in picked:
                    continue
                picked.append(role)
                if len(picked) >= cfg.min_enemies:
                    break
            if len(picked) >= cfg.min_enemies:
                break
        return EnemyQueue(slots=tuple(EnemySlot(r, EMPTY) for r in picked))

    def _pick_queue_start(self, squads: List[EnemyQueue],
                          light, target: float, demo: bool):
        gaps = [(difficulty_gap(light.evaluate(sq), target), sq)
                for sq in squads]
        if demo:
            # Demo: seed PERTAMA ditemukan (bervariasi antar run/base_seed),
            # agar LS punya jarak tempuh. Gameplay: seed terbaik.
            return gaps[0][0], squads[0], "RANDOM (demo)"
        gaps.sort(key=lambda t: (t[0], -sum(
            1 for x in t[1].slots if x.item != "NONE")))
        return gaps[0][0], gaps[0][1], "BEST (gameplay)"

    def _run_q_ls(self, start, squads, light, prefilter, wins, budget,
                  target):
        cfg, t = self.cfg, self.tracer
        kw = dict(tracer=t, avoid_roles=self.avoid_roles)
        if self.ls_algo == "hill_climbing":
            return hill_climb_q(start, light, target, wins, budget, cfg,
                                prefilter=prefilter, **kw)
        if self.ls_algo == "simulated_annealing":
            return simulated_annealing_q(start, light, target, wins,
                                         budget, cfg, seed=self.base_seed,
                                         **kw)
        if self.ls_algo == "genetic":
            return genetic_q(squads, light, target, wins, budget, cfg,
                             seed=self.base_seed, **kw)
        seeds = squads
        return random_restart_q(lambda r: seeds[r % len(seeds)], light,
                                target, wins, budget, cfg,
                                prefilter=prefilter, **kw)

    def plan_queue(self, wins: int, target: float, player=None,
                   demo: bool = False) -> QueueDirectorResult:
        """Jalur instant/blocking (dipompa-tuntas == run_gen_queue)."""
        from game.ambush.governor import cap_target
        cfg = self.cfg
        target, requested, capped = cap_target(cfg, target)
        budget = cfg.budget_q_for(target)
        squads = self._queue_seeds(wins, budget)
        if not squads:  # darurat (tak terjadi di 60/60 uji)
            squads = [self._emergency_queue(cfg)]
        light = _queue_light(cfg, player, self.base_seed)
        prefilter = _queue_prefilter(cfg, player)
        seed_gap, start, seed_mode = self._pick_queue_start(
            squads, light, target, demo)
        self.last_queue_start = start
        self.last_queue_seeds = list(squads)
        res, _events = drain(self._run_q_ls(start, squads, light, prefilter,
                                            wins, budget, target))
        winner = res.best
        if not is_queue_valid(winner, wins, budget, cfg):
            winner = start
        winner = self._avoid_winner(winner, wins, budget)
        sim = ChainSim(cfg, player, seed=self.base_seed,
                       games=cfg.chain_rerank_games)
        result = self._finalize_queue(winner, res, wins, budget, target,
                                      seed_gap, seed_mode, sim, prefilter,
                                      player, capped, requested)
        # ^^^ pemanggil plan_queue + run_gen_queue (keduanya menjepit target)
        self.last_queue_result = result
        if self.tracer is not None:
            self.tracer.emit("director_done", gap=result.gap, target=target,
                             verified=result.verified, algo=res.algo,
                             stop=res.stop, sim=result.sim_difficulty,
                             light=result.light)
        return result

    def run_gen_queue(self, wins: int, target: float, player=None,
                      demo: bool = False):
        """Versi resumable: event CSP + LS di-yield per langkah."""
        from game.ambush.governor import cap_target
        cfg = self.cfg
        target, requested, capped = cap_target(cfg, target)
        budget = cfg.budget_q_for(target)
        gen = self._queue_seeds_gen(wins, budget)
        squads: List[EnemyQueue] = []
        try:
            while True:
                event = next(gen)
                if event.get("phase") == "csp_seed_done":
                    pass
                yield event
        except StopIteration as done:
            squads = done.value or []
        if not squads:
            squads = [self._emergency_queue(cfg)]
        self.last_queue_seeds = list(squads)
        light = _queue_light(cfg, player, self.base_seed)
        prefilter = _queue_prefilter(cfg, player)
        seed_gap, start, seed_mode = self._pick_queue_start(
            squads, light, target, demo)
        self.last_queue_start = start
        yield {"phase": "ls_start", "algo": self.ls_algo,
               "seed_gap": seed_gap, "seed_mode": seed_mode,
               "start": start.order_str()}
        ls_gen = self._run_q_ls(start, squads, light, prefilter, wins,
                                budget, target)
        try:
            while True:
                event = next(ls_gen)
                phase = {"hill_climbing": "ls_iter",
                         "random_restart": "ls_iter",
                         "simulated_annealing": "ls_sa",
                         "genetic": "ga_gen"}.get(self.ls_algo, "ls_iter")
                yield {"phase": phase, **event}
        except StopIteration as done_ls:
            res = done_ls.value
        yield {"phase": "ls_done", "algo": res.algo, "stop": res.stop,
               "iters": res.iters, "best_gap": res.best_gap}
        winner = res.best
        if not is_queue_valid(winner, wins, budget, cfg):
            winner = start
        winner = self._avoid_winner(winner, wins, budget)
        sim = ChainSim(cfg, player, seed=self.base_seed,
                       games=cfg.chain_rerank_games)
        result = self._finalize_queue(winner, res, wins, budget, target,
                                      seed_gap, seed_mode, sim, prefilter,
                                      player, capped, requested)
        # ^^^ pemanggil plan_queue + run_gen_queue (keduanya menjepit target)
        self.last_queue_result = result
        if self.tracer is not None:
            self.tracer.emit("director_done", gap=result.gap, target=target,
                             verified=result.verified, algo=res.algo,
                             stop=res.stop, sim=result.sim_difficulty,
                             light=result.light)
        yield {"phase": "done", "gap": result.gap,
               "verified": result.verified}

    def _finalize_queue(self, winner, res, wins, budget, target, seed_gap,
                        seed_mode, sim, prefilter,
                        player, capped: bool = False,
                        requested: Optional[float] = None
                        ) -> QueueDirectorResult:
        from game.ambush.difficulty import difficulty_gap as _gap
        cfg = self.cfg
        light = _queue_light(cfg, player, self.base_seed)
        # Rerank: top-M versi ringan dinilai ulang sim penuh; final =
        # gap_full terkecil (fallback: pemenang LS -> seed bila invalid).
        cands = [(g, qq) for g, qq in (res.topm or [(res.best_gap, winner)])]
        # Variasi antar-pertemuan: bila ADA kandidat yang bebas peran
        # pertemuan sebelumnya, rerank hanya di antara kandidat itu.
        # (Best-effort: tanpa kandidat bebas, kandidat valid apa adanya
        # tetap dipakai agar duel tidak berubah jadi "duel polos".)
        if self.avoid_roles:
            free = [(g, qq) for g, qq in cands if not self._uses_old_roles(qq)]
            if free:
                cands = free
            else:
                fallback = self.last_queue_start
                if (fallback is not None
                        and not self._uses_old_roles(fallback)
                        and is_queue_valid(fallback, wins, budget, cfg)):
                    cands = [(res.best_gap, fallback)]
        scored = []
        for _g_light, qq in cands[:max(1, cfg.rerank_M)]:
            full = sim.evaluate(qq)
            scored.append((_gap(full, target), full, qq))
        scored.sort(key=lambda t: t[0])
        gap_full, full_best, final = scored[0]
        rerank_info = [{"order": qq.order_str(), "k": qq.k(),
                        "gap_light": round(_gap(light.evaluate(qq), target), 4),
                        "gap_full": round(g, 4)} for g, _f, qq in scored]
        if self.tracer is not None:
            self.tracer.emit("ls_rerank", candidates=rerank_info,
                             picked=final.order_str())
        winner = final
        if not is_queue_valid(winner, wins, budget, cfg):
            winner = res.best
            if not is_queue_valid(winner, wins, budget, cfg):
                # start dijamin valid (seed CSP); disimpan pemanggil.
                if (self.last_queue_start is not None and is_queue_valid(
                        self.last_queue_start, wins, budget, cfg)):
                    winner = self.last_queue_start
        if self.avoid_roles and self._uses_old_roles(winner):
            winner = self._avoid_winner(winner, wins, budget)
        difficulty = light.evaluate(winner)
        gap = difficulty_gap(difficulty, target)
        verified = is_queue_valid(winner, wins, budget, cfg)
        per_duel = None
        if prefilter is not None:
            try:
                per_duel = prefilter.per_duel(winner)
            except Exception:
                per_duel = None
        return QueueDirectorResult(
            queue=winner, buffs=queue_to_buffs(winner, cfg),
            light=difficulty, gap=gap, target=target, budget=budget,
            wins=wins, verified=verified, seed_gap=seed_gap,
            seed_mode=seed_mode, ls_algo=res.algo, ls_stop=res.stop,
            ls_iters=res.iters, ls_evals=res.evals,
            ls_rejected=res.rejected,
            sim_difficulty=sim.evaluate(winner),
            sim_entries=list(getattr(sim, "last_entries", []) or []),
            gap_full=difficulty_gap(sim.evaluate(winner), target),
            clear_rate=sim.clear_rate(winner), per_duel=per_duel,
            capped=capped,
            requested_target=target if requested is None else requested)


@dataclass
class DirectorResult:
    """Paket akhir director untuk battle + overlay + CSV."""

    squad: SquadConfig
    buff: Buff
    difficulty: float       # heuristik (yang dioptimasi LS)
    gap: float              # |difficulty - target| heuristik
    target: float
    budget: int
    wins: int
    verified: bool
    seed_gap: float       # gap heuristik seed CSP terbaik (vs gap akhir)
    ls_algo: str
    ls_stop: str
    ls_iters: int
    ls_evals: int
    ls_rejected: int
    evaluator_name: str
    sim_difficulty: Optional[float] = None  # validasi simulasi (rerank)
    capped: bool = False  # True bila target diminta > plafon (opsi C)
    requested_target: float = 0.0  # target asli sebelum dijepit plafon


class AmbushDirector(QueueDirectorMixin):
    """Orkestrator pembentukan squad sebelum battle mode."""

    def __init__(
        self,
        cfg: AmbushConfig,
        governor: DifficultyGovernor,
        tracer=None,
        evaluator: Optional[SquadEvaluator] = None,
        csp_options: Optional[Dict[str, Any]] = None,
        ls_algo: str = "random_restart",
        base_seed: int = 0,
        player_loadout=None,
        avoid_roles: Tuple[str, ...] = (),
    ):
        if ls_algo not in LS_ALGOS:
            raise ValueError(f"ls_algo harus salah satu {LS_ALGOS}")
        self.cfg = cfg
        self.governor = governor
        self.tracer = tracer
        self.heuristic = evaluator or HeuristicEvaluator(cfg)
        self.csp_options = csp_options or {}
        self.ls_algo = ls_algo
        self.base_seed = base_seed
        self.player_loadout = player_loadout
        # Peran musuh pertemuan sebelumnya (variasi antar-pertemuan).
        self.avoid_roles: Tuple[str, ...] = tuple(avoid_roles or ())
        if (player_loadout is not None
                and hasattr(self.heuristic, "set_player")):
            self.heuristic.set_player(player_loadout)
        self.last_result: Optional[DirectorResult] = None
        self.last_seeds: List[SquadConfig] = []  # seed CSP run terakhir
        # Jalur antrean (diisi ulang tiap run; dipakai variasi antar-pertemuan
        # + overlay/compare panel).
        self.last_queue_start: Optional[EnemyQueue] = None
        self.last_queue_seeds: List[EnemyQueue] = []
        self.last_queue_result: Optional[QueueDirectorResult] = None

    # -- blocking (instant gameplay + eksperimen) ----------------------
    def plan(self, wins: int, target: float) -> DirectorResult:
        """Jalankan seluruh alur sekaligus; kembalikan hasil terverifikasi."""
        from game.ambush.governor import cap_target
        cfg = self.cfg
        target, requested, capped = cap_target(cfg, target)
        budget = cfg.budget_for(target)
        problem = squad_problem(wins, budget, cfg)

        squads: List[SquadConfig] = []
        for s in range(cfg.dir_seeds):
            solver = CSPSolver(
                problem, seed=self.base_seed + s, tracer=self.tracer,
                time_limit=cfg.csp_time_limit, max_nodes=cfg.csp_max_nodes,
                **self.csp_options,
            )
            sol, _stats = solver.solve()
            if sol is not None:
                cand = _to_squad(sol, cfg)
                if all(c.key() != cand.key() for c in squads):
                    squads.append(cand)
        if not squads:
            squads.append(_fallback_squad(cfg))
        self.last_seeds = list(squads)

        seed_gaps = [(difficulty_gap(self.heuristic.evaluate(sq), target), sq)
                     for sq in squads]
        # Tie-break menarik: bila gap dalam toleransi, pilih yang lebih
        # banyak item (CSP tetap murni; hanya urutan seed yang dipilih).
        seed_gaps.sort(key=lambda t: (t[0], -_item_count(t[1])))
        seed_gap, start = seed_gaps[0]

        res = self._run_ls(start, squads, wins, budget, target)
        # Final = yang terbaik versi LS; bila GA-penalty tak menemukan yang
        # feasible, mundur ke seed CSP (dijamin feasible) agar verified.
        winner = res.best
        assign = _assign_of(winner)
        if not (is_complete(assign, cfg)
                and is_consistent(assign, wins, budget, cfg)):
            winner = start
        sim_diff = self._sim_validate(winner, target)
        result = self._finalize(winner, sim_diff, res, wins, budget,
                                target, seed_gap, capped, requested)
        self.last_result = result
        if self.tracer is not None:
            self.tracer.emit("director_done", gap=result.gap,
                             target=target, verified=result.verified,
                             algo=res.algo, stop=res.stop)
        return result

    def _run_ls(self, start: SquadConfig, squads: List[SquadConfig],
                wins: int, budget: int, target: float):
        heu, t = self.heuristic, self.tracer
        if self.ls_algo == "hill_climbing":
            return hill_climb(start, heu, target, wins, budget, self.cfg,
                              tracer=t)
        if self.ls_algo == "simulated_annealing":
            return simulated_annealing(start, heu, target, wins, budget,
                                       self.cfg, seed=self.base_seed,
                                       tracer=t)
        if self.ls_algo == "genetic":
            return genetic(squads, heu, target, wins, budget, self.cfg,
                           seed=self.base_seed, tracer=t)
        seeds = squads  # random_restart: seed CSP dipakai ulang berputar
        return random_restart(lambda r: seeds[r % len(seeds)], heu, target,
                              wins, budget, self.cfg, tracer=t)

    def _sim_validate(self, squad: SquadConfig,
                      target: float) -> Optional[float]:
        """Nilai squad final dengan simulasi (validasi, tak mengganti squad).

        Mengembalikan sim difficulty atau None bila rerank dimatikan.
        """
        if not self.cfg.dir_rerank:
            return None
        # Hemat: validasi memakai duel lebih sedikit (sekali jalan).
        rerank_cfg = replace(self.cfg, sim_games=self.cfg.dir_rerank_games)
        sim = SimulationEvaluator(rerank_cfg, seed=self.base_seed,
                                    player=self.player_loadout)
        return sim.evaluate(squad)

    def _finalize(self, winner: SquadConfig,
                  sim_diff: Optional[float], res, wins: int, budget: int,
                  target: float, seed_gap: float,
                  capped: bool = False,
                  requested: Optional[float] = None) -> DirectorResult:
        cfg = self.cfg
        difficulty = self.heuristic.evaluate(winner)
        gap = difficulty_gap(difficulty, target)
        assign = _assign_of(winner)
        verified = (is_complete(assign, cfg)
                    and is_consistent(assign, wins, budget, cfg))
        squad = _to_squad(assign, cfg)
        return DirectorResult(
            squad=squad, buff=plan_duels(squad, cfg).rounds[0],
            difficulty=difficulty, gap=gap, target=target, budget=budget,
            wins=wins, verified=verified, seed_gap=seed_gap,
            ls_algo=res.algo, ls_stop=res.stop, ls_iters=res.iters,
            ls_evals=res.evals, ls_rejected=res.rejected,
            evaluator_name=("simulation(rerank)" if sim_diff is not None
                            else "heuristic"),
            sim_difficulty=sim_diff,
            capped=capped,
            requested_target=target if requested is None else requested,
        )

    # -- generator (mode slow/step: pompa per frame/tombol) ------------
    def run_gen(self, wins: int, target: float):
        """Sama seperti plan() tetapi event CSP di-yield satu per satu."""
        from game.ambush.governor import cap_target
        cfg = self.cfg
        target, requested, capped = cap_target(cfg, target)
        budget = cfg.budget_for(target)
        problem = squad_problem(wins, budget, cfg)
        squads: List[SquadConfig] = []
        for s in range(cfg.dir_seeds):
            solver = CSPSolver(
                problem, seed=self.base_seed + s, tracer=self.tracer,
                time_limit=cfg.csp_time_limit, max_nodes=cfg.csp_max_nodes,
                **self.csp_options,
            )
            for event in solver.run():
                yield {"phase": "csp", "seed": s, **event}
            if solver._solution is not None:
                cand = _to_squad(solver._solution, cfg)
                if all(c.key() != cand.key() for c in squads):
                    squads.append(cand)
            yield {"phase": "csp_seed_done", "seed": s,
                   "solutions": len(squads)}
        if not squads:
            squads.append(_fallback_squad(cfg))
        self.last_seeds = list(squads)
        seed_gaps = [(difficulty_gap(self.heuristic.evaluate(sq), target), sq)
                     for sq in squads]
        # Tie-break menarik: bila gap dalam toleransi, pilih yang lebih
        # banyak item (CSP tetap murni; hanya urutan seed yang dipilih).
        seed_gaps.sort(key=lambda t: (t[0], -_item_count(t[1])))
        seed_gap, start = seed_gaps[0]
        yield {"phase": "ls_start", "algo": self.ls_algo,
               "seed_gap": seed_gap}
        res = self._run_ls(start, squads, wins, budget, target)
        yield {"phase": "ls_done", "algo": res.algo, "stop": res.stop,
               "iters": res.iters, "best_gap": res.best_gap}
        winner = res.best
        assign = _assign_of(winner)
        if not (is_complete(assign, cfg)
                and is_consistent(assign, wins, budget, cfg)):
            winner = start
        sim_diff = self._sim_validate(winner, target)
        self.last_result = self._finalize(winner, sim_diff, res, wins,
                                          budget, target, seed_gap,
                                          capped, requested)
        gap, verified = self.last_result.gap, self.last_result.verified
        if self.tracer is not None:
            self.tracer.emit("director_done", gap=gap, target=target,
                             verified=verified, algo=res.algo, stop=res.stop)
        yield {"phase": "done", "gap": gap, "verified": verified}


