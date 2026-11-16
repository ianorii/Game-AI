"""
mdp.py - Kerangka Markov Decision Process (MDP), Bellman Equation, dan Synchronous Value Iteration.
Materi: Slide 9 - 21 (Decisions Under Uncertainty).
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Callable
import copy
import config


class MDP:
    """
    Representasi Formal Markov Decision Process (S, A, P, R, gamma).

    Sesuai slide 9-11:
      - States (S): Himpunan status dunia.
      - Terminal States: Status penyerap/akhir di mana tidak ada aksi lanjutan.
      - Actions (A(s)): Himpunan aksi yang tersedia dari status s.
      - Transition P(s' | s, a): Distribusi probabilitas menuju status s'.
      - Reward R(s'): Ditentukan oleh status tujuan s'.
      - Discount Factor (gamma): Bobot penghargaan masa depan (default 0.8).
    """

    def __init__(self,
                 states: List[str],
                 actions_dict: Dict[str, List[str]],
                 transitions: Dict[Tuple[str, str], List[Tuple[str, float]]],
                 rewards: Dict[str, float],
                 terminal_states: Optional[Set[str]] = None,
                 gamma: float = config.DECISION_MDP_GAMMA):
        self.states = list(states)
        self.actions_dict = {s: list(acts) for s, acts in actions_dict.items()}
        self.transitions = {k: list(v) for k, v in transitions.items()}
        self.rewards = dict(rewards)
        self.terminal_states = set(terminal_states) if terminal_states else set()
        self.gamma = gamma

        self.validate()

    def actions(self, s: str) -> List[str]:
        """Daftar aksi legal dari status s. Status terminal mengembalikan list kosong []."""
        if s in self.terminal_states:
            return []
        return self.actions_dict.get(s, [])

    def transition(self, s: str, a: str) -> List[Tuple[str, float]]:
        """Mengembalikan daftar pasangan (s', P(s' | s, a))."""
        return self.transitions.get((s, a), [])

    def get_reward(self, s_prime: str) -> float:
        """Mengembalikan reward R(s') saat mendarat di status tujuan s'."""
        return self.rewards.get(s_prime, 0.0)

    def validate(self, tolerance: float = 1e-5):
        """
        Validasi integritas matematis MDP:
          1. 0 <= gamma <= 1
          2. Untuk setiap state non-terminal dan aksi legal, sum_s' P(s'|s,a) == 1.0.
          3. Setiap probabilitas dalam rentang [0, 1].
        """
        if not (0.0 <= self.gamma <= 1.0):
            raise ValueError(f"Gamma harus dalam [0, 1], ditemukan: {self.gamma}")

        for s in self.states:
            if s in self.terminal_states:
                continue
            for a in self.actions(s):
                trans = self.transition(s, a)
                if not trans:
                    raise ValueError(f"Aksi '{a}' dari status '{s}' tidak memiliki transisi.")
                total_p = 0.0
                for next_s, p in trans:
                    if next_s not in self.states:
                        raise ValueError(f"Status transisi '{next_s}' tidak terdaftar dalam states.")
                    if p < 0.0 or p > 1.0:
                        raise ValueError(f"Probabilitas P({next_s}|{s},{a}) = {p} di luar [0, 1].")
                    total_p += p
                if abs(total_p - 1.0) > tolerance:
                    raise ValueError(f"Total probabilitas aksi '{a}' di '{s}' adalah {total_p:.6f} != 1.0.")


def compute_q(mdp: MDP, s: str, a: str, V: Dict[str, float]) -> float:
    """
    Menghitung Q-value untuk pasangan state-action:
      Q(s, a) = sum_s' P(s' | s, a) * [ R(s') + gamma * V(s') ]
    Catatan: Untuk status terminal s', V(s') = 0.
    """
    q_val = 0.0
    for next_s, prob in mdp.transition(s, a):
        v_next = 0.0 if next_s in mdp.terminal_states else V.get(next_s, 0.0)
        r = mdp.get_reward(next_s)
        q_val += prob * (r + mdp.gamma * v_next)
    return q_val


def value_iteration(mdp: MDP,
                    tolerance: float = config.DECISION_VI_TOLERANCE,
                    max_iterations: int = config.DECISION_VI_MAX_ITER) -> Tuple[Dict[str, float], Dict[str, str], List[Dict[str, Any]]]:
    """
    Synchronous Value Iteration (Slide 13-21):
      Setiap baris k murni menggunakan nilai dari baris sebelumnya k-1 (bukan in-place Gauss-Seidel).
      Update:
        V_k(s) = max_a Q_k(s, a)
        Q_k(s, a) = sum_s' P(s' | s, a) * [ R(s') + gamma * V_{k-1}(s') ]

    Berhenti saat:
      max_s |V_k(s) - V_{k-1}(s)| < tolerance ATAU iterasi >= max_iterations.

    Returns:
        Tuple: (V_final, policy_final, history)
          history: list dict per iterasi berisi (iteration, V, Q, policy, delta).
    """
    # Inisialisasi V_0(s) = 0.0 untuk semua s
    v_prev = {s: 0.0 for s in mdp.states}
    history = []

    # Catat keadaan awal (Iterasi 0): sesuai Slide 17, iterasi 0 hanya memuat V_0 = 0.0,
    # sedangkan Q-value dan Aksi belum dievaluasi (ditandai '-' di tabel).
    history.append({
        "iteration": 0,
        "V": dict(v_prev),
        "Q": {},
        "policy": {},
        "delta": 0.0
    })

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        v_curr = {}
        q_curr = {}
        policy_curr = {}
        max_delta = 0.0

        for s in mdp.states:
            if s in mdp.terminal_states:
                v_curr[s] = 0.0
                continue

            acts = mdp.actions(s)
            if not acts:
                v_curr[s] = 0.0
                continue

            best_val = float("-inf")
            best_act = None

            for a in acts:
                # Menggunakan v_prev (SINKRON!)
                q_val = compute_q(mdp, s, a, v_prev)
                q_curr[(s, a)] = q_val
                if q_val > best_val:
                    best_val = q_val
                    best_act = a

            v_curr[s] = best_val
            policy_curr[s] = best_act
            diff = abs(v_curr[s] - v_prev[s])
            if diff > max_delta:
                max_delta = diff

        history.append({
            "iteration": iteration,
            "V": dict(v_curr),
            "Q": dict(q_curr),
            "policy": dict(policy_curr),
            "delta": max_delta
        })

        v_prev = v_curr

        if max_delta < tolerance:
            break

    final_policy = extract_policy(mdp, v_prev)
    return v_prev, final_policy, history


def extract_policy(mdp: MDP, V: Dict[str, float]) -> Dict[str, str]:
    """
    Mengekstrak kebijakan optimal pi*(s) dari fungsi nilai V:
      pi*(s) = argmax_a Q(s, a)
    """
    policy = {}
    for s in mdp.states:
        if s in mdp.terminal_states:
            continue
        acts = mdp.actions(s)
        if not acts:
            continue
        best_act = max(acts, key=lambda a: compute_q(mdp, s, a, V))
        policy[s] = best_act
    return policy


def format_flood_iteration_table(history: List[Dict[str, Any]]) -> str:
    """
    Membuat tabel terformat rapi sesuai slide presentasi 15-21:
    Iterasi | V(Rumah) | Q(Warung,Pintas) | Q(Warung,Raya) | Q(Warung,Balik) | V(Warung) [Aksi] | V(Jalan Raya)
    """
    lines = []
    header = (
        f"{'Iter':<5} | {'V(Rumah)':<9} | {'Q(Pintas)':<10} | {'Q(Raya)':<9} | "
        f"{'Q(Balik)':<9} | {'V(Warung)':<10} | {'Aksi Warung':<12} | {'V(Jln Raya)':<10}"
    )
    sep = "-" * len(header)
    lines.append(sep)
    lines.append(header)
    lines.append(sep)

    for entry in history:
        it = entry["iteration"]
        V = entry["V"]
        Q = entry["Q"]
        pol = entry["policy"]

        v_rumah = f"{V.get('Rumah', 0.0):.2f}"
        v_warung = f"{V.get('Warung', 0.0):.2f}"
        v_raya = f"{V.get('Jalan Raya', 0.0):.2f}"

        if it == 0:
            q_pintas = "-"
            q_raya = "-"
            q_balik = "-"
            act_warung = "-"
        else:
            q_pintas = f"{Q.get(('Warung', 'Pintas'), 0.0):.2f}"
            q_raya = f"{Q.get(('Warung', 'Raya'), 0.0):.2f}"
            q_balik = f"{Q.get(('Warung', 'Balik'), 0.0):.2f}"
            act_warung = pol.get('Warung', '-')

        row = (
            f"{it:<5} | {v_rumah:<9} | {q_pintas:<10} | {q_raya:<9} | "
            f"{q_balik:<9} | {v_warung:<10} | {act_warung:<12} | {v_raya:<10}"
        )
        lines.append(row)

    lines.append(sep)
    return "\n".join(lines)

