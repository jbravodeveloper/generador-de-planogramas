# -*- coding: utf-8 -*-
"""Motor de acomodo: reparte los productos dentro de un modulo de 122 x 180 cm.

Criterio (retail estandar):
  * Zona de GANCHOS arriba  -> productos "Colgado" (cuelgan de la barra, alineados
    por su borde superior; el largo del empaque es lo que se ve en vertical).
  * Zona de TABLILLAS abajo -> productos "Tablilla", los mas altos/pesados al piso.
  * Se conserva el orden del Excel para que las familias queden juntas.
  * Las caras (facings) se agregan de forma pareja hasta llenar el mueble.

Todo el sistema de coordenadas esta en centimetros, con origen en la esquina
inferior izquierda del mueble.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .config import Config
from .excel_reader import Product


@dataclass
class Facing:
    """Una cara individual dibujada en el plano."""
    product: Product
    x: float
    y: float          # borde inferior
    w: float
    h: float
    first: bool       # primera cara del bloque (lleva el numero de ubicacion)


@dataclass
class Level:
    """Una fila de ganchos o una tablilla."""
    kind: str                     # "gancho" | "tablilla"
    index: int                    # 1..n dentro de su zona (de arriba hacia abajo)
    facings: List[Facing] = field(default_factory=list)
    height: float = 0.0           # alto del producto mas alto del nivel
    base_y: float = 0.0           # tablilla: superficie de apoyo
    top_y: float = 0.0            # gancho: altura de la barra
    board_y: float = 0.0          # tablilla: borde inferior de la tabla que la sostiene
    has_board: bool = False

    @property
    def code(self) -> str:
        return ("G%d" if self.kind == "gancho" else "T%d") % self.index

    @property
    def label(self) -> str:
        return ("Gancho fila %d" if self.kind == "gancho" else "Tablilla %d") % self.index


@dataclass
class Module:
    index: int
    cfg: Config
    peg_levels: List[Level] = field(default_factory=list)
    shelf_levels: List[Level] = field(default_factory=list)
    products: List[Product] = field(default_factory=list)   # en orden de numeracion
    shelf_top: float = 0.0        # altura donde termina la zona de tablillas
    peg_bottom: float = 0.0       # altura donde arranca la zona de ganchos

    @property
    def levels(self) -> List[Level]:
        return self.peg_levels + self.shelf_levels

    @property
    def total_facings(self) -> int:
        return sum(len(lv.facings) for lv in self.levels)

    @property
    def fill_pct(self) -> float:
        """% del ancho lineal disponible que queda ocupado por producto."""
        lineal = self.cfg.usable_w * len(self.levels)
        if not lineal:
            return 0.0
        used = sum(f.w for lv in self.levels for f in lv.facings)
        return 100.0 * used / lineal


# --------------------------------------------------------------------------- #
#  Acomodo horizontal
# --------------------------------------------------------------------------- #
@dataclass
class _Block:
    product: Product
    n: int
    w: float


def _max_facings_by_width(p: Product, cfg: Config) -> int:
    """Cuantas caras caben, como maximo, en un solo nivel."""
    n = 1
    while True:
        w = (n + 1) * p.face_w + n * cfg.gap_facing
        if w > cfg.usable_w:
            return n
        n += 1


def _blocks(items, facings, cfg) -> List[_Block]:
    out = []
    for p in items:
        n = max(1, min(facings.get(p.idx, 1), _max_facings_by_width(p, cfg)))
        out.append(_Block(p, n, n * p.face_w + (n - 1) * cfg.gap_facing))
    return out


def _pack_rows(blocks: List[_Block], cfg: Config) -> List[List[_Block]]:
    """Reparte los bloques en filas conservando el orden (first-fit por ancho)."""
    rows, cur, cur_w = [], [], 0.0
    for b in blocks:
        add = b.w if not cur else cfg.gap_x + b.w
        if cur and cur_w + add > cfg.usable_w + 1e-9:
            rows.append(cur)
            cur, cur_w = [b], b.w
        else:
            cur.append(b)
            cur_w += add
    if cur:
        rows.append(cur)
    return rows


def _place_row(level: Level, blocks: List[_Block], cfg: Config, *, top_aligned: bool):
    """Justifica los bloques a lo ancho y crea las caras del nivel."""
    total = sum(b.w for b in blocks)
    n = len(blocks)
    if n > 1:
        gap = (cfg.usable_w - total) / (n - 1)
        gap = max(cfg.gap_x, min(gap, cfg.max_gap_x))
    else:
        gap = 0.0
    used = total + gap * (n - 1)
    x = (cfg.module_w - used) / 2.0

    for b in blocks:
        for i in range(b.n):
            h = b.product.face_h
            y = (level.top_y - h) if top_aligned else level.base_y
            level.facings.append(Facing(b.product, x, y, b.product.face_w, h, first=(i == 0)))
            x += b.product.face_w + cfg.gap_facing
        x += -cfg.gap_facing + gap


# --------------------------------------------------------------------------- #
#  Acomodo vertical
# --------------------------------------------------------------------------- #
def _try_layout(products: List[Product], facings: dict, cfg: Config) -> Optional[Module]:
    """Devuelve el modulo armado, o None si no cabe en el alto disponible."""
    mod = Module(index=1, cfg=cfg)

    colgados = [p for p in products if not p.is_shelf]
    # lo mas alto (y pesado) abajo; en empate se respeta el orden del Excel
    tablilla = sorted((p for p in products if p.is_shelf),
                      key=lambda p: -p.face_h)

    # --- tablillas, de abajo hacia arriba ---
    shelf_rows = _pack_rows(_blocks(tablilla, facings, cfg), cfg)
    alturas = [max(b.product.face_h for b in row) for row in shelf_rows]
    clearance = cfg.shelf_clearance
    if shelf_rows and not colgados:
        # sin zona de ganchos, el aire sobrante se reparte entre las tablillas
        libre = cfg.module_h - cfg.header_h - cfg.base_h
        ocupado = sum(alturas) + cfg.shelf_t * (len(shelf_rows) - 1)
        clearance = max(clearance, min((libre - ocupado) / len(shelf_rows), 30.0))

    y = cfg.base_h
    built = []
    for i, (row, h) in enumerate(zip(shelf_rows, alturas)):
        lv = Level(kind="tablilla", index=0)
        if i > 0:
            lv.board_y = y
            lv.has_board = True
            y += cfg.shelf_t
        lv.base_y = y
        lv.height = h
        _place_row(lv, row, cfg, top_aligned=False)
        built.append(lv)
        y += h + clearance
    shelf_top = y if shelf_rows else cfg.base_h
    if shelf_top > cfg.module_h - cfg.header_h:
        return None

    # numeracion de tablillas de arriba hacia abajo
    for i, lv in enumerate(reversed(built), start=1):
        lv.index = i
    mod.shelf_levels = list(reversed(built))

    # --- ganchos, de arriba hacia abajo ---
    zone_top = cfg.module_h - cfg.header_h
    zone_bottom = shelf_top
    if colgados and shelf_rows:
        zone_bottom += cfg.peg_zone_gap
    if colgados and zone_bottom > zone_top:
        return None
    mod.shelf_top = shelf_top
    mod.peg_bottom = zone_bottom

    peg_rows = _pack_rows(_blocks(colgados, facings, cfg), cfg)
    if peg_rows:
        heights = [max(b.product.face_h for b in row) for row in peg_rows]
        needed = sum(heights) + cfg.peg_gap * (len(peg_rows) + 1)
        avail = zone_top - zone_bottom
        if needed > avail + 1e-9:
            return None
        extra = (avail - needed) / (len(peg_rows) + 1)
        bar = zone_top
        for i, (row, h) in enumerate(zip(peg_rows, heights), start=1):
            bar -= cfg.peg_gap + extra
            lv = Level(kind="gancho", index=i, height=h, top_y=bar)
            _place_row(lv, row, cfg, top_aligned=True)
            mod.peg_levels.append(lv)
            bar -= h
    elif not shelf_rows:
        return None

    _number(mod)
    return mod


def _number(mod: Module):
    """Numera de arriba hacia abajo y de izquierda a derecha; una cara por producto."""
    n = 0
    seen = set()
    ordered = []
    for lv in mod.levels:
        for f in sorted(lv.facings, key=lambda f: f.x):
            if not f.first or f.product.idx in seen:
                continue
            seen.add(f.product.idx)
            n += 1
            f.product.number = n
            f.product.location = lv.code
            ordered.append(f.product)
    mod.products = ordered


# --------------------------------------------------------------------------- #
#  Optimizacion de caras y reparto en modulos
# --------------------------------------------------------------------------- #
def _base_facings(products: List[Product]) -> dict:
    """Punto de partida: la columna 'Caras' del Excel si existe, si no 1 por producto."""
    return {p.idx: (p.facings_fixed or 1) for p in products}


def _optimize(products: List[Product], cfg: Config) -> Optional[Module]:
    facings = _base_facings(products)
    mod = _try_layout(products, facings, cfg)
    if mod is None:
        return None
    if not cfg.auto_facings:
        return mod

    caps = {p.idx: min(cfg.max_facings, _max_facings_by_width(p, cfg)) for p in products}
    while True:
        # el producto con menos caras primero; en empate, el orden del Excel
        order = sorted(products, key=lambda p: (facings[p.idx], p.idx))
        for p in order:
            if facings[p.idx] >= caps[p.idx]:
                continue
            trial = dict(facings)
            trial[p.idx] += 1
            cand = _try_layout(products, trial, cfg)
            if cand is not None:
                facings, mod = trial, cand
                break
        else:
            return mod


def build_modules(products: List[Product], cfg: Config):
    """Arma uno o mas modulos de 122 x 180 cm. Devuelve (modulos, avisos)."""
    warnings = []
    usables = []
    for p in products:
        if p.face_w > cfg.usable_w:
            warnings.append("%s: %.1f cm de ancho, no cabe en un modulo de %.0f cm."
                            % (p.description, p.face_w, cfg.module_w))
        else:
            usables.append(p)
    if not usables:
        raise ValueError("Ningun producto cabe en el modulo con las medidas indicadas.")

    modules, pending, offset = [], list(usables), 0
    while pending:
        # cuantos productos (en orden) caben con la cantidad base de caras
        n = len(pending)
        while n > 0 and _try_layout(pending[:n], _base_facings(pending[:n]), cfg) is None:
            n -= 1
        if n == 0:
            p = pending[0]
            aviso = ("'%s' (%g x %g cm de cara) no se pudo acomodar en el modulo y se omite."
                     % (p.description, p.face_w, p.face_h))
            if aviso not in warnings:
                warnings.append(aviso)
            pending = pending[1:]
            continue
        mod = _optimize(pending[:n], cfg)
        mod.index = len(modules) + 1
        for p in mod.products:                       # numeracion continua entre modulos
            p.number += offset
        offset += len(mod.products)
        modules.append(mod)
        pending = pending[n:]

    if not modules:
        raise ValueError("No fue posible acomodar los productos en el modulo.")
    return modules, warnings
