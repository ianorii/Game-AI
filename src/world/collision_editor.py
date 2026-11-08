"""
collision_editor.py - Sistem Collision Editor Interaktif & Runtime Walkability Overrides.

Arsitektur:
  1. Tiga Mode (F1 Toggle):
     - OFF  : Gameplay normal (HUD & kontrol standar).
     - VIEW : Overlay visualisasi collision (hanya lihat, culling aktif).
     - EDIT : Editor aktif (hero/musuh freeze, free-cam, kuas tile, bresenham, undo/redo).
  2. Single Source of Truth:
     - Fungsi `is_walkable(tx, ty)` menggabungkan data map asli + overrides delta.
     - Setiap perubahan override langsung disinkronkan ke:
       * `TileMap.grid[ty][tx]` (T_FLOOR vs T_WALL) untuk A*, Dijkstra, CSP, & STRIPS.
       * `GameMap.walkable_mask` (32x32 piksel per tile) untuk physics sliding & goblin combat.
  3. Alat Edit:
     - Klik Kiri   : BLOCKED (Oranye).
     - Klik Kanan  : WALKABLE (Hijau).
     - Tahan & Seret: Garis kontinu dengan algoritma Bresenham.
     - Shift + Seret: Area persegi panjang (Rectangle fill).
     - Tombol C    : Clear override pada tile di kursor (kembali ke data asli).
     - Ctrl+Z / Y  : Undo / Redo multi-langkah (maks 100 langkah per stroke).
     - Tombol [ / ]: Ukuran kuas (1x1, 2x2, 3x3).
     - Tombol G    : Toggle grid garis tile.
     - Tombol H    : Toggle panel bantuan shortcut.
     - Ctrl+S      : Simpan manual permanen.
     - Ctrl+Shift+R: Reset semua override kembali ke bawaan map.
  4. Persistensi Permanen:
     - Delta override disimpan di `data/collision_overrides.json` format JSON.
     - Autosave saat keluar dari mode EDIT dan saat exit game.
     - Penulisan atomik (.tmp -> replace) dan backup otomatis (.bak).
     - Proteksi konektivitas (BFS flood-fill ke BOSS_POS & jembatan).
"""

from __future__ import annotations

import json
import math
import os
import shutil
from collections import deque
from typing import Dict, List, Tuple, Optional, Set
import pygame

import config


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    """Algoritma garis Bresenham: menjamin sapuan mouse cepat tidak melewatkan tile."""
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    cx, cy = x0, y0
    while True:
        points.append((cx, cy))
        if cx == x1 and cy == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            cx += sx
        if e2 < dx:
            err += dx
            cy += sy
    return points


class CollisionToast:
    """Notifikasi toast mengambang dengan animasi fade out."""
    def __init__(self, message: str, color: Tuple[int, int, int] = config.WHITE, duration: float = 2.5):
        self.message = message
        self.color = color
        self.duration = duration
        self.timer = duration

    def update(self, dt: float) -> bool:
        self.timer -= dt
        return self.timer > 0


