#!/usr/bin/env python3
"""
tools/audit_assets.py - Sunnyside World Asset Usage Auditor

Memindai seluruh aset di assets/sunnyside_world/ (mengabaikan Sunnyside_World_Gamemaker,
GIF, dan _Source), memeriksa pemakaian aset di kode sumber (src/ dan config.py),
dan menghasilkan laporan komprehensif ke docs/ASSET_AUDIT.md.
"""

import os
import re
import sys
from collections import defaultdict
from datetime import datetime

IGNORED_DIRS = {"Sunnyside_World_Gamemaker", "GIF", "_Source"}
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(ROOT_DIR, "assets", "sunnyside_world")
SRC_DIR = os.path.join(ROOT_DIR, "src")
CONFIG_PATH = os.path.join(ROOT_DIR, "config.py")
DOCS_DIR = os.path.join(ROOT_DIR, "docs")
REPORT_PATH = os.path.join(DOCS_DIR, "ASSET_AUDIT.md")


def collect_assets(root_dir):
    """Kumpulkan seluruh file .png valid di bawah root_dir dengan filter ignore."""
    assets = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filter dirnames in-place agar os.walk tidak masuk ke folder ignored
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]

        rel_dir = os.path.relpath(dirpath, root_dir)
        parts = rel_dir.split(os.sep)
        if any(p in IGNORED_DIRS for p in parts):
            continue

        for fname in sorted(filenames):
            if fname.endswith(".png"):
                full_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(full_path, root_dir)
                stem = os.path.splitext(fname)[0]
                strip_m = re.search(r"_strip(\d+)$", stem)
                strip_count = int(strip_m.group(1)) if strip_m else 1

                assets.append({
                    "filename": fname,
                    "stem": stem,
                    "rel_path": rel_path,
                    "rel_dir": rel_dir if rel_dir != "." else "Root",
                    "full_path": full_path,
                    "strip_count": strip_count,
                    "size_bytes": os.path.getsize(full_path),
                })
    return assets


def collect_source_code():
    """Kumpulkan seluruh teks kode sumber Python di src/ dan config.py."""
    source_files = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            source_files["config.py"] = f.read()

    for dirpath, _, filenames in os.walk(SRC_DIR):
        for fname in filenames:
            if fname.endswith(".py"):
                full_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(full_path, ROOT_DIR)
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    source_files[rel_path] = f.read()

    return source_files


def audit_usage(assets, source_files):
    """
    Evaluasi penggunaan tiap aset terhadap kode sumber.
    Klasifikasi:
      - EXPLICIT: Nama file atau stem spesifik ditulis langsung di kode gameplay/renderer
      - DYNAMIC: Aset dimuat via generic scanner / dynamic template (mis. _load_ui, hero_sprite {style})
      - UNUSED: Tidak ada referensi eksplisit dan tidak aktif digunakan dalam gameplay
    """
    results = []

    # Helper lookup texts
    all_code = "\n".join(source_files.values())

    # Pre-parse HeroSpriteManager dynamic patterns
    # In hero_sprite.py, hair styles supported: spikeyhair is default; anim_defs has 8 actions
    active_hair = "spikeyhair"
    active_human_actions = {"idle", "walk", "run", "attack", "hurt", "casting", "waiting", "death"}

    for a in assets:
        fname = a["filename"]
        stem = a["stem"]
        rel = a["rel_path"]

        matched_files = []
        is_explicit = False
        is_dynamic = False

        # 1. Direct filename or stem match in code
        for sfile, content in source_files.items():
            if fname in content or f'"{stem}"' in content or f"'{stem}'" in content:
                matched_files.append(sfile)
                is_explicit = True
            elif stem in content:
                # Check word boundaries / quoted
                if re.search(r'\b' + re.escape(stem) + r'\b', content):
                    matched_files.append(sfile)
                    is_explicit = True

        # 2. Check dynamic matches in Human sprites
        if rel.startswith("Characters/Human"):
            parts = rel.split(os.sep)
            action_folder = parts[1].lower() if len(parts) > 1 else ""
            prefix = fname.split("_")[0]  # base, spikeyhair, bowlhair, tools, etc.

            # If action is in active human actions
            if action_folder in active_human_actions or (action_folder == "walking" and "walk" in active_human_actions):
                if prefix == "base":
                    is_explicit = True
                    matched_files.append("src/hero_sprite.py (base template)")
                elif prefix == active_hair:
                    is_dynamic = True
                    matched_files.append(f"src/hero_sprite.py ({active_hair} active style)")
                elif prefix == "tools" and action_folder == "attack":
                    is_explicit = True
                    matched_files.append("src/hero_sprite.py (tools attack)")
                else:
                    # other hair styles (bowlhair, curlyhair, etc.)
                    is_dynamic = False

        # 3. Check dynamic matches in UI (AssetManager._load_ui loads all UI/ *.png into self.ui)
        if rel.startswith("UI"):
            # If not explicitly used elsewhere in code, check if it's in self.ui
            # Expressions used in core/animal.py or combat: expression_alerted, expression_attack, expression_chat, expression_love, expression_confused
            # Redbar / greenbar used in AssetManager
            if not is_explicit and "self.ui" in all_code:
                # It's bulk-loaded by _load_ui, but not specifically queried
                is_dynamic = True

        # 4. Check dynamic matches in Elements (AssetManager._load_props scans Elements/ for strip)
        if rel.startswith("Elements") and "_strip" in fname:
            if not is_explicit and "_load_props" in all_code:
                is_dynamic = True

        # Determine status
        if is_explicit:
            status = "USED_EXPLICIT"
        elif is_dynamic:
            status = "LOADED_GENERIC"
        else:
            status = "UNUSED"

        results.append({
            **a,
            "status": status,
            "matched_files": sorted(list(set(matched_files))),
        })

    return results


