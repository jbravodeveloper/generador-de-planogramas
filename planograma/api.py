# -*- coding: utf-8 -*-
"""Traduce el resultado del motor de acomodo a JSON, para que el front lo dibuje."""

from __future__ import annotations

import itertools
from typing import List

from .config import Config
from .layout import Module


def _bloques(level):
    caras = sorted(level.facings, key=lambda f: f.x)
    return [list(g) for _, g in itertools.groupby(caras, key=lambda f: f.product.idx)]


def _r(v: float) -> float:
    return round(float(v), 2)


def modulo_a_dict(mod: Module) -> dict:
    niveles = []
    for lv in mod.levels:
        bloques = []
        for grupo in _bloques(lv):
            p = grupo[0].product
            bloques.append({
                "idx": p.idx,
                "numero": p.number,
                "caras": len(grupo),
                "x": _r(grupo[0].x),
                "ancho": _r(grupo[-1].x + grupo[-1].w - grupo[0].x),
                "alto": _r(max(f.y + f.h for f in grupo) - min(f.y for f in grupo)),
                "y": _r(min(f.y for f in grupo)),
                "facings": [{"x": _r(f.x), "y": _r(f.y), "w": _r(f.w), "h": _r(f.h)}
                            for f in grupo],
            })
        niveles.append({
            "tipo": lv.kind,
            "codigo": lv.code,
            "etiqueta": lv.label,
            "alto": _r(lv.height),
            "base_y": _r(lv.base_y),
            "top_y": _r(lv.top_y),
            "board_y": _r(lv.board_y),
            "tiene_tabla": lv.has_board,
            "altura_ref": _r(lv.top_y if lv.kind == "gancho" else lv.base_y),
            "bloques": bloques,
        })
    return {
        "indice": mod.index,
        "shelf_top": _r(mod.shelf_top),
        "peg_bottom": _r(mod.peg_bottom),
        "productos": len(mod.products),
        "caras": mod.total_facings,
        "ocupacion": round(mod.fill_pct, 1),
        "niveles": niveles,
    }


def resultado_a_dict(modules: List[Module], cfg: Config, avisos, hoja, categoria) -> dict:
    productos = {}
    for mod in modules:
        conteo = {}
        for lv in mod.levels:
            for f in lv.facings:
                conteo[f.product.idx] = conteo.get(f.product.idx, 0) + 1
        for p in mod.products:
            nivel = next((lv for lv in mod.levels
                          if any(f.product.idx == p.idx for f in lv.facings)), None)
            productos[p.idx] = {
                "idx": p.idx,
                "numero": p.number,
                "modulo": mod.index,
                "barcode": p.barcode,
                "material": p.material,
                "descripcion": p.description,
                "exhibicion": p.display_type,
                "alto": p.alto, "ancho": p.ancho, "largo": p.largo,
                "medidas": p.medidas,
                "ubicacion": p.location,
                "nivel": nivel.label if nivel else "",
                "caras": conteo.get(p.idx, 1),
                "tiene_foto": bool(p.image),
            }
    return {
        "hoja": hoja,
        "categoria": categoria,
        "mueble": {
            "ancho": cfg.module_w, "alto": cfg.module_h,
            "cenefa": cfg.header_h, "base": cfg.base_h,
            "espesor": cfg.shelf_t, "margen": cfg.side_margin,
        },
        "modulos": [modulo_a_dict(m) for m in modules],
        "productos": sorted(productos.values(), key=lambda d: d["numero"]),
        "avisos": list(avisos),
    }
