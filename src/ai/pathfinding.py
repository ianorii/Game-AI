"""
pathfinding.py - A* Search & Dijkstra Search (grid 4-arah)

- astar()     : A* dengan heuristik Manhattan. Menyimpan daftar OPEN (kuning)
                dan CLOSED (merah) untuk kebutuhan overlay debug [F1].
                Jika tujuan terblokir, mengembalikan jalur "best-effort"
                ke node terdekat (hero tetap bergerak mendekati tujuan).
- dijkstra()  : Dijkstra / Uniform-Cost Search untuk jalur patroli monster.
                Memakai networkx bila terinstal (lihat requirements.txt),
                jika tidak tersedia otomatis fallback ke implementasi internal.

Struktur SearchResult dipakai langsung oleh debug_overlay.py (F1).
"""

import heapq
import itertools
import math
from dataclasses import dataclass, field

try:                                   # opsional - lihat requirements.txt
    import networkx as nx
    HAS_NETWORKX = True
except Exception:                      # pragma: no cover
    nx = None
    HAS_NETWORKX = False

# empat arah: atas, kanan, bawah, kiri
DIRS4 = ((0, -1), (1, 0), (0, 1), (-1, 0))


@dataclass
class SearchResult:
    """Hasil pencarian jalur + jejak untuk visualisasi debug."""
    path: list = field(default_factory=list)      # list[(x,y)] menuju goal
    found: bool = False                           # False = goal terblokir/hilang
    open_set: set = field(default_factory=set)    # simpul pada OPEN list
    closed_set: set = field(default_factory=set)  # simpul pada CLOSED list
    nodes_expanded: int = 0
    cost: float = 0.0
    algorithm: str = "?"
    best_effort: tuple = None                     # simpul terdekat ke goal


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _reconstruct(came, node):
    path = [node]
    while node in came:
        node = came[node]
        path.append(node)
    path.reverse()
    return path[1:]        # tanpa simpul start


# ==============================================================================
# A* SEARCH
# ==============================================================================
def astar(width, height, start, goal, is_blocked, track=True):
    """
    A* 4-arah pada grid `width x height`.
    is_blocked(x, y) -> bool. Menyimpan open/closed list untuk overlay F1.
    """
    counter = itertools.count()
    open_heap = [(manhattan(start, goal), next(counter), start)]
    open_set = {start}
    closed = set()
    came = {}
    g = {start: 0.0}
    expanded = 0
    best_node, best_h = start, manhattan(start, goal)
    found = False

    while open_heap:
        _, _, node = heapq.heappop(open_heap)
        if node in closed:
            continue
        open_set.discard(node)
        closed.add(node)
        expanded += 1

        h_node = manhattan(node, goal)
        if h_node < best_h:
            best_h, best_node = h_node, node

        if node == goal:
            found = True
            break

        nx_, ny_ = node
        for dx, dy in DIRS4:
            nb = (nx_ + dx, ny_ + dy)
            if not (0 <= nb[0] < width and 0 <= nb[1] < height):
                continue
            if nb in closed:
                continue
            if is_blocked(*nb) and nb != goal:
                continue
            tentative = g[node] + 1.0
            if tentative < g.get(nb, math.inf):
                came[nb] = node
                g[nb] = tentative
                heapq.heappush(open_heap,
                               (tentative + manhattan(nb, goal), next(counter), nb))
                open_set.add(nb)

    if found:
        path = _reconstruct(came, goal)
        return SearchResult(path=path, found=True,
                            open_set=open_set if track else set(),
                            closed_set=closed if track else set(),
                            nodes_expanded=expanded, cost=g.get(goal, 0.0),
                            algorithm="A*")

    # goal terblokir -> jalur best-effort menuju simpul terdekat
    path = _reconstruct(came, best_node) if best_node in came else []
    return SearchResult(path=path, found=False,
                        open_set=open_set if track else set(),
                        closed_set=closed if track else set(),
                        nodes_expanded=expanded, cost=g.get(best_node, 0.0),
                        algorithm="A* (best-effort)", best_effort=best_node)


# ==============================================================================
# DIJKSTRA / UNIFORM-COST SEARCH
# ==============================================================================
def _dijkstra_internal(width, height, start, goal, is_blocked):
    dist = {start: 0.0}
    came = {}
    heap = [(0.0, next(itertools.count()), start)]
    closed = set()
    while heap:
        d, _, node = heapq.heappop(heap)
        if node in closed:
            continue
        closed.add(node)
        if node == goal:
            break
        nx_, ny_ = node
        for dx, dy in DIRS4:
            nb = (nx_ + dx, ny_ + dy)
            if not (0 <= nb[0] < width and 0 <= nb[1] < height):
                continue
            if is_blocked(*nb):
                continue
            nd = d + 1.0
            if nd < dist.get(nb, math.inf):
                dist[nb] = nd
                came[nb] = node
                heapq.heappush(heap, (nd, next(itertools.count()), nb))
    return dist, came


def dijkstra(width, height, start, goal, is_blocked, use_networkx=True):
    """
    Dijkstra (uniform cost) start -> goal. Dipakai monster untuk patroli.
    Jika networkx tersedia, graph grid dibangun lewat networkx dan
    nx.dijkstra_path dipakai; selain itu pakai implementasi internal.
    """
    # Untuk dunia open-world (grid besar), membangun ulang networkx graph
    # setiap kali monster repath terlalu mahal. Implementasi internal lebih
    # ringan karena berhenti begitu goal ditemukan.
    if use_networkx and HAS_NETWORKX and width * height <= 2000:
        try:
            G = nx.Graph()
            for y in range(height):
                for x in range(width):
                    if is_blocked(x, y):
                        continue
                    node = (x, y)
                    G.add_node(node)
                    for dx, dy in ((1, 0), (0, 1)):   # cukup edge tetangga unik
                        nb = (x + dx, y + dy)
                        if 0 <= nb[0] < width and 0 <= nb[1] < height and not is_blocked(*nb):
                            G.add_edge(node, nb, weight=1.0)
            if start in G and goal in G:
                path = [tuple(p) for p in nx.dijkstra_path(G, start, goal, weight="weight")]
                return SearchResult(path=path[1:], found=True,
                                    nodes_expanded=len(path), cost=len(path) - 1.0,
                                    algorithm="Dijkstra (networkx)")
            return SearchResult(found=False, algorithm="Dijkstra (networkx)")
        except Exception:
            pass    # jatuh ke implementasi internal bila networkx gagal

    dist, came = _dijkstra_internal(width, height, start, goal, is_blocked)
    if goal in came or goal == start:
        path = _reconstruct(came, goal) if goal != start else []
        return SearchResult(path=path, found=True, nodes_expanded=len(dist),
                            cost=dist.get(goal, 0.0), algorithm="Dijkstra")
    # best-effort: node dengan jarak terkecil
    if dist:
        best = min(dist, key=lambda n: manhattan(n, goal))
        path = _reconstruct(came, best)
        return SearchResult(path=path, found=False, nodes_expanded=len(dist),
                            cost=dist[best], algorithm="Dijkstra (best-effort)")
    return SearchResult(found=False, algorithm="Dijkstra")


def dijkstra_dist_map(width, height, start, is_blocked):
    """Peta jarak (dist, prev) dari `start` ke SEMUA simpul - utilitas patrol."""
    return _dijkstra_internal(width, height, start, (-1, -1), is_blocked)
