"""
adversarial.py - ADVERSARIAL SEARCH: Minimax + Alpha-Beta Pruning

Turn-Based Boss Battle untuk AI LABYRINTH: THE DUNGEON OVERSEER.

Aksi Player (HANYA 3):
  [1] ATTACK : Serang musuh (18-24 DMG, rata-rata deterministik 21 untuk search)
  [2] POTION : Pulihkan 30 HP, mulai 3 buah, disabled bila habis (0)
  [3] DEFEND : Kurangi damage giliran lawan berikutnya sebesar 60%, efek hilang
               setelah giliran lawan selesai.

Aksi Boss:
  1. ATTACK       : 20-28 DMG (rata-rata deterministik 24 untuk search)
  2. HEAVY_ATTACK : 40 DMG (cooldown 3 giliran, player defend hanya kurangi 30%)
  3. DEFEND       : Kurangi damage dari player sebesar 50%
  4. HEAL         : Pulihkan 20 HP, maksimal 2x pakai

Evaluasi Minimax (sudut pandang BOSS):
  Score = (HP_Boss - HP_Hero)*2 + Boss_Defend_Val - Player_Defend_Val
          + Heavy_Readiness - Player_Potion_Threat + Boss_Heal_Count
"""

from dataclasses import dataclass, field
import time
import config


# ==============================================================================
# STATE PERTARUNGAN (Imutabel / Copyable)
# ==============================================================================
@dataclass
class BattleState:
    """Snapshot keadaan pertarungan (dapat di-clone untuk search tree)."""

    player_hp: int = config.HERO_MAX_HP
    player_max_hp: int = config.HERO_MAX_HP
    boss_hp: int = config.BOSS_MAX_HP
    boss_max_hp: int = config.BOSS_MAX_HP
    potion_count: int = config.HERO_INITIAL_POTIONS
    player_defending: bool = False
    boss_defending: bool = False
    boss_heavy_cd: int = 0
    boss_heal_count: int = config.BOSS_MAX_HEALS
    turn: str = "player"        # "player" atau "boss"
    turn_number: int = 1

    # Atribut bonus dari loadout perlengkapan CSP
    hero_attack_bonus: int = 0
    hero_defend_bonus: float = 0.0
    potion_heal_bonus: int = 0
    boss_weights: tuple = field(default_factory=lambda: tuple(config.BOSS_DEFAULT_WEIGHTS))
    loadout: dict = field(default_factory=dict)

    def clone(self):
        d = dict(self.__dict__)
        if "loadout" in d and isinstance(d["loadout"], dict):
            d["loadout"] = dict(d["loadout"])
        return BattleState(**d)

    # --- Property kompatibilitas dengan kode eksisting ---
    @property
    def hero_hp(self) -> int:
        return self.player_hp

    @hero_hp.setter
    def hero_hp(self, val: int):
        self.player_hp = val

    @property
    def hero_guard(self) -> bool:
        return self.player_defending

    @hero_guard.setter
    def hero_guard(self, val: bool):
        self.player_defending = val

    @property
    def boss_guard(self) -> bool:
        return self.boss_defending

    @boss_guard.setter
    def boss_guard(self, val: bool):
        self.boss_defending = val

    @property
    def round_no(self) -> int:
        return self.turn_number

    @round_no.setter
    def round_no(self, val: int):
        self.turn_number = val

    @property
    def hero_mana(self) -> int:
        return 0

    @property
    def hero_buff_turns(self) -> int:
        return 0

    @property
    def boss_buff(self) -> int:
        return 0

    @property
    def boss_raged(self) -> bool:
        return False

    @property
    def hero_guard_cd(self) -> int:
        return 0

    @property
    def boss_guard_cd(self) -> int:
        return self.boss_heavy_cd