class CollisionEditor:
    """Pengelola editor tabrakan, overlay render, dan persistensi override."""

    def __init__(self, game_map, tile_map, world_seed: int = config.LEVEL_SEED_DEFAULT, override_path: Optional[str] = None):
        self.game_map = game_map
        self.tile_map = tile_map
        self.world_w = getattr(tile_map, "width", config.WORLD_W)
        self.world_h = getattr(tile_map, "height", config.WORLD_H)
        self.world_seed = world_seed
        self.tile_size = config.TILE_SIZE
        self.override_path = override_path or config.COLLISION_OVERRIDES_PATH
        self.backup_path = (override_path + ".bak") if override_path else config.COLLISION_BACKUP_PATH

        # Mode editor: OFF | VIEW | EDIT
        self.mode = config.EDITOR_MODE_OFF

        # Base collision data (Snapshot asli tanpa modifikasi)
        self.base_solid: List[List[bool]] = []
        self._init_base_collision()

        # Delta Overrides: (tx, ty) -> is_blocked (True = blocked, False = walkable)
        self.overrides: Dict[Tuple[int, int], bool] = {}
        self.dirty = False

        # Undo / Redo Stacks (Tiap elemen adalah dict changes per stroke)
        self.undo_stack: deque = deque(maxlen=config.EDITOR_MAX_UNDO)
        self.redo_stack: deque = deque(maxlen=config.EDITOR_MAX_UNDO)
        self.current_stroke: Dict[Tuple[int, int], Optional[bool]] = {}
        self.is_dragging = False
        self.last_drag_tile: Optional[Tuple[int, int]] = None
        self.drag_button: Optional[int] = None  # 1: Left (Block), 3: Right (Walk)

        # Shift + Drag selection box
        self.shift_selecting = False
        self.shift_start_tile: Optional[Tuple[int, int]] = None

        # Pengaturan kuas & tampilan
        self.brush_size = 1        # 1, 2, atau 3
        self.show_grid = True      # Garis petak tile
        self.show_help = False     # Modal bantuan shortcut
        self.show_walkable_base = False  # Hijau transparan untuk walkable bawaan

        # Free-cam untuk mode EDIT
        self.free_cam_x = 0.0
        self.free_cam_y = 0.0

        # UI & Fonts
        self.font_main = pygame.font.Font(None, 20)
        self.font_bold = pygame.font.Font(None, 22)
        self.font_small = pygame.font.Font(None, 16)
        self.font_tiny = pygame.font.Font(None, 14)
        self.toasts: List[CollisionToast] = []

        # Mask 32x32 untuk blitting cepat ke GameMap.walkable_mask
        self._tile_mask = pygame.mask.Mask((self.tile_size, self.tile_size), fill=True)

        # Muat file persistensi jika ada
        self.load_overrides()

    # ==========================================================================
    # INISIALISASI BASE COLLISION & SINGLE SOURCE OF TRUTH
    # ==========================================================================
    def _init_base_collision(self):
        """Ambil snapshot kondisi collision asli map dari TileMap."""
        self.base_solid = []
        has_raw = hasattr(self.tile_map, "solid_raw") and self.tile_map.solid_raw
        for y in range(self.world_h):
            row = []
            for x in range(self.world_w):
                if has_raw and y < len(self.tile_map.solid_raw) and x < len(self.tile_map.solid_raw[y]):
                    is_solid = bool(self.tile_map.solid_raw[y][x])
                else:
                    is_solid = self.tile_map.is_wall(x, y)
                row.append(is_solid)
            self.base_solid.append(row)

    def is_base_blocked(self, tx: int, ty: int) -> bool:
        """Cek apakah tile berstatus blocked pada data peta asli."""
        if 0 <= tx < self.world_w and 0 <= ty < self.world_h:
            return self.base_solid[ty][tx]
        return True

    def is_walkable(self, tx: int, ty: int) -> bool:
        """
        SINGLE SOURCE OF TRUTH untuk walkability tile (tx, ty).
        Data asli digabungkan dengan override pemain.
        """
        if not (0 <= tx < self.world_w and 0 <= ty < self.world_h):
            return False
        if (tx, ty) in self.overrides:
            return not self.overrides[(tx, ty)]
        return not self.base_solid[ty][tx]

    def is_blocked(self, tx: int, ty: int) -> bool:
        """Kebalikan dari is_walkable."""
        return not self.is_walkable(tx, ty)

    # ==========================================================================
    # TOGGLE MODE (F1)
    # ==========================================================================
    def toggle_mode(self, current_cam: Tuple[float, float]) -> str:
        """
        Siklus F1: OFF -> VIEW (LIHAT) -> EDIT -> OFF.
        Mengembalikan nama mode baru.
        """
        if self.mode == config.EDITOR_MODE_OFF:
            self.mode = config.EDITOR_MODE_VIEW
            self.add_toast("COLLISION: LIHAT (Hanya Tampilan)", config.CYAN)
        elif self.mode == config.EDITOR_MODE_VIEW:
            self.mode = config.EDITOR_MODE_EDIT
            self.free_cam_x, self.free_cam_y = current_cam
            self.add_toast("COLLISION: EDIT (Hero & Musuh Dijeda, Free-Cam WASD)", config.ORANGE)
        else:
            # Keluar dari EDIT -> autosave jika ada perubahan
            if self.dirty:
                self.save_overrides(is_autosave=True)
            self.mode = config.EDITOR_MODE_OFF
            self.add_toast("COLLISION: OFF (Mode Normal)", config.GREEN)

        return self.mode

    # ==========================================================================
    # APLIKASI OVERRIDE KE TILEMAP & GAMEMAP
    # ==========================================================================
    def set_tile_override(self, tx: int, ty: int, is_blocked: bool, record_stroke: bool = True):
        """Ubah status walkability tile dan sinkronkan ke TileMap & GameMap."""
        if not (0 <= tx < self.world_w and 0 <= ty < self.world_h):
            return

        old_override = self.overrides.get((tx, ty), None)

        # Jika nilai baru sama persis dengan base map asli, override dihapus
        if is_blocked == self.base_solid[ty][tx]:
            if (tx, ty) in self.overrides:
                if record_stroke and (tx, ty) not in self.current_stroke:
                    self.current_stroke[(tx, ty)] = old_override
                del self.overrides[(tx, ty)]
                self.dirty = True
        else:
            if old_override != is_blocked:
                if record_stroke and (tx, ty) not in self.current_stroke:
                    self.current_stroke[(tx, ty)] = old_override
                self.overrides[(tx, ty)] = is_blocked
                self.dirty = True

        # Sinkronisasi ke TileMap (T_WALL / T_FLOOR)
        if hasattr(self.tile_map, "grid") and self.tile_map.grid:
            self.tile_map.grid[ty][tx] = "wall" if is_blocked else "floor"

        # Sinkronisasi ke GameMap.walkable_mask (32x32 piksel)
        if self.game_map and getattr(self.game_map, "walkable_mask", None):
            px, py = tx * self.tile_size, ty * self.tile_size
            if is_blocked:
                self.game_map.walkable_mask.erase(self._tile_mask, (px, py))
            else:
                self.game_map.walkable_mask.draw(self._tile_mask, (px, py))

    def clear_tile_override(self, tx: int, ty: int, record_stroke: bool = True):
        """Hapus override pada tile di bawah kursor (kembali ke base map)."""
        if (tx, ty) in self.overrides:
            base_blocked = self.base_solid[ty][tx]
            self.set_tile_override(tx, ty, base_blocked, record_stroke=record_stroke)

    def apply_brush(self, center_tx: int, center_ty: int, is_blocked: bool):
        """Menerapkan kuas berukuran 1x1, 2x2, atau 3x3 pada koordinat tengah."""
        tiles = self.get_brush_tiles(center_tx, center_ty)
        for tx, ty in tiles:
            self.set_tile_override(tx, ty, is_blocked, record_stroke=True)

    def get_brush_tiles(self, cx: int, cy: int) -> List[Tuple[int, int]]:
        """Mendapatkan daftar koordinat tile yang tercakup oleh kuas saat ini."""
        tiles = []
        if self.brush_size == 1:
            tiles.append((cx, cy))
        elif self.brush_size == 2:
            for dy in range(2):
                for dx in range(2):
                    tiles.append((cx + dx, cy + dy))
        else:  # brush_size == 3
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    tiles.append((cx + dx, cy + dy))
        return [t for t in tiles if 0 <= t[0] < self.world_w and 0 <= t[1] < self.world_h]

    # ==========================================================================
    # UNDO & REDO
    # ==========================================================================
    def undo(self) -> bool:
        """Kembalikan satu langkah perubahan (stroke)."""
        if not self.undo_stack:
            self.add_toast("Tidak ada langkah untuk di-undo", config.GREY)
            return False

        stroke = self.undo_stack.pop()
        redo_stroke = {}

        for (tx, ty), old_val in stroke.items():
            current_val = self.overrides.get((tx, ty), None)
            redo_stroke[(tx, ty)] = current_val

            if old_val is None:
                # Dulu tidak ada override -> kembalikan ke base
                self.set_tile_override(tx, ty, self.base_solid[ty][tx], record_stroke=False)
            else:
                self.set_tile_override(tx, ty, old_val, record_stroke=False)

        self.redo_stack.append(redo_stroke)
        self.dirty = True
        self.add_toast(f"Undo berhasil ({len(stroke)} tile dipulihkan)", config.CYAN)
        return True

    def redo(self) -> bool:
        """Ulangi satu langkah perubahan yang telah di-undo."""
        if not self.redo_stack:
            self.add_toast("Tidak ada langkah untuk di-redo", config.GREY)
            return False

        stroke = self.redo_stack.pop()
        undo_stroke = {}

        for (tx, ty), new_val in stroke.items():
            current_val = self.overrides.get((tx, ty), None)
            undo_stroke[(tx, ty)] = current_val

            if new_val is None:
                self.set_tile_override(tx, ty, self.base_solid[ty][tx], record_stroke=False)
            else:
                self.set_tile_override(tx, ty, new_val, record_stroke=False)

        self.undo_stack.append(undo_stroke)
        self.dirty = True
        self.add_toast(f"Redo berhasil ({len(stroke)} tile)", config.CYAN)
        return True

    # ==========================================================================
    # INPUT & EVENT HANDLING (HANYA AKTIF SAAT EDIT)
    # ==========================================================================
    def handle_event(self, event: pygame.event.Event, camera: Tuple[float, float], hero=None) -> bool:
        """
        Memproses input mouse dan keyboard pada mode EDIT.
        Mengembalikan True jika event ditangani oleh editor (mencegah bentrok).
        """
        if self.mode != config.EDITOR_MODE_EDIT:
            return False

        # 1. Shortcut Keyboard
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = bool(mods & pygame.KMOD_CTRL)
            shift = bool(mods & pygame.KMOD_SHIFT)

            # Ctrl+S: Simpan manual
            if ctrl and not shift and event.key == pygame.K_s:
                self.save_overrides(is_autosave=False)
                return True

            # Ctrl+Z: Undo
            if ctrl and not shift and event.key == pygame.K_z:
                self.undo()
                return True

            # Ctrl+Y atau Ctrl+Shift+Z: Redo
            if (ctrl and event.key == pygame.K_y) or (ctrl and shift and event.key == pygame.K_z):
                self.redo()
                return True

            # Ctrl+Shift+R: Reset semua overrides ke data asli
            if ctrl and shift and event.key == pygame.K_r:
                self.reset_all_overrides()
                return True

            # Tombol C: Clear override pada tile di kursor
            if event.key == pygame.K_c:
                mx, my = pygame.mouse.get_pos()
                tx, ty = self.screen_to_tile((mx, my), camera)
                if (tx, ty) in self.overrides:
                    self.current_stroke = {}
                    self.clear_tile_override(tx, ty, record_stroke=True)
                    if self.current_stroke:
                        self.undo_stack.append(self.current_stroke)
                        self.redo_stack.clear()
                    self.add_toast(f"Override pada ({tx}, {ty}) dihapus", config.YELLOW)
                return True

            # Tombol [ / ]: Ukuran kuas
            if event.key == pygame.K_LEFTBRACKET:
                self.brush_size = max(1, self.brush_size - 1)
                self.add_toast(f"Kuas: {self.brush_size}x{self.brush_size}", config.WHITE)
                return True
            if event.key == pygame.K_RIGHTBRACKET:
                self.brush_size = min(3, self.brush_size + 1)
                self.add_toast(f"Kuas: {self.brush_size}x{self.brush_size}", config.WHITE)
                return True

            # Tombol G: Toggle grid
            if event.key == pygame.K_g:
                self.show_grid = not self.show_grid
                self.add_toast(f"Grid: {'ON' if self.show_grid else 'OFF'}", config.WHITE)
                return True

            # Tombol H: Toggle Help Panel
            if event.key == pygame.K_h:
                self.show_help = not self.show_help
                return True

        # 2. Input Mouse
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.pos[1] > config.MAP_PIXEL_H:
                return False  # Klik pada HUD bawah diabaikan

            tx, ty = self.screen_to_tile(event.pos, camera)
            mods = pygame.key.get_mods()
            shift = bool(mods & pygame.KMOD_SHIFT)

            if shift and event.button in (1, 3):
                # Mulai Shift + Drag area selection
                self.shift_selecting = True
                self.shift_start_tile = (tx, ty)
                self.drag_button = event.button
                return True

            if event.button in (1, 3):
                # Validasi jangan kurung hero
                is_blocked = (event.button == 1)
                if hero and is_blocked and self._would_trap_hero(tx, ty, hero):
                    self.add_toast("TIDAK BISA: Jangan memblokir posisi Hero!", config.RED)
                    return True

                self.is_dragging = True
                self.drag_button = event.button
                self.last_drag_tile = (tx, ty)
                self.current_stroke = {}
                self.apply_brush(tx, ty, is_blocked)
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.is_dragging and self.drag_button in (1, 3):
                curr_tx, curr_ty = self.screen_to_tile(event.pos, camera)
                is_blocked = (self.drag_button == 1)

                if self.last_drag_tile and (curr_tx, curr_ty) != self.last_drag_tile:
                    # Bresenham line interpolation antara titik terakhir dan titik saat ini
                    line_points = bresenham_line(self.last_drag_tile[0], self.last_drag_tile[1], curr_tx, curr_ty)
                    for px, py in line_points:
                        if hero and is_blocked and self._would_trap_hero(px, py, hero):
                            continue
                        self.apply_brush(px, py, is_blocked)
                    self.last_drag_tile = (curr_tx, curr_ty)
                return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if self.shift_selecting and event.button == self.drag_button:
                # Akhiri seleksi kotak dan isi seluruh area
                end_tx, end_ty = self.screen_to_tile(event.pos, camera)
                if self.shift_start_tile:
                    x0 = min(self.shift_start_tile[0], end_tx)
                    x1 = max(self.shift_start_tile[0], end_tx)
                    y0 = min(self.shift_start_tile[1], end_ty)
                    y1 = max(self.shift_start_tile[1], end_ty)

                    is_blocked = (event.button == 1)
                    self.current_stroke = {}
                    count = 0
                    for y in range(y0, y1 + 1):
                        for x in range(x0, x1 + 1):
                            if hero and is_blocked and self._would_trap_hero(x, y, hero):
                                continue
                            self.set_tile_override(x, y, is_blocked, record_stroke=True)
                            count += 1
                    if self.current_stroke:
                        self.undo_stack.append(self.current_stroke)
                        self.redo_stack.clear()
                    action_name = "BLOCKED" if is_blocked else "WALKABLE"
                    self.add_toast(f"Area {x1 - x0 + 1}x{y1 - y0 + 1} ({count} tile) diubah -> {action_name}", config.CYAN)

                self.shift_selecting = False
                self.shift_start_tile = None
                self.drag_button = None
                return True

            if self.is_dragging and event.button == self.drag_button:
                self.is_dragging = False
                self.last_drag_tile = None
                self.drag_button = None
                if self.current_stroke:
                    self.undo_stack.append(self.current_stroke)
                    self.redo_stack.clear()
                return True

        return False

    def update_free_cam(self, keys_held: Set[int], dt: float):
        """Geser kamera bebas pada mode EDIT dengan WASD atau tombol panah."""
        if self.mode != config.EDITOR_MODE_EDIT:
            return

        speed = config.EDITOR_CAMERA_SPEED * dt
        dx, dy = 0.0, 0.0

        if pygame.K_w in keys_held or pygame.K_UP in keys_held:
            dy -= speed
        if pygame.K_s in keys_held or pygame.K_DOWN in keys_held:
            dy += speed
        if pygame.K_a in keys_held or pygame.K_LEFT in keys_held:
            dx -= speed
        if pygame.K_d in keys_held or pygame.K_RIGHT in keys_held:
            dx += speed

        if dx != 0.0 and dy != 0.0:
            dx *= 0.7071
            dy *= 0.7071

        self.free_cam_x += dx
        self.free_cam_y += dy

        # Batasi kamera di dalam batas dunia
        max_x = max(0.0, self.world_w * self.tile_size - config.MAP_PIXEL_W)
        max_y = max(0.0, self.world_h * self.tile_size - config.MAP_PIXEL_H)
        self.free_cam_x = max(0.0, min(max_x, self.free_cam_x))
        self.free_cam_y = max(0.0, min(max_y, self.free_cam_y))

    def _would_trap_hero(self, tx: int, ty: int, hero) -> bool:
        """Cek apakah mengedit tile (tx, ty) akan menimpa posisi kaki Hero saat ini."""
        if not hero:
            return False
        hx = int(hero.px // self.tile_size)
        hy = int(hero.py // self.tile_size)
        return (tx, ty) == (hx, hy)

    def screen_to_tile(self, screen_pos: Tuple[int, int], camera: Tuple[float, float]) -> Tuple[int, int]:
        """Konversi piksel layar -> indeks tile map (tx, ty)."""
        mx, my = screen_pos
        cam_x, cam_y = camera
        tx = int((mx + cam_x) // self.tile_size)
        ty = int((my + cam_y) // self.tile_size)
        return tx, ty

    # ==========================================================================
    # PERSISTENSI JSON & ATOMIC SAVE / LOAD
    # ==========================================================================
    def save_overrides(self, is_autosave: bool = False) -> bool:
        """
        Simpan selisih (delta overrides) ke file JSON secara atomik.
        Mencakup pembuatan file .bak dan peringatan konektivitas.
        """
        target_path = self.override_path
        os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
        tmp_path = target_path + ".tmp"
        bak_path = self.backup_path

        # Siapkan struktur data delta
        data = {
            "version": 1,
            "map_id": "sunnyside_island",
            "world_seed": self.world_seed,
            "world_size": [self.world_w, self.world_h],
            "overrides": [
                {"x": k[0], "y": k[1], "blocked": v}
                for k, v in sorted(self.overrides.items())
            ]
        }

        try:
            # 1. Tulis ke file sementara (.tmp)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # 2. Cadangkan file lama ke .bak bila ada
            if os.path.exists(target_path):
                shutil.copy2(target_path, bak_path)

            # 3. Ganti secara atomik (.tmp -> target)
            os.replace(tmp_path, target_path)

            self.dirty = False
            label = "Autosave" if is_autosave else "Tersimpan"
            self.add_toast(f"{label}: {len(self.overrides)} override disimpan ke JSON", config.GREEN)

            # 4. Validasi konektivitas (BFS flood-fill dari spawn)
            self._validate_connectivity_after_save()
            return True

        except Exception as e:
            self.add_toast(f"GAGAL MENYIMPAN: {e}", config.RED)
            return False

    def load_overrides(self) -> bool:
        """
        Muat file delta override saat startup game.
        Toleran terhadap error/korupsi dan memverifikasi kecocokan seed & ukuran peta.
        """
        path = self.override_path
        if not os.path.exists(path):
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validasi kecocokan ukuran dan seed
            file_seed = data.get("world_seed")
            file_size = data.get("world_size")

            if file_size != [self.world_w, self.world_h]:
                print(f"[CollisionEditor] PERINGATAN: Ukuran peta di file {file_size} tidak cocok dengan dunia {self.world_w}x{self.world_h}. Override diabaikan.")
                self.add_toast("Peringatan: Ukuran peta override tidak cocok!", config.YELLOW)
                return False

            if file_seed is not None and file_seed != self.world_seed:
                print(f"[CollisionEditor] CATATAN: Seed peta berbeda ({file_seed} != {self.world_seed}). Override tetap diterapkan.")

            # Terapkan semua override
            count = 0
            for item in data.get("overrides", []):
                tx = int(item["x"])
                ty = int(item["y"])
                is_blocked = bool(item["blocked"])
                self.set_tile_override(tx, ty, is_blocked, record_stroke=False)
                count += 1

            self.dirty = False
            self.undo_stack.clear()
            self.redo_stack.clear()
            print(f"[CollisionEditor] Berhasil memuat {count} collision override dari '{path}'")
            return True

        except Exception as e:
            print(f"[CollisionEditor] Gagal membaca '{path}': {e}. Memakai collision asli tanpa crash.")
            self.add_toast(f"Peringatan: File override korup ({e})", config.RED)
            return False

    def reset_all_overrides(self):
        """Reset seluruh override kembali ke data collision map asli."""
        if not self.overrides:
            self.add_toast("Tidak ada override aktif", config.GREY)
            return

        self.current_stroke = {}
        # Kembalikan semua tile yang pernah diubah
        for (tx, ty) in list(self.overrides.keys()):
            self.clear_tile_override(tx, ty, record_stroke=True)

        if self.current_stroke:
            self.undo_stack.append(self.current_stroke)
            self.redo_stack.clear()

        self.dirty = True
        self.add_toast("Semua override di-reset ke bawaan map!", config.YELLOW)

    # ==========================================================================
    # PROTEKSI KONEKTIVITAS (FLOOD FILL BFS)
    # ==========================================================================
    def _validate_connectivity_after_save(self):
        """Periksa apakah Boss dan jembatan masih dapat dicapai dari titik spawn."""
        spawn_tx = int(self.tile_map.spawn[0])
        spawn_ty = int(self.tile_map.spawn[1])

        # Target verifikasi: Titik Boss
        boss_tx = int(config.BOSS_POS[0] // self.tile_size)
        boss_ty = int(config.BOSS_POS[1] // self.tile_size)

        reachable = self._flood_fill_reachable(spawn_tx, spawn_ty)

        if (boss_tx, boss_ty) not in reachable:
            self.add_toast("PERINGATAN: Akses ke BOSS terputus oleh modifikasi!", (255, 210, 50), duration=4.0)

    def _flood_fill_reachable(self, start_x: int, start_y: int) -> Set[Tuple[int, int]]:
        """BFS flood fill untuk mendapatkan semua sel yang dapat dicapai dari start."""
        if not self.is_walkable(start_x, start_y):
            return set()

        visited = set()
        queue = deque([(start_x, start_y)])
        visited.add((start_x, start_y))

        while queue:
            cx, cy = queue.popleft()
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.world_w and 0 <= ny < self.world_h:
                    if (nx, ny) not in visited and self.is_walkable(nx, ny):
                        visited.add((nx, ny))
                        queue.append((nx, ny))

        return visited

    # ==========================================================================
    # TOAST NOTIFIKASI
    # ==========================================================================
    def add_toast(self, message: str, color: Tuple[int, int, int] = config.WHITE, duration: float = 2.5):
        """Tambahkan pesan toast notifikasi."""
        self.toasts.append(CollisionToast(message, color, duration))
        if len(self.toasts) > 4:
            self.toasts.pop(0)

    def update_toasts(self, dt: float):
        """Update timer animasi toast."""
        self.toasts = [t for t in self.toasts if t.update(dt)]

    # ==========================================================================
    # RENDERING & FRUSTUM CULLING
    # ==========================================================================
    def draw(self, screen: pygame.Surface, camera: Tuple[float, float], mouse_pos: Tuple[int, int]):
        """Gambar overlay collision dengan frustum culling, highlight, dan panel UI."""
        if self.mode == config.EDITOR_MODE_OFF:
            return

        cam_x, cam_y = camera
        ts = self.tile_size

        # 1. Frustum Culling: Hanya render tile yang terlihat di kamera
        min_tx = max(0, int(cam_x // ts))
        max_tx = min(self.world_w, int((cam_x + config.MAP_PIXEL_W) // ts) + 2)
        min_ty = max(0, int(cam_y // ts))
        max_ty = min(self.world_h, int((cam_y + config.MAP_PIXEL_H) // ts) + 2)

        # Pre-create translucent surfaces untuk efisiensi
        surf_blocked_base = pygame.Surface((ts, ts), pygame.SRCALPHA)
        surf_blocked_base.fill(config.EDITOR_BLOCKED_BASE_COLOR)
        pygame.draw.rect(surf_blocked_base, config.EDITOR_BLOCKED_BASE_BORDER, (0, 0, ts, ts), 1)

        surf_blocked_override = pygame.Surface((ts, ts), pygame.SRCALPHA)
        surf_blocked_override.fill(config.EDITOR_BLOCKED_OVERRIDE_COLOR)
        pygame.draw.rect(surf_blocked_override, config.EDITOR_BLOCKED_OVERRIDE_BORDER, (0, 0, ts, ts), 1)

        surf_walkable_override = pygame.Surface((ts, ts), pygame.SRCALPHA)
        surf_walkable_override.fill(config.EDITOR_WALKABLE_OVERRIDE_COLOR)
        pygame.draw.rect(surf_walkable_override, config.EDITOR_WALKABLE_OVERRIDE_BORDER, (0, 0, ts, ts), 1)

        # 2. Render Overlay per Tile
        for ty in range(min_ty, max_ty):
            for tx in range(min_tx, max_tx):
                screen_x = int(tx * ts - cam_x)
                screen_y = int(ty * ts - cam_y)

                has_override = (tx, ty) in self.overrides
                if has_override:
                    is_ov_blocked = self.overrides[(tx, ty)]
                    if is_ov_blocked:
                        # Oranye: Override Blocked
                        screen.blit(surf_blocked_override, (screen_x, screen_y))
                    else:
                        # Hijau: Override Walkable
                        screen.blit(surf_walkable_override, (screen_x, screen_y))
                else:
                    if self.base_solid[ty][tx]:
                        # Merah: Base Blocked Asli
                        screen.blit(surf_blocked_base, (screen_x, screen_y))
                    elif self.show_walkable_base:
                        # Opsional: Hijau tipis walkable
                        pass

                # Grid lines
                if self.show_grid and self.mode == config.EDITOR_MODE_EDIT:
                    pygame.draw.rect(screen, config.EDITOR_GRID_COLOR, (screen_x, screen_y, ts, ts), 1)

        # 3. Render Area Seleksi Kotak (Shift + Drag)
        if self.shift_selecting and self.shift_start_tile:
            curr_tx, curr_ty = self.screen_to_tile(mouse_pos, camera)
            x0 = min(self.shift_start_tile[0], curr_tx)
            x1 = max(self.shift_start_tile[0], curr_tx)
            y0 = min(self.shift_start_tile[1], curr_ty)
            y1 = max(self.shift_start_tile[1], curr_ty)

            sel_rx = int(x0 * ts - cam_x)
            sel_ry = int(y0 * ts - cam_y)
            sel_rw = int((x1 - x0 + 1) * ts)
            sel_rh = int((y1 - y0 + 1) * ts)

            sel_surf = pygame.Surface((sel_rw, sel_rh), pygame.SRCALPHA)
            sel_surf.fill(config.EDITOR_SELECT_BOX_COLOR)
            screen.blit(sel_surf, (sel_rx, sel_ry))
            pygame.draw.rect(screen, config.EDITOR_SELECT_BOX_BORDER, (sel_rx, sel_ry, sel_rw, sel_rh), 2)

        # 4. Highlight Kuas di Bawah Kursor & Tooltip Status
        hover_tx, hover_ty = self.screen_to_tile(mouse_pos, camera)
        if 0 <= hover_tx < self.world_w and 0 <= hover_ty < self.world_h and mouse_pos[1] <= config.MAP_PIXEL_H:
            # Highlight semua tile kuas
            brush_tiles = self.get_brush_tiles(hover_tx, hover_ty) if self.mode == config.EDITOR_MODE_EDIT else [(hover_tx, hover_ty)]
            for btx, bty in brush_tiles:
                hx = int(btx * ts - cam_x)
                hy = int(bty * ts - cam_y)
                pygame.draw.rect(screen, config.EDITOR_HOVER_COLOR, (hx, hy, ts, ts), 2)

            # Tooltip kecil di samping kursor
            self._draw_tooltip(screen, hover_tx, hover_ty, mouse_pos)

        # 5. Panel HUD Editor (< 15% layar)
        self._draw_hud_panel(screen)

        # 6. Toast Notifikasi
        self._draw_toasts(screen)

        # 7. Modal Bantuan Shortcut [H]
        if self.show_help and self.mode == config.EDITOR_MODE_EDIT:
            self._draw_help_modal(screen)

    def _draw_tooltip(self, screen: pygame.Surface, tx: int, ty: int, mouse_pos: Tuple[int, int]):
        """Render tooltip kecil berisi koordinat dan status tile."""
        mx, my = mouse_pos
        has_override = (tx, ty) in self.overrides

        if has_override:
            if self.overrides[(tx, ty)]:
                status_text = "OVERRIDE: BLOCKED"
                status_color = (255, 170, 50)
            else:
                status_text = "OVERRIDE: WALKABLE"
                status_color = (80, 255, 120)
        else:
            if self.base_solid[ty][tx]:
                status_text = "ASLI: BLOCKED"
                status_color = (255, 70, 70)
            else:
                status_text = "ASLI: WALKABLE"
                status_color = (100, 220, 255)

        coord_text = f"Tile ({tx}, {ty})"
        surf_coord = self.font_tiny.render(coord_text, True, config.WHITE)
        surf_stat = self.font_tiny.render(status_text, True, status_color)

        tw = max(surf_coord.get_width(), surf_stat.get_width()) + 14
        th = 30
        tx_pos = mx + 16
        ty_pos = my + 16

        # Hindari keluar layar
        if tx_pos + tw > config.WINDOW_SIZE[0]:
            tx_pos = mx - tw - 8
        if ty_pos + th > config.MAP_PIXEL_H:
            ty_pos = my - th - 8

        tip_bg = pygame.Surface((tw, th), pygame.SRCALPHA)
        tip_bg.fill((12, 14, 20, 225))
        screen.blit(tip_bg, (tx_pos, ty_pos))
        pygame.draw.rect(screen, (80, 85, 110), (tx_pos, ty_pos, tw, th), 1)

        screen.blit(surf_coord, (tx_pos + 6, ty_pos + 3))
        screen.blit(surf_stat, (tx_pos + 6, ty_pos + 16))

    def _draw_hud_panel(self, screen: pygame.Surface):
        """Render panel status kecil di pojok kanan atas (kurang dari 15% luas layar)."""
        pw = 320
        ph = 76 if self.mode == config.EDITOR_MODE_EDIT else 42
        px = config.WINDOW_SIZE[0] - pw - 12
        py = 10

        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((14, 16, 24, 230))
        screen.blit(panel, (px, py))

        border_color = config.ORANGE if self.mode == config.EDITOR_MODE_EDIT else config.CYAN
        pygame.draw.rect(screen, border_color, (px, py, pw, ph), 2)

        # Baris 1: Mode & Indikator Dirty
        mode_str = "COLLISION: EDIT" if self.mode == config.EDITOR_MODE_EDIT else "COLLISION: LIHAT"
        title_surf = self.font_bold.render(mode_str, True, border_color)
        screen.blit(title_surf, (px + 10, py + 8))

        # Titik status simpan
        dirty_x = px + title_surf.get_width() + 18
        dirty_y = py + 14
        if self.dirty:
            pygame.draw.circle(screen, config.ORANGE, (dirty_x, dirty_y), 4)
            stat_lbl = self.font_tiny.render("Belum Disimpan", True, config.ORANGE)
        else:
            pygame.draw.circle(screen, config.GREEN, (dirty_x, dirty_y), 4)
            stat_lbl = self.font_tiny.render("Tersimpan", True, config.GREEN)
        screen.blit(stat_lbl, (dirty_x + 8, py + 8))

        if self.mode == config.EDITOR_MODE_EDIT:
            # Baris 2: Kuas & Jumlah Override
            blocked_cnt = sum(1 for v in self.overrides.values() if v)
            walk_cnt = sum(1 for v in self.overrides.values() if not v)
            info_str = f"Kuas: {self.brush_size}x{self.brush_size} [ / ] | Total Overrides: {len(self.overrides)} (B:{blocked_cnt}, W:{walk_cnt})"
            info_surf = self.font_small.render(info_str, True, (210, 215, 230))
            screen.blit(info_surf, (px + 10, py + 30))

            # Baris 3: Shortcut Ringkas
            hint_str = "[Klik L] Block  [Klik R] Walk  [C] Clear  [H] Bantuan"
            hint_surf = self.font_tiny.render(hint_str, True, (170, 180, 205))
            screen.blit(hint_surf, (px + 10, py + 52))
        else:
            # Hint mode lihat
            hint_str = "F1: Beralih ke EDIT | Klik/Kamera normal"
            hint_surf = self.font_tiny.render(hint_str, True, (170, 180, 205))
            screen.blit(hint_surf, (px + 10, py + 26))

    def _draw_toasts(self, screen: pygame.Surface):
        """Render daftar notifikasi toast di bagian bawah layar."""
        ty = config.MAP_PIXEL_H - 30
        for toast in reversed(self.toasts):
            alpha = max(0, min(255, int(255 * (toast.timer / 0.5)))) if toast.timer < 0.5 else 255
            txt_surf = self.font_small.render(toast.message, True, toast.color).copy()
            txt_surf.set_alpha(alpha)

            tw = txt_surf.get_width() + 24
            th = 24
            tx = (config.WINDOW_SIZE[0] - tw) // 2

            bg = pygame.Surface((tw, th), pygame.SRCALPHA)
            bg.fill((16, 18, 26, min(230, alpha)))
            screen.blit(bg, (tx, ty))
            pygame.draw.rect(screen, (80, 90, 120), (tx, ty, tw, th), 1)
            screen.blit(txt_surf, (tx + 12, ty + 4))

            ty -= 30

    def _draw_help_modal(self, screen: pygame.Surface):
        """Modal bantuan shortcut editor."""
        mw, mh = 480, 280
        mx = (config.WINDOW_SIZE[0] - mw) // 2
        my = (config.MAP_PIXEL_H - mh) // 2

        modal = pygame.Surface((mw, mh), pygame.SRCALPHA)
        modal.fill((12, 14, 22, 245))
        screen.blit(modal, (mx, my))
        pygame.draw.rect(screen, config.CYAN, (mx, my, mw, mh), 2)

        title = self.font_bold.render("BANTUAN KONTROL COLLISION EDITOR", True, config.GOLD)
        screen.blit(title, (mx + (mw - title.get_width()) // 2, my + 14))

        shortcuts = [
            ("F1", "Toggle mode: OFF -> LIHAT -> EDIT -> OFF"),
            ("Klik Kiri (Tahan & Seret)", "Ubah tile jadi BLOCKED (Oranye)"),
            ("Klik Kanan (Tahan & Seret)", "Ubah tile jadi WALKABLE (Hijau)"),
            ("Shift + Seret Mouse", "Isi area persegi panjang (Box Fill)"),
            ("Tombol C", "Hapus override (kembali ke bawaan map asli)"),
            ("Ctrl + Z  /  Ctrl + Y", "Undo / Redo riwayat perubahan"),
            ("Tombol [  dan  ]", "Kecilkan / Besarkan ukuran kuas (1x1, 2x2, 3x3)"),
            ("Tombol G", "Toggle tampilan garis grid tile"),
            ("Ctrl + S", "Simpan perubahan permanen ke JSON"),
            ("Ctrl + Shift + R", "Reset seluruh override ke default map"),
            ("WASD / Panah", "Geser kamera bebas (Hero tetap diam)"),
            ("Tombol H", "Tutup jendela bantuan ini"),
        ]

        sy = my + 44
        for key_txt, desc_txt in shortcuts:
            k_surf = self.font_tiny.render(key_txt, True, config.CYAN)
            d_surf = self.font_tiny.render(f": {desc_txt}", True, config.WHITE)
            screen.blit(k_surf, (mx + 20, sy))
            screen.blit(d_surf, (mx + 175, sy))
            sy += 18
