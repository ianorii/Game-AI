"""
adversarial_ai.py - Adversarial Search untuk Turn-Based Battle Duel.

Modul ini memodelkan duel sebagai permainan zero-sum antara Player (manusia)
dan NPC (kendali komputer), lalu mengimplementasikan keluarga algoritma
pencarian adversarial di atas model tersebut:

1. Minimax murni (tanpa pruning)          - baseline kebenaran
2. Minimax + Alpha-Beta Pruning           - algoritma produksi
3. Expectimax                              - dengan chance node probabilistik
4. Iterative Deepening + node budget      - "early stop" adaptif

Model Permainan
---------------
State  : BattleState (HP, defend, potion, cooldown SPECIAL, turn)
Aksi   : ATTACK, DEFEND, POTION, SPECIAL (branching factor <= 4)
Max    : NPC  (karena evaluasi ditulis dari sudut pandang NPC)
Min    : Player

Sudut Pandang Evaluasi
----------------------
Semua fungsi evaluasi mengembalikan skor dari sudut pandang NPC:
    score > 0  -> NPC unggul
    score < 0  -> NPC kalah
Karena itu NPC adalah node MAX dan Player adalah node MIN. Menyusun
pencarian sebagai MAX untuk Player akan membuat AI mengorbankan
dirinya sendiri demi menguntungkan lawan.

Skor terminal: +WIN_SCORE jika Player HP <= 0, -WIN_SCORE jika NPC HP <= 0
(0 jika keduanya mati bersamaan, yaitu seri).

Asumsi Pemodelan
----------------
A1. Perfect information : kedua pihak melihat state lengkap satu sama lain.
A2. Zero-sum           : utility satu pihak persis negatif dari yang lain;
                          tidak ada langkah yang saling menguntungkan.
A3. Damage ATTACK acak : lemparan 15..20 (uniform). Pencarian deterministik
                          memakai ekspektasi (ATTACK_DAMAGE) atau distribusi
                          penuh (expectimax, lihat `_action_outcomes`).
A4. Horizon terbatas    : pencarian dibatasi kedalaman; state di bawah horizon
                          dinilai dengan fungsi evaluasi, bukan nilai utility
                          sebenarnya.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Konstanta aturan battle
# ---------------------------------------------------------------------------

MAX_HP = 100
ATTACK_MIN = 15
ATTACK_MAX = 20
ATTACK_DAMAGE = 18           # ekspektasi damage ATTACK untuk pencarian deterministik
SPECIAL_DAMAGE = 30
POTION_HEAL = 25
POTION_LIMIT = 3
SPECIAL_COOLDOWN = 2
DEFEND_REDUCTION = 0.5
WIN_SCORE = 1000
DEFAULT_DEPTH = 4

ACTIONS = ("ATTACK", "DEFEND", "POTION", "SPECIAL")

ACTION_LABEL = {
    "ATTACK": "Serang",
    "DEFEND": "Bertahan",
    "POTION": "Ramuan",
    "SPECIAL": "Jurus Khusus",
}

INF = float("inf")

# Kombinasi damage ATTACK beserta probabilitasnya (asumsi A3: uniform).
ATTACK_OUTCOMES: Tuple[Tuple[int, float], ...] = tuple(
    (dmg, 1.0 / (ATTACK_MAX - ATTACK_MIN + 1))
    for dmg in range(ATTACK_MIN, ATTACK_MAX + 1)
)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class BattleState:
    """Representasi state duel turn-based.

    Attributes:
        player_hp: HP player saat ini (0..MAX_HP)
        npc_hp: HP NPC saat ini (0..MAX_HP)
        player_defending: Player sedang bertahan (damage masuk -50%)
        npc_defending: NPC sedang bertahan (damage masuk -50%)
        player_potions: Sisa potion player
        npc_potions: Sisa potion NPC
        player_special_cd: Cooldown SPECIAL player
        npc_special_cd: Cooldown SPECIAL NPC
        turn: Siapa yang giliran (0 = Player/MIN, 1 = NPC/MAX)
    """

    player_hp: int = MAX_HP
    npc_hp: int = MAX_HP
    player_defending: bool = False
    npc_defending: bool = False
    player_potions: int = POTION_LIMIT
    npc_potions: int = POTION_LIMIT
    player_special_cd: int = 0
    npc_special_cd: int = 0
    turn: int = 0

    # -- util -------------------------------------------------------------
    def clone(self) -> "BattleState":
        """Return salinan state (state asli tidak pernah dimutasi)."""
        return replace(self)

    def hp(self, is_npc: bool) -> int:
        """HP milik salah satu pihak."""
        return self.npc_hp if is_npc else self.player_hp

    def potions(self, is_npc: bool) -> int:
        """Stok potion milik salah satu pihak."""
        return self.npc_potions if is_npc else self.player_potions

    def is_terminal(self) -> bool:
        """True jika duel sudah berakhir (ada HP <= 0)."""
        return self.player_hp <= 0 or self.npc_hp <= 0

    # -- aturan permainan -------------------------------------------------
    def legal_actions(self, is_npc: bool) -> Tuple[str, ...]:
        """Aksi legal untuk pihak yang gilirannya berjalan.

        - ATTACK & DEFEND selalu tersedia.
        - POTION hanya jika stok potion masih ada.
        - SPECIAL hanya jika cooldown sudah 0.

        Args:
            is_npc: True jika giliran NPC (MAX)

        Returns:
            Tuple aksi legal (urutan tetap sesuai ACTIONS)
        """
        if self.is_terminal():
            return ()

        acts: List[str] = ["ATTACK", "DEFEND"]
        if self.potions(is_npc) > 0:
            acts.append("POTION")
        cd = self.npc_special_cd if is_npc else self.player_special_cd
        if cd == 0:
            acts.append("SPECIAL")
        return tuple(acts)

    def apply_action(
        self,
        is_npc: bool,
        action: str,
        attack_damage: int = ATTACK_DAMAGE,
        special_damage: int = SPECIAL_DAMAGE,
    ) -> "BattleState":
        """Terapkan aksi dan kembalikan state baru.

        Aturan:
        - Defense aktif satu giliran lawan, lalu kedaluwarsa.
        - ATTACK/SPECIAL damage dipotong 50% jika target defending.
        - POTION memulihkan POTION_HEAL (maks MAX_HP) dan mengurangi stok.
        - SPECIAL memberi damage besar tetapi memicu cooldown.

        Args:
            is_npc: True jika aksi dilakukan NPC
            action: Salah satu dari ACTIONS
            attack_damage: Damage ATTACK (deterministic search memakai
                ekspektasi ATTACK_DAMAGE, expectimax mengiterasi semua nilai)
            special_damage: Nilai damage SPECIAL

        Returns:
            BattleState baru setelah aksi diterapkan
        """
        s = self.clone()
        me = "npc" if is_npc else "player"
        opp = "player" if is_npc else "npc"

        setattr(s, f"{me}_defending", False)

        cd = getattr(s, f"{me}_special_cd")
        if cd > 0:
            setattr(s, f"{me}_special_cd", cd - 1)

        if action == "ATTACK":
            dmg = attack_damage
            if getattr(s, f"{opp}_defending"):
                dmg = int(math.ceil(dmg * DEFEND_REDUCTION))
                setattr(s, f"{opp}_defending", False)
            setattr(s, f"{opp}_hp", max(0, getattr(s, f"{opp}_hp") - dmg))

        elif action == "DEFEND":
            setattr(s, f"{me}_defending", True)

        elif action == "POTION":
            setattr(s, f"{me}_hp", min(MAX_HP, getattr(s, f"{me}_hp") + POTION_HEAL))
            setattr(s, f"{me}_potions", max(0, getattr(s, f"{me}_potions") - 1))

        elif action == "SPECIAL":
            dmg = special_damage
            if getattr(s, f"{opp}_defending"):
                dmg = int(math.ceil(dmg * DEFEND_REDUCTION))
                setattr(s, f"{opp}_defending", False)
            setattr(s, f"{opp}_hp", max(0, getattr(s, f"{opp}_hp") - dmg))
            setattr(s, f"{me}_special_cd", SPECIAL_COOLDOWN)

        s.turn = 0 if is_npc else 1
        return s


# ---------------------------------------------------------------------------
# Analisis satu giliran (dasar untuk heuristik berbasis ancaman)
# ---------------------------------------------------------------------------

def incoming_damage(state: BattleState, attacker_is_npc: bool) -> int:
    """Damage maksimum yang bisa diberikan penyerang pada satu giliran.

    Mengasumsikan penyerang tidak memilih DEFEND, sehingga tidak ada pengurangan
    damage. Bila SPECIAL siap, SPECIAL (30) mengalahkan ATTACK (18).

    Args:
        state: State saat ini
        attacker_is_npc: True bila NPC yang menyerang

    Returns:
        Damage maksimum yang mungkin (0..SPECIAL_DAMAGE)
    """
    cd = state.npc_special_cd if attacker_is_npc else state.player_special_cd
    return SPECIAL_DAMAGE if cd == 0 else ATTACK_DAMAGE


def escapes_death(state: BattleState, victim_is_npc: bool) -> bool:
    """True bila pihak korban bisa selamat dari serangan maksimal giliran ini.

    Tiga jalan bertahan:
    1. HP saat ini sudah melebihi damage masuk.
    2. Stok potion ada dan hasil heal+(damage) masih di atas damage.
    3. DEFEND memotong damage 50% dan HP masih di atas damage terpotong.

    Args:
        state: State saat ini
        victim_is_npc: True bila NPC yang menjadi korban

    Returns:
        True bila korban punya minimal satu cara bertahan
    """
    dmg = incoming_damage(state, not victim_is_npc)
    hp = state.hp(victim_is_npc)

    if hp > dmg:
        return True
    if state.potions(victim_is_npc) > 0 and min(MAX_HP, hp + POTION_HEAL) > dmg:
        return True
    return hp > math.ceil(dmg * DEFEND_REDUCTION)


def is_decided(state: BattleState) -> bool:
    """True bila pemenang duel sudah pasti pada giliran ini.

    Dipakai sebagai kondisi *early stop*: bila tepat satu pihak pasti mati
    (tidak bisa dihindari) sementara pihak lain tidak, maka menelusuri lebih
    jauh tidak mengubah pemenang sehingga cabang boleh dipangkas.

    Catatan: ini kondisi heuristik, bukan pembuktian formal.
    ``escapes_death()`` hanya melihat satu giliran ke depan, jadi cabang yang
    dipangkas masih mungkin dapat dibalik oleh gerakan berikutnya. Pemangkasan
    ini karena itu dapat mengorbankan optimalitas pada state tertentu.

    Args:
        state: State saat ini

    Returns:
        True bila hasil duel sudah ditentukan
    """
    if state.is_terminal():
        return False
    player_dies = not escapes_death(state, False)
    npc_dies = not escapes_death(state, True)
    return player_dies != npc_dies


# ---------------------------------------------------------------------------
# Fungsi evaluasi
# ---------------------------------------------------------------------------
#
# Semua fungsi bersignatur (state) -> int dan berskala dari sudut pandang NPC.
# Skor terminal selalu ditambahkan terpisah lewat `_terminal_bonus`.


def _terminal_bonus(state: BattleState) -> int:
    """Bonus terminal: +WIN_SCORE bila Player mati, -WIN_SCORE bila NPC mati."""
    score = 0
    if state.player_hp <= 0:
        score += WIN_SCORE
    if state.npc_hp <= 0:
        score -= WIN_SCORE
    return score


def eval_hp_diff(state: BattleState) -> int:
    """Baseline paling naive: selisih HP saja.

   serve sebagai titik awal untuk mengukur berapa nilai yang disumbangkan
    komponen lain (potion, defend, ancaman).
    """
    return (state.npc_hp - state.player_hp) + _terminal_bonus(state)


def eval_balanced(state: BattleState) -> int:
    """Fungsi evaluasi baseline proyek.

        score = (NPC_HP - Player_HP)
                + (NPC_Potions - Player_Potions) * 10
                + 15 jika NPC defending, -15 jika Player defending
    """
    score = (state.npc_hp - state.player_hp)
    score += (state.npc_potions - state.player_potions) * 10
    score += 15 if state.npc_defending else 0
    score -= 15 if state.player_defending else 0
    return score + _terminal_bonus(state)


def eval_threat_aware(state: BattleState) -> int:
    """eval_balanced ditambah bonus untuk ancaman imminent.

    Menambahkan +60 bila Player tidak dapat menghindar dari serangan
    maksimal NPC pada giliran ini, dan -60 secara simetris untuk NPC.
    Tujuannya membuat AI "sadar" ketika salah satu pihak hampir kalah,
    kondisi yang sama sekali tidak tertangkap oleh eval_balanced.
    """
    score = (state.npc_hp - state.player_hp)
    score += (state.npc_potions - state.player_potions) * 10
    score += 15 if state.npc_defending else 0
    score -= 15 if state.player_defending else 0

    if not escapes_death(state, False):
        score += 60
    if not escapes_death(state, True):
        score -= 60
    return score + _terminal_bonus(state)


@dataclass(frozen=True)
class EvalWeights:
    """Bobot parametrik untuk keluarga fungsi evaluasi.

    Satu keluarga fungsi evaluasi dengan lima knob. Dipakai untuk eksperimen
    "perilaku NPC": mengubah bobot mengubah langsung preferensi aksi tanpa
    mengubah algoritma pencarian sama sekali.

    Attributes:
        name: Nama profil (untuk pelaporan)
        hp: Bobot selisih HP
        potion: Bobot selisih potion
        defend: Bonus saat NPC menahan, penalti saat Player menahan
        threat: Bonus saat Player tidak bisa lup dari serangan maximal
    """

    name: str
    hp: int = 1
    potion: int = 10
    defend: int = 15
    threat: int = 0


def make_weighted_eval(weights: EvalWeights) -> Callable[[BattleState], int]:
    """Bangun fungsi evaluasi dari satu set bobot.

    Args:
        weights: Objek EvalWeights yang mendefinisikan profile

    Returns:
        Fungsi ``(state) -> int`` berskala dari sudut pandang NPC
    """

    def _eval(state: BattleState) -> int:
        score = weights.hp * (state.npc_hp - state.player_hp)
        score += weights.potion * (state.npc_potions - state.player_potions)
        score += weights.defend if state.npc_defending else 0
        score -= weights.defend if state.player_defending else 0
        if weights.threat:
            if not escapes_death(state, False):
                score += weights.threat
            if not escapes_death(state, True):
                score -= weights.threat
        return score + _terminal_bonus(state)

    _eval.__name__ = f"eval_{weights.name}"
    return _eval


# Registry fungsi evaluasi siap pakai.
EVAL_FUNCTIONS: Dict[str, Callable[[BattleState], int]] = {
    "hp_diff": eval_hp_diff,
    "balanced": eval_balanced,
    "threat_aware": eval_threat_aware,
}

# Profile perilaku untuk eksperimen "tingkah laku NPC".
# Semua profile memakai algoritma & kedalaman yang sama, hanya evaluasinya
# yang berbeda, sehingga perilaku yang berbeda murni berasal dari evaluasi.
EVAL_PROFILES: Dict[str, EvalWeights] = {
    "aggressive": EvalWeights("aggressive", hp=1, potion=0, defend=-20, threat=80),
    "balanced": EvalWeights("balanced", hp=1, potion=10, defend=15, threat=0),
    "defensive": EvalWeights("defensive", hp=1, potion=25, defend=45, threat=20),
    "opportunist": EvalWeights("opportunist", hp=1, potion=15, defend=10, threat=60),
}


# ---------------------------------------------------------------------------
# Urutan aksi
# ---------------------------------------------------------------------------
#
# Alpha-beta hanya memangkas subtree yang "tidak mungkin outperform".
# Efektivitasnya sangat bergantung pada urutan: aksi yang lebih mungkin
# bagus dicoba lebih awal menutup window lebih cepat.
#
# Catatan: urutan dievaluasi di SEMUA node (kedua pihak), bukan hanya root,
# karena di situlah pemangkasan terjadi.

MOVE_ORDERS: Dict[str, Optional[Tuple[str, ...]]] = {
    "default": ("ATTACK", "DEFEND", "POTION", "SPECIAL"),
    "aggressive": ("SPECIAL", "ATTACK", "POTION", "DEFEND"),
    "defensive": ("DEFEND", "POTION", "ATTACK", "SPECIAL"),
    "random": None,          # diacak dengan RNG berbiji tetap (reproducible)
}

DEFAULT_ORDER = "default"
DEFAULT_EVAL = "balanced"
DEFAULT_ALGORITHM = "alphabeta"


# ---------------------------------------------------------------------------
# Algoritma pencarian
# ---------------------------------------------------------------------------

class AdversarialAI:
    """Keluarga algoritma pencarian adversarial untuk duel.

    Satu kelas ini dapat dikonfigurasi untuk menjalankan minimax, alpha-beta,
    expectimax, atau iterative deepening pada model yang sama, sehingga
    perbandingan kinerjanya benar-benar apples-to-apples (state, urutan, dan
    evaluasi identik; hanya algoritmanya yang diganti).

    Attributes:
        depth: Kedalaman pencarian default
        algorithm: "minimax" | "alphabeta" | "expectimax" | "iterative"
        eval_name: Kunci fungsi evaluasi yang aktif
        order_name: Kunci urutan aksi yang aktif
        early_stop: Aktifkan pemangkasan berbasis kondisi duel pasti dim Result
        node_budget: Batas node untuk iterative deepening
        nodes: Node dieksplorasi pada pencarian berjalan
        evaluations: Pemanggilan fungsi evaluasi
        prunes: Jumlah cutoff alpha-beta
        last_stats: Metrik pencarian terakhir
    """

    def __init__(
        self,
        depth: int = DEFAULT_DEPTH,
        algorithm: str = DEFAULT_ALGORITHM,
        eval_name: str = DEFAULT_EVAL,
        order_name: str = DEFAULT_ORDER,
        early_stop: bool = False,
        node_budget: Optional[int] = None,
        seed: int = 0,
    ):
        self.depth = depth
        self.algorithm = algorithm
        self.eval_name = eval_name
        self.order_name = order_name
        self.early_stop = early_stop
        self.node_budget = node_budget
        self.seed = seed

        self._eval = self._resolve_eval(eval_name)
        self._rng = random.Random(seed)

        self.nodes = 0
        self.evaluations = 0
        self.prunes = 0
        self.early_stops = 0
        self.last_stats: Dict = {}
        self.think_history: List[Dict] = []

    # ------------------------------------------------------------------
    # Konfigurasi
    # ------------------------------------------------------------------
    def _resolve_eval(self, name: str) -> Callable[[BattleState], int]:
        """Cari fungsi evaluasi berdasarkan nama, dukung juga nama profile."""
        if name in EVAL_FUNCTIONS:
            return EVAL_FUNCTIONS[name]
        if name in EVAL_PROFILES:
            return make_weighted_eval(EVAL_PROFILES[name])
        raise ValueError(f"Fungsi evaluasi tidak dikenal: {name!r}")

    def configure(
        self,
        algorithm: Optional[str] = None,
        eval_name: Optional[str] = None,
        order_name: Optional[str] = None,
        early_stop: Optional[bool] = None,
        node_budget: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> "AdversarialAI":
        """Ubah konfigurasi di tempat (chainable), lalu reset RNG."""
        if algorithm is not None:
            self.algorithm = algorithm
        if eval_name is not None:
            self.eval_name = eval_name
            self._eval = self._resolve_eval(eval_name)
        if order_name is not None:
            self.order_name = order_name
        if early_stop is not None:
            self.early_stop = early_stop
        if node_budget is not None:
            self.node_budget = node_budget
        if seed is not None:
            self.seed = seed
            self._rng = random.Random(seed)
        return self

    def _reset_counters(self) -> None:
        """Nolkan semua counter sebelum satuaporefrom benchmark."""
        self.nodes = 0
        self.evaluations = 0
        self.prunes = 0
        self.early_stops = 0

    # ------------------------------------------------------------------
    # Fungsi evaluasi
    # ------------------------------------------------------------------
    def evaluate_state(self, state: BattleState) -> int:
        """Nilai state memakai fungsi evaluasi yang sedang aktif.

        Skor positif berarti NPC unggul. Terminal: +WIN_SCORE bila Player mati,
        -WIN_SCORE bila NPC mati.
        """
        return self._eval(state)

    # ------------------------------------------------------------------
    # Chance node (asumsi A3: damage ATTACK acak 15..20)
    # ------------------------------------------------------------------
    def _action_outcomes(
        self, state: BattleState, is_npc: bool, action: str
    ) -> List[Tuple[float, BattleState]]:
        """Distribusi hasil satu aksi untuk expectimax.

        ATTACK mengembang semua lemparan damage 15..20 dengan probabilitas
        seragam; aksi lain deterministik (probabilitas 1).

        Args:
            state: State sebelum aksi
            is_npc: True bila aksi dilakukan NPC
            action: Nama aksi

        Returns:
            List pasangan (probabilitas, state_baru)
        """
        if action == "ATTACK":
            return [
                (p, state.apply_action(is_npc, action, attack_damage=dmg))
                for dmg, p in ATTACK_OUTCOMES
            ]
        return [(1.0, state.apply_action(is_npc, action))]

    # ------------------------------------------------------------------
    # Urutan aksi
    # ------------------------------------------------------------------
    def ordered_actions(self, state: BattleState, is_npc: bool) -> Tuple[str, ...]:
        """Aksi legal yang sudah diurutkan sesuai ``order_name``.

        Args:
            state: State saat ini
            is_npc: True untuk NPC (MAX)

        Returns:
            Tuple aksi legal terurut
        """
        legal = state.legal_actions(is_npc)
        if self.order_name == "random":
            shuffled = list(legal)
            self._rng.shuffle(shuffled)
            return tuple(shuffled)
        order = MOVE_ORDERS.get(self.order_name) or ACTIONS
        return tuple(a for a in order if a in legal) or legal

    # ------------------------------------------------------------------
    # 1) Minimax murni (baseline)
    # ------------------------------------------------------------------
    def minimax(
        self, state: BattleState, depth: int, is_maximizing: bool
    ) -> Tuple[float, Optional[str]]:
        """Minimax tanpa pruning.

        Args:
            state: State saat ini
            depth: Sisa kedalaman pencarian
            is_maximizing: True jika giliran NPC (MAX), False jika Player (MIN)

        Returns:
            Tuple (best_score, best_action). best_action None di leaf/terminal.
        """
        self.nodes += 1

        if depth == 0 or state.is_terminal():
            self.evaluations += 1
            return self.evaluate_state(state), None

        if self.early_stop and is_decided(state):
            self.early_stops += 1
            self.evaluations += 1
            return self.evaluate_state(state), None

        actions = self.ordered_actions(state, is_maximizing)
        if not actions:
            self.evaluations += 1
            return self.evaluate_state(state), None

        if is_maximizing:
            best_score, best_action = -INF, None
            for action in actions:
                child = state.apply_action(True, action)
                score, _ = self.minimax(child, depth - 1, False)
                if score > best_score:
                    best_score, best_action = score, action
            return best_score, best_action

        best_score, best_action = INF, None
        for action in actions:
            child = state.apply_action(False, action)
            score, _ = self.minimax(child, depth - 1, True)
            if score < best_score:
                best_score, best_action = score, action
        return best_score, best_action

    # ------------------------------------------------------------------
    # 2) Minimax + Alpha-Beta Pruning
    # ------------------------------------------------------------------
    def alphabeta(
        self,
        state: BattleState,
        depth: int,
        alpha: float,
        beta: float,
        is_maximizing: bool,
    ) -> Tuple[float, Optional[str]]:
        """Minimax dengan Alpha-Beta Pruning.

        ``alpha`` adalah batas bawah yang dijamin oleh MAX di jalur ini,
        ``beta`` adalah batas atas yang dijamin oleh MIN. Saat ``beta <= alpha``,
        cabang di atas sudah pasti kalah dan boleh dipangkas.

        Args:
            state: State saat ini
            depth: Sisa kedalaman
            alpha: Batas bawah
            beta: Batas atas
            is_maximizing: True jika giliran NPC (MAX)

        Returns:
            Tuple (best_score, best_action)
        """
        self.nodes += 1

        if depth == 0 or state.is_terminal():
            self.evaluations += 1
            return self.evaluate_state(state), None

        if self.early_stop and is_decided(state):
            self.early_stops += 1
            self.evaluations += 1
            return self.evaluate_state(state), None

        actions = self.ordered_actions(state, is_maximizing)
        if not actions:
            self.evaluations += 1
            return self.evaluate_state(state), None

        if is_maximizing:
            best_score, best_action = -INF, None
            for action in actions:
                child = state.apply_action(True, action)
                score, _ = self.alphabeta(child, depth - 1, alpha, beta, False)
                if score > best_score:
                    best_score, best_action = score, action
                alpha = max(alpha, best_score)
                if beta <= alpha:
                    self.prunes += 1
                    break
            return best_score, best_action

        best_score, best_action = INF, None
        for action in actions:
            child = state.apply_action(False, action)
            score, _ = self.alphabeta(child, depth - 1, alpha, beta, True)
            if score < best_score:
                best_score, best_action = score, action
            beta = min(beta, best_score)
            if beta <= alpha:
                self.prunes += 1
                break
        return best_score, best_action

    # ------------------------------------------------------------------
    # 3) Expectimax (opsional, dengan probabilitas)
    # ------------------------------------------------------------------
    def expectimax(
        self, state: BattleState, depth: int, is_maximizing: bool
    ) -> Tuple[float, Optional[str]]:
        """Expectimax dengan chance node pada damage ATTACK.

        Bentuk yang dipakai: ``max_a E_omega[...]`` pada node NPC, dan
        ``min_a E_omega[...]`` pada node Player. Node MIN tetap memakai minimum
        karena lawan adalah manusia yang rasional dan berlawanan, bukan agen
        acak; hanya nilai damage-nya yang dimodelkan secara probabilistik.

        Tidak ada alpha-beta di sini: nilai yang rendah dibatasi oleh
        ekspektasi, bukan oleh minimum, sehingga pruning berbasis jendela
        alpha-beta tidak lagi berlaku.

        Args:
            state: State saat ini
            depth: Sisa kedalaman
            is_maximizing: True jika giliran NPC (MAX)

        Returns:
            Tuple (best_score, best_action)
        """
        self.nodes += 1

        if depth == 0 or state.is_terminal():
            self.evaluations += 1
            return self.evaluate_state(state), None

        if self.early_stop and is_decided(state):
            self.early_stops += 1
            self.evaluations += 1
            return self.evaluate_state(state), None

        actions = self.ordered_actions(state, is_maximizing)
        if not actions:
            self.evaluations += 1
            return self.evaluate_state(state), None

        if is_maximizing:
            best_score, best_action = -INF, None
            for action in actions:
                expected = self._expected_value(state, True, action, depth - 1)
                if expected > best_score:
                    best_score, best_action = expected, action
            return best_score, best_action

        best_score, best_action = INF, None
        for action in actions:
            expected = self._expected_value(state, False, action, depth - 1)
            if expected < best_score:
                best_score, best_action = expected, action
        return best_score, best_action

    def _expected_value(
        self, state: BattleState, is_npc: bool, action: str, depth: int
    ) -> float:
        """Ekspektasi skor anak untuk satu aksi (chance node).

        Args:
            state: State sebelum aksi
            is_npc: True bila aksi dilakukan NPC
            action: Nama aksi
            depth: Sisa kedalaman untuk rekuensi anak

        Returns:
            Ekspektasi skor dari sudut pandang NPC
        """
        total = 0.0
        for prob, child in self._action_outcomes(state, is_npc, action):
            score, _ = self.expectimax(child, depth, not is_npc)
            total += prob * score
        return total

    # ------------------------------------------------------------------
    # 4) Iterative Deepening + node budget ("early stop" berbasis waktu)
    # ------------------------------------------------------------------
    def iterative_deepening(
        self, state: BattleState, max_depth: int, is_maximizing: bool = True
    ) -> Tuple[float, Optional[str], int, List[Tuple[str, float]]]:
        """Iterative deepening dengan batas node.

        Menjalankan alpha-beta pada kedalaman 1, 2, 3, ... dan berhenti begitu
        anggaran node habis. Hanya hasil iterasi yang *selesai* yang diterima;
        hasil kedalaman yang lebih dalam tidak pernah dipakai sebagai jawaban.

        Setiap iterasi memakai ``_root_scores`` (jendela penuh per aksi root)
        alih-alih ``alphabeta`` biasa, supaya skor tiap aksi root selalu
        tersedia untuk debug overlay dan supaya biaya per iterasi konsisten
        dengan algoritma lain yang dibandingkan di laporan.

        Keuntungan: pada anggaran kecil AI tetap punya jawaban dari iterasi
        terdalam yang tuntas, bukan jawaban di kedalaman 1.

        Args:
            state: State root
            max_depth: Kedalaman maksimum
            is_maximizing: True jika giliran NPC (MAX)

        Returns:
            Tuple (best_score, best_action, kedalaman_yang_selesai, root_scores)
        """
        budget = self.node_budget
        best_score = self.evaluate_state(state)
        best_action: Optional[str] = None
        best_scores: List[Tuple[str, float]] = []
        completed = 0

        for d in range(1, max_depth + 1):
            if budget is not None and self.nodes >= budget:
                break
            scores = self._root_scores(
                state, d, use_alpha=True, is_npc=is_maximizing
            )
            if scores:
                best_scores = scores
                best_action = scores[0][0]
                best_score = scores[0][1]
                completed = d
        return best_score, best_action, completed, best_scores

    # ------------------------------------------------------------------
    # Analisis root (skor tiap aksi, untuk overlay debug)
    # ------------------------------------------------------------------
    def _root_scores(
        self,
        state: BattleState,
        depth: int,
        use_alpha: bool,
        is_npc: bool = True,
    ) -> List[Tuple[str, float]]:
        """Hitung skor tiap aksi legal di root.

        Tiap anak dievaluasi dengan jendela penuh agar skor tiap cabang akurat,
        sehingga bisa ditampilkan pada debug overlay tanpa bias pruning.

        Fungsi evaluasi selalu berorientasi NPC (skor positif berarti NPC
        unggul). Karena itu ketika root adalah giliran Player, Player mencari
        skor *terendah*, dan hasilnya diurutkan menaik. Sisi maximizer dan
        minimizer di dalam pohon tetap bergantian normal sesuai giliran.

        Args:
            state: State root
            depth: Kedalaman pencarian
            use_alpha: True pakai alphabeta, False pakai minimax murni
            is_npc: True bila root adalah giliran NPC (MAX), False bila Player (MIN)

        Returns:
            List pasangan (action, score) terurut dari yang paling menguntungkan
            bagi pihak yang mendapat giliran di root
        """
        results: List[Tuple[str, float]] = []
        for action in self.ordered_actions(state, is_npc):
            child = state.apply_action(is_npc, action)
            if use_alpha:
                score, _ = self.alphabeta(child, depth - 1, -INF, INF, not is_npc)
            else:
                score, _ = self.minimax(child, depth - 1, not is_npc)
            results.append((action, score))
        results.sort(key=lambda item: item[1], reverse=is_npc)
        return results

    def _root_expectimax(
        self, state: BattleState, depth: int, is_npc: bool = True
    ) -> List[Tuple[str, float]]:
        """Skor tiap aksi di root untuk expectimax.

        Di node chance, ekspektasi dihitung sebagai rata-rata. Di node
        Player, yang diambil adalah nilai ekspektasi *terkecil* (Player mencari
        hasil terburuk), bukan rata-rata dari nilai ekspektasi.

        Args:
            state: State root
            depth: Kedalaman pencarian
            is_npc: True bila root adalah giliran NPC (MAX)

        Returns:
            List pasangan (action, score) terurut dari yang paling menguntungkan
        """
        results: List[Tuple[str, float]] = []
        for action in self.ordered_actions(state, is_npc):
            results.append(
                (action, self._expected_value(state, is_npc, action, depth - 1))
            )
        results.sort(key=lambda item: item[1], reverse=is_npc)
        return results

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def _empty_stats(self, depth: int, root_is_npc: bool = True) -> Dict:
        """Struktur stats kosong (dipakai saat state sudah terminal)."""
        return {
            "depth": depth,
            "algorithm": self.algorithm,
            "eval_name": self.eval_name,
            "order_name": self.order_name,
            "early_stop": self.early_stop,
            "root_is_npc": root_is_npc,
            "best_action": None,
            "best_score": None,
            "root_scores": [],
            "minimax_root_scores": [],
            "minimax_nodes": 0,
            "alphabeta_nodes": 0,
            "iterative_nodes": 0,
            "expectimax_nodes": 0,
            "algorithm_nodes": 0,
            "completed_depth": 0,
            "pruned_nodes": 0,
            "cutoffs": 0,
            "early_stop_hits": 0,
            "prune_efficiency": 0.0,
            "evaluations": 0,
            "minimax_evaluations": 0,
            "time_ms": 0.0,
        }

    def think(
        self,
        state: BattleState,
        depth: Optional[int] = None,
        run_baseline: bool = True,
        root_is_npc: bool = True,
    ) -> Dict:
        """Tentukan aksi terbaik untuk pihak yang mendapat giliran.

        Default ``root_is_npc=True`` mempertahankan perilaku produksi: AI
        mengendalikan NPC, yang menjadi pihak pemaksimum. Setel
        ``root_is_npc=False`` untuk menjalankan algoritma yang sama dari sisi
        Player; karena fungsi evaluasi berorientasi NPC, Player lalu memilih
        aksi dengan skor terendah. Ini yang dipakai eksperimen duel agar
        lawan AI benar-benar Mau bersaing, bukan agen yang justru
        bekerja untuk NPC.

        Args:
            state: State saat giliran pihak yang akan bertindak
            depth: Override kedalaman pencarian (opsional)
            run_baseline: Jalankan juga minimax murni sebagai pembanding node
                count. Parameter ini default True demi mempertahankan overlay
                debug, dan False untuk benchmark murni (hemat ~2x waktu).
            root_is_npc: True bila giliran root milik NPC (MAX), False bila Player (MIN)

        Returns:
            dict statistik (juga disimpan di self.last_stats)
        """
        depth = self.depth if depth is None else depth

        if state.is_terminal():
            self.last_stats = self._empty_stats(depth, root_is_npc)
            self._record(state, self.last_stats)
            return self.last_stats

        t0 = time.perf_counter()

        # --- Baseline minimax murni (opsional, untuk perbandingan node) ---
        minimax_scores: List[Tuple[str, float]] = []
        minimax_nodes = 0
        minimax_eval = 0
        if run_baseline:
            self._reset_counters()
            minimax_scores = self._root_scores(
                state, depth, use_alpha=False, is_npc=root_is_npc
            )
            minimax_nodes = self.nodes
            minimax_eval = self.evaluations

        # --- Algoritma yang dikonfigurasi ---
        self._reset_counters()
        completed_depth = depth

        if self.algorithm == "minimax":
            scores = self._root_scores(
                state, depth, use_alpha=False, is_npc=root_is_npc
            )
        elif self.algorithm == "alphabeta":
            scores = self._root_scores(
                state, depth, use_alpha=True, is_npc=root_is_npc
            )
        elif self.algorithm == "expectimax":
            scores = self._root_expectimax(state, depth, is_npc=root_is_npc)
        elif self.algorithm == "iterative":
            # Iterative deepening sudah menjalankan alpha-beta sendiri pada
            # kedalaman 1..depth, jadi tidak perlu run depth penuh terpisah.
            _, _, completed_depth, scores = self.iterative_deepening(
                state, depth, is_maximizing=root_is_npc
            )
        else:
            raise ValueError(f"Algoritma tidak dikenal: {self.algorithm!r}")

        algorithm_nodes = self.nodes
        algorithm_eval = self.evaluations
        cutoffs = self.prunes
        stops = self.early_stops

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        best_action = scores[0][0] if scores else None
        best_score = scores[0][1] if scores else None

        # Node terpangkas = selisih node minimax murni vs algoritma aktif.
        if run_baseline and minimax_nodes > 0:
            pruned = max(0, minimax_nodes - algorithm_nodes)
            prune_eff = pruned / minimax_nodes * 100.0
        else:
            pruned = 0
            prune_eff = 0.0

        stats = {
            "depth": depth,
            "algorithm": self.algorithm,
            "eval_name": self.eval_name,
            "order_name": self.order_name,
            "early_stop": self.early_stop,
            "root_is_npc": root_is_npc,
            "best_action": best_action,
            "best_score": best_score,
            "root_scores": scores,
            "minimax_root_scores": minimax_scores,
            "minimax_nodes": minimax_nodes,
            "alphabeta_nodes": algorithm_nodes if self.algorithm in ("alphabeta", "minimax", "iterative") else 0,
            "iterative_nodes": algorithm_nodes if self.algorithm == "iterative" else 0,
            "expectimax_nodes": algorithm_nodes if self.algorithm == "expectimax" else 0,
            "algorithm_nodes": algorithm_nodes,
            "completed_depth": completed_depth,
            "pruned_nodes": pruned,
            "cutoffs": cutoffs,
            "early_stop_hits": stops,
            "prune_efficiency": prune_eff,
            "evaluations": algorithm_eval,
            "minimax_evaluations": minimax_eval,
            "time_ms": elapsed_ms,
        }
        self.last_stats = stats
        self._record(state, stats)
        return stats

    def _record(self, state: BattleState, stats: Dict) -> None:
        """Simpan satu entri riwayat giliran untuk keperluan logging.

        Riwayat ini hanya dipakai alat eksperimen (``experiments.log_duel_csv``)
        agar CSV bisa ditulis per giliran, bukan hanya snapshot terakhir.
        Produksi tidak memakainya, jadi penambahannya tidak memengaruhi
        perilaku pencarian.

        Args:
            state: State saat keputusan diambil
            stats: Dict statistik yang dikembalikan ``think``
        """
        self.think_history.append(
            {
                "state": BattleState(
                    player_hp=state.player_hp,
                    npc_hp=state.npc_hp,
                    player_potions=state.player_potions,
                    npc_potions=state.npc_potions,
                    player_defending=state.player_defending,
                    npc_defending=state.npc_defending,
                    player_special_cd=state.player_special_cd,
                    npc_special_cd=state.npc_special_cd,
                    turn=state.turn,
                ),
                "stats": dict(stats),
            }
        )

    # ------------------------------------------------------------------
    # Perbandingan tiga algoritma pada state yang sama
    # ------------------------------------------------------------------
    def compare_all(self, state: BattleState, depth: Optional[int] = None) -> Dict:
        """Jalankan minimax, alpha-beta, dan early stop pada state yang sama.

        Node count ketiganya dibandingkan langsung karena state, urutan, dan
        fungsi evaluasinya identik - hanya algoritme pemangkasannya yang beda.
        Ini yang dipakai overlay debug untuk tabel perbandingan.

        Args:
            state: State saat giliran NPC
            depth: Override kedalaman pencarian (opsional)

        Returns:
            Dict berisi node count tiap algoritma dan aksi yang dipilih masing-masing
        """
        depth = self.depth if depth is None else depth
        if state.is_terminal():
            return self._empty_stats(depth)

        results: Dict[str, Dict] = {}

        self._reset_counters()
        t0 = time.perf_counter()
        mm_scores = self._root_scores(state, depth, use_alpha=False)
        results["minimax"] = {
            "nodes": self.nodes,
            "evaluations": self.evaluations,
            "time_ms": (time.perf_counter() - t0) * 1000.0,
            "best_action": mm_scores[0][0] if mm_scores else None,
        }

        self._reset_counters()
        t0 = time.perf_counter()
        ab_scores = self._root_scores(state, depth, use_alpha=True)
        results["alphabeta"] = {
            "nodes": self.nodes,
            "evaluations": self.evaluations,
            "cutoffs": self.prunes,
            "time_ms": (time.perf_counter() - t0) * 1000.0,
            "best_action": ab_scores[0][0] if ab_scores else None,
        }

        # Early stop: alpha-beta + pemangkasan berbasis kondisi duel pasti
        self._reset_counters()
        t0 = time.perf_counter()
        saved = self.early_stop
        self.early_stop = True
        es_scores = self._root_scores(state, depth, use_alpha=True)
        self.early_stop = saved
        results["early_stop"] = {
            "nodes": self.nodes,
            "evaluations": self.evaluations,
            "cutoffs": self.prunes,
            "early_stop_hits": self.early_stops,
            "time_ms": (time.perf_counter() - t0) * 1000.0,
            "best_action": es_scores[0][0] if es_scores else None,
        }

        mm_nodes = results["minimax"]["nodes"]
        stats = {
            "depth": depth,
            "algorithm": self.algorithm,
            "eval_name": self.eval_name,
            "order_name": self.order_name,
            "root_scores": ab_scores,
            "minimax_root_scores": mm_scores,
            "comparison": results,
            "minimax_nodes": mm_nodes,
            "alphabeta_nodes": results["alphabeta"]["nodes"],
            "pruned_nodes": max(0, mm_nodes - results["alphabeta"]["nodes"]),
            "prune_efficiency": (
                max(0, mm_nodes - results["alphabeta"]["nodes"]) / mm_nodes * 100.0
                if mm_nodes
                else 0.0
            ),
            "best_action": results["alphabeta"]["best_action"],
            "best_score": ab_scores[0][1] if ab_scores else None,
            "actions_agree": len(
                {r["best_action"] for r in results.values()}
            ) == 1,
        }
        self.last_stats = stats
        return stats


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    s = BattleState(player_hp=100, npc_hp=100, turn=1)

    print("=== Alpha-beta harus identik dengan minimax ===")
    for d in range(1, 7):
        ai_a = AdversarialAI(depth=d, algorithm="minimax")
        ai_b = AdversarialAI(depth=d, algorithm="alphabeta")
        mm = ai_a.think(s, depth=d, run_baseline=False)
        ab = ai_b.think(s, depth=d, run_baseline=False)
        agree = mm["best_action"] == ab["best_action"]
        print(
            f"depth {d}: {mm['best_action']:>7} vs {ab['best_action']:<7} "
            f"node {mm['algorithm_nodes']:>6} -> {ab['algorithm_nodes']:<6} "
            f"{'OK' if agree else 'BEDA'}"
        )

    print("\n=== Perbandingan algoritma (state sama) ===")
    ai = AdversarialAI(depth=5)
    cmp_stats = ai.compare_all(s, depth=5)
    for name, r in cmp_stats["comparison"].items():
        print(f"{name:>11}: {r['nodes']:>6} node  {r['time_ms']:6.2f} ms  aksi={r['best_action']}")

    print("\n=== Ekspektasi ATTACK harus 17.5 ===")
    print(f"  mean damage = {sum(d * p for d, p in ATTACK_OUTCOMES):.2f}")
