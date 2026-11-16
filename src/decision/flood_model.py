"""
flood_model.py - Pemodelan Masalah Menuju Kampus Saat Banjir (Slide 9 - 23).
Mendukung analisis sensitivitas f dan varian kesalahan Reward Shaping (+3).
"""

import os
from typing import Dict, List, Tuple, Optional, Any
import config
from decision.mdp import MDP, compute_q, value_iteration, extract_policy


def create_flood_mdp(f: float = config.FLOOD_PRIOR_DEFAULT,
                     gamma: float = config.DECISION_MDP_GAMMA,
                     step_reward: float = config.DECISION_REWARD_STEP_DEFAULT,
                     reward_shaping: bool = False) -> MDP:
    """
    Membangun instance MDP Model Banjir sesuai slide 9-11 dan varian slide 23.

    Status:
      - Rumah: Posisi awal
      - Warung: Titik simpang keputusan (Pintas, Raya, Balik)
      - Jalan Raya: Jalur aman tapi berputar
      - Kampus: Status terminal tujuan sukses (Reward +10)
      - Banjir: Status terminal kegagalan (Reward -20)

    Args:
        f: Probabilitas banjir di jalan pintas (0 <= f <= 1).
        gamma: Discount factor (default 0.8).
        step_reward: Biaya langkah standar (default -2.0).
        reward_shaping: Jika True, langkah diberi reward positif +3 (slide 23).

    Returns:
        MDP: Instance MDP siap diselesaikan dengan Value Iteration.

    Raises:
        ValueError: Jika f di luar rentang [0, 1].
    """
    if f < 0.0 or f > 1.0:
        raise ValueError(f"Probabilitas banjir f harus dalam rentang [0, 1], ditemukan: {f}")

    states = ["Rumah", "Warung", "Jalan Raya", "Kampus", "Banjir"]
    terminal_states = {"Kampus", "Banjir"}

    actions_dict = {
        "Rumah": ["Jalan"],
        "Warung": ["Pintas", "Raya", "Balik"],
        "Jalan Raya": ["Jalan"],
        "Kampus": [],
        "Banjir": []
    }

    transitions = {
        ("Rumah", "Jalan"): [("Warung", 1.0)],
        ("Warung", "Pintas"): [("Kampus", 1.0 - f), ("Banjir", f)],
        ("Warung", "Raya"): [("Jalan Raya", 1.0)],
        ("Warung", "Balik"): [("Rumah", 1.0)],
        ("Jalan Raya", "Jalan"): [("Kampus", 1.0)]
    }

    if reward_shaping:
        # Varian Slide 23: Setiap langkah gerak (Jalan, Balik) diberi +3
        shaping_val = config.DECISION_REWARD_SHAPING_STEP
        rewards = {
            "Kampus": config.DECISION_REWARD_CAMPUS,
            "Banjir": config.DECISION_REWARD_FLOOD,
            "Rumah": shaping_val,
            "Warung": shaping_val,
            "Jalan Raya": shaping_val
        }
    else:
        # Model Standar Slide 10: Kampus +10, Banjir -20, lainnya -2
        rewards = {
            "Kampus": config.DECISION_REWARD_CAMPUS,
            "Banjir": config.DECISION_REWARD_FLOOD,
            "Rumah": step_reward,
            "Warung": step_reward,
            "Jalan Raya": step_reward
        }

    return MDP(
        states=states,
        actions_dict=actions_dict,
        transitions=transitions,
        rewards=rewards,
        terminal_states=terminal_states,
        gamma=gamma
    )


