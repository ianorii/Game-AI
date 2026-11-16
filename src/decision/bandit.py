"""
bandit.py - Multi-Armed Bandit (Explore vs Exploit) Decision Framework
Sunnyside Isle - Modul Keputusan dalam Ketidakpastian (Decisions Under Uncertainty)

Formulasi:
  - K-Armed Bernoulli Bandit dengan Common Random Numbers (CRN).
  - K = 5 Fishing Spots di muara pantai (Spot A s/d Spot E) dengan peluang sukses tersembunyi theta = [theta_0, ..., theta_K-1].
  - Tiap tarikan (cast) menghasilkan reward biner:
      r = 1 (Tangkapan Langka / Rare Fish: bernilai 60 koin)
      r = 0 (Tangkapan Biasa / Common Fish: bernilai 15 koin)
  - Common Random Numbers (CRN): Bilangan acak u[arm][n] di-precompute pada awal sesi
    sehingga pemain manual, AI autopilot, dan semua ghost agent menghadapi lemparan dadu yang 100% IDENTIK.
  - Perbandingan 5 Algoritma Klasik (Lockstep Execution):
      1. RandomAgent: Eksplorasi murni seragam (Uniform Random).
      2. GreedyAgent: Eksploitasi murni (mu_hat tertinggi setelah mencoba tiap arm 1 kali).
      3. EpsilonGreedyAgent: Campuran eksplorasi acak (probabilitas eps) dan eksploitasi.
      4. UCB1Agent: Optimism in the face of uncertainty (Q_i + c * sqrt(2 * ln(t) / N_i)).
      5. ThompsonSamplingAgent: Bayesian posterior sampling via Beta(1 + s_i, 1 + n_i - s_i).
  - Evaluasi Kuantitatif:
      * Pseudo-Regret Kumulatif: R_T = sum_{t=1}^T (theta* - theta_{a_t})
      * Theoretical Bound: Batas bawah logaritmik Lai-Robbins c * ln(t)
      * % Pemilihan Arm Optimal (Moving Window 20 lemparan)
"""

import math
import random
from collections import deque
from typing import List, Dict, Tuple, Optional, Any


# ==============================================================================
# 1. KONFIGURASI PRESET KESULITAN
# ==============================================================================

BANDIT_PRESETS = {
    "EASY": {
        "name": "Mudah (Gap Lebar)",
        "thetas": [0.10, 0.20, 0.35, 0.50, 0.85],
        "desc": "Satu spot sangat dominan (theta*=0.85). Mudah diidentifikasi algoritma.",
        "horizon": 100,
    },
    "REALISTIC": {
        "name": "Realistis (Alami)",
        "thetas": [0.15, 0.25, 0.30, 0.45, 0.55],
        "desc": "Distribusi bertingkat alami di perairan muara (theta*=0.55).",
        "horizon": 100,
    },
    "HARD": {
        "name": "Sulit (Gap Sempit)",
        "thetas": [0.40, 0.42, 0.45, 0.48, 0.50],
        "desc": "Selisih antar spot sangat tipis. Butuh sampel besar untuk konvergensi.",
        "horizon": 100,
    }
}


# ==============================================================================
# 2. ENVIRONMENT BERNOULLI DENGAN COMMON RANDOM NUMBERS (CRN)
# ==============================================================================

class SpotBandit:
    """
    K-armed Bernoulli Bandit Environment dengan Common Random Numbers (CRN).
    Menjamin keadilan absolut antar algoritma: lemparan ke-k pada arm i
    menggunakan bilangan acak u[i][k] yang persis sama untuk seluruh aktor.
    """
    def __init__(self, thetas: List[float], horizon: int = 100, seed: int = 42):
        self.thetas = list(thetas)
        self.K = len(thetas)
        self.T = horizon
        self.seed = seed
        
        # Precompute tabel CRN u[arm][t]
        rng = random.Random(seed)
        self._u = [[rng.random() for _ in range(horizon)] for _ in self.thetas]
        
        # Identifikasi arm optimal
        self.best_arm = max(range(self.K), key=lambda i: self.thetas[i])
        self.theta_star = self.thetas[self.best_arm]

    def create_actor_view(self) -> "ActorView":
        """Membuat view terisolasi untuk satu aktor (pemain / agent) yang berbagi CRN."""
        return ActorView(self)


