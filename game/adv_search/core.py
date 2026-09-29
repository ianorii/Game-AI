"""
Adversarial Search module - Battle system dengan Min-Max & Alpha-Beta Pruning.

Modul ini berisi "otak" pertarungan turn-based. Tidak ada kode rendering di
sini, sehingga bisa diuji secara terpisah dari pygame.

Isi modul:
1. GameState      : model state battle (HP, status, giliran, hasil)
2. evaluate()     : evaluation function dari perspektif satu pihak
3. minimax()      : Min-Max dengan Alpha-Beta Pruning + move ordering
4. iterative deepening + time budget (aman terhadap frame hitches)
5. search_best_move() : root search yang mengembalikan aksi, skor,
                        statistik pencarian, dan principal variation

Konsep Taktis (Rock-Paper-Scissors ringan):
    ATTACK > DEFEND  -> musuh yang defend kehilangan giliran menyerang
    DEFEND  > CHARGE -> guard membatalkan mayoritas damage serangan bertenaga
    CHARGE  > ATTACK -> kalau musuh tidak guard, damage x2.4 menghancurkan

Status (di-reset saat pemiliknya beraksi sendiri):
    guard   : serangan berikutnya masuk hanya 40% damage
    open    : serangan berikutnya masuk 150% damage (akibat potion)
    charged : serangan berikutnya damage x2.4 (akibat charge)

Karena pemain selalu bergerak duluan di tiap ronde, aturan "status bertahan
sampai pemiliknya beraksi lagi" membuat semua pihak mendapat hukuman/keuntungan
yang sama: tepat satu serangan.
"""
import copy
import math
import random
import time


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Urutan aksi dipakai untuk tombol UI (1/2/3/4) dan shortcut keyboard
ACTIONS = ("attack", "defend", "potion", "charge")

# Label & warna aksi (dipakai UI battle)
ACTION_INFO = {
    "attack": {"label": "ATTACK", "hotkey": "1", "color": (220, 70, 60)},
    "defend": {"label": "DEFEND", "hotkey": "2", "color": (60, 140, 230)},
    "potion": {"label": "POTION", "hotkey": "3", "color": (160, 80, 220)},
    "charge": {"label": "CHARGE", "hotkey": "4", "color": (230, 170, 50)},
}

# Variasi damage +-10% supaya pertarungan tidak terlalu deterministik
VARIANCE = 0.10

# Pengali status
GUARD_MULT = 0.40    # guard  -> damage masuk 40% (turun 60%)
OPEN_MULT = 1.80     # open   -> damage masuk 180% (harga yang wajar untuk heal)
CHARGE_MULT = 2.40   # charged-> damage keluar x2.4

# DEF stat memotong damage secara flat (murah tapi tetap terasa)
DEF_FACTOR = 0.40

# Nilai terminal saat ada pihak yang mati (jauh lebih besar dari eval biasa)
TERMINAL = 100000.0

# Perbedaan skor yang masih dianggap "seri" -> diacak agar AI tidak monoton
TIE_EPSILON = 0.75

# Default pencarian
DEFAULT_MAX_DEPTH = 4
TIME_BUDGET = 0.15  # detik per giliran AI (iterative deepening berhenti di sini)

# Bobot evaluation function default (bisa dioverride per arketipe musuh)
DEFAULT_WEIGHTS = {
    "hp": 1.0,         # selisih rasio HP
    "potion": 1.0,     # ekonomi potion
    "lethal": 1.0,     # kesadaran "bisa kill satu pukulan"
    "initiative": 1.0, # keuntungan giliran
    "guard": 1.0,      # nilai status guard
    "charge": 1.0,     # nilai status charged
    "open": 1.0,       # risiko status open
}

# Nilai status untuk evaluation function (dari sudut pandang pemiliknya).
# Disetarakan dengan swing damage aktual agar AI tidak over/under value:
#   guard   ~ damage yang diblokir        (0.6 x serangan normal)
#   open    ~ damage tambahan yang diterima (0.8 x serangan normal)
#   charged ~ damage tambahan saat dibelanjakan (x2.4 - 1.0, didiskon)
CHARGE_VALUE = 10.0
GUARD_VALUE = 6.0
OPEN_VALUE = -11.0

