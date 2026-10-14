"""tests/test_ambush_director.py - Unit test director/governor/CSV/overlay.

Jalan tanpa dependensi baru: `python3 tests/test_ambush_director.py`.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.csv_export import (  # noqa: E402
    write_csp_csv,
    write_ls_csv,
    write_summary_csv,
)
from game.ambush.director import AmbushDirector  # noqa: E402
from game.ambush.governor import DifficultyGovernor  # noqa: E402
from game.ambush.overlay_ambush import build_view  # noqa: E402
from game.ambush.trace import TraceBuffer  # noqa: E402

CFG = AmbushConfig()


def test_governor_up_down_clamp():
    gov = DifficultyGovernor(CFG)
    assert gov.target == CFG.gov_init
    up = gov.update("player", 0.8)   # menang telak: naik agresif
    assert up > CFG.gov_init
    down = gov.update("npc", 0.2)    # kalah: turun
    assert down < up
    for _ in range(30):
        gov.update("player", 1.0)
    assert gov.target <= CFG.governor_max_target  # plafon opsi C
    for _ in range(60):
        gov.update("npc", 1.0)
    assert gov.target >= CFG.gov_min  # dijepit bawah
    assert len(gov.history) > 0


def test_governor_never_exceeds_ceiling_40_wins():
    """Opsi C: menang-terus 40x menempel di plafon 0.80, tak lebih."""
    gov = DifficultyGovernor(CFG)
    peak = gov.target
    for _ in range(40):
        peak = max(peak, gov.update("player", 0.5, progress=1.0,
                                    failed_at=None))
    assert peak <= CFG.governor_max_target
    assert gov.target == CFG.governor_max_target  # plateau, bukan hanyut


def test_above_ceiling_honest_label_and_hardest_queue():
    """Target 0.95 -> di-cap 0.80 + label jujur + antrean tetap tersulit."""
    from game.ambush.enemy_queue import is_queue_valid
    from game.ambush.governor import ceiling_label
    director = AmbushDirector(CFG, DifficultyGovernor(CFG), base_seed=11)
    res = director.plan_queue(0, 0.95)
    assert res.capped is True
    assert res.requested_target == 0.95 and res.target == 0.80
    assert is_queue_valid(res.queue, 0, CFG.budget_q_for(0.80), CFG)
    assert res.queue.k() >= 2
    assert ceiling_label(res.queue.order_str()) == (
        "target di atas plafon, antrean tersulit: "
        f"{res.queue.order_str()}")
    # Tanpa cap (0.80) tidak berlabel.
    res2 = AmbushDirector(CFG, DifficultyGovernor(CFG),
                          base_seed=11).plan_queue(0, 0.80)
    assert res2.capped is False


def test_target_050_vs_080_differ():
    """0.50 vs 0.80 menghasilkan antrean berbeda (kriteria iii)."""
    gov = DifficultyGovernor(CFG)
    a = AmbushDirector(CFG, gov, base_seed=21).plan_queue(0, 0.50)
    b = AmbushDirector(CFG, gov, base_seed=21).plan_queue(0, 0.80)
    assert (a.queue.key() != b.queue.key()
            or abs(a.light - b.light) > 1e-9), (a.queue.order_str(),
                                                b.queue.order_str(),
                                                a.light, b.light)


def test_director_plan_verified():
    tr = TraceBuffer()
    director = AmbushDirector(CFG, DifficultyGovernor(CFG), tracer=tr,
                              base_seed=42)
    result = director.plan(wins=0, target=0.5)
    assert result.verified is True
    assert result.gap <= 0.05
    assert result.squad.size() >= 1
    # Event penutup terpancar (regresi bug csp_done yang hilang).
    done = tr.latest("csp_done")
    assert done is not None and done["time_ms"] > 0


def test_director_run_gen_matches_plan():
    tr = TraceBuffer()
    director = AmbushDirector(CFG, DifficultyGovernor(CFG), tracer=tr,
                              base_seed=42)
    phases = [e["phase"] for e in director.run_gen(0, 0.5)]
    assert "csp" in phases and "ls_done" in phases
    assert phases[-1] == "done"
    assert director.last_result is not None
    assert director.last_result.verified is True


def test_csv_writers_headers():
    tr = TraceBuffer()
    director = AmbushDirector(CFG, DifficultyGovernor(CFG), tracer=tr,
                              ls_algo="hill_climbing", base_seed=9)
    director.plan(wins=0, target=0.5)
    with tempfile.TemporaryDirectory() as tmp:
        csp_p, ls_p, sum_p = (os.path.join(tmp, n) for n in
                              ("c.csv", "l.csv", "s.csv"))
        assert write_csp_csv(tr, csp_p) > 0
        # LS bisa 0 baris bila start langsung dalam toleransi (hanya header).
        assert write_ls_csv(tr, ls_p, run_id=1, algo="hill_climbing") >= 0
        assert write_summary_csv([{
            "run_id": 1, "algo": "hill_climbing", "heuristik": "x",
            "nodes_iter": 5, "waktu_ms": 1.0, "skor_akhir": 0.5,
            "jarak_ke_target": 0.0, "alasan_berhenti": "target"}], sum_p) \
            == 1
        for path, head in ((csp_p, "step"), (ls_p, "run_id"),
                           (sum_p, "run_id")):
            with open(path, encoding="utf-8") as f:
                assert csv.reader(f).__next__()[0] == head


def test_build_view_keys():
    tr = TraceBuffer()
    director = AmbushDirector(CFG, DifficultyGovernor(CFG), tracer=tr,
                              base_seed=4)
    result = director.plan(wins=0, target=0.5)
    view = build_view(tr, {"phase": "Selesai", "status": "selesai",
                           "ls_algo": "random_restart", "target": 0.5,
                           "pump": "instant", "toggles": {},
                           "sideways_limit": 10, "ls_stop": result.ls_stop,
                           "seed_gap": result.seed_gap,
                           "squad": result.squad, "sim": "0.8"})
    for key in ("phase", "nodes", "backtracks", "pruned", "var", "reason",
                "domains", "candidates", "queue", "arc", "ls_it", "cur",
                "best", "rejected", "history", "squad"):
        assert key in view, key
    assert len(view["history"]) >= 0


def test_overlay_ceiling_label_draws():
    """Label plafon tampil di overlay + HUD review tanpa crash (opsi C)."""
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    from game.ambush.governor import ceiling_label
    from game.ambush.overlay_ambush import AmbushDebugOverlay, build_view
    from game.ambush.trace import TraceBuffer
    tr = TraceBuffer()
    label = ceiling_label("Archer>Mage>Boss")
    assert label == ("target di atas plafon, antrean tersulit: "
                     "Archer>Mage>Boss")
    view = build_view(tr, {"phase": "Selesai", "status": "selesai",
                           "ls_algo": "hill_climbing", "target": 0.80,
                           "target_label": "0.95", "ceiling": label})
    assert view["ceiling"] == label
    screen = pygame.display.set_mode((1280, 720))
    font = pygame.font.SysFont("consolas", 14)
    ov = AmbushDebugOverlay()
    ov.view = view
    ov.draw(screen, font)  # tak crash


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
