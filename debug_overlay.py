"""
Debug overlay module - Visualisasi hasil pathfinding untuk debugging.

Modul ini menghandle:
1. Visualisasi visited nodes (kotak biru transparan)
2. Visualisasi path nodes (kotak merah)
3. Info panel (jumlah expanded, heuristic yang digunakan)
4. Toggle layers dengan keyboard (1, 2, 3)

Layer Debug:
- Layer 1 (tombol 1): Visited nodes - node-node yang diekspansi A*
- Layer 2 (tombol 2): Path nodes - jalur terpendek yang ditemukan
- Layer 3 (tombol 3): Info panel - jumlah expanded dan heuristic
"""
import pygame

from utils import game_pos


class DebugOverlay:
    """Manages debug visualization layers untuk pathfinding.

    Attributes:
        show_visited: Tampilkan visited nodes (kotak biru)
        show_path: Tampilkan path nodes (kotak merah)
        show_info: Tampilkan info panel (text)
    """

    def __init__(self):
        """Inisialisasi semua layer debug sebagai visible."""
        self.show_visited = True
        self.show_path = True
        self.show_info = True

    def toggle(self, key):
        """Toggle layer debug berdasarkan tombol yang ditekan.

        Mapping:
            K_1: Toggle visited nodes
            K_2: Toggle path nodes
            K_3: Toggle info panel

        Args:
            key: Tombol keyboard yang ditekan (pygame key constant)
        """
        if key == pygame.K_1:
            self.show_visited = not self.show_visited
        elif key == pygame.K_2:
            self.show_path = not self.show_path
        elif key == pygame.K_3:
            self.show_info = not self.show_info

    def draw_scaled(self, screen, player, font, viewport, hide_visited=False):
        """Gambar semua layer debug yang aktif ke layar.

        Visualisasi:
        - Visited nodes: Kotak biru transparan (70, 140, 255, 120)
        - Path nodes: Kotak merah (255, 70, 90)
        - Info text: Putih, di bagian atas tengah layar

        Args:
            screen: Surface utama untuk drawing
            player: Objek Player dengan debug_visited, debug_path, dll.
            font: pygame Font untuk rendering teks
            viewport: Objek Viewport untuk koordinat
            hide_visited: True untuk skip drawing visited (digunakan di edit mode)
        """
        # ---- Visited Nodes (kotak biru) ----
        # Node-node yang diekspansi oleh A* tapi bukan bagian dari path
        if self.show_visited and not hide_visited:
            for r, c in player.debug_visited:
                # Skip jika bagian dari path atau posisi player
                if (r, c) not in player.debug_path and (r, c) != (player.row, player.col):
                    x, y = game_pos(r, c, viewport)
                    size = max(3, int(9 * viewport.scale))
                    # Buat surface transparan untuk visited
                    s = pygame.Surface((size, size), pygame.SRCALPHA)
                    s.fill((70, 140, 255, 120))  # Biru transparan
                    screen.blit(s, (x - size // 2, y - size // 2))

        # ---- Path Nodes (kotak merah) ----
        # Jalur terpendek yang ditemukan oleh A*
        if self.show_path:
            for r, c in player.debug_path:
                x, y = game_pos(r, c, viewport)
                pygame.draw.rect(screen, (255, 70, 90), (x - 3, y - 3, 6, 6))

        # ---- Info Panel (text) ----
        # Menampilkan jumlah node expanded dan heuristic yang digunakan
        info = font.render(
            f"Expanded: {player.total_expanded} | Heuristic: {player.heuristic}",
            True,
            (255, 255, 255),
        )
        screen.blit(info, ((screen.get_width() - info.get_width()) // 2, 12))
