"""game/ambush/csv_export.py - Tulis CSV dari trace buffer yang sama.

Dipanggil sekali setiap pencarian selesai (director / skrip eksperimen).
Kolom sesuai spek Tahap 3.
"""
from __future__ import annotations

import csv
from typing import Dict, List

from game.ambush.trace import TraceBuffer

CSP_FIELDS = ["step", "variabel", "value", "domain_size", "pruned",
              "backtrack", "nodes"]
LS_FIELDS = ["run_id", "algo", "iter", "current", "best", "target", "T",
             "deltaE", "accepted", "rejected_by_constraint"]
SUMMARY_FIELDS = ["run_id", "algo", "heuristik", "nodes_iter", "waktu_ms",
                  "skor_akhir", "jarak_ke_target", "alasan_berhenti"]
BATTLE_FIELDS = ["run_id", "k", "order", "target", "pred_light", "pred_full",
                 "actual_progress", "duel_menang", "hp_sisa_per_duel",
                 "potion_sisa", "hasil", "duel_gagal_ke"]


def write_csp_csv(tracer: TraceBuffer, path: str) -> int:
    """csp_trace.csv dari event assign/select/backtrack/revise/fc_prune."""
    rows = []
    for e in tracer.events:
        kind = e["kind"]
        if kind == "assign":
            rows.append([e["step"], e.get("var"), e.get("val"),
                         e.get("domain_size"), e.get("pruned"), 0,
                         e.get("nodes")])
        elif kind == "select":
            rows.append([e["step"], e.get("var"), "", e.get("domain_size"),
                         e.get("pruned"), 0, e.get("nodes")])
        elif kind in ("backtrack", "restore"):
            rows.append([e["step"], "", "", "", e.get("pruned"), 1,
                         e.get("nodes")])
        elif kind in ("revise", "fc_prune"):
            rows.append([e["step"], e.get("xi", e.get("var")), "",
                         e.get("left"), e.get("pruned"), 0, e.get("nodes")])
    _write(path, CSP_FIELDS, rows)
    return len(rows)


def write_ls_csv(tracer: TraceBuffer, path: str, run_id: int = 0,
                 algo: str = "") -> int:
    """ls_trace.csv dari event ls_iter/ls_sa/ga_gen/ls_restart."""
    rows = []
    target = _first(tracer, "ls_start", "target", "")
    for e in tracer.events:
        kind = e["kind"]
        if kind == "ls_iter":
            rows.append([run_id, algo or _algo_of(tracer), e.get("it"),
                         _r(e.get("current")), _r(e.get("best")), target,
                         "", "", "", e.get("rejected")])
        elif kind == "ls_sa":
            rows.append([run_id, "simulated_annealing", e.get("it"),
                         _r(e.get("current")), "", target,
                         _r(e.get("temp")), _r(e.get("delta_e")),
                         int(bool(e.get("accepted"))), ""])
        elif kind == "ga_gen":
            rows.append([run_id, "genetic", e.get("gen"), "",
                         _r(e.get("best_gap")), target, "", "", "", ""])
    _write(path, LS_FIELDS, rows)
    return len(rows)


def write_summary_csv(rows: List[Dict], path: str) -> int:
    """summary.csv: satu baris per run (diisi director/eksperimen)."""
    _write(path, SUMMARY_FIELDS,
           [[r.get(k, "") for k in SUMMARY_FIELDS] for r in rows])
    return len(rows)


def _r(value) -> object:
    return round(value, 4) if isinstance(value, float) else value


def _first(tracer: TraceBuffer, kind: str, field: str, default: object):
    event = tracer.latest(kind)
    return event.get(field, default) if event else default


def _algo_of(tracer: TraceBuffer) -> str:
    event = tracer.latest("ls_start")
    return event.get("algo", "") if event else ""


def _write(path: str, fields: List[str], rows: List[list]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(rows)


def append_battle_result(row: dict, path: str) -> None:
    """Tambah satu baris battle_result.csv (buat + header bila belum ada)."""
    import os
    exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BATTLE_FIELDS,
                                extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)
