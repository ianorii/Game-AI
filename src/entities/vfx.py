"""
vfx.py - Efek Visual Transien Real-Time (Hit Sparks, Dust, Slash Arc).

Efek beranimasi sekali (one-shot), digambar dengan koordinat kamera,
dan otomatis dihapus setelah frame terakhir selesai diputar.
"""

from typing import List, Tuple
import math
import pygame


class VisualEffect:
    """Efek visual sementara yang diputar sekali lalu lenyap otomatis."""

    def __init__(self, x: float, y: float,
                 frames: List[pygame.Surface],
                 frame_duration: float = 0.05,
                 centered: bool = True):
        self.x = float(x)
        self.y = float(y)
        self.frames = frames or []
        self.frame_duration = max(0.01, frame_duration)
        self.centered = centered
        self.timer = 0.0
        self.alive = len(self.frames) > 0

    @property
    def finished(self) -> bool:
        return not self.alive

    def update(self, dt: float):
        """Update progres frame efek."""
        if not self.alive:
            return

        self.timer += dt
        self.frame_index = int(self.timer / self.frame_duration)

        if self.frame_index >= len(self.frames):
            self.alive = False

    def draw(self, surface: pygame.Surface, camera: Tuple[int, int]):
        """Render frame aktif efek ke layar dengan offset kamera."""
        if not self.alive or not self.frames:
            return

        idx = min(self.frame_index, len(self.frames) - 1)
        frame = self.frames[idx]

        cam_x, cam_y = camera
        draw_x = self.x - cam_x
        draw_y = self.y - cam_y

        if self.centered:
            draw_x -= frame.get_width() / 2
            draw_y -= frame.get_height() / 2

        surface.blit(frame, (int(draw_x), int(draw_y)))


class SlashArcEffect:
    """
    Efek tebasan melengkung dinamis (crescent slash arc) saat serangan mengenai musuh.
    Menghasilkan busur tebasan tajam berwarna emas/putih dengan streak garis tebasan,
    arah dinamis sesuai orientasi serangan hero, dan fade-out halus.
    """

    def __init__(self, x: float, y: float,
                 direction: str = "right",
                 duration: float = 0.16,
                 radius: int = 24,
                 core_color: Tuple[int, int, int] = (255, 255, 255),
                 accent_color: Tuple[int, int, int] = (232, 184, 74)):
        self.x = float(x)
        self.y = float(y)
        self.direction = direction
        self.duration = max(0.04, duration)
        self.radius = radius
        self.core_color = core_color
        self.accent_color = accent_color
        self.timer = 0.0
        self.alive = True

    @property
    def finished(self) -> bool:
        return not self.alive

    def update(self, dt: float):
        if not self.alive:
            return
        self.timer += dt
        if self.timer >= self.duration:
            self.alive = False

    def draw(self, surface: pygame.Surface, camera: Tuple[int, int]):
        if not self.alive:
            return

        progress = max(0.0, min(1.0, self.timer / self.duration))
        alpha = int(255 * (1.0 - progress))
        if alpha <= 0:
            return

        cam_x, cam_y = camera
        draw_x = int(self.x - cam_x)
        draw_y = int(self.y - cam_y)

        size = self.radius * 2 + 16
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = size // 2
        cy = size // 2
        r = self.radius

        # Orientasi sudut tebasan berdasarkan arah serangan
        if self.direction == "left":
            start_angle = math.pi * 0.60
            sweep = math.pi * 0.85 * min(1.0, progress * 1.5)
        elif self.direction == "up":
            start_angle = math.pi * 1.10
            sweep = math.pi * 0.85 * min(1.0, progress * 1.5)
        elif self.direction == "down":
            start_angle = math.pi * 0.10
            sweep = math.pi * 0.85 * min(1.0, progress * 1.5)
        else:  # right
            start_angle = -math.pi * 0.40
            sweep = math.pi * 0.85 * min(1.0, progress * 1.5)

        edge_col = (*self.accent_color, int(alpha * 0.85))
        core_col = (*self.core_color, alpha)

        arc_rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        inner_rect = pygame.Rect(cx - r + 2, cy - r + 2, (r - 2) * 2, (r - 2) * 2)

        # Busur tebasan luar (emas) dan inti tajam (putih)
        pygame.draw.arc(surf, edge_col, arc_rect, start_angle, start_angle + sweep, 4)
        pygame.draw.arc(surf, core_col, inner_rect, start_angle + 0.05, start_angle + sweep, 2)

        # Garis kilat tebasan (slash streak)
        p1 = (cx - int(r * 0.75 * math.cos(start_angle)), cy - int(r * 0.75 * math.sin(start_angle)))
        cur_ang = start_angle + sweep
        p2 = (cx - int(r * 0.75 * math.cos(cur_ang)), cy - int(r * 0.75 * math.sin(cur_ang)))
        pygame.draw.line(surf, (*self.core_color, int(alpha * 0.8)), p1, p2, 2)

        surface.blit(surf, (draw_x - cx, draw_y - cy))
