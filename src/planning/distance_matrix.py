"""
distance_matrix.py - Matriks Jarak Nyata A* antar Lokasi Dunia

Menghitung jarak sebenarnya (panjang jalur A* dibagi kecepatan hero)
antara semua titik lokasi di config.LOCATIONS.
Mendukung:
  - Caching matriks (loc_a, loc_b) -> (durasi_detik, jumlah_tile, path)
  - Invalidasi saat collision berubah (editor F1, jembatan, gerbang)
  - Deteksi tak terjangkau (durasi = float('inf'))
"""

from typing import Dict, Tuple, List, Optional, Any
import math

import config
from ai.pathfinding import astar


class DistanceMatrix:
    """
    Mengelola perhitungan dan caching jarak A* nyata antar lokasi di dunia Sunnyside.
    """

    def __init__(self, game_map: Any = None, locations: Optional[Dict[str, Tuple[int, int]]] = None,
                 hero_speed_tps: float = config.HERO_SPEED_TPS):
        if game_map is None:
            try:
                from world.game_map import GameMap
                game_map = GameMap()
            except Exception:
                game_map = None
        self.game_map = game_map
        self.locations = dict(locations or getattr(config, "LOCATIONS", {}))
        self.hero_speed_tps = hero_speed_tps
        self._cache: Dict[Tuple[str, str, bool], Tuple[float, int, List[Tuple[int, int]]]] = {}
        self._collision_version: int = 0
        self.width_tiles = 86
        self.height_tiles = 48

    def invalidate(self):
        """Mengosongkan cache matriks jarak bila terjadi perubahan rintangan/collision."""
        self._cache.clear()
        self._collision_version += 1

    def get_distance(self, loc_a: str, loc_b: str, gate_open: bool = False) -> Tuple[float, int, List[Tuple[int, int]]]:
        """
        Mengembalikan (durasi_detik, jumlah_langkah_tile, path_astar).
        Bila tak terjangkau, mengembalikan (float('inf'), 0, []).
        """
        if loc_a == loc_b:
            return 0.0, 0, []

        cache_key = (loc_a, loc_b, gate_open)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if loc_a not in self.locations or loc_b not in self.locations:
            return float("inf"), 0, []

        pos_a = self.locations[loc_a]
        pos_b = self.locations[loc_b]

        cell_a = (int(pos_a[0] // 32), int(pos_a[1] // 32))
        cell_b = (int(pos_b[0] // 32), int(pos_b[1] // 32))

        # Fungsi is_blocked berdasarkan game_map dan status gerbang
        def is_blocked(cx: int, cy: int) -> bool:
            px = cx * 32 + 16
            py = cy * 32 + 16

            # Gerbang: bentang chokepoint (2336..2624, 800..880) tertutup bila not gate_open
            if not gate_open and (2320 <= px <= 2630) and (784 <= py <= 896):
                return True

            if self.game_map is not None:
                # Bila gate_open=True, jangan biarkan obstacle dinamis gerbang di game_map memblokir
                if gate_open and (2320 <= px <= 2630) and (784 <= py <= 896):
                    if hasattr(self.game_map, "walkable_mask") and self.game_map.walkable_mask:
                        if 0 <= px < self.game_map.width and 0 <= py < self.game_map.height:
                            return not bool(self.game_map.walkable_mask.get_at((px, py)))
                if hasattr(self.game_map, "is_walkable_at"):
                    return not self.game_map.is_walkable_at(px, py)
                elif hasattr(self.game_map, "is_walkable"):
                    return not self.game_map.is_walkable(cx, cy)
            return False

        res = astar(self.width_tiles, self.height_tiles, cell_a, cell_b, is_blocked)

        if not res.found or not res.path:
            # Tidak terjangkau
            result = (float("inf"), 0, [])
        else:
            tile_steps = len(res.path)
            duration_sec = tile_steps / self.hero_speed_tps
            result = (duration_sec, tile_steps, res.path)

        self._cache[cache_key] = result
        return result

    def get_all_pairs(self, gate_open: bool = False) -> Dict[Tuple[str, str], float]:
        """Menghitung seluruh pasangan lokasi untuk analisis jaringan dan problem generation."""
        matrix = {}
        for a in self.locations:
            for b in self.locations:
                if a == b:
                    matrix[(a, b)] = 0.0
                else:
                    dur, _, _ = self.get_distance(a, b, gate_open=gate_open)
                    matrix[(a, b)] = dur
        return matrix

