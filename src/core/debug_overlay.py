"""
debug_overlay.py - Sistem Visualisasi Debug (F1 - F5 & F12)

  [F1] Pathfinding  : node jalur A* (garis hijau), OPEN list (kuning),
                      CLOSED list (merah).
  [F2] CSP           : kotak transparan hijau = sel valid, merah = sel yang
                      melanggar aturan CSP + panel daftar constraint aktif.
  [F3] Local Search  : panel statistik Simulated Annealing (Current Temp,
                      Current Score, Best Score, dll).
  [F4] Adversarial   : pohon nilai Minimax (skor evaluasi aksi +10/-5 di
                      atas kepala Boss + pohon nilai lengkap).
  [F5] Planning      : teks urutan aksi STRIPS pahlawan secara real-time.
  [F12] Toggle All   : nyalakan/matikan seluruh overlay sekaligus.

LAYOUT PANEL (PENTING)
    Semua teks/bar debug TIDAK lagi digambar di koordinat (0, 0) yang menutupi
    map. Setiap info diletakkan di dalam panel semi-transparan di pojok layar:

        pojok kiri atas   : indikator CONTROL MODE + log pesan (main.py)
        pojok kanan atas  : legenda overlay aktif, lalu panel CSP [F2]
        pojok kiri bawah : panel STRIPS [F5] & Local Search [F3] (bertumpuk)
        bawah tengah     : ringkasan A* [F1]
        pojok kanan bawah: pohon Minimax [F4]
"""

import pygame

import config


