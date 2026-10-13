"""game/ambush/queue_search.py - Local search antrean (Fase 4).

State = EnemyQueue valid. Objective = |light_sim - target| (progres).
6 neighbour (semua dicek check_queue SEBELUM dievaluasi; penolakan +
alasan dicatat): ganti-peran, ganti-item, tukar-item, tambah, kurang,
tukar-urutan.

Semua algoritma adalah GENERATOR (yield event per iterasi, return hasil
via StopIteration.value) agar resumable per frame; dipompa-tuntas ==
instant pada seed sama (ada tesnya). Bila tracer diberikan, event juga
di-emit (sumber tunggal overlay + CSV).
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from game.ambush.config import AmbushConfig
from game.ambush.difficulty import difficulty_gap
from game.ambush.enemy_queue import (
    EnemyQueue,
    EnemySlot,
    check_queue,
    is_queue_valid,
)
from game.ambush.types import BOSS, EMPTY, ITEM_TABLE, ROLE_TABLE

EPS = 1e-12

#: (kind, detail) neighbour yang dicoba.
Move = Tuple[str, str]


class _TopM:
    """Kandidat ringan terbaik (untuk rerank sim-penuh di director)."""

    def __init__(self, m: int):
        self.m = max(1, m)
        self.items: List[Tuple[float, EnemyQueue]] = []

    def push(self, gap: float, queue: EnemyQueue) -> None:
        if any(q.key() == queue.key() for _, q in self.items):
            return
        self.items.append((gap, queue))
        self.items.sort(key=lambda t: t[0])
        del self.items[self.m:]


@dataclass
class QueueLSResult:
    """Hasil satu run LS antrean (angka untuk overlay + CSV)."""

    algo: str
    best: EnemyQueue
    best_diff: float
    best_gap: float
    iters: int = 0
    evals: int = 0
    rejected: int = 0
    restarts: int = 1
    stop: str = ""
    history: List[Tuple[int, float, float]] = field(default_factory=list)
    extra: Dict = field(default_factory=dict)
    topm: List[Tuple[float, EnemyQueue]] = field(default_factory=list)


def _assign_of(queue: EnemyQueue, cfg: AmbushConfig) -> Dict[str, str]:
    out = {}
    for i in range(1, cfg.kmax + 1):
        if i <= queue.k():
            out[f"ROLE_{i}"] = queue.slots[i - 1].role
            out[f"ITEM_{i}"] = queue.slots[i - 1].item
        else:
            out[f"ROLE_{i}"] = EMPTY
            out[f"ITEM_{i}"] = EMPTY
    return out


def _mode_roles(cfg: AmbushConfig) -> List[str]:
    return [r for r in ROLE_TABLE if r != EMPTY]


_ITEM_OPTIONS = [it for it in ITEM_TABLE]


def neighbours(queue: EnemyQueue, wins: int, budget: int,
               cfg: AmbushConfig,
               ) -> Tuple[List[Tuple[EnemyQueue, Move]],
                          List[Tuple[Move, str]]]:
    """Semua neighbour VALID (+kind/detail) dan penolakan (+alasan).

    k dijaga 2..kmax oleh konstruksi + check; kanonis (padat-kiri) selalu
    terjaga sehingga tukar-urutan selalu antar slot aktif.
    """
    valid: Dict[tuple, Tuple[EnemyQueue, Move]] = {}
    rejected: List[Tuple[Move, str]] = []

    def consider(cand: EnemyQueue, move: Move) -> None:
        key = cand.key()
        if key in valid or key == queue.key():
            return
        bad = check_queue(cand, wins, budget, cfg)
        if bad:
            rejected.append((move, bad[0]))
            return
        valid[key] = (cand, move)

    def Q(slots) -> EnemyQueue:
        return EnemyQueue(slots=tuple(slots))

    members = list(queue.slots)
    k = len(members)

    for i, slot in enumerate(members):
        # (1) Ganti peran: item dipertahankan bila kompatibel, else NONE.
        for alt in _mode_roles(cfg):
            if alt == slot.role:
                continue
            item = (slot.item if slot.item == EMPTY
                    or alt in ITEM_TABLE[slot.item].allowed_roles else EMPTY)
            s2 = list(members)
            s2[i] = EnemySlot(alt, item)
            consider(Q(s2), ("ganti-peran", f"{i + 1}:{slot.role}->{alt}"))
        # (2) Ganti item satu slot.
        for alt_item in _ITEM_OPTIONS:
            if alt_item == slot.item:
                continue
            s2 = list(members)
            s2[i] = EnemySlot(slot.role, alt_item)
            consider(Q(s2), ("ganti-item", f"{i + 1}:{slot.item}->{alt_item}"))
    # (3) Tukar item dua slot.
    for a in range(k):
        for b in range(a + 1, k):
            if members[a].item == members[b].item:
                continue
            s2 = list(members)
            s2[a] = EnemySlot(members[a].role, members[b].item)
            s2[b] = EnemySlot(members[b].role, members[a].item)
            consider(Q(s2), ("tukar-item", f"{a + 1}<->{b + 1}"))
    # (4) Tambah musuh di belakang (k+1 <= kmax).
    if k < cfg.kmax:
        for alt in _mode_roles(cfg):
            consider(Q(members + [EnemySlot(alt, EMPTY)]),
                     ("tambah", f"{k + 1}:{alt}"))
    # (5) Kurangi 1 musuh lalu padatkan (k-1 >= min).
    if k > cfg.min_enemies:
        for drop in range(k):
            rest = members[:drop] + members[drop + 1:]
            consider(Q(rest), ("kurang", f"{k}->{k - 1} buang #{drop + 1}"))
    # (6) Tukar urutan dua musuh (role+item pindah bersama; revalidasi
    # Boss-terakhir + adjacency di consider).
    for a in range(k):
        for b in range(a + 1, k):
            if members[a] == members[b]:
                continue
            s2 = list(members)
            s2[a], s2[b] = s2[b], s2[a]
            consider(Q(s2), ("tukar-urutan", f"{a + 1}<->{b + 1}"))
    return list(valid.values()), rejected


def _emit(tracer, kind: str, **data):
    event = {"kind": kind, **data}
    if tracer is not None:
        tracer.emit(kind, **data)
    return event


def hill_climb_q(start: EnemyQueue, evaluator, target: float, wins: int,
                 budget: int, cfg: AmbushConfig, sideways_limit=None,
                 max_iters=None, time_limit=None, tracer=None,
                 prefilter=None, prefilter_top=None):
    """Steepest-ascent antrean (generator). Lihat modul Tabel 3 fase 2."""
    if sideways_limit is None:
        sideways_limit = cfg.hc_sideways
    if max_iters is None:
        max_iters = cfg.hc_max_iters
    if time_limit is None:
        time_limit = cfg.hc_time_limit
    if prefilter_top is None:
        prefilter_top = cfg.qs_prefilter_top
    t0 = time.perf_counter()
    cur = start
    cur_diff = evaluator.evaluate(cur)
    cur_gap = difficulty_gap(cur_diff, target)
    best, best_gap, best_diff = cur, cur_gap, cur_diff
    evals, rejected_total = 1, 0
    topm = _TopM(cfg.rerank_M)
    topm.push(cur_gap, cur)
    sideways_left, sideways_used = sideways_limit, 0
    history = [(0, cur_gap, best_gap)]
    stop = "iter_limit"
    yield _emit(tracer, "ls_start", algo="hill_climbing", start_gap=cur_gap,
                start=cur.order_str(), target=target, k=cur.k(),
                prefilter=prefilter is not None)
    if best_gap <= cfg.target_tol:
        yield _emit(tracer, "ls_skip", gap=best_gap, tol=cfg.target_tol,
                    algo="hill_climbing")
        return QueueLSResult(
            algo="hill_climbing", best=best, best_diff=best_diff,
            best_gap=best_gap, iters=0, evals=evals, stop="skipped",
            history=history)
    it = 0
    while stop == "iter_limit" and it < max_iters \
            and time.perf_counter() - t0 < time_limit:
        it += 1
        nbs, rej = neighbours(cur, wins, budget, cfg)
        rejected_total += len(rej)
        if prefilter is not None and len(nbs) > prefilter_top:
            nbs = sorted(nbs, key=lambda t: difficulty_gap(
                prefilter.evaluate(t[0]), target))[:prefilter_top]
        scored = []
        for nb, move in nbs:
            nb_diff = evaluator.evaluate(nb)
            scored.append((difficulty_gap(nb_diff, target), nb_diff, nb,
                           move))
            topm.push(scored[-1][0], nb)
        evals += len(nbs)
        rej_sample = [(m[0], r) for m, r in rej[:3]]
        if not scored:
            stop = "no_valid_neighbour"
            yield _emit(tracer, "ls_iter", algo="hill_climbing", it=it,
                        current=cur_gap, best=best_gap, evaluated=0,
                        rejected=len(rej), sideways_left=sideways_left,
                        k=cur.k(), took=None, rejected_sample=rej_sample)
            break
        scored.sort(key=lambda t: t[0])
        top_gap, top_diff, top_nb, top_move = scored[0]
        took = {"kind": top_move[0], "detail": top_move[1], "gap": top_gap}
        if top_gap < cur_gap - EPS:
            cur, cur_gap, cur_diff = top_nb, top_gap, top_diff
        elif top_gap <= cur_gap + EPS and sideways_left > 0:
            cur, cur_gap, cur_diff = top_nb, top_gap, top_diff
            sideways_left -= 1
            sideways_used += 1
        else:
            stop = ("plateau" if top_gap <= cur_gap + EPS
                    else "local_maximum")
            yield _emit(tracer, "ls_iter", algo="hill_climbing", it=it,
                        current=cur_gap, best=best_gap, evaluated=len(nbs),
                        rejected=len(rej), sideways_left=sideways_left,
                        k=cur.k(), took=None, rejected_sample=rej_sample)
            break
        if top_gap < best_gap:
            best, best_gap, best_diff = cur, top_gap, top_diff
        history.append((it, cur_gap, best_gap))
        yield _emit(tracer, "ls_iter", algo="hill_climbing", it=it,
                    current=cur_gap, best=best_gap, evaluated=len(nbs),
                    rejected=len(rej), sideways_left=sideways_left,
                    k=cur.k(), took=took, rejected_sample=rej_sample)
        if best_gap <= cfg.target_tol:
            stop = "target"
            break
    return QueueLSResult(
        algo="hill_climbing", best=best, best_diff=best_diff,
        best_gap=best_gap, iters=it, evals=evals, rejected=rejected_total,
        stop=stop, history=history, topm=list(topm.items),
        extra={"sideways_used": sideways_used,
               "sideways_limit": sideways_limit})


def random_restart_q(initial_fn, evaluator, target: float, wins: int,
                     budget: int, cfg: AmbushConfig, n_restarts=None,
                     tracer=None, **hc_kwargs):
    """HC dari n start (seed CSP + blocking). Generator: teruskan event."""
    if n_restarts is None:
        n_restarts = cfg.hc_restarts
    yield _emit(tracer, "ls_start", algo="random_restart", target=target,
                restarts=n_restarts,
                start_gap=difficulty_gap(evaluator.evaluate(initial_fn(0)),
                                         target))
    overall = None
    extra_first_eval = 1
    for r in range(n_restarts):
        res = yield from hill_climb_q(initial_fn(r), evaluator, target,
                                      wins, budget, cfg, tracer=tracer,
                                      **hc_kwargs)
        res.restarts = n_restarts
        res.algo = "random_restart"
        yield _emit(tracer, "ls_restart", restart=r, best_gap=res.best_gap,
                    stop=res.stop)
        if overall is None or res.best_gap < overall.best_gap - EPS:
            merged = _TopM(cfg.rerank_M)
            if overall is not None:
                for g, qq in overall.topm:
                    merged.push(g, qq)
            for g, qq in res.topm:
                merged.push(g, qq)
            overall = res
            overall.topm = list(merged.items)
            overall.evals += extra_first_eval
            extra_first_eval = 0
        else:
            overall.evals += res.evals
            overall.iters += res.iters
            merged = _TopM(cfg.rerank_M)
            for g, qq in overall.topm + res.topm:
                merged.push(g, qq)
            overall.topm = list(merged.items)
        if overall.best_gap <= cfg.target_tol:
            overall.stop = "target"
            break
    assert overall is not None
    return overall


def simulated_annealing_q(start: EnemyQueue, evaluator, target: float,
                          wins: int, budget: int, cfg: AmbushConfig,
                          t0=None, cooling=None, tmin=None, max_iters=None,
                          time_limit=None, seed: int = 0, tracer=None):
    """SA antrean: neighbour acak, terima buruk dgn e^(deltaE/T). Generator."""
    if t0 is None:
        t0 = cfg.sa_t0
    if cooling is None:
        cooling = cfg.sa_cooling
    if tmin is None:
        tmin = cfg.sa_tmin
    if max_iters is None:
        max_iters = cfg.sa_max_iters
    if time_limit is None:
        time_limit = cfg.sa_time_limit
    rng = random.Random(seed)
    wall = time.perf_counter()
    cur = start
    cur_gap = difficulty_gap(evaluator.evaluate(cur), target)
    best, best_gap = cur, cur_gap
    best_diff = evaluator.evaluate(cur)
    topm = _TopM(cfg.rerank_M)
    topm.push(cur_gap, cur)
    evals, rejected_total, accepted_bad = 1, 0, 0
    history = [(0, cur_gap, best_gap)]
    temp, stop, it = t0, "iter_limit", 0
    yield _emit(tracer, "ls_start", algo="simulated_annealing",
                start_gap=cur_gap, target=target, t0=t0, k=cur.k())
    if best_gap <= cfg.target_tol:
        yield _emit(tracer, "ls_skip", gap=best_gap, tol=cfg.target_tol,
                    algo="simulated_annealing")
        return QueueLSResult(
            algo="simulated_annealing", best=best, best_diff=best_diff,
            best_gap=best_gap, iters=0, evals=evals, stop="skipped",
            history=history)
    while stop == "iter_limit" and it < max_iters \
            and time.perf_counter() - wall < time_limit:
        if temp < tmin:
            stop = "cooled"
            break
        it += 1
        nbs, rej = neighbours(cur, wins, budget, cfg)
        rejected_total += len(rej)
        if not nbs:
            stop = "no_valid_neighbour"
            break
        nb, move = rng.choice(nbs)
        nb_gap = difficulty_gap(evaluator.evaluate(nb), target)
        evals += 1
        topm.push(nb_gap, nb)
        delta_e = cur_gap - nb_gap
        prob = 1.0 if delta_e >= 0 else math.exp(delta_e / temp)
        u = rng.random()
        accepted = delta_e >= 0 or u < prob
        yield _emit(tracer, "ls_sa", it=it, current=cur_gap, best=best_gap,
                    temp=temp, delta_e=delta_e, prob=prob, u=u,
                    accepted=accepted, k=cur.k(),
                    move=f"{move[0]} {move[1]}", move_gap=nb_gap,
                    rejected=len(rej))
        if accepted:
            if delta_e < 0:
                accepted_bad += 1
            cur, cur_gap = nb, nb_gap
            if nb_gap < best_gap:
                best, best_gap = nb, nb_gap
                best_diff = evaluator.evaluate(nb)
        history.append((it, cur_gap, best_gap))
        temp *= cooling
        if best_gap <= cfg.target_tol:
            stop = "target"
            break
    return QueueLSResult(
        algo="simulated_annealing", best=best, best_diff=best_diff,
        best_gap=best_gap, iters=it, evals=evals, rejected=rejected_total,
        stop=stop, history=history,
        extra={"t_final": temp, "cooling": cooling,
               "accepted_bad": accepted_bad}, topm=list(topm.items))


# ---------------------------------------------------------------------------
# Genetic algorithm: kromosom = tuple per-SLOT (role_idx, item_idx) BERURUTAN
# (ekor NONE inklusif, panjang tetap kmax). Crossover single-point ANTAR
# slot valid karena memindahkan BLOK URUTAN utuh: koherensi role-item dalam
# satu gen + urutan relatif blok tak disobek (beda dengan crossover per-bit).
# Pelanggaran (default): penalti fitness -gap - penalty*n. Repair (opsi):
# repair_queue deterministik (murah, bukan solver penuh).
# ---------------------------------------------------------------------------

def _role_opts(slot: int, cfg: AmbushConfig) -> List[str]:
    opts = [r for r in ROLE_TABLE if r != EMPTY]
    return opts if slot == 1 else [r for r in opts if r != BOSS]


def encode_queue(queue: EnemyQueue, cfg: AmbushConfig):
    """Antrean -> kromosom indeks per slot (ri<0 = NONE)."""
    chrom = []
    for i in range(1, cfg.kmax + 1):
        if i <= queue.k():
            s = queue.slots[i - 1]
            chrom.append((_role_opts(i, cfg).index(s.role),
                          _ITEM_OPTIONS.index(s.item)))
        else:
            chrom.append((-1, _ITEM_OPTIONS.index(EMPTY)))
    return tuple(chrom)


def decode_queue(chrom, cfg: AmbushConfig) -> EnemyQueue:
    """Kromosom -> antrean (gen -1 = slot NONE, dipadatkan)."""
    from game.ambush.enemy_queue import EnemyQueue as _EQ
    slots = []
    for i, (ri, ii) in enumerate(chrom, 1):
        if ri < 0:
            continue
        slots.append(EnemySlot(_role_opts(i, cfg)[ri], _ITEM_OPTIONS[ii]))
    return _EQ(slots=tuple(slots))


def repair_queue(queue: EnemyQueue, wins: int, budget: int,
                 cfg: AmbushConfig) -> EnemyQueue:
    """Proyeksi deterministik ke antrean feasible terdekat (repair=True).

    Urutan: item tanpa peran (tak mungkin di sini) -> Healer kedua+ kosong
    -> pasangan inkompatibel jadi NONE -> Fang ganda NONE-kan -> Boss
    bukan-terakhir didemosikan ke Warrior -> putuskan adjacency defensif
    (demote yang belakangan jadi Warrior) -> padatkan -> pangkas budget
    dari belakang -> isi min-2 dari depan (Warrior).
    """
    slots = [EnemySlot(s.role, s.item) for s in queue.slots]
    out_r, out_i = [], []
    for s in slots:
        r, it = s.role, s.item
        if it != EMPTY and r not in ITEM_TABLE[it].allowed_roles:
            it = EMPTY
        out_r.append(r)
        out_i.append(it)
    # Healer kedua+ -> Minion (bukan kosong: jaga k).
    seen_healer = False
    for i, r in enumerate(out_r):
        if r == "Healer":
            if seen_healer:
                out_r[i] = "Minion"
                if out_i[i] != EMPTY and "Minion" not in ITEM_TABLE[
                        out_i[i]].allowed_roles:
                    out_i[i] = EMPTY
            seen_healer = True
    # Fang ganda -> NONE-kan yang belakangan.
    seen_fang = False
    for i, it in enumerate(out_i):
        if it == "Dragon Fang":
            if seen_fang:
                out_i[i] = EMPTY
            seen_fang = True
    # Boss bukan-terakhir -> Warrior (alternatif: pindah ke akhir; demote
    # dipilih karena murah dan menjaga k).
    for i, r in enumerate(out_r):
        if r == BOSS and (i != len(out_r) - 1 or wins < cfg.boss_min_wins):
            out_r[i] = "Warrior"
            if out_i[i] != EMPTY and "Warrior" not in ITEM_TABLE[
                    out_i[i]].allowed_roles:
                out_i[i] = EMPTY
    # Adjacency defensif: demote yang belakangan jadi Warrior.
    defensive = {"Healer", "Tank"}
    for i in range(len(out_r) - 1):
        if out_r[i] in defensive and out_r[i + 1] in defensive:
            out_r[i + 1] = "Warrior"
            if out_i[i + 1] != EMPTY and "Warrior" not in ITEM_TABLE[
                    out_i[i + 1]].allowed_roles:
                out_i[i + 1] = EMPTY
    members = [(r, it) for r, it in zip(out_r, out_i) if r != EMPTY]
    while len(members) < cfg.min_enemies:
        members.append(("Warrior", EMPTY))
    while len(members) > cfg.min_enemies - 1:
        cand = EnemyQueue(slots=tuple(EnemySlot(r, it) for r, it in members))
        if cand.total_cost() <= budget or len(members) <= cfg.min_enemies:
            break
        members.pop()
    return EnemyQueue(slots=tuple(EnemySlot(r, it) for r, it in members))


def _random_queue(rng: random.Random, cfg: AmbushConfig) -> EnemyQueue:
    k = rng.randint(cfg.min_enemies, cfg.kmax)
    slots = []
    for i in range(1, k + 1):
        opts = _role_opts(i, cfg)
        slots.append(EnemySlot(rng.choice(opts),
                               rng.choice(_ITEM_OPTIONS)))
    return EnemyQueue(slots=tuple(slots))


def genetic_q(seeds: List[EnemyQueue], evaluator, target: float, wins: int,
              budget: int, cfg: AmbushConfig, pop_size=None, generations=None,
              cx_prob=None, mut_prob=None, tour_size=None, penalty=None,
              repair=None, seed: int = 0, time_limit=None, tracer=None):
    """GA antrean berurutan (generator). Fitness = -gap [- penalti]."""
    if pop_size is None:
        pop_size = cfg.ga_pop
    if generations is None:
        generations = cfg.ga_gens
    if cx_prob is None:
        cx_prob = cfg.ga_cx
    if mut_prob is None:
        mut_prob = cfg.ga_mut
    if tour_size is None:
        tour_size = cfg.ga_tour
    if penalty is None:
        penalty = cfg.ga_penalty
    if repair is None:
        repair = cfg.ga_repair
    if time_limit is None:
        time_limit = cfg.ga_time_limit
    rng = random.Random(seed)
    wall = time.perf_counter()

    def fitness_of(chrom):
        squad = decode_queue(chrom, cfg)
        if repair:
            squad = repair_queue(squad, wins, budget, cfg)
            nviol = 0
        else:
            nviol = len(check_queue(squad, wins, budget, cfg))
        gap = difficulty_gap(evaluator.evaluate(squad), target)
        return (-gap - penalty * nviol, gap, nviol, squad)

    pop = [encode_queue(s, cfg) for s in seeds[:pop_size]]
    tries = 0
    while len(pop) < pop_size and tries < pop_size * 50:
        tries += 1
        cand = _random_queue(rng, cfg)
        if repair or is_queue_valid(cand, wins, budget, cfg):
            pop.append(encode_queue(cand, cfg))
    while len(pop) < pop_size:
        pop.append(encode_queue(seeds[0], cfg))
    evals = 0
    best_overall = None
    best_feas = None
    history = []
    stop, gen = "generations", 0
    topm = _TopM(cfg.rerank_M)
    yield _emit(tracer, "ls_start", algo="genetic", target=target,
                pop=pop_size, repair=repair)
    for gen in range(1, generations + 1):
        if time.perf_counter() - wall > time_limit:
            stop = "time_limit"
            break
        scored = [fitness_of(ch) for ch in pop]
        evals += len(pop)
        fits = [s[0] for s in scored]
        for fit, gap, nviol, squad in scored:
            if best_overall is None or fit > best_overall[0]:
                best_overall = (fit, squad, gap)
            if nviol == 0 and (best_feas is None or gap < best_feas[0]):
                best_feas = (gap, squad, gap)
        cur_best_gap = best_feas[0] if best_feas else best_overall[2]
        history.append((gen, cur_best_gap, cur_best_gap))
        for _fit, gap, nviol, squad in scored:
            if nviol == 0:
                topm.push(gap, squad)
        yield _emit(tracer, "ga_gen", gen=gen, best_fit=max(fits),
                    avg_fit=sum(fits) / len(fits), best_gap=cur_best_gap,
                    pop_summary=_pop_summary(scored))
        if best_feas is not None and best_feas[0] <= cfg.target_tol:
            stop = "target"
            break
        elite = max(range(len(pop)), key=lambda i: scored[i][0])
        nxt = [pop[elite]]
        while len(nxt) < pop_size:
            p1 = _tournament(pop, scored, tour_size, rng)
            p2 = _tournament(pop, scored, tour_size, rng)
            c1, c2 = _crossover(p1, p2, cx_prob, rng, cfg)
            nxt.append(_mutate(c1, mut_prob, rng, cfg))
            if len(nxt) < pop_size:
                nxt.append(_mutate(c2, mut_prob, rng, cfg))
        pop = nxt
    if best_feas is not None:
        gap, squad, _ = best_feas
    else:
        _, squad, gap = best_overall
    return QueueLSResult(
        algo="genetic", best=squad, best_diff=evaluator.evaluate(squad),
        best_gap=gap, iters=gen, evals=evals, rejected=0,
        stop=stop, history=history, topm=list(topm.items),
        extra={"pop_size": pop_size, "repair": repair,
               "feasible_found": best_feas is not None})


def _pop_summary(scored) -> str:
    kinds: Dict[str, int] = {}
    for _, _, nviol, squad in scored:
        kinds["ok" if nviol == 0 else "bad"] = kinds.get(
            "ok" if nviol == 0 else "bad", 0) + 1
        kinds[f"k{squad.k()}"] = kinds.get(f"k{squad.k()}", 0) + 1
    return ",".join(f"{k}:{v}" for k, v in sorted(kinds.items()))


def _tournament(pop, scored, size: int, rng: random.Random):
    cand = rng.sample(range(len(pop)), min(size, len(pop)))
    return pop[max(cand, key=lambda i: scored[i][0])]


def _crossover(p1, p2, prob: float, rng: random.Random, cfg: AmbushConfig):
    if rng.random() >= prob or cfg.kmax < 2:
        return p1, p2
    point = rng.randrange(1, cfg.kmax)
    return p1[:point] + p2[point:], p2[:point] + p1[point:]


def _mutate(chrom, prob: float, rng: random.Random, cfg: AmbushConfig):
    out = list(chrom)
    for i in range(1, cfg.kmax + 1):
        if rng.random() >= prob:
            continue
        ri, ii = out[i - 1]
        if rng.random() < 0.5 or ri < 0:
            ri = rng.randrange(len(_role_opts(i, cfg)))
            ii = _ITEM_OPTIONS.index(EMPTY) if rng.random() < 0.3 else ii
        else:
            ii = rng.randrange(len(_ITEM_OPTIONS))
        out[i - 1] = (ri, ii)
    return tuple(out)


def drain(gen):
    """Pompa generator LS sampai habis; kembalikan (result, events)."""
    events = []
    try:
        while True:
            events.append(next(gen))
    except StopIteration as done:
        return done.value, events