class ActorView:
    """
    View terisolasi untuk satu aktor.
    Masing-masing aktor memiliki counter lemparan mandiri n[arm],
    namun hasil lemparan ditarik dari undian deterministik CRN yang sama.
    """
    def __init__(self, env: SpotBandit):
        self.env = env
        self.n = [0] * env.K

    def pull(self, arm: int) -> int:
        """Menarik arm i dan mengembalikan reward 1 (rare fish) atau 0 (common fish)."""
        if arm < 0 or arm >= self.env.K:
            raise ValueError(f"Arm index {arm} di luar batas [0, {self.env.K - 1}]")
        
        k = self.n[arm]
        # Jika melebihi batas horizon awal, fallback ke pseudo-random deterministik terprediksi
        if k < self.env.T:
            u_val = self.env._u[arm][k]
        else:
            fallback_rng = random.Random(self.env.seed + arm * 1000 + k)
            u_val = fallback_rng.random()

        reward = 1 if u_val < self.env.thetas[arm] else 0
        self.n[arm] += 1
        return reward


# ==============================================================================
# 3. KELAS DASAR DAN 5 AGEN MULTI-ARMED BANDIT
# ==============================================================================

class BanditAgent:
    """Kelas dasar agen Bandit."""
    name: str = "BaseAgent"
    display_name: str = "Base"
    color: Tuple[int, int, int] = (180, 180, 180)

    def __init__(self, K: int, rng: Optional[random.Random] = None):
        self.K = K
        self.rng = rng or random.Random()
        self.n = [0] * K       # Jumlah tarikan per arm
        self.s = [0] * K       # Jumlah sukses per arm
        self.t = 0             # Total tarikan kumulatif

    def mean(self, i: int) -> float:
        """Estimasi rata-rata keberhasilan mu_hat pada arm i."""
        return self.s[i] / self.n[i] if self.n[i] > 0 else 0.0

    def _argmax(self, scores: List[float]) -> int:
        """Argmax dengan tie-breaking acak yang adil."""
        max_val = max(scores)
        best_indices = [i for i, v in enumerate(scores) if v == max_val]
        return self.rng.choice(best_indices)

    def _untried(self) -> Optional[int]:
        """Mengembalikan indeks arm yang belum pernah dicoba, jika ada."""
        untried = [i for i in range(self.K) if self.n[i] == 0]
        return self.rng.choice(untried) if untried else None

    def update(self, arm: int, reward: int):
        """Memperbarui statistik observasi setelah menarik arm."""
        self.n[arm] += 1
        self.s[arm] += reward
        self.t += 1

    def select(self) -> int:
        """Memilih arm untuk ditarik. Diimplementasikan oleh subkelas."""
        raise NotImplementedError

    def diagnostics(self, i: int) -> Dict[str, Any]:
        """Diagnostik untuk visualisasi HUD."""
        return {
            "n": self.n[i],
            "s": self.s[i],
            "mean": self.mean(i)
        }


class RandomAgent(BanditAgent):
    """Agen Random: Memilih arm secara acak seragam (Uniform Exploration)."""
    name = "Random"
    display_name = "Acak Seragam"
    color = (160, 160, 160)

    def select(self) -> int:
        return self.rng.randrange(self.K)


class GreedyAgent(BanditAgent):
    """Agen Greedy: Eksploitasi murni setelah mencoba tiap arm 1 kali."""
    name = "Greedy"
    display_name = "Pure Greedy"
    color = (230, 80, 80)

    def select(self) -> int:
        # Coba arm yang belum pernah ditarik terlebih dahulu
        untried = self._untried()
        if untried is not None:
            return untried
        # Eksploitasi arm dengan mu_hat tertinggi
        return self._argmax([self.mean(i) for i in range(self.K)])