class DebugOverlay:
    """Manager toggle overlay debug + renderer-nya."""

    KEYS = {
        pygame.K_F1: "path",
        pygame.K_F2: "csp",
        pygame.K_F3: "local",
        pygame.K_F4: "minimax",
        pygame.K_F5: "plan",
    }

    def __init__(self):
        self.flags = {name: False for name in config.OVERLAY_LABELS}
        self._font = None
        self._font_small = None
        self._font_big = None
        self._panel_cache = {}     # cache permukaan panel (ukuran -> surface)
        self._text_cache = {}      # cache hasil render teks
        self._grid_surf = None     # permukaan overlay grid (reused)
        self._col_y = config.BATTLE_SIDE_RECT[1]   # kursor panel kolom kanan (battle)
        self._left_y = config.MAP_PIXEL_H - 8      # kursor kolom kiri (explore)
        self._legend_bottom = 8                    # dasar legenda (explore)

    # ================================================================ util
    def _ensure_fonts(self):
        if self._font is None:
            self._font = pygame.font.Font(None, 20)
            self._font_small = pygame.font.Font(None, 17)
            self._font_big = pygame.font.Font(None, 26)

    def handle_key(self, key):
        """Proses tombol F1..F5 / F12. True bila tombol terkonsumsi."""
        if key in self.KEYS:
            name = self.KEYS[key]
            self.flags[name] = not self.flags[name]
            return True
        if key == pygame.K_F12:
            self.toggle_all()
            return True
        return False

    def toggle_all(self):
        if all(self.flags.values()):
            for k in self.flags:
                self.flags[k] = False
        else:
            for k in self.flags:
                self.flags[k] = True

    def any_active(self):
        return any(self.flags.values())

    # =============================================================== render
    def draw(self, surface, game):
        self._ensure_fonts()
        f = self.flags
        if getattr(game, "state", "") == config.STATE_BATTLE:
            # ---- BATTLE MODE: panel debug ditumpuk di kolom kanan battle UI ----
            side = config.BATTLE_SIDE_RECT
            self._col_y = side[1]
            self._draw_legend(surface, game)          # legenda di atas kolom
            # tinggi panel bawah (STRIPS / Local Search) direservasi dulu supaya
            # panel Minimax (yang fleksibel) tidak menimpanya.
            plan_h = (56 + 16 * max(1, len(game.plan_monitor.step_states()))
                      if f["plan"] else 0)
            local_h = 168 if f["local"] else 0
            reserved = plan_h + local_h
            if reserved:
                reserved += 6 * ((1 if plan_h else 0) + (1 if local_h else 0))
            avail = side[1] + side[3] - self._col_y - reserved
            self._mm_h = max(180, min(536, avail))
            if f["minimax"]:
                self.draw_minimax(surface, game)
            if f["plan"]:
                self.draw_planning(surface, game)
            if f["local"]:
                self.draw_local_search(surface, game)
            return

        # ---- EXPLORATION: tiap panel di pojok layar (tidak menutupi map) ----
        self._draw_legend(surface, game)             # pojok kanan atas
        if f["csp"]:
            self.draw_csp(surface, game)             # tepat di bawah legenda
        # kolom kiri bawah: panel diisi dari bawah ke atas (tak tumpang tindih)
        self._left_y = config.MAP_PIXEL_H - 8
        if f["plan"]:
            self.draw_planning(surface, game)
        if f["local"]:
            self.draw_local_search(surface, game)
        if f["path"]:
            self.draw_pathfinding(surface, game)
        if f["minimax"]:
            self.draw_minimax(surface, game)

    # ------------------------------------------------------------ internal
    def _col_rect(self, game, w, h):
        """Posisi panel di kolom kanan Battle Mode (stack vertikal)."""
        side = config.BATTLE_SIDE_RECT
        y = getattr(self, "_col_y", side[1])
        self._col_y = y + h + 6
        return pygame.Rect(side[0], y, side[2], h)

    def _left_rect(self, w, h):
        """Posisi panel di kolom kiri bawah (isi dari bawah ke atas)."""
        y = max(180, self._left_y - h)      # jangan menimpa log pesan
        self._left_y = y - 6
        return pygame.Rect(config.OVERLAY_PLAN_X, y, w, h)

    @staticmethod
    def _ab(v):
        """Format nilai alpha/beta untuk tampilan (+/-inf)."""
        if v <= -100000:
            return "-inf"
        if v >= 100000:
            return "+inf"
        return str(v)

    def _panel(self, surface, rect, title=None):
        key = (rect.w, rect.h)
        bg = self._panel_cache.get(key)
        if bg is None:
            bg = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            bg.fill(config.PANEL_BG)
            pygame.draw.rect(bg, config.CYAN, bg.get_rect(), 1)
            if len(self._panel_cache) > 32:
                self._panel_cache.clear()
            self._panel_cache[key] = bg
        surface.blit(bg, rect.topleft)
        if title:
            self.text(surface, title, (rect.x + 8, rect.y + 5), config.CYAN, self._font)

    def text(self, surface, msg, pos, color=config.WHITE, font=None):
        key = (str(msg), color, id(font or self._font))
        surf = self._text_cache.get(key)
        if surf is None:
            surf = (font or self._font).render(str(msg), True, color)
            if len(self._text_cache) > 1200:
                self._text_cache.clear()
            self._text_cache[key] = surf
        surface.blit(surf, pos)
        return surf.get_rect(topleft=pos)

    def _overlay_surface(self):
        """Permukaan translusen seukuran map (dipakai ulang tiap frame)."""
        if self._grid_surf is None:
            self._grid_surf = pygame.Surface((config.MAP_PIXEL_W, config.MAP_PIXEL_H),
                                             pygame.SRCALPHA)
        self._grid_surf.fill((0, 0, 0, 0))
        return self._grid_surf

    def _draw_legend(self, surface, game):
        """Daftar overlay aktif di pojok layar."""
        active = [lbl for name, lbl in config.OVERLAY_LABELS.items() if self.flags[name]]
        is_battle = getattr(game, "state", "") == config.STATE_BATTLE
        if not active:
            if not is_battle:
                self._legend_bottom = 8
            return
        h = 18 + 16 * len(active)
        if is_battle:
            # Battle Mode: legenda di paling atas kolom kanan
            side = config.BATTLE_SIDE_RECT
            x, y, w = side[0], side[1], side[2]
            self._col_y = y + h + 6
        else:
            x, y, _w, _h = config.OVERLAY_LEGEND_RECT
            w = config.OVERLAY_LEGEND_RECT[2]
        rect = pygame.Rect(x, y, w, h)
        self._panel(surface, rect)
        for i, lbl in enumerate(active):
            self.text(surface, "* " + lbl, (rect.x + 8, rect.y + 4 + 16 * i),
                      config.YELLOW, self._font_small)
        self._legend_bottom = rect.bottom + 6

    # ============================================================== F1 A*
    def draw_pathfinding(self, surface, game):
        result = game.path_result
        if result is None:
            return
        t = config.TILE_SIZE
        camx, camy = getattr(game, "camera", (0, 0))
        overlay = self._overlay_surface()
        view = pygame.Rect(0, 0, config.MAP_PIXEL_W, config.MAP_PIXEL_H)

        def visible_cell(x, y):
            return view.collidepoint(x * t - camx + t // 2, y * t - camy + t // 2)

        for (x, y) in result.closed_set:                     # CLOSED -> merah
            if visible_cell(x, y):
                overlay.fill((230, 60, 60, 60), (x * t - camx, y * t - camy, t, t))
        for (x, y) in result.open_set:                       # OPEN -> kuning
            if visible_cell(x, y):
                overlay.fill((240, 210, 60, 95), (x * t - camx, y * t - camy, t, t))
        surface.blit(overlay, (0, 0))

        # jalur A* -> garis hijau di antara pusat node
        if len(result.path) >= 1:
            pts = [(x * t + t // 2 - camx, y * t + t // 2 - camy) for (x, y) in
                   [game.hero.cell] + list(result.path)]
            if len(pts) >= 2:
                pygame.draw.lines(surface, config.GREEN, False, pts, 3)
            for p in pts:
                if view.collidepoint(p):
                    pygame.draw.circle(surface, config.WHITE, p, 3)

        # jalur patroli monster (Dijkstra) -> oranye
        for m in game.monsters:
            if len(m.path) >= 2:
                pts = [(m.gx * t + t // 2 - camx,
                        m.gy * t + t // 2 - camy)] + \
                      [(x * t + t // 2 - camx, y * t + t // 2 - camy)
                       for (x, y) in m.path]
                pygame.draw.lines(surface, config.ORANGE, False, pts, 2)

        info = [f"A* [{result.algorithm}]  nodes={result.nodes_expanded}  "
                f"len={len(result.path)}  "
                f"{'FOUND' if result.found else 'BLOCKED -> best-effort'}",
                f"OPEN={len(result.open_set)}  CLOSED={len(result.closed_set)}  "
                f"(Dijkstra patroli monster: oranye)"]
        rx, ry, rw, rh = config.OVERLAY_PATH_RECT
        self._panel(surface, pygame.Rect(rx, ry, rw, rh))
        for i, line in enumerate(info):
            self.text(surface, line, (rx + 6, ry + 4 + 18 * i),
                      config.WHITE if i == 0 else config.GREY, self._font_small)

    # =============================================================== F2 CSP
    def draw_csp(self, surface, game):
        report = game.csp_report
        t = config.TILE_SIZE
        camx, camy = getattr(game, "camera", (0, 0))
        overlay = self._overlay_surface()
        view = pygame.Rect(0, 0, config.MAP_PIXEL_W, config.MAP_PIXEL_H)
        sx0, sy0 = camx // t, camy // t
        sx1 = (camx + config.MAP_PIXEL_W) // t + 1
        sy1 = (camy + config.MAP_PIXEL_H) // t + 1
        for (x, y) in report.ok_cells:
            if sx0 <= x <= sx1 and sy0 <= y <= sy1:
                overlay.fill((80, 220, 100, 42),
                             (x * t - camx, y * t - camy, t, t))
        for (x, y) in report.bad_cells:
            if sx0 <= x <= sx1 and sy0 <= y <= sy1:
                overlay.fill((230, 60, 60, 70),
                             (x * t - camx, y * t - camy, t, t))
                pygame.draw.rect(overlay, config.RED,
                                 (x * t - camx, y * t - camy, t, t), 2)
        surface.blit(overlay, (0, 0))

        # panel constraint
        lines = []
        for code, ok, detail in report.constraints:
            lines.append((f"[{code}] {'OK ' if ok else 'VIOLATED'} - {detail}",
                          config.GREEN if ok else config.RED))
        lines.append((f"Energi: {report.energy_used}/{report.capacity}   "
                      f"Item terpasang: {len(game.placements)}",
                      config.WHITE))
        for v in report.violations[:5]:
            lines.append((f"! {v.rule} di {v.cell}: {v.message[:44]}", config.YELLOW))
        if game.hover and game.hover in report.bad_cells and not game.hover_report_ok:
            lines.append(("Kursor: penempatan DITOLAK (lihat alasan di atas)",
                          config.RED))

        w = config.OVERLAY_CSP_W
        h = 30 + 15 * len(lines)
        y = max(self._legend_bottom, config.OVERLAY_CSP_Y)
        rect = pygame.Rect(config.OVERLAY_CSP_X, y, w, h)
        self._panel(surface, rect,
                    "CSP - CONSTRAINT CHECK (hijau=valid / merah=melanggar)")
        for i, (line, color) in enumerate(lines):
            self.text(surface, line, (rect.x + 8, rect.y + 26 + 15 * i), color,
                      self._font_small)

    # ======================================================= F3 LOCAL SEARCH
    def draw_local_search(self, surface, game):
        snap = game.sa.snapshot
        if getattr(game, "state", "") == config.STATE_BATTLE:
            rect = self._col_rect(game, config.BATTLE_SIDE_RECT[2], 168)
        else:
            rect = self._left_rect(config.OVERLAY_LOCAL_RECT[2], 168)
        self._panel(surface, rect, "LOCAL SEARCH - SIMULATED ANNEALING [O]")
        rows = [
            ("Status", "RUNNING..." if snap.running else
                       ("FINISHED (layout terbaik diterapkan)" if snap.finished else "idle")),
            ("Temperature", f"{snap.temp:8.2f}"),
            ("Current Score", f"{snap.current_score:8.2f}"),
            ("Best Score", f"{snap.best_score:8.2f}"),
            ("Start Score", f"{snap.start_score:8.2f}"),
            ("Iterasi", str(snap.iteration)),
            ("Accepted / Rejected", f"{snap.accepted} / {snap.rejected}"),
        ]
        for i, (k, v) in enumerate(rows):
            y = rect.y + 26 + 18 * i
            self.text(surface, k, (rect.x + 10, y), config.GREY, self._font_small)
            self.text(surface, v, (rect.x + 150, y), config.WHITE, self._font_small)

        # bar temperature
        bar = pygame.Rect(rect.x + 10, rect.y + 148, rect.w - 20, 10)
        pygame.draw.rect(surface, config.DARK_GREY, bar)
        frac = max(0.0, min(1.0, snap.temp / config.SA_START_TEMP))
        pygame.draw.rect(surface, config.CYAN, (bar.x, bar.y, int(bar.w * frac), bar.h))
        pygame.draw.rect(surface, config.GREY, bar, 1)

        # sparkline skor
        if len(snap.history) > 1:
            vals = [s for _, s in snap.history]
            lo, hi = min(vals), max(vals)
            rng = (hi - lo) or 1.0
            pts = []
            w = rect.w - 20
            for i, v in enumerate(vals):
                x = rect.x + 10 + int(w * i / (len(vals) - 1))
                y = rect.y + 152 - int(26 * (v - lo) / rng)
                pts.append((x, y))
            if len(pts) >= 2:
                pygame.draw.lines(surface, config.YELLOW, False, pts, 1)

    # =========================================================== F4 MINIMAX
    def draw_minimax(self, surface, game):
        ai = game.battle_ai
        if getattr(game, "state", "") == config.STATE_BATTLE:
            self._draw_minimax_battle(surface, game)
            return
        boss = game.boss
        camx, camy = getattr(game, "camera", (0, 0))
        # --- skor di atas kepala boss -------------------------------------
        if boss.alive and ai.last_root_children:
            bx = int(boss.px) - camx + config.TILE_SIZE // 2
            by = int(boss.py) - camy - 12
            for i, item in enumerate(ai.last_root_children[:4]):
                action, score = item[0], item[1]
                color = config.GREEN if score >= 0 else config.RED
                label = f"{action} {score:+d}"
                surf = self._font_small.render(label, True, color)
                surface.blit(surf, (bx - surf.get_width() // 2, by - 18 * (i + 1)))
            pygame.draw.line(surface, config.GREY, (bx, by - 4),
                             (bx, boss.py - camy + 4), 1)

        # --- panel pohon nilai + statistik --------------------------------
        rx, ry, rw, rh = config.OVERLAY_MINIMAX_RECT
        rect = pygame.Rect(rx, ry, rw, rh)
        self._panel(surface, rect,
                    "ADVERSARIAL - MINIMAX + ALPHA-BETA (Boss)")
        st = ai.last_stats
        y = rect.y + 26
        info = [
            f"Depth: {st.depth}   Nodes: {st.nodes}   Pruned: {st.pruned}",
            f"Boss memilih: {game.battle['chosen'] if game.battle else '-'}",
            "Aksi akar (skor evaluate):",
        ]
        for line in info:
            self.text(surface, line, (rect.x + 8, y), config.WHITE, self._font_small)
            y += 15
        for item in ai.last_root_children:
            action, score = item[0], item[1]
            color = config.GREEN if score >= 0 else config.RED
            self.text(surface, f"  {action:<8} {score:+d}", (rect.x + 12, y),
                      color, self._font_small)
            y += 14

        # gambar pohon nilai (root + anak + cucu bila muat)
        if ai.last_tree and y < rect.bottom - 20:
            self._draw_tree(surface, ai.last_tree, pygame.Rect(rect.x + 6, y + 2,
                                                               rect.w - 12,
                                                               rect.bottom - y - 8))

    # -------------------------------------------- F4 versi BATTLE MODE
    def _draw_minimax_battle(self, surface, game):
        """
        Panel [F4] khusus Battle Mode (kolom kanan layar battle).

        Menampilkan: nilai Alpha, Beta, Depth, dan skor evaluasi untuk SETIAP
        cabang aksi yang dipertimbangkan Boss (secara real-time).
        """
        ai = game.battle_ai
        st = ai.last_stats
        side = config.BATTLE_SIDE_RECT
        rect = self._col_rect(game, side[2], getattr(self, "_mm_h", 536))
        self._panel(surface, rect, "ADVERSARIAL - MINIMAX + ALPHA-BETA")

        y = rect.y + 24
        head = [
            ("Score=(HP_Boss-HP_Hero)+BuffBoss-ShieldHero", config.CYAN),
            (f"Depth {st.depth} | Nodes {st.nodes} | Pruned {st.pruned}", config.WHITE),
            (f"Root v={st.best_value:+d}  alpha={self._ab(st.alpha)}  "
             f"beta={self._ab(st.beta)}", config.YELLOW),
            (f"Boss memilih: {game.battle['chosen'] if game.battle else '-'}",
             config.GREEN),
            ("Skor tiap cabang aksi yang dipertimbangkan:", config.WHITE),
        ]
        for text, color in head:
            self.text(surface, text, (rect.x + 8, y), color, self._font_small)
            y += 15

        for item in ai.last_root_children:
            action, score = item[0], item[1]
            alpha, beta = (item[2], item[3]) if len(item) > 3 else (0, 0)
            color = config.GREEN if score >= 0 else config.RED
            self.text(surface,
                      f"  {action:<12} v={score:+5d} a={self._ab(alpha):>5} "
                      f"b={self._ab(beta):>5}",
                      (rect.x + 12, y), color, self._font_small)
            y += 14

        y += 4
        self.text(surface, "Pohon keputusan (v=nilai, a=alpha, b=beta):",
                  (rect.x + 8, y), config.WHITE, self._font_small)
        y += 16
        for text, depth in self._tree_lines(ai.last_tree):
            if y > rect.bottom - 14:
                self.text(surface, "... (pohon dipotong, lihat panel F4 penuh)",
                          (rect.x + 10, y), config.GREY, self._font_small)
                break
            color = config.CYAN if depth == 0 else (
                config.WHITE if depth == 1 else config.GREY)
            self.text(surface, text, (rect.x + 10, y), color, self._font_small)
            y += 14

    def _tree_lines(self, node, max_depth=3, limit=30):
        """Ubah pohon nilai menjadi baris teks (indented) + levelnya."""
        lines = []
        if node is None:
            return lines

        def walk(n, depth):
            if len(lines) >= limit or depth > max_depth:
                return
            label = n.label if n.label != "leaf" else "eval"
            lines.append((f"{'  ' * depth}{label} v={n.value:+d} "
                          f"a={self._ab(n.alpha)} b={self._ab(n.beta)}", depth))
            for c in n.children:
                walk(c, depth + 1)

        walk(node, 0)
        return lines

    def _draw_tree(self, surface, node, area):
        """Pohon nilai minimax sederhana (layout per level)."""
        leaves = []

        def layout(n, depth):
            if not n.children:
                leaves.append((n, depth))
                idx = len(leaves) - 1
                return idx
            idxs = [layout(c, depth + 1) for c in n.children]
            mid = (idxs[0] + idxs[-1]) / 2
            leaves.append((n, depth))
            return mid

        total_leaves = [0]

        def count_leaves(n):
            if not n.children:
                total_leaves[0] += 1
                return
            for c in n.children:
                count_leaves(c)
        count_leaves(node)
        if total_leaves[0] > 12:     # batasi agar tidak penuh
            node = type(node)(node.label, node.value, node.depth,
                              alpha=node.alpha, beta=node.beta,
                              children=node.children[:4])

        entries = []

        def assign(n, depth, span):
            entries.append((n, depth, span[0] + span[1] / 2))
            if not n.children or depth >= 2:
                return
            step = span[1] / max(1, len(n.children))
            for i, c in enumerate(n.children):
                assign(c, depth + 1, (span[0] + i * step, step))
        assign(node, 0, (area.x, float(area.w)))

        depth_max = max(e[1] for e in entries) or 1
        for n, d, cx in entries:
            y = area.y + 8 + (area.h - 30) * d / max(1, depth_max)
            label = n.label if n.label != "leaf" else "*"
            surf = self._font_small.render(f"{label}={n.value}", True,
                                           config.CYAN if d == 0 else config.WHITE)
            x = int(cx - surf.get_width() // 2)
            surface.blit(surf, (x, int(y)))
            if d > 0:
                pygame.draw.line(surface, config.DARK_GREY,
                                 (int(cx), int(y) - 4), (int(cx), int(y) - 8), 1)

    # ============================================================= F5 STRIPS
    def draw_planning(self, surface, game):
        monitor = game.plan_monitor
        steps = monitor.step_states()
        w = config.OVERLAY_PLAN_W
        h = 56 + 16 * max(1, len(steps))
        if getattr(game, "state", "") == config.STATE_BATTLE:
            rect = self._col_rect(game, config.BATTLE_SIDE_RECT[2], h)
        else:
            rect = self._left_rect(w, h)
        status_color = {"OK": config.GREEN, "PLAN FAILURE": config.RED,
                        "NO PLAN": config.RED}.get(monitor.status, config.YELLOW)
        self._panel(surface, rect, "AUTOMATED PLANNING - STRIPS [F5]")
        self.text(surface, f"Status: {monitor.status}    Re-plan: {monitor.replan_count}",
                  (rect.x + 8, rect.y + 24), status_color, self._font_small)
        for i, (state, action) in enumerate(steps):
            color = {"DONE": config.GREEN, "ACTIVE": config.YELLOW,
                     "PENDING": config.GREY}[state]
            mark = {"DONE": "[x]", "ACTIVE": "[>]", "PENDING": "[ ]"}[state]
            self.text(surface,
                      f"{i + 1}. {mark} {action.name:<13} - {action.description[:24]}",
                      (rect.x + 8, rect.y + 42 + 16 * i), color, self._font_small)
        if monitor.last_failure != "-":
            self.text(surface, f"Last failure: {monitor.last_failure[:42]}",
                      (rect.x + 8, rect.y + 42 + 16 * len(steps) + 2),
                      config.ORANGE, self._font_small)
