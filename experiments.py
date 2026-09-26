"""
experiments.py - Harness eksperimen untuk laporan Adversarial Search.

Modul ini membandingkan varian algoritma pencarian adversarial di atas model
yang sama persis (state, urutan aksi, fungsi evaluasi), lalu mencetak hasil
dalam bentuk tabel markdown yang siap ditempel ke laporan.

Eksperimen yang tersedia
------------------------
E1. Minimax vs Alpha-Beta vs Early Stop     (node count & waktu per kedalaman)
E2. Perbandingan fungsi evaluasi             (hp_diff / balanced / threat_aware)
E3. Perbandingan urutan aksi                 (default / aggressive / defensive / random)
E4. Perbandingan kedalaman pencarian          (kualitas aksi vs biaya)
E5. Perilaku NPC untuk berbagai evaluasi     (distribusi aksi + win rate duel)
E6. Expectimax                                (node cost & kapan keputusannya beda)
E7. Branching 3 vs 4                          (versi literal tugas vs tambahan SPECIAL)

Cara pakai
----------
    python experiments.py                # semua eksperimen, ringkas
    python experiments.py --all           # sama, tapi verbose
    python experiments.py --only E1 E5    # pilih eksperimen tertentu
    python experiments.py --quick         # jumlah state lebih sedikit
    python experiments.py --out hasil.md  # simpan tabel ke file markdown
    python experiments.py --log-csv duel.csv  # log ai_stats tiap giliran duel
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import statistics
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from adversarial_ai import (
    ACTIONS,
    ATTACK_MAX,
    ATTACK_MIN,
    EVAL_FUNCTIONS,
    EVAL_PROFILES,
    MOVE_ORDERS,
    WIN_SCORE,
    AdversarialAI,
    BattleState,
    escapes_death,
    incoming_damage,
    is_decided,
)


# ---------------------------------------------------------------------------
# Utilitas
# ---------------------------------------------------------------------------

def make_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """Renders tabel markdown dari header dan baris data.

    Args:
        headers: Label kolom
        rows: Baris data (boleh berisi float yang akan diformat)

    Returns:
        String markdown berisi tabel
    """
    def fmt(v: object) -> str:
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    out = ["| " + " | ".join(str(h) for h in headers) + " |"]
    out.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        out.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(out)


def benchmark_states(count: int, seed: int = 2024) -> List[BattleState]:
    """Buat set state duel yang deterministik untuk dipakai semua eksperimen.

    State selalu merupakan giliran NPC (``turn = 1``) karena itu titik masuk
    pencarian yang dilakukan AI. Nilai HP dan sumber daya diacak supaya
    statistiknya tidakbias oleh satu kondisi khusus.

    Distribusi HP sengaja condong ke nilai yang lebih rendah dibanding HP penuh:
    dalam duel nyata HP terbawa antar-memen (``main.py`` menyimpan
    ``player_hp``), sehingga kondisi "hampir kalah" lazim terjadi dan justru
    kondisi itu yang paling sulit bagi pruning.

    Args:
        count: Jumlah state yang dibuat
        seed: Seed RNG agar hasil reproducible

    Returns:
        List BattleState siap pakai
    """
    rng = random.Random(seed)
    states: List[BattleState] = []
    for _ in range(count):
        states.append(
            BattleState(
                player_hp=rng.randint(5, 100),
                npc_hp=rng.randint(5, 100),
                player_potions=rng.randint(0, 3),
                npc_potions=rng.randint(0, 3),
                player_special_cd=rng.choice([0, 0, 1, 2]),
                npc_special_cd=rng.choice([0, 0, 1, 2]),
                player_defending=rng.random() < 0.15,
                npc_defending=rng.random() < 0.15,
                turn=1,
            )
        )
    return states


def run_benchmark(
    states: Sequence[BattleState],
    algorithm: str,
    depth: int,
    eval_name: str = "balanced",
    order_name: str = "default",
    early_stop: bool = False,
) -> Dict[str, float]:
    """Jalankan satu konfigurasi pada seluruh benchmark states.

    Args:
        states: List state dari `benchmark_states`
        algorithm: "minimax" | "alphabeta" | "expectimax" | "iterative"
        depth: Kedalaman pencarian
        eval_name: Nama fungsi evaluasi
        order_name: Nama urutan aksi
        early_stop: Aktifkan pemangkasan berbasis kondisi pasti

    Returns:
        Dict berisi rata-rata node, waktu, jumlah cutoff, dan duration akhir
    """
    ai = AdversarialAI(
        depth=depth,
        algorithm=algorithm,
        eval_name=eval_name,
        order_name=order_name,
        early_stop=early_stop,
    )
    nodes = 0
    ms = 0.0
    evals = 0
    cutoffs = 0
    stops = 0
    depths_done = []
    actions: Dict[str, int] = {}
    t_wall = time.perf_counter()

    for state in states:
        stats = ai.think(state, depth=depth, run_baseline=False)
        nodes += stats["algorithm_nodes"]
        ms += stats["time_ms"]
        evals += stats["evaluations"]
        cutoffs += stats.get("cutoffs", 0)
        stops += stats.get("early_stop_hits", 0)
        if stats.get("completed_depth"):
            depths_done.append(stats["completed_depth"])
        if stats["best_action"]:
            actions[stats["best_action"]] = actions.get(stats["best_action"], 0) + 1

    n = max(1, len(states))
    return {
        "nodes": nodes / n,
        "time_ms": ms / n,
        "wall_s": time.perf_counter() - t_wall,
        "evaluations": evals / n,
        "cutoffs": cutoffs / n,
        "early_stop_hits": stops / n,
        "avg_depth": statistics.fmean(depths_done) if depths_done else float(depth),
        "actions": actions,
    }


# ---------------------------------------------------------------------------
# E1. Minimax vs Alpha-Beta vs Early Stop
# ---------------------------------------------------------------------------

def exp1_algorithms(depths: Sequence[int], n_states: int) -> str:
    """Bandingkan tiga algoritma pada state yang sama, variedasi kedalaman.

    Args:
        depths: Daftar kedalaman yang diuji
        n_states: Jumlah state benchmark

    Returns:
        Tabel markdown
    """
    states = benchmark_states(n_states)
    rows = []
    for d in depths:
        mm = run_benchmark(states, "minimax", d)
        ab = run_benchmark(states, "alphabeta", d)
        es = run_benchmark(states, "alphabeta", d, early_stop=True)
        saving = (1 - ab["nodes"] / mm["nodes"]) * 100 if mm["nodes"] else 0.0
        es_saving = (1 - es["nodes"] / mm["nodes"]) * 100 if mm["nodes"] else 0.0
        rows.append(
            [
                d,
                round(mm["nodes"], 1),
                round(ab["nodes"], 1),
                f"{saving:.1f}%",
                round(es["nodes"], 1),
                f"{es_saving:.1f}%",
                round(es["early_stop_hits"], 1),
                round(mm["time_ms"], 3),
                round(ab["time_ms"], 3),
            ]
        )
    return make_table(
        [
            "depth", "minimax node", "alpha-beta node", "hemat",
            "early-stop node", "hemat", "early-stop hit",
            "minimax ms", "alpha-beta ms",
        ],
        rows,
    )


# ---------------------------------------------------------------------------
# E2. Perbandingan fungsi evaluasi
# ---------------------------------------------------------------------------

def exp2_evaluations(depth: int, n_states: int) -> str:
    """Bandingkan fungsi evaluasi: biaya node, distribusi aksi, dan konsistensi.

    Catatan penting: struktur pohon ditentukan oleh ``depth`` dan ``legal_actions``,
    jadi     secara teori jumlah node seharusnya identik.
    differences that *do* appear come from alpha-beta: kondisi cutoff
    ``beta <= alpha`` membandingkan skor asli, sehingga *skala* fungsi evaluasi
    memengaruhi seberapa cepat jendela menyempit. Fungsi dengan skor
    lebih tajam (mis. ``threat_aware`` yang menambah bonus ancaman) menutup
    jendela lebih cepat dan karena itu sedikit lebih hemat.

    Args:
        depth: Kedalaman pencarian tetap
        n_states: Jumlah state benchmark

    Returns:
        Tabel markdown
    """
    states = benchmark_states(n_states)
    names = list(EVAL_FUNCTIONS)
    baseline = "balanced" if "balanced" in names else names[0]

    picks: Dict[str, List[Optional[str]]] = {}
    rows = []
    for name in names:
        res = run_benchmark(states, "alphabeta", depth, eval_name=name)
        picks[name] = [
            AdversarialAI(depth=depth, algorithm="alphabeta", eval_name=name)
            .think(s, depth=depth, run_baseline=False)["best_action"]
            for s in states
        ]
        rows.append(
            [
                name,
                round(res["nodes"], 1),
                round(res["evaluations"], 1),
                round(res["time_ms"], 3),
                res["actions"].get("ATTACK", 0) * 100 / len(states),
                res["actions"].get("DEFEND", 0) * 100 / len(states),
                res["actions"].get("POTION", 0) * 100 / len(states),
                res["actions"].get("SPECIAL", 0) * 100 / len(states),
            ]
        )

    table = make_table(
        [
            "evaluasi", "node", "eval", "ms",
            "% ATTACK", "% DEFEND", "% POTION", "% SPECIAL",
        ],
        rows,
    )

    # Matriks kesamaan keputusan antar pasangan fungsi evaluasi
    agree_rows = []
    for a in names:
        cells: List[object] = [a]
        for b in names:
            same = sum(1 for x, y in zip(picks[a], picks[b]) if x == y)
            cells.append(f"{same * 100 / len(states):.0f}%")
        agree_rows.append(cells)
    agree_table = make_table(
        ["evaluasi \\ lainnya"] + list(names), agree_rows
    )
    return (
        table
        + "\n\n**Matriks kesamaan keputusan antar fungsi evaluasi "
        + f"(baseline produksi = `{baseline}`):**\n\n"
        + agree_table
    )


# ---------------------------------------------------------------------------
# E3. Perbandingan urutan aksi
# ---------------------------------------------------------------------------

def exp3_orderings(depth: int, n_states: int) -> str:
    """Bandingkan urutan aksi pada alpha-beta.

    Alpha-beta bersifat *order-independent* pada level **nilai**: untuk state
    yang sama, pemetaan ``{aksi: skor}`` dari semua aksi root harus identik
    apa pun urutan eksplorasi. Yang bisa berubah hanyalah *tie-break*, yaitu
    aksi mana yang dipilih ketika dua aksi memiliki skor persis sama.

    Eksperimen ini sengaja memisahkan dua hal tersebut:

    - ``% skor identik`` - harus 100% pada semua urutan. Ini bukti kebenaran
      alpha-beta sekaligus berfungsi sebagai uji regresi.
    - ``% aksi sama`` - bisa di bawah 100% karena tie-break mengikuti urutan.
    - ``% beda karena seri`` - bagian dari perbedaan aksi yang skornya sama,
      sehingga secara gameplay keduanya ekuivalen (bukan kesalahan keputusan).
    - ``beda nyata`` - perbedaan aksi dengan skor yang juga berbeda. harus 0.
    """
    states = benchmark_states(n_states)
    order_names = list(MOVE_ORDERS)
    base = order_names[0]
    rows = []
    picks: Dict[str, List[Optional[str]]] = {}
    score_maps: Dict[str, List[Dict[str, float]]] = {}

    base_nodes = None
    for name in order_names:
        res = run_benchmark(states, "alphabeta", depth, order_name=name)
        if base_nodes is None:
            base_nodes = res["nodes"]
        picks[name] = []
        score_maps[name] = []
        for i, s in enumerate(states):
            ai = AdversarialAI(
                depth=depth, algorithm="alphabeta", order_name=name, seed=1000 + i
            )
            stats = ai.think(s, depth=depth, run_baseline=False)
            picks[name].append(stats["best_action"])
            score_maps[name].append(dict(stats["root_scores"]))

        same_scores = sum(
            1 for a, b in zip(score_maps[base], score_maps[name]) if a == b
        )
        same_action = sum(1 for a, b in zip(picks[base], picks[name]) if a == b)
        tie_diff = 0
        real_diff = 0
        for sm_a, sm_b, act_a, act_b in zip(
            score_maps[base], score_maps[name], picks[base], picks[name]
        ):
            if act_a == act_b:
                continue
            if act_a in sm_a and act_a in sm_b and sm_a[act_a] == sm_b[act_a]:
                tie_diff += 1
            else:
                real_diff += 1

        rows.append(
            [
                name,
                round(res["nodes"], 1),
                round(res["cutoffs"], 1),
                round(res["time_ms"], 3),
                f"{(1 - res['nodes'] / base_nodes) * 100:+.1f}%",
                f"{same_scores * 100 / len(states):.1f}%",
                f"{same_action * 100 / len(states):.1f}%",
                f"{tie_diff * 100 / len(states):.1f}%",
                real_diff,
            ]
        )
    return make_table(
        ["urutan", "node", "cutoff", "ms", "hemat node",
         "% skor identik", "% aksi sama", "% beda karena seri", "beda nyata"],
        rows,
    )


# E4. Perbandingan kedalaman
# ---------------------------------------------------------------------------

def exp4_depths(depths: Sequence[int], n_states: int) -> str:
    """Tunjukkan trade-off kedalaman: biaya node vs perubahan keputusan.

    Args:
        depths: Daftar kedalaman yang diuji
        n_states: Jumlah state benchmark

    Returns:
        Tabel markdown
    """
    states = benchmark_states(n_states)
    picks: Dict[int, List[Optional[str]]] = {}
    rows = []
    for d in depths:
        res = run_benchmark(states, "alphabeta", d)
        picks[d] = [
            AdversarialAI(depth=d, algorithm="alphabeta")
            .think(s, depth=d, run_baseline=False)["best_action"]
            for s in states
        ]
        rows.append([d, round(res["nodes"], 1), round(res["time_ms"], 3), "-"])
    # kesamaan terhadap kedalaman terdalam
    deepest = max(depths)
    fixed = []
    for i, d in enumerate(depths):
        same = sum(1 for a, b in zip(picks[deepest], picks[d]) if a == b)
        rows[i][3] = f"{same * 100 / len(states):.1f}%"
    return make_table(
        ["depth", "node (alpha-beta)", "ms", f"sama dgn depth {deepest}"], rows
    )


# ---------------------------------------------------------------------------
# E5. Perilaku NPC untuk berbagai pendekatan
# ---------------------------------------------------------------------------

def simulate_duel(
    npc_ai: AdversarialAI,
    player_policy: str,
    seed: int,
    max_plies: int = 80,
    state_cls=BattleState,
) -> Dict[str, object]:
    """Mainkan satu duel penuh dengan damage acak dan catat hasil.

    Damage ATTACK diundi 15..20 persis seperti ``battle_system._resolve``,
    sehingga hasil eksperimen mencerminkan duel yang benar-benar dimainkan.

    Args:
        npc_ai: Objek AI yang mengendalikan NPC
        player_policy: "random" | "greedy" | "ai"
        seed: Seed RNG duel
        max_plies: Batas plies untuk mencegah duel mandek
        state_cls: Kelas state yang dipakai, untuk varian aturan duel

    Returns:
        Dict berisi winner, jumlah plies, dan distribusi aksi NPC
    """
    rng = random.Random(seed)
    state = state_cls(turn=0)
    npc_actions: Dict[str, int] = {}
    npc_plies: List[int] = []
    plies = 0

    player_ai = None
    if player_policy == "ai":
        player_ai = AdversarialAI(depth=3, algorithm="alphabeta", eval_name="balanced")

    for _ in range(max_plies):
        if state.is_terminal():
            break
        is_npc = state.turn == 1
        plies += 1

        if is_npc:
            action = npc_ai.think(state, run_baseline=False)["best_action"]
            if action is None:
                break
            npc_actions[action] = npc_actions.get(action, 0) + 1
            npc_plies.append(plies)
        else:
            if player_policy == "random":
                action = rng.choice(state.legal_actions(False))
            elif player_policy == "greedy":
                legal = state.legal_actions(False)
                action = "SPECIAL" if "SPECIAL" in legal else (
                    "ATTACK" if "ATTACK" in legal else legal[0]
                )
            else:
                # PENTING: root_is_npc=False. Tanpa ini, agent Player akan
                # memakai root MAX dengan evaluasi berorientasi NPC, artinya
                # ia justru memilih apa yang paling menguntungkan bagi NPC dan
                # duel ini tidak mengukur apa pun.
                action = player_ai.think(
                    state, run_baseline=False, root_is_npc=False
                )["best_action"]
            if action is None:
                break

        # Resolusi dengan damage acak (sama dengan battle_system)
        if action == "ATTACK":
            state = state.apply_action(
                is_npc, action, attack_damage=rng.randint(ATTACK_MIN, ATTACK_MAX)
            )
        else:
            state = state.apply_action(is_npc, action)

    if state.npc_hp <= 0 and state.player_hp <= 0:
        winner = "draw"
    elif state.npc_hp <= 0:
        winner = "player"
    elif state.player_hp <= 0:
        winner = "npc"
    else:
        winner = "timeout"

    return {
        "winner": winner,
        "npc_actions": npc_actions,
        "npc_plies": npc_plies,
        "plies": plies,
        "state": state,
    }


def exp5_behaviour(depth: int, n_duels: int, profiles: Sequence[str]) -> str:
    """Ukur perilaku NPC untuk beberapa profil evaluasi.

    Tiga opponent tetap dipakai agar perbedaan hasil murni dari profil NPC:
    ``greedy`` (serang terus tanpa bernalar), ``ai`` (alpha-beta berkedalaman
    3 yang dijalankan dari sisi Player lewat ``root_is_npc=False``), dan
    ``random`` (acak). ``greedy`` dan ``random`` berguna sebagai kontrol:
    keduanya tidak pernah menyesuaikan strategi, sehingga kemenangan AI hanya
    mencerminkan seberapa baik profilnya membaca tekanan.

    Penting: duel bisa berakhir sebagai *stalemate* (batas ``max_plies``
    tercapai tanpa ada yang mati). Penyebabnya ekonomi potion: kalau satu sisi
    masih punya potion sementara lawan turtling tanpa minum, tidak ada yang
    bisa menghabisi. Karena itu reported "menang %" dihitung terhadap duel yang
    *selesai* (decided), bukan terhadap seluruh duel, dan stalemate dilaporkan
    terpisah. Menggabungkan keduanya akan menyesatkan:Profil yang kalah cepat
    dan profil yang mandek terlihat sama saja di kolom "menang".

    Args:
        depth: Kedalaman pencarian NPC
        n_duels: Jumlah duel per kombinasi
        profiles: Nama profil evaluasi yang diuji

    Returns:
        Tabel markdown
    """
    rows = []
    for opponent in ("greedy", "random", "ai"):
        for profile in profiles:
            wins = draws = losses = timeouts = 0
            agg: Dict[str, int] = {}
            for i in range(n_duels):
                ai = AdversarialAI(
                    depth=depth, algorithm="alphabeta", eval_name=profile
                )
                res = simulate_duel(ai, opponent, seed=9000 + i)
                w = res["winner"]
                if w == "npc":
                    wins += 1
                elif w == "player":
                    losses += 1
                elif w == "draw":
                    draws += 1
                else:
                    timeouts += 1
                for k, v in res["npc_actions"].items():
                    agg[k] = agg.get(k, 0) + v
            total_acts = sum(agg.values()) or 1
            decided = wins + losses + draws
            win_decided = wins * 100 / decided if decided else 0.0
            rows.append(
                [
                    opponent,
                    profile,
                    f"{timeouts * 100 / n_duels:.1f}%",
                    f"{win_decided:.1f}%",
                    f"{wins * 100 / n_duels:.1f}%",
                    f"{losses * 100 / n_duels:.1f}%",
                    round(agg.get("ATTACK", 0) * 100 / total_acts, 1),
                    round(agg.get("DEFEND", 0) * 100 / total_acts, 1),
                    round(agg.get("POTION", 0) * 100 / total_acts, 1),
                    round(agg.get("SPECIAL", 0) * 100 / total_acts, 1),
                ]
            )
    return make_table(
        [
            "opponent", "profil NPC", "stalemate", "menang (decided)",
            "menang (semua)", "kalah",
            "%ATK", "%DEF", "%POT", "%SPC",
        ],
        rows,
    )


# ---------------------------------------------------------------------------
# E6. Expectimax
# ---------------------------------------------------------------------------

def exp6_expectimax(depths: Sequence[int], n_states: int) -> str:
    """Bandingkan expectimax terhadap alpha-beta deterministik.

    Karena fungsi evaluasi linear terhadap HP dan distribusi damage seragam,
    expectimax *harusnya* memilih aksi yang sama dengan pencarian deterministik.
    Perbedaan hanya muncul di mana nonlinearity ada: saturasi
    ``min(MAX_HP, hp + POTION_HEAL)`` dan ambang ``escapes_death``.

    Args:
        depths: Daftar kedalaman yang diuji
        n_states: Jumlah state benchmark

    Returns:
        Tabel markdown
    """
    states = benchmark_states(n_states)
    rows = []
    for d in depths:
        ab = run_benchmark(states, "alphabeta", d)
        ex = run_benchmark(states, "expectimax", d)
        ab_pick = [
            AdversarialAI(depth=d, algorithm="alphabeta")
            .think(s, depth=d, run_baseline=False)["best_action"]
            for s in states
        ]
        ex_pick = [
            AdversarialAI(depth=d, algorithm="expectimax")
            .think(s, depth=d, run_baseline=False)["best_action"]
            for s in states
        ]
        same = sum(1 for a, b in zip(ab_pick, ex_pick) if a == b)
        rows.append(
            [
                d,
                round(ab["nodes"], 1),
                round(ex["nodes"], 1),
                round(ex["nodes"] / ab["nodes"], 2) if ab["nodes"] else "-",
                round(ab["time_ms"], 3),
                round(ex["time_ms"], 3),
                f"{same * 100 / len(states):.1f}%",
            ]
        )
    return make_table(
        ["depth", "alpha-beta node", "expectimax node", "rasio node",
         "alpha-beta ms", "expectimax ms", "aksi sama"],
        rows,
    )


def exp7_branching(depth: int, n_states: int, n_duels: int) -> str:
    """Bandingkan branching 3 (literal tugas) vs branching 4 (versi produksi).

    Tugas menyebut ``attack, defend, potion`` dengan batas ``branching <= 4``.
    Implementasi produksi menambahkan SPECIAL sebagai aksi keempat. Eksperimen
    ini mengukur apakah tambahan itu searing biaya node yang dibayar, dan
    apakah keputusan AI benar-benar berbeda.

    Args:
        depth: Kedalaman pencarian yang diuji
        n_states: Jumlah state benchmark
        n_duels: Duel per varian untuk mengukur win rate

    Returns:
        Tabel markdown
    """
    base = benchmark_states(n_states)
    trio = [
        NoSpecialState(
            player_hp=s.player_hp, npc_hp=s.npc_hp,
            player_potions=s.player_potions, npc_potions=s.npc_potions,
            player_special_cd=s.player_special_cd, npc_special_cd=s.npc_special_cd,
            player_defending=s.player_defending, npc_defending=s.npc_defending,
            turn=s.turn,
        )
        for s in base
    ]

    rows = []
    for label, states in (("3 (tanpa SPECIAL)", trio), ("4 (produksi)", base)):
        ab = run_benchmark(states, "alphabeta", depth)
        picks: Dict[str, int] = {}
        ai = AdversarialAI(depth=depth, algorithm="alphabeta")
        for s in states:
            a = ai.think(s, run_baseline=False)["best_action"]
            picks[a] = picks.get(a, 0) + 1
        total = sum(picks.values()) or 1
        dist = " ".join(
            f"{a} {picks.get(a, 0) * 100 / total:.1f}%" for a in ACTIONS
        )

        npc_ai = AdversarialAI(depth=depth, algorithm="alphabeta", eval_name="balanced")
        wins = draws = unfinished = 0
        for i in range(n_duels):
            r = simulate_duel(npc_ai, "ai", 7000 + i, state_cls=type(states[0]))
            if r["winner"] == "npc":
                wins += 1
            elif r["winner"] == "draw":
                draws += 1
            else:
                unfinished += 1
        rows.append([
            label,
            round(ab["nodes"], 1),
            round(ab["time_ms"], 2),
            f"{wins * 100 / n_duels:.1f}%",
            f"{draws * 100 / n_duels:.1f}%",
            f"{unfinished * 100 / n_duels:.1f}%",
            dist,
        ])
    return make_table(
        ["branching", "node", "ms", "NPC menang", "seri", "belum selesai",
         "distribusi aksi root"],
        rows,
    )


# ---------------------------------------------------------------------------
# Varian aturan duel untuk E7
# ---------------------------------------------------------------------------

@dataclass
class NoSpecialState(BattleState):
    """State duel dengan aksi SPECIAL dinonaktifkan.

    Tugas menyebut tiga aksi per giliran (attack, defend, potion) dengan
    batas ``branching <= 4``. Implementasi produksi memakai empat aksi karena
    SPECIAL ditambahkan sebagai fitur. Subkelas ini dipakai E7 untuk
    mengukur biaya dan manfaat aksi tambahan itu, tanpa mengubah
    ``BattleState`` yang dipakai jalur produksi.
    """

    def legal_actions(self, is_npc: bool) -> Tuple[str, ...]:
        """Aksi legal tanpa SPECIAL, jadi maksimal tiga cabang."""
        return tuple(
            a for a in super().legal_actions(is_npc) if a != "SPECIAL"
        )


# ---------------------------------------------------------------------------
# Analisis pendukung (horizon & decided state)
# ---------------------------------------------------------------------------

def analyse_horizon() -> str:
    """Ukur apakah horizon pencarian bisa mencapai state terminal.

    Ini penting untuk laporan: bila horizon tidak pernah sampai ke terminal,
    maka nilai ``WIN_SCORE`` tidak pernah muncul di evaluasi dan algoritma
    sebenarnya berperilaku seperti greedy berhorizon pendek.

    Returns:
        Tabel markdown
    """

    def min_depth_for_terminal(state: BattleState, limit: int = 12) -> Optional[int]:
        """Cari kedalaman TERDALAM di mana terminal bisa dicapai (BFS)."""
        if state.is_terminal():
            return 0
        queue = deque([(state, 1)])
        while queue:
            cur, d = queue.popleft()
            if cur.is_terminal():
                return d
            if d >= limit:
                continue
            is_max = cur.turn == 1
            for a in cur.legal_actions(is_max):
                queue.append((cur.apply_action(is_max, a), d + 1))
        return None

    rows = []
    for hp in (100, 90, 80, 70, 60, 50, 48, 40, 35, 30, 20, 10):
        s = BattleState(player_hp=hp, npc_hp=100, turn=1)
        d = min_depth_for_terminal(s)
        rows.append([hp, d if d is not None else f">{12}"])

    decided_rows = []
    for hp in (100, 60, 40, 30, 25, 20, 15, 10):
        for pots in (0, 3):
            s = BattleState(
                player_hp=hp, npc_hp=100, player_potions=pots, turn=1
            )
            decided_rows.append(
                [
                    hp,
                    pots,
                    incoming_damage(s, True),
                    escapes_death(s, False),
                    is_decided(s),
                ]
            )

    return make_table(
        ["player HP", "kedalaman min. agar terminal terlihat"], rows
    ) + "\n\n**Kondisi `is_decided` (dasar early stop):**\n\n" + make_table(
        ["player HP", "potion", "damage masuk maks",
         "player bisa menghindar", "duel diputuskan"],
        decided_rows,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

EXPERIMENTS: Dict[str, Tuple[str, Callable[[], str]]] = {}


def register(name: str, title: str):
    """Daftarkan satu eksperimen agar bisa dipanggil dari CLI.

    Args:
        name: Kode eksperimen (mis. "E1")
        title: Judul untuk dicetak

    Returns:
        Dekorator yang mendaftarkan fungsi eksperimen
    """

    def deco(fn: Callable[[], str]) -> Callable[[], str]:
        EXPERIMENTS[name] = (title, fn)
        return fn

    return deco


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point CLI.

    Args:
        argv: Argument command line (opsional, untuk testing)

    Returns:
        Exit code
    """
    ap = argparse.ArgumentParser(description="Eksperimen Adversarial Search")
    ap.add_argument("--only", nargs="*", default=None,
                    help="Pilih eksperimen, mis. --only E1 E5")
    ap.add_argument("--quick", action="store_true",
                    help="Lebih sedikit state (untuk iterasi cepat)")
    ap.add_argument("--out", default=None, help="Simpan tabel ke file markdown")
    ap.add_argument("--log-csv", default=None,
                    help="Log statistik AI per giliran duel ke CSV")
    ap.add_argument("--all", action="store_true", help="Jalankan semua (default)")
    args = ap.parse_args(argv)

    n_states = 150 if args.quick else 600
    n_duels = 20 if args.quick else 60
    depths_ab = (1, 2, 3, 4, 5, 6) if args.quick else (1, 2, 3, 4, 5, 6, 7)
    depths_ex = (1, 2, 3) if args.quick else (1, 2, 3, 4)

    register("E1", "Minimax vs Alpha-Beta vs Early Stop")(
        lambda: exp1_algorithms(depths_ab, n_states)
    )
    register("E2", "Perbandingan fungsi evaluasi")(
        lambda: exp2_evaluations(4, n_states)
    )
    register("E3", "Perbandingan urutan aksi")(
        lambda: exp3_orderings(5, n_states)
    )
    register("E4", "Perbandingan kedalaman pencarian")(
        lambda: exp4_depths(depths_ab, n_states)
    )
    register("E5", "Perilaku NPC untuk berbagai pendekatan")(
        lambda: exp5_behaviour(4, n_duels, list(EVAL_PROFILES))
    )
    register("E6", "Expectimax")(
        lambda: exp6_expectimax(depths_ex, n_states)
    )
    register("E7", "Branching 3 vs 4 (aksi khusus)")(
        lambda: exp7_branching(4, n_states, n_duels)
    )
    register("E0", "Analisis horizon & kondisi early stop")(analyse_horizon)

    chosen = args.only or [f"E{i}" for i in range(0, 8)]
    chunks: List[str] = ["# Hasil Eksperimen Adversarial Search", ""]
    chunks.append(
        f"Benchmark: {n_states} state acak (seed tetap), "
        f"{n_duels} duel per kombinasi pada E5 dan E7."
    )
    chunks.append("")

    for key in chosen:
        key = key.upper()
        if key not in EXPERIMENTS:
            print(f"[warn] eksperimen tidak dikenal: {key}", file=sys.stderr)
            continue
        title, fn = EXPERIMENTS[key]
        t0 = time.perf_counter()
        body = fn()
        chunks.append(f"## {key}. {title}")
        chunks.append("")
        chunks.append(body)
        chunks.append("")
        print(f"[{key}] {title}  ({time.perf_counter() - t0:.1f}s)")

    report = "\n".join(chunks)
    if args.out:
        with io.open(args.out, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"\n-> {args.out}")
    else:
        print()
        print(report)

    if args.log_csv:
        log_duel_csv(args.log_csv, n_duels, depth=4)
        print(f"-> {args.log_csv}")

    return 0


