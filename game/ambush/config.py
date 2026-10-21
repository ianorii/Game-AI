"""game/ambush/config.py - Seluruh parameter Tahap 3 di satu tempat.

Aturan: tidak ada magic number di modul lain; semua angka tuning dibaca
dari AmbushConfig. Nilai default di bawah adalah titik awal yang wajar,
bukan hasil kalibrasi - eksperimen fase 6 yang menentukannya.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AmbushConfig:
    """Satu-satunya sumber angka tuning Tahap 3."""

    # -- Struktur squad -------------------------------------------------
    kmax: int = 4              # jumlah slot peran (slot 1 = lead, efek penuh)
    diminish: float = 0.5      # faktor kontribusi slot i: 1 / (1 + diminish*i)
    armor_max: float = 0.50    # batas atas armor total hasil penjumlahan buff
    weaken_max: float = 0.60   # batas atas weaken total

    # -- Budget CSP (global constraint) ---------------------------------
    # kmax=4 berbagi budget yang sama (6+6·target) sehingga ruang efektif
    # lebih ketat: pruned 4->9 pada target 0.5 (lihat laporan Fase 1).
    base_budget: int = 6       # budget minimum walau target = 0
    budget_scale: int = 6      # budget = base + round(target * scale)

    # -- Duel berurutan (SEQUENTIAL) vs buff gabungan (BUFF) --------------
    mode: str = "SEQUENTIAL"  # "BUFF" = perilaku lama (1 NPC lead);
                              # "SEQUENTIAL" = antrean k musuh (default)
    min_enemies: int = 2      # antrean valid minimal 2 musuh aktif
    rest_heal_pct: float = 0.15  # Disetujui diagnosis: satu-satunya tuas kecil
                                 # yang menggeser kedua kebijakan (gagal greedy
                                 # 31->39%, d4 14->25%) tanpa ubah rasa 1v1
    npc_potions_carry: bool = False  # True = potion musuh ikut terbawa
                                     # (default False = musuh segar)
    npc_starting_potions: int = 1  # potion awal TIAP musuh (anti-stall rantai;
                                   # player & POTION_LIMIT tak tersentuh)
    enemy_base_hp: int = 70  # HP dasar musuh (cermin ENEMY_BASE_HP di
                              # enemy_queue). SENGAJA BUKAN 100: permintaan
                              # pemain "darah musuh jangan disamain sama
                              # darah player". Player tetap 100 (tahap 2,
                              # MAX_HP, tak tersentuh angka ini).
                              # Ditambah bonus HP peran di ROLE_TABLE
                              # (Minion 60, Warrior/Archer/Tank/Healer 70,
                              # Mage 80, Boss +80 -> 150), sehingga
                              # TIDAK ada peran yang HP-nya 100.
                              # HP maks musuh = base + buff.hp lewat
                              # enemy_max_hp() (sim == battle == HUD).
                              # Setiap musuh baru SELALU mulai di HP maks
                              # penuh (tidak terbawa antar-duel) dan HP-nya
                              # turun normal sampai 0 saat duel (tanpa clamp
                              # minimum lagi - bug "HP beku di 80" sudah
                              # dihapus di battle_system.py).
                              # Jika mengubah angka ini, docs/balance_TahapA.md
                              # dan data kalibrasi ikut berubah.
    refill_potions_each_duel: bool = True  # potion heal player isi penuh
                                           # (POTION_LIMIT) tiap ganti lawan
                                           # dalam antrean (via carry_potions,
                                           # sim == driver)
    enemy_stat_scale: float = 1.0  # skala stat musuh RANTAI (sapuan Fase 3);
                                   # hanya dipakai bila mode=SEQUENTIAL
                                   # (mode BUFF tak tersentuh)
    potion_bonus_per_duel: int = 0  # potion player +N tiap duel (pembanding;
                                    # default 0 = murni terbawa)

    # -- Budget antrean (global constraint, titik awal terverifikasi) -----
    base_q: int = 8           # budget antrean minimum
    budget_q_scale: int = 8   # budget antrean = base_q + round(target*scale)

    # -- Evaluator rantai (tiga tingkat, §3 keputusan) --------------------
    rerank_M: int = 2         # kandidat top-M untuk sim penuh (bukan inner)
    chain_rerank_games: int = 4  # duel-simulasi per kandidat rerank
    light_sim_enabled: bool = True  # LS antrean memakai sim ringan
    light_sim_games: int = 4  # duel per eval ringan (murah, CRN per search)
    allow_heuristic_prefilter: bool = True  # heuristik hanya pra-penyaring
    qs_prefilter_top: int = 12  # kandidat neighbour teratas untuk dinilai
    allow_fallback_weights: bool = False  # True = boleh pakai bobot darurat
                                          # TAK terkalibrasi (butuh ACC eksplisit)
    corr_pearson_min: float = 0.85  # ambang kalibrasi (test set)
    corr_spearman_min: float = 0.80
    rmse_max: float = 0.08
    instant_budget_s: float = 3.0  # jalur gameplay sampai REVIEW (mode instant)
    transition_hold_s: float = 1.5  # TIDAK dipakai lagi: layar transisi/
                                    # hasil duel kini menunggu Enter pemain
                                    # (permintaan pemain), bukan lanjut
                                    # otomatis setelah jeda.

    def budget_q_for(self, target: float) -> int:
        """Budget power antrean untuk satu target difficulty."""
        return self.base_q + int(round(target * self.budget_q_scale))

    def csp_flags(self) -> dict:
        """Flag CSP mengikuti mode (jaminan SEQUENTIAL memakai aturan antrean).

        Director (Fase 4+) WAJIB membangun squad_problem lewat helper ini,
        bukan hardcode queue_rules=False. Tes `test_mode_flags_drive_rules`
        gagal bila mapping ini rusak.
        """
        seq = self.mode == "SEQUENTIAL"
        return {"queue_rules": seq,
                "min_active": self.min_enemies if seq else 1}
    boss_min_wins: int = 3     # unary: Boss hanya jika wins >= ini

    # -- Heuristic difficulty: AFFINE yang difit ke data simulasi -------
    # Provenance: experiments/fit_heuristic.py (150 squad canonical acak,
    # sim 6 duel depth-4-vs-4, seed 20260712): korelasi 0.934, MAE 0.048,
    # rentang prediksi [0.468, 0.998]. Jangan ubah manual; jalankan ulang
    # fitting bila tabel role/item berubah. w_spec ~ 0 (noise): AI jarang
    # memakai SPECIAL dalam horizon sim sehingga efeknya tak terukur.
    w_hp: float = 0.0031
    w_atk: float = 0.0188
    w_spec: float = -0.0043
    w_regen: float = 0.0384
    w_armor: float = 0.7017
    w_chip: float = 0.0337
    w_weaken: float = 0.6974
    w_bias: float = 0.4679
    diff_norm: float = 6.0     # (warisan; tak dipakai formula affine)

    # -- Objective local search -----------------------------------------
    target_tol: float = 0.02   # |diff - target| <= tol berarti "sampai target"

    # -- Simulation evaluator -------------------------------------------
    sim_games: int = 12        # duel per evaluasi (mahal; untuk re-ranking)
    sim_max_plies: int = 80    # batas plies per duel simulasi
    sim_npc_depth: int = 4     # depth NPC = depth produksi duel nyata
    sim_player_depth: int = 4  # depth lawan-AI: SAMA dengan NPC agar sim
                               # simetris (buff yang memutuskan, bukan otak)

    # -- Buff-aware AI (lookahead ronde untuk penyesuaian HP efektif) -----
    bew_rounds: int = 3

    # -- CSP solver ------------------------------------------------------
    csp_time_limit: float = 2.0    # detik per satu pemanggilan solve()
    csp_max_nodes: int = 50000     # pengaman agar backtracking selalu berhenti

    # -- Hill climbing / random restart ----------------------------------
    hc_max_iters: int = 200
    hc_sideways: int = 10      # batas sideways move per restart
    hc_restarts: int = 4       # jumlah restart (seed dari CSP acak)
    hc_time_limit: float = 3.0

    # -- Simulated annealing ---------------------------------------------
    sa_t0: float = 0.5         # suhu awal (skala gap 0..1)
    sa_cooling: float = 0.995  # T <- T * cooling tiap iterasi (default spek)
    sa_tmin: float = 1e-3      # berhenti bila T < ini ("cooled")
    sa_max_iters: int = 2000
    sa_time_limit: float = 3.0

    # -- Genetic algorithm -----------------------------------------------
    ga_pop: int = 24
    ga_gens: int = 40
    ga_cx: float = 0.8         # probabilitas crossover per pasangan
    ga_mut: float = 0.15       # probabilitas mutasi per gen
    ga_tour: int = 3           # ukuran turnamen seleksi
    ga_penalty: float = 0.5    # penalti fitness per pelanggaran constraint
    ga_repair: bool = False    # True = proyeksikan ke feasible (bukan penalti)
    ga_time_limit: float = 5.0

    # -- Governor adaptif ------------------------------------------------
    gov_init: float = 0.5      # target awal permainan
    # gov_min dari DATA (jalur 3, opsi A bersyarat): 0.3 terbukti tak
    # terjangkau (maks 1.7% sampel dalam +-0.15 di semua tuas); 0.40 adalah
    # kelipatan 0.05 terendah dengan >=10% (14.7% pada loadout sedang).
    gov_min: float = 0.40      # batas bawah terjangkau (bukan tebakan)
    gov_max: float = 0.95      # batas atas absolut (pengaman, bukan target)
    # Plafon terbukti Director (opsi C disetujui): 0.80 vs 0.95 identik dalam
    # noise karena constraint budget membatasi difficulty maks ~0.75-0.81.
    # Governor dijepit [gov_min, governor_max_target]; permintaan di atasnya
    # dijawab antrean tersulit + label jujur (bukan target lebih tinggi).
    governor_max_target: float = 0.80
    # Siklus tombol C (Fase 4+): nilai terendah yang terbukti, lalu 0.5/0.8;
    # ADAPTIF ditambahkan driver saat runtime (bukan di sini).
    target_cycle: tuple = (0.40, 0.50, 0.80)
    gov_up: float = 0.05       # langkah naik per kemenangan player
    gov_down: float = 0.07     # langkah turun per kekalahan (lebih peka)

    # -- Director --------------------------------------------------------
    dir_seeds: int = 3         # solusi CSP awal yang dikumpulkan
    dir_rerank: bool = True    # validasi akhir dengan simulation evaluator
    dir_rerank_games: int = 6  # duel validasi (kecil: sekali jalan)
    dir_slow_steps: int = 3    # event CSP per frame pada mode "slow" (kecil
                               # agar langkah terlihat; slow = menu demo)
    dir_phase_hold: float = 0.8  # jeda baca (detik) tiap ganti fase besar
                               # pada mode slow (CSP -> LS)

    def budget_for(self, target: float) -> int:
        """Budget power squad untuk satu target difficulty (global constraint)."""
        return self.base_budget + int(round(target * self.budget_scale))
