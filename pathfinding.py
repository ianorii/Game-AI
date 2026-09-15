"""
Pathfinding module - Implementasi A* dan UCS dengan multiple heuristic.

Modul ini mengimplementasikan:
1. A* (A-Star) algorithm dengan configurable heuristic
2. UCS (Uniform Cost Search) sebagai special case A* dengan h(n)=0
3. Multiple heuristic functions: Manhattan, Euclidean, UCS
4. Debug visualization data (visited nodes, path, expanded count)

A* Algorithm:
    f(n) = g(n) + h(n)
    - g(n): Cost aktual dari start ke node n
    - h(n): Heuristic estimate dari node n ke goal
    - f(n): Total estimated cost melalui node n

UCS (Uniform Cost Search):
    f(n) = g(n)  (h(n) = 0)
    - Menjelajahi semua node secara uniform berdasarkan cost g(n)
    - Selalu optimal untuk graf dengan non-negative edge weights
    - Lebih lambat dari A* karena tidak ada heuristic guidance

Heuristic Functions:
    - Manhattan: |dx| + |dy| - Best untuk 4-directional grids
    - Euclidean: sqrt(dx² + dy²) - Admissible tapi kurang informed
    - UCS: 0 - Tidak ada heuristic guidance
"""
import heapq
import math


# ---------------------------------------------------------------------------
# Heuristic Functions
# ---------------------------------------------------------------------------