class EpsilonGreedyAgent(BanditAgent):
    """Agen Epsilon-Greedy: Eksplorasi acak dengan probabilitas eps, selebihnya greedy."""
    name = "EpsGreedy"
    display_name = "ε-Greedy (ε=0.15)"
    color = (240, 160, 50)

    def __init__(self, K: int, rng: Optional[random.Random] = None, eps: float = 0.15):
        super().__init__(K, rng)
        self.eps = eps

    def select(self) -> int:
        untried = self._untried()
        if untried is not None:
            return untried
        if self.rng.random() < self.eps:
            return self.rng.randrange(self.K)
        return self._argmax([self.mean(i) for i in range(self.K)])


class UCB1Agent(BanditAgent):
    """
    Agen UCB1 (Upper Confidence Bound 1 - Auer et al., 2002):
    Score_i = mu_hat_i + c * sqrt(2 * ln(t) / n_i)
    """
    name = "UCB1"
    display_name = "UCB1 (c=√2)"
    color = (70, 140, 240)

    def __init__(self, K: int, rng: Optional[random.Random] = None, c: float = 1.414):
        super().__init__(K, rng)
        self.c = c

    def bonus(self, i: int) -> float:
        """Komponen nilai optimisme batas atas ketidakpastian."""
        if self.n[i] == 0:
            return float("inf")
        return self.c * math.sqrt(2.0 * math.log(max(1, self.t)) / self.n[i])

    def score(self, i: int) -> float:
        """Skor total UCB1."""
        if self.n[i] == 0:
            return float("inf")
        return self.mean(i) + self.bonus(i)

    def select(self) -> int:
        untried = self._untried()
        if untried is not None:
            return untried
        scores = [self.score(i) for i in range(self.K)]
        return self._argmax(scores)

    def diagnostics(self, i: int) -> Dict[str, Any]:
        d = super().diagnostics(i)
        d["bonus"] = self.bonus(i) if self.n[i] > 0 else 9.99
        d["ucb_score"] = self.score(i) if self.n[i] > 0 else 9.99
        return d


class ThompsonSamplingAgent(BanditAgent):
    """
    Agen Thompson Sampling (Posterior Sampling - Thompson, 1933):
    Mengambil sampel theta_tilde_i ~ Beta(alpha_i, beta_i)
    dengan prior uninformative Beta(1, 1).
    """
    name = "Thompson"
    display_name = "Thompson Sampling (Beta)"
    color = (60, 210, 120)

    def __init__(self, K: int, rng: Optional[random.Random] = None,
                 prior_alpha: float = 1.0, prior_beta: float = 1.0):
        super().__init__(K, rng)
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta

    def sample_posterior(self, i: int) -> float:
        """Mengambil satu sampel dari distribusi posterior Beta arm i."""
        a = self.prior_alpha + self.s[i]
        b = self.prior_beta + (self.n[i] - self.s[i])
        return self.rng.betavariate(a, b)

    def select(self) -> int:
        # Thompson Sampling langsung mengeksplorasi secara alami via varians Beta
        samples = [self.sample_posterior(i) for i in range(self.K)]
        return self._argmax(samples)

    def credible_interval(self, i: int, samples: int = 200, confidence: float = 0.95) -> Tuple[float, float]:
        """Menghitung 95% Bayesian Credible Interval dari sampel Beta."""
        a = self.prior_alpha + self.s[i]
        b = self.prior_beta + (self.n[i] - self.s[i])
        # Gunakan rng lokal independen agar tidak menggeser seed permainan
        sample_rng = random.Random(self.t * 31 + i * 17)
        vals = sorted([sample_rng.betavariate(a, b) for _ in range(samples)])
        low_idx = int(samples * (1.0 - confidence) / 2.0)
        high_idx = int(samples * (1.0 + confidence) / 2.0) - 1
        return (vals[low_idx], vals[high_idx])


# ==============================================================================
# 4. METRIK & TRACKER REGRET KUMULATIF
# ==============================================================================