def find_f_star_bisection(f_min: float = 0.0,
                          f_max: float = 0.5,
                          tol: float = 1e-6,
                          max_iter: int = 100) -> Tuple[float, int]:
    """
    Pencarian Bisection (Bagi Dua) untuk menemukan titik kritis f* secara numerik.
    Catatan Teoretis: Ini adalah ekstensi analitik di luar slide kuliah
    (Slide 22 menyajikan diagram konvergensi untuk kasus f = 0.25).

    Mencari f* sedemikian rupa sehingga:
      Q(Warung, Pintas) - Q(Warung, Raya) = 0
      [(1 - f)*10 + f*(-20)] - [-2 + 0.8*10] = 0
      (10 - 30f) - 6 = 4 - 30f = 0  =>  f* = 4/30 ~ 0.133333.

    Kriteria Berhenti (Dual Termination Criteria):
      1. Lebar Interval (Bracket Width): (high - low) / 2 <= tol.
         Menyusut secara eksponensial (0.5 / 2^k). Pada k=18, lebar = 1.91e-6;
         pada k=19, lebar = 9.54e-7 <= 1e-6.
      2. Toleransi Residu Fungsi (Function Tolerance): |diff| < tol.
         Berhenti seketika jika residual |4 - 30*mid| < 1e-6.

    Args:
        f_min: Batas bawah probabilitas (default 0.0).
        f_max: Batas atas probabilitas (default 0.5).
        tol: Toleransi kesalahan (default 1e-6).
        max_iter: Iterasi maksimum (default 100).

    Returns:
        Tuple[float, int]: (f_star_ditemukan, jumlah_iterasi)
    """
    low = f_min
    high = f_max
    iter_count = 0

    while (high - low) / 2.0 > tol and iter_count < max_iter:
        iter_count += 1
        mid = (low + high) / 2.0

        # Evaluasi numerik langsung melalui MDP dan Value Iteration
        mdp = create_flood_mdp(f=mid)
        v, _, _ = value_iteration(mdp, tolerance=1e-7)
        q_pintas = compute_q(mdp, "Warung", "Pintas", v)
        q_raya = compute_q(mdp, "Warung", "Raya", v)
        diff = q_pintas - q_raya

        if abs(diff) < tol:
            return mid, iter_count

        # Fungsi diff(f) = 4 - 30f monoton turun terhadap f:
        # diff > 0 -> f* ada di kanan (mid..high)
        # diff < 0 -> f* ada di kiri (low..mid)
        if diff > 0:
            low = mid
        else:
            high = mid

    mid = (low + high) / 2.0
    return mid, iter_count


def analyze_sensitivity_f(f_start: float = 0.0,
                          f_end: float = 0.5,
                          steps: int = 101) -> Dict[str, Any]:
    """
    Analisis Sensitivitas Kebijakan terhadap Probabilitas Banjir f.
    Catatan Teoretis: Ini merupakan ekstensi analitik/numerik di luar materi slide
    (Slide 22 menyajikan diagram hasil akhir f = 0.25).

    Titik temu analitik:
      Q(Warung, Pintas) = (1 - f)*10 + f*(-20) = 10 - 30f
      Q(Warung, Raya) = -2 + 0.8*10 = 6
      10 - 30f* = 6  =>  30f* = 4  =>  f* = 4/30 = 2/15 (~0.133333)

    Langkah sweep (step size) dihitung sebagai:
      step_size = (f_end - f_start) / (steps - 1)
      Untuk rentang [0.0, 0.5] dan steps = 101, step_size = 0.5 / 100 = 0.005.

    Returns:
        Dict: Hasil analisis numerik, analitik, dan bisection.
    """
    f_star_analytic = config.DECISION_ANALYTIC_F_STAR
    step_size = (f_end - f_start) / (steps - 1) if steps > 1 else 0.0
    sweep_data = []
    numerical_switch_f = None
    prev_policy = None

    for i in range(steps):
        f_val = f_start + i * step_size
        f_val = round(f_val, 6)
        mdp = create_flood_mdp(f=f_val)
        v, policy, _ = value_iteration(mdp)

        q_pintas = (1.0 - f_val) * 10.0 + f_val * (-20.0)
        q_raya = -2.0 + 0.8 * 10.0  # 6.0
        act = policy.get("Warung", "")

        sweep_data.append({
            "f": f_val,
            "Q_Pintas": q_pintas,
            "Q_Raya": q_raya,
            "V_Warung": v.get("Warung", 0.0),
            "V_Rumah": v.get("Rumah", 0.0),
            "policy_warung": act
        })

        if prev_policy is not None and prev_policy != act and numerical_switch_f is None:
            numerical_switch_f = f_val
        prev_policy = act

    # Jalankan pencarian bisection untuk akurasi tinggi
    bisection_f, bisection_iters = find_f_star_bisection(f_min=f_start, f_max=f_end)

    return {
        "f_star_analytic": f_star_analytic,
        "step_size": step_size,
        "numerical_switch_f": numerical_switch_f,
        "bisection_switch_f": bisection_f,
        "bisection_iterations": bisection_iters,
        "sweep_data": sweep_data
    }


