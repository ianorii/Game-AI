"""
NPC module - Pergerakan NPC untuk mengejar player menggunakan A* pathfinding.

Modul ini menghandle:
1. NPC follow behavior - mengejar player menggunakan A* pathfinding
2. Periodic path recomputation - menghitung ulang jalur setiap 0.1 detik
3. Smooth interpolation untuk animasi gerak
4. Dialogue bubble saat NPC dekat dengan player
5. Debug info untuk visualisasi

NPC Follow Behavior:
- NPC secara periodik menghitung ulang jalur ke player (recompute)
- Ini diperlukan karena posisi player berubah-ubah
- NPC bergerak lebih lambat dari player (600 px/s vs 750 px/s)
- NPC berhenti jika sudah dekat dengan player (Manhattan distance <= 1)
"""
import math

import pygame

from game.map import CELL_SIZE
from game.pathfinding import astar
from game.map.utils import (
    draw_sprite_smooth,
    game_pos,
    snap_to_walkable,
)


class NPC:
    """Karakter NPC yang bisa mengikuti player menggunakan pathfinding.

    Attributes:
        start_pos: Posisi awal (row, col) untuk reset
        row, col: Posisi grid saat ini
        sprite: Gambar karakter NPC
        name: Nama NPC untuk dialogue
        facing: Arah menghadap (-1 = kiri, 1 = kanan)
        follow: Mode follow (True = ikuti player, False = diam)
        heuristic: Nama heuristic untuk A* (default: "ucs")
        move_speed: Kecepatan gerak (600 px/s, lebih lambat dari player)
        recompute_interval: Interval recompute path (0.1 detik)
        path: Jalur A* yang ditemukan
        path_index: Index saat ini di path
        timer: Timer untuk recomputation
        recompute_timer: Timer untuk periodic recomputation
        debug_visited: Node-node yang diekspansi (untuk visualisasi)
        debug_path: Jalur yang ditemukan (untuk visualisasi)
        total_expanded: Jumlah total node yang diekspansi
        smooth_r, smooth_c: Posisi floating-point untuk interpolasi
    """

    def __init__(self, row, col, sprite=None, name="Niko"):
        """Inisialisasi NPC di posisi grid (row, col).

        Args:
            row: Baris awal di grid
            col: Kolom awal di grid
            sprite: pygame.Surface gambar karakter (opsional)
            name: Nama NPC untuk dialogue
        """
        self.start_pos = (row, col)
        self.row, self.col = row, col
        self.sprite = sprite
        self.name = name
        self.facing = -1  # -1 = kiri, 1 = kanan

        # Follow mode - NPC mengikuti player
        self.follow = True
        self.heuristic = "ucs"  # Default: UCS (uniform exploration)

        # Movement - lebih lambat dari player
        self.move_speed = 600.0  # pixels per second (player: 750)
        self.recompute_interval = 0.10  # seconds between path recomputations

        # Pathfinding state
        self.path = []  # Jalur A* yang ditemukan
        self.path_index = 0  # Index saat ini di path
        self.timer = 0.0  # Timer umum
        self.recompute_timer = 0.0  # Timer untuk recompute path

        # Debug info untuk visualisasi
        self.debug_visited = []  # Node-node yang diekspansi
        self.debug_path = []  # Jalur yang ditemukan
        self.total_expanded = 0  # Jumlah node expanded
        self.debug_node_data = {}  # Data g, h, f per node
        self.debug_found = False  # Apakah jalur ditemukan

        # Smooth movement interpolation
        self.smooth_r = float(row)
        self.smooth_c = float(col)

        # Cached dialogue panel
        self._dlg_panel = None
        self._dlg_size = (0, 0)

    def reset(self):
        """Reset NPC ke posisi awal dan bersihkan semua state."""
        self.row, self.col = self.start_pos
        self.facing = -1
        self.smooth_r, self.smooth_c = float(self.row), float(self.col)
        self.path = []
        self.path_index = 0
        self.timer = 0.0
        self.recompute_timer = 0.0
        self.debug_visited = []
        self.debug_path = []
        self.total_expanded = 0
        self.debug_node_data = {}
        self.debug_found = False

    def set_heuristic(self, heuristic):
        """Set heuristic function untuk pathfinding.

        Args:
            heuristic: Nama heuristic ("ucs", "manhattan", "euclidean")
        """
        self.heuristic = heuristic

    def snap_to_walkable(self, game_map):
        """Cari cell walkable terdekat jika posisi saat ini terblokir.

        Args:
            game_map: Objek GameMap untuk cek walkability
        """
        snap_to_walkable(self, game_map)

    def get_pos(self):
        """Return posisi grid saat ini sebagai (row, col)."""
        return self.row, self.col

    def is_near(self, player):
        """Cek apakah NPC dekat dengan player (Manhattan distance <= 1).

        Digunakan untuk menampilkan dialogue bubble.

        Args:
            player: Objek Player

        Returns:
            True jika NPC bersebelahan dengan player
        """
        return abs(self.row - player.row) + abs(self.col - player.col) <= 1

    def update(self, game_map, player, dt):
        """Update pergerakan NPC mengejar player.

        Alur:
        1. Jika follow mode OFF, return langsung
        2. Periodic recomputation path (setiap 0.1 detik)
        3. Jalankan A* dari posisi NPC ke posisi player
        4. Simpan path (exclude posisi player agar NPC berhenti di dekat player)
        5. Bergerak mengikuti path dengan smooth interpolation

        Args:
            game_map: Objek GameMap
            player: Objek Player (target NPC)
            dt: Delta time dalam detik
        """
        # Jika follow mode mati, tidak bergerak
        if not self.follow:
            return

        # Periodic recomputation path
        self.recompute_timer -= dt
        if self.recompute_timer <= 0:
            self.recompute_timer = self.recompute_interval

            # Jalankan A* dari NPC ke player
            result = astar(
                game_map.get_grid(),
                (self.row, self.col),
                (player.row, player.col),
                heuristic_name=self.heuristic,
                allow_diagonal=False,  # NPC bergerak 4 arah
            )

            # Simpan debug info
            self.debug_visited = result["visited"]
            self.debug_path = result["path"]
            self.total_expanded = result["total_expanded"]
            self.debug_node_data = result["node_data"]
            self.debug_found = result["found"]

            if result["found"]:
                # Exclude goal (posisi player) agar NPC berhenti di dekat player
                self.path = result["path"][:-1]
            else:
                self.path = []
            self.path_index = 0
            # Reset smooth position
            self.smooth_r = float(self.row)
            self.smooth_c = float(self.col)

        # Bergerak mengikuti path
        if not self.path or self.path_index >= len(self.path):
            return

        # Budget = jarak yang bisa ditempuh dalam dt
        budget = self.move_speed * dt

        # Bergerak sepanjang path hingga budget habis
        while budget > 0 and self.path_index < len(self.path):
            # Hitung jarak pixel dari smooth position ke posisi grid
            dr = self.row - self.smooth_r
            dc = self.col - self.smooth_c
            pixel_dist = math.sqrt(dr * dr + dc * dc) * CELL_SIZE

            if pixel_dist > budget:
                # Masih ada sisa budget, interpolasi partial
                ratio = budget / pixel_dist
                self.smooth_r += dr * ratio
                self.smooth_c += dc * ratio
                budget = 0
            else:
                # Budget cukup untuk sampai ke cell berikutnya
                self.smooth_r = float(self.row)
                self.smooth_c = float(self.col)
                budget -= pixel_dist

                # Ambil cell berikutnya dari path
                nr, nc = self.path[self.path_index]

                # Cek walkability sebelum bergerak
                if game_map.is_walkable(nr, nc):
                    # Update facing direction
                    if nc != self.col:
                        self.facing = 1 if nc > self.col else -1
                    # Update posisi
                    self.row, self.col = nr, nc
                self.path_index += 1

    def draw(self, screen, viewport):
        """Gambar sprite NPC di posisi smooth saat ini.

        Args:
            screen: Surface utama untuk drawing
            viewport: Objek Viewport untuk koordinat
        """
        draw_sprite_smooth(
            screen, self.sprite, self.smooth_r, self.smooth_c, viewport, self.facing
        )

    def draw_debug(self, screen, cell_size):
        """Gambar debug circle di posisi grid NPC.

        Args:
            screen: Surface utama
            cell_size: Ukuran cell dalam pixel
        """
        from utils import draw_circle_debug
        draw_circle_debug(screen, self.row, self.col, cell_size, (200, 50, 50))

    def draw_dialogue(self, screen, viewport, font, player):
        """Tampilkan dialogue bubble saat NPC dekat dengan player.

        Dialogue ditampilkan di atas NPC dengan panel gelap transparan.

        Args:
            screen: Surface utama
            viewport: Objek Viewport
            font: pygame Font untuk rendering teks
            player: Objek Player
        """
        # Hanya tampilkan jika dekat dengan player
        if not self.is_near(player):
            return

        x, y = game_pos(self.row, self.col, viewport)
        text = f"{self.name}: ketangkep kamu"
        surf = font.render(text, True, (255, 255, 255))
        box = surf.get_rect(midtop=(x, y + int(8 * viewport.scale)))

        # Gambar panel background dialogue
        panel_size = (box.width + 18, box.height + 12)
        if self._dlg_panel is None or self._dlg_size != panel_size:
            self._dlg_panel = pygame.Surface(panel_size, pygame.SRCALPHA)
            self._dlg_panel.fill((15, 20, 30, 225))
            self._dlg_size = panel_size
        screen.blit(self._dlg_panel, (box.x - 9, box.y - 6))
        screen.blit(surf, box)