class RegretTracker:
    """
    Mencatat Pseudo-Regret Kumulatif dan Laju Pemilihan Arm Optimal.
    R_t = sum_{tau=1}^t (theta* - theta_{a_tau})
    """
    def __init__(self, env: SpotBandit, window: int = 20):
        self.env = env
        self.window = window
        self.cum_regret: List[float] = [0.0]
        self.history_arms: List[int] = []
        self.history_rewards: List[int] = []
        self._window_opt: deque = deque(maxlen=window)
        self.windowed_optimal_rate: List[float] = [0.0]

    def record(self, arm: int, reward: int):
        """Mencatat pemilihan arm dan menghitung delta regret."""
        delta = self.env.theta_star - self.env.thetas[arm]
        new_cum = self.cum_regret[-1] + delta
        self.cum_regret.append(new_cum)
        self.history_arms.append(arm)
        self.history_rewards.append(reward)

        is_optimal = 1.0 if arm == self.env.best_arm else 0.0
        self._window_opt.append(is_optimal)
        opt_rate = sum(self._window_opt) / len(self._window_opt)
        self.windowed_optimal_rate.append(opt_rate)

    @property
    def total_regret(self) -> float:
        return self.cum_regret[-1]

    @property
    def optimal_pick_ratio(self) -> float:
        if not self.history_arms:
            return 0.0
        opt_count = sum(1 for a in self.history_arms if a == self.env.best_arm)
        return opt_count / len(self.history_arms)


# ==============================================================================
# 5. BANDIT DIRECTOR (ORKESTRASI SESI & GHOST RUNNERS)
# ==============================================================================

