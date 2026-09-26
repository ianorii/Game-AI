"""
Debug overlay module - Visualisasi hasil pathfinding untuk debugging.

Modul ini menghandle:
1. Visualisasi visited nodes (kotak biru transparan)
2. Visualisasi path nodes (kotak hijau dengan border)
3. Label g/h/f pada cell saat zoom cukup besar
4. Info panel (judul, stats, legend, kontrol)
5. Toggle layers dengan keyboard (1, 2, 3, 4)

Layer Debug:
- Layer 1 (tombol 1): Visited nodes - node-node yang diekspansi A*
- Layer 2 (tombol 2): Path nodes - jalur terpendek yang ditemukan
- Layer 3 (tombol 3): Info panel - panel info di kiri atas
- Layer 4 (tombol 4): Cell labels - label g/h/f pada cell
"""
import pygame

from game.map import CELL_SIZE
from game.map.utils import game_pos


def _fit_text(font, text, color, max_w):
    """Render ``text`` dan potong dengan ellipsis bila melebihi ``max_w``.

    Args:
        font: Font untuk merender
        text: Teks asal
        color: Warna teks
        max_w: Lebar maksimum piksel yang boleh dipakai

    Returns:
        Surface teks dengan lebar dijamin <= ``max_w``
    """
    surf = font.render(text, True, color)
    if surf.get_width() <= max_w:
        return surf
    ell = "..."
    trimmed = text
    while trimmed and font.size(trimmed + ell)[0] > max_w:
        trimmed = trimmed[:-1]
    return font.render(trimmed + ell if trimmed else ell, True, color)