# ==============================================================================
# GENERATOR AKSI
# ==============================================================================
HERO_SKILLS = {
    "ATTACK": {"desc": f"Attack  dmg {config.HERO_ATTACK_DMG[0]}-{config.HERO_ATTACK_DMG[1]} (avg 21)"},
    "POTION": {"desc": f"Potion  +{config.HERO_POTION_HEAL} HP (jumlah terbatas)"},
    "DEFEND": {"desc": f"Defend  blok {int(config.HERO_DEFEND_REDUCE * 100)}% damage giliran lawan"},
}

BOSS_SKILLS = {
    "ATTACK": {"desc": f"Boss Attack  dmg {config.BOSS_ATTACK_DMG[0]}-{config.BOSS_ATTACK_DMG[1]} (avg 24)"},
    "HEAVY_ATTACK": {"desc": f"Heavy Attack  dmg {config.BOSS_HEAVY_DMG} (cd 3 turns)"},
    "DEFEND": {"desc": f"Boss Defend  blok {int(config.BOSS_DEFEND_REDUCE * 100)}% damage player"},
    "HEAL": {"desc": f"Boss Heal  +{config.BOSS_HEAL_AMOUNT} HP (maks {config.BOSS_MAX_HEALS}x)"},
}

HERO_ACTIONS = ("ATTACK", "POTION", "DEFEND")
BOSS_ACTIONS = ("ATTACK", "HEAVY_ATTACK", "DEFEND", "HEAL")


def hero_actions(state: BattleState):
    """Aksi yang boleh dipilih player pada gilirannya (HANYA 3)."""
    acts = ["ATTACK"]
    if state.potion_count > 0:
        acts.append("POTION")
    acts.append("DEFEND")
    return acts


def boss_actions(state: BattleState):
    """Opsi aksi Boss yang dievaluasi Minimax + Alpha-Beta."""
    acts = ["ATTACK", "DEFEND"]
    if state.boss_heavy_cd <= 0:
        acts.append("HEAVY_ATTACK")
    if state.boss_heal_count > 0 and state.boss_hp < state.boss_max_hp:
        acts.append("HEAL")
    return acts


