"""experiments/run_all.py - Eksperimen final satu perintah (Fase 7).

Seed tetap, hasil ke data/results/ (CSV) + RINGKASAN.md. Memakai ulang
modul eksperimen yang sudah ada (tanpa logika baru):
  a. ablasi CSP (ablate_csp)         c. fidelitas (fidelity.json / --full)
  b. perbandingan LS (compare_ls)    d. autoplay 3 kebijakan + lintasan adaptif

Jalan: `python3 experiments/run_all.py --quick` (beberapa menit) atau
`--full`. Quick harus konsisten kualitatif dengan full (dilaporkan).
"""
from __future__ import annotations

import csv
import datetime
import random
import statistics as S
import sys
import time
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, str(Path(ROOT) / "experiments"))

OUTDIR = Path(ROOT) / "data" / "results"


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def save_csv(name: str, fields, rows):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    with open(OUTDIR / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def part_csp(n_seeds: int):
    """a. Ablasi CSP: varian x target x skenario (nodes/bt/ms)."""
    from ablate_csp import VARIANTS, p90, scenario_prob
    from game.ambush.config import AmbushConfig
    from game.ambush.csp_solver import CSPSolver
    t0 = time.perf_counter()
    cfg = AmbushConfig()
    rows = []
    for target in (0.3, 0.5, 0.8):
        for scenario in ("normal", "hybrid", "wins9"):
            for name, kw, seedmode, perm in VARIANTS:
                from ablate_csp import permuted
                ns, bs, ms = [], [], []
                ok = 0
                for s in range(n_seeds):
                    prob = scenario_prob(target, scenario, s)
                    if perm:
                        prob = permuted(prob, s)
                    seed = s if seedmode else None
                    u0 = time.perf_counter()
                    sol, st = CSPSolver(prob, seed=seed, **kw).solve()
                    ms.append((time.perf_counter() - u0) * 1000.0)
                    ns.append(st["nodes"])
                    bs.append(st["backtracks"])
                    ok += sol is not None
                rows.append({"seeds": n_seeds, "target": target,
                             "skenario": scenario, "varian": name,
                             "nodes_mean": round(S.mean(ns), 1),
                             "nodes_p90": p90(ns),
                             "bt_mean": round(S.mean(bs), 1),
                             "bt_p90": p90(bs),
                             "ms_mean": round(S.mean(ms), 1),
                             "solved": f"{ok}/{n_seeds}"})
    save_csv("csp_ablasi.csv", list(rows[0]), rows)
    return time.perf_counter() - t0, rows


def part_ls(n_seeds: int):
    """b. Perbandingan LS: 5 algoritma x BEST/RANDOM (gap/eval/ms/tol)."""
    import compare_ls
    from game.ambush.config import AmbushConfig
    t0 = time.perf_counter()
    rows = []
    for mode in ("BEST", "RANDOM"):
        for algo in ("hc_plain", "hc", "restart", "sa", "ga"):
            gaps, evals, mss, bads, hits, n = [], [], [], [], 0, 0
            for seed in range(n_seeds):
                for target in compare_ls.TARGETS:
                    for loname, lo in compare_ls.LOADOUTS.items():
                        from game.ambush.chain_eval import ChainLightSim
                        light = ChainLightSim(compare_ls.CFG, lo,
                                              seed=1000 + seed, games=2)
                        seeds = compare_ls.seeds_for(seed)
                        if not seeds:
                            continue
                        if mode == "BEST":
                            from game.ambush.difficulty import difficulty_gap
                            gaps0 = [(difficulty_gap(light.evaluate(s),
                                                     target), s)
                                     for s in seeds]
                            start = min(gaps0, key=lambda t: t[0])[1]
                        else:
                            start = seeds[0]
                        g, e, ms, bad, _ = compare_ls.run_algo(
                            algo, start, seeds, light, target)
                        gaps.append(g)
                        evals.append(e)
                        mss.append(ms)
                        bads.append(bad)
                        hits += g <= compare_ls.CFG.target_tol
                        n += 1
            rows.append({"seeds": n_seeds, "mode": mode, "algo": algo,
                         "gap_mean": round(S.mean(gaps), 4),
                         "gap_p90": round(pct(gaps, 0.9), 4),
                         "eval_mean": round(S.mean(evals), 1),
                         "ms_mean": round(S.mean(mss), 1),
                         "tol_pct": round(hits / n * 100, 1),
                         "sa_bad_mean": round(S.mean(bads), 2)})
    save_csv("ls_banding.csv", list(rows[0]), rows)
    return time.perf_counter() - t0, rows


def part_fidelity(full: bool):
    """c. Angka fidelitas (baca JSON; --full menjalankan ulang ~12 mnt)."""
    import json
    import subprocess
    t0 = time.perf_counter()
    if full:
        subprocess.run([sys.executable, "experiments/fidelity.py"],
                       cwd=ROOT, check=True)
    with open(Path(ROOT) / "data" / "fidelity.json",
              encoding="utf-8") as f:
        report = json.load(f)
    rows = [{"loadout": k, **{kk: vv for kk, vv in v.items()
                              if kk != "bias_per_role"}}
            for k, v in report["by_loadout"].items()]
    save_csv("fidelitas.csv", list(rows[0]), rows)
    return time.perf_counter() - t0, report


def _greedy(ai, state, is_npc):
    """Delegasi ke policies.greedy_action (satu sumber, anti-typo)."""
    from game.ambush.policies import greedy_action as _g
    return _g(ai, state, is_npc)


def play_adaptive(n: int, seed0: int):
    """Lintasan target adaptif: governor dipakai ulang antar pertemuan."""
    from game.ambush.buff_ai import BuffAwareAI, BuffBattleState
    from game.ambush.chain_eval import apply_chip_hook
    from game.ambush.config import AmbushConfig
    from game.ambush.director import AmbushDirector
    from game.ambush.enemy_queue import enemy_max_hp, slot_to_buff
    from game.ambush.flow.queue_driver import QueueRun
    from game.ambush.governor import DifficultyGovernor
    from game.ambush.player_loadout import PlayerLoadout, loadout_to_buff
    from adversarial_ai import ATTACK_MAX, ATTACK_MIN, MAX_HP
    cfg, gov = AmbushConfig(), DifficultyGovernor(AmbushConfig())
    loadout = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    traj = []
    for m in range(n):
        director = AmbushDirector(cfg, gov, base_seed=seed0 + m)
        res = director.plan_queue(0, gov.target, loadout)
        pbuff = loadout_to_buff(loadout, cfg)
        cap = MAX_HP + pbuff.hp
        run = QueueRun(queue=res.queue, buffs=list(res.buffs),
                       target=res.target, pred_light=res.light,
                       pred_full=res.sim_difficulty, hp=cap, potions=3,
                       cap=cap, cfg=cfg)
        rng = random.Random(5000 + seed0 + m)
        for slot, buff in zip(run.queue.slots, run.buffs):
            state = BuffBattleState(player_hp=run.hp,
                                    npc_hp=enemy_max_hp(buff, cfg.enemy_base_hp),
                                    turn=0, buff=buff, player_buff=pbuff)
            state.player_potions = run.potions
            state.npc_potions = cfg.npc_starting_potions
            ai_n = BuffAwareAI(depth=1, buff=buff, player_buff=pbuff)
            ai_p = BuffAwareAI(depth=1, buff=buff, player_buff=pbuff)
            for _ in range(cfg.sim_max_plies):
                if state.is_terminal():
                    break
                is_npc = state.turn == 1
                a = _greedy(ai_n if is_npc else ai_p, state, is_npc)
                if a is None:
                    break
                dmg = rng.randint(ATTACK_MIN, ATTACK_MAX) if a == "ATTACK" \
                    else None
                kw = {"attack_damage": dmg} if dmg is not None else {}
                state = state.apply_action(is_npc, a, **kw)
                apply_chip_hook(state, buff)
            st = run.record(max(0, state.player_hp), state.player_potions,
                            state.npc_hp <= 0)
            if st != "next":
                break
        won = st == "won_all"
        gov.update("player" if won else "npc", run.margin(),
                   progress=run.progress(),
                   failed_at=None if won else run.failed_at + 1)
        traj.append({"pertemuan": m + 1, "target": round(gov.target, 3),
                     "hasil": "menang" if won else "kalah",
                     "progres": round(run.progress(), 3)})
    return traj


def part_autoplay(n: int, seed: int):
    """d. Autoplay 3 kebijakan + lintasan adaptif."""
    import sys as _sys
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "autoplay_run", str(Path(ROOT) / "experiments" / "autoplay.py"))
    ap = importlib.util.module_from_spec(spec)
    _sys.modules["autoplay_run"] = ap
    spec.loader.exec_module(ap)
    t0 = time.perf_counter()
    rows, traj = [], []
    cfgs = [("greedy", n, seed), ("conserve", n, seed + 1000),
            ("depth4", max(3, n // 3), seed + 2000)]
    for policy, nn, sd in cfgs:
        wins, progs, errs_l, errs_f = 0, [], [], []
        for i in range(nn):
            row = ap.play_meeting(i, sd + i, ap.PlayerLoadout(
                items=("Iron Sword", "Heavy Shield")), policy)
            rows.append({"policy": policy, **row})
            wins += row["hasil"] == "menang"
            progs.append(row["actual_progress"])
            errs_l.append(abs(row["pred_light"] - row["actual_progress"]))
            if row["pred_full"] != "":
                errs_f.append(abs(float(row["pred_full"])
                                  - row["actual_progress"]))
        traj.append({"policy": policy, "n": nn,
                     "menang_pct": round(wins / nn * 100, 1),
                     "progres": round(S.mean(progs), 3),
                     "mae_light": round(S.mean(errs_l), 3),
                     "mae_full": round(S.mean(errs_f), 3)
                     if errs_f else "-"})
    save_csv("autoplay.csv",
             ["policy", "run_id", "k", "order", "target", "pred_light",
              "pred_full", "actual_progress", "duel_menang",
              "hp_sisa_per_duel", "potion_sisa", "hasil", "duel_gagal_ke"],
             rows)
    traj += play_adaptive(max(6, n // 2), seed + 3000)
    save_csv("lintasan_adaptif.csv", ["pertemuan", "target", "hasil",
                                      "progres"],
             [r for r in traj if "pertemuan" in r])
    summary = [r for r in traj if "policy" in r]
    return time.perf_counter() - t0, summary


def main(quick: bool, full_fidelity: bool = False):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    n_csp = 10 if quick else 100
    n_ls = 5 if quick else 20
    n_ap = 10 if quick else 30
    times, summary = {}, {}
    tag = "quick" if quick else "full"
    print(f"== run_all --{tag} ==", flush=True)
    times["csp"], _rows = part_csp(n_csp)
    print(f"csp: {times['csp']:.0f}s", flush=True)
    times["ls"], _rows = part_ls(n_ls)
    print(f"ls: {times['ls']:.0f}s", flush=True)
    times["fidelity"], _rep = part_fidelity(full_fidelity)
    print(f"fidelity: {times['fidelity']:.0f}s", flush=True)
    times["autoplay"], summary["autoplay"] = part_autoplay(n_ap, 99)
    print(f"autoplay: {times['autoplay']:.0f}s", flush=True)
    lines = [f"# Ringkasan run_all --{tag}",
             f"{datetime.date.today().isoformat()}",
             "", "## Waktu (detik)"]
    lines += [f"- {k}: {v:.0f}s" for k, v in times.items()]
    lines += ["", "## Autoplay",
              "| policy | menang% | progres | MAE ringan | MAE penuh |",
              "|---|---|---|---|---|"]
    for r in summary["autoplay"]:
        lines.append(f"| {r['policy']} | {r['menang_pct']} | {r['progres']} "
                     f"| {r['mae_light']} | {r['mae_full']} |")
    (OUTDIR / "RINGKASAN.md").write_text("\n".join(lines) + "\n",
                                         encoding="utf-8")
    print("\n".join(lines[3:]), flush=True)


if __name__ == "__main__":
    quick = "--full" not in sys.argv
    main(quick=quick, full_fidelity="--fidelity-full" in sys.argv)