def log_duel_csv(path: str, n_duels: int, depth: int = 4) -> None:
    """Log statistik AI per giliran NPC ke CSV.

    CSV ini bisa langsung dipakai sebagai data eksperimen: berasal dari duel
    yang benar-benar dimainkan (damage acak, urutan giliran nyata), bukan
    dari state sintetis.

    Satu baris ditulis untuk setiap giliran NPC, dengan ``ply`` menyatakan
    nomor giliran tersebut. Baris state merekam kondisi_player **sebelum**
    NPC bertindak, jadi ``best_action`` dan skornya bisa dibaca bersama
    keadaan yang mendasarinya. Kolom ``is_last`` menandai giliran terakhir
    duel, karena baris itu tidak sama dengan baris summary satu-duel.

    Args:
        path: Path file CSV output
        n_duels: Jumlah duel yang dilog
        depth: Kedalaman pencarian AI
    """
    fields = [
        "duel", "ply", "algorithm", "eval_name", "order_name", "depth",
        "player_hp", "npc_hp", "player_potions", "npc_potions",
        "player_defending", "npc_defending",
        "best_action", "best_score", "minimax_nodes", "alphabeta_nodes",
        "pruned_nodes", "cutoffs", "prune_efficiency", "evaluations", "time_ms",
        "is_last",
    ]
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for d in range(n_duels):
            ai = AdversarialAI(depth=depth, algorithm="alphabeta")
            history = ai.think_history
            history.clear()
            res = simulate_duel(ai, "ai", seed=4200 + d)
            npc_plies = res["npc_plies"]
            total = len(history)
            for i, entry in enumerate(history):
                st = entry["stats"]
                s = entry["state"]
                writer.writerow(
                    {
                        "duel": d,
                        "ply": npc_plies[i] if i < len(npc_plies) else -1,
                        "algorithm": st.get("algorithm"),
                        "eval_name": st.get("eval_name"),
                        "order_name": st.get("order_name"),
                        "depth": st.get("depth"),
                        "player_hp": s.player_hp,
                        "npc_hp": s.npc_hp,
                        "player_potions": s.player_potions,
                        "npc_potions": s.npc_potions,
                        "player_defending": s.player_defending,
                        "npc_defending": s.npc_defending,
                        "best_action": st.get("best_action"),
                        "best_score": st.get("best_score"),
                        "minimax_nodes": st.get("minimax_nodes"),
                        "alphabeta_nodes": st.get("alphabeta_nodes"),
                        "pruned_nodes": st.get("pruned_nodes"),
                        "cutoffs": st.get("cutoffs"),
                        "prune_efficiency": round(
                            st.get("prune_efficiency", 0.0), 2
                        ),
                        "evaluations": st.get("evaluations"),
                        "time_ms": round(st.get("time_ms", 0.0), 3),
                        "is_last": i == total - 1,
                    }
                )


if __name__ == "__main__":
    raise SystemExit(main())