# ==============================================================================
# RESOLUSI AKSI & DETERMINISME
# ==============================================================================
def apply_action(state: BattleState, actor: str, action: str, rng=None):
    """
    Terapkan aksi ke state -> (state_baru, log_message).

    rng=None  -> damage deterministik rata-rata (digunakan oleh Minimax).
    rng=Random-> variasi acak +-10% (digunakan saat eksekusi permainan nyata).
    """
    s = state.clone()
    msg = ""

    if actor in ("hero", "player"):
        # Aksi player dieksekusi
        if action == "ATTACK":
            if rng is not None:
                raw_dmg = rng.randint(config.HERO_ATTACK_DMG[0], config.HERO_ATTACK_DMG[1])
            else:
                raw_dmg = config.HERO_ATTACK_EXPECTED
            raw_dmg += getattr(s, "hero_attack_bonus", 0)

            dmg = raw_dmg
            if s.boss_defending:
                dmg = max(1, int(raw_dmg * (1.0 - config.BOSS_DEFEND_REDUCE)))
                msg = f"Hero ATTACK -> Boss -{dmg} HP (Boss DEFEND menahan 50%!)"
            else:
                msg = f"Hero ATTACK -> Boss -{dmg} HP"

            s.boss_hp = max(0, s.boss_hp - dmg)

        elif action == "POTION":
            if s.potion_count > 0:
                s.potion_count -= 1
                heal_cap = config.HERO_POTION_HEAL + getattr(s, "potion_heal_bonus", 0)
                healed = min(heal_cap, s.player_max_hp - s.player_hp)
                s.player_hp = min(s.player_max_hp, s.player_hp + heal_cap)
                msg = f"Hero minum POTION -> Pulih +{healed} HP (Sisa: {s.potion_count})"
            else:
                msg = "Hero mencoba minum ramuan, tetapi POTION habis!"

        elif action == "DEFEND":
            s.player_defending = True
            red_pct = int((config.HERO_DEFEND_REDUCE + getattr(s, "hero_defend_bonus", 0.0)) * 100)
            msg = f"Hero DEFEND -> Menahan {red_pct}% damage giliran berikutnya!"

        # Boss defend hilang setelah giliran player selesai
        s.boss_defending = False
        s.turn = "boss"

    else:
        # Aksi Boss dieksekusi
        if s.boss_heavy_cd > 0:
            s.boss_heavy_cd -= 1

        if action == "ATTACK":
            if rng is not None:
                raw_dmg = rng.randint(config.BOSS_ATTACK_DMG[0], config.BOSS_ATTACK_DMG[1])
            else:
                raw_dmg = config.BOSS_ATTACK_EXPECTED

            dmg = raw_dmg
            if s.player_defending:
                defend_reduce = min(0.90, config.HERO_DEFEND_REDUCE + getattr(s, "hero_defend_bonus", 0.0))
                dmg = max(1, int(raw_dmg * (1.0 - defend_reduce)))
                msg = f"Boss ATTACK -> Hero -{dmg} HP (Hero DEFEND menahan {int(defend_reduce*100)}%!)"
            else:
                msg = f"Boss ATTACK -> Hero -{dmg} HP"

            s.player_hp = max(0, s.player_hp - dmg)

        elif action == "HEAVY_ATTACK":
            if rng is not None:
                # Variasi +-10% sekitar 40 (36-44)
                raw_dmg = rng.randint(int(config.BOSS_HEAVY_DMG * 0.9), int(config.BOSS_HEAVY_DMG * 1.1))
            else:
                raw_dmg = config.BOSS_HEAVY_DMG

            dmg = raw_dmg
            if s.player_defending:
                # Heavy attack tidak bisa diblok penuh, base 30% + setengah bonus defend
                heavy_reduce = min(0.60, config.BOSS_HEAVY_GUARD_REDUCE + getattr(s, "hero_defend_bonus", 0.0) * 0.5)
                dmg = max(1, int(raw_dmg * (1.0 - heavy_reduce)))
                msg = f"Boss HEAVY ATTACK! -> Hero -{dmg} HP (Hero DEFEND hanya tahan {int(heavy_reduce*100)}%!)"
            else:
                msg = f"Boss HEAVY ATTACK! -> Hero -{dmg} HP hantaman telak!"

            s.player_hp = max(0, s.player_hp - dmg)
            s.boss_heavy_cd = config.BOSS_HEAVY_CD

        elif action == "DEFEND":
            s.boss_defending = True
            msg = f"Boss DEFEND -> Bersiap menahan {int(config.BOSS_DEFEND_REDUCE * 100)}% damage serangan Hero!"

        elif action == "HEAL":
            if s.boss_heal_count > 0:
                s.boss_heal_count -= 1
                healed = min(config.BOSS_HEAL_AMOUNT, s.boss_max_hp - s.boss_hp)
                s.boss_hp = min(s.boss_max_hp, s.boss_hp + config.BOSS_HEAL_AMOUNT)
                msg = f"Boss HEAL -> Memulihkan +{healed} HP (Sisa heal: {s.boss_heal_count})"
            else:
                msg = "Boss mencoba menyembuhkan diri, namun energi habis!"

        # Player defend hilang setelah giliran boss selesai
        s.player_defending = False
        s.turn_number += 1
        s.turn = "player"

    return s, msg


def is_terminal(state: BattleState):
    """Battle selesai bila HP <= 0 atau batas ronde maksimal tercapai."""
    return (state.player_hp <= 0 or
            state.boss_hp <= 0 or
            state.turn_number > config.BATTLE_MAX_TURNS)


