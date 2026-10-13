"""tests/test_ambush_queue.py - Tes model duel berurutan (Fase 1: model+config).

Jalan: `python3 tests/test_ambush_queue.py` (tanpa pygame/display).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.buff import Buff  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.enemy_queue import (  # noqa: E402
    EnemyQueue,
    EnemySlot,
    check_queue,
    is_queue_valid,
    queue_to_buffs,
    slot_to_buff,
)
from game.ambush.types import EMPTY  # noqa: E402

CFG = AmbushConfig()


def q(*pairs) -> EnemyQueue:
    """Bangun antrean dari pasangan (role, item)."""
    return EnemyQueue(slots=tuple(EnemySlot(r, it) for r, it in pairs))


def test_config_defaults():
    assert CFG.mode == "SEQUENTIAL"
    assert CFG.min_enemies == 2 and CFG.kmax == 4
    assert CFG.rest_heal_pct == 0.25  # Tahap-A S terkunci
    assert CFG.npc_potions_carry is False
    assert CFG.light_sim_enabled is True  # objektif LS (Fase 4)
    assert CFG.light_sim_games == 4
    assert CFG.allow_heuristic_prefilter is True  # hanya pra-penyaring
    assert CFG.qs_prefilter_top == 12
    assert CFG.rerank_M == 2 and CFG.chain_rerank_games == 4
    assert CFG.budget_q_for(0.5) == 12  # 8 + round(0.5*8)
    assert CFG.budget_q_for(0.3) == 10 and CFG.budget_q_for(0.8) == 14


def test_valid_queue():
    queue = q(("Warrior", "Iron Sword"), ("Archer", "Swift Boots"),
              ("Tank", "Heavy Shield"))
    assert queue.total_cost() == 13  # (3+1)+(3+1)+(4+1)
    assert is_queue_valid(queue, wins=0, budget=13, cfg=CFG)
    assert queue.k() == 3
    assert queue.order_str() == "Warrior>Archer>Tank"


def test_k_bounds():
    assert not is_queue_valid(q(("Warrior", EMPTY)), wins=0, budget=99,
                              cfg=CFG)  # k=1 < min 2
    assert not is_queue_valid(
        q(*[("Warrior", EMPTY)] * 5), wins=0, budget=99, cfg=CFG)  # k=5 > 4
    assert any("2..4" in v for v in check_queue(
        q(("Warrior", EMPTY)), 0, 99, CFG))


def test_boss_last_and_gated():
    mid = q(("Boss", EMPTY), ("Warrior", EMPTY))
    assert any("terakhir" in v for v in check_queue(mid, 9, 99, CFG))
    early = q(("Warrior", EMPTY), ("Boss", "Dragon Fang"))
    assert any("wins" in v for v in check_queue(early, 0, 99, CFG))
    assert is_queue_valid(early, wins=3, budget=99, cfg=CFG)


def test_adjacency_defensive():
    bad = q(("Healer", "Healing Charm"), ("Tank", "Heavy Shield"))
    assert any("berturutan" in v for v in check_queue(bad, 0, 99, CFG))
    tank_tank = q(("Warrior", EMPTY), ("Tank", EMPTY), ("Tank", EMPTY))
    assert any("berturutan" in v for v in check_queue(tank_tank, 0, 99, CFG))
    ok = q(("Healer", "Healing Charm"), ("Warrior", "Iron Sword"))
    assert is_queue_valid(ok, wins=0, budget=99, cfg=CFG)


def test_single_source_numbers():
    slot = EnemySlot("Tank", "Heavy Shield")
    buff = slot_to_buff(slot, CFG)
    assert isinstance(buff, Buff)
    assert buff.hp == 4 and abs(buff.armor - 0.15) < 1e-9  # Tahap-A FINAL
    # Sama persis bila dihitung dua kali (HUD == battle == sim).
    assert slot_to_buff(slot, CFG) == buff
    buffs = queue_to_buffs(q(("Tank", "Heavy Shield"),
                             ("Warrior", "Iron Sword")), CFG)
    assert len(buffs) == 2 and buffs[0] == buff


def test_budget_and_unique_and_compat():
    over = q(("Boss", "Dragon Fang"), ("Mage", EMPTY))
    assert any("budget" in v for v in check_queue(over, 9, 5, CFG))
    dup = q(("Warrior", "Dragon Fang"), ("Archer", "Dragon Fang"))
    assert any("unik" in v for v in check_queue(dup, 0, 99, CFG))
    bad_pair = q(("Healer", "Iron Sword"), ("Warrior", EMPTY))
    assert any("kompatibel" in v for v in check_queue(bad_pair, 0, 99, CFG))


def test_key_stable():
    a = q(("Tank", EMPTY), ("Warrior", EMPTY))
    b = q(("Warrior", EMPTY), ("Tank", EMPTY))
    assert a.key() != b.key()  # urutan bermakna (mempengaruhi skor rantai)



# --- Fase 2: aturan antrean di CSP (solver tak berubah, hanya predikat) ---

def _qprob(wins=0, target=0.5, **kw):
    from game.ambush.csp_solver import squad_problem
    return squad_problem(wins, CFG.budget_q_for(target), CFG,
                         queue_rules=True, min_active=2, **kw)


def _assign(roles, items):
    out = {}
    for i, r in enumerate(roles, 1):
        out[f"ROLE_{i}"] = r
    for i, it in enumerate(items, 1):
        out[f"ITEM_{i}"] = it
    return out


def test_csp_boss_last():
    from game.ambush.constraints import check
    bad = _assign(["Boss", "Warrior", EMPTY, EMPTY],
                  [EMPTY] * 4)
    assert any("terakhir" in v for v in check(
        bad, 9, 99, CFG, queue_rules=True, min_active=2))
    ok = _assign(["Warrior", "Boss", EMPTY, EMPTY], [EMPTY] * 4)
    assert not check(ok, 9, 99, CFG, queue_rules=True, min_active=2)


def test_csp_adjacency():
    from game.ambush.constraints import check
    for a, b in (("Healer", "Tank"), ("Tank", "Tank"), ("Healer", "Healer")):
        roles = [a, b, EMPTY, EMPTY]
        bad = _assign(roles, [EMPTY] * 4)
        assert any("berturutan" in v for v in check(
            bad, 0, 99, CFG, queue_rules=True, min_active=2)), (a, b)
    ok = _assign(["Healer", "Warrior", EMPTY, EMPTY], [EMPTY] * 4)
    assert not check(ok, 0, 99, CFG, queue_rules=True, min_active=2)
    # Mode BUFF lama tak berubah: Tank-Tank tetap boleh.
    tank2 = _assign(["Tank", "Tank", EMPTY, EMPTY], [EMPTY] * 4)
    assert not check(tank2, 0, 99, CFG)


def test_csp_min_two_active():
    from game.ambush.constraints import check
    one = _assign(["Warrior", EMPTY, EMPTY, EMPTY], [EMPTY] * 4)
    assert any("minimal 2" in v for v in check(
        one, 0, 99, CFG, queue_rules=True, min_active=2))
    two = _assign(["Warrior", "Warrior", EMPTY, EMPTY], [EMPTY] * 4)
    assert not check(two, 0, 99, CFG, queue_rules=True, min_active=2)
    # Mode BUFF lama: 1 anggota tetap valid.
    assert not check(one, 0, 99, CFG)


def test_csp_canonical_unchanged():
    from game.ambush.constraints import check
    hole = _assign(["Warrior", EMPTY, "Archer", EMPTY], [EMPTY] * 4)
    assert any("slot kosong" in v for v in check(
        hole, 0, 99, CFG, queue_rules=True, min_active=2))


def test_ac3_adjacency_prunes():
    from game.ambush.csp_solver import CSPSolver
    for lead, gone in (("Tank", "Healer"), ("Tank", "Tank"),
                       ("Healer", "Healer")):
        prob = _qprob()
        prob.domains = dict(prob.domains)
        prob.domains["ROLE_1"] = [lead]
        prob.domains["ROLE_2"] = [gone, "Warrior"]
        sol, stats = CSPSolver(prob).solve()
        assert stats["pruned"] >= 1, (lead, gone, stats)
        assert stats["revises"] >= 1
        assert sol is not None and sol["ROLE_2"] == "Warrior", (lead, gone)


def test_ac3_boss_last_prunes():
    from game.ambush.csp_solver import CSPSolver
    prob = _qprob(wins=9)
    prob.domains = dict(prob.domains)
    prob.domains["ROLE_1"] = ["Boss", "Warrior"]
    prob.domains["ROLE_2"] = ["Warrior"]
    sol, stats = CSPSolver(prob).solve()
    assert stats["pruned"] >= 1
    assert sol is not None and sol["ROLE_1"] == "Warrior"


def test_degree_positive_queue():
    prob = _qprob()
    for v in prob.variables:
        assert len(prob.neighbors[v]) > 0, v


def test_lcv_differs_queue():
    from game.ambush.csp_solver import CSPSolver
    from game.ambush.trace import TraceBuffer
    tr = TraceBuffer()
    CSPSolver(_qprob(), tracer=tr).solve()
    first = tr.of_kind("lcv")[0]
    removed = [c["removed"] for c in first["candidates"]]
    assert max(removed) - min(removed) >= 2, first  # Healer vs Warrior


def test_queue_solves_multiseed_targets():
    from game.ambush.csp_solver import CSPSolver
    from game.ambush.enemy_queue import is_queue_valid, queue_from_assign
    for target in (0.3, 0.5, 0.8):
        for seed in range(6):
            prob = _qprob(target=target)
            sol, stats = CSPSolver(prob, seed=seed).solve()
            assert sol is not None, (target, seed)
            queue = queue_from_assign(sol, CFG)
            assert 2 <= queue.k() <= CFG.kmax
            assert is_queue_valid(queue, 0, CFG.budget_q_for(target), CFG), (
                target, seed, sol)


def test_mode_flags_drive_rules():
    """Jaminan: mode SEQUENTIAL menyalakan aturan antrean via csp_flags()."""
    from dataclasses import replace
    from game.ambush.constraints import check
    from game.ambush.csp_solver import squad_problem
    seq = replace(CFG, mode="SEQUENTIAL")
    buff = replace(CFG, mode="BUFF")
    assert seq.csp_flags() == {"queue_rules": True, "min_active": 2}
    assert buff.csp_flags() == {"queue_rules": False, "min_active": 1}
    # Masalah yang dibangun LEWAT helper (cara director Fase 4 nanti):
    tank2 = {"ROLE_1": "Tank", "ROLE_2": "Tank", "ROLE_3": EMPTY,
             "ROLE_4": EMPTY, "ITEM_1": EMPTY, "ITEM_2": EMPTY,
             "ITEM_3": EMPTY, "ITEM_4": EMPTY}
    prob_seq = squad_problem(0, 99, seq, **seq.csp_flags())
    prob_buff = squad_problem(0, 99, buff, **buff.csp_flags())
    assert not prob_seq.partial_ok(tank2)  # ditolak di SEQUENTIAL...
    assert prob_buff.partial_ok(tank2)  # ...tetap lolos di BUFF


def test_ablation_reproducible():
    """Ablasi reproducible: seed sama -> statistik dan solusi identik."""
    from game.ambush.csp_solver import CSPSolver
    for kw in (dict(use_mrv=False, use_degree=False, use_lcv=False,
                    inference="none"),
               dict(use_mrv=True, use_degree=True, use_lcv=True,
                    inference="ac3")):
        a, sa = CSPSolver(_qprob(), seed=11, **kw).solve()
        b, sb = CSPSolver(_qprob(), seed=11, **kw).solve()
        assert a == b and sa["nodes"] == sb["nodes"]


def test_hybrid_locked_slots():
    """HYBRID: slot dikunci (domain singleton) tetap valid/gagal benar."""
    from game.ambush.csp_solver import CSPSolver
    from game.ambush.enemy_queue import is_queue_valid, queue_from_assign
    # Kunci ROLE_1=Warrior + ITEM_1=Sword: harus ada solusi memuatnya.
    prob = _qprob()
    prob.domains = dict(prob.domains)
    prob.domains["ROLE_1"] = ["Warrior"]
    prob.domains["ITEM_1"] = ["Iron Sword"]
    sol, _ = CSPSolver(prob, seed=4).solve()
    assert sol is not None
    assert sol["ROLE_1"] == "Warrior" and sol["ITEM_1"] == "Iron Sword"
    assert is_queue_valid(queue_from_assign(sol, CFG), 0,
                          CFG.budget_q_for(0.5), CFG)
    # Kunci mustahil: Healer + Sword (inkompatibel) -> gagal bersih.
    prob2 = _qprob()
    prob2.domains = dict(prob2.domains)
    prob2.domains["ROLE_1"] = ["Healer"]
    prob2.domains["ITEM_1"] = ["Iron Sword"]
    sol2, stats2 = CSPSolver(prob2, seed=4).solve()
    assert sol2 is None and stats2["stop"] == "unsatisfiable"



def test_lower_bound_shortfall():
    """Lower-bound: mustahil mencapai min-2 -> prune sejak parsial."""
    from game.ambush.constraints import check
    # 3 NONE + 1 belum isi: maks 1 aktif < 2 -> langgar walau budget lega.
    partial = {"ROLE_1": EMPTY, "ROLE_2": EMPTY, "ROLE_3": EMPTY}
    bad = check(partial, 0, 99, CFG, queue_rules=True, min_active=2)
    assert any("minimal 2" in v for v in bad)
    # 2 belum isi masih bisa -> lolos.
    partial2 = {"ROLE_1": "Warrior", "ROLE_3": EMPTY}
    assert not check(partial2, 0, 99, CFG, queue_rules=True, min_active=2)


def test_lower_bound_budget():
    """Lower-bound biaya: isi termurah pun over-budget -> prune."""
    from game.ambush.constraints import check
    # 1 aktif (Warrior=3) + butuh 1 lagi (termurah Minion=1) = 4 > budget 3.
    partial = {"ROLE_1": "Warrior"}
    bad = check(partial, 0, 3, CFG, queue_rules=True, min_active=2)
    assert any("budget" in v for v in bad)
    # Budget 4 muat (3+1) -> lolos.
    assert not check(partial, 0, 4, CFG, queue_rules=True, min_active=2)


def test_lower_bound_sample_oracle():
    """20.000 assignment acak: klaim 'valid' baru == oracle independen.

    Oracle = check_queue pada antrean yang dipadatkan, dibandingkan HANYA
    untuk assignment kanonis lengkap tanpa item-yatim (di situlah pemadatan
    lossless sehingga verdict harus sama). Pemadatan sengaja membuang
    item-yatim (solver tak pernah menghasilkannya: unary + pair_ok
    melarangnya saat search); kasus itu di-skip di sini. Parsial hanya
    diuji tak-crash.
    """
    import random
    from game.ambush.constraints import check
    from game.ambush.enemy_queue import check_queue, queue_from_assign
    from game.ambush.types import EMPTY
    rng = random.Random(77)
    roles = ["Warrior", "Archer", "Mage", "Healer", "Tank", "Boss", EMPTY]
    items = ["NONE", "Iron Sword", "Heavy Shield", "Swift Boots",
             "Healing Charm", "Dragon Fang"]
    compared = 0
    for _ in range(20000):
        assign = {}
        for i in (1, 2, 3, 4):
            if rng.random() < 0.85:  # 15% dibiarkan tak-terisi (parsial)
                assign[f"ROLE_{i}"] = rng.choice(roles)
            if rng.random() < 0.85:
                assign[f"ITEM_{i}"] = rng.choice(items)
        new_bad = check(assign, 0, 12, CFG, queue_rules=True, min_active=2)
        assert isinstance(new_bad, list)
        r = [assign.get(f"ROLE_{i}") for i in (1, 2, 3, 4)]
        if any(v is None for v in r):
            continue  # parsial: tak ada oracle
        seen_none = hole = False
        for v in r:
            if v == EMPTY:
                seen_none = True
            elif seen_none:
                hole = True
                break
        if hole:
            continue  # berlubang: pemadatan lossy, skip
        orphan = any(assign.get(f"ITEM_{i}") not in (None, "NONE")
                     and r[i - 1] == EMPTY for i in (1, 2, 3, 4))
        if orphan:
            continue  # item-yatim: solver tak pernah menghasilkan, skip
        compared += 1
        q = queue_from_assign(assign, CFG)
        assert (not new_bad) == (not check_queue(q, 0, 12, CFG)), assign
    assert compared > 5000, compared


def test_ac3_pre_event():
    """Trace pra-pencarian AC-3 terekspos sebagai event sendiri."""
    from game.ambush.csp_solver import CSPSolver
    from game.ambush.trace import TraceBuffer
    tr = TraceBuffer()
    CSPSolver(_qprob(), tracer=tr).solve()
    pre = tr.of_kind("ac3_pre")
    assert len(pre) == 1
    assert pre[0]["removed"] >= 0 and "details" in pre[0]


def test_seed_diversity_targets():
    """Pembangkit seed beragam: target keragaman Fase 2c (50 seed, t=0.5)."""
    from collections import Counter
    from game.ambush.csp_solver import CSPSolver
    from game.ambush.enemy_queue import is_queue_valid, queue_from_assign
    r1 = Counter()
    uniq = set()
    for s in range(50):
        sol, _ = CSPSolver(
            _qprob(target=0.5), seed=s, use_mrv=False, use_degree=False,
            use_lcv=False, inference="none").solve()
        queue = queue_from_assign(sol, CFG)
        assert is_queue_valid(queue, 0, CFG.budget_q_for(0.5), CFG)
        r1[queue.slots[0].role] += 1
        uniq.add(queue.key())
    assert max(r1.values()) <= 30, dict(r1)  # tak ada peran > 60%
    assert len(uniq) >= 20, len(uniq)



def test_chain_heuristic_order_sensitive():
    """Heuristik rantai: urutan sama-set -> jejak HP berbeda (Fase 3).

    Bobot eksplisit (bukan file): yang diuji STRUKTUR peka-urutan,
    bukan nilai fit. Fallback murni jenuh (pool menyerap semua) sehingga
    tak cocok untuk asersi ini.
    """
    from game.ambush.chain_eval import ChainHeuristic, FALLBACK_WEIGHTS
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot
    from game.ambush.player_loadout import PlayerLoadout
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    members = [("Tank", "Heavy Shield"), ("Warrior", "Iron Sword"),
               ("Mage", "Swift Boots")]
    weights = dict(FALLBACK_WEIGHTS, w_atk=3.0, slope=0.3)
    ev = ChainHeuristic(CFG, pl, weights)
    fwd = ev.per_duel(EnemyQueue(
        slots=tuple(EnemySlot(r, i) for r, i in members)))
    bwd = ev.per_duel(EnemyQueue(
        slots=tuple(EnemySlot(r, i) for r, i in members[::-1])))
    assert [h for h, _, _ in fwd] != [h for h, _, _ in bwd]
    assert ev.evaluate(EnemyQueue(
        slots=tuple(EnemySlot(r, i) for r, i in members))) == \
        ev.evaluate(EnemyQueue(
            slots=tuple(EnemySlot(r, i) for r, i in members)))


def test_chain_sim_reproducible_cached():
    """Sim rantai: seed sama -> sama; cache dipakai (Fase 3, kecil)."""
    from game.ambush.chain_eval import ChainSim
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot
    from game.ambush.player_loadout import PlayerLoadout
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    q = EnemyQueue(slots=(EnemySlot("Warrior", "NONE"),
                          EnemySlot("Warrior", "NONE")))
    a = ChainSim(CFG, pl, seed=5, games=2).evaluate(q)
    ev = ChainSim(CFG, pl, seed=5, games=2)
    assert ev.evaluate(q) == a
    assert len(ev._cache) == 1
    assert ev.evaluate(q) == a and len(ev._cache) == 1


def test_weights_json_honest_record():
    """JSON bobot ada dan jujur (berisi metrik, termasuk bila gagal)."""
    import json
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath("tests/test_ambush_queue.py"))), "data",
        "queue_weights.json")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    assert {"version", "date", "fit_seed", "weights", "metrics"} <= set(doc)
    assert {"pearson_test", "spearman_test", "rmse_test"} <= set(doc["metrics"])



def test_progress_objective_bounds_shift():
    """Objektif progres di [0,1]; loadout kuat menurunkan difficulty."""
    from game.ambush.chain_eval import ChainHeuristic, ChainSim
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot
    from game.ambush.player_loadout import PlayerLoadout
    weak = PlayerLoadout(items=("NONE", "NONE"))
    mid = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    strong = PlayerLoadout(items=("Dragon Fang", "Heavy Shield"))
    q = EnemyQueue(slots=(EnemySlot("Warrior", "NONE"),
                          EnemySlot("Archer", "NONE")))
    sims = [ChainSim(CFG, pl, seed=5, games=2).evaluate(q)
            for pl in (weak, mid, strong)]
    assert all(0.0 <= v <= 1.0 for v in sims), sims
    # Lemah >= sedang (kuat tak diurutkan: Fang Tahap-A (1/1) memukul lebih
    # lemah dari Sword (2/0) sehingga label "kuat" basi untuk offense).
    assert sims[0] >= sims[1], sims
    heurs = [ChainHeuristic(CFG, pl).evaluate(q) for pl in (weak, mid, strong)]
    assert all(0.0 <= v <= 1.0 for v in heurs)


def test_weights_gate_uncalibrated():
    """Bobot gagal-ambang: resolve menolak tanpa izin eksplisit."""
    from dataclasses import replace
    from game.ambush import chain_eval as ce
    _, cal = ce.resolve_weights(replace(CFG, allow_fallback_weights=True))
    assert cal is False  # JSON saat ini calibrated=false
    try:
        ce.resolve_weights(replace(CFG, allow_fallback_weights=False))
        raise SystemExit("seharusnya menolak")
    except RuntimeError:
        pass
    try:
        ce.resolve_weights(replace(CFG, allow_fallback_weights=False),
                           path="/tmp/tidak-ada.json")
        raise SystemExit("seharusnya menolak")
    except RuntimeError:
        pass



def test_rest_heal_applies():
    """Bug rest mati: helper + ekstrem rest=100% mengubah difficulty."""
    from dataclasses import replace
    from game.ambush.chain_eval import ChainSim, apply_rest
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot
    from game.ambush.player_loadout import PlayerLoadout
    assert apply_rest(42, 100, 1.0) == 100
    assert apply_rest(0, 100, 1.0) == 0  # gugur tetap gugur
    assert apply_rest(42, 100, 0.0) == 42
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    q = EnemyQueue(slots=(EnemySlot("Warrior", "NONE"),
                          EnemySlot("Warrior", "NONE")))
    d0 = ChainSim(replace(CFG, rest_heal_pct=0.0), pl, seed=5,
                  games=4).evaluate(q)
    d1 = ChainSim(replace(CFG, rest_heal_pct=1.0), pl, seed=5,
                  games=4).evaluate(q)
    assert 0.0 < d0 < 1.0, d0
    assert d1 < d0, (d0, d1)  # HP duel-2 penuh -> lebih mudah



def test_enemy_scale_sequential_only():
    """Skala stat musuh hanya berlaku di SEQUENTIAL (BUFF tak tersentuh)."""
    from dataclasses import replace
    from game.ambush.buff import squad_to_buff
    from game.ambush.chain_eval import scaled_enemy_buff
    from game.ambush.enemy_queue import EnemySlot
    from game.ambush.types import SquadConfig
    slot = EnemySlot("Tank", "Heavy Shield")
    seq = replace(CFG, enemy_stat_scale=0.8)
    buff_mode = replace(CFG, mode="BUFF", enemy_stat_scale=0.8)
    assert scaled_enemy_buff(slot, seq).hp == 3  # Tahap-A: int(4 x 0.8)
    assert scaled_enemy_buff(slot, buff_mode).hp == 4  # Tahap-A, diabaikan
    squad = SquadConfig(roles=("Tank", "NONE", "NONE", "NONE"),
                        items=("Heavy Shield", "NONE", "NONE", "NONE"))
    assert squad_to_buff(squad, seq) == squad_to_buff(squad, CFG)


def test_potion_bonus_default_zero():
    """Default potion murni terbawa (bonus hanya pembanding eksplisit)."""
    assert CFG.potion_bonus_per_duel == 0
    assert CFG.enemy_stat_scale == 1.0
    assert CFG.rest_heal_pct == 0.25  # Tahap-A S terkunci



def test_potion_bonus_reaches_duel():
    """Plumbing potion: refill vs terbawa -> duel-2 masuk bawa 3 potion.

    Antrean Mage-Boss menghabiskan 1 potion di duel-1 (seed tetap):
    tanpa refill duel-2 masuk bawa 2; dengan refill default bawa 3 penuh.
    """
    from dataclasses import replace
    from game.ambush.chain_eval import ChainSim
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot
    from game.ambush.player_loadout import PlayerLoadout
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    q = EnemyQueue(slots=(EnemySlot("Mage", "NONE"),
                          EnemySlot("Boss", "NONE")))
    e0 = ChainSim(replace(CFG, refill_potions_each_duel=False), pl, seed=5,
                  games=1)
    e0.evaluate(q)
    eR = ChainSim(CFG, pl, seed=5, games=1)
    eR.evaluate(q)
    assert e0.last_entries[1][1] == 2, e0.last_entries  # terbawa (habis 1)
    assert eR.last_entries[1][1] == 3, eR.last_entries  # isi penuh



def test_minion_sequential_only():
    """Minion ada di domain SEQUENTIAL, tak ada di BUFF (mode tak berubah)."""
    from dataclasses import replace
    from game.ambush.config import AmbushConfig
    from game.ambush.constraints import build_domains
    seq = replace(AmbushConfig(), mode="SEQUENTIAL")
    buff = replace(AmbushConfig(), mode="BUFF")
    assert "Minion" in build_domains(0, seq)["ROLE_1"]
    assert "Minion" not in build_domains(0, buff)["ROLE_1"]
    assert "Minion" not in build_domains(0, buff)["ROLE_2"]


def test_minion_rules_and_display():
    """Minion: Fang dilarang, non-defensif, cost 1, tampil jelas."""
    from game.ambush.enemy_queue import EnemySlot, slot_to_buff
    bad = q(("Minion", "Dragon Fang"), ("Warrior", "NONE"))
    assert any("kompatibel" in v or "unik" in v or "Fang" in v
               for v in check_queue(bad, 0, 99, CFG))
    ok = q(("Tank", "Heavy Shield"), ("Minion", "Iron Sword"))
    assert is_queue_valid(ok, wins=0, budget=99, cfg=CFG)  # bukan defensif
    slot = EnemySlot("Minion", "Iron Sword")
    assert slot.cost() == 2  # 1 + 1
    buff = slot_to_buff(slot, CFG)
    assert buff.hp == -50 and buff.atk == -7  # M3: delta tampil di HUD
    assert slot.role == "Minion"  # nama jelas, tanpa aset baru



def test_minion_candidates_rules():
    """Semua kandidat (M1/M2/M3) valid di aturan SEQUENTIAL; BUFF tetap."""
    import sys as _sys
    _sys.path.insert(0, str(Path("experiments").resolve()))
    from game.ambush.types import ROLE_TABLE
    from minion_gate import CANDIDATES
    saved = ROLE_TABLE["Minion"]
    try:
        for name, spec in CANDIDATES.items():
            ROLE_TABLE["Minion"] = spec
            queue = q(("Minion", "NONE"), ("Warrior", "Iron Sword"))
            assert is_queue_valid(queue, wins=0, budget=99, cfg=CFG), name
            assert EnemySlot("Minion", "NONE").cost() == spec.cost, name
    finally:
        ROLE_TABLE["Minion"] = saved
    from dataclasses import replace
    from game.ambush.config import AmbushConfig
    from game.ambush.constraints import build_domains
    buff = replace(AmbushConfig(), mode="BUFF")
    assert "Minion" not in build_domains(0, buff)["ROLE_1"]



def test_honest_gap_label():
    """Label jujur: dalam tol vs di luar jangkauan (jalur 3)."""
    from game.ambush.governor import honest_gap_label
    assert honest_gap_label(0.01, 0.02) == "pas target (gap 0.010)"
    assert "di luar jangkauan" in honest_gap_label(0.20, 0.02)
    assert "0.200" in honest_gap_label(0.20, 0.02)



def test_cache_key_covers_config():
    """Kunci cache berubah bila stat/skala/potion/rest berubah (audit)."""
    from dataclasses import replace
    from game.ambush.chain_eval import config_fingerprint
    from game.ambush.types import ROLE_TABLE, RoleSpec, stat_fingerprint
    base = config_fingerprint(CFG)
    assert config_fingerprint(replace(CFG, enemy_stat_scale=0.9)) != base
    assert config_fingerprint(replace(CFG, potion_bonus_per_duel=1)) != base
    assert config_fingerprint(replace(CFG, rest_heal_pct=0.1)) != base
    assert config_fingerprint(replace(CFG, mode="BUFF")) != base
    saved = ROLE_TABLE["Minion"]
    before = stat_fingerprint()
    ROLE_TABLE["Minion"] = RoleSpec("Minion", hp=0, atk=0, cost=1)
    try:
        assert stat_fingerprint() != before
    finally:
        ROLE_TABLE["Minion"] = saved
    assert stat_fingerprint() == before


def test_m1_m3_differ_same_seed():
    """M1 vs M3 pada seed sama HARUS beda (gagal bila identik = basi)."""
    from game.ambush.chain_eval import ChainSim
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot
    from game.ambush.player_loadout import PlayerLoadout
    from game.ambush.types import ROLE_TABLE, RoleSpec
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    q = EnemyQueue(slots=(EnemySlot("Minion", "NONE"),
                          EnemySlot("Minion", "NONE")))
    saved = ROLE_TABLE["Minion"]
    ROLE_TABLE["Minion"] = RoleSpec("Minion", hp=80, atk=10, cost=1)
    try:
        a = ChainSim(CFG, pl, seed=5, games=8).evaluate(q)
    finally:
        ROLE_TABLE["Minion"] = saved
    b = ChainSim(CFG, pl, seed=5, games=8).evaluate(q)
    assert abs(a - b) > 1e-9, (a, b)  # tabel-beda -> skor beda (cache jujur)


def test_cache_consistent_same_config():
    """Cache vs tanpa-cache identik pada konfigurasi sama."""
    from game.ambush.chain_eval import ChainSim
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot
    from game.ambush.player_loadout import PlayerLoadout
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    q = EnemyQueue(slots=(EnemySlot("Warrior", "NONE"),
                          EnemySlot("Archer", "NONE")))
    ev = ChainSim(CFG, pl, seed=5, games=2)
    first = ev.evaluate(q)
    assert len(ev._cache) == 1
    assert ev.evaluate(q) == first  # cache hit
    fresh = ChainSim(CFG, pl, seed=5, games=2).evaluate(q)
    assert fresh == first


def test_weights_rejected_on_hash_mismatch():
    """Bobot ditolak bila hash konfigurasi tak cocok (anti-basi)."""
    from dataclasses import replace
    from game.ambush import chain_eval as ce
    good = {"calibrated": True,
            "config_hash": ce.config_fingerprint(CFG),
            "metrics": {"pearson_test": 0.9, "spearman_test": 0.9,
                        "rmse_test": 0.01},
            "weights": dict(ce.FALLBACK_WEIGHTS)}
    import json, tempfile, os
    for doc, cal in ((good, True),
                     ({**good, "config_hash": "basi"}, False)):
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as f:
            json.dump(doc, f)
            path = f.name
        try:
            _, got = ce.resolve_weights(
                replace(CFG, allow_fallback_weights=True), path=path)
            assert got is cal, (doc, got)
        finally:
            os.unlink(path)



def _qeval(games=2, seed=1):
    from game.ambush.chain_eval import ChainLightSim
    from game.ambush.player_loadout import PlayerLoadout
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    return ChainLightSim(CFG, pl, seed=seed, games=games), pl


def _qseed(seed=0):
    from game.ambush.csp_solver import CSPSolver, squad_problem
    from game.ambush.enemy_queue import queue_from_assign
    prob = squad_problem(0, CFG.budget_q_for(0.5), CFG,
                         **CFG.csp_flags())
    sol, _ = CSPSolver(prob, seed=seed).solve()
    return queue_from_assign(sol, CFG)


def test_neighbours_fuzz_valid():
    """Fuzz 500: neighbour tak pernah langgar constraint, k 2..4."""
    import random
    from game.ambush.enemy_queue import is_queue_valid
    from game.ambush.queue_search import neighbours
    rng = random.Random(11)
    roles = ["Warrior", "Archer", "Mage", "Healer", "Tank", "Minion"]
    items = ["NONE", "Iron Sword", "Heavy Shield", "Swift Boots",
             "Healing Charm", "Dragon Fang"]
    for _ in range(500):
        k = rng.randint(2, 4)
        members = []
        for _ in range(k):
            members.append((rng.choice(roles), rng.choice(items)))
        from game.ambush.enemy_queue import EnemyQueue, EnemySlot
        start = EnemyQueue(slots=tuple(EnemySlot(r, i) for r, i in members))
        budget = CFG.budget_q_for(0.5)
        nbs, rej = neighbours(start, 0, budget, CFG)
        for nb, _move in nbs:
            assert 2 <= nb.k() <= CFG.kmax
            assert is_queue_valid(nb, 0, budget, CFG), nb
        for _move, reason in rej:
            assert isinstance(reason, str) and reason


def test_ls_seed_vs_final():
    """3 seed/target: LS tak pernah memburuk (membaik atau sudah pas)."""
    from game.ambush.difficulty import difficulty_gap
    from game.ambush.queue_search import drain, hill_climb_q
    ev, _pl = _qeval()
    for target in (0.4, 0.5, 0.8):
        for seed in (1, 2, 3):
            start = _qseed(seed)
            budget = CFG.budget_q_for(target)
            sg = difficulty_gap(ev.evaluate(start), target)
            res, _ = drain(hill_climb_q(
                start, ev, target, 0, budget, CFG, max_iters=10))
            assert res.best_gap <= sg + 1e-9, (target, seed)
            assert res.stop in ("target", "local_maximum", "plateau",
                                "iter_limit", "time_limit",
                                "no_valid_neighbour", "skipped")


def test_ls_reproducible_and_crn():
    """Seed sama -> hasil sama; tetangga dievaluasi deterministik."""
    from game.ambush.queue_search import drain, hill_climb_q
    ev, _pl = _qeval()
    kw = dict(evaluator=ev, target=0.5, wins=0,
              budget=CFG.budget_q_for(0.5), cfg=CFG, max_iters=10)
    a, _ = drain(hill_climb_q(_qseed(2), **kw))
    b, _ = drain(hill_climb_q(_qseed(2), **kw))
    assert a.best.key() == b.best.key() and a.best_gap == b.best_gap
    c, _ = drain(hill_climb_q(_qseed(2), evaluator=_qeval()[0], target=0.5,
                              wins=0, budget=CFG.budget_q_for(0.5), cfg=CFG,
                              max_iters=10))
    assert c.best.key() == a.best.key()  # CRN: instance baru, sama


def test_ls_skip_message():
    """Seed dalam toleransi -> 'skipped' + event ls_skip."""
    from game.ambush.queue_search import drain, hill_climb_q
    ev, _pl = _qeval()
    start = _qseed(1)
    target = ev.evaluate(start)  # gap tepat 0 <= tol
    res, events = drain(hill_climb_q(start, ev, target, 0,
                                     CFG.budget_q_for(target), CFG))
    assert res.stop == "skipped" and res.iters == 0
    kinds = [e["kind"] for e in events]
    assert "ls_skip" in kinds


def test_queue_director_verified():
    """Director antrean: verified, seed-mode, resumable==instant."""
    from game.ambush.director import AmbushDirector
    from game.ambush.governor import DifficultyGovernor
    from game.ambush.player_loadout import PlayerLoadout
    from game.ambush.trace import TraceBuffer
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    kw = dict(tracer=TraceBuffer(), base_seed=3)
    a = AmbushDirector(CFG, DifficultyGovernor(CFG), **kw).plan_queue(
        0, 0.5, pl)
    assert a.verified is True and 2 <= a.queue.k() <= 4
    assert a.seed_mode == "BEST (gameplay)"
    b = AmbushDirector(CFG, DifficultyGovernor(CFG), **kw)
    list(b.run_gen_queue(0, 0.5, pl))
    r = b.last_queue_result
    assert r.queue.key() == a.queue.key() and abs(r.gap - a.gap) < 1e-9
    c = AmbushDirector(CFG, DifficultyGovernor(CFG), **kw).plan_queue(
        0, 0.5, pl, demo=True)
    assert c.seed_mode == "RANDOM (demo)"



def _qrun(k=3, hp=100, potions=3):
    from game.ambush.buff import Buff
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot
    from game.ambush.flow.queue_driver import QueueRun
    roles = ["Warrior", "Archer", "Mage", "Tank"][:k]
    queue = EnemyQueue(slots=tuple(EnemySlot(r, "NONE") for r in roles))
    return QueueRun(queue=queue, buffs=[Buff() for _ in roles], target=0.5,
                    pred_light=0.5, pred_full=0.5, hp=hp, potions=potions,
                    cap=100, cfg=CFG)


def test_queue_run_flow():
    """ENEMY_1 -> transisi -> ENEMY_2 ...; menang/kalah tercatat benar."""
    run = _qrun(k=3)
    assert run.duel_label() == "MUSUH 1/3"
    assert run.record(62, 2, True) == "next"  # APPLY rest di sini (+25)
    assert (run.idx, run.hp, run.potions) == (1, 87, 3)  # potion isi penuh
    assert run.duel_label() == "MUSUH 2/3"
    assert run.record(40, 1, True) == "next"  # 40+25=65
    assert run.hp == 65
    assert run.record(0, 0, False) == "failed"
    assert run.failed_at == 2
    assert run.progress() == 2 / 3
    row = run.result_row(7, "kalah")
    assert row["duel_menang"] == 2 and row["duel_gagal_ke"] == 3
    assert row["hp_sisa_per_duel"] == "62;40;0"
    run2 = _qrun(k=2)
    assert run2.record(80, 3, True) == "next"
    assert run2.record(55, 2, True) == "won_all"
    assert run2.progress() == 1.0 and run2.margin() == (0.8 + 0.55) / 2


def test_queue_run_rest_uses_helper():
    """Driver WAJIB memakai apply_rest (angka sim == game)."""
    from unittest import mock
    import game.ambush.flow.queue_driver as qd
    run = _qrun(k=2, hp=100)
    with mock.patch.object(qd, "apply_rest",
                           wraps=qd.apply_rest) as spy:
        assert run.record(62, 2, True) == "next"
        assert spy.call_count == 1
        assert spy.call_args[0][:2] == (62, 100)


def test_governor_progress_binary():
    """Governor menerima progres + biner + duel_gagal_ke."""
    from game.ambush.governor import DifficultyGovernor
    gov = DifficultyGovernor(CFG)
    gov.update("npc", 0.3, progress=0.5, failed_at=2)
    assert gov.last_progress == 0.5 and gov.last_failed_at == 2
    gov.update("player", 0.6, progress=1.0, failed_at=None)
    assert gov.last_progress == 1.0 and gov.last_failed_at is None
    # Panggilan lama tetap sah.
    gov.update("player", 0.5)
    assert gov.last_progress == 1.0


def test_c_key_gating():
    """C hanya aktif saat F3 + fase PREP_*; tak auto-ulang."""
    import pygame
    from game.ambush.overlay_ambush import AmbushDebugOverlay
    import main as game_main
    ov = AmbushDebugOverlay()
    ov.visible = False
    state = {"ambush_overlay": ov, "mode": "PREP_NPC_CSP",
             "ambush_cfg": CFG, "target_override": None, "status": ""}
    game_main.handle_director_key(pygame.K_c, None, None, None, state)
    assert state["target_override"] is None  # F3 mati -> abaikan
    ov.visible = True
    game_main.handle_director_key(pygame.K_c, None, None, None, state)
    assert state["target_override"] == 0.40
    game_main.handle_director_key(pygame.K_c, None, None, None, state)
    assert state["target_override"] == 0.50
    game_main.handle_director_key(pygame.K_c, None, None, None, state)
    assert state["target_override"] == 0.80
    game_main.handle_director_key(pygame.K_c, None, None, None, state)
    assert state["target_override"] is None  # ADAPTIF
    state["mode"] = "BATTLE"
    game_main.handle_director_key(pygame.K_c, None, None, None, state)
    assert state["target_override"] is None  # di luar PREP_* -> abaikan


def test_state_machine_transition():
    """TRANSITION terhubung BATTLE dua arah; urutan penuh legal."""
    from game.ambush.flow.prep_state_machine import (
        check_sequence,
        is_legal,
    )
    assert is_legal("BATTLE", "TRANSITION")
    assert is_legal("TRANSITION", "BATTLE")
    assert check_sequence(["EXPLORE", "PREP_PLAYER", "PREP_NPC_CSP",
                           "PREP_NPC_LS", "PREP_REVIEW", "BATTLE",
                           "TRANSITION", "BATTLE", "EXPLORE"]) == []


def test_headless_full_queue_uses_slot_buff():
    """Satu antrean headless: buff battle == slot_to_buff; HP/potion bawa."""
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    from battle_system import BattleSystem
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot, slot_to_buff
    queue = EnemyQueue(slots=(EnemySlot("Tank", "Heavy Shield"),
                              EnemySlot("Minion", "NONE")))
    buffs = [slot_to_buff(s, CFG) for s in queue.slots]
    first = BattleSystem(player_hp=62, npc_buff=buffs[0],
                         player_potions=2, npc_potions=3,
                         duel_label="MUSUH 1/2")
    assert first.npc_max_hp == 70 + buffs[0].hp
    assert first.state.player_hp == 62 and first.state.player_potions == 2
    assert first.state.npc_potions == 3
    assert first.duel_label == "MUSUH 1/2"



def test_autoplay_reproducible():
    """Autoplay seed-tetap -> baris CSV identik antar run."""
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import importlib.util
    import tempfile
    spec = importlib.util.spec_from_file_location(
        "autoplay_mod", os.path.join(ROOT, "experiments", "autoplay.py"))
    autoplay_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(autoplay_mod)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "battle_result.csv")
        old = autoplay_mod.OUT
        autoplay_mod.OUT = out
        try:
            autoplay_mod.main(2, 4242)
            with open(out, encoding="utf-8") as f:
                first = f.read()
            os.unlink(out)
            autoplay_mod.main(2, 4242)
            with open(out, encoding="utf-8") as f:
                second = f.read()
        finally:
            autoplay_mod.OUT = old
    assert first == second and "duel_menang" in first


def test_transition_draw():
    """Layar transisi tergambar tanpa error (headless)."""
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    from game.ambush.ui.transition import draw_transition
    screen = pygame.display.set_mode((800, 600))
    font = pygame.font.SysFont("consolas", 14)
    draw_transition(screen, font, 2, 3, "Tank", "Heavy Shield", 62, 100,
                    2, 1.5)



def test_governor_progress_scaled():
    """Governor memakai progres: tipis < sapuan; streak hanya wipe."""
    from game.ambush.governor import DifficultyGovernor
    gov = DifficultyGovernor(CFG)
    gov.update("npc", 0.3, progress=0.67)
    narrow = gov.target
    gov2 = DifficultyGovernor(CFG)
    gov2.update("npc", 0.3, progress=0.0)
    assert narrow > gov2.target  # tipis turun lebih sedikit
    assert gov.loss_streak == 0  # tipis memutus streak
    assert gov2.loss_streak == 1  # sapuan memperpanjang
    gov2.update("npc", 0.3, progress=0.0)
    assert gov2.loss_streak == 2



def _headless_battle(queue, hp=100, potions=3, size=(1280, 720)):
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    from battle_system import BattleSystem
    from game.ambush.enemy_queue import slot_to_buff
    from game.ambush.player_loadout import PlayerLoadout, loadout_to_buff
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    buffs = [slot_to_buff(s, CFG) for s in queue.slots]
    screen = pygame.display.set_mode(size)
    font = pygame.font.SysFont("consolas", 14)
    battles = []
    for i, buff in enumerate(buffs):
        b = BattleSystem(player_hp=hp, npc_buff=buff,
                         player_buff=loadout_to_buff(pl, CFG),
                         player_loadout=pl, target=0.5, sim_rate="0.5",
                         player_potions=potions, npc_potions=3,
                         duel_label=f"MUSUH {i + 1}/{len(buffs)}",
                         queue_view={"order": [(s.role, s.item)
                                               for s in queue.slots],
                                     "idx": i,
                                     "done": [j < i for j in
                                              range(len(buffs))]})
        b.draw(screen, font)
        battles.append(b)
    return battles, buffs, screen


def test_hud_numbers_equal_battle():
    """HUD==battle: baris efek = slot_to_buff yang dipakai duel (k=2..4)."""
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot, slot_to_buff
    from game.ambush.ui.battle_hud import buff_lines_short
    for roles in (("Warrior", "Mage"), ("Tank", "Healer", "Archer"),
                  ("Minion", "Mage", "Tank", "Warrior")):
        queue = EnemyQueue(slots=tuple(EnemySlot(r, "NONE") for r in roles))
        battles, buffs, _ = _headless_battle(queue)
        for b, buff, slot in zip(battles, buffs, queue.slots):
            assert b.npc_buff == buff == slot_to_buff(slot, CFG)
            lines = buff_lines_short(buff, "npc")
            assert lines  # tak kosong
            assert b.npc_max_hp == 70 + buff.hp


def test_render_two_sizes_k_range():
    """Render tak crash: k=2,3,4 x (1280x720, 1600x900)."""
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot
    for roles in (("Warrior", "Mage"), ("Tank", "Healer", "Archer"),
                  ("Minion", "Mage", "Tank", "Warrior")):
        queue = EnemyQueue(slots=tuple(EnemySlot(r, "NONE") for r in roles))
        for size in ((1280, 720), (1600, 900)):
            _headless_battle(queue, size=size)


def test_overlay_equals_csv():
    """Angka overlay == baris CSV dari trace yang sama."""
    import csv
    import tempfile
    from game.ambush.csv_export import write_csp_csv, write_ls_csv
    from game.ambush.director import AmbushDirector
    from game.ambush.governor import DifficultyGovernor
    from game.ambush.overlay_ambush import build_view
    from game.ambush.player_loadout import PlayerLoadout
    from game.ambush.trace import TraceBuffer
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    tr = TraceBuffer()
    d = AmbushDirector(CFG, DifficultyGovernor(CFG), tracer=tr, base_seed=5)
    res = d.plan_queue(0, 0.5, pl)
    with tempfile.TemporaryDirectory() as tmp:
        csp_p = tmp + "/c.csv"
        ls_p = tmp + "/l.csv"
        assert write_csp_csv(tr, csp_p) > 0
        write_ls_csv(tr, ls_p, run_id=1, algo=res.ls_algo)
        with open(csp_p, encoding="utf-8") as f:
            csp_rows = list(csv.DictReader(f))
        with open(ls_p, encoding="utf-8") as f:
            ls_rows = [r for r in csv.DictReader(f)]
    view = build_view(tr, {"phase": "Selesai", "status": "selesai",
                           "ls_algo": res.ls_algo, "target": 0.5,
                           "pump": "instant", "toggles": {},
                           "sideways_limit": 10, "ls_stop": res.ls_stop,
                           "seed_gap": res.seed_gap, "squad": res.queue,
                           "sim": f"{res.sim_difficulty:.3f}"})
    last_csp = tr.latest("csp_done")
    assert view["nodes"] == last_csp["nodes"]
    assert view["backtracks"] == last_csp["backtracks"]
    assert abs(float(view["best"]) - res.gap) < 1e-9
    n_ls_events = len(tr.of_kind("ls_iter")) + len(tr.of_kind("ls_sa")) + \
        len(tr.of_kind("ga_gen"))
    assert len(ls_rows) == n_ls_events
    assert len(csp_rows) > 0


def test_compare_nonblocking():
    """Panel perbandingan: 11 unit, tiap pump < 1 dtk, selesai tuntas."""
    import time
    from game.ambush.compare_panel import build_units, pump_compare
    from game.ambush.csp_solver import squad_problem
    from game.ambush.director import AmbushDirector
    from game.ambush.governor import DifficultyGovernor
    from game.ambush.player_loadout import PlayerLoadout
    from game.ambush.trace import TraceBuffer
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    d = AmbushDirector(CFG, DifficultyGovernor(CFG), tracer=TraceBuffer(),
                       base_seed=3)
    res = d.plan_queue(0, 0.5, pl)
    ctx = {"cfg": CFG, "wins": 0, "budget": res.budget, "target": 0.5,
           "player": pl, "seeds": d.last_queue_seeds,
           "start": d.last_queue_start,
           "problem": lambda: squad_problem(0, res.budget, CFG,
                                            **CFG.csp_flags())}
    state = {"compare": {"units": build_units(ctx), "idx": 0, "total": 11,
                         "results": {}, "done": False, "max_ms": 0.0}}
    assert len(state["compare"]["units"]) == 11
    pumps = 0
    while not state["compare"]["done"]:
        t0 = time.perf_counter()
        pump_compare(state)
        assert (time.perf_counter() - t0) * 1000.0 < 1000.0
        pumps += 1
        assert pumps <= 11
    assert len(state["compare"]["results"]) == 11


def test_overlay_tabs():
    """Tab T memfilter seksi (ALL/CSP/LS/CMP)."""
    from game.ambush.overlay_ambush import AmbushDebugOverlay, TABS
    ov = AmbushDebugOverlay()
    assert TABS[ov.tab] == "ALL"
    ov.cycle_tab()
    assert TABS[ov.tab] == "CSP"
    view = {"phase": "CSP", "status": "berjalan", "ls_algo": "-",
            "target": 0.5, "target_label": "", "seed_mode": "", "pump": "s",
            "toggles": {}, "nodes": 0, "backtracks": 0, "pruned": 0,
            "csp_ms": 0.0, "csp_stop": "", "var": "-", "reason": {},
            "domains": {}, "domains0": {}, "candidates": [], "queue": 0,
            "arc": "-", "removed": 0, "queue_max": 0, "revises": 0,
            "ac3_pre": {}, "complete_consistent": "", "ls_it": 0, "cur": "",
            "best": "", "sideways": "", "restarts": 0, "evaluated": "",
            "rejected": 0, "sa": {}, "sa_bad": 0, "ga_best": "",
            "ga_avg": "", "ga_pop": "", "ls_stop": "", "ls_skip": {},
            "seed_gap": "", "final_gap": "", "verified": False,
            "history": [], "squad": None, "buff_lines": [], "pl_lines": [],
            "sim": "", "sim_gap": "", "prefilter": "", "seed_queue": None,
            "final_queue": None, "budget": "", "per_duel": None,
            "sim_hp_in": [], "honest": "", "event_log": [], "compare": None,
            "target_tol": 0.02}
    rows = ov._rows(view, "CSP")
    assert all(r[0] in ("H", "CSP") for r in rows)



def test_overlay_draw_with_compare():
    """Regresi crash CMP (NameError tab): draw dengan hasil perbandingan."""
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    from game.ambush.overlay_ambush import AmbushDebugOverlay
    screen = pygame.display.set_mode((1280, 720))
    font = pygame.font.SysFont("consolas", 14)
    ov = AmbushDebugOverlay()
    base = {"phase": "Selesai", "status": "selesai", "ls_algo": "-",
            "target": 0.5, "target_label": "", "seed_mode": "", "pump": "s",
            "toggles": {}, "nodes": 0, "backtracks": 0, "pruned": 0,
            "csp_ms": 0.0, "csp_stop": "", "var": "-", "reason": "-",
            "domains": {}, "domains0": {}, "candidates": [], "queue": 0,
            "arc": "-", "removed": 0, "queue_max": 0, "revises": 0,
            "ac3_pre": {}, "complete_consistent": "", "ls_it": 0, "cur": "",
            "best": "", "sideways": "", "restarts": 0, "evaluated": "",
            "rejected": 0, "sa": {}, "sa_bad": 0, "ga_best": "",
            "ga_avg": "", "ga_pop": "", "ls_stop": "", "ls_skip": {},
            "seed_gap": "", "final_gap": "", "verified": False,
            "history": [], "squad": None, "buff_lines": [], "pl_lines": [],
            "sim": "", "sim_gap": "", "prefilter": "", "seed_queue": None,
            "final_queue": None, "budget": "", "per_duel": None,
            "sim_hp_in": [], "honest": "", "event_log": [], "compare": None,
            "target_tol": 0.02}
    cmp_ = {"done": True, "idx": 11, "total": 11, "max_ms": 62,
            "results": {f"u{i}": {"gap": 0.1, "evals": 5, "ms": 2.0}
                        for i in range(11)}}
    for tab in range(4):
        ov.tab = tab
        view = dict(base, compare=cmp_)
        ov.update(view)
        ov.draw(screen, font)  # dulu NameError di tab CMP



def _duel_start_state():
    from game.ambush.buff_ai import BuffAwareAI, BuffBattleState
    from game.ambush.enemy_queue import EnemySlot, slot_to_buff
    from game.ambush.player_loadout import PlayerLoadout, loadout_to_buff
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    eb = slot_to_buff(EnemySlot("Warrior", "NONE"), CFG)
    pbuff = loadout_to_buff(pl, CFG)
    state = BuffBattleState(player_hp=100, npc_hp=80, turn=0, buff=eb,
                            player_buff=pbuff)
    ai = BuffAwareAI(depth=1, buff=eb, player_buff=pbuff)
    return state, ai


def test_policies_attack_and_legal():
    """Semua kebijakan menyerang sesuai definisi (anti-pola-ATTACK)."""
    from game.ambush.buff_ai import BuffAwareAI
    state, ai = _duel_start_state()

    def greedy(ai, st, isnpc):
        best, bk = None, None
        for a in st.legal_actions(isnpc):
            k = ai.evaluate_state(st.apply_action(isnpc, a))
            if bk is None or (k > bk if isnpc else k < bk):
                best, bk = a, k
        return best

    assert greedy(ai, state, False) == "SPECIAL"  # bukan ATTACK membabi
    assert greedy(ai, state, False) in state.legal_actions(False)
    ai4 = BuffAwareAI(depth=4, buff=state.buff, player_buff=None)
    first = ai4.think(state, run_baseline=False,
                      root_is_npc=False)["best_action"]
    assert first in state.legal_actions(False)


def test_conserve_veto_binds():
    """Hemat-baru BERBEDA dari greedy via play() konteks-antrean.

    Konteks duel awal (duels_left=3, bukan terakhir): Mage memakai potion di
    greedy tapi ditahan hemat -> plies berbeda, hasil sama (1.0). Mekanisme
    veto sendiri diuji unit di test_hemat_veto_queue_binding (tak tergantung
    stat); sel ini hanya membuktikan veto MENGUBAH jalannya duel nyata.
    """
    import sys as _sys
    _sys.path.insert(0, str(Path("experiments").resolve()))
    from balance_baseline import play
    from game.ambush.player_loadout import PlayerLoadout
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    kw = dict(seed=5, games=6, cfg=CFG, duels_left=3, duel_last=False)
    g = play("Mage", "NONE", pl, "greedy", **kw)
    h = play("Mage", "NONE", pl, "hemat", **kw)
    assert g != h  # veto mengubah jalannya duel
    assert g[0] == h[0]  # hasil menang sama (bukan sulap)


def test_policies_all_choose_special():
    """Langkah 0: SEMUA kebijakan pemain pilih SPECIAL saat tersedia.

    Mencakup: shared policies.greedy_action, sim ringan (ChainLightSim),
    sim penuh (ChainSim/think depth4 dua sisi), skrip ukur
    (balance_baseline.play greedy), autoplay (greedy/think_policy),
    run_all._greedy. Anti-pola typo `key < key` (selalu ATTACK).
    """
    import sys as _sys
    _sys.path.insert(0, str(Path("experiments").resolve()))
    from game.ambush.buff_ai import BuffAwareAI, BuffBattleState
    from game.ambush.enemy_queue import EnemySlot, slot_to_buff
    from game.ambush.player_loadout import PlayerLoadout, loadout_to_buff
    from game.ambush.policies import greedy_action, think_policy
    from adversarial_ai import MAX_HP
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    eb = slot_to_buff(EnemySlot("Warrior", "NONE"), CFG)
    pbuff = loadout_to_buff(pl, CFG)
    state = BuffBattleState(player_hp=MAX_HP, npc_hp=80, turn=0, buff=eb,
                            player_buff=pbuff)
    ai = BuffAwareAI(depth=1, buff=eb, player_buff=pbuff)
    assert greedy_action(ai, state, False) == "SPECIAL"
    # Sim ringan: ChainLightSim._greedy mendelegasi ke shared.
    from game.ambush.chain_eval import ChainLightSim
    light = ChainLightSim(CFG, pl, seed=5, games=2)
    assert light._greedy(ai, state, False) == "SPECIAL"
    # Skrip ukur: balance_baseline.greedy.
    import balance_baseline as _bb
    assert _bb.greedy(ai, state, False) == "SPECIAL"
    # Autoplay: greedy + think_policy greedy.
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "autoplay_chk", str(Path(ROOT) / "experiments" / "autoplay.py"))
    _ap = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_ap)
    assert _ap.greedy(ai, state, False) == "SPECIAL"
    _ap._POLICY = "greedy"
    assert _ap.think_policy(ai, state, False, False, True, 0, MAX_HP) \
        == "SPECIAL"
    # run_all._greedy.
    _spec2 = _ilu.spec_from_file_location(
        "runall_chk", str(Path(ROOT) / "experiments" / "run_all.py"))
    _ra = _ilu.module_from_spec(_spec2)
    _spec2.loader.exec_module(_ra)
    assert _ra._greedy(ai, state, False) == "SPECIAL"
    # Sim penuh: depth-4 think dua sisi legal (NPC MAX, player MIN).
    ai4 = BuffAwareAI(depth=4, buff=eb, player_buff=pbuff)
    assert ai4.think(state, run_baseline=False,
                     root_is_npc=False)["best_action"] in \
        state.legal_actions(False)
    nstate = BuffBattleState(player_hp=MAX_HP, npc_hp=80, turn=1, buff=eb,
                             player_buff=pbuff)
    assert ai4.think(nstate, run_baseline=False,
                     root_is_npc=True)["best_action"] in \
        nstate.legal_actions(True)
    # think_policy depth4 juga legal.
    _ap._POLICY = "depth4"
    assert _ap.think_policy(ai4, state, False, False, True, 0, MAX_HP) in \
        state.legal_actions(False)


def test_hemat_veto_queue_binding():
    """Hemat-baru: veto mengikat di awal antrean, longgar di duel terakhir."""
    from game.ambush.buff_ai import BuffBattleState
    from game.ambush.policies import hemat_veto
    from adversarial_ai import MAX_HP
    # HP penuh + potion penuh + 3 duel tersisa -> veto mengikat.
    s = BuffBattleState(player_hp=MAX_HP, npc_hp=100, turn=0)
    s.player_potions = 3
    assert hemat_veto(s, False, 3, MAX_HP) is True
    # HP kritis (<40%) + duel terakhir -> potion diizinkan.
    s2 = BuffBattleState(player_hp=30, npc_hp=100, turn=0)
    s2.player_potions = 3
    assert hemat_veto(s2, True, 0, MAX_HP) is False
    # HP kritis + potion tersisa > sisa duel -> diizinkan.
    s3 = BuffBattleState(player_hp=30, npc_hp=100, turn=0)
    s3.player_potions = 3
    assert hemat_veto(s3, False, 1, MAX_HP) is False
    # HP kritis + potion pas-pasan untuk sisa duel -> veto (cadangan).
    s4 = BuffBattleState(player_hp=30, npc_hp=100, turn=0)
    s4.player_potions = 1
    assert hemat_veto(s4, False, 2, MAX_HP) is True
    # HP tinggi walau duel terakhir -> tetap veto (bukan darurat).
    s5 = BuffBattleState(player_hp=90, npc_hp=100, turn=0)
    s5.player_potions = 3
    assert hemat_veto(s5, True, 0, MAX_HP) is True


def test_k1_k2_sample_smoke():
    """Sampel kecil K1/K2: win/plies terukur, legal, slot_to_buff eksak.

    Angka-angka duel sungguhan == slot_to_buff untuk SEMUA peran+item
    termasuk Minion (7x6=42 kombinasi, jalur BuffBattleState).
    """
    import sys as _sys
    _sys.path.insert(0, str(Path("experiments").resolve()))
    from balance_baseline import play
    from game.ambush.enemy_queue import EnemySlot, slot_to_buff
    from game.ambush.player_loadout import PlayerLoadout
    from game.ambush.types import ITEM_TABLE, ROLE_TABLE
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    for r in ("Warrior", "Tank", "Healer", "Archer", "Mage", "Boss",
              "Minion"):
        for it in ITEM_TABLE:
            b = slot_to_buff(EnemySlot(r, it), CFG)
            rs, its = ROLE_TABLE[r], ITEM_TABLE[it]
            assert (b.hp, b.atk, b.regen, b.chip) == (
                rs.hp + its.hp, rs.atk + its.atk, rs.regen + its.regen,
                rs.chip + its.chip), (r, it)
    for role in ("Warrior", "Mage", "Minion"):
        w, n, _ = play(role, "NONE", pl, "greedy", 5, 4, CFG)
        assert 0.0 <= w <= 1.0 and n >= 1
    w, n, _ = play("Warrior", "NONE", pl, "depth4", 5, 2, CFG)
    assert 0.0 <= w <= 1.0 and n >= 1


def test_k6_items_smoke():
    """Sampel kecil K6: semua item terukur tanpa crash (smoke).

    Gerbang penuh K6 (depth-4 N=20, <=50pp, Fang wajib) diukur di
    eksperimen Langkah R; N kecil di sini terlalu noisy untuk dijadikan
    gerbang (mis. Warrior+Shield ayunan 83pp pada greedy N=6 = temuan
    knife-edge, bukan regresi).
    """
    import sys as _sys
    _sys.path.insert(0, str(Path("experiments").resolve()))
    from balance_baseline import play
    from game.ambush.player_loadout import PlayerLoadout
    from game.ambush.types import ITEM_TABLE
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    for role in ("Warrior", "Mage", "Minion", "Boss"):
        for it in ITEM_TABLE:
            w, n, _ = play(role, it, pl, "greedy", 5, 4, CFG)
            assert 0.0 <= w <= 1.0 and n >= 1, (role, it)


def test_csp_solvability_20x3():
    """Solvabilitas CSP: 20 seed x 3 target semua valid (gerbang R)."""
    from game.ambush.csp_solver import CSPSolver
    from game.ambush.enemy_queue import is_queue_valid, queue_from_assign
    for target in (0.40, 0.50, 0.80):
        for seed in range(20):
            prob = _qprob(target=target)
            sol, _ = CSPSolver(prob, seed=seed).solve()
            assert sol is not None, (target, seed)
            queue = queue_from_assign(sol, CFG)
            assert is_queue_valid(queue, 0, CFG.budget_q_for(target),
                                  CFG), (target, seed)


def test_rest_driver_sim_same_value():
    """Rest via apply_rest: driver QueueRun == simulator ChainSim/Light."""
    from game.ambush.chain_eval import apply_rest
    from game.ambush.flow.queue_driver import QueueRun
    assert apply_rest(42, 100, 0.25) == 67
    assert apply_rest(0, 100, 0.25) == 0
    run = QueueRun(queue=q(("Warrior", EMPTY), ("Mage", EMPTY)), buffs=[],
                   target=0.5, pred_light=0.5, pred_full=None, hp=42,
                   potions=3, cap=100, cfg=CFG)
    # pct default Tahap-A 0.25 -> HP dipulihkan via helper (bukan mentah).
    assert run.cfg.rest_heal_pct == 0.25
    assert run.record(42, 2, True) == "next" and run.hp == 67  # 42+25


def test_enemy_base_hp_70():
    """Darah dasar musuh 70 (player tetap 100): satu jalur enemy_max_hp."""
    from battle_system import BattleSystem
    from game.ambush.buff import Buff
    from game.ambush.enemy_queue import (ENEMY_BASE_HP, EnemySlot,
                                         enemy_max_hp, slot_to_buff)
    from game.ambush.player_loadout import PlayerLoadout
    assert ENEMY_BASE_HP == 70 and CFG.enemy_base_hp == 70
    assert enemy_max_hp(Buff()) == 70
    for role in ("Warrior", "Tank", "Healer", "Archer", "Mage", "Boss",
                 "Minion"):
        eb = slot_to_buff(EnemySlot(role, "NONE"), CFG)
        assert enemy_max_hp(eb, CFG.enemy_base_hp) == max(
            1, 70 + eb.hp), role
    assert enemy_max_hp(slot_to_buff(EnemySlot("Minion", "NONE"), CFG)) \
        == 20  # 70-50: lemah tapi tetap dilawan
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    b = BattleSystem(player_hp=100,
                     npc_buff=slot_to_buff(EnemySlot("Warrior", "NONE"),
                                           CFG),
                     player_potions=3, npc_potions=2)
    assert b.npc_max_hp == 70 + 10 and b.player_max_hp == 100
    assert b.state.npc_hp == 80 and b.state.player_hp == 100
    polo = BattleSystem(player_hp=100)  # duel polos: musuh juga 70
    assert polo.state.npc_hp == 70 and polo.state.player_hp == 100


def test_potion_refill_each_duel():
    """Heal isi penuh tiap ganti lawan: driver == sim ringan == sim penuh."""
    from dataclasses import replace
    from game.ambush.chain_eval import (ChainLightSim, ChainSim,
                                        carry_potions)
    from game.ambush.enemy_queue import EnemyQueue, EnemySlot
    from game.ambush.flow.queue_driver import QueueRun
    from game.ambush.player_loadout import PlayerLoadout
    from adversarial_ai import POTION_LIMIT
    assert CFG.refill_potions_each_duel is True
    assert carry_potions(0, CFG) == POTION_LIMIT
    assert carry_potions(1, CFG) == POTION_LIMIT
    assert carry_potions(1, replace(
        CFG, refill_potions_each_duel=False)) == 1  # murni terbawa bila mati
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    run = QueueRun(queue=q(("Boss", EMPTY), ("Warrior", EMPTY)), buffs=[],
                   target=0.5, pred_light=0.5, pred_full=None, hp=79,
                   potions=2, cap=100, cfg=CFG)
    assert run.record(79, 1, True) == "next" and run.potions == POTION_LIMIT
    qb = EnemyQueue(slots=(EnemySlot("Boss", "NONE"),
                           EnemySlot("Warrior", "NONE")))
    for ev in (ChainLightSim(CFG, pl, seed=5, games=1),
               ChainSim(CFG, pl, seed=5, games=1)):
        ev.evaluate(qb)
        assert ev.last_entries[1][1] == POTION_LIMIT, ev.last_entries



if __name__ == "__main__":
    tests = sorted(
        (v for k, v in globals().items() if k.startswith("test_")),
        key=lambda fn: fn.__name__,
    )
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 - runner mandiri
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} lolos")
    raise SystemExit(1 if failed else 0)
