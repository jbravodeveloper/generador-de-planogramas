# -*- coding: utf-8 -*-
"""Salida en PDF: una hoja con el plano por modulo y las hojas de detalle."""

from __future__ import annotations

import datetime
import itertools
import os
from typing import List

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .config import Config
from .images import reader
from .layout import Module

# --------------------------------------------------------------------------- #
#  Paleta
# --------------------------------------------------------------------------- #
NAVY = HexColor("#173A5E")
NAVY_SOFT = HexColor("#2C5C8F")
INK = HexColor("#1F2933")
MUTED = HexColor("#6B7683")
BOARD = HexColor("#A8B2BD")
BOARD_DARK = HexColor("#7C8794")
LINE = HexColor("#C9D1DA")
BORDER = HexColor("#AEB8C4")
PEG_BG = HexColor("#F7F9FB")
SHELF_BG = HexColor("#F1F4F7")
ZEBRA = HexColor("#F2F5F8")
ACCENT = HexColor("#C8102E")

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"

PAGE_W, PAGE_H = A4
MARGIN = 14 * mm
GUTTER = 19 * mm          # regleta de alturas a la izquierda del mueble


# --------------------------------------------------------------------------- #
#  Utilidades de texto
# --------------------------------------------------------------------------- #
def _fit(c, text, font, size, max_w):
    """Recorta el texto con '...' para que quepa en max_w."""
    text = text or ""
    if c.stringWidth(text, font, size) <= max_w:
        return text
    while text and c.stringWidth(text + "...", font, size) > max_w:
        text = text[:-1]
    return text + "..." if text else ""


def _shrink(c, text, font, max_size, min_size, max_w):
    size = max_size
    while size > min_size and c.stringWidth(text, font, size) > max_w:
        size -= 0.5
    return size


def _wrap(c, text, font, size, max_w, max_lines=2):
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        probe = (cur + " " + w).strip()
        if c.stringWidth(probe, font, size) <= max_w or not cur:
            cur = probe
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines:
        used = len(" ".join(lines).split())
        if used < len(words):
            lines[-1] = _fit(c, lines[-1] + " " + " ".join(words[used:]), font, size, max_w)
    return lines


# --------------------------------------------------------------------------- #
#  Encabezado / pie
# --------------------------------------------------------------------------- #
def _header(c, categoria, sub, right=""):
    y = PAGE_H - MARGIN
    c.setFillColor(NAVY)
    c.setFont(FONT_B, _shrink(c, categoria.upper(), FONT_B, 22, 12, PAGE_W - 2 * MARGIN - 60 * mm))
    c.drawString(MARGIN, y - 16, categoria.upper())
    c.setFillColor(MUTED)
    c.setFont(FONT, 8.5)
    c.drawString(MARGIN, y - 28, sub)
    if right:
        c.drawRightString(PAGE_W - MARGIN, y - 28, right)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.6)
    c.line(MARGIN, y - 36, MARGIN + 34, y - 36)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(MARGIN + 38, y - 36, PAGE_W - MARGIN, y - 36)
    return y - 36


def _footer(c, texto, pagina, total):
    c.setFillColor(MUTED)
    c.setFont(FONT, 7)
    c.drawString(MARGIN, MARGIN - 5, texto)
    c.drawRightString(PAGE_W - MARGIN, MARGIN - 5, "Página %d de %d" % (pagina, total))


