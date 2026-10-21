"""game/ambush/overlay_ambush.py - Renderer overlay debug Ambush Director.

Hanya menggambar; angka dibaca dari view dict (dibangun build_view dari
trace buffer + konteks director). Trace yang SAMA dibaca exporter CSV.
Toggle F3; tab T (ALL/CSP/LS/CMP) saat overlay tampil.
"""
from __future__ import annotations

import pygame

from game.ambush.buff import summarize_squad
from game.ambush.config import AmbushConfig
from game.ambush.trace import TraceBuffer
from game.ambush.types import display_role

GREEN = (140, 240, 170)
RED = (240, 120, 120)
YELLOW = (240, 196, 96)
TEXT = (232, 238, 248)
DIM = (150, 165, 190)
HEAD = (210, 226, 255)

TABS = ("ALL", "CSP", "LS", "CMP")

CALIB_LINE = "objektif: sim ringan | rerank: sim penuh | calib: partial"


def _f(value) -> str:
    if value == "" or value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _trim(font: pygame.font.Font, text: str,
           color: tuple, max_w: int) -> pygame.Surface:
    """Render teks dipotong ellipsis agar muat dalam max_w piksel."""
    if font.size(text)[0] <= max_w:
        return font.render(text, True, color)
    ell = "..."
    while text and font.size(text + ell)[0] > max_w:
        text = text[:-1]
    return font.render(text + ell if text else ell, True, color)


def event_log(tracer: TraceBuffer, limit: int = 6):
    """3-6 baris terakhir bernarasi (simbol hasil). Untuk overlay + demo."""
    out = []
    for e in reversed(tracer.events):
        line = _narrate(e)
        if line is not None:
            out.append(line)
        if len(out) >= limit:
            break
    return list(reversed(out))


def _narrate(e: dict):
    kind = e["kind"]
    if kind == "assign":
        return (f"CSP isi {e.get('var')}={e.get('val')} +", GREEN)
    if kind == "reject":
        return (f"CSP {e.get('var')}={e.get('val')} X "
                f"melanggar: {e.get('reason')} ", RED)
    if kind == "backtrack":
        return (f"backtrack (kedalaman {e.get('depth', '?')}) -> coba lain",
                YELLOW)
    if kind == "revise":
        left = e.get("left", 0) or 0
        rem = e.get("removed", 0) or 0
        return (f"AC-3 hapus {e.get('xi')} "
                f"-> domain {left + rem}->{left} (via {e.get('xj')})", YELLOW)
    if kind == "fc_prune":
        left = e.get("left", 0) or 0
        rem = e.get("removed", 0) or 0
        return (f"FC pangkas {e.get('var')}: {left + rem}->{left}", YELLOW)
    if kind == "ac3_pre":
        det = ", ".join(f"{a}>{b}(-{r})" for a, b, r in
                        (e.get("details") or [])[:3])
        return (f"AC-3 pra-pencarian: hapus {e.get('removed', 0)} value"
                + (f" [{det}]" if det else ""), YELLOW)
    if kind == "ls_start":
        return (f"LS {e.get('algo')} mulai (gap { _f(e.get('start_gap'))})",
                YELLOW)
    if kind == "ls_skip":
        return (f"LS dilewati: seed sudah dalam toleransi "
                f"(gap {_f(e.get('gap'))} <= {_f(e.get('tol'))})", GREEN)
    if kind == "ls_iter":
        took = e.get("took")
        rej = e.get("rejected") or 0
        if took is None:
            return (f"LS iter {e.get('it')}: {_f(e.get('current'))} buntu "
                    f"(tolak_CSP {rej})", RED)
        return (f"LS {took.get('kind')} {took.get('detail')}: "
                f"{_f(e.get('prev', e.get('current')))}->"
                f"{_f(took.get('gap'))} diterima", GREEN)
    if kind == "ls_sa":
        ok = e.get("accepted")
        return (f"SA T={_f(e.get('temp'))} dE={_f(e.get('delta_e'))} "
                f"p={_f(e.get('prob'))} u={_f(e.get('u'))} "
                f"{'TERIMA' if ok else 'TOLAK'}", GREEN if ok else RED)
    if kind == "ga_gen":
        return (f"GA gen {e.get('gen')}: fit "
                f"{_f(e.get('best_fit'))}/{_f(e.get('avg_fit'))}", TEXT)
    if kind == "ls_restart":
        return (f"restart {e.get('restart')}: best "
                f"{_f(e.get('best_gap'))} ({e.get('stop')})", TEXT)
    if kind == "ls_rerank":
        return (f"rerank sim-penuh: {e.get('picked')}", GREEN)
    if kind == "director_done":
        return (f"selesai: gap {_f(e.get('gap'))} "
                f"{'valid' if e.get('verified') else 'INVALID'}", GREEN)
    return None


