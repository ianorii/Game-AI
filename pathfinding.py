"""
A* Pathfinding Algorithm with multiple heuristic support.

This module provides:
- A* search with configurable heuristics (Manhattan, Euclidean, Chebyshev, Octile)
- UCS (Uniform Cost Search) as a special case of A* with zero heuristic
- Returns path, visited nodes, and expansion count for debugging/visualization
"""
import heapq
import math


# ---------------------------------------------------------------------------
# Heuristic functions
# ---------------------------------------------------------------------------

def heuristic_manhattan(a, b):
    """Manhattan distance: |dx| + |dy|. Best for 4-directional grids."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def heuristic_euclidean(a, b):
    """Euclidean distance: sqrt(dx^2 + dy^2). Admissible but less informed."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def heuristic_chebyshev(a, b):
    """Chebyshev distance: max(|dx|, |dy|). For 8-directional grids."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def heuristic_octile(a, b):
    """Octile distance: optimized for 8-directional grids with diagonal movement."""
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def heuristic_ucs(a, b):
    """UCS heuristic: always returns 0 (no heuristic guidance)."""
    return 0


# Heuristic lookup table
HEURISTICS = {
    "manhattan": heuristic_manhattan,
    "euclidean": heuristic_euclidean,
    "chebyshev": heuristic_chebyshev,
    "octile": heuristic_octile,
    "ucs": heuristic_ucs,
}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WALKABLE = 0
DIRECTIONS_4 = [(-1, 0), (0, 1), (1, 0), (0, -1)]  # up, right, down, left


# ---------------------------------------------------------------------------
# A* algorithm
# ---------------------------------------------------------------------------

def astar(grid, start, goal, heuristic_name="manhattan", allow_diagonal=False):
    """Find the shortest path from start to goal using A* algorithm.

    Args:
        grid: 2D list where 0 = walkable, 1 = obstacle
        start: (row, col) tuple for starting position
        goal: (row, col) tuple for goal position
        heuristic_name: name of heuristic function to use
        allow_diagonal: reserved for future 8-directional movement

    Returns:
        dict with keys:
            - path: list of (row, col) from start to goal (excluding start)
            - visited: list of (row, col) in order they were expanded
            - total_expanded: number of nodes expanded
            - found: True if path to goal was found
    """
    rows = len(grid)
    cols = len(grid[0])

    # Validate start and goal positions
    if not (0 <= start[0] < rows and 0 <= start[1] < cols):
        return _empty_result()
    if not (0 <= goal[0] < rows and 0 <= goal[1] < cols):
        return _empty_result()
    if grid[start[0]][start[1]] != WALKABLE or grid[goal[0]][goal[1]] != WALKABLE:
        return _empty_result()

    heuristic = HEURISTICS[heuristic_name]
    sr, sc = start
    gr, gc = goal

    # Initialize data structures
    INF = float('inf')
    g_score = [INF] * (rows * cols)
    g_score[sr * cols + sc] = 0

    came_from = [-1] * (rows * cols)
    closed = [False] * (rows * cols)

    # Priority queue: (f_score, counter, row, col)
    # counter ensures FIFO order for equal f_scores
    counter = 0
    h0 = heuristic(start, goal)
    open_set = [(h0, counter, sr, sc)]

    visited_order = []

    # Main A* loop
    while open_set:
        f, _, r, c = heapq.heappop(open_set)
        idx = r * cols + c

        # Skip if already processed
        if closed[idx]:
            continue
        closed[idx] = True
        visited_order.append((r, c))

        # Check if we reached the goal
        if r == gr and c == gc:
            path = _reconstruct_path(came_from, idx, sr, sc, cols)
            return {
                "path": path,
                "visited": visited_order,
                "total_expanded": len(visited_order),
                "found": True,
            }

        # Explore neighbors
        g_cur = g_score[idx]
        for dr, dc in DIRECTIONS_4:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if grid[nr][nc] != WALKABLE:
                continue
            nidx = nr * cols + nc
            if closed[nidx]:
                continue

            # Calculate new g-score (all moves cost 1)
            tg = g_cur + 1
            if tg < g_score[nidx]:
                g_score[nidx] = tg
                came_from[nidx] = idx
                counter += 1
                f_score = tg + heuristic((nr, nc), goal)
                heapq.heappush(open_set, (f_score, counter, nr, nc))

    # No path found
    return {
        "path": [],
        "visited": visited_order,
        "total_expanded": len(visited_order),
        "found": False,
    }


def _empty_result():
    """Return an empty result dict for invalid inputs."""
    return {"path": [], "visited": [], "total_expanded": 0, "found": False}


def _reconstruct_path(came_from, current_idx, start_r, start_c, cols):
    """Reconstruct the path from goal to start using came_from array."""
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
    """Uniform Cost Search: A* with zero heuristic (explores uniformly)."""
    return astar(grid, start, goal, heuristic_name="ucs", allow_diagonal=allow_diagonal)


# ---------------------------------------------------------------------------
# Debug visualization
# ---------------------------------------------------------------------------

def print_grid_with_path(grid, path, visited=None, start=None, goal=None):
    """Print an ASCII visualization of the grid with path and visited nodes.

    Legend:
        .  = walkable
        #  = obstacle
        x  = visited
        *  = path
        S  = start
        G  = goal
    """
    rows = len(grid)
    cols = len(grid[0])
    display = [['.' for _ in range(cols)] for _ in range(rows)]

    # Mark obstacles
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                display[r][c] = '#'

    # Mark visited nodes
    if visited:
        for r, c in visited:
            if display[r][c] == '.':
                display[r][c] = 'x'

    # Mark path
    if path:
        for r, c in path:
            display[r][c] = '*'

    # Mark start and goal
    if start:
        display[start[0]][start[1]] = 'S'
    if goal:
        display[goal[0]][goal[1]] = 'G'

    # Print the grid
    for r in range(rows):
        print(f"{r:2} " + "  ".join(display[r]))


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
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

    for h_name in ["ucs", "manhattan", "euclidean", "chebyshev", "octile"]:
        result = astar(grid, (0, 0), (9, 9), heuristic_name=h_name)
        print(
            f"{h_name}: path_len={len(result['path'])} "
            f"expanded={result['total_expanded']}"
        )
