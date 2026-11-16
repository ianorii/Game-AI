#!/usr/bin/env python3
"""
tools/check_report.py
Skrip verifikasi mandiri kepatuhan penulisan dokumen laporan:
1. docs/LAPORAN_INDUK.md (Dokumen Sintesis Utama Seluruh Modul AI)
2. docs/LAPORAN_AUTOMATED_PLANNING.md (Laporan Detail Automated Planning)
3. docs/DECISION_UNCERTAINTY.md (Laporan Detail Keputusan di Bawah Ketidakpastian)

Memvalidasi:
(a) Keberadaan seluruh file gambar yang dirujuk (docs/screenshots/ dan docs/figures/).
(b) Bebas dari path absolut (/home/..., /mnt/...) dan skema URL lokal (file://).
(c) Bebas dari callout khusus GitHub ([!NOTE], [!WARNING], dll.) dan tag HTML non-standar.
(d) Penomoran formal pada tabel ("Tabel X.") dan gambar ("Gambar Y.").
(e) Konsistensi angka-angka kunci terhadap data mentah di docs/report_data/.
(f) Deteksi penanda [LENGKAPI: ...].
"""

import os
import sys
import re
import json
from typing import Dict, List, Tuple, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
REPORT_DATA_DIR = os.path.join(PROJECT_ROOT, "docs", "report_data")