def build_view(tracer: TraceBuffer, ctx: dict) -> dict:
    """Rakit view overlay dari trace + konteks director (dipanggil per frame)."""
    select = tracer.latest("select") or {}
    lcv = tracer.latest("lcv") or tracer.latest("order") or {}
    revise = tracer.latest("revise") or {}
    csp_done = tracer.latest("csp_done") or {}
    ac3_pre = tracer.latest("ac3_pre") or {}
    sa = tracer.latest("ls_sa") or {}
    ga = tracer.latest("ga_gen") or {}
    it = tracer.latest("ls_iter") or {}
    skip = tracer.latest("ls_skip") or {}
    ls_start_ev = tracer.latest("ls_start") or {}
    rerank = tracer.latest("ls_rerank") or {}
    done = tracer.latest("director_done") or {}
    restarts = len(tracer.of_kind("ls_restart"))
    rejected = sum(int(e.get("rejected") or 0)
                   for e in tracer.of_kind("ls_iter"))
    # Best GLOBAL lintas restart/run (bukan event terakhir): "best" overlay
    # selalu sama dengan "akhir" director. Riwayat = best-so-far kumulatif
    # (monoton) dengan indeks global agar sparkline tak reset per restart.
    bests = []
    for e in tracer.events:
        if e["kind"] in ("ls_iter", "ls_sa") and e.get("best") != "":
            try:
                bests.append(float(e["best"]))
            except (TypeError, ValueError):
                pass
        elif e["kind"] == "ga_gen" and e.get("best_gap") not in ("", None):
            bests.append(float(e["best_gap"]))
    global_best = min(bests) if bests else ""
    history = []
    running_best = None
    idx = 0
    for e in tracer.events:
        if e["kind"] == "ls_iter" and e.get("it") is not None:
            cur = e.get("current", 0.0) or 0.0
            running_best = cur if running_best is None else min(
                running_best, float(e.get("best", cur)))
            history.append((idx, cur, running_best))
            idx += 1
        elif e["kind"] == "ls_sa" and e.get("it") is not None:
            cur = e.get("current", 0.0) or 0.0
            running_best = cur if running_best is None else min(
                running_best, float(e.get("best", cur)))
            history.append((idx, cur, running_best))
            idx += 1
        elif e["kind"] == "ga_gen" and e.get("gen") is not None:
            g = e.get("best_gap", 0.0) or 0.0
            running_best = g if running_best is None else min(running_best, g)
            history.append((idx, g, running_best))
            idx += 1
    # Langkah buruk SA yang diterima (dihitung dari trace, bukan memori).
    sa_bad = sum(1 for e in tracer.of_kind("ls_sa")
                 if e.get("accepted") and (e.get("delta_e") or 0) < 0)
    sw_left = it.get("sideways_left")
    sideways = ""
    if sw_left is not None and ctx.get("sideways_limit") is not None:
        sideways = (f"{ctx['sideways_limit'] - sw_left}/"
                    f"{ctx['sideways_limit']}")
    squad = ctx.get("squad")
    buff_lines = []
    if squad is not None:
        # Satu sumber kebenaran yang sama dengan battle (BuffSummary).
        buff_lines = summarize_squad(squad, AmbushConfig()).lines()
    # Loadout player tampil terus di fase NPC (spek C.2).
    from game.ambush.player_loadout import describe_item
    pl = ctx.get("player_loadout")
    pl_lines = []
    if pl is not None:
        pl_lines = [f"Slot {i + 1}: {it} ({describe_item(it)})"
                    for i, it in enumerate(pl.items)]
    # HP masuk rata-rata per posisi dari rerank (bukti urutan penting).
    sim_entries = ctx.get("sim_entries") or []
    k_positions = ctx.get("k_positions", 0) or 0
    sim_hp_in = []
    if sim_entries and k_positions:
        buckets = [[] for _ in range(k_positions)]
        for pos, (hp, _pot) in enumerate(sim_entries):
            buckets[pos % k_positions].append(hp)
        sim_hp_in = [round(sum(b) / len(b), 1) if b else None
                     for b in buckets]
    return {
        "phase": ctx.get("phase", "csp"),
        "status": ctx.get("status", "berjalan"),
        "ls_algo": ctx.get("ls_algo", "-"),
        "target": ctx.get("target", 0.0),
        "target_label": ctx.get("target_label", ""),
        "target_tol": ctx.get("target_tol", 0.02),
        "seed_mode": ctx.get("seed_mode", ""),
        "pump": ctx.get("pump", "instant"),
        "toggles": ctx.get("toggles", {}),
        "nodes": csp_done.get("nodes", select.get("nodes", 0)),
        "backtracks": csp_done.get("backtracks",
                                   select.get("backtracks", 0)),
        "pruned": csp_done.get("pruned", select.get("pruned", 0)),
        "csp_ms": round(csp_done.get("time_ms", 0.0), 2),
        "csp_stop": csp_done.get("stop", ""),
        "var": select.get("var", "-"),
        "reason": select.get("reason", "-"),
        "domains": select.get("domains", {}),
        "domains0": ctx.get("domains0", {}),
        "candidates": lcv.get("candidates") or [],
        "queue": revise.get("queue", 0),
        "arc": f"{revise.get('xi', '-')}>{revise.get('xj', '-')}"
               if revise else "-",
        "removed": revise.get("removed", 0),
        "queue_max": csp_done.get("queue_max", 0),
        "revises": csp_done.get("revises", 0),
        "ac3_pre": ac3_pre,
        "complete_consistent": ctx.get("complete_consistent", ""),
        "ls_it": it.get("it", sa.get("it", ga.get("gen", 0))),
        "cur": it.get("current", sa.get("current", "")),
        "best": global_best if global_best != "" else it.get(
            "best", sa.get("best", ga.get("best_gap", ""))),
        "sideways": sideways,
        "restarts": restarts,
        "evaluated": it.get("evaluated", ""),
        "rejected": rejected,
        "sa": sa,
        "sa_bad": sa_bad,
        "ga_best": ga.get("best_fit", ""),
        "ga_avg": ga.get("avg_fit", ""),
        "ga_pop": ga.get("pop_summary", ""),
        "ls_stop": ctx.get("ls_stop", ""),
        "ls_skip": skip,
        "prefilter": "heuristik" if ls_start_ev.get("prefilter") else "",
        "seed_gap": ctx.get("seed_gap", ""),
        "final_gap": done.get("gap", ""),
        "verified": done.get("gap") is not None and done.get("verified"),
        "history": history,
        "squad": squad,
        "buff_lines": buff_lines,
        "pl_lines": pl_lines,
        "sim": ctx.get("sim", ""),
        "sim_gap": ctx.get("sim_gap", ""),
        "prefilter": ctx.get("prefilter", ""),
        "seed_queue": ctx.get("seed_queue"),
        "final_queue": ctx.get("final_queue"),
        "budget": ctx.get("budget", ""),
        "per_duel": ctx.get("per_duel"),
        "sim_hp_in": sim_hp_in,
        "honest": ctx.get("honest", ""),
        "ceiling": ctx.get("ceiling", ""),
        "event_log": event_log(tracer),
        "compare": ctx.get("compare"),
    }