def heuristic_manhattan(a, b):
    """Manhattan distance: |dx| + |dy|.

    Best untuk 4-directional grids (atas, bawah, kiri, kanan).
    Admissible: tidak pernah overestimate jarak aktual.
    Consistent: h(n) <= cost(n, n') + h(n') untuk semua neighbor n'.

    Formula: |a[0] - b[0]| + |a[1] - b[1]|

    Args:
        a: Tuple (row, col) posisi pertama
        b: Tuple (row, col) posisi kedua

    Returns:
        Manhattan distance (integer)
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def heuristic_euclidean(a, b):
    """Euclidean distance: sqrt(dx² + dy²).

    Admissible: tidak pernah overestimate jarak aktual.
    Kurang informed dari Manhattan untuk 4-directional grids karena
    mengasumsikan gerakan diagonal (yang tidak ada di grid 4-arah).

    Formula: sqrt((a[0]-b[0])² + (a[1]-b[1])²)

    Args:
        a: Tuple (row, col) posisi pertama
        b: Tuple (row, col) posisi kedua

    Returns:
        Euclidean distance (float)
    """
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def heuristic_ucs(a, b):
    """UCS heuristic: selalu return 0.

    Tidak ada heuristic guidance, menjelajahi semua arah secara uniform.
    Equivalent dengan BFS jika semua edge cost = 1.

    Args:
        a: Tuple (row, col) - tidak digunakan
        b: Tuple (row, col) - tidak digunakan

    Returns:
        0 (selalu)
    """
    return 0


# Heuristic lookup table untuk akses berdasarkan nama
HEURISTICS = {
    "manhattan": heuristic_manhattan,
    "euclidean": heuristic_euclidean,
    "ucs": heuristic_ucs,
}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Nilai cell yang bisa dilewati
WALKABLE = 0

# Arah gerakan 4-directional (atas, kanan, bawah, kiri)
DIRECTIONS_4 = [(-1, 0), (0, 1), (1, 0), (0, -1)]

# Arah gerakan 8-directional (+ diagonal)
DIRECTIONS_8 = DIRECTIONS_4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]

# Cost untuk gerakan diagonal
SQRT2 = math.sqrt(2)


# ---------------------------------------------------------------------------
# A* Algorithm
# ---------------------------------------------------------------------------

def astar(grid, start, goal, heuristic_name="manhattan", allow_diagonal=True):
    """Cari jalur terpendek dari start ke goal menggunakan A* algorithm.

    A* menggunakan priority queue (min-heap) untuk memilih node dengan f(n) terkecil.
    f(n) = g(n) + h(n), dimana:
    - g(n) = cost aktual dari start ke node n
    - h(n) = heuristic estimate dari node n ke goal

    Args:
        grid: 2D list dimana 0 = walkable, 1 = obstacle
        start: Tuple (row, col) posisi awal
        goal: Tuple (row, col) posisi goal
        heuristic_name: Nama heuristic ("manhattan", "euclidean", "ucs")
        allow_diagonal: True untuk 8-directional, False untuk 4-directional

    Returns:
        Dict dengan keys:
            - path: List of (row, col) dari start ke goal (excluding start)
            - visited: List of (row, col) urutan ekspansi node
            - total_expanded: Jumlah node yang diekspansi
            - found: True jika jalur ditemukan
    """
    rows = len(grid)
    cols = len(grid[0])

    # Validasi posisi start dan goal
    if not (0 <= start[0] < rows and 0 <= start[1] < cols):
        return _empty_result()
    if not (0 <= goal[0] < rows and 0 <= goal[1] < cols):
        return _empty_result()
    if grid[start[0]][start[1]] != WALKABLE or grid[goal[0]][goal[1]] != WALKABLE:
        return _empty_result()

    # Pilih heuristic function
    heuristic = HEURISTICS[heuristic_name]
    sr, sc = start
    gr, gc = goal
    directions = DIRECTIONS_8 if allow_diagonal else DIRECTIONS_4

    # Inisialisasi data structures
    INF = float('inf')

    # g_score[i] = cost terendah dari start ke node i
    # Menggunakan flat array untuk efisiensi: index = row * cols + col
    g_score = [INF] * (rows * cols)
    g_score[sr * cols + sc] = 0

    # came_from[i] = index node parent untuk reconstruct path
    came_from = [-1] * (rows * cols)

    # closed[i] = True jika node i sudah diekspansi
    closed = [False] * (rows * cols)

    # Priority queue: (f_score, counter, row, counter)
    # Counter menjamin FIFO order untuk f_score yang sama
    counter = 0
    h0 = heuristic(start, goal)
    open_set = [(h0, counter, sr, sc)]

    # List untuk menyimpan urutan visited nodes (untuk debug overlay)
    visited_order = []

    # ---- Main A* Loop ----
    while open_set:
        # Ambil node dengan f_score terkecil
        f, _, r, c = heapq.heappop(open_set)
        idx = r * cols + c

        # Skip jika sudah diproses (bisa ada duplikat di queue)
        if closed[idx]:
            continue
        closed[idx] = True
        visited_order.append((r, c))

        # Cek apakah sudah mencapai goal
        if r == gr and c == gc:
            path = _reconstruct_path(came_from, idx, sr, sc, cols)
            return {
                "path": path,
                "visited": visited_order,
                "total_expanded": len(visited_order),
                "found": True,
            }

        # Eksplorasi neighbor
        g_cur = g_score[idx]
        for dr, dc in directions:
            nr, nc = r + dr, c + dc

            # Cek bounds
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue

            # Cek walkability
            if grid[nr][nc] != WALKABLE:
                continue

            nidx = nr * cols + nc

            # Skip jika sudah diekspansi
            if closed[nidx]:
                continue

            # Hitung g_score baru
            # Cost: sqrt(2) untuk diagonal, 1 untuk cardinal
            move_cost = SQRT2 if (dr != 0 and dc != 0) else 1
            tg = g_cur + move_cost

            # Jika jalur baru lebih murah, update
            if tg < g_score[nidx]:
                g_score[nidx] = tg
                came_from[nidx] = idx
                counter += 1
                # f_score = g_score + heuristic
                f_score = tg + heuristic((nr, nc), goal)
                heapq.heappush(open_set, (f_score, counter, nr, nc))

    # Tidak ada jalur ditemukan
    return {
        "path": [],
        "visited": visited_order,
        "total_expanded": len(visited_order),
        "found": False,
    }


def _empty_result():
    """Return hasil kosong untuk input tidak valid."""
    return {"path": [], "visited": [], "total_expanded": 0, "found": False}


def _reconstruct_path(came_from, current_idx, start_r, start_c, cols):
    """Rekonstruksi jalur dari goal ke start menggunakan came_from array.

    Args:
        came_from: Array parent nodes
        current_idx: Index node goal
        start_r: Row node start
        start_c: Column node start
        cols: Jumlah kolom grid

    Returns:
        List of (row, col) dari start ke goal (excluding start)
    """
    path = []
    start_idx = start_r * cols + start_c
    while current_idx != start_idx:
        path.append((current_idx // cols, current_idx % cols))
        current_idx = came_from[current_idx]
    path.reverse()
    return path


# ---------------------------------------------------------------------------
# UCS (Uniform Cost Search)
# ---------------------------------------------------------------------------

def ucs(grid, start, goal, allow_diagonal=False):
    """Uniform Cost Search: A* dengan zero heuristic.

    UCS menjelajahi semua node secara uniform berdasarkan cost g(n).
    Equivalent dengan BFS jika semua edge cost = 1.

    Args:
        grid: 2D list dimana 0 = walkable, 1 = obstacle
        start: Tuple (row, col) posisi awal
        goal: Tuple (row, col) posisi goal
        allow_diagonal: True untuk 8-directional, False untuk 4-directional

    Returns:
        Dict sama seperti astar()
    """
    return astar(grid, start, goal, heuristic_name="ucs", allow_diagonal=allow_diagonal)


# ---------------------------------------------------------------------------
# Debug Visualization
# ---------------------------------------------------------------------------

def print_grid_with_path(grid, path, visited=None, start=None, goal=None):
    """Cetak visualisasi ASCII dari grid dengan path dan visited nodes.

    Legend:
        .  = walkable
        #  = obstacle
        x  = visited
        *  = path
        S  = start
        G  = goal

    Args:
        grid: 2D list grid
        path: List of (row, col) jalur
        visited: List of (row, col) node yang dikunjungi
        start: Tuple (row, col) posisi awal
        goal: Tuple (row, col) posisi goal
    """
    rows = len(grid)
    cols = len(grid[0])
    display = [['.' for _ in range(cols)] for _ in range(rows)]

    # Tandai obstacle
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                display[r][c] = '#'

    # Tandai visited nodes
    if visited:
        for r, c in visited:
            if display[r][c] == '.':
                display[r][c] = 'x'

    # Tandai path
    if path:
        for r, c in path:
            display[r][c] = '*'

    # Tandai start dan goal
    if start:
        display[start[0]][start[1]] = 'S'
    if goal:
        display[goal[0]][goal[1]] = 'G'

    # Cetak grid
    for r in range(rows):
        print(f"{r:2} " + "  ".join(display[r]))


# ---------------------------------------------------------------------------
# Standalone Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Grid test 10x10 dengan beberapa obstacle
    grid = [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 0, 0, 0, 1, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 1, 1, 1, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ]

    # Test semua heuristic
    for h_name in ["ucs", "manhattan", "euclidean"]:
        result = astar(grid, (0, 0), (9, 9), heuristic_name=h_name)
        print(
            f"{h_name}: path_len={len(result['path'])} "
            f"expanded={result['total_expanded']}"
        )