class DebugOverlay:
    """Manages debug visualization layers untuk pathfinding.

    Attributes:
        show_visited: Tampilkan visited nodes (kotak biru)
        show_path: Tampilkan path nodes (kotak hijau)
        show_info: Tampilkan info panel (text)
        show_labels: Tampilkan label g/h/f pada cell
    """

    def __init__(self):
        """Inisialisasi semua layer debug sebagai visible."""
        self.show_visited = True
        self.show_path = True
        self.show_info = True
        self.show_labels = True
        self._vis_buf = None
        self._vis_buf_size = 0
        self._path_fill_buf = None
        self._path_fill_size = 0
        self._label_bg_cache = {}
        self._panel_cache = None
        self._panel_size = (0, 0)
        self._close_btn = None   # Tombol ✕ hide panel (skenario klik)
        self._show_btn = None    # Tombol ▶ restore panel saat ter-hide

    def toggle(self, key):
        """Toggle layer debug berdasarkan tombol yang ditekan.

        Mapping:
            K_1: Toggle visited nodes
            K_2: Toggle path nodes
            K_3: Toggle info panel
            K_4: Toggle cell labels (g/h/f)

        Args:
            key: Tombol keyboard yang ditekan (pygame key constant)
        """
        if key == pygame.K_1:
            self.show_visited = not self.show_visited
        elif key == pygame.K_2:
            self.show_path = not self.show_path
        elif key == pygame.K_3:
            self.show_info = not self.show_info
        elif key == pygame.K_4:
            self.show_labels = not self.show_labels

    def handle_click(self, pos):
        """Handle klik mouse pada tombol info panel.

        Klik ✕ pada panel = hide panel info (tombol 3 juga bisa).
        Klik pill "▶" saat panel ter-hide = restore panel.

        Args:
            pos: Tuple (x, y) posisi klik

        Returns:
            True jika klik dikonsumsi (tombol panel), False jika tidak
        """
        if self._close_btn is not None and self._close_btn.collidepoint(pos):
            self.show_info = False
            self._close_btn = None
            return True
        if self._show_btn is not None and self._show_btn.collidepoint(pos):
            self.show_info = True
            self._show_btn = None
            return True
        return False

    def draw_scaled(self, screen, player, font, viewport, hide_visited=False, status=""):
        """Gambar semua layer debug yang aktif ke layar.

        Args:
            screen: Surface utama untuk drawing
            player: Objek Player dengan debug_visited, debug_path, dll.
            font: pygame Font untuk rendering teks
            viewport: Objek Viewport untuk koordinat
            hide_visited: True untuk skip drawing visited (digunakan di edit mode)
            status: Status text dari game state
        """
        cellw = int(CELL_SIZE * viewport.scale)
        show_label_cells = self.show_labels and cellw >= 36

        # ---- Visited Nodes (kotak biru dengan border) ----
        if self.show_visited and not hide_visited:
            size = max(3, int(9 * viewport.scale))
            if self._vis_buf is None or self._vis_buf_size != size:
                self._vis_buf = pygame.Surface((size, size), pygame.SRCALPHA)
                self._vis_buf.fill((70, 140, 255, 100))
                self._vis_buf_size = size
            cellw = int(CELL_SIZE * viewport.scale)
            border_w = max(1, int(2 * viewport.scale))
            for r, c in player.debug_visited:
                if (r, c) not in player.debug_path and (r, c) != (player.row, player.col):
                    x, y = game_pos(r, c, viewport)
                    half = cellw // 2
                    rect = pygame.Rect(x - half, y - half, cellw, cellw)
                    # Isi biru transparan (cached)
                    screen.blit(self._vis_buf, rect.topleft)
                    # Border biru terang
                    pygame.draw.rect(screen, (70, 140, 255), rect, border_w)

                    # Label g/h/f pada visited node
                    if show_label_cells and (r, c) in player.debug_node_data:
                        self._draw_cell_label(
                            screen, r, c, viewport, cellw, font,
                            player.debug_node_data[(r, c)],
                            bg_color=(30, 60, 120, 160),
                        )

        # ---- Path Nodes (hijau dengan border) ----
        if self.show_path:
            # Cache fill surface untuk path nodes
            path_fill_size = max(3, cellw)
            if not hasattr(self, '_path_fill_buf') or self._path_fill_size != path_fill_size:
                self._path_fill_buf = pygame.Surface((path_fill_size, path_fill_size), pygame.SRCALPHA)
                self._path_fill_buf.fill((40, 200, 80, 100))
                self._path_fill_size = path_fill_size

            for i, (r, c) in enumerate(player.debug_path):
                x, y = game_pos(r, c, viewport)
                half = cellw // 2
                rect = pygame.Rect(x - half, y - half, cellw, cellw)

                # Isi hijau transparan (cached)
                screen.blit(self._path_fill_buf, rect.topleft)

                # Border hijau
                pygame.draw.rect(screen, (40, 220, 90), rect, max(1, int(2 * viewport.scale)))

                # Nomor urut di tengah cell (hanya jika label tidak aktif)
                if cellw >= 28 and not show_label_cells:
                    num_font_size = max(10, min(16, cellw // 4))
                    num_font = pygame.font.SysFont("consolas", num_font_size)
                    num_text = num_font.render(str(i), True, (255, 255, 255))
                    screen.blit(
                        num_text,
                        (x - num_text.get_width() // 2, y - num_text.get_height() // 2),
                    )

                # Label g/h/f pada path node
                if show_label_cells and (r, c) in player.debug_node_data:
                    self._draw_cell_label(
                        screen, r, c, viewport, cellw, font,
                        player.debug_node_data[(r, c)],
                        bg_color=(20, 100, 40, 160),
                    )

        # ---- Start & Goal markers ----
        if player.debug_visited:
            # Start node
            sr, sc = player.debug_visited[0]
            sx, sy = game_pos(sr, sc, viewport)
            half = cellw // 2
            pygame.draw.rect(
                screen, (0, 200, 255),
                (sx - half, sy - half, cellw, cellw),
                max(2, int(3 * viewport.scale)),
            )

        if player.target is not None:
            tx, ty = game_pos(*player.target, viewport)
            half = cellw // 2
            pygame.draw.rect(
                screen, (255, 220, 50),
                (tx - half, ty - half, cellw, cellw),
                max(2, int(3 * viewport.scale)),
            )

        # ---- Info Panel (kiri atas) ----
        # Panel info bisa di-hide (tombol ✕ / angka 3) dan di-restore (pill ▶)
        if self.show_info:
            self._show_btn = None
            self._draw_info_panel(screen, player, font, status)
        else:
            self._close_btn = None
            self._draw_show_pill(screen, font)

    def _draw_cell_label(self, screen, r, c, viewport, cellw, font, data, bg_color):
        """Gambar label g/h/f di satu cell.

        Args:
            screen: Surface utama
            r, c: Grid position
            viewport: Viewport object
            cellw: Ukuran cell dalam pixel
            font: pygame Font
            data: Dict {"g": float, "h": float, "f": float}
            bg_color: Warna background (R, G, B, A)
        """
        x, y = game_pos(r, c, viewport)
        half = cellw // 2

        # Background transparan (cached per warna)
        bg_key = (cellw, bg_color)
        if not hasattr(self, '_label_bg_cache'):
            self._label_bg_cache = {}
        if bg_key not in self._label_bg_cache:
            bg = pygame.Surface((cellw, cellw), pygame.SRCALPHA)
            bg.fill(bg_color)
            self._label_bg_cache[bg_key] = bg
        screen.blit(self._label_bg_cache[bg_key], (x - half, y - half))

        # Font kecil untuk label
        label_size = max(8, min(13, cellw // 7))
        label_font = pygame.font.SysFont("consolas", label_size)

        g_val = data["g"]
        h_val = data["h"]
        f_val = data["f"]

        # Format angka: bulatkan jika integer
        def fmt(v):
            return str(int(v)) if v == int(v) else f"{v:.1f}"

        lines = [
            (f"g={fmt(g_val)}", (120, 220, 120)),
            (f"h={fmt(h_val)}", (120, 180, 255)),
            (f"f={fmt(f_val)}", (255, 220, 80)),
        ]

        line_h = label_size + 1
        total_h = line_h * len(lines)
        start_y = y - total_h // 2

        for i, (text, color) in enumerate(lines):
            rendered = label_font.render(text, True, color)
            screen.blit(
                rendered,
                (x - rendered.get_width() // 2, start_y + i * line_h),
            )

    def _draw_show_pill(self, screen, font):
        """Gambar pill kecil "▶ DEBUG" saat info panel ter-hide.

        Args:
            screen: Surface utama
            font: pygame Font
        """
        label = "▶  DEBUG  [3]"
        text = font.render(label, True, (210, 225, 245))
        pad_x, pad_y = 10, 6
        rect = pygame.Rect(10, 10, text.get_width() + pad_x * 2, text.get_height() + pad_y * 2)
        self._show_btn = rect

        hovered = rect.collidepoint(pygame.mouse.get_pos())
        bg = (30, 42, 62, 210) if not hovered else (52, 74, 104, 230)

        pill = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(pill, bg, pill.get_rect(), border_radius=10)
        pygame.draw.rect(pill, (90, 140, 200, 255), pill.get_rect(), 1, border_radius=10)
        screen.blit(pill, rect.topleft)
        screen.blit(text, (rect.x + pad_x, rect.y + pad_y))

    def _draw_info_panel(self, screen, player, font, status=""):
        """Gambar info panel rapi di kiri atas layar.

        Panel berisi:
        - Header "A* DEBUGGER" dengan badge status dan tombol ✕ (hide)
        - Statistik pencarian (label kiri, nilai kanan)
        - Legend warna (dengan swatch)
        - Kontrol (dua kolom)

        Args:
            screen: Surface utama
            player: Objek Player
            font: pygame Font
            status: Status text dari game state
        """
        pad = 12
        line_h = 18
        panel_w = min(300, max(220, screen.get_width() // 4))
        header_h = 32

        # Status pencarian
        if player.debug_found:
            status_text, status_color = "FOUND", (90, 230, 130)
        elif player.debug_visited:
            status_text, status_color = "NO PATH", (235, 100, 100)
        else:
            status_text, status_color = "IDLE", (150, 150, 155)

        sections = self._get_panel_sections(player, status)

        # Hitung tinggi panel
        body_h = pad
        for sec in sections:
            if sec.get("header"):
                body_h += line_h + 4
            body_h += len(sec["lines"]) * line_h + 8
        panel_h = header_h + body_h

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (13, 17, 27, 218), panel.get_rect(), border_radius=12)
        pygame.draw.rect(panel, (60, 72, 92, 255), panel.get_rect(), 1, border_radius=12)

        # Header bar (lebih terang) + garis aksen atas
        pygame.draw.rect(panel, (22, 30, 45, 235), (0, 0, panel_w, header_h),
                         border_top_left_radius=12, border_top_right_radius=12)
        pygame.draw.rect(panel, (90, 150, 220, 255), (0, 0, panel_w, 3),
                         border_top_left_radius=2, border_top_right_radius=2)

        title = font.render("A* DEBUGGER", True, (205, 228, 255))
        panel.blit(title, (pad, (header_h - title.get_height()) // 2 + 1))

        # Badge status (di kanan judul)
        badge = font.render(status_text, True, status_color)
        badge_rect = pygame.Rect(0, 0, badge.get_width() + 14, badge.get_height() + 6)
        badge_rect.topleft = (panel_w - badge_rect.width - 34, (header_h - badge_rect.height) // 2)
        pygame.draw.rect(panel, (10, 14, 22, 200), badge_rect, border_radius=7)
        pygame.draw.rect(panel, status_color, badge_rect, 1, border_radius=7)
        panel.blit(badge, (badge_rect.x + 7, badge_rect.y + 3))

        # Tombol ✕ (hide) di ujung kanan header
        x_rect = pygame.Rect(panel_w - 28, (header_h - 20) // 2, 20, 20)
        hovered = False
        if self._close_btn is not None:
            hovered = self._close_btn.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(panel, (70, 34, 40, 230) if hovered else (34, 40, 54, 220),
                         x_rect, border_radius=6)
        x_surf = font.render("✕", True, (255, 150, 150) if hovered else (200, 210, 225))
        panel.blit(x_surf, (x_rect.centerx - x_surf.get_width() // 2,
                            x_rect.centery - x_surf.get_height() // 2 + 1))

        # Isi section
        y = header_h + 4
        for sec in sections:
            if sec.get("header"):
                head = font.render(sec["header"], True, sec.get("header_color", (180, 190, 210)))
                panel.blit(head, (pad, y))
                y += line_h + 2
                pygame.draw.line(panel, (48, 56, 72), (pad, y - 4), (panel_w - pad, y - 4))

            swatches = sec.get("swatches") or []
            for i, (a_txt, b_txt, color) in enumerate(sec["lines"]):
                text_x = pad
                if swatches:
                    sw_color = swatches[i] if i < len(swatches) else (200, 200, 200)
                    pygame.draw.rect(panel, sw_color, (pad, y + 3, 11, 11), border_radius=3)
                    text_x = pad + 18

                a_surf = font.render(a_txt, True, color)
                panel.blit(a_surf, (text_x, y))

                if b_txt:
                    b_surf = font.render(b_txt, True, color)
                    if sec.get("align_right"):
                        panel.blit(b_surf, (panel_w - pad - b_surf.get_width(), y))
                    else:
                        panel.blit(b_surf, (text_x + 78, y))
                y += line_h
            y += 8

        panel_x, panel_y = 10, 10
        screen.blit(panel, (panel_x, panel_y))

        # Rect tombol ✕ dalam koordinat layar (untuk handle_click)
        self._close_btn = pygame.Rect(panel_x + x_rect.x, panel_y + x_rect.y,
                                      x_rect.width, x_rect.height)

    def _get_panel_sections(self, player, status=""):
        """Bangun data section untuk info panel.

        Args:
            player: Objek Player
            status: Status text dari game state

        Returns:
            List of dicts. Tiap section: {"header", "header_color", "lines": [(a, b, color)]}.
            Opsi tambahan: "swatches" (list warna), "align_right" (nilai rata kanan).
        """
        sections = []

        # --- Section: Status ---
        if player.debug_found:
            status_text, status_color = "FOUND", (90, 230, 130)
        elif player.debug_visited:
            status_text, status_color = "NO PATH", (235, 100, 100)
        else:
            status_text, status_color = "IDLE", (150, 150, 155)

        status_lines = [("Status", status_text, status_color)]
        if status:
            status_lines.append(("Info", status[:26], (150, 160, 180)))

        sections.append({
            "header": "SEARCH",
            "header_color": (180, 200, 225),
            "lines": status_lines,
        })

        # --- Section: Statistics ---
        if player.debug_visited:
            heuristic_display = player.heuristic.upper()
            if heuristic_display == "UCS":
                heuristic_display = "UCS (h=0)"

            sections.append({
                "header": "STATISTICS",
                "header_color": (180, 200, 225),
                "align_right": True,
                "lines": [
                    ("Expanded", str(player.total_expanded), (200, 210, 230)),
                    ("Path len", str(len(player.debug_path)), (200, 210, 230)),
                    ("Heuristic", heuristic_display, (200, 210, 230)),
                ],
            })

        # --- Section: Legend ---
        sections.append({
            "header": "LEGEND",
            "header_color": (180, 200, 225),
            "swatches": [(70, 140, 255), (40, 220, 90), (0, 200, 255), (255, 220, 50)],
            "lines": [
                ("Visited (open set)", "", (200, 210, 230)),
                ("Path (solution)", "", (200, 210, 230)),
                ("Start node", "", (200, 210, 230)),
                ("Goal node", "", (200, 210, 230)),
            ],
        })

        # --- Section: Controls ---
        sections.append({
            "header": "CONTROLS",
            "header_color": (180, 200, 225),
            "lines": [
                ("1-4", "Toggle layers", (150, 165, 190)),
                ("Q/E", "Heuristic player", (150, 165, 190)),
                ("T/G", "Heuristic NPC", (150, 165, 190)),
                ("3 / ✕", "Hide this panel", (150, 165, 190)),
            ],
        })

        return sections


# ---------------------------------------------------------------------------
# Battle Debug Overlay - Visualisasi Adversarial Search saat BATTLE_MODE
# ---------------------------------------------------------------------------

class BattleDebugOverlay:
    """Panel debug untuk pencarian adversarial pada Turn-Based Battle Duel.

    Menampilkan:
    1. Skor evaluasi tiap aksi di root (depth 0), contoh:
       [ATTACK: +18, DEFEND: +15, POTION: -10, SPECIAL: +18]
    2. Perbandingan jumlah node Minimax murni vs Alpha-Beta Pruning.
    3. Efisiensi pruning (% node yang dipotong) dan waktu kalkulasi (ms).
    4. Opsional (``compare_mode``): tabel perbandingan Minimax vs Alpha-Beta vs
       Early Stop sekaligus, termasuk aksi yang dipilih masing-masing algoritma
       sehingga terlihat apakah ketiganya sepakat atau tidak.

    Attributes:
        visible: Apakah panel ditampilkan (toggle tombol 'D')
        compare_mode: Apakah panel menampilkan tabel 3 algoritma (tombol 'C')
        stats: Dict statistik terakhir dari AdversarialAI.think()
    """

    ACTION_COLOR = {
        "ATTACK": (240, 96, 96),
        "DEFEND": (96, 176, 240),
        "POTION": (120, 220, 140),
        "SPECIAL": (208, 150, 250),
    }

    COMPARE_LABEL = {
        "minimax": "Minimax (tanpa pruning)",
        "alphabeta": "Alpha-Beta Pruning",
        "early_stop": "Early Stop (decided-state)",
    }

    COMPARE_SHORT = {
        "minimax": "Minimax",
        "alphabeta": "Alpha-Beta",
        "early_stop": "Early Stop",
    }

    def __init__(self):
        self.visible = True
        self.compare_mode = False
        self.stats = {}

    def toggle(self):
        """Sembunyikan/tampilkan panel."""
        self.visible = not self.visible

    def toggle_compare(self):
        """Aktifkan/nonaktifkan tabel perbandingan tiga algoritma.

        Mode ini memakai ``AdversarialAI.compare_all()`` yang menjalankan
        ketiga algoritma pada state yang sama, jadi biayanya sekitar tiga kali
        pencarian biasa. Karena itu ia dimatikan secara default.
        """
        self.compare_mode = not self.compare_mode

    def update(self, stats):
        """Simpan statistik terbaru dari AI.

        Args:
            stats: Dict hasil AdversarialAI.think() atau compare_all()
        """
        if stats:
            self.stats = stats

    def draw(self, screen, font, safe_rect=None):
        """Gambar panel debug di tengah layar.

        Args:
            screen: Surface utama
            font: pygame Font monospace untuk isi panel
            safe_rect: Area layar yang boleh dipakai panel. Bila tidak diisi,
                panel memakai layar penuh dengan tirai gelap (mode modal).
        """
        if not self.visible or not self.stats:
            return

        sw, sh = screen.get_size()
        f = font
        line_h = f.get_height() + 3

        title = "DEBUG ADVERSARIAL SEARCH"
        hint = "[D] sembunyikan  [C] banding"
        depth = self.stats.get("depth", "-")
        algo = self.stats.get("algorithm", "alphabeta")
        if algo == "alphabeta":
            algo = "Alpha-Beta Pruning"
        elif algo == "minimax":
            algo = "Minimax"
        elif algo == "expectimax":
            algo = "Expectimax"
        elif algo == "iterative":
            algo = "Iterative Deepening"
        if self.compare_mode:
            algo += " + perbandingan"
        head = f"{title}   |   depth={depth}   |   {algo}"

        root = self.stats.get("root_scores") or []
        best = self.stats.get("best_action")
        comparison = self.stats.get("comparison") or {}

        mm_nodes = comparison.get("minimax", {}).get(
            "nodes", self.stats.get("minimax_nodes", 0)
        )
        ab_nodes = comparison.get("alphabeta", {}).get(
            "nodes", self.stats.get("alphabeta_nodes", 0)
        )
        pruned = self.stats.get("pruned_nodes", 0)
        eff = self.stats.get("prune_efficiency", 0.0)
        evals = self.stats.get("evaluations", 0)
        t_ms = self.stats.get("time_ms", 0.0)
        eval_name = self.stats.get("eval_name", "-")
        order_name = self.stats.get("order_name", "-")

        # --- Ukuran panel ---
        pad = 14
        marker = "<= dipilih"
        marker_w = f.size(marker)[0] + 8
        width = max(f.size(head)[0] + pad * 2, 430)

        label_max = 0
        for action, score in root:
            label_max = max(label_max, f.size(f"{action:<8}{score:+5d}")[0])
        width = max(width, label_max + 12 + 150 + 8 + marker_w + pad * 2)

        n_cmp = len(comparison) if comparison else 0
        cmp_lab_w = cmp_act_w = cmp_ex_w = 0
        if comparison:
            keys = [k for k in ("minimax", "alphabeta", "early_stop") if comparison.get(k)]
            cmp_lab_w = max(
                f.size(f"  {self.COMPARE_SHORT.get(k, self.COMPARE_LABEL.get(k, k))}")[0]
                for k in keys
            )
            cmp_act_w = max(
                f.size(str(comparison[k].get("best_action") or "-"))[0] for k in keys
            )
            for k in keys:
                row = comparison[k]
                extra = f"{row.get('nodes', 0)} node  {row.get('time_ms', 0.0):.2f} ms"
                if row.get("early_stop_hits"):
                    extra += f"  stop={row['early_stop_hits']}"
                cmp_ex_w = max(cmp_ex_w, f.size(extra)[0])
            width = max(width, cmp_lab_w + 12 + cmp_act_w + 12 + cmp_ex_w + pad * 2)

        width = min(width, sw - 40)

        # Bar skor dan marker harus tetap muat setelah lebar diklem.
        bar_space = width - pad * 2 - label_max - 12 - 8 - marker_w
        show_marker = bar_space >= 40
        bar_w = max(24, min(150, bar_space))
        marker_w = marker_w if show_marker else 0

        # Tinggi panel dihitung dari baris yang benar-benar digambar:
        # header, pemisah, judul "Pilihan aksi", baris skor (minimal 1),
        # judul "Perbandingan", 8 stat_line, bar efisiensi, tabel banding,
        # dan footer kontrol. `gaps` menjumlahkan jarak non-garis_baris:
        # pemisah 7px, spasi 5px, spasi 4px, bar 4px, dan footer 4+6px.
        cmp_extra = 0
        if comparison:
            cmp_extra = 1 + n_cmp  # header + satu baris per algoritma
            if self.stats.get("actions_agree") is not None:
                cmp_extra += 1  # baris pesan setuju/tidak
        root_rows = max(1, len(root))
        gaps = 7 + 5 + 4 + 4 + 4 + 6
        height = pad * 2 + gaps + line_h * (13 + root_rows + cmp_extra)

        # Panel digambar pada surface sendiri lalu diskalakan ke area aman,
        # sehingga isinya tidak pernah menimpa panel UI duel lain.
        target = screen
        content = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(content, (12, 16, 26, 236), content.get_rect(), border_radius=14)
        pygame.draw.rect(content, (120, 170, 255, 235), content.get_rect(), 2, border_radius=14)
        screen = content
        rect = content.get_rect()

        # --- Header ---
        cy = rect.y + pad
        screen.blit(
            _fit_text(f, head, (210, 226, 255), rect.width - pad * 2),
            (rect.x + pad, cy),
        )
        cy += line_h

        sep = pygame.Rect(rect.x + pad, cy, rect.width - pad * 2, 1)
        pygame.draw.rect(screen, (60, 74, 100), sep)
        cy += 7

        # --- Skor tiap aksi di root ---
        screen.blit(f.render("Pilihan aksi NPC di root (depth 0):", True, (240, 196, 96)), (rect.x + pad, cy))
        cy += line_h
        if not root:
            screen.blit(f.render("- (tidak ada aksi legal)", True, (170, 180, 200)), (rect.x + pad, cy))
            cy += line_h
        else:
            scores = [s for _, s in root]
            lo, hi = min(scores), max(scores)
            span = (hi - lo) or 1
            bar_x = rect.right - pad - marker_w - bar_w
            for action, score in root:
                chosen = action == best
                col = self.ACTION_COLOR.get(action, (200, 200, 200))
                label = f"{action:<8}{score:+5d}"
                screen.blit(
                    _fit_text(f, label, col if chosen else (200, 210, 230), bar_x - 12 - (rect.x + pad)),
                    (rect.x + pad, cy),
                )
                # Bar skor relatif (0..1)
                frac = (score - lo) / span if hi != lo else 0.5
                pygame.draw.rect(screen, (30, 36, 50), (bar_x, cy + 3, bar_w, line_h - 8), border_radius=4)
                pygame.draw.rect(screen, col, (bar_x, cy + 3, max(3, int(bar_w * frac)), line_h - 8), border_radius=4)
                if chosen and show_marker:
                    screen.blit(f.render(marker, True, (140, 240, 170)), (bar_x + bar_w + 6, cy))
                cy += line_h
        cy += 5

        # --- Perbandingan algoritma ---
        def stat_line(label, value, color=(200, 210, 230)):
            nonlocal cy
            vw = f.size(value)[0]
            screen.blit(
                _fit_text(f, label, (150, 165, 190), rect.width - pad * 2 - vw - 12),
                (rect.x + pad, cy),
            )
            screen.blit(_fit_text(f, value, color, vw), (rect.right - pad - vw, cy))
            cy += line_h

        screen.blit(f.render("Perbandingan algoritma (state sama):", True, (240, 196, 96)), (rect.x + pad, cy))
        cy += line_h
        stat_line("Node Minimax (tanpa pruning)", str(mm_nodes), (200, 210, 230))
        stat_line("Node Alpha-Beta (pruning)", str(ab_nodes), (140, 240, 170))
        stat_line("Node terpangkas", f"{pruned}  ({eff:.1f}%)", (255, 200, 120))
        stat_line("Cutoff alpha-beta", str(self.stats.get("cutoffs", 0)), (200, 210, 230))
        stat_line("Evaluasi daun (leaf)", str(evals), (200, 210, 230))
        stat_line("Waktu kalkulasi", f"{t_ms:.2f} ms", (120, 210, 255))
        stat_line("Fungsi evaluasi", str(eval_name), (200, 210, 230))
        stat_line("Urutan aksi", str(order_name), (200, 210, 230))
        cy += 4

        # Bar efisiensi pruning
        pygame.draw.rect(screen, (30, 36, 50), (rect.x + pad, cy + 3, rect.width - pad * 2, line_h - 6), border_radius=4)
        pygame.draw.rect(
            screen, (140, 240, 170),
            (rect.x + pad, cy + 3, max(3, int((rect.width - pad * 2) * min(1.0, eff / 100.0))), line_h - 6),
            border_radius=4,
        )
        cy += line_h + 4

        # --- Tabel perbandingan tiga algoritma (mode compare) ---
        if comparison:
            screen.blit(
                f.render("Aksi & biaya tiap algoritma:", True, (240, 196, 96)),
                (rect.x + pad, cy),
            )
            cy += line_h

            col_node = rect.right - pad
            col_lab = rect.x + pad
            col_act = col_lab + cmp_lab_w + 12
            for key in ("minimax", "alphabeta", "early_stop"):
                row = comparison.get(key)
                if not row:
                    continue
                label = self.COMPARE_SHORT.get(key, self.COMPARE_LABEL.get(key, key))
                col = self.ACTION_COLOR.get(row.get("best_action"), (200, 210, 230))
                screen.blit(
                    _fit_text(f, f"  {label}", (170, 180, 200), cmp_lab_w),
                    (col_lab, cy),
                )

                acted = f"{row.get('best_action') or '-'}"
                act_max = col_node - cmp_ex_w - 12 - col_act
                screen.blit(_fit_text(f, acted, col, act_max), (col_act, cy))

                extra = f"{row.get('nodes', 0)} node  {row.get('time_ms', 0.0):.2f} ms"
                if row.get("early_stop_hits"):
                    extra += f"  stop={row['early_stop_hits']}"
                ew = f.size(extra)[0]
                screen.blit(
                    _fit_text(f, extra, (200, 210, 230), ew), (col_node - ew, cy)
                )
                cy += line_h

            agree = self.stats.get("actions_agree")
            if agree is True:
                msg, mcol = "  Semua algoritma memilih aksi yang sama", (140, 240, 170)
            elif agree is False:
                msg, mcol = "  Ada algoritma yang memilih aksi berbeda", (255, 140, 140)
            else:
                msg, mcol = "", (200, 210, 230)
            if msg:
                screen.blit(
                    _fit_text(f, msg, mcol, rect.width - pad * 2), (rect.x + pad, cy)
                )
                cy += line_h

        # --- Footer: kontrol panel ---
        cy += 4
        screen.blit(
            _fit_text(f, hint, (150, 165, 190), rect.width - pad * 2), (rect.x + pad, cy + 6)
        )

        min_line = self.MIN_LINE
        self._place(target, content, safe_rect, (sw, sh), min_line / max(1, line_h))

    MIN_LINE = 15

    def _place(self, screen, content, safe_rect, screen_size, min_scale=1.0):
        """Tempatkan panel di area aman, atau sebagai modal bila tidak terbaca.

        Args:
            screen: Surface tujuan
            content: Surface panel yang sudah selesai digambar
            safe_rect: Area bebas yang boleh dipakai, atau None
            screen_size: Ukuran layar (w, h)
            min_scale: Skala minimum agar teks masih terbaca
        """
        sw, sh = screen_size
        width, height = content.get_size()
        area = pygame.Rect(0, 0, sw, sh)
        if safe_rect is not None and safe_rect.width > 0 and safe_rect.height > 0:
            area = safe_rect.clip(area)

        scale = min(1.0, area.width / width, area.height / height)
        if scale < min_scale:
            veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
            veil.fill((4, 6, 12, 176))
            screen.blit(veil, (0, 0))
            area = pygame.Rect(20, 20, sw - 40, sh - 40)
            scale = min(1.0, area.width / width, area.height / height)

        target_w = max(1, int(width * scale))
        target_h = max(1, int(height * scale))
        image = content if scale >= 1.0 else pygame.transform.smoothscale(
            content, (target_w, target_h)
        )
        dest = area.copy()
        dest.width, dest.height = target_w, target_h
        dest.center = area.center
        screen.blit(image, dest.topleft)

