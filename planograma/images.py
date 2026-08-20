# -*- coding: utf-8 -*-
"""Preparacion de las imagenes de producto para el PDF.

Las fotos que vienen del Excel suelen traer margenes vacios (transparentes o
blancos). Si se dibujaran tal cual, el producto se veria mas chico que su
espacio real en el mueble, asi que se recortan antes de usarlas.
"""

from __future__ import annotations

import io
from typing import Optional

from PIL import Image, ImageChops

_MAX_SIDE = 480          # px; ~300 dpi al tamano en que se imprimen, y PDF liviano
_WHITE_TOL = 12          # tolerancia para detectar fondo blanco
_cache: dict = {}
_readers: dict = {}


def _trim(im: Image.Image) -> Image.Image:
    """Recorta el marco vacio (transparente o blanco) alrededor del producto."""
    bbox = None
    if im.mode in ("RGBA", "LA"):
        alpha = im.getchannel("A")
        if alpha.getextrema()[0] < 250:
            bbox = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox is None or bbox == (0, 0, im.width, im.height):
        rgb = im.convert("RGB")
        blanco = Image.new("RGB", im.size, (255, 255, 255))
        diff = ImageChops.difference(rgb, blanco).convert("L")
        alt = diff.point(lambda v: 255 if v > _WHITE_TOL else 0).getbbox()
        if alt:
            bbox = alt
    if bbox and (bbox[2] - bbox[0]) > 4 and (bbox[3] - bbox[1]) > 4:
        im = im.crop(bbox)
    return im


def prepare(data: Optional[bytes]) -> Optional[Image.Image]:
    """bytes -> imagen PIL recortada y reducida, lista para reportlab (o None)."""
    if not data:
        return None
    key = (len(data), hash(data))
    if key in _cache:
        return _cache[key]
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return None
    if im.mode not in ("RGBA", "RGB"):
        im = im.convert("RGBA" if "A" in im.getbands() or im.mode == "P" else "RGB")
    im = _trim(im)
    if max(im.size) > _MAX_SIDE:
        f = _MAX_SIDE / float(max(im.size))
        im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))),
                       Image.LANCZOS)
    _cache[key] = im
    return im


def reader(data: Optional[bytes]):
    """Igual que prepare(), pero devuelve un ImageReader reutilizable.

    Reutilizar la misma instancia hace que reportlab incruste cada foto una sola
    vez aunque se dibuje en varias caras y en la hoja de detalle.
    """
    if not data:
        return None
    key = (len(data), hash(data))
    if key not in _readers:
        im = prepare(data)
        if im is None:
            _readers[key] = None
        else:
            from reportlab.lib.utils import ImageReader
            _readers[key] = ImageReader(im)
    return _readers[key]
