"""
probability.py - Fondasi Probabilitas, Expected Value, Utility, MEU, dan Teorema Bayes.
Materi: Slide 3 - 8 (Decisions Under Uncertainty).
"""

from typing import List, Tuple, Dict, Optional, Callable


def expected_value(outcomes: List[Tuple[float, float]], tolerance: float = 1e-5) -> float:
    """
    Menghitung Nilai Harapan (Expected Value):
      EV = sum_i (P(o_i) * V(o_i))

    Args:
        outcomes: Daftar pasangan (probabilitas, nilai) -> [(p1, v1), (p2, v2), ...]
        tolerance: Batas toleransi validasi jumlah probabilitas == 1.0.

    Returns:
        float: Nilai harapan matematis.

    Raises:
        ValueError: Jika probabilitas di luar [0, 1] atau total probabilitas != 1.0.
    """
    if not outcomes:
        raise ValueError("Daftar outcomes tidak boleh kosong.")

    total_prob = 0.0
    ev = 0.0

    for prob, val in outcomes:
        if prob < 0.0 or prob > 1.0:
            raise ValueError(f"Probabilitas harus dalam rentang [0, 1], ditemukan: {prob}")
        total_prob += prob
        ev += prob * val

    if abs(total_prob - 1.0) > tolerance:
        raise ValueError(f"Total probabilitas harus bernilai 1.0, ditemukan: {total_prob:.6f}")

    return ev


def expected_utility(outcomes: List[Tuple[float, float]],
                     utility_fn: Optional[Callable[[float], float]] = None,
                     tolerance: float = 1e-5) -> float:
    """
    Menghitung Utilitas Harapan (Expected Utility):
      EU = sum_i (P(o_i) * U(v_i))

    Args:
        outcomes: Daftar pasangan (probabilitas, nilai).
        utility_fn: Fungsi pemetaan nilai ke utilitas U(v). Jika None, U(v) = v.
        tolerance: Toleransi validasi probabilitas.

    Returns:
        float: Utilitas harapan.
    """
    if utility_fn is None:
        return expected_value(outcomes, tolerance=tolerance)

    if not outcomes:
        raise ValueError("Daftar outcomes tidak boleh kosong.")

    total_prob = 0.0
    eu = 0.0

    for prob, val in outcomes:
        if prob < 0.0 or prob > 1.0:
            raise ValueError(f"Probabilitas harus dalam rentang [0, 1], ditemukan: {prob}")
        total_prob += prob
        eu += prob * utility_fn(val)

    if abs(total_prob - 1.0) > tolerance:
        raise ValueError(f"Total probabilitas harus bernilai 1.0, ditemukan: {total_prob:.6f}")

    return eu


def meu(action_outcomes: Dict[str, List[Tuple[float, float]]],
        utility_fn: Optional[Callable[[float], float]] = None) -> Tuple[str, float]:
    """
    Prinsip Maximum Expected Utility (MEU):
      Memilih aksi a* yang memaksimalkan EU(a):
      a* = argmax_a EU(a)

    Args:
        action_outcomes: Pemetaan nama aksi -> daftar outcomes [(p, v)].
        utility_fn: Fungsi utilitas opsional.

    Returns:
        Tuple[str, float]: (nama_aksi_terbaik, nilai_eu_maksimal).
    """
    if not action_outcomes:
        raise ValueError("Kamus action_outcomes tidak boleh kosong.")

    best_action = None
    max_eu = float("-inf")

    for action_name, outcomes in action_outcomes.items():
        eu_val = expected_utility(outcomes, utility_fn=utility_fn)
        if eu_val > max_eu:
            max_eu = eu_val
            best_action = action_name

    return best_action, max_eu


def bayes_update(prior: float,
                 p_e_given_h: float,
                 p_e_given_not_h: float) -> Tuple[float, float]:
    """
    Pembaruan Probabilitas Bayesian (Teorema Bayes):
      P(H | E) = (P(E | H) * P(H)) / P(E)
      P(E) = P(E | H)*P(H) + P(E | ~H)*P(~H)

    Args:
        prior: P(H) - Probabilitas awal hipotesis H terjadi (misal Banjir).
        p_e_given_h: P(E | H) - Likelihood bukti E jika H benar (misal Berita jika Banjir).
        p_e_given_not_h: P(E | ~H) - False positive rate bukti E jika H salah.

    Returns:
        Tuple[float, float]: (posterior P(H|E), total evidence prob P(E)).

    Raises:
        ValueError: Jika salah satu probabilitas di luar [0, 1].
        ZeroDivisionError: Jika probabilitas bukti P(E) bernilai 0.
    """
    for name, p in [("prior", prior),
                    ("p_e_given_h", p_e_given_h),
                    ("p_e_given_not_h", p_e_given_not_h)]:
        if p < 0.0 or p > 1.0:
            raise ValueError(f"Parameter '{name}' harus dalam rentang [0, 1], ditemukan: {p}")

    p_not_h = 1.0 - prior
    p_e = (p_e_given_h * prior) + (p_e_given_not_h * p_not_h)

    if p_e <= 0.0:
        raise ZeroDivisionError(f"P(E) bernilai {p_e}, tidak dapat melakukan pembaruan Bayes.")

    posterior = (p_e_given_h * prior) / p_e
    return posterior, p_e

