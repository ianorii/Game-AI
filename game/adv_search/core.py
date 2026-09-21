"""
Adversarial Search module - Battle system dengan Min-Max & Alpha-Beta Pruning.

Fitur:
- Turn-based battle: Player vs NPC
- 3 aksi: Attack, Defend, Potion
- NPC menggunakan Min-Max dengan Alpha-Beta Pruning untuk memilih aksi
- Eval function: npc_hp - player_hp (NPC maximize, Player minimize)
"""
import math
import random
from copy import deepcopy


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTIONS = ("attack", "defend", "potion")

# Default stats
DEFAULT_PLAYER_STATS = {
    "hp": 100,
    "max_hp": 100,
    "atk": 12,
    "def": 5,
    "potions": 3,
    "heal_amount": 30,
}

DEFAULT_NPC_STATS = {
    "hp": 100,
    "max_hp": 100,
    "atk": 10,
    "def": 5,
    "potions": 3,
    "heal_amount": 30,
}

# Search settings
MAX_DEPTH = 5
DEFEND_MULTIPLIER = 0.5


# ---------------------------------------------------------------------------
# Game State
# ---------------------------------------------------------------------------

class GameState:
    """State untuk pertarungan turn-based.

    Attributes:
        player_hp, player_atk, player_def, player_potions: Stats player
        npc_hp, npc_atk, npc_def, npc_potions: Stats NPC
        whose_turn: "player" atau "npc"
        turn: Nomor turn saat ini
        log: List aksi yang terjadi di turn ini
        finished: Apakah battle sudah selesai
        winner: "player", "npc", atau None
    """

    def __init__(self, player_stats=None, npc_stats=None):
        p = player_stats or DEFAULT_PLAYER_STATS
        n = npc_stats or DEFAULT_NPC_STATS

        self.player_hp = p["hp"]
        self.player_max_hp = p["max_hp"]
        self.player_atk = p["atk"]
        self.player_def = p["def"]
        self.player_potions = p["potions"]
        self.player_heal = p.get("heal_amount", 30)
        self.player_defending = False

        self.npc_hp = n["hp"]
        self.npc_max_hp = n["max_hp"]
        self.npc_atk = n["atk"]
        self.npc_def = n["def"]
        self.npc_potions = n["potions"]
        self.npc_heal = n.get("heal_amount", 25)
        self.npc_defending = False

        self.whose_turn = "player"
        self.turn = 1
        self.log = []
        self.finished = False
        self.winner = None

    def clone(self):
        """Deep copy state untuk tree search."""
        return deepcopy(self)

    def get_legal_actions(self, who=None):
        """Return list aksi yang tersedia untuk player/NPC.

        Args:
            who: "player" atau "npc". Jika None, gunakan whose_turn.

        Returns:
            List of action strings
        """
        who = who or self.whose_turn
        actions = ["attack", "defend"]
        if getattr(self, f"{who}_potions") > 0:
            actions.append("potion")
        return actions

    def apply_action(self, actor, action, use_random=True):
        """Terapkan aksi dan resolve damage.

        Args:
            actor: "player" atau "npc"
            action: "attack", "defend", atau "potion"
            use_random: True untuk damage random, False untuk fixed (Min-Max search)

        Returns:
            Dict info hasil aksi
        """
        result = {"actor": actor, "action": action, "damage": 0, "heal": 0}

        opponent = "npc" if actor == "player" else "player"
        opp_def = getattr(self, f"{opponent}_def")
        is_defending = getattr(self, f"{opponent}_defending", False)

        if action == "attack":
            # Hitung damage: random 10-15
            damage = random.randint(10, 15) if use_random else 12

            # Kurangi damage jika lawan defending
            if is_defending:
                damage = max(1, damage // 2)

            new_hp = max(0, getattr(self, f"{opponent}_hp") - damage)
            setattr(self, f"{opponent}_hp", new_hp)
            result["damage"] = damage

        elif action == "defend":
            setattr(self, f"{actor}_defending", True)
            result["message"] = f"{actor} defends!"

        elif action == "potion":
            heal = getattr(self, f"{actor}_heal")
            current_hp = getattr(self, f"{actor}_hp")
            max_hp = getattr(self, f"{actor}_max_hp")
            new_hp = min(max_hp, current_hp + heal)
            setattr(self, f"{actor}_hp", new_hp)
            setattr(self, f"{actor}_potions", getattr(self, f"{actor}_potions") - 1)
            result["heal"] = new_hp - current_hp

        # Reset defending status setelah resolve
        setattr(self, f"{actor}_defending", False)

        # Cek win/lose
        if self.player_hp <= 0:
            self.finished = True
            self.winner = "npc"
        elif self.npc_hp <= 0:
            self.finished = True
            self.winner = "player"

        self.log.append(result)
        return result

    def next_turn(self):
        """Ganti giliran ke lawan."""
        self.whose_turn = "npc" if self.whose_turn == "player" else "player"
        if self.whose_turn == "player":
            self.turn += 1


# ---------------------------------------------------------------------------
# Evaluation Function
# ---------------------------------------------------------------------------

def evaluate(state):
    """Eval function untuk Min-Max.

    NPC maximize, Player minimize.
    Nilai positif = NPC unggul, negatif = Player unggul.

    Args:
        state: GameState saat ini

    Returns:
        float: Score evaluasi
    """
    if state.winner == "npc":
        return 1000 + state.npc_hp
    if state.winner == "player":
        return -1000 - state.player_hp

    # Selisih HP sebagai dasar evaluasi
    hp_diff = state.npc_hp - state.player_hp

    # Bonus untuk potion tersisa
    potion_bonus = (state.npc_potions - state.player_potions) * 3

    # Bonus untuk defending status
    defend_bonus = 5 if state.npc_defending else 0

    return hp_diff + potion_bonus + defend_bonus


# ---------------------------------------------------------------------------
# Min-Max with Alpha-Beta Pruning
# ---------------------------------------------------------------------------

def minimax(state, depth, is_npc_turn, alpha=-math.inf, beta=math.inf):
    """Min-Max dengan Alpha-Beta Pruning.

    Args:
        state: GameState saat ini
        depth: Sisa depth search
        is_npc_turn: True jika giliran NPC (maximize)
        alpha: Alpha value untuk pruning
        beta: Beta value untuk pruning

    Returns:
        Tuple (score, best_action)
    """
    # Base case: battle selesai atau depth habis
    if state.finished or depth == 0:
        return evaluate(state), None

    legal_actions = state.get_legal_actions()

    if is_npc_turn:
        # NPC maximize
        max_score = -math.inf
        best_action = legal_actions[0]

        for action in legal_actions:
            child = state.clone()
            child.apply_action("npc", action, use_random=False)
            child.next_turn()
            score, _ = minimax(child, depth - 1, False, alpha, beta)

            if score > max_score:
                max_score = score
                best_action = action

            alpha = max(alpha, score)
            if beta <= alpha:
                break  # Beta pruning

        return max_score, best_action
    else:
        # Player minimize (asumsi player optimal)
        min_score = math.inf
        best_action = legal_actions[0]

        for action in legal_actions:
            child = state.clone()
            child.apply_action("player", action, use_random=False)
            child.next_turn()
            score, _ = minimax(child, depth - 1, True, alpha, beta)

            if score < min_score:
                min_score = score
                best_action = action

            beta = min(beta, score)
            if beta <= alpha:
                break  # Alpha pruning

        return min_score, best_action


def get_npc_action(state):
    """Hitung aksi terbaik NPC menggunakan Min-Max.

    Args:
        state: GameState saat ini

    Returns:
        Tuple (best_action, score)
    """
    score, action = minimax(state, MAX_DEPTH, is_npc_turn=True)
    return action, score


# ---------------------------------------------------------------------------
# Helper: Buat GameState dari Player & NPC objects
# ---------------------------------------------------------------------------

def create_battle_state(player, npc):
    """Buat GameState dari objek Player dan NPC.

    Args:
        player: Objek Player dengan battle stats
        npc: Objek NPC dengan battle stats

    Returns:
        GameState yang siap digunakan
    """
    return GameState(
        player_stats={
            "hp": player.battle_hp,
            "max_hp": player.battle_max_hp,
            "atk": player.battle_atk,
            "def": player.battle_def,
            "potions": player.battle_potions,
            "heal_amount": player.battle_heal,
        },
        npc_stats={
            "hp": npc.battle_hp,
            "max_hp": npc.battle_max_hp,
            "atk": npc.battle_atk,
            "def": npc.battle_def,
            "potions": npc.battle_potions,
            "heal_amount": npc.battle_heal,
        },
    )