class BanditDirector:
    """
    Orkestrator Sesi Multi-Armed Bandit di Sunnyside Isle.
    Menghubungkan:
      - Aktor Utama: Pemain Manual atau AI Autopilot (F9)
      - 5 Ghost Agents: Berjalan headless dalam lockstep di environment CRN yang sama
      - Metrik & Evaluasi: RegretTracker untuk setiap aktor
    """
    ACTOR_CLASSES = {
        "Random": RandomAgent,
        "Greedy": GreedyAgent,
        "EpsGreedy": EpsilonGreedyAgent,
        "UCB1": UCB1Agent,
        "Thompson": ThompsonSamplingAgent
    }

    def __init__(self, preset_key: str = "REALISTIC", seed: int = 42,
                 primary_kind: str = "player", primary_agent_name: str = "Thompson"):
        self.preset_key = preset_key
        self.seed = seed
        self.primary_kind = primary_kind  # "player" | "autopilot"
        self.primary_agent_name = primary_agent_name
        self.start_session(preset_key, seed, primary_kind, primary_agent_name)

    def start_session(self, preset_key: str = "REALISTIC", seed: int = 42,
                      primary_kind: str = "player", primary_agent_name: str = "Thompson"):
        """Memulai atau mereset sesi permainan/musim memancing baru."""
        cfg = BANDIT_PRESETS.get(preset_key, BANDIT_PRESETS["REALISTIC"])
        self.preset_key = preset_key
        self.seed = seed
        self.primary_kind = primary_kind
        self.primary_agent_name = primary_agent_name
        
        # Buat environment master dengan CRN
        self.env = SpotBandit(cfg["thetas"], horizon=cfg["horizon"], seed=seed)
        self.K = self.env.K
        self.T = self.env.T
        self.t = 0
        
        # Aktor utama (Player / Autopilot)
        self.primary_view = self.env.create_actor_view()
        self.primary_tracker = RegretTracker(self.env)
        
        if primary_kind == "autopilot":
            agent_cls = self.ACTOR_CLASSES.get(primary_agent_name, ThompsonSamplingAgent)
            self.primary_agent: Optional[BanditAgent] = agent_cls(self.K, random.Random(seed + 100))
        else:
            self.primary_agent = None

        # Ghost agents: 5 algoritma berjalan di background lockstep dengan undian CRN
        self.ghosts: Dict[str, Dict[str, Any]] = {}
        for idx, (name, cls) in enumerate(self.ACTOR_CLASSES.items()):
            agent = cls(self.K, random.Random(seed + 200 + idx * 10))
            view = self.env.create_actor_view()
            tracker = RegretTracker(self.env)
            self.ghosts[name] = {
                "agent": agent,
                "view": view,
                "tracker": tracker,
                "color": agent.color,
                "display_name": agent.display_name
            }

        # Statistik pemain untuk HUD
        self.player_pulls = [0] * self.K
        self.player_successes = [0] * self.K
        self.rare_fish_caught = 0
        self.common_fish_caught = 0

    def choose_spot(self) -> int:
        """
        Dipanggil oleh AI Autopilot (atau tombol rekomendasi bantuan AI pemain)
        untuk menentukan spot pancingan terbaik berdasarkan strategi bandit aktif.
        """
        if self.primary_agent:
            return self.primary_agent.select()
        # Fallback jika mode manual: gunakan agen Thompson sebagai advisor
        advisor = self.ghosts["Thompson"]["agent"]
        return advisor.select()

    def resolve_cast(self, spot_id: int) -> Tuple[bool, int]:
        """
        Dieksekusi saat proses memancing selesai pada spot tertentu.
        1. Aktor utama menarik arm dari ActorView (CRN).
        2. Aktor utama diperbarui (jika AI Autopilot) & tracker dicatat.
        3. Seluruh 5 ghost agent melangkah 1 kali secara paralel lockstep!
        4. Mengembalikan: (is_rare_fish: bool, coin_reward: int)
        """
        if spot_id < 0 or spot_id >= self.K:
            spot_id = 0

        # Tarikan aktor utama
        reward = self.primary_view.pull(spot_id)
        self.primary_tracker.record(spot_id, reward)

        if self.primary_agent:
            self.primary_agent.update(spot_id, reward)

        # Catat statistik pemain
        self.player_pulls[spot_id] += 1
        self.player_successes[spot_id] += reward
        if reward == 1:
            self.rare_fish_caught += 1
            coin_reward = 60  # Rare Fish bernilai tinggi
        else:
            self.common_fish_caught += 1
            coin_reward = 15  # Common Fish biasa

        # Jalankan 5 ghost agent dalam lockstep (Common Random Numbers)
        self._step_ghosts()

        self.t += 1
        is_rare = (reward == 1)
        return is_rare, coin_reward

    def _step_ghosts(self):
        """Memajukan setiap ghost agent 1 langkah pada view CRN masing-masing."""
        for g in self.ghosts.values():
            agent: BanditAgent = g["agent"]
            view: ActorView = g["view"]
            tracker: RegretTracker = g["tracker"]

            chosen_arm = agent.select()
            r = view.pull(chosen_arm)
            agent.update(chosen_arm, r)
            tracker.record(chosen_arm, r)

    @property
    def is_finished(self) -> bool:
        """Apakah sesi horizon T telah tercapai."""
        return self.t >= self.T

    def get_lai_robbins_bound(self) -> List[float]:
        """
        Menghitung kurva referensi teoritis batas bawah logaritmik Lai-Robbins (1985):
        R(t) >= sum_{i: delta_i > 0} (delta_i / KL(theta_i, theta*)) * ln(t)
        """
        # Hitung konstanta c_LR
        theta_star = self.env.theta_star
        c_lr = 0.0
        for i, th in enumerate(self.env.thetas):
            if i == self.env.best_arm:
                continue
            delta = theta_star - th
            # KL divergence untuk Bernoulli: KL(p, q) = p*ln(p/q) + (1-p)*ln((1-p)/(1-q))
            p = max(0.001, min(0.999, th))
            q = max(0.001, min(0.999, theta_star))
            kl = p * math.log(p / q) + (1.0 - p) * math.log((1.0 - p) / (1.0 - q))
            if kl > 0.0001:
                c_lr += delta / kl

        # Buat kurva untuk setiap t = 0..self.t
        curve = [0.0]
        for step in range(1, self.t + 1):
            curve.append(c_lr * math.log(step))
        return curve