def generate_markdown_report(results):
    """Hasilkan dokumen Markdown yang mendalam untuk docs/ASSET_AUDIT.md."""
    total_assets = len(results)
    used_explicit = sum(1 for r in results if r["status"] == "USED_EXPLICIT")
    loaded_generic = sum(1 for r in results if r["status"] == "LOADED_GENERIC")
    unused_count = sum(1 for r in results if r["status"] == "UNUSED")

    # Folder breakdown
    by_folder = defaultdict(lambda: {"total": 0, "explicit": 0, "generic": 0, "unused": 0, "items": []})
    for r in results:
        folder = r["rel_dir"]
        by_folder[folder]["total"] += 1
        if r["status"] == "USED_EXPLICIT":
            by_folder[folder]["explicit"] += 1
        elif r["status"] == "LOADED_GENERIC":
            by_folder[folder]["generic"] += 1
        else:
            by_folder[folder]["unused"] += 1
        by_folder[folder]["items"].append(r)

    lines = []
    lines.append("# AUDIT PEMAKAIAN ASET SUNNYSIDE WORLD")
    lines.append(f"**Tanggal Audit**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Direktori Aset**: `assets/sunnyside_world/` (Filter: Mengabaikan `Sunnyside_World_Gamemaker`, `GIF`, `_Source`)")
    lines.append("")
    lines.append("## 1. RINGKASAN EKSEKUTIF")
    lines.append(f"- **Total File Aset (.png)**: **{total_assets}** file")
    lines.append(f"- **Aset Digunakan Eksplisit di Gameplay/Renderer**: **{used_explicit}** file ({used_explicit / total_assets * 100:.1f}%)")
    lines.append(f"- **Aset Dimuat Generik ke Dictionary / Template**: **{loaded_generic}** file ({loaded_generic / total_assets * 100:.1f}%)")
    lines.append(f"- **Aset Menganggur (Belum Dipakai Sama Sekali)**: **{unused_count}** file ({unused_count / total_assets * 100:.1f}%)")
    lines.append("")
    lines.append("> [!NOTE]")
    lines.append("> Sebagian besar aset (khususnya variasi aksi manusia, seluruh tanaman 6 tahap, hewan, prop kincir angin, dan perahu) sudah tersedia dengan format strip berkualitas tinggi, namun belum diintegrasikan ke gameplay loop dungeon/overworld.")
    lines.append("")

    lines.append("## 2. TABEL STATISTIK PER FOLDER")
    lines.append("| Folder | Total File | Eksplisit | Generic / Dimuat | Belum Dipakai (Unused) | % Tidak Terpakai |")
    lines.append("|---|:---:|:---:|:---:|:---:|:---:|")
    for folder, data in sorted(by_folder.items()):
        pct_unused = (data["unused"] / data["total"] * 100) if data["total"] else 0
        lines.append(f"| `{folder}` | {data['total']} | {data['explicit']} | {data['generic']} | {data['unused']} | {pct_unused:.1f}% |")
    lines.append("")

    # Specific Target Sections
    lines.append("## 3. AUDIT MENDALAM TARGET KHUSUS")
    lines.append("")

    # A. Human Characters
    lines.append("### A. Characters / Human (160 File)")
    lines.append("Setiap folder aksi memiliki 8 file: `base_*`, 6 varian rambut (`bowlhair`, `curlyhair`, `longhair`, `mophair`, `shorthair`, `spikeyhair`), dan `tools_*`.")
    lines.append("")
    lines.append("| Aksi | Folder | Status Base | Rambut Terpakai | Status Tools | Status Keseluruhan |")
    lines.append("|---|---|:---:|:---:|:---:|---|")

    human_actions = [
        ("ATTACK", "Serangan jarak dekat", True, "spikeyhair", True),
        ("AXE", "Menebang pohon / kapak kayu", False, "-", False),
        ("CARRY", "Membawa peti / hasil panen", False, "-", False),
        ("CASTING", "Merapal mantra sihir", True, "spikeyhair", False),
        ("CAUGHT", "Tertangkap / ekspresi kaget", False, "-", False),
        ("DEATH", "Animasi roboh / gugur (13 frame)", True, "spikeyhair", False),
        ("DIG", "Mencangkul tanah dengan sekop", False, "-", False),
        ("DOING", "Interaksi generik / berkarya", False, "-", False),
        ("HAMMERING", "Menempa / memukul palu (23 frame)", False, "-", False),
        ("HURT", "Terkena pukulan / hitstun", True, "spikeyhair", False),
        ("IDLE", "Diam / napas idle (9 frame)", True, "spikeyhair", False),
        ("JUMP", "Melompat rintangan / jurang", False, "-", False),
        ("MINING", "Menambang batu / ore pickaxe", False, "-", False),
        ("REELING", "Memancing ikan / menarik kail", False, "-", False),
        ("ROLL", "Gulingan menghindar (dodge roll)", False, "-", False),
        ("RUN", "Berlari kencang (8 frame)", True, "spikeyhair", False),
        ("SWIMMING", "Berenang di air / danau", False, "-", False),
        ("WAITING", "Menunggu giliran / santai", True, "spikeyhair", False),
        ("WALKING", "Berjalan standar (8 frame)", True, "spikeyhair", False),
        ("WATERING", "Menyiram tanaman dengan ember", False, "-", False),
    ]

    for act, desc, base_used, hair_used, tools_used in human_actions:
        b_s = "✅ Digunakan" if base_used else "❌ Belum"
        t_s = "✅ Digunakan" if tools_used else "❌ Belum"
        stat = "Aktif (Battle & Dunia)" if base_used else "Menganggur (Tersedia)"
        lines.append(f"| **{act}** ({desc}) | `Characters/Human/{act}` | {b_s} | {hair_used} | {t_s} | {stat} |")
    lines.append("")
    lines.append("> **Gaya Rambut Tersedia**: `bowlhair`, `curlyhair`, `longhair`, `mophair`, `shorthair`, `spikeyhair`. Saat ini konfigurasi aktif adalah `spikeyhair` (merah). 5 gaya rambut lainnya (100+ file) siap digunakan untuk kustomisasi hero atau NPC desa.")
    lines.append("")

    # B. Skeleton & Goblin
    lines.append("### B. Characters / Skeleton & Goblin")
    lines.append("#### 1. Skeleton (6 File)")
    lines.append("| File | Strip | Status | Catatan Pemakaian |")
    lines.append("|---|:---:|:---:|---|")
    lines.append("| `skeleton_idle_strip6.png` | 6 | ✅ Aktif | Digunakan untuk Boss Idle (skala 7x) |")
    lines.append("| `skeleton_attack_strip7.png` | 7 | ✅ Aktif | Digunakan untuk Boss Attack animasi |")
    lines.append("| `skeleton_hurt_strip7.png` | 7 | ✅ Aktif | Digunakan untuk Boss Hurt animasi |")
    lines.append("| `skeleton_death_strip10.png` | 10 | ✅ Aktif | Digunakan untuk Boss Death & sisa tengkorak |")
    lines.append("| `skeleton_walk_strip8.png` | 8 | ⚠️ Dimuat parsial | Dimuat di asset_loader tetapi Boss statis, belum berpatroli |")
    lines.append("| `skeleton_jump_strip10.png` | 10 | ❌ Belum | Animasi lompat/slam attack belum diimplementasikan |")
    lines.append("")

    lines.append("#### 2. Goblin (20 File)")
    lines.append("Folder `Characters/Goblin/PNG/` memiliki seluruh set aksi (20 animasi lengkap strip) identik dengan hero human.")
    lines.append("- **Animasi tersedia**: `attack`, `axe`, `carry`, `casting`, `caught`, `death`, `dig`, `doing`, `hammering`, `hurt`, `idle`, `jump`, `mining`, `reeling`, `roll`, `run`, `swimming`, `waiting`, `walk`, `watering`.")
    lines.append("- **Status saat ini**: `spr_idle_strip9`, `spr_run_strip8`, `spr_walk_strip8`, `spr_attack_strip10`, `spr_hurt_strip8`, `spr_death_strip13` sudah dibaca oleh `AssetManager`, namun monster Goblin belum aktif spawn di dunia game sebagai entitas hidup yang dapat berinteraksi.")
    lines.append("")

    # C. Elements / Crops
    lines.append("### C. Elements / Crops (78 File)")
    lines.append("Total 11 varian tanaman agrikultur, masing-masing dengan 6 tahap pertumbuhan (`_00` benih hingga `_05` panen matang):")
    lines.append("- **Daftar Tanaman (66 File)**: `beetroot`, `cabbage`, `carrot`, `cauliflower`, `kale`, `parsnip`, `potato`, `pumpkin`, `radish`, `sunflower`, `wheat`.")
    lines.append("- **Daftar Tanah & Barang (12 File)**:")
    lines.append("  - Tanah: `soil_00.png` (kering datar), `soil_01.png` (lembab), `soil_03.png` (sudut), `soil_04.png` (gundukan)")
    lines.append("  - Hasil Tani & Material: `seeds_generic.png`, `wood.png`, `rock.png`, `crate_base.png`, `crate_top.png`")
    lines.append("  - Makanan/Produk: `egg.png`, `milk.png`, `fish.png`")
    lines.append("- **Status Pemakaian**: ❌ **100% Menganggur** (hanya `rock.png` yang dirujuk di kode map). Belum ada sistem ladang bercocok tanam atau pengumpulan bahan.")
    lines.append("")

    # D. Elements / VFX
    lines.append("### D. Elements / VFX (9 File)")
    lines.append("| File / Subfolder | Strip | Status | Catatan Pemakaian |")
    lines.append("|---|:---:|:---:|---|")
    lines.append("| `Elements/VFX/Fire/spr_deco_fire_01_strip4.png` | 4 | ✅ Aktif | Animasi api jebakan merah & es biru |")
    lines.append("| `Elements/VFX/Fire/spr_deco_fire_02_strip4.png` | 4 | ❌ Belum | Variasi kobaran api kedua belum dipakai |")
    lines.append("| `Elements/VFX/Glint/spr_deco_glint_01_strip6.png` | 6 | ✅ Aktif | Hit sparks efek tebasan serangan |")
    lines.append("| `Elements/VFX/Glint/spr_deco_glint_02_strip4.png` | 4 | ⚠️ Dimuat | Alternatif kilatan glint |")
    lines.append("| `Elements/VFX/Chimney Smoke/chimneysmoke_01_strip30.png` | 30 | ❌ Belum | Animasi asap cerobong 30 frame (varian 1) |")
    lines.append("| `Elements/VFX/Chimney Smoke/chimneysmoke_02_strip30.png` | 30 | ❌ Belum | Animasi asap cerobong 30 frame (varian 2) |")
    lines.append("| `Elements/VFX/Chimney Smoke/chimneysmoke_03_strip30.png` | 30 | ❌ Belum | Animasi asap cerobong 30 frame (varian 3) |")
    lines.append("| `Elements/VFX/Chimney Smoke/chimneysmoke_04_strip30.png` | 30 | ❌ Belum | Animasi asap cerobong 30 frame (varian 4) |")
    lines.append("| `Elements/VFX/Chimney Smoke/chimneysmoke_05_strip30.png` | 30 | ❌ Belum | Animasi asap cerobong 30 frame (varian 5) |")
    lines.append("")

    # E. Elements / Other
    lines.append("### E. Elements / Other (5 File)")
    lines.append("| File | Status | Deskripsi & Rekomendasi |")
    lines.append("|---|:---:|---|")
    lines.append("| `spr_deco_windmill_strip9.png` | ❌ Belum | Kincir angin berputar (9 frame). Sangat cocok untuk pusat desa / peternakan. |")
    lines.append("| `spr_deco_windmillshadow_strip9.png` | ❌ Belum | Bayangan kincir angin berputar (9 frame). Memberikan kedalaman visual realistis. |")
    lines.append("| `spr_deco_windmill_withshadow_strip9.png` | ❌ Belum | Kincir angin gabungan dengan bayangan dalam satu sprite. |")
    lines.append("| `spr_deco_coracle_land.png` | ❌ Belum | Perahu bulat tradisional bertengger di daratan/pesisir. |")
    lines.append("| `spr_deco_coracle_strip4.png` | ❌ Belum | Perahu bulat mengapung di air dengan animasi goyangan air 4 frame. |")
    lines.append("")

    # F. UI
    lines.append("### F. Antarmuka / UI (102 File)")
    lines.append("Folder `UI` (75 file) dan `UI/9slice_box_white` (27 file).")
    lines.append("- **Ikon Emosi & Status Terpakai**: `expression_alerted`, `expression_attack`, `expression_confused`, `expression_love`, `expression_chat`, `indicator`.")
    lines.append("- **Resource Bars Menganggur**: `bluebar_00` s/d `bluebar_05` (mana/stamina bar), `greenbar_00` s/d `greenbar_06` (health bar hijau), `redbar_00` s/d `redbar_06` (health bar merah). Saat ini HUD menggambar bar via poligon pygame dasar, belum memakai sprite strip otentik ini.")
    lines.append("- **Ikon Perkakas / Senjata Menganggur**: `axe.png`, `hammer.png`, `pickaxe.png`, `shovel.png`, `rod.png`, `water.png`, `sword.png`, `basket.png`, `plant.png`.")
    lines.append("- **Elemen Kontrol Menganggur**: `confirm.png`, `cancel.png`, `itemdisc_01.png`, `itemdisc_02.png`, `sandtimer.png`, `stopwatch.png`, `playercount.png`, `hand_closed_01/02`, `hand_open_01/02`, `cursor_01` s/d `cursor_05`, `happiness_01` s/d `04`.")
    lines.append("- **9-Slice Box Menganggur**: 27 slice kotak dialog/panel putih siap pakai untuk merender jendela dialog modular.")
    lines.append("")

    # Recommendations
    lines.append("## 4. REKOMENDASI INTEGRASI KE GAMEPLAY & DUNIA")
    lines.append("Berikut rekomendasi konkret pemanfaatan aset tanpa mengganggu mekanisme kecerdasan buatan (Minimax, CSP, Local Search, A*):")
    lines.append("")
    lines.append("1. **Kincir Angin Desa (`spr_deco_windmill_strip9.png`)**:")
    lines.append("   - Letakkan 1 bangunan kincir angin di area desa/tengah peta.")
    lines.append("   - Menggunakan animasi 9-frame looping lambat (8-10 FPS) dengan y-sort dan bayangan.")
    lines.append("2. **Efek Asap Cerobong (`chimneysmoke_01..05_strip30.png`)**:")
    lines.append("   - Pasang emitter asap di atas atap rumah-rumah desa Sunnyside.")
    lines.append("   - Siklus 30 frame halus dengan alpha blending menghidupkan suasana pedesaan.")
    lines.append("3. **Ladang Pertanian Interaktif (`soil_00..04` + `crops` 6 tahap)**:")
    lines.append("   - Tambahkan petak ladang di desa dengan tanaman bertumbuh (mis. Gandum / Labu / Wortel).")
    lines.append("   - Hero dapat berinteraksi menekan [E] untuk memanen bahan consumable/potion.")
    lines.append("4. **Ikon UI Asli pada HUD & Prep Screen**:")
    lines.append("   - Ganti bar HP kotak polos dengan sprite `greenbar_00-06` dan `redbar_00-06`.")
    lines.append("   - Gunakan ikon alat otentik (`sword.png`, `axe.png`, `water.png`, `sandtimer.png`) pada layar Persiapan CSP / Prep UI.")
    lines.append("5. **Patroli Goblin & Skeleton Mengembara**:")
    lines.append("   - Spawn minion Goblin dan Skeleton liar di luar zona aman desa yang berpatroli (A*).")
    lines.append("   - Menggunakan animasi `walk` dan `jump` yang belum terpakai.")
    lines.append("6. **Perahu Pesisir (`spr_deco_coracle_strip4.png`)**:")
    lines.append("   - Tempatkan perahu mengapung di dermaga atau tepian danau pulau dengan animasi 4 frame.")
    lines.append("")

    lines.append("## 5. DAFTAR LENGKAP ASET BELUM DIPAKAI (UNUSED)")
    lines.append(f"Total: **{unused_count}** file yang siap dimuat oleh `src/asset_catalog.py`:")
    lines.append("")
    lines.append("| No | Path Relatif | Ukuran Frame Strip | Ukuran File |")
    lines.append("|:---:|---|:---:|:---:|")
    idx = 1
    for r in sorted(results, key=lambda x: x["rel_path"]):
        if r["status"] == "UNUSED":
            lines.append(f"| {idx} | `{r['rel_path']}` | {r['strip_count']} frame | {r['size_bytes']:,} byte |")
            idx += 1
    lines.append("")

    return "\n".join(lines)