class AmbushDebugOverlay:
    """Panel debug pembentukan squad/antrean (saat fase persiapan)."""

    def __init__(self):
        self.visible = True
        self.tab = 0  # 0=ALL 1=CSP 2=LS 3=CMP (tombol T)
        self.view: dict = {}

    def update(self, view: dict) -> None:
        """Simpan snapshot view terbaru."""
        self.view = view

    def cycle_tab(self) -> None:
        """Ganti tab tampilan (tombol T saat overlay tampil)."""
        self.tab = (self.tab + 1) % len(TABS)

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Gambar panel kanan; no-op bila disembunyikan atau view kosong."""
        if not self.visible or not self.view:
            return
        v = self.view
        w, h = screen.get_size()
        pad = 12
        lh = font.get_height() + 3
        rows = self._rows(v, TABS[self.tab])
        label_w = max([font.size(r[1])[0] for r in rows] + [0])
        pw = min(w - 40, 660, label_w + pad * 3
                 + max([font.size(r[2])[0] for r in rows] + [0]))
        # Cadangan sparkline + kontrol selalu terlihat (konten dipotong).
        reserve = 64 + lh
        ph = min(h - 40, pad * 2 + lh * len(rows) + reserve)
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        running = v["status"] == "berjalan"
        edge = YELLOW if running else GREEN
        pygame.draw.rect(panel, (12, 16, 26, 232), panel.get_rect(),
                         border_radius=12)
        pygame.draw.rect(panel, (*edge, 235), panel.get_rect(), 2,
                         border_radius=12)
        y = pad
        max_w = pw - pad * 2
        # Kontrol + sparkline selalu terlihat (disematkan bawah).
        ctrl = [r for r in rows if r[1] == "" and r[2].startswith("[F3]")]
        body = [r for r in rows if r not in ctrl]
        spark_h = 56
        bottom_y = ph - pad - lh * len(ctrl) - spark_h - 6
        for _sec, label, value, color in body:
            if y + lh > bottom_y:
                break
            # Kolom label:nilai sejajar; ellipsis agar tak terpotong panel.
            line = f"{label:<{self._lw(rows)}} {value}" if label else value
            panel.blit(_trim(font, line, color, max_w), (pad, y))
            y += lh
        cy = bottom_y + 4
        for _sec, _label, value, color in ctrl:
            panel.blit(_trim(font, value, color, max_w), (pad, cy))
            cy += lh
        self._sparkline(panel, v, pygame.Rect(pad, cy + 2, pw - pad * 2,
                                              ph - cy - pad - 4))
        # Panel kanan dengan padding 12px dari tepi (tak terpotong).
        screen.blit(panel, (w - pw - 12, 12))

    @staticmethod
    def _lw(rows) -> int:
        return max([len(r[1]) for r in rows] + [0])

    def _rows(self, v: dict, tab: str = "ALL"):
        rows = self._all_rows(v)
        if tab != "ALL":
            rows = [r for r in rows if r[0] in ("H", tab)]
        return rows

    def _all_rows(self, v: dict):
        R = []  # (seksi, label, nilai, warna)
        phase = {"PREP_NPC_CSP": "CSP", "PREP_NPC_LS": "LOCAL SEARCH",
                 "PREP_REVIEW": "REVIEW"}.get(v["phase"], v["phase"])
        R.append(("H", "", f"AMBUSH [{phase}] {v['status']}", HEAD))
        R.append(("H", "", f"algo {v['ls_algo']} | pump {v['pump']} | "
                           f"{v['seed_mode'] or 'SEED: BEST (gameplay)'}",
                  DIM))
        R.append(("H", "", f"target {_f(v['target'])} "
                           f"{v['target_label'] or ''}| {CALIB_LINE}", DIM))
        tg = v["toggles"]
        R.append(("H", "", f"CSP mrv={tg.get('mrv', '-')} "
                           f"deg={tg.get('deg', '-')} "
                           f"lcv={tg.get('lcv', '-')} "
                           f"infer={tg.get('infer', '-')}", DIM))
        for line, color in v.get("event_log", []):
            R.append(("H", "", line, color))
        if v.get("pl_lines"):
            R.append(("H", "", "--- LOADOUT PLAYER ---", GREEN))
            for line in v["pl_lines"][:2]:
                R.append(("H", "", f"  {line}"[:64], TEXT))
        R.append(("CSP", "", "--- CSP ---", YELLOW))
        R.append(("CSP", "nodes/back/prune",
                  f"{v['nodes']}/{v['backtracks']}/{v['pruned']} "
                  f"{v['csp_ms']}ms {v['csp_stop']}", TEXT))
        R.append(("CSP", "var", f"{v['var']} ({v['reason']})", TEXT))
        doms, doms0 = v["domains"], v.get("domains0", {})
        if doms:
            R.append(("CSP", "domain",
                      " ".join(f"{k.split('_')[0][0]}{k.split('_')[1]}:"
                               f"{doms0.get(k, '?')}->{n}"
                               for k, n in sorted(doms.items())), TEXT))
        cands = v["candidates"]
        for c in cands[:4]:
            R.append(("CSP", "", f"  LCV {c.get('val')}: "
                                 f"buang {c.get('removed')}", DIM))
        if len(cands) > 4:
            R.append(("CSP", "", f"  ... +{len(cands) - 4} kandidat", DIM))
        R.append(("CSP", "AC-3",
                  f"queue={v['queue']}/max{v.get('queue_max', 0)} "
                  f"arc={v['arc']} hapus={v['removed']} "
                  f"rev={v.get('revises', 0)}", TEXT))
        if v.get("ac3_pre") and v["ac3_pre"].get("removed", 0):
            R.append(("CSP", "", f"AC-3 pra: hapus "
                                 f"{v['ac3_pre'].get('removed', 0)} value",
                      YELLOW))
        if v.get("complete_consistent"):
            R.append(("CSP", "", v["complete_consistent"], GREEN))
        R.append(("LS", "", "--- LOCAL SEARCH ---", YELLOW))
        if v.get("ls_skip"):
            sk = v["ls_skip"]
            R.append(("LS", "", f"LS dilewati: seed sudah dalam toleransi "
                                f"(gap {_f(sk.get('gap'))} "
                                f"<= {_f(sk.get('tol'))})", GREEN))
        R.append(("LS", "iter/cur/best",
                  f"{v['ls_it']}/{_f(v['cur'])}/{_f(v['best'])} "
                  f"target={_f(v['target'])}", TEXT))
        if v["sideways"] != "":
            R.append(("LS", "sideways/eval/tolak",
                      f"{v['sideways']} / {v['evaluated']} / "
                      f"{v['rejected']}", TEXT))
        else:
            R.append(("LS", "restart/tolak",
                      f"{v['restarts']} / {v['rejected']}", TEXT))
        sa = v["sa"]
        if sa:
            ok = sa.get("accepted")
            R.append(("LS", "SA",
                      f"T={_f(sa.get('temp'))} dE={_f(sa.get('delta_e'))} "
                      f"p={_f(sa.get('prob'))} u={_f(sa.get('u'))} "
                      f"{'TERIMA' if ok else 'TOLAK'} "
                      f"(buruk:{v.get('sa_bad', 0)})",
                      GREEN if ok else RED))
        if v["ga_pop"] != "":
            R.append(("LS", "GA fit",
                      f"best={_f(v['ga_best'])} avg={_f(v['ga_avg'])}",
                      TEXT))
            R.append(("LS", "", f"pop: {v['ga_pop']}"[:64], DIM))
        if v["ls_stop"]:
            R.append(("LS", "", f"berhenti: {v['ls_stop']}", GREEN))
        if v.get("prefilter"):
            R.append(("LS", "", f"pra-penyaring: {v['prefilter']} (approx)",
                      DIM))
        R.append(("LS", "", "--- SEBELUM vs SESUDAH ---", YELLOW))
        R.append(("LS", "seed->akhir",
                  f"{_f(v['seed_gap'])}->{_f(v['final_gap'])} "
                  f"(target {_f(v['target'])})",
                  GREEN if v["verified"] else TEXT))
        for tag, qq in (("seed", v.get("seed_queue")),
                        ("akhir", v.get("final_queue"))):
            if qq is not None:
                _order = ">".join(display_role(s.role) for s in qq.slots)
                R.append(("LS", tag,
                          f"{_order} "
                          f"cost={qq.total_cost()}/{v.get('budget', '?')}",
                          TEXT))
        R.append(("LS", "ringan/sim",
                  f"{_f(v['best'])}/{v['sim'] or '-'} "
                  f"(selisih {_diff_str(v)})", TEXT))
        if v.get("honest"):
            R.append(("LS", "", v["honest"], YELLOW))
        if v.get("ceiling"):
            R.append(("LS", "", v["ceiling"], YELLOW))
        per, hp_in = v.get("per_duel"), v.get("sim_hp_in") or []
        if per:
            R.append(("LS", "", "--- PER POSISI (urutan penting) ---",
                      YELLOW))
            for i, (hp, pw, _ho) in enumerate(per):
                sim_h = hp_in[i] if i < len(hp_in) and hp_in[i] is not None \
                    else "-"
                R.append(("LS", f"duel{i + 1}",
                          f"p={pw:.2f} masuk~{sim_h}", TEXT))
        squad = v["squad"]
        if squad is not None:
            R.append(("LS", "", "--- ANTREAN ---", YELLOW))
            for i, (r, it) in enumerate(zip(squad.roles, squad.items)):
                if r == "NONE":
                    continue
                R.append(("LS", f"#{i + 1}",
                          f"{display_role(r)} [{it}]", TEXT))
            for line in v.get("buff_lines", [])[:4]:
                R.append(("LS", "", f"  * {line}", GREEN))
        cmp_ = v.get("compare")
        if cmp_ is not None:
            R.append(("CMP", "", "--- PERBANDINGAN ---", YELLOW))
            if not cmp_.get("done"):
                R.append(("CMP", "", f"menghitung... {cmp_.get('idx', 0)}/"
                                     f"{cmp_.get('total', '?')}", YELLOW))
            results = cmp_.get("results") or {}
            show = results.items() if TABS[self.tab] == "CMP" else list(
                results.items())[:3]
            for name, row in show:
                R.append(("CMP", name,
                          f"gap={row.get('gap')} eval={row.get('evals')} "
                          f"{row.get('ms')}ms", TEXT))
            if TABS[self.tab] != "CMP" and len(results) > 3:
                R.append(("CMP", "",
                          f"... +{len(results) - 3} (T: tab CMP detail)",
                          DIM))
        R.append(("H", "", "[F3] overlay [T] tab [TAB] algo [F4] pump "
                           "[Spasi] step [C] target [X] seed [G] ulang "
                           "[Enter] duel [H] HUD",
                  DIM))
        return R

    def _sparkline(self, panel: pygame.Surface, v: dict,
                   rect: pygame.Rect) -> None:
        """Grafik gap per iterasi + garis toleransi (gap <= tol = target).

        Sumbu-Y adalah GAP (|difficulty - target|), bukan difficulty. Karena
        itu garis acuan yang benar adalah toleransi gap, BUKAN target
        difficulty: nilai target (mis. 0.500) bisa jauh di atas gap maksimum
        dan dulu tergambar keluar kotak (garis kuning melintang di tengah
        teks overlay). Garis acuan kini selalu dijepit di dalam kotak.
        """
        hist = v["history"]
        if rect.height < 24 or not hist:
            return
        pygame.draw.rect(panel, (30, 36, 50), rect, border_radius=4)
        gaps = [float(h[2]) for h in hist]
        try:
            tol = float(v.get("target_tol", 0.02) or 0.02)
        except (TypeError, ValueError):
            tol = 0.02
        # Sertakan toleransi dalam skala agar garis acuan tak pernah keluar
        # kotak (dulu hi = max(gap) saja, target 0.5 -> ty negatif).
        hi = max(max(gaps), tol * 1.5, 0.05)
        n = len(gaps)
        prev = None
        for i, g in enumerate(gaps):
            x = rect.x + int(i / max(1, n - 1) * (rect.width - 4)) + 2
            y = rect.y + rect.height - 3 - int(
                (g - 0.0) / (hi - 0.0) * (rect.height - 6))
            if prev is not None:
                pygame.draw.line(panel, GREEN, prev, (x, y), 2)
            prev = (x, y)
        if tol > 0:
            ty = rect.y + rect.height - 3 - int(
                tol / (hi - 0.0) * (rect.height - 6))
            ty = max(rect.top + 1, min(rect.bottom - 2, ty))
            pygame.draw.line(panel, DIM, (rect.x + 2, ty),
                             (rect.right - 2, ty), 1)


def _diff_str(v: dict) -> str:
    try:
        d = abs(float(v.get("best") or 0) - float(v.get("sim") or 0))
        return f"{d:.3f}"
    except (TypeError, ValueError):
        return "-"
