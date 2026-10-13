"""experiments/mae_report.py - Selisih prediksi vs aktual battle_result.csv.

Jalan: `python3 experiments/mae_report.py [path]` (default data/).
Lapor MAE(|pred_light - aktual|), MAE(|pred_full - aktual|), dan per-baris.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])


def main(path: str):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("kosong")
        return
    for key in ("pred_light", "pred_full"):
        errs = [abs(float(r[key]) - float(r["actual_progress"])) for r in rows
                if r.get(key) not in ("", None)]
        print(f"MAE {key}: {sum(errs) / len(errs):.3f} (n={len(errs)})")
    print(f"baris: {len(rows)}, menang: "
          f"{sum(1 for r in rows if r['hasil'] == 'menang')}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(ROOT) / "data"
                                                   / "battle_result.csv"))