# --------------------------------------------------------------------------- #
#  Plano del modulo
# --------------------------------------------------------------------------- #
def _draw_module(c, mod: Module, cfg: Config, categoria: str, area):
    """Dibuja el mueble dentro de `area` = (x, y, ancho, alto) en puntos."""
    ax, ay, aw, ah = area
    aw -= GUTTER
    ax += GUTTER
    sc = min(aw / cfg.module_w, ah / cfg.module_h)          # puntos por cm
    mw, mh = cfg.module_w * sc, cfg.module_h * sc
    x0 = ax + (aw - mw) / 2.0
    y0 = ay + (ah - mh) / 2.0

    X = lambda cm: x0 + cm * sc
    Y = lambda cm: y0 + cm * sc

    header_bottom = cfg.module_h - cfg.header_h

    # --- fondos de zona ---
    c.setFillColor(PEG_BG)
    c.rect(X(0), Y(mod.peg_bottom), mw, (header_bottom - mod.peg_bottom) * sc, stroke=0, fill=1)
    c.setFillColor(SHELF_BG)
    c.rect(X(0), Y(0), mw, mod.shelf_top * sc, stroke=0, fill=1)

    # malla del panel perforado
    if mod.peg_levels:
        c.setFillColor(HexColor("#DFE6ED"))
        step = 4.0
        yy = mod.peg_bottom + step / 2
        while yy < header_bottom - 1:
            xx = cfg.side_margin
            while xx < cfg.module_w - cfg.side_margin:
                c.circle(X(xx), Y(yy), 0.5, stroke=0, fill=1)
                xx += step
            yy += step

    # --- zocalo y tablillas ---
    c.setFillColor(BOARD)
    c.rect(X(0), Y(0), mw, cfg.base_h * sc, stroke=0, fill=1)
    c.setFillColor(BOARD_DARK)
    c.rect(X(0), Y(cfg.base_h - 0.8), mw, 0.8 * sc, stroke=0, fill=1)
    for lv in mod.shelf_levels:
        if lv.has_board:
            c.setFillColor(BOARD)
            c.rect(X(0), Y(lv.board_y), mw, cfg.shelf_t * sc, stroke=0, fill=1)

    # --- barras de ganchos ---
    c.setStrokeColor(BOARD_DARK)
    c.setLineWidth(1.1)
    for lv in mod.peg_levels:
        c.line(X(cfg.side_margin * 0.4), Y(lv.top_y), X(cfg.module_w - cfg.side_margin * 0.4), Y(lv.top_y))

    # --- productos ---
    for lv in mod.levels:
        for block in _blocks_of(lv):
            for f in block:
                _draw_facing(c, f, X, Y, sc)
            bx0 = X(block[0].x)
            bx1 = X(block[-1].x + block[-1].w)
            top = Y(max(f.y + f.h for f in block))
            _badge(c, (bx0 + bx1) / 2.0, top, str(block[0].product.number))

    # --- rotulo de categoria ---
    c.setFillColor(NAVY)
    c.rect(X(0), Y(header_bottom), mw, cfg.header_h * sc, stroke=0, fill=1)
    c.setFillColor(white)
    size = _shrink(c, categoria.upper(), FONT_B, min(16, cfg.header_h * sc * 0.42), 6, mw - 20)
    c.setFont(FONT_B, size)
    c.drawCentredString(x0 + mw / 2, Y(header_bottom) + cfg.header_h * sc / 2 - size * 0.35,
                        categoria.upper())

    # --- marco ---
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.3)
    c.rect(X(0), Y(0), mw, mh, stroke=1, fill=0)

    # --- regleta de alturas ---
    c.setFont(FONT, 6)
    for lv in mod.levels:
        h_cm = lv.top_y if lv.kind == "gancho" else lv.base_y
        yy = Y(h_cm)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.line(x0 - 5, yy, x0, yy)
        c.setFillColor(NAVY_SOFT)
        c.setFont(FONT_B, 5.8)
        c.drawRightString(x0 - 7.5, yy - 2, lv.code)
        c.setFillColor(MUTED)
        c.setFont(FONT, 6)
        c.drawRightString(x0 - 20, yy - 2, "%g" % round(h_cm, 1))

    # --- cotas ---
    c.setStrokeColor(MUTED)
    c.setLineWidth(0.5)
    dx = x0 - GUTTER + 5
    c.line(dx, y0, dx, y0 + mh)
    for yy in (y0, y0 + mh):
        c.line(dx - 2.5, yy, dx + 2.5, yy)
    c.saveState()
    c.translate(dx - 3, y0 + mh / 2)
    c.rotate(90)
    c.setFillColor(MUTED)
    c.setFont(FONT_B, 7)
    c.drawCentredString(0, 1.5, "%g cm" % cfg.module_h)
    c.restoreState()

    dy = y0 - 11
    c.line(x0, dy, x0 + mw, dy)
    for xx in (x0, x0 + mw):
        c.line(xx, dy - 2.5, xx, dy + 2.5)
    c.setFillColor(MUTED)
    c.setFont(FONT_B, 7)
    c.drawCentredString(x0 + mw / 2, dy - 8, "%g cm" % cfg.module_w)

    # --- leyenda de zonas ---
    c.setFont(FONT, 6)
    c.setFillColor(NAVY_SOFT)
    if mod.peg_levels:
        c.saveState()
        c.translate(x0 + mw + 6, Y((mod.peg_bottom + header_bottom) / 2))
        c.rotate(-90)
        c.drawCentredString(0, 0, "ZONA COLGADO")
        c.restoreState()
    if mod.shelf_levels:
        c.saveState()
        c.translate(x0 + mw + 6, Y(mod.shelf_top / 2))
        c.rotate(-90)
        c.drawCentredString(0, 0, "ZONA TABLILLA")
        c.restoreState()


