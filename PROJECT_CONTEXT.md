# Project Context: AI Labyrinth - The Dungeon Overseer

## 1. Tujuan & Tech Stack
Game 2D top-down bertema *Dungeon Overseer vs Hero AI* pada peta open-world Sunnyside 96x72 tile (tugas mata kuliah AI Semester 3). Menggabungkan kontrol manual/otomatis Hero dengan berbagai algoritma AI mandiri tanpa library pihak ketiga.
- **Tech Stack**: Python 3.12+, Pygame-CE (2D game engine), modul matematika/AI murni (MDP, HTN, Minimax, CSP, A*).

## 2. Arsitektur & Struktur Folder
- `src/ai/`: Pathfinding (`pathfinding.py` A*/Dijkstra), CSP (`csp.py` penempatan jebakan/musuh), Local Search (`local_search.py` Simulated Annealing), Adversarial Search (`adversarial.py` Minimax + Alpha-Beta duel Boss).
- `src/planning/`: Automated Planning (`planning.py` STRIPS, `htn.py` Hierarchical Task Network untuk rutinitas Hero & NPC).
- `src/decision/`: Decision Under Uncertainty mandiri (`probability.py`, `bayes_update`, `mdp.py` Value Iteration, `flood_model.py`).
- `src/core/` & `src/world/`: Entitas karakter/hewan (`entity.py`, `animal.py`), peta Sunnyside (`game_map.py`, `village_deco.py`), deteksi collision (`can_stand`), dan kamera.
- `assets/`: Atlas tileset Sunnyside World (1280x1280 px), sprites hero/monsters, serta data collision/footprint JSON.
- `tests/` & `tools/`: Test suite (`test_collision_and_decor_fixes.py`, `test_decision_under_uncertainty.py`) dan skrip simulasi/verifikasi.

## 3. Status Fitur
- **Berjalan (Done)**: Pathfinding A*, Turn-based battle Minimax/Alpha-Beta, CSP + Local Search antrean musuh, Modul Decision Under Uncertainty (EV, MEU, Bayes, MDP Value Iteration, Monte Carlo 10k), Sistem collision `can_stand` & audit footprint 22 bangunan desa, Papan ramalan cuaca Bayes desa, Animasi swimming & flush banjir pantai, Tab Ketidakpastian di panel terpadu [F7], Aset gerbang pantai (terbuka/tertutup).
- **Sedang Dikerjakan (In Progress)**: Validasi dan review akhir Putaran 3 bersama Claude.

