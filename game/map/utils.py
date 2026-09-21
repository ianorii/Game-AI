"""
Utils module - Fungsi utilitas untuk rendering sprite dan mencari cell walkable.

Modul ini menyediakan fungsi-fungsi yang digunakan oleh Player dan NPC:
1. snap_to_walkable: BFS untuk mencari cell walkable terdekat
2. game_pos: Konversi grid position ke screen pixel coordinates
3. draw_sprite: Gambar sprite di posisi grid (snapped)
4. draw_sprite_smooth: Gambar sprite di posisi floating-point (interpolasi)
5. draw_circle_debug: Gambar debug circle di posisi grid
"""
import math
import pygame

from collections import deque
from game.map import CELL_SIZE


def snap_to_walkable(entity, game_map):
    """Cari cell walkable terdekat dari posisi entity menggunakan BFS.

    Jika posisi entity saat ini tidak walkable, BFS mencari cell walkable
    terdekat dan memindahkan entity ke sana.

    Alur BFS:
    1. Mulai dari posisi entity
    2. Eksplorasi neighbor secara berurutan (4 arah)
    3. Jika neighbor walkable, pindahkan entity ke sana
    4. Jika tidak, tambahkan ke queue untuk dieksplorasi

    Args:
        entity: Objek dengan atribut row, col, smooth_r, smooth_c, start_pos
        game_map: Objek GameMap untuk cek walkability

    Returns:
        None (entity dipindahkan secara in-place)
    """
    # Jika sudah walkable, tidak perlu mencari
    if game_map.is_walkable(entity.row, entity.col):
        entity.start_pos = (entity.row, entity.col)
        return

    # BFS untuk mencari cell walkable terdekat
    start = (entity.row, entity.col)
    seen = {start}
    queue = deque([start])

    while queue:
        r, c = queue.popleft()
        # Eksplorasi 4 arah (atas, bawah, kiri, kanan)
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc

            # Skip jika sudah dikunjungi atau tidak valid
            if not game_map.is_valid(nr, nc) or (nr, nc) in seen:
                continue
            seen.add((nr, nc))

            # Jika walkable, pindahkan entity
            if game_map.is_walkable(nr, nc):
                entity.row, entity.col = entity.start_pos = (nr, nc)
                entity.smooth_r, entity.smooth_c = float(nr), float(nc)
                return

            # Tambahkan ke queue untuk dieksplorasi
            queue.append((nr, nc))


def game_pos(row, col, viewport):
    """Konversi grid position (row, col) ke screen pixel coordinates.

    Menghitung posisi tengah cell dalam koordinat layar.

    Args:
        row: Baris di grid
        col: Kolom di grid
        viewport: Objek Viewport dengan map_rect dan scale

    Returns:
        Tuple (x, y) koordinat pixel di layar
    """
    return (
        viewport.map_rect.x + int((col + 0.5) * CELL_SIZE * viewport.scale),
        viewport.map_rect.y + int((row + 0.5) * CELL_SIZE * viewport.scale),
    )


def draw_sprite(screen, sprite, row, col, viewport, facing=1):
    """Gambar sprite di posisi grid (snapped to cell center).

    Sprite di-scale berdasarkan viewport.scale dan di-flip
    berdasarkan direction facing.

    Args:
        screen: Surface utama untuk drawing
        sprite: pygame.Surface gambar sprite
        row: Baris di grid
        col: Kolom di grid
        viewport: Objek Viewport
        facing: Arah menghadap (-1 = kiri, 1 = kanan)
    """
    if sprite is None:
        return

    # Scale sprite berdasarkan viewport
    width = max(28, int(sprite.get_width() * viewport.scale))
    height = max(42, int(sprite.get_height() * viewport.scale))
    scaled = pygame.transform.scale(sprite, (width, height))

    # Flip horizontal jika menghadap kiri
    if facing < 0:
        scaled = pygame.transform.flip(scaled, True, False)

    # Posisi tengah cell
    x, y = game_pos(row, col, viewport)
    # Gambar sprite (di-center horizontal, di-anchor ke bawah)
    screen.blit(scaled, (x - width // 2, y - height + max(2, int(4 * viewport.scale))))


def draw_sprite_smooth(screen, sprite, smooth_r, smooth_c, viewport, facing=1):
    """Gambar sprite di posisi floating-point untuk animasi halus.

    Sama seperti draw_sprite tapi menggunakan posisi smooth (float)
    untuk interpolasi antar cell.

    Args:
        screen: Surface utama untuk drawing
        sprite: pygame.Surface gambar sprite
        smooth_r: Posisi row floating-point
        smooth_c: Posisi col floating-point
        viewport: Objek Viewport
        facing: Arah menghadap (-1 = kiri, 1 = kanan)
    """
    if sprite is None:
        return

    # Scale sprite
    width = max(28, int(sprite.get_width() * viewport.scale))
    height = max(42, int(sprite.get_height() * viewport.scale))
    scaled = pygame.transform.scale(sprite, (width, height))

    # Flip jika menghadap kiri
    if facing < 0:
        scaled = pygame.transform.flip(scaled, True, False)

    # Hitung posisi pixel menggunakan smooth position
    x = viewport.map_rect.x + int((smooth_c + 0.5) * CELL_SIZE * viewport.scale)
    y = viewport.map_rect.y + int((smooth_r + 0.5) * CELL_SIZE * viewport.scale)
    screen.blit(scaled, (x - width // 2, y - height + max(2, int(4 * viewport.scale))))


def draw_circle_debug(screen, row, col, cell_size, color):
    """Gambar debug circle di tengah cell grid.

    Digunakan untuk menandai posisi player/NPC saat debug.

    Args:
        screen: Surface utama
        row: Baris di grid
        col: Kolom di grid
        cell_size: Ukuran cell dalam pixel
        color: Warna circle (R, G, B)
    """
    cx = col * cell_size + cell_size // 2
    cy = row * cell_size + cell_size // 2
    pygame.draw.circle(screen, color, (cx, cy), cell_size // 3)
