"""game/ambush/constraints.py - Rumusan CSP: X, D, C + uji konsistensi.

X: ROLE_1..ROLE_k, ITEM_1..ITEM_k (k = cfg.kmax).
D: D(ROLE_1) memuat Boss; D(ROLE_2..k) tanpa Boss (domain tiap slot beda);
   D(ITEM_i) = semua item + NONE.
C: unary (Boss perlu wins; NONE menular role->item; pantangan peran
   pertemuan sebelumnya), biner (maks 1 Healer; pasangan role-item
   terlarang; slot kosong tidak di tengah; peran musuh saling berbeda;
   Boss terakhir + defensif tak berturutan di mode antrean), global
   (Dragon Fang <= 1; total power <= budget).

Fungsi check() hanya menilai variabel yang SUDAH ter-assign sehingga bisa
dipakai untuk partial assignment saat backtracking maupun neighbour LS.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from game.ambush.config import AmbushConfig
from game.ambush.types import BOSS, EMPTY, HEALER, ITEM_TABLE, MINION, ROLE_TABLE

ROLE_PREFIX = "ROLE_"
ITEM_PREFIX = "ITEM_"

#: Isi termurah satu slot (Warrior + NONE): batas bawah sound untuk prune
#: budget parsial (Fase 2c). Warrior+NONE selalu lolos aturan non-biaya
#: (kompatibel, non-defensif, bukan Boss, NONE bebas di AllDifferent dan
#: canonical terpenuhi bila mengisi slot dengan slot-belakang-kosong —
#: bila tidak, bound ini tetap sound karena hanya dipakai sebagai batas
#: bawah: prune hanya bila BAHKAN isi termurah pun over-budget).
def _min_fill_cost(cfg: AmbushConfig) -> int:
    """Isi termurah satu slot pada mode aktif (BUFF: tanpa Minion)."""
    return min(
        spec.cost for name, spec in ROLE_TABLE.items()
        if name != EMPTY and (cfg.mode == "SEQUENTIAL" or name != MINION)
    )


MIN_FILL_COST = 3  # warisan (dipertahankan agar impor lama tak pecah)


def variable_names(cfg: AmbushConfig) -> List[str]:
    """Urutan variabel tetap (tie-break terakhir & basis deterministik)."""
    names = []
    for i in range(1, cfg.kmax + 1):
        names.append(f"{ROLE_PREFIX}{i}")
    for i in range(1, cfg.kmax + 1):
        names.append(f"{ITEM_PREFIX}{i}")
    return names


def slot_of(var: str) -> int:
    """Nomor slot (1-based) dari nama variabel."""
    return int(var.split("_")[1])


def _mode_roles(cfg: AmbushConfig) -> List[str]:
    """Daftar peran pada mode aktif (Minion HANYA di SEQUENTIAL)."""
    return [r for r in ROLE_TABLE if r != EMPTY
            and (cfg.mode == "SEQUENTIAL" or r != MINION)]


def build_domains(wins: int, cfg: AmbushConfig) -> Dict[str, List[str]]:
    """Domain awal tiap variabel. (wins tidak dipakai di sini karena gating
    Boss ditegakkan sebagai unary constraint agar trace-nya terlihat; slot
    lead tetap satu-satunya yang BOLEH berisi Boss.)"""
    del wins  # gating Boss = constraint C, bukan penyempitan D
    roles_lead = _mode_roles(cfg) + [EMPTY]
    roles_rest = [r for r in roles_lead if r != BOSS]
    items = list(ITEM_TABLE)
    domains: Dict[str, List[str]] = {}
    for i in range(1, cfg.kmax + 1):
        domains[f"{ROLE_PREFIX}{i}"] = (
            list(roles_lead) if i == 1 else list(roles_rest)
        )
        domains[f"{ITEM_PREFIX}{i}"] = list(items)
    return domains


def neighbors_of(var: str, cfg: AmbushConfig) -> List[str]:
    """Graf tetangga statis untuk degree heuristic.

    ROLE_i bertetangga dengan semua ROLE lain (batas 1 Healer) + ITEM_i
    (pasangan terlarang). ITEM_i bertetangga dengan ROLE_i + semua ITEM lain
    (keunikan legendary). Urutan tetap agar deterministik.
    """
    out = []
    if var.startswith(ROLE_PREFIX):
        i = slot_of(var)
        for j in range(1, cfg.kmax + 1):
            if j != i:
                out.append(f"{ROLE_PREFIX}{j}")
        out.append(f"{ITEM_PREFIX}{i}")
    else:
        i = slot_of(var)
        out.append(f"{ROLE_PREFIX}{i}")
        for j in range(1, cfg.kmax + 1):
            if j != i:
                out.append(f"{ITEM_PREFIX}{j}")
    return out


def partial_cost(assign: Dict[str, str]) -> int:
    """Total biaya power variabel yang sudah ter-assign."""
    total = 0
    for var, val in assign.items():
        if val == EMPTY:
            continue
        if var.startswith(ROLE_PREFIX):
            total += ROLE_TABLE[val].cost
        else:
            total += ITEM_TABLE[val].cost
    return total


def check(
    assign: Dict[str, str], wins: int, budget: int, cfg: AmbushConfig,
    queue_rules: bool = False, min_active: int = 1,
    avoid_roles: Tuple[str, ...] = (),
) -> List[str]:
    """Kembalikan daftar pelanggaran untuk (partial) assignment. Kosong = konsisten.

    Args:
        queue_rules: True = aturan antrean duel berurutan (Boss terakhir,
            larangan defensif berturutan, peran musuh saling berbeda).
            False = aturan BUFF lama. Default False agar jalur BUFF/tahap
            lama tidak berubah.
        min_active: minimal slot ROLE non-NONE saat semua ROLE terisi
            (1 = mode BUFF, 2 = mode antrean SEQUENTIAL).
        avoid_roles: peran musuh pertemuan sebelumnya (variasi antar
            pertemuan; hanya berlaku di mode antrean).
    """
    bad: List[str] = []
    roles = {v: a for v, a in assign.items() if v.startswith(ROLE_PREFIX)}
    items = {v: a for v, a in assign.items() if v.startswith(ITEM_PREFIX)}

    # Unary: Boss hanya jika wins mencukupi.
    for var, val in roles.items():
        if val == BOSS and wins < cfg.boss_min_wins:
            bad.append(f"{var}=Boss butuh wins>={cfg.boss_min_wins} (wins={wins})")

    # Unary: slot kosong -> item harus kosong.
    for var, val in items.items():
        role_var = f"{ROLE_PREFIX}{slot_of(var)}"
        if val != EMPTY and roles.get(role_var) == EMPTY:
            bad.append(f"{var} terisi tapi {role_var}=NONE")

    # Biner: slot kosong tidak boleh di tengah (canonical, bunuh permutasi).
    seen_empty = False
    for i in range(1, cfg.kmax + 1):
        val = roles.get(f"{ROLE_PREFIX}{i}")
        if val is None:
            continue  # partial: belum bisa dinilai
        if val == EMPTY:
            seen_empty = True
        elif seen_empty:
            bad.append(f"ROLE_{i} terisi setelah slot kosong")
            break

    # Biner: maksimal satu Healer per squad.
    if sum(1 for v in roles.values() if v == HEALER) > 1:
        bad.append("dua Healer dalam satu squad")

    if queue_rules:
        # Antrean: Boss hanya di slot AKTIF terakhir (partial: slot di
        # belakangnya yang sudah terisi non-NONE = langgar; yang belum
        # terisi masih boleh diisi).
        for i in range(1, cfg.kmax + 1):
            if roles.get(f"{ROLE_PREFIX}{i}") != BOSS:
                continue
            for j in range(i + 1, cfg.kmax + 1):
                if roles.get(f"{ROLE_PREFIX}{j}") not in (None, EMPTY):
                    bad.append(f"Boss di ROLE_{i} bukan slot aktif "
                               f"terakhir (ROLE_{j} terisi)")
                    break
        # Antrean: dua peran defensif (Healer/Tank, termasuk Tank-Tank dan
        # Healer-Healer) tidak boleh BERTURUTAN.
        # Alasan desain: dua duel defensif berturut-turut menumpuk regen +
        # armor sehingga antrean membosankan dan urutan kehilangan makna
        # strategis (aturan ini yang membuat posisi penting untuk LS).
        # Partial yang berlubang di-skip (canonical menanganinya terpisah).
        defensive = {"Healer", "Tank"}
        for i in range(1, cfg.kmax):
            a = roles.get(f"{ROLE_PREFIX}{i}")
            b = roles.get(f"{ROLE_PREFIX}{i + 1}")
            if a in defensive and b in defensive:
                bad.append(f"{a}-{b} berturutan di ROLE_{i}/ROLE_{i + 1} "
                           f"(defensif ganda)")
                break
        # Antrean: SETIAP musuh dalam satu pertandingan harus berbeda
        # (permintaan pemain: jangan ada musuh yang sama muncul dua kali).
        # Dinilai pada ROLE yang sudah ter-assign (partial pun terpangkas).
        seen_roles = [v for v in roles.values() if v != EMPTY]
        if len(set(seen_roles)) != len(seen_roles):
            bad.append("peran musuh harus saling berbeda dalam satu antrean")
        # Antrean: variasi antar-pertemuan - peran pertemuan sebelumnya
        # tidak dipakai lagi bila memungkinkan (best-effort: CSP
        # mempruning sejak dini; pemilihan akhir tetap punya cadangan).
        if avoid_roles:
            repeated = sorted({v for v in seen_roles if v in avoid_roles})
            if repeated:
                bad.append("peran pertemuan sebelumnya masih dipakai "
                           f"({', '.join(repeated)})")

    # Biner: pasangan role-item harus kompatibel (matriks ITEM_ALLOWED).
    # Matriks ini yang mengikat graph: tiap ITEM terhubung ke ROLE slotnya
    # dengan dukungan parsial, sehingga degree/LCV/AC-3 punya bahan kerja.
    for var, val in items.items():
        if val == EMPTY:
            continue
        role_var = f"{ROLE_PREFIX}{slot_of(var)}"
        role = roles.get(role_var)
        if role is None or role == EMPTY:
            continue  # sudah/belum ditangani aturan lain
        if role not in ITEM_TABLE[val].allowed_roles:
            bad.append(f"{role} tidak kompatibel dengan {val}")

    # Global: antrean/squad minimal min_active anggota (director menyusun
    # PENYERANG; squad kosong membuat buff nol dan duel polos - sekaligus
    # mencegah LS mengosongkan squad demi mengejar target di bawah baseline
    # heuristik). Mode antrean butuh min 2 (syarat duel berurutan).
    # (Hanya dinilai bila semua ROLE sudah ter-assign; partial assignment
    # masih bisa diisi. Tanpa guard ini, assignment kosong ikut ditolak.)
    if len(roles) == cfg.kmax:
        n_active = sum(1 for v in roles.values() if v != EMPTY)
        if n_active < min_active:
            bad.append(f"slot aktif {n_active} < minimal {min_active}")

    # Global: SEMUA item non-NONE saling berbeda (AllDifferent penuh,
    # diurai pairwise di pair_ok). NONE boleh berulang (slot kosong).
    # Efek samping disengaja: duplikat Charm/Pedang kini ilegal sehingga
    # graph ITEM-ITEM padat (degree>0 sejak awal, LCV/AC-3 terlihat).
    seen_items = [v for v in items.values() if v != EMPTY]
    if len(set(seen_items)) != len(seen_items):
        bad.append("item non-NONE harus saling berbeda")

    # Global: total biaya power <= budget (berlaku juga untuk partial).
    cost = partial_cost(assign)
    if cost > budget:
        bad.append(f"total power {cost} melebihi budget {budget}")
    # Lower-bound sound (Fase 2c): slot kosong = cost 0, KECUALI kewajiban
    # min_active memaksa pengisian. Bila slot aktif + slot ROLE yang belum
    # terisi < min_active -> mustahil (prune). Bila kurang `need` anggota,
    # bahkan isi termurah (need × MIN_FILL_COST) yang over-budget -> prune.
    # Sound karena prune hanya bila TIDAK ADA penyelesaian dalam budget.
    n_role_unassigned = cfg.kmax - len(roles)
    n_active_now = sum(1 for v in roles.values() if v != EMPTY)
    if n_active_now + n_role_unassigned < min_active:
        bad.append(f"slot aktif maks {n_active_now + n_role_unassigned} "
                   f"< minimal {min_active}")
    elif min_active > n_active_now:
        need = min_active - n_active_now
        if cost + need * _min_fill_cost(cfg) > budget:
            bad.append(f"butuh {need} anggota lagi (min {cost + need * _min_fill_cost(cfg)} "
                       f"power) melebihi budget {budget}")

    return bad


def is_consistent(
    assign: Dict[str, str], wins: int, budget: int, cfg: AmbushConfig,
    queue_rules: bool = False, min_active: int = 1,
) -> bool:
    """True jika (partial) assignment tidak melanggar constraint apa pun."""
    return not check(assign, wins, budget, cfg, queue_rules, min_active)


def is_complete(assign: Dict[str, str], cfg: AmbushConfig) -> bool:
    """True jika semua variabel X sudah terisi (syarat solusi CSP)."""
    return all(
        f"{p}{i}" in assign for p in (ROLE_PREFIX, ITEM_PREFIX)
        for i in range(1, cfg.kmax + 1)
    )