def _blocks_of(level):
    """Agrupa las caras contiguas de un mismo producto."""
    caras = sorted(level.facings, key=lambda f: f.x)
    return [list(g) for _, g in itertools.groupby(caras, key=lambda f: f.product.idx)]


def _draw_facing(c, f, X, Y, sc):
    x, y, w, h = X(f.x), Y(f.y), f.w * sc, f.h * sc
    c.setFillColor(white)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.35)
    c.rect(x, y, w, h, stroke=1, fill=1)

    im = reader(f.product.image)
    pad = min(w, h) * 0.07
    aw, ah = w - 2 * pad, h - 2 * pad
    if im is not None and aw > 1 and ah > 1:
        try:
            c.drawImage(im, x + pad, y + pad, aw, ah,
                        mask="auto", preserveAspectRatio=True, anchor="c")
            return
        except Exception:
            pass
    # sin foto: trama diagonal
    c.saveState()
    c.setStrokeColor(LINE)
    c.setLineWidth(0.3)
    c.rect(x, y, w, h, stroke=0, fill=0)
    c.clipPath(_rect_path(c, x, y, w, h), stroke=0, fill=0)
    step = 4
    d = -h
    while d < w:
        c.line(x + d, y, x + d + h, y + h)
        d += step
    c.restoreState()


def _rect_path(c, x, y, w, h):
    p = c.beginPath()
    p.rect(x, y, w, h)
    return p