# ==============================================================================
# EVALUASI (Sudut Pandang BOSS - Maximizing)
# ==============================================================================
def evaluate(state: BattleState, weights=None, depth: int = 0):
    """
    Fungsi evaluasi heuristik Minimax dari perspektif BOSS.
    Nilai lebih tinggi = menguntungkan Boss.
    Nilai lebih rendah = menguntungkan Player.
    weights: tuple (w_hp, w_def, w_hvy, w_res)
    depth: sisa kedalaman pencarian untuk depth-penalty (kemenangan lebih cepat lebih baik,
           kekalahan lebih lama lebih baik untuk mencegah keputusasaan/blunder bunuh diri).
    """
    if state.boss_hp <= 0:
        return -config.EVAL_WIN_SCORE - depth
    if state.player_hp <= 0:
        return config.EVAL_WIN_SCORE + depth
    if state.turn_number > config.BATTLE_MAX_TURNS:
        b_pct = state.boss_hp / max(1, state.boss_max_hp)
        p_pct = state.player_hp / max(1, state.player_max_hp)
        if b_pct > p_pct:
            return config.EVAL_WIN_SCORE + depth
        elif p_pct > b_pct:
            return -config.EVAL_WIN_SCORE - depth
        return 0

    w = weights if weights is not None else getattr(state, "boss_weights", None) or config.BOSS_DEFAULT_WEIGHTS
    w_hp, w_def, w_hvy, w_res = w

    # Heuristik linear
    # 1. Selisih HP bernilai tinggi
    score = (state.boss_hp - state.player_hp) * float(w_hp)

    # 2. Defend aktif
    if state.boss_defending:
        score += float(w_def)
    if state.player_defending:
        score -= float(w_def) * 1.25

    # 3. Kesiapan Heavy Attack
    if state.boss_heavy_cd <= 0:
        score += float(w_hvy)
    else:
        score -= state.boss_heavy_cd * (float(w_hvy) / 4.0)

    # 4. Potions player yang tersisa (ancaman bagi boss)
    score -= state.potion_count * float(w_res)

    # 5. Sisa heal boss
    score += state.boss_heal_count * 5.0

    return int(score)


# ==============================================================================
# MINIMAX + ALPHA-BETA PRUNING
# ==============================================================================
@dataclass
class TreeNode:
    """Simpul pohon keputusan Minimax untuk inspeksi & debug."""
    label: str
    value: int = 0
    depth: int = 0
    alpha: int = -100000
    beta: int = 100000
    children: list = field(default_factory=list)
    pruned: int = 0
    order: int = 0


@dataclass
class SearchStats:
    """Statistik pencarian minimax lengkap untuk F3 panel."""
    nodes: int = 0
    pruned: int = 0
    depth: int = 0
    alpha: int = -100000
    beta: int = 100000
    best_value: int = 0
    best_action: str = "-"
    elapsed_ms: float = 0.0
    candidates: list = field(default_factory=list)