def generate_sensitivity_chart(output_path: str = "docs/figures/sensitivity_policy_vs_f.png"):
    """
    Menghasilkan grafik visual Policy vs f menggunakan Pygame surface rendering (Headless).
    Menampilkan kurva Q(Pintas), Q(Raya), titik kritis f* = 0.1333, dan shading area policy.
    """
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    import pygame
    pygame.init()

    width, height = 800, 500
    surf = pygame.Surface((width, height))
    surf.fill((250, 250, 252))

    # Margin grafik
    m_left, m_right, m_top, m_bottom = 80, 50, 60, 60
    plot_w = width - m_left - m_right
    plot_h = height - m_top - m_bottom

    # Rentang sumbu
    f_min, f_max = 0.0, 0.5
    q_min, q_max = -6.0, 12.0

    def to_screen(f_val: float, q_val: float) -> Tuple[int, int]:
        sx = m_left + int(((f_val - f_min) / (f_max - f_min)) * plot_w)
        sy = m_top + int(((q_max - q_val) / (q_max - q_min)) * plot_h)
        return sx, sy

    # 1. Shading Area Kebijakan
    f_star = config.DECISION_ANALYTIC_F_STAR
    star_x, _ = to_screen(f_star, 0.0)

    # Shading Pintas (kiri f*) - Hijau muda lembut
    pintas_rect = pygame.Rect(m_left, m_top, star_x - m_left, plot_h)
    pintas_surf = pygame.Surface((pintas_rect.w, pintas_rect.h), pygame.SRCALPHA)
    pintas_surf.fill((100, 200, 120, 45))
    surf.blit(pintas_surf, pintas_rect.topleft)

    # Shading Raya (kanan f*) - Biru muda lembut
    raya_rect = pygame.Rect(star_x, m_top, m_left + plot_w - star_x, plot_h)
    raya_surf = pygame.Surface((raya_rect.w, raya_rect.h), pygame.SRCALPHA)
    raya_surf.fill((100, 140, 240, 45))
    surf.blit(raya_surf, raya_rect.topleft)

    # 2. Grid & Sumbu
    c_grid = (220, 224, 230)
    c_axis = (60, 64, 75)
    font_sm = pygame.font.Font(None, 18)
    font_md = pygame.font.Font(None, 22)
    font_lg = pygame.font.Font(None, 26)

    # Grid horizontal
    for q_tick in range(-6, 13, 2):
        _, sy = to_screen(0.0, q_tick)
        pygame.draw.line(surf, c_grid, (m_left, sy), (m_left + plot_w, sy), 1)
        lbl = font_sm.render(f"{q_tick:+d}", True, (100, 105, 115))
        surf.blit(lbl, (m_left - 36, sy - 6))

    # Grid vertikal
    for f_step in range(0, 6):
        f_tick = f_step * 0.1
        sx, _ = to_screen(f_tick, 0.0)
        pygame.draw.line(surf, c_grid, (sx, m_top), (sx, m_top + plot_h), 1)
        lbl = font_sm.render(f"{f_tick:.1f}", True, (100, 105, 115))
        surf.blit(lbl, (sx - 10, m_top + plot_h + 8))

    # Kotak pembatas plot
    pygame.draw.rect(surf, c_axis, (m_left, m_top, plot_w, plot_h), 2)

    # 3. Plot Garis Q(Pintas) & Q(Raya)
    pts_pintas = []
    pts_raya = []
    for i in range(101):
        f_val = f_min + (f_max - f_min) * (i / 100.0)
        qp = 10.0 - 30.0 * f_val
        qr = 6.0
        pts_pintas.append(to_screen(f_val, qp))
        pts_raya.append(to_screen(f_val, qr))

    # Garis Q(Pintas) = 10 - 30f (Merah Tua / Oranye)
    pygame.draw.lines(surf, (220, 50, 40), False, pts_pintas, 3)

    # Garis Q(Raya) = 6.0 (Biru)
    pygame.draw.lines(surf, (30, 100, 220), False, pts_raya, 3)

    # Garis putus-putus f* vertikal
    star_pt = to_screen(f_star, 6.0)
    for y_dash in range(m_top, m_top + plot_h, 8):
        pygame.draw.line(surf, (150, 50, 180), (star_pt[0], y_dash), (star_pt[0], min(y_dash + 4, m_top + plot_h)), 2)

    # Titik perpotongan f*
    pygame.draw.circle(surf, (150, 30, 180), star_pt, 6)
    pygame.draw.circle(surf, (255, 255, 255), star_pt, 3)

    # 4. Label dan Teks Informasi
    # Judul
    title_surf = font_lg.render("Analisis Sensitivitas Kebijakan vs Probabilitas Banjir (f)", True, (25, 30, 45))
    surf.blit(title_surf, (m_left + (plot_w - title_surf.get_width()) // 2, 18))

    # Label Sumbu X & Y
    x_lbl = font_md.render("Probabilitas Banjir (f)", True, (40, 45, 55))
    surf.blit(x_lbl, (m_left + (plot_w - x_lbl.get_width()) // 2, height - 28))

    y_lbl = font_md.render("Q(Warung, a)", True, (40, 45, 55))
    surf.blit(y_lbl, (15, m_top - 25))

    # Keterangan Titik Kritis
    f_star_txt = font_md.render(f"f* = 4/30 = 0.1333", True, (140, 20, 170))
    surf.blit(f_star_txt, (star_pt[0] + 10, star_pt[1] - 25))

    # Label Region Kebijakan
    txt_pol1 = font_lg.render("PILIH PINTAS", True, (35, 130, 60))
    surf.blit(txt_pol1, (m_left + 30, m_top + 40))

    txt_pol2 = font_lg.render("PILIH JALAN RAYA", True, (30, 80, 180))
    surf.blit(txt_pol2, (star_pt[0] + 80, m_top + 40))

    # Legend
    leg_x = m_left + plot_w - 240
    leg_y = m_top + plot_h - 90
    pygame.draw.rect(surf, (255, 255, 255), (leg_x, leg_y, 230, 80), border_radius=4)
    pygame.draw.rect(surf, (200, 205, 215), (leg_x, leg_y, 230, 80), 1, border_radius=4)

    pygame.draw.line(surf, (220, 50, 40), (leg_x + 12, leg_y + 20), (leg_x + 40, leg_y + 20), 3)
    surf.blit(font_sm.render("Q(Pintas) = 10 - 30f", True, (40, 40, 50)), (leg_x + 48, leg_y + 13))

    pygame.draw.line(surf, (30, 100, 220), (leg_x + 12, leg_y + 44), (leg_x + 40, leg_y + 44), 3)
    surf.blit(font_sm.render("Q(Raya) = 6.0", True, (40, 40, 50)), (leg_x + 48, leg_y + 37))

    pygame.draw.line(surf, (150, 50, 180), (leg_x + 12, leg_y + 66), (leg_x + 40, leg_y + 66), 2)
    surf.blit(font_sm.render(f"Batas Kritis f* = {f_star:.4f}", True, (130, 30, 160)), (leg_x + 48, leg_y + 59))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    pygame.image.save(surf, output_path)
    print(f"[Chart] Berhasil menyimpan grafik sensitivitas ke: '{output_path}'")
    return output_path