def _badge(c, cx, top, text):
    size = 6.2
    tw = c.stringWidth(text, FONT_B, size)
    w = max(9.5, tw + 6)
    h = 8.6
    x, y = cx - w / 2, top - h * 0.62
    c.setFillColor(NAVY)
    c.roundRect(x, y, w, h, 2.2, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont(FONT_B, size)
    c.drawCentredString(cx, y + 2.5, text)


# --------------------------------------------------------------------------- #
#  Hoja de detalle
# --------------------------------------------------------------------------- #
COLS = [
    ("N°", 9 * mm, "center"),
    ("Imagen", 15 * mm, "center"),
    ("C. Barra", 25 * mm, "left"),
    ("Material", 17 * mm, "left"),
    ("Descripción", 61 * mm, "left"),
    ("Ubicación", 21 * mm, "left"),
    ("Alto × Ancho × Prof.", 21 * mm, "center"),
    ("Caras", 9 * mm, "center"),
]
ROW_H = 15 * mm


def _facings_por_producto(mod: Module):
    conteo = {}
    for lv in mod.levels:
        for f in lv.facings:
            conteo[f.product.idx] = conteo.get(f.product.idx, 0) + 1
    return conteo


def _detalle_filas(modules: List[Module]):
    filas = []
    for mod in modules:
        conteo = _facings_por_producto(mod)
        for p in mod.products:
            nivel = next((lv for lv in mod.levels
                          if any(f.product.idx == p.idx for f in lv.facings)), None)
            filas.append({
                "n": p.number,
                "img": p.image,
                "barcode": p.barcode or "-",
                "material": p.material or "-",
                "desc": p.description,
                "ubic_1": ("M%d-%s" % (mod.index, p.location)) if len(modules) > 1 else p.location,
                "ubic_2": nivel.label if nivel else "",
                "medidas": p.medidas,
                "caras": conteo.get(p.idx, 1),
            })
    return filas


def _tabla_header(c, x, y, ancho):
    c.setFillColor(NAVY)
    c.rect(x, y - 7 * mm, ancho, 7 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    cx = x
    for titulo, w, align in COLS:
        c.setFont(FONT_B, _shrink(c, titulo, FONT_B, 7, 5, w - 4))
        if align == "center":
            c.drawCentredString(cx + w / 2, y - 4.6 * mm, titulo)
        else:
            c.drawString(cx + 2 * mm, y - 4.6 * mm, titulo)
        cx += w
    return y - 7 * mm


def _tabla_fila(c, fila, x, y, i):
    ancho = sum(w for _, w, _ in COLS)
    if i % 2:
        c.setFillColor(ZEBRA)
        c.rect(x, y - ROW_H, ancho, ROW_H, stroke=0, fill=1)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.3)
    c.line(x, y - ROW_H, x + ancho, y - ROW_H)

    cx = x
    mid = y - ROW_H / 2

    # numero
    w = COLS[0][1]
    _badge(c, cx + w / 2, mid + 4.3, str(fila["n"]))
    cx += w

    # imagen
    w = COLS[1][1]
    im = reader(fila["img"])
    if im is not None:
        pad = 1.5 * mm
        try:
            c.drawImage(im, cx + pad, y - ROW_H + pad,
                        w - 2 * pad, ROW_H - 2 * pad,
                        mask="auto", preserveAspectRatio=True, anchor="c")
        except Exception:
            pass
    cx += w

    c.setFillColor(INK)
    for key, size in (("barcode", 7.5), ("material", 7.5)):
        w = COLS[2][1] if key == "barcode" else COLS[3][1]
        c.setFont(FONT, size)
        c.drawString(cx + 2 * mm, mid - 2, _fit(c, fila[key], FONT, size, w - 3 * mm))
        cx += w

    # descripcion
    w = COLS[4][1]
    c.setFont(FONT_B, 7.5)
    lineas = _wrap(c, fila["desc"], FONT_B, 7.5, w - 4 * mm, max_lines=2)
    ty = mid + (3 if len(lineas) > 1 else 0) - 2
    for ln in lineas:
        c.drawString(cx + 2 * mm, ty, ln)
        ty -= 8
    cx += w

    # ubicacion
    w = COLS[5][1]
    c.setFillColor(NAVY)
    c.setFont(FONT_B, 8)
    c.drawString(cx + 2 * mm, mid + 1, fila["ubic_1"])
    c.setFillColor(MUTED)
    c.setFont(FONT, 6)
    c.drawString(cx + 2 * mm, mid - 7, _fit(c, fila["ubic_2"], FONT, 6, w - 3 * mm))
    cx += w

    # medidas
    w = COLS[6][1]
    c.setFillColor(INK)
    c.setFont(FONT, 7)
    c.drawCentredString(cx + w / 2, mid - 2, fila["medidas"])
    cx += w

    # caras
    w = COLS[7][1]
    c.setFont(FONT_B, 8)
    c.drawCentredString(cx + w / 2, mid - 2.5, str(fila["caras"]))


# --------------------------------------------------------------------------- #
#  Documento
# --------------------------------------------------------------------------- #
def generar_pdf(salida: str, categoria: str, modules: List[Module], cfg: Config,
                origen: str = ""):
    c = canvas.Canvas(salida, pagesize=A4)
    c.setTitle("Planograma - %s" % categoria)
    c.setAuthor("Generador de Planogramas")
    c.setSubject("Planograma %g x %g cm" % (cfg.module_w, cfg.module_h))

    hoy = datetime.date.today().strftime("%d/%m/%Y")
    filas = _detalle_filas(modules)
    ancho_tabla = sum(w for _, w, _ in COLS)
    alto_util = PAGE_H - 2 * MARGIN - 44
    por_pagina = max(1, int((alto_util - 7 * mm) // ROW_H))
    paginas_detalle = (len(filas) + por_pagina - 1) // por_pagina
    total_paginas = len(modules) + paginas_detalle
    pie = "%s%s" % (os.path.basename(origen) + "  -  " if origen else "", hoy)

    # ---- planos ----
    for mod in modules:
        n_prod = len(mod.products)
        sub = ("Módulo %d de %d   |   %g × %g cm   |   %d productos   |   %d caras"
               % (mod.index, len(modules), cfg.module_w, cfg.module_h,
                  n_prod, mod.total_facings))
        top = _header(c, categoria, sub, "Fecha: " + hoy)
        _draw_module(c, mod, cfg, categoria,
                     (MARGIN, MARGIN + 14, PAGE_W - 2 * MARGIN, top - MARGIN - 24))
        _footer(c, pie, mod.index, total_paginas)
        c.showPage()

    # ---- detalle ----
    for i in range(paginas_detalle):
        lote = filas[i * por_pagina:(i + 1) * por_pagina]
        sub = ("Detalle de productos   |   %d de %d   |   la ubicación corresponde al "
               "número del plano" % (i + 1, paginas_detalle))
        top = _header(c, categoria, sub, "Fecha: " + hoy)
        x = MARGIN + (PAGE_W - 2 * MARGIN - ancho_tabla) / 2
        y = _tabla_header(c, x, top - 8, ancho_tabla)
        for j, fila in enumerate(lote):
            _tabla_fila(c, fila, x, y, j)
            y -= ROW_H
        c.setStrokeColor(LINE)
        c.setLineWidth(0.3)
        c.rect(x, y, ancho_tabla, (top - 8 - 7 * mm) - y + 7 * mm, stroke=1, fill=0)
        _footer(c, pie, len(modules) + i + 1, total_paginas)
        c.showPage()

    c.save()
    return salida
