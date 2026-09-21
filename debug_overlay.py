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

from map import CELL_SIZE
from utils import game_pos


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

        # ---- Visited Nodes (kotak biru) ----
        if self.show_visited and not hide_visited:
            size = max(3, int(9 * viewport.scale))
            if self._vis_buf is None or self._vis_buf_size != size:
                self._vis_buf = pygame.Surface((size, size), pygame.SRCALPHA)
                self._vis_buf.fill((70, 140, 255, 120))
                self._vis_buf_size = size
            for r, c in player.debug_visited:
                if (r, c) not in player.debug_path and (r, c) != (player.row, player.col):
                    x, y = game_pos(r, c, viewport)
                    screen.blit(self._vis_buf, (x - size // 2, y - size // 2))

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
        if self.show_info:
            self._draw_info_panel(screen, player, font, status)

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

    def _draw_info_panel(self, screen, player, font, status=""):
        """Gambar info panel di kiri atas layar.

        Panel berisi:
        - Judul "A* DEBUGGER"
        - Status pencarian
        - Statistik (expanded, path len, heuristic)
        - Legend warna
        - Kontrol

        Args:
            screen: Surface utama
            player: Objek Player
            font: pygame Font
            status: Status text dari game state
        """
        sw, sh = screen.get_size()
        panel_w = min(260, sw // 4)
        padding = 10
        line_h = 18

        # Hitung tinggi panel
        sections = self._get_panel_sections(player, status)
        total_lines = sum(len(s["lines"]) for s in sections) + len(sections) - 1
        panel_h = padding * 2 + total_lines * line_h + 8

        # Background panel
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((12, 16, 24, 210))

        # Border tipis
        pygame.draw.rect(panel, (60, 70, 90), panel.get_rect(), 1)

        # Garis pemisah antar section
        y_cursor = padding

        for si, section in enumerate(sections):
            # Header section
            if section.get("header"):
                header_surf = font.render(section["header"], True, section.get("header_color", (180, 190, 210)))
                panel.blit(header_surf, (padding, y_cursor))
                y_cursor += line_h

            # Isi section
            for text, color in section["lines"]:
                text_surf = font.render(text, True, color)
                panel.blit(text_surf, (padding + 4, y_cursor))
                y_cursor += line_h

            # Garis pemisah (kecuali section terakhir)
            if si < len(sections) - 1:
                y_cursor += 4
                pygame.draw.line(
                    panel, (50, 55, 70),
                    (padding, y_cursor - 2),
                    (panel_w - padding, y_cursor - 2),
                )
                y_cursor += 4

        screen.blit(panel, (10, 10))

    def _get_panel_sections(self, player, status=""):
        """Bangun data section untuk info panel.

        Args:
            player: Objek Player
            status: Status text dari game state

        Returns:
            List of dicts, tiap dict = {"header": str, "header_color": tuple, "lines": [(text, color)]}
        """
        sections = []

        # --- Section: Title + Status ---
        if player.debug_found:
            status_text = "FOUND"
            status_color = (80, 220, 120)
        elif player.debug_visited:
            status_text = "NO PATH"
            status_color = (220, 80, 80)
        else:
            status_text = "IDLE"
            status_color = (140, 140, 140)

        status_lines = [
            (f"Status   : {status_text}", status_color),
        ]
        if status:
            status_lines.append((f"Info     : {status[:30]}", (150, 160, 180)))

        sections.append({
            "header": "A* DEBUGGER",
            "header_color": (220, 230, 255),
            "lines": status_lines,
        })

        # --- Section: Statistics ---
        if player.debug_visited:
            heuristic_display = player.heuristic.upper()
            if heuristic_display == "UCS":
                heuristic_display = "UCS (h=0)"

            sections.append({
                "header": "STATISTICS",
                "header_color": (180, 190, 210),
                "lines": [
                    (f"Expanded : {player.total_expanded}", (200, 210, 230)),
                    (f"Path len : {len(player.debug_path)}", (200, 210, 230)),
                    (f"Heuristic: {heuristic_display}", (200, 210, 230)),
                ],
            })

        # --- Section: Legend ---
        sections.append({
            "header": "LEGEND",
            "header_color": (180, 190, 210),
            "lines": [
                ("[ ] Visited (open set)", (70, 140, 255)),
                ("[ ] Path (solution)", (40, 220, 90)),
                ("[ ] Start node", (0, 200, 255)),
                ("[ ] Goal node", (255, 220, 50)),
            ],
        })

        # --- Section: Controls ---
        sections.append({
            "header": "CONTROLS",
            "header_color": (180, 190, 210),
            "lines": [
                ("1/2/3/4  Toggle layers", (150, 160, 180)),
                ("Q/E      Heuristic", (150, 160, 180)),
                ("WASD     Move player", (150, 160, 180)),
                ("Click    A* to target", (150, 160, 180)),
            ],
        })

        return sections
