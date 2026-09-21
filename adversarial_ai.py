"""
adversarial_ai.py - Adversarial Search untuk Turn-Based Battle Duel.

Modul ini mengimplementasikan model permainan zero-sum antara Player dan NPC
beserta dua algoritma pencarian adversarial:

1. Minimax murni (tanpa pruning)
2. Minimax dengan Alpha-Beta Pruning

Model permainan
---------------
State  : BattleState (player_hp, npc_hp, defending, potions, special cooldown)
Aksi   : ATTACK, DEFEND, POTION, SPECIAL (branching factor <= 4)
Max    : NPC AI (karena fungsi evaluasi ditulis dari sudut pandang NPC:
         skor positif = kondisi menguntungkan NPC)
Min    : Player

Catatan sudut pandang
---------------------
Rumus evaluasi yang dipakai adalah rumus dari sudut pandang NPC:
    score = (NPC_HP - Player_HP) + (NPC_Potions - Player_Potions) * 10
            + (15 jika NPC defending) - (15 jika Player defending)
Terminal: +1000 jika Player HP <= 0, -1000 jika NPC HP <= 0.

Karena skor positif berarti NPC unggul, maka NPC diperlakukan sebagai node MAX
dan Player sebagai node MIN agar AI bermain optimal (menang).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Konstanta aturan battle
# ---------------------------------------------------------------------------

MAX_HP = 100                 # HP maksimum Player dan NPC
ATTACK_MIN = 15              # Damage ATTACK minimum (dipakai saat resolusi)
ATTACK_MAX = 20              # Damage ATTACK maksimum (dipakai saat resolusi)
ATTACK_DAMAGE = 18           # Damage ATTACK ekspektasi (dipakai mesin pencarian)
SPECIAL_DAMAGE = 30          # Damage SPECIAL (serangan kuat)
POTION_HEAL = 25             # HP yang dipulihkan POTION
POTION_LIMIT = 3             # Stok potion awal
SPECIAL_COOLDOWN = 2         # Cooldown SPECIAL dalam giliran
DEFEND_REDUCTION = 0.5       # DEFEND mengurangi damage 50%
WIN_SCORE = 1000             # Bonus terminal
DEFAULT_DEPTH = 4            # Kedalaman pencarian default

# Urutan aksi (sesuai spesifikasi)
ACTIONS = ("ATTACK", "DEFEND", "POTION", "SPECIAL")

# Label manusiawi untuk UI
ACTION_LABEL = {
    "ATTACK": "Serang",
    "DEFEND": "Bertahan",
    "POTION": "Ramuan",
    "SPECIAL": "Jurus Khusus",
}


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
        """Return salinan state (dipakai setiap transisi agar state asli aman)."""
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
        """Daftar aksi legal untuk pihak yang gilirannya berjalan.

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
        - POTION memulihkan POTION_HEAL (maksimal MAX_HP) dan mengurangi stok.
        - SPECIAL memberi damage besar tetapi memicu cooldown.

        Args:
            is_npc: True jika aksi dilakukan NPC
            action: Salah satu dari ACTIONS
            attack_damage: Nilai damage ATTACK (search pakai ekspektasi, battle
                bisa memakai nilai acak 15-20)
            special_damage: Nilai damage SPECIAL

        Returns:
            BattleState baru setelah aksi diterapkan
        """
        s = self.clone()
        me = "npc" if is_npc else "player"
        opp = "player" if is_npc else "npc"

        # Defense kedaluwarsa di awal giliran sendiri (hanya melindungi 1 giliran lawan)
        setattr(s, f"{me}_defending", False)

        # Tick cooldown SPECIAL milik pihak yang beraksi
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

        # Serahkan giliran ke lawan
        s.turn = 0 if is_npc else 1
        return s


class AdversarialAI:
    """AI adversarial (Minimax & Alpha-Beta) untuk mengendalikan NPC.

    Attribute statistik (diisi oleh think()):
        last_stats: dict berisi metrik performa pencarian terakhir
        nodes: Jumlah node yang dieksplorasi pada pencarian yang berjalan
        evaluations: Jumlah pemanggilan evaluate_state
        prunes: Jumlah pemangkasan alpha-beta
    """

    def __init__(self, depth: int = DEFAULT_DEPTH):
        """
        Args:
            depth: Kedalaman pencarian (ply) default
        """
        self.depth = depth
        self.nodes = 0
        self.evaluations = 0
        self.prunes = 0
        self.last_stats: Dict = {}

    # ------------------------------------------------------------------
    # Fungsi evaluasi heuristik
    # ------------------------------------------------------------------
    def evaluate_state(self, state: BattleState) -> int:
        """Nilai heuristik state dari sudut pandang NPC.

        Score = (NPC_HP - Player_HP)
                + (NPC_Potions - Player_Potions) * 10
                + (15 jika NPC defending) - (15 jika Player defending)

        Terminal:
            +1000 jika Player HP <= 0 (NPC menang)
            -1000 jika NPC HP <= 0 (NPC kalah)

        Args:
            state: BattleState yang dinilai

        Returns:
            int skor heuristik
        """
        score = (state.npc_hp - state.player_hp)
        score += (state.npc_potions - state.player_potions) * 10
        score += 15 if state.npc_defending else 0
        score -= 15 if state.player_defending else 0

        if state.player_hp <= 0:
            score += WIN_SCORE
        if state.npc_hp <= 0:
            score -= WIN_SCORE
        return score

    # ------------------------------------------------------------------
    # 1) Minimax murni
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

        actions = state.legal_actions(is_maximizing)
        if not actions:
            self.evaluations += 1
            return self.evaluate_state(state), None

        if is_maximizing:
            best_score, best_action = -math.inf, None
            for action in actions:
                child = state.apply_action(True, action)
                score, _ = self.minimax(child, depth - 1, False)
                if score > best_score:
                    best_score, best_action = score, action
            return best_score, best_action

        best_score, best_action = math.inf, None
        for action in actions:
            child = state.apply_action(False, action)
            score, _ = self.minimax(child, depth - 1, True)
            if score < best_score:
                best_score, best_action = score, action
        return best_score, best_action

    # ------------------------------------------------------------------
    # 2) Alpha-Beta Pruning
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

        Args:
            state: State saat ini
            depth: Sisa kedalaman
            alpha: Batas bawah (best untuk MAX sejauh ini)
            beta: Batas atas (best untuk MIN sejauh ini)
            is_maximizing: True jika giliran NPC (MAX)

        Returns:
            Tuple (best_score, best_action)
        """
        self.nodes += 1

        if depth == 0 or state.is_terminal():
            self.evaluations += 1
            return self.evaluate_state(state), None

        actions = state.legal_actions(is_maximizing)
        if not actions:
            self.evaluations += 1
            return self.evaluate_state(state), None

        if is_maximizing:
            best_score, best_action = -math.inf, None
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

        best_score, best_action = math.inf, None
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
    # Analisis root (skor tiap aksi di depth 0, untuk overlay debug)
    # ------------------------------------------------------------------
    def _root_scores(
        self, state: BattleState, depth: int, use_alpha: bool
    ) -> List[Tuple[str, float]]:
        """Hitung skor tiap aksi legal di root (giliran NPC).

        Tiap anak dievaluasi dengan jendela penuh agar skor tiap cabang akurat,
        sehingga bisa ditampilkan pada debug overlay.

        Args:
            state: State root (giliran NPC)
            depth: Kedalaman pencarian
            use_alpha: True pakai alphabeta, False pakai minimax murni

        Returns:
            List pasangan (action, score) terurut dari skor tertinggi
        """
        results: List[Tuple[str, float]] = []
        for action in state.legal_actions(True):
            child = state.apply_action(True, action)
            if use_alpha:
                score, _ = self.alphabeta(child, depth - 1, -math.inf, math.inf, False)
            else:
                score, _ = self.minimax(child, depth - 1, False)
            results.append((action, score))
        results.sort(key=lambda item: item[1], reverse=True)
        return results

    # ------------------------------------------------------------------
    # Entry point: pilih aksi terbaik + kumpulkan statistik
    # ------------------------------------------------------------------
    def think(self, state: BattleState, depth: Optional[int] = None) -> Dict:
        """Tentukan aksi NPC terbaik dan kumpulkan metrik performa.

        Menjalankan minimax murni dan alpha-beta pada state yang sama agar
        jumlah node keduanya dapat dibandingkan pada debug overlay.

        Args:
            state: State saat giliran NPC
            depth: Override kedalaman pencarian (opsional)

        Returns:
            dict statistik (juga disimpan di self.last_stats)
        """
        depth = self.depth if depth is None else depth

        if state.is_terminal():
            self.last_stats = {
                "depth": depth,
                "best_action": None,
                "best_score": None,
                "root_scores": [],
                "minimax_nodes": 0,
                "alphabeta_nodes": 0,
                "pruned_nodes": 0,
                "prune_efficiency": 0.0,
                "evaluations": 0,
                "time_ms": 0.0,
            }
            return self.last_stats

        t0 = time.perf_counter()

        # --- Minimax murni (baseline node count) ---
        self.nodes = 0
        self.evaluations = 0
        minimax_scores = self._root_scores(state, depth, use_alpha=False)
        minimax_nodes = self.nodes
        minimax_eval = self.evaluations

        # --- Alpha-Beta (dipakai untuk keputusan) ---
        self.nodes = 0
        self.evaluations = 0
        self.prunes = 0
        alphabeta_scores = self._root_scores(state, depth, use_alpha=True)
        alphabeta_nodes = self.nodes
        alphabeta_eval = self.evaluations
        cutoffs = self.prunes

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        best_action = alphabeta_scores[0][0] if alphabeta_scores else None
        best_score = alphabeta_scores[0][1] if alphabeta_scores else None

        # Node yang berhasil dipotong = selisih node minimax murni vs alpha-beta
        pruned = max(0, minimax_nodes - alphabeta_nodes)
        prune_eff = 0.0
        if minimax_nodes > 0:
            prune_eff = pruned / minimax_nodes * 100.0

        self.last_stats = {
            "depth": depth,
            "best_action": best_action,
            "best_score": best_score,
            "root_scores": alphabeta_scores,
            "minimax_root_scores": minimax_scores,
            "minimax_nodes": minimax_nodes,
            "alphabeta_nodes": alphabeta_nodes,
            "pruned_nodes": pruned,
            "cutoffs": cutoffs,
            "prune_efficiency": prune_eff,
            "evaluations": alphabeta_eval,
            "minimax_evaluations": minimax_eval,
            "time_ms": elapsed_ms,
        }
        return self.last_stats
