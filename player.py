"""
Player module - Pergerakan player dengan smooth interpolation.

Modul ini menghandle:
1. Manual movement (WASD/Arrow keys) - 1 cell per input
2. A* pathfinding (mouse click) - jalur otomatis ke target
3. Smooth interpolation untuk animasi gerak yang halus
4. Debug info untuk visualisasi (visited nodes, path, expanded count)

A* Pathfinding:
- Menggunakan heuristic yang bisa diganti (manhattan, euclidean, ucs)
- Mengembalikan path, visited nodes, dan jumlah node yang diekspansi
- Path berupa list of (row, col) dari start ke goal
"""
import math

import pygame

from game.map import CELL_SIZE
from game.pathfinding import astar
from game.map.utils import (
    draw_circle_debug,
    draw_sprite_smooth,
    game_pos,
    snap_to_walkable,
)


class Player:
    """Karakter player dengan manual movement dan A* pathfinding.

    Attributes:
        start_pos: Posisi awal (row, col) untuk reset
        row, col: Posisi grid saat ini
        sprite: Gambar karakter
        facing: Arah menghadap (-1 = kiri, 1 = kanan)
        heuristic: Nama heuristic untuk A* (default: "manhattan")
        target: Posisi target A* (row, col) atau None
        path: List of (row, col) jalur A*
        path_index: Index saat ini di dalam path
        debug_visited: Node-node yang diekspansi A* (untuk visualisasi)
        debug_path: Jalur yang ditemukan A* (untuk visualisasi)
        total_expanded: Jumlah total node yang diekspansi
        move_speed: Kecepatan gerak dalam pixels per second
        manual_interval: Jeda antar input manual (detik)
        manual_timer: Timer untuk jeda input manual
        smooth_r, smooth_c: Posisi floating-point untuk interpolasi halus
    """

    def __init__(self, row, col, sprite=None):
        """Inisialisasi player di posisi grid (row, col).

        Args:
            row: Baris awal di grid
            col: Kolom awal di grid
            sprite: pygame.Surface gambar karakter (opsional)
        """
        self.start_pos = (row, col)
        self.row, self.col = row, col
        self.sprite = sprite
        self.facing = 1  # -1 = kiri, 1 = kanan

        # Pathfinding
        self.heuristic = "manhattan"  # Default heuristic
        self.target = None  # Target A* (row, col) atau None
        self.path = []  # Jalur A* yang ditemukan
        self.path_index = 0  # Index saat ini di path

        # Debug info untuk visualisasi
        self.debug_visited = []  # Node-node yang diekspansi
        self.debug_path = []  # Jalur yang ditemukan
        self.total_expanded = 0  # Jumlah node expanded
        self.debug_node_data = {}  # Data g, h, f per node
        self.debug_found = False  # Apakah jalur ditemukan

        # Movement
        self.move_speed = 750.0  # pixels per second
        self.manual_interval = 0.012  # seconds between manual moves (anti-bounce)
        self.manual_timer = 0.0  # Timer countdown

        # Smooth movement interpolation
        # Menggunakan float agar animasi halus antar cell
        self.smooth_r = float(row)
        self.smooth_c = float(col)

        # Battle stats (adversarial search)
        self.battle_hp = 100
        self.battle_max_hp = 100
        self.battle_atk = 12
        self.battle_def = 5
        self.battle_potions = 3
        self.battle_heal = 30

    def snap_to_walkable(self, game_map):
        """Cari cell walkable terdekat jika posisi saat ini terblokir.

        Menggunakan BFS untuk mencari cell walkable terdekat.

        Args:
            game_map: Objek GameMap untuk cek walkability
        """
        snap_to_walkable(self, game_map)

    def set_target(self, row, col, game_map):
        """Set target posisi dan hitung jalur A* ke target.

        Alur:
        1. Validasi target (walkable dan dalam bounds)
        2. Jalankan A* dari posisi saat ini ke target
        3. Simpan path, visited nodes, dan expanded count
        4. Return True jika jalur ditemukan

        Args:
            row: Baris target di grid
            col: Kolom target di grid
            game_map: Objek GameMap

        Returns:
            True jika jalur valid ditemukan, False jika tidak
        """
        # Validasi target harus walkable
        if not game_map.is_walkable(row, col):
            self.target = None
            self.path = []
            self.path_index = 0
            return False

        # Jalankan A* pathfinding
        result = astar(
            game_map.get_grid(),
            (self.row, self.col),
            (row, col),
            heuristic_name=self.heuristic,
            allow_diagonal=False,  # Player hanya bisa bergerak 4 arah
        )

        # Simpan hasil untuk debug overlay
        self.debug_visited = result["visited"]
        self.debug_path = result["path"]
        self.total_expanded = result["total_expanded"]
        self.debug_node_data = result["node_data"]
        self.debug_found = result["found"]

        # Jika tidak ada jalur ditemukan
        if not result["found"]:
            self.target = None
            self.path = []
            self.path_index = 0
            return False

        # Set target dan path
        self.target = (row, col)
        self.path = result["path"]
        self.path_index = 0
        # Reset smooth position ke posisi grid
        self.smooth_r = float(self.row)
        self.smooth_c = float(self.col)
        return True

    def handle_input(self, keys, game_map, dt):
        """Proses keyboard input untuk manual movement (WASD / Arrow keys).

        Menggunakan timer untuk anti-bounce agar tidak terlalu cepat.
        Saat manual movement aktif, A* pathfinding dibatalkan.

        Args:
            keys: Array status keyboard dari pygame.key.get_pressed()
            game_map: Objek GameMap untuk cek walkability
            dt: Delta time dalam detik
        """
        # Update timer
        self.manual_timer = max(0.0, self.manual_timer - dt)
        if self.manual_timer > 0:
            return

        # Hitung delta movement
        dr = dc = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dr = -1  # Atas
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dr = 1   # Bawah
        elif keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dc = -1  # Kiri
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dc = 1   # Kanan

        if dr or dc:
            # Batalkan A* pathfinding yang sedang aktif
            self.target = None
            self.path = []
            self.path_index = 0

            # Hitung posisi baru
            nr, nc = self.row + dr, self.col + dc
            if game_map.is_walkable(nr, nc):
                # Update facing direction
                if dc:
                    self.facing = 1 if dc > 0 else -1
                # Update posisi grid dan smooth position
                self.row, self.col = nr, nc
                self.smooth_r, self.smooth_c = float(nr), float(nc)

            # Set timer untuk anti-bounce
            self.manual_timer = self.manual_interval

    def update(self, game_map, dt):
        """Update pergerakan player mengikuti jalur A* dengan smooth interpolation.

        Menggunakan budget-based movement:
        - Hitung jarak pixel yang bisa ditempuh dalam dt
        - Bergerak sepanjang path hingga budget habis
        - Jika cell berikutnya tidak walkable, recompute path

        Args:
            game_map: Objek GameMap
            dt: Delta time dalam detik
        """
        # Tidak ada target atau path kosong
        if self.target is None or not self.path:
            return

        # Sudah mencapai akhir path
        if self.path_index >= len(self.path):
            self.target = None
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

                # Jika cell berikutnya tidak walkable, recompute path
                if not game_map.is_walkable(nr, nc):
                    old_target = self.target
                    self.target = None
                    self.path = []
                    self.path_index = 0
                    self.set_target(*old_target, game_map)
                    return

                # Update facing direction
                if nc != self.col:
                    self.facing = 1 if nc > self.col else -1

                # Update posisi grid
                self.row, self.col = nr, nc
                self.path_index += 1

                # Cek apakah sudah mencapai target
                if (self.row, self.col) == self.target:
                    self.target = None
                    self.path = []
                    self.path_index = 0
                    break

    def reset(self):
        """Reset player ke posisi awal dan bersihkan semua state."""
        self.row, self.col = self.start_pos
        self.smooth_r, self.smooth_c = float(self.row), float(self.col)
        self.target = None
        self.path = []
        self.path_index = 0
        self.debug_visited = []
        self.debug_path = []
        self.total_expanded = 0
        self.debug_node_data = {}
        self.debug_found = False

    def get_pos(self):
        """Return posisi grid saat ini sebagai (row, col)."""
        return self.row, self.col

    def draw(self, screen, viewport):
        """Gambar sprite player di posisi smooth saat ini.

        Args:
            screen: Surface utama untuk drawing
            viewport: Objek Viewport untuk koordinat
        """
        draw_sprite_smooth(
            screen, self.sprite, self.smooth_r, self.smooth_c, viewport, self.facing
        )

    def draw_debug(self, screen, cell_size):
        """Gambar debug circle di posisi grid player.

        Args:
            screen: Surface utama
            cell_size: Ukuran cell dalam pixel
        """
        draw_circle_debug(screen, self.row, self.col, cell_size, (0, 200, 0))

    def draw_target(self, screen, viewport):
        """Gambar target indicator (lingkaran kuning) di posisi A* goal.

        Args:
            screen: Surface utama
            viewport: Objek Viewport
        """
        if self.target is None:
            return
        x, y = game_pos(*self.target, viewport)
        pygame.draw.circle(
            screen,
            (255, 235, 70),  # Kuning
            (x, y),
            max(5, int(8 * viewport.scale)),
            max(2, int(2 * viewport.scale)),  # Outline saja
        )

    def draw_target_debug(self, screen, cell_size):
        """Gambar debug target indicator di posisi goal grid.

        Args:
            screen: Surface utama
            cell_size: Ukuran cell dalam pixel
        """
        if self.target is None:
            return
        r, c = self.target
        cx = c * cell_size + cell_size // 2
        cy = r * cell_size + cell_size // 2
        pygame.draw.circle(screen, (255, 235, 70), (cx, cy), cell_size // 3, 3)