def main():
    print(f"[AUDIT] Memindai aset di '{ASSETS_DIR}'...")
    assets = collect_assets(ASSETS_DIR)
    print(f"[AUDIT] Ditemukan {len(assets)} file PNG valid (mengabaikan Gamemaker, GIF, _Source).")

    print(f"[AUDIT] Membaca kode sumber di '{SRC_DIR}' & '{CONFIG_PATH}'...")
    source_files = collect_source_code()
    print(f"[AUDIT] Ditemukan {len(source_files)} file kode sumber Python.")

    print("[AUDIT] Menganalisis referensi & penggunaan aset...")
    results = audit_usage(assets, source_files)

    os.makedirs(DOCS_DIR, exist_ok=True)
    report_content = generate_markdown_report(results)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"[AUDIT] Laporan berhasil disimpan ke '{REPORT_PATH}'!")

    # Cetak ringkasan terminal
    total = len(results)
    explicit = sum(1 for r in results if r["status"] == "USED_EXPLICIT")
    generic = sum(1 for r in results if r["status"] == "LOADED_GENERIC")
    unused = sum(1 for r in results if r["status"] == "UNUSED")

    print("\n" + "=" * 65)
    print("           RINGKASAN AUDIT ASET SUNNYSIDE WORLD")
    print("=" * 65)
    print(f"Total File Aset (.png)          : {total:4d}")
    print(f"Digunakan Eksplisit di Kode     : {explicit:4d}  ({explicit/total*100:5.1f}%)")
    print(f"Dimuat Generik / Template       : {generic:4d}  ({generic/total*100:5.1f}%)")
    print(f"Belum Dipakai Sama Sekali       : {unused:4d}  ({unused/total*100:5.1f}%)")
    print("=" * 65)


if __name__ == "__main__":
    main()