def verify_document(doc_filename: str, doc_title: str, key_metrics: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    doc_path = os.path.join(DOCS_DIR, doc_filename)
    print("=" * 80)
    print(f"VERIFIKASI DOKUMEN: {doc_filename} ({doc_title})")
    print("=" * 80)

    if not os.path.isfile(doc_path):
        print(f"[FATAL] Berkas dokumen tidak ditemukan di {doc_path}")
        return False, {"errors": [f"File {doc_filename} not found"], "warnings": [], "passed": []}

    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    total_words = len(content.split())
    approx_pages = max(1, round(total_words / 500))

    errors = []
    warnings = []
    passed = []

    # 1. Cek Path Absolut dan file://
    abs_matches = re.findall(r"(?:/home/\S+|/mnt/\S+|file://\S+)", content)
    if abs_matches:
        errors.append(f"Ditemukan {len(abs_matches)} path absolut / file://: {abs_matches[:3]}...")
    else:
        passed.append("Bebas dari path absolut dan tautan file://")

    # 2. Cek Callout Khusus Editor/GitHub ([!NOTE], [!WARNING], dll.)
    callout_matches = re.findall(r">?\s*\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", content)
    if callout_matches:
        errors.append(f"Ditemukan {len(callout_matches)} callout khusus GitHub: {callout_matches[:3]}")
    else:
        passed.append("Bebas dari callout khusus GitHub ([!...])")

    # 3. Cek Tag HTML non-standar (<div>, <span>, <br>, <iframe>, carousel)
    html_matches = re.findall(r"<(?:div|span|br|iframe|carousel)\b[^>]*>", content, re.IGNORECASE)
    if html_matches:
        errors.append(f"Ditemukan {len(html_matches)} tag HTML non-standar: {html_matches[:3]}")
    else:
        passed.append("Bebas dari tag HTML non-standar")

    # 4. Cek Keberadaan Seluruh Gambar yang Dirujuk
    img_refs = re.findall(r"!\[(.*?)\]\((.*?)\)", content)
    missing_imgs = []
    found_imgs = 0
    for caption, rel_path in img_refs:
        clean_path = rel_path.split()[0].strip()
        candidates = [
            os.path.join(DOCS_DIR, clean_path),
            os.path.join(PROJECT_ROOT, clean_path),
            os.path.join(PROJECT_ROOT, "docs", clean_path),
        ]
        exists = any(os.path.isfile(c) for c in candidates)
        if not exists:
            missing_imgs.append((caption, clean_path))
        else:
            found_imgs += 1

    if missing_imgs:
        errors.append(f"Ditemukan {len(missing_imgs)} gambar yang tidak ada di disk: {missing_imgs}")
    else:
        passed.append(f"Semua {found_imgs} berkas gambar yang dirujuk ditemukan di disk")

    # 5. Cek Penomoran Tabel dan Gambar Formal
    table_captions = re.findall(r"(?:Tabel\s+\d+\.|\*\*Tabel\s+\d+\.)", content)
    figure_captions = re.findall(r"(?:Gambar\s+\d+\.|\*\*Gambar\s+\d+\.)", content)

    if table_captions:
        passed.append(f"Ditemukan {len(table_captions)} penomoran tabel formal ('Tabel X.')")
    else:
        warnings.append("Tidak ditemukan penomoran tabel formal ('Tabel X.')")

    if figure_captions:
        passed.append(f"Ditemukan {len(figure_captions)} penomoran gambar formal ('Gambar Y.')")
    elif found_imgs > 0:
        warnings.append("Tidak ditemukan penomoran gambar formal ('Gambar Y.')")

    # 6. Cek Konsistensi Angka Kunci
    for label, val in key_metrics.items():
        val_str = str(val)
        if val_str in content:
            passed.append(f"Metrik kunci '{label}' ({val_str}) ditemukan di dokumen")
        else:
            warnings.append(f"Metrik kunci '{label}' ({val_str}) tidak ditemukan di dokumen")

    # 7. Cek Tag [LENGKAPI: ...]
    incomplete_tags = re.findall(r"\[LENGKAPI:[^\]]+\]", content)
    if incomplete_tags:
        warnings.append(f"Ditemukan {len(incomplete_tags)} penanda [LENGKAPI: ...]: {incomplete_tags}")
    else:
        passed.append("Bebas dari penanda [LENGKAPI: ...]")

    # Cetak Ringkasan
    print(f"\nStatistik Dokumen {doc_filename}:")
    print(f"  - Total Baris    : {len(lines):,} baris")
    print(f"  - Total Kata     : {total_words:,} kata")
    print(f"  - Perkiraan Halaman: ~{approx_pages} halaman PDF (standar A4 500 kata/halaman)")
    print(f"\nItem Lolos Verifikasi ({len(passed)}):")
    for p in passed:
        print(f"  [PASSED] {p}")

    if warnings:
        print(f"\nPeringatan ({len(warnings)}):")
        for w in warnings:
            print(f"  [WARNING] {w}")

    if errors:
        print(f"\nKesalahan Fatal ({len(errors)}):")
        for e in errors:
            print(f"  [ERROR] {e}")
        print(f"\nStatus Dokumen {doc_filename}: GAGAL")
        return False, {"errors": errors, "warnings": warnings, "passed": passed}
    else:
        print(f"\nStatus Dokumen {doc_filename}: SUKSES")
        return True, {"errors": errors, "warnings": warnings, "passed": passed}


def verify_ground_truth_crosscheck() -> bool:
    print("=" * 80)
    print("VERIFIKASI SILANG ANGKA MENTAH JSON TERHADAP DOKUMEN LAPORAN (GROUND TRUTH)")
    print("=" * 80)

    docs = {}
    for fname in ["LAPORAN_INDUK.md", "LAPORAN_AUTOMATED_PLANNING.md", "DECISION_UNCERTAINTY.md"]:
        fpath = os.path.join(DOCS_DIR, fname)
        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                docs[fname] = f.read()
        else:
            print(f"[FATAL] Berkas dokumen {fname} tidak ditemukan!")
            return False

    errors = []
    passed = []

    # 1. unittest.json
    u_path = os.path.join(REPORT_DATA_DIR, "unittest.json")
    if os.path.isfile(u_path):
        with open(u_path, "r", encoding="utf-8") as f:
            u_data = json.load(f)
        tot_tests = str(u_data.get("total_tests", ""))
        u_status = u_data.get("status", "")
        if tot_tests in docs["LAPORAN_INDUK.md"] and u_status == "OK":
            passed.append(f"unittest.json: {tot_tests} tests (Status {u_status}) cocok dengan Dokumen Induk")
        else:
            errors.append(f"unittest.json: inkonsistensi data ({tot_tests} tests, status {u_status})")
    else:
        errors.append("unittest.json tidak ditemukan")

    # 2. benchmark.json
    b_path = os.path.join(REPORT_DATA_DIR, "benchmark.json")
    if os.path.isfile(b_path):
        with open(b_path, "r", encoding="utf-8") as f:
            b_data = json.load(f)
        p4 = next((c for c in b_data.get("benchmark_cells", []) if "Final Game" in c.get("problem", "") and "WA*" in c.get("algorithm", "")), None)
        if p4:
            plan_len = str(p4["plan_length"])
            cost_sec = str(p4["cost_seconds"])
            if (plan_len in docs["LAPORAN_INDUK.md"] and plan_len in docs["LAPORAN_AUTOMATED_PLANNING.md"]
                and cost_sec in docs["LAPORAN_INDUK.md"] and cost_sec in docs["LAPORAN_AUTOMATED_PLANNING.md"]):
                passed.append(f"benchmark.json: P4 WA* ({plan_len} langkah, {cost_sec}s) cocok lintas dokumen")
            else:
                errors.append(f"benchmark.json: P4 ({plan_len} langkah, {cost_sec}s) tidak cocok dengan dokumen laporan")
        else:
            errors.append("benchmark.json: entri P4 WA* tidak ditemukan")
    else:
        errors.append("benchmark.json tidak ditemukan")

    # 3. corridor_segment_analysis.json
    c_path = os.path.join(REPORT_DATA_DIR, "corridor_segment_analysis.json")
    if os.path.isfile(c_path):
        with open(c_path, "r", encoding="utf-8") as f:
            c_data = json.load(f)
        dt_full = f"{c_data['corridor_full']['delta_t_sec']:.2f}"
        dt_sub_val = c_data['subsegment_local']['delta_t_sec']
        raw_sav = f"{c_data['corridor_full']['raw_savings_measured_1_78s']:.4f}"
        sub_ok_induk = "0.36" in docs["LAPORAN_INDUK.md"] or f"{dt_sub_val:.4f}" in docs["LAPORAN_INDUK.md"]
        sub_ok_unc = "0.36" in docs["DECISION_UNCERTAINTY.md"] or f"{dt_sub_val:.4f}" in docs["DECISION_UNCERTAINTY.md"]
        if (dt_full in docs["LAPORAN_INDUK.md"] and dt_full in docs["DECISION_UNCERTAINTY.md"]
            and sub_ok_induk and sub_ok_unc
            and raw_sav in docs["LAPORAN_INDUK.md"] and raw_sav in docs["DECISION_UNCERTAINTY.md"]):
            passed.append(f"corridor_segment_analysis.json: dt_full={dt_full}s, dt_sub=0.36s ({dt_sub_val:.4f}s), raw_savings={raw_sav}s cocok")
        else:
            errors.append("corridor_segment_analysis.json: ketidakcocokan nilai delta_t atau raw_savings")
    else:
        errors.append("corridor_segment_analysis.json tidak ditemukan")

    # 4. flood_penalty_measurement.json
    fl_path = os.path.join(REPORT_DATA_DIR, "flood_penalty_measurement.json")
    if os.path.isfile(fl_path):
        with open(fl_path, "r", encoding="utf-8") as f:
            fl_data = json.load(f)
        mean_d = f"{fl_data['measured_delay_sec']['mean']:.4f}"
        ci_low = f"{fl_data['measured_delay_sec']['ci95_low']:.4f}"
        ci_high = f"{fl_data['measured_delay_sec']['ci95_high']:.4f}"
        rewalk = f"{fl_data['components']['mean_rewalk_diff_sec']:.4f}"
        cal_d = f"{fl_data['comparison_to_calibrated_model_b']['calibrated_delay_sec']:.2f}"
        cal_f = f"{fl_data['comparison_to_calibrated_model_b']['calibrated_f_star']:.4f}"
        if (mean_d in docs["LAPORAN_INDUK.md"] and mean_d in docs["DECISION_UNCERTAINTY.md"]
            and ci_low in docs["LAPORAN_INDUK.md"] and ci_low in docs["DECISION_UNCERTAINTY.md"]
            and ci_high in docs["LAPORAN_INDUK.md"] and ci_high in docs["DECISION_UNCERTAINTY.md"]
            and rewalk in docs["LAPORAN_INDUK.md"] and rewalk in docs["DECISION_UNCERTAINTY.md"]
            and cal_d in docs["LAPORAN_INDUK.md"] and cal_d in docs["DECISION_UNCERTAINTY.md"]
            and cal_f in docs["LAPORAN_INDUK.md"] and cal_f in docs["DECISION_UNCERTAINTY.md"]):
            passed.append(f"flood_penalty_measurement.json: delay {mean_d}s [{ci_low}, {ci_high}], rewalk {rewalk}s, cal {cal_d}s cocok")
        else:
            errors.append("flood_penalty_measurement.json: metrik penalti empiris tidak cocok dengan dokumen laporan")
    else:
        errors.append("flood_penalty_measurement.json tidak ditemukan")

    # 5. information_cost_analysis.json
    ic_path = os.path.join(REPORT_DATA_DIR, "information_cost_analysis.json")
    if os.path.isfile(ic_path):
        with open(ic_path, "r", encoding="utf-8") as f:
            ic_data = json.load(f)
        vpi = f"{ic_data['abstract_vpi_utility_points']:.2f}"
        k_be = f"{ic_data['corridor_full_model']['measured_1_78s']['spawns']['Rumah']['k_breakeven']:.1f}"
        interact = f"{ic_data['interaction_delay_sec']:.2f}"
        if (vpi in docs["LAPORAN_INDUK.md"] and vpi in docs["DECISION_UNCERTAINTY.md"]
            and k_be in docs["LAPORAN_INDUK.md"] and k_be in docs["DECISION_UNCERTAINTY.md"]
            and interact in docs["LAPORAN_INDUK.md"] and interact in docs["DECISION_UNCERTAINTY.md"]):
            passed.append(f"information_cost_analysis.json: VPI={vpi}, K_breakeven={k_be}, interact={interact}s cocok")
        else:
            errors.append("information_cost_analysis.json: nilai VPI atau K_breakeven tidak cocok")
    else:
        errors.append("information_cost_analysis.json tidak ditemukan")

    # 6. footprint_audit.json
    fp_path = os.path.join(REPORT_DATA_DIR, "footprint_audit.json")
    if os.path.isfile(fp_path):
        with open(fp_path, "r", encoding="utf-8") as f:
            fp_data = json.load(f)
        fp_rects = str(fp_data["total_footprint_rects"])
        if fp_rects in docs["LAPORAN_INDUK.md"] and "4.21%" in docs["LAPORAN_INDUK.md"] and "4.21%" in docs["DECISION_UNCERTAINTY.md"]:
            passed.append(f"footprint_audit.json: {fp_rects} rects dan 4.21% luas terbuang terbobot cocok")
        else:
            errors.append("footprint_audit.json: total rect atau 4.21% luas terbuang tidak cocok")
    else:
        errors.append("footprint_audit.json tidak ditemukan")

    # 7. checksums.sha256
    sha_path = os.path.join(REPORT_DATA_DIR, "checksums.sha256")
    if os.path.isfile(sha_path):
        with open(sha_path, "r", encoding="utf-8") as f:
            sha_lines = [l for l in f if l.strip()]
        sha_count = str(len(sha_lines))
        if f"{sha_count} berkas" in docs["LAPORAN_INDUK.md"]:
            passed.append(f"checksums.sha256: {sha_count} berkas hash cocok dengan klaim di Dokumen Induk")
        else:
            errors.append(f"checksums.sha256: total berkas {sha_count} tidak cocok dengan klaim di Dokumen Induk")
    else:
        errors.append("checksums.sha256 tidak ditemukan")

    print(f"\nHasil Audit Silang JSON Ground-Truth ({len(passed)} sukses):")
    for p in passed:
        print(f"  [PASSED] {p}")

    if errors:
        print(f"\nKesalahan Audit Silang ({len(errors)} error):")
        for e in errors:
            print(f"  [ERROR] {e}")
        return False
    return True


def main():
    print("=" * 80)
    print("CHECK REPORT: VALIDASI KOMPREHENSIF DOKUMEN LAPORAN GAME AI")
    print("=" * 80)

    # 1. Dokumen Induk (docs/LAPORAN_INDUK.md)
    induk_metrics = {
        "Total Unit Test": "217",
        "Rencana Final P4 Langkah": "37",
        "Biaya Final P4 Detik": "118.48",
        "Entitas Resmi": "15 entitas",
        "Ambang Kritis Teoretis": "0.1333",
        "Selisih Koridor Penuh Detik": "0.87",
        "Selisih Sub-segmen Detik": "0.36",
    }
    ok_induk, _ = verify_document("LAPORAN_INDUK.md", "Dokumen Induk Sintesis Seluruh Modul AI", induk_metrics)

    print("\n")
    # 2. Laporan Khusus Automated Planning (docs/LAPORAN_AUTOMATED_PLANNING.md)
    planning_metrics = {
        "Rencana Final P4 Langkah": "37 langkah",
        "Biaya Final P4 Detik": "118.48",
    }
    ok_planning, _ = verify_document("LAPORAN_AUTOMATED_PLANNING.md", "Laporan Khusus Automated Planning", planning_metrics)

    print("\n")
    # 3. Laporan Khusus Keputusan di Bawah Ketidakpastian (docs/DECISION_UNCERTAINTY.md)
    uncertainty_metrics = {
        "Ambang Kritis f*": "0.1333",
        "VPI Abstrak": "1.98",
        "Prior Banjir": "0.10",
        "Posterior Berita": "0.50",
        "Luas Terbuang Terbobot": "4.21%",
    }
    ok_unc, _ = verify_document("DECISION_UNCERTAINTY.md", "Laporan Khusus Decisions Under Uncertainty", uncertainty_metrics)

    print("\n")
    # 4. Verifikasi Silang Angka Mentah JSON (Cross-Validation Ground Truth)
    ok_cross = verify_ground_truth_crosscheck()

    print("\n" + "=" * 80)
    all_ok = ok_induk and ok_planning and ok_unc and ok_cross
    if all_ok:
        print("HASIL AKHIR: SELURUH 3 DOKUMEN LAPORAN & AUDIT SILANG JSON LOLOS VERIFIKASI DENGAN SUKSES!")
    else:
        print("HASIL AKHIR: ADA DOKUMEN / DATA SILANG DENGAN KESALAHAN FATAL (Periksa log di atas).")
    print("=" * 80)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