# Nilai ekonomis satu potion (resource langka, dipakai lintas battle)
POTION_VALUE = 15.0

# Default stats pemain (lebih kuat dari 1 arketipe musuh karena pemain
# membawa HP & potion antar battle, sedangkan musuh datang segar tiap wave)
DEFAULT_PLAYER_STATS = {
    "hp": 105,
    "max_hp": 105,
    "atk": 14,
    "def": 6,
    "potions": 3,
    "heal_amount": 40,
}

DEFAULT_NPC_STATS = {
    "hp": 100,
    "max_hp": 100,
    "atk": 13,
    "def": 5,
    "potions": 2,
    "heal_amount": 35,
}


# ---------------------------------------------------------------------------
# Arketipe Musuh
# ---------------------------------------------------------------------------

# Tiap arketipe punya stat berbeda + bobot eval berbeda sehingga gaya
# bertarungnya terasa berbeda: ada yang agresif, ada yang suka bertahan,
# ada yang hemat potion, ada yang gemar menghukum.
ARCHETYPES = {
    "brute": {
        "name": "Brute",
        "hp": 105, "atk": 14, "def": 4, "potions": 1, "heal": 30,
        "weights": {
            "hp": 1.1, "potion": 0.5, "lethal": 1.5, "initiative": 1.3,
            "guard": 0.6, "charge": 1.2, "open": 1.0,
        },
    },
    "guardian": {
        "name": "Penjaga Batu",
        "hp": 125, "atk": 10, "def": 8, "potions": 2, "heal": 30,
        "weights": {
            "hp": 1.0, "potion": 1.2, "lethal": 0.8, "initiative": 0.7,
            "guard": 1.6, "charge": 0.7, "open": 1.2,
        },
    },
    # heal 35: diukur lewat simulasi, heal >= 37 membuat Alkemis tak
    # terkalahkan (out-sustain pemain), heal <= 34 terlalu mudah dikalahkan
    "alchemist": {
        "name": "Alkemis Liar",
        "hp": 85, "atk": 11, "def": 5, "potions": 4, "heal": 35,
        "weights": {
            "hp": 1.4, "potion": 0.7, "lethal": 0.7, "initiative": 0.8,
            "guard": 0.9, "charge": 0.8, "open": 0.6,
        },
    },
    "assassin": {
        "name": "Bayangan",
        "hp": 80, "atk": 15, "def": 3, "potions": 1, "heal": 25,
        "weights": {
            "hp": 1.2, "potion": 0.6, "lethal": 1.8, "initiative": 1.4,
            "guard": 0.7, "charge": 1.4, "open": 1.5,
        },
    },
}

# Scaling level ancaman (wave) - sengaja dibuat lembut karena kekuatan musuh
# punya threshold tajam (1 poin ATK/DEF bisa mengubah jumlah ronde kill).
# HP +4/wave, ATK +1 tiap 3 wave, DEF +1 tiap 6 wave, dengan cap.
THREAT_HP_BONUS = 4
THREAT_ATK_STEP = 3
THREAT_DEF_STEP = 6
THREAT_MAX = 6


