#!/usr/bin/env python3
"""
================================================================================
 setup_structure.py - AUTOGENERATE STRUKTUR PROYEK "AI LABYRINTH"
================================================================================
 Script ini memastikan seluruh struktur folder & aset game tersedia:

    DungeonGame/
    ├── assets/
    │   ├── tilesets/
    │   │   ├── sunnyside_world.png            (atlas utama, 64x64 sel)
    │   │   ├── sunnyside_forest.png           (atlas kanopi hutan)
    │   │   └── CREDITS_sunnyside_world.txt
    │   ├── sprites/hero/                      (idle / run / attack / hurt / cast)
    │   ├── sprites/monsters/                  (goblin, skeleton, boss)
    │   ├── props/                             (pohon, jamur, hewan, batu, tanaman)
    │   └── vfx/                               (api, kilau, ikon hati)
    ├── src/
    │   ├── main.py, config.py, asset_loader.py, __init__.py
    │   ├── core/   (worldgen, world_art, map, entity, battle_ui, debug_overlay)
    │   └── ai/     (pathfinding, csp, local_search, adversarial, planning)
    ├── tools/
    │   └── import_sunnyside.py                (impor ulang aset: --pack /path/ke/paket)
    └── requirements.txt

 Jalankan:  python setup_structure.py
 Aman dijalankan berkali-kali (idempotent).
================================================================================
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ------------------------------------------------------------------------------
# 1. Daftar folder yang harus ada
# ------------------------------------------------------------------------------
FOLDERS = [
    "assets/tilesets",
    "assets/sprites/hero",
    "assets/sprites/monsters",
    "assets/props",
    "assets/vfx",
    "src",
    "src/core",
    "src/ai",
    "tools",
]

# ------------------------------------------------------------------------------
# 2. Aset wajib (dicek, bukan disalin - aset dibuat oleh tools/import_sunnyside.py)
# ------------------------------------------------------------------------------
TILESET = ROOT / "assets" / "tilesets" / "sunnyside_world.png"
FOREST_TILESET = ROOT / "assets" / "tilesets" / "sunnyside_forest.png"
CREDITS = ROOT / "assets" / "tilesets" / "CREDITS_sunnyside_world.txt"
HERO_DIR = ROOT / "assets" / "sprites" / "hero"
IMPORTER = ROOT / "tools" / "import_sunnyside.py"

# File yang WAJIB ada agar struktur sesuai spesifikasi (dibuat kosong jika belum)
REQUIRED_FILES = [
    "requirements.txt",
    "src/__init__.py",
    "src/config.py",
    "src/asset_loader.py",
    "src/main.py",
    "src/core/__init__.py",
    "src/core/map.py",
    "src/core/worldgen.py",
    "src/core/world_art.py",
    "src/core/entity.py",
    "src/core/battle_ui.py",
    "src/core/debug_overlay.py",
    "src/ai/__init__.py",
    "src/ai/pathfinding.py",
    "src/ai/csp.py",
    "src/ai/local_search.py",
    "src/ai/adversarial.py",
    "src/ai/planning.py",
    "tools/import_sunnyside.py",
]


def main() -> int:
    print("=" * 70)
    print(" AUTOGENERATE STRUKTUR: AI LABYRINTH - THE DUNGEON OVERSEER")
    print("=" * 70)
    print(f" Root proyek: {ROOT}\n")

    # --- 1. Buat folder -------------------------------------------------------
    for rel in FOLDERS:
        path = ROOT / rel
        path.mkdir(parents=True, exist_ok=True)
        print(f" [folder] {rel}")

    # --- 2. Atlas Sunnyside World --------------------------------------------
    if TILESET.exists():
        print(f" [tileset] OK  {TILESET.relative_to(ROOT)}")
    else:
        print("\n [!] Atlas Sunnyside tidak ditemukan:")
        print(f"     {TILESET}")
        print("     Jalankan: python tools/import_sunnyside.py --pack /path/ke/paket")
        print("     (paket sumber Sunnyside World V2.1 tidak disimpan di proyek)")
        print("     Game tetap berjalan dengan placeholder.\n")
    if FOREST_TILESET.exists():
        print(f" [tileset] OK  {FOREST_TILESET.relative_to(ROOT)}")
    if CREDITS.exists():
        print(f" [lisensi] OK  {CREDITS.relative_to(ROOT)}")

    # --- 3. Sprite hero / monster / prop / vfx --------------------------------
    hero_frames = sorted(HERO_DIR.glob("hero_idle_f*.png")) if HERO_DIR.exists() else []
    if hero_frames:
        total = sum(1 for _ in (ROOT / "assets").rglob("*.png"))
        print(f" [sprite ] OK  {len(hero_frames)} frame idle + total {total} PNG aset")
    elif IMPORTER.exists():
        print(" [sprite ] Aset belum ada - mengimpor dari paket sumber (--pack) ...")
        try:
            res = subprocess.run([sys.executable, str(IMPORTER)],
                                 cwd=str(ROOT), capture_output=True, text=True)
            if res.returncode == 0:
                print(" [sprite ] OK  aset Sunnyside diimpor")
            else:
                print(" [sprite ] GAGAL:", res.stderr.strip()[:200])
        except Exception as exc:                      # pragma: no cover
            print(" [sprite ] GAGAL:", exc)
    else:
        print(" [sprite ] tools/import_sunnyside.py tidak ditemukan")

    # --- 4. Pastikan file source ada (jangan timpa yang sudah diisi) -----------
    created = 0
    for rel in REQUIRED_FILES:
        path = ROOT / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
            created += 1
    print(f" [src   ] {created} file source dibuat (kosong) / sudah ada dilewati")

    # --- 5. Ringkasan ---------------------------------------------------------
    print("\n" + "-" * 70)
    print(" STRUKTUR FINAL:")
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames.sort()
        if any(d.startswith(".") for d in dirnames):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel = os.path.relpath(dirpath, ROOT)
        depth = rel.count(os.sep)
        if depth > 2:
            dirnames[:] = []
            continue
        print(f" {'' if rel == '.' else rel}/")
        for f in sorted(filenames):
            if f.startswith("."):
                continue
            print(f"    - {f}")
    print("-" * 70)
    print(" Selesai! Jalankan game dengan:  python src/main.py\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