class MinimaxBattleAI:
    """
    AI Adversarial Boss: Minimax dengan Alpha-Beta Pruning,
    Move Ordering, dan Transposition Table (TT).
    """

    def __init__(self, depth=config.MINIMAX_DEPTH, weights=None, move_prior_provider=None,
                 use_tt: bool = False, use_ordering: bool = True):
        self.depth = depth
        self.weights = list(weights) if weights is not None else list(config.BOSS_DEFAULT_WEIGHTS)
        self.move_prior_provider = move_prior_provider
        self.use_tt = use_tt
        self.use_ordering = use_ordering
        self.tt = {}
        self.last_stats = SearchStats(depth=depth)
        self.last_tree = None
        self.last_root_children = []
        self.considered = []

    def set_weights(self, weights):
        self.weights = list(weights)

    def evaluate(self, state: BattleState, depth: int = 0):
        return evaluate(state, self.weights, depth=depth)

    def _state_key(self, state: BattleState, depth: int) -> tuple:
        return (
            state.player_hp,
            state.boss_hp,
            state.potion_count,
            state.player_defending,
            state.boss_defending,
            state.boss_heavy_cd,
            state.boss_heal_count,
            state.turn,
            depth
        )

    def minimax(self, state: BattleState, depth: int, alpha: int, beta: int,
                is_maximizing: bool, stats: SearchStats = None):
        if stats is None:
            stats = SearchStats(depth=depth)
        stats.nodes += 1

        key = self._state_key(state, depth)
        if self.use_tt and key in self.tt:
            c_val, c_flag = self.tt[key]
            if c_flag == "EXACT":
                return c_val, TreeNode("tt_leaf", c_val, depth, alpha, beta)
            elif c_flag == "LOWER" and c_val >= beta:
                return c_val, TreeNode("tt_leaf", c_val, depth, alpha, beta)
            elif c_flag == "UPPER" and c_val <= alpha:
                return c_val, TreeNode("tt_leaf", c_val, depth, alpha, beta)

        if depth == 0 or is_terminal(state):
            val = self.evaluate(state, depth=depth)
            if self.use_tt:
                self.tt[key] = (val, "EXACT")
            node = TreeNode("leaf", val, depth, alpha, beta)
            return val, node

        actor = "boss" if is_maximizing else "player"
        actions = list(boss_actions(state)) if is_maximizing else list(hero_actions(state))

        # Heuristic Move Ordering
        if self.use_ordering:
            if is_maximizing:
                # Prioritaskan Heavy Attack jika CD=0, lalu Attack biasa, Heal, dan Defend
                actions.sort(key=lambda a: 0 if a == "HEAVY_ATTACK" else (1 if a == "ATTACK" else (2 if a == "HEAL" else 3)))
            else:
                # Prioritaskan Potion jika HP kritis, lalu Attack, Defend
                actions.sort(key=lambda a: 0 if (a == "POTION" and state.player_hp <= 35) else (1 if a == "ATTACK" else 2))

        node = TreeNode(actor, 0, depth, alpha, beta)
        best = -100000 if is_maximizing else 100000
        orig_alpha, local_alpha, local_beta = alpha, alpha, beta

        for order, action in enumerate(actions):
            child, _ = apply_action(state, actor, action, rng=None)
            val, sub = self.minimax(child, depth - 1, local_alpha, local_beta,
                                    not is_maximizing, stats)
            sub.label = action
            sub.order = order
            node.children.append(sub)

            if is_maximizing:
                if val > best:
                    best = val
                local_alpha = max(local_alpha, val)
            else:
                if val < best:
                    best = val
                local_beta = min(local_beta, val)

            if local_beta <= local_alpha:
                # Pruning terjadi
                remaining = len(actions) - order - 1
                stats.pruned += remaining
                sub.pruned += remaining
                node.pruned += remaining
                break

        node.value = int(best)
        node.alpha = local_alpha
        node.beta = local_beta

        if self.use_tt:
            flag = "EXACT"
            if best <= orig_alpha:
                flag = "UPPER"
            elif best >= beta:
                flag = "LOWER"
            self.tt[key] = (node.value, flag)

        return node.value, node

    def choose_move(self, state: BattleState):
        """
        Pilih aksi terbaik untuk Boss dan simpan skor tiap kandidat aksi.
        Mendukung move ordering bila ada preferred action dari planner.
        """
        t0 = time.perf_counter()
        if self.use_tt:
            self.tt.clear()
        stats = SearchStats(depth=self.depth)
        best_action, best_value = None, -100000
        root = TreeNode("boss", 0, self.depth, -100000, 100000)
        candidates = []
        alpha, beta = -100000, 100000

        legal_acts = list(boss_actions(state))
        preferred = None
        if self.move_prior_provider is not None:
            if hasattr(self.move_prior_provider, "get_next_action"):
                preferred = self.move_prior_provider.get_next_action(state.turn_number)
            elif callable(self.move_prior_provider):
                preferred = self.move_prior_provider(state)
        if preferred and preferred in legal_acts:
            legal_acts.remove(preferred)
            legal_acts.insert(0, preferred)
        elif self.use_ordering:
            # Urutkan aksi boss: jika hero bertahan, prioritaskan HEAL/DEFEND daripada buang Heavy Attack
            if state.player_defending:
                legal_acts.sort(key=lambda a: 0 if (a == "HEAL" and state.boss_heal_count > 0 and state.boss_hp < state.boss_max_hp) else (1 if a == "DEFEND" else (2 if a == "ATTACK" else 3)))
            else:
                legal_acts.sort(key=lambda a: 0 if a == "HEAVY_ATTACK" else (1 if a == "ATTACK" else (2 if a == "HEAL" else 3)))

        for order, action in enumerate(legal_acts):
            child, _ = apply_action(state, "boss", action, rng=None)
            val, sub = self.minimax(child, self.depth - 1, alpha, beta, False, stats)
            sub.label = action
            sub.order = order
            root.children.append(sub)
            candidates.append({
                "action": action,
                "score": val,
                "alpha": sub.alpha,
                "beta": sub.beta,
                "chosen": False
            })
            if val > best_value:
                best_value, best_action = val, action
                alpha = max(alpha, val)

        for c in candidates:
            if c["action"] == best_action:
                c["chosen"] = True

        root.value = int(best_value)
        root.alpha = alpha
        root.beta = beta
        stats.alpha = alpha
        stats.beta = beta
        stats.best_value = int(best_value)
        stats.best_action = best_action or "ATTACK"
        stats.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        stats.candidates = candidates

        self.last_stats = stats
        self.last_tree = root
        self.last_root_children = [(c["action"], c["score"], c["alpha"], c["beta"]) for c in candidates]
        self.considered = self.last_root_children
        return best_action or "ATTACK", root, stats