def make_enemy_stats(archetype, threat=0):
    """Bangun stat musuh dari arketipe, diskalakan dengan level ancaman.

    Args:
        archetype: key di ARCHETYPES
        threat: jumlah pemain yang sudah dikalahkan (wave berikutnya)

    Returns:
        Dict stats siap pakai GameState
    """
    a = ARCHETYPES[archetype]
    t = min(THREAT_MAX, max(0, threat))
    hp = a["hp"] + t * THREAT_HP_BONUS
    return {
        "hp": hp,
        "max_hp": hp,
        "atk": a["atk"] + t // THREAT_ATK_STEP,
        "def": a["def"] + t // THREAT_DEF_STEP,
        "potions": a["potions"],
        "heal_amount": a["heal"],
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _opp(who):
    """Return lawan dari 'player' atau 'npc'."""
    return "npc" if who == "player" else "player"


class SearchStats:
    """Statistik pencarian Min-Max (ditampilkan di UI battle).

    Attributes:
        nodes: jumlah state yang dievaluasi
        pruned: jumlah cabang yang dipotong alpha-beta
        max_depth: depth yang benar-benar selesai
        ms: waktu pencarian dalam milidetik
        role: sisi yang dimaksimalkan saat pencarian ("npc"/"player")
        action: aksi terbaik yang dipilih
        score: skor aksi terbaik (perspektif role)
        root_scores: skor tiap aksi di root (perspektif role)
        line: principal variation [(actor, action), ...]
        terms: rincian evaluation function (perspektif npc)
    """

    __slots__ = (
        "nodes", "pruned", "max_depth", "ms",
        "role", "action", "score", "root_scores", "line", "terms",
    )

    def __init__(self):
        self.nodes = 0        # jumlah state yang dievaluasi
        self.pruned = 0       # jumlah cabang yang dipotong alpha-beta
        self.max_depth = 0    # depth yang benar-benar selesai
        self.ms = 0.0         # waktu pencarian dalam milidetik
        self.role = "npc"     # sisi yang dimaksimalkan
        self.action = None    # aksi terpilih
        self.score = 0.0      # skor aksi terpilih (perspektif role)
        self.root_scores = {} # skor per aksi di root (perspektif role)
        self.line = []        # principal variation
        self.terms = {}       # rincian eval (perspektif npc)

    def as_dict(self):
        return {
            "nodes": self.nodes,
            "pruned": self.pruned,
            "depth": self.max_depth,
            "ms": self.ms,
            "role": self.role,
            "action": self.action,
            "score": self.score,
            "root_scores": dict(self.root_scores),
            "line": list(self.line),
            "terms": dict(self.terms),
        }

    def scores_npc_view(self):
        """Skor per aksi root dari perspektif NPC (untuk visualisasi).

        Returns:
            Dict {aksi: skor npc-view}
        """
        sign = 1.0 if self.role == "npc" else -1.0
        return {a: s * sign for a, s in self.root_scores.items()}


# ---------------------------------------------------------------------------
# Game State
# ---------------------------------------------------------------------------

class GameState:
    """State untuk pertarungan turn-based.

    Attributes:
        player_hp/max_hp/atk/def/potions/heal: Stat pemain
        player_guard/player_open/player_charged: Status pemain
        npc_*: Analog untuk musuh
        whose_turn: "player" atau "npc"
        turn: Nomor ronde
        w: Bobot evaluation function untuk sisi musuh
        finished/winner: Hasil pertarungan
    """

    def __init__(self, player_stats=None, npc_stats=None, npc_weights=None):
        p = player_stats or DEFAULT_PLAYER_STATS
        n = npc_stats or DEFAULT_NPC_STATS

        self.player_hp = float(p["hp"])
        self.player_max_hp = float(p["max_hp"])
        self.player_atk = int(p["atk"])
        self.player_def = int(p["def"])
        self.player_potions = int(p["potions"])
        self.player_heal = int(p.get("heal_amount", 40))
        self.player_guard = False
        self.player_open = False
        self.player_charged = False

        self.npc_hp = float(n["hp"])
        self.npc_max_hp = float(n["max_hp"])
        self.npc_atk = int(n["atk"])
        self.npc_def = int(n["def"])
        self.npc_potions = int(n["potions"])
        self.npc_heal = int(n.get("heal_amount", 30))
        self.npc_guard = False
        self.npc_open = False
        self.npc_charged = False

        self.whose_turn = "player"
        self.turn = 1

        self.finished = False
        self.winner = None

        # Bobot eval untuk musuh (personality per arketipe)
        self.w = dict(DEFAULT_WEIGHTS)
        if npc_weights:
            self.w.update(npc_weights)

        # Kedalaman pencarian yang diminta (dipakai UI)
        self.max_depth = DEFAULT_MAX_DEPTH

    def clone(self):
        """Salinan state untuk tree search.

        Semua field berupa skalar sehingga shallow copy sudah aman (dan jauh
        lebih cepat daripada deepcopy saat membentuk ribuan node).
        """
        return copy.copy(self)

    # -- aksi ---------------------------------------------------------------

    def get_legal_actions(self, who=None):
        """Return daftar aksi yang legal untuk 'who'.

        Potion hanya muncul kalau masih ada, charge hanya muncul kalau
        belum charged (mencegah aksi sia-sia memperbesar branching factor).

        Args:
            who: "player"/"npc". Default: giliran saat ini.

        Returns:
            List of action string sesuai urutan ACTIONS
        """
        who = who or self.whose_turn
        potions = getattr(self, f"{who}_potions")
        charged = getattr(self, f"{who}_charged")
        out = []
        for action in ACTIONS:
            if action == "potion" and potions <= 0:
                continue
            if action == "charge" and charged:
                continue
            out.append(action)
        return out

    def compute_damage(self, actor, target, charged=False, roll=1.0, use_status=True):
        """Hitung damage deterministik dari actor ke target.

        Rumus:
            base  = max(1, atk * roll - target_def * DEF_FACTOR)
            base *= CHARGE_MULT jika actor charged
            base *= GUARD_MULT  jika target guard
            base *= OPEN_MULT   jika target open

        Args:
            actor: "player" atau "npc"
            target: lawan
            charged: True jika serangan ini memakai bonus charge
            roll: faktor variasi (1.0 = damage rata-rata)
            use_status: True untuk menghitung guard/open target

        Returns:
            float damage
        """
        atk = getattr(self, f"{actor}_atk")
        dfn = getattr(self, f"{target}_def")
        dmg = max(1.0, atk * roll - dfn * DEF_FACTOR)
        if charged:
            dmg *= CHARGE_MULT
        if use_status:
            if getattr(self, f"{target}_guard"):
                dmg *= GUARD_MULT
            if getattr(self, f"{target}_open"):
                dmg *= OPEN_MULT
        return dmg

    def apply_action(self, actor, action, use_random=True):
        """Terapkan aksi dan resolve efeknya.

        Urutan resolusi penting untuk konsistensi giliran:
        1. Status lama milik actor dibersihkan (dia baru saja beraksi)
        2. Efek aksi diterapkan
        3. Cek kemenangan

        Args:
            actor: "player" atau "npc"
            action: "attack"/"defend"/"potion"/"charge"
            use_random: True = damage variatif (nyata), False = deterministik
                        (dipakai di dalam Min-Max supaya pohon stabil)

        Returns:
            Dict info hasil aksi untuk UI/log
        """
        target = _opp(actor)
        res = {
            "actor": actor,
            "action": action,
            "damage": 0,
            "heal": 0,
            "blocked": False,
            "bonus": False,
            "killed": False,
        }

        # 1) Status lama habis saat pemiliknya mengambil giliran
        was_charged = getattr(self, f"{actor}_charged")
        guard_status = getattr(self, f"{target}_guard")
        setattr(self, f"{actor}_guard", False)
        setattr(self, f"{actor}_open", False)
        setattr(self, f"{actor}_charged", False)

        if action == "attack":
            roll = random.uniform(1 - VARIANCE, 1 + VARIANCE) if use_random else 1.0
            dmg = self.compute_damage(
                actor, target, charged=was_charged, roll=roll
            )
            res["bonus"] = was_charged
            res["blocked"] = guard_status
            dmg = max(1, int(round(dmg)))
            res["damage"] = dmg

            new_hp = max(0.0, getattr(self, f"{target}_hp") - dmg)
            setattr(self, f"{target}_hp", new_hp)

            # Guard menahan tepat satu serangan
            if guard_status:
                setattr(self, f"{target}_guard", False)

            if new_hp <= 0:
                self.finished = True
                self.winner = actor
                res["killed"] = True

        elif action == "defend":
            setattr(self, f"{actor}_guard", True)

        elif action == "potion":
            hp = getattr(self, f"{actor}_hp")
            max_hp = getattr(self, f"{actor}_max_hp")
            heal = min(getattr(self, f"{actor}_heal"), max_hp - hp)
            setattr(self, f"{actor}_hp", hp + heal)
            setattr(self, f"{actor}_potions", getattr(self, f"{actor}_potions") - 1)
            # Meminum potion membuatmu terbuka sampai giliranmu berikutnya
            setattr(self, f"{actor}_open", True)
            res["heal"] = int(round(heal))

        elif action == "charge":
            setattr(self, f"{actor}_charged", True)

        return res

    def next_turn(self):
        """Ganti giliran; ronde bertambah saat kembali ke pemain."""
        self.whose_turn = _opp(self.whose_turn)
        if self.whose_turn == "player":
            self.turn += 1

    # -- evaluasi pendukung -------------------------------------------------

    def burst(self, actor):
        """Damage maksimum yang bisa dikeluarkan 'actor' pada gilirannya."""
        return self.compute_damage(
            actor, _opp(actor), charged=getattr(self, f"{actor}_charged")
        )


# ---------------------------------------------------------------------------
# Evaluation Function
# ---------------------------------------------------------------------------

def _flag_value(state, who, flag, value, weight):
    """Nilai satu flag status milik 'who' (0 jika flag tidak aktif)."""
    return value * weight if getattr(state, f"{who}_{flag}") else 0.0


def _status_value(state, who, weights=None):
    """Nilai status milik 'who' (positif = menguntungkan pemiliknya).

    Args:
        state: GameState
        who: "player" atau "npc"
        weights: dict bobot eval (untuk personalitas tiap arketipe)

    Returns:
        float nilai status
    """
    w = weights or state.w
    return (
        _flag_value(state, who, "charged", CHARGE_VALUE, w["charge"])
        + _flag_value(state, who, "guard", GUARD_VALUE, w["guard"])
        + _flag_value(state, who, "open", OPEN_VALUE, w["open"])
    )


def evaluate_terms(state):
    """Rincian evaluation function per komponen (perspektif NPC).

    Dipakai untuk menampilkan "kenapa AI memilih aksi X" di debug overlay:
    tiap komponen skor terlihat terpisah (HP, lethal, potion, status, giliran).

    Args:
        state: GameState

    Returns:
        Dict {nama_komponen: kontribusi skor} (perspektif npc, tanpa bagian
        terminal - bagian terminal ditangani oleh _evaluate_npc_view)
    """
    w = state.w
    terms = {}

    # 1. Selisih HP ternormalisasi (0..1 per pihak -> skala 0..100)
    terms["hp"] = w["hp"] * (
        state.npc_hp / max(1.0, state.npc_max_hp)
        - state.player_hp / max(1.0, state.player_max_hp)
    ) * 100.0

    # 2. Kesadaran lethal window (bisa kill / bisa dikill satu pukulan)
    lethal = 0.0
    npc_burst = state.burst("npc")
    player_burst = state.burst("player")
    if npc_burst >= state.player_hp:
        lethal += w["lethal"] * 50.0
    elif npc_burst >= state.player_hp * 0.5:
        lethal += w["lethal"] * 8.0
    if player_burst >= state.npc_hp:
        lethal -= w["lethal"] * 50.0
    elif player_burst >= state.npc_hp * 0.5:
        lethal -= w["lethal"] * 8.0
    terms["lethal"] = lethal

    # 3. Ekonomi potion (resource langka yang dibawa antar battle)
    terms["potion"] = (
        w["potion"] * (state.npc_potions - state.player_potions) * POTION_VALUE
    )

    # 4. Nilai status (dipisah per flag supaya jelas di panel debug)
    terms["charge"] = (
        _flag_value(state, "npc", "charged", CHARGE_VALUE, w["charge"])
        - _flag_value(state, "player", "charged", CHARGE_VALUE, w["charge"])
    )
    terms["guard"] = (
        _flag_value(state, "npc", "guard", GUARD_VALUE, w["guard"])
        - _flag_value(state, "player", "guard", GUARD_VALUE, w["guard"])
    )
    terms["open"] = (
        _flag_value(state, "npc", "open", OPEN_VALUE, w["open"])
        - _flag_value(state, "player", "open", OPEN_VALUE, w["open"])
    )

    # 5. Keuntungan giliran berikutnya
    terms["initiative"] = (
        w["initiative"] * (3.0 if state.whose_turn == "npc" else -3.0)
    )
    return terms


def _evaluate_npc_view(state):
    """Evaluation function dari perspektif musuh (npc)."""
    # Terminal
    if state.winner == "npc":
        return TERMINAL + (state.npc_hp / max(1.0, state.npc_max_hp)) * 100.0
    if state.winner == "player":
        return -TERMINAL - (state.player_hp / max(1.0, state.player_max_hp)) * 100.0
    return sum(evaluate_terms(state).values())


# Skala konversi skor eval -> peluang menang (fungsi logistik)
PROB_SCALE = 60.0


def win_probability(score, perspective="npc"):
    """Konversi skor evaluation menjadi ESTIMASI peluang menang (0-100).

    Penting: ini estimasi heuristik (fungsi logistik), bukan probabilitas
    pasti. Skor 0 = 50:50, skor +100 (unggul HP penuh) = ~92%. Dipakai
    oleh debug overlay untuk memvisualkan seberapa yakin pencarian.

    Args:
        score: skor evaluation
        perspective: "npc" atau "player" (sisi yang dimaksimalkan)

    Returns:
        float peluang menang 0..100 dari sudut pandang 'perspective'
    """
    s = score if perspective == "npc" else -score
    if s >= TERMINAL:
        return 100.0
    if s <= -TERMINAL:
        return 0.0
    return 100.0 / (1.0 + math.exp(-s / PROB_SCALE))


def evaluate(state, role="npc"):
    """Evaluation function untuk Min-Max.

    Args:
        state: GameState saat ini
        role: sisi yang MENGMAKSIMALKAN ("npc" atau "player").
              Nilai selalu dikembalikan dari perspektif 'role'.

    Returns:
        float: skor evaluasi
    """
    val = _evaluate_npc_view(state)
    return val if role == "npc" else -val


# ---------------------------------------------------------------------------
# Min-Max dengan Alpha-Beta Pruning
# ---------------------------------------------------------------------------

def _order_actions(state, actor, actions):
    """Move ordering: aksi yang langsung membunuh diprioritaskan.

    Ordering yang baik membuat alpha-beta memangkas jauh lebih banyak node.

    Args:
        state: GameState
        actor: pihak yang beraksi
        actions: daftar aksi legal

    Returns:
        List aksi terurut
    """

    def key(action):
        if action == "attack":
            target = _opp(actor)
            lethal = state.compute_damage(
                actor, target, charged=getattr(state, f"{actor}_charged")
            ) >= getattr(state, f"{target}_hp")
            return 0 if lethal else 1
        return {"charge": 2, "defend": 3, "potion": 4}.get(action, 5)

    return sorted(actions, key=key)


def minimax(state, depth, is_max, role, alpha, beta, stats):
    """Min-Max dengan Alpha-Beta Pruning.

    Args:
        state: GameState saat ini
        depth: sisa kedalaman pencarian
        is_max: True jika giliran sisi 'role' (maximize)
        role: sisi yang dimaksimalkan ("npc" untuk AI, "player" untuk hint)
        alpha/beta: nilai pruning
        stats: SearchStats yang diisi in-place

    Returns:
        Tuple (score, line) di mana line adalah principal variation
        berupa list of (actor, action)
    """
    stats.nodes += 1

    if state.finished or depth <= 0:
        return evaluate(state, role), []

    actor = role if is_max else _opp(role)
    actions = state.get_legal_actions(actor)
    if not actions:
        return evaluate(state, role), []

    best_score = -math.inf if is_max else math.inf
    best_line = []

    for action in _order_actions(state, actor, actions):
        child = state.clone()
        child.apply_action(actor, action, use_random=False)
        if not child.finished:
            child.next_turn()

        score, line = minimax(child, depth - 1, not is_max, role, alpha, beta, stats)

        if is_max:
            if score > best_score:
                best_score = score
                best_line = [(actor, action)] + line
            if best_score > alpha:
                alpha = best_score
        else:
            if score < best_score:
                best_score = score
                best_line = [(actor, action)] + line
            if best_score < beta:
                beta = best_score

        if beta <= alpha:
            stats.pruned += 1
            break

    return best_score, best_line


# ---------------------------------------------------------------------------
# Root Search (Iterative Deepening)
# ---------------------------------------------------------------------------

def search_best_move(state, role="npc", max_depth=DEFAULT_MAX_DEPTH,
                     time_budget=TIME_BUDGET, randomize=True):
    """Cari aksi terbaik untuk 'role' menggunakan iterative deepening.

    Iterative deepening naik dari depth 1 sampai max_depth dan berhenti jika
    budget waktu habis, sehingga AI selalu punya jawaban valid walau budget
    sempit (anytime algorithm).

    Args:
        state: GameState saat ini (giliran harus milik 'role')
        role: "npc" (AI) atau "player" (hint untuk pemain)
        max_depth: kedalaman maksimum
        time_budget: batas waktu dalam detik
        randomize: True = pilih acak di antara aksi dengan skor nyaris sama

    Returns:
        Tuple (action, score, stats, line)
    """
    stats = SearchStats()
    start = time.perf_counter()

    actions = state.get_legal_actions(role)
    if not actions:
        stats.ms = (time.perf_counter() - start) * 1000.0
        return None, 0.0, stats, []

    best_action = actions[0]
    best_score = 0.0
    best_line = []
    scores = {}

    for depth in range(1, max_depth + 1):
        # Evaluasi SEMUA cabang root tanpa pruning lintas-cabang agar kita
        # mendapat skor eksak untuk tiap aksi (dipakai tie-breaking).
        scores = {}
        lines = {}
        for action in _order_actions(state, role, actions):
            child = state.clone()
            child.apply_action(role, action, use_random=False)
            if not child.finished:
                child.next_turn()
            score, line = minimax(
                child, depth - 1, False, role, -math.inf, math.inf, stats
            )
            scores[action] = score
            lines[action] = [(role, action)] + line

        # Skor dari depth yang BARU SELESAI selalu dipakai lebih dulu,
        # sehingga budget yang habis di tengah tidak pernah membuat AI
        # jatuh ke aksi default (actions[0]) padahal skor sudah ada.
        stats.max_depth = depth
        best_score = max(scores.values())
        best_action = max(scores, key=scores.get)
        best_line = lines[best_action]

        # Cek budget sebelum naik depth lagi
        if time.perf_counter() - start > time_budget:
            break

        # Semua aksi sudah terminal -> tidak perlu lebih dalam
        if abs(best_score) >= TERMINAL:
            break

    # Tie-break: aksi dengan skor nyaris sama diacak supaya AI tidak monoton
    if randomize and scores:
        ties = [a for a, s in scores.items() if s >= best_score - TIE_EPSILON]
        if len(ties) > 1:
            best_action = random.choice(ties)
            best_score = scores[best_action]
            best_line = [
                (role, best_action)
            ] + _line_tail(state, role, best_action, stats)

    # Metadata pencarian untuk debug overlay (proses keputusan AI)
    stats.role = role
    stats.action = best_action
    stats.score = best_score
    stats.line = list(best_line)
    stats.root_scores = dict(scores)
    stats.terms = evaluate_terms(state)

    stats.ms = (time.perf_counter() - start) * 1000.0
    return best_action, best_score, stats, best_line


def _line_tail(state, role, action, stats):
    """Lanjutan principal variation setelah aksi root tertentu."""
    child = state.clone()
    child.apply_action(role, action, use_random=False)
    if child.finished:
        return []
    child.next_turn()
    _, line = minimax(
        child, min(2, max(1, state.max_depth - 1)), False, role,
        -math.inf, math.inf, stats,
    )
    return line


def get_npc_action(state, max_depth=None):
    """Hitung aksi terbaik musuh menggunakan Min-Max + Alpha-Beta.

    Args:
        state: GameState saat ini (giliran npc)
        max_depth: kedalaman pencarian (default: state.max_depth)

    Returns:
        Tuple (action, score, stats, line)
    """
    depth = max_depth or getattr(state, "max_depth", DEFAULT_MAX_DEPTH)
    return search_best_move(state, role="npc", max_depth=depth, randomize=True)


def get_player_hint(state, max_depth=None):
    """Saran aksi untuk pemain (search dari sisi pemain / maximize).

    Berguna untuk memvisualisasikan bahwa algoritma yang sama bisa
    dimanfaatkan kedua belah pihak.

    Args:
        state: GameState saat ini (giliran player)

    Returns:
        Tuple (action, score, stats, line)
    """
    depth = max_depth or getattr(state, "max_depth", DEFAULT_MAX_DEPTH)
    return search_best_move(
        state, role="player", max_depth=depth, randomize=False
    )


# ---------------------------------------------------------------------------
# Helper: Terapkan arketipe musuh ke objek enemy (NPC)
# ---------------------------------------------------------------------------

# Urutan arketipe untuk rotasi wave
ARCHETYPE_KEYS = tuple(ARCHETYPES)


def choose_archetype(threat=0):
    """Pilih arketipe musuh bergiliran berdasarkan level ancaman.

    Args:
        threat: jumlah pemain yang sudah dikalahkan

    Returns:
        String key di ARCHETYPES
    """
    return ARCHETYPE_KEYS[max(0, threat) % len(ARCHETYPE_KEYS)]


def apply_enemy_archetype(enemy, threat=0, archetype=None):
    """Terapkan stat + personality arketipe ke objek enemy (NPC).

    Fungsi ini jembatan antara data ARCHETYPES dan objek NPC, sehingga
    gaya bertarung AI (bobot evaluation function) berubah tiap wave.

    Args:
        enemy: objek dengan attribute battle_* (NPC)
        threat: level ancaman (dipakai scaling stat)
        archetype: key arketipe; default dipilih otomatis dari threat

    Returns:
        objek enemy yang sama (memudahkan chaining)
    """
    key = archetype or choose_archetype(threat)
    stats = make_enemy_stats(key, threat)
    enemy.archetype = key
    enemy.archetype_name = ARCHETYPES[key]["name"]
    enemy.battle_hp = stats["hp"]
    enemy.battle_max_hp = stats["max_hp"]
    enemy.battle_atk = stats["atk"]
    enemy.battle_def = stats["def"]
    enemy.battle_potions = stats["potions"]
    enemy.battle_heal = stats["heal_amount"]
    enemy.personality = dict(ARCHETYPES[key]["weights"])
    return enemy


# ---------------------------------------------------------------------------
# Helper: Buat GameState dari objek Player & Enemy
# ---------------------------------------------------------------------------

def create_battle_state(player, enemy, max_depth=None):
    """Buat GameState dari objek Player dan Enemy.

    Args:
        player: Objek Player dengan battle stats
        enemy: Objek Enemy dengan battle stats + personality
        max_depth: kedalaman minimax yang dipakai AI musuh

    Returns:
        GameState yang siap digunakan
    """
    state = GameState(
        player_stats={
            "hp": player.battle_hp,
            "max_hp": player.battle_max_hp,
            "atk": player.battle_atk,
            "def": player.battle_def,
            "potions": player.battle_potions,
            "heal_amount": player.battle_heal,
        },
        npc_stats={
            "hp": enemy.battle_hp,
            "max_hp": enemy.battle_max_hp,
            "atk": enemy.battle_atk,
            "def": enemy.battle_def,
            "potions": enemy.battle_potions,
            "heal_amount": enemy.battle_heal,
        },
        npc_weights=getattr(enemy, "personality", None),
    )
    if max_depth:
        state.max_depth = max_depth
    else:
        state.max_depth = getattr(enemy, "ai_depth", DEFAULT_MAX_DEPTH)
    return state
