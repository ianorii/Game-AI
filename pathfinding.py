"""
A* Pathfinding Algorithm
- Grid-based 2D pathfinding
- Multiple heuristic functions
- Debug info: expanded nodes, visited nodes, path, total node expanded count
"""

import heapq
import math

# --- Heuristic Functions ---
# Semua menerima (row, col) untuk node a dan b

def heuristic_manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def heuristic_euclidean(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

def heuristic_chebyshev(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

def heuristic_octile(a, b):
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)

# UCS menggunakan h=0 (heuristic trivial)
def heuristic_ucs(a, b):
    return 0

# Registry heuristic agar mudah dipilih dari luar
HEURISTICS = {
    "manhattan": heuristic_manhattan,
    "euclidean": heuristic_euclidean,
    "chebyshev": heuristic_chebyshev,
    "octile": heuristic_octile,
    "ucs": heuristic_ucs,
}

# --- Grid Constants ---
WALKABLE = 0
OBSTACLE = 1

# 4 arah: atas, kanan, bawah, kiri
DIRECTIONS_4 = [(-1, 0), (0, 1), (1, 0), (0, -1)]
# 8 arah (termasuk diagonal)
DIRECTIONS_8 = [(-1, 0), (-1, 1), (0, 1), (1, 1),
                (1, 0), (1, -1), (0, -1), (-1, -1)]

def astar(grid, start, goal, heuristic_name="manhattan", allow_diagonal=False):
    rows = len(grid)
    cols = len(grid[0])

    # validasi start dan goal ada di dalam grid
    if not (0 <= start[0] < rows and 0 <= start[1] < cols):
        return {"path": [], "visited": [], "total_expanded": 0, "found":False}
    if not (0 <= goal[0] < rows and 0 <= goal[1] < cols):
        return {"path": [], "visited": [], "total_expanded": 0, "found":False}
    if (grid[start[0]][start[1]] != WALKABLE or grid[goal[0]][goal[1]] != WALKABLE):
        return {"path": [], "visited": [], "total_expanded": 0, "found":False}

    heuristic = HEURISTICS[heuristic_name]
    directions = DIRECTIONS_8 if allow_diagonal else DIRECTIONS_4

    # priority queue : (f_score, counter, row, col)
    counter = 0
    open_set = []
    heapq.heappush(open_set, (0, counter, start[0], start[1]))

    # g_score[row][col] = cost terbaik dari start
    g_score = [[float('inf')] * cols for _ in range(rows)]
    g_score[start[0]][start[1]] = 0;

    # came_from[row][col] = predecessor (row, col)
    came_from = [[None] * cols for _ in range(rows)]

    # untuk node yang sudah di-expand
    visited_order = []

    # set untuk cek apakah sudah di-expand
    closed = set()

    while open_set:
        _, _, r, c = heapq.heappop(open_set)

        # skip jika sudah di-expand
        if(r, c) in closed:
            continue
        closed.add((r, c))
        visited_order.append((r, c))

        # goal reached
        if(r, c) == goal:
            path = _reconstruct_path(came_from, start, goal)
            return {
                "path": path,
                "visited": visited_order,
                "total_expanded": len(visited_order),
                "found": True,
            }

        # expand neighbors
        for dr, dc in directions:
            nr, nc = r+dr, c+dc

            # validasi bounds
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            
            if grid[nr][nc] != WALKABLE:
                continue

            # cost dari start ke neighbor
            # diagnola = sqrt(2) ~ 1.414
            move_cost = math.sqrt(2) if (dr != 0 and dc != 0) else 1
            tentative_g = g_score[r][c] + move_cost

            if tentative_g < g_score[nr][nc]:
                g_score[nr][nc] = tentative_g
                f_score = tentative_g + heuristic((nr, nc), goal)
                came_from[nr][nc] = (r, c)
                counter += 1
                heapq.heappush(open_set, (f_score, counter, nr, nc))

    # tidak ada path
    return {
        "path": [],
        "visited": visited_order,
        "total_expanded": len(visited_order),
        "found": False,
    }


def _reconstruct_path(came_from, start, goal):
    """Rekonstruksi path dari came_from dict."""
    path = []
    current = goal
    while current != start:
        path.append(current)
        current = came_from[current[0]][current[1]]
        if current is None:
            return []  # broken path, seharusnya tidak terjadi
    path.reverse()
    return path


# --- UCS (Uniform Cost Search) ---
# UCS = A* dengan h=0, jadi cukup panggil astar dengan heuristic="ucs"
def ucs(grid, start, goal, allow_diagonal=False):
    return astar(grid, start, goal, heuristic_name="ucs", allow_diagonal=allow_diagonal)


# --- Fungsi bantu untuk debug ---
def print_grid_with_path(grid, path, visited=None, start=None, goal=None):
    """
    Cetak grid ke console dengan path ditandai.
    - 'S' = start, 'G' = goal
    - '*' = path
    - 'x' = visited (expanded node)
    - '#' = obstacle
    - '.' = walkable
    """
    rows = len(grid)
    cols = len(grid[0])
    display = [['.' for _ in range(cols)] for _ in range(rows)]

    # Tandai obstacle
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == OBSTACLE:
                display[r][c] = '#'

    # Tandai visited (expanded nodes)
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

    # Cetak
    header = "   " + " ".join(f"{c:2}" for c in range(cols))
    print(header)
    for r in range(rows):
        row_str = f"{r:2} " + "  ".join(display[r])
        print(row_str)


# --- Main (test driver) ---
if __name__ == "__main__":
    # Contoh grid 10x10
    # 0 = jalan, 1 = obstacle
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

    start = (0, 0)
    goal = (9, 9)

    print("=" * 60)
    print("A* PATHFINDING - PERBANDINGAN HEURISTIK")
    print("=" * 60)
    print(f"Start: {start}, Goal: {goal}")
    print()

    for h_name in ["ucs", "manhattan", "euclidean", "chebyshev", "octile"]:
        result = astar(grid, start, goal, heuristic_name=h_name)

        print(f"--- {h_name.upper()} ---")
        print(f"  Path found: {result['found']}")
        print(f"  Path length: {len(result['path'])} langkah")
        print(f"  Total expanded nodes: {result['total_expanded']}")

        if result['found']:
            print_grid_with_path(grid, result['path'], result['visited'], start, goal)
        print()

    # Test tanpa path (terhalang)
    grid_blocked = [
        [0, 0, 1],
        [1, 1, 1],
        [0, 0, 0],
    ]
    print("=" * 60)
    print("TEST: Path terhalang")
    print("=" * 60)
    result = astar(grid_blocked, (0, 0), (2, 2), heuristic_name="manhattan")
    print(f"  Path found: {result['found']}")
    print(f"  Total expanded: {result['total_expanded']}")
    print_grid_with_path(grid_blocked, result['path'], result['visited'], (0, 0), (2, 2))