BattleAI = MinimaxBattleAI


def pure_minimax_search(state: BattleState, depth: int, is_maximizing: bool = True, weights=None) -> tuple[int, int]:
    """
    Standard Minimax murni tanpa pruning alpha-beta (baseline benchmark).
    Mengembalikan (best_value, total_nodes_evaluated).
    """
    nodes = 1
    if depth == 0 or is_terminal(state):
        return evaluate(state, weights, depth=depth), nodes

    actor = "boss" if is_maximizing else "player"
    actions = list(boss_actions(state)) if is_maximizing else list(hero_actions(state))
    best = -100000 if is_maximizing else 100000

    for action in actions:
        child, _ = apply_action(state, actor, action, rng=None)
        val, sub_nodes = pure_minimax_search(child, depth - 1, not is_maximizing, weights)
        nodes += sub_nodes
        if is_maximizing:
            best = max(best, val)
        else:
            best = min(best, val)

    return int(best), nodes


def pure_minimax_root(state: BattleState, depth: int, weights=None, use_ordering: bool = True) -> tuple[str, int, int]:
    """
    Standard Minimax murni pada root node (memilih aksi boss terbaik).
    Mengembalikan (best_action, best_value, total_nodes_evaluated).
    Digunakan untuk verifikasi bahwa Alpha-Beta menghasilkan move dan nilai identik 100%.
    """
    legal_acts = list(boss_actions(state))
    if use_ordering:
        if state.player_defending:
            legal_acts.sort(key=lambda a: 0 if (a == "HEAL" and state.boss_heal_count > 0 and state.boss_hp < state.boss_max_hp) else (1 if a == "DEFEND" else (2 if a == "ATTACK" else 3)))
        else:
            legal_acts.sort(key=lambda a: 0 if a == "HEAVY_ATTACK" else (1 if a == "ATTACK" else (2 if a == "HEAL" else 3)))
    best_action = legal_acts[0] if legal_acts else "ATTACK"
    best_val = -100000
    total_nodes = 1

    for act in legal_acts:
        child, _ = apply_action(state, "boss", act, rng=None)
        val, nodes = pure_minimax_search(child, depth - 1, False, weights)
        total_nodes += nodes
        if val > best_val:
            best_val = val
            best_action = act

    return best_action, int(best_val), total_nodes


def minimax(state, depth, alpha, beta, is_maximizing, stats=None, ai=None):
    engine = ai or MinimaxBattleAI(depth)
    return engine.minimax(state, depth, alpha, beta, is_maximizing, stats)
