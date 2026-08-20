# -*- coding: utf-8 -*-
"""Parametros del modulo de exhibicion. Todas las medidas estan en centimetros."""

from dataclasses import dataclass


@dataclass
class Config:
    # --- Dimensiones del modulo ---
    module_w: float = 122.0          # ancho total del mueble
    module_h: float = 180.0          # alto total del mueble

    # --- Estructura ---
    side_margin: float = 2.0         # aire a cada lado dentro del mueble
    header_h: float = 14.0           # franja del rotulo de categoria (arriba)
    base_h: float = 12.0             # zocalo / base sobre la que apoya la 1a tablilla
    shelf_t: float = 2.0             # espesor de cada tablilla
    shelf_clearance: float = 4.0     # aire libre sobre el producto en tablilla
    peg_gap: float = 4.0             # separacion minima entre filas de ganchos
    peg_zone_gap: float = 6.0        # separacion entre zona colgada y zona de tablillas

    # --- Acomodo horizontal ---
    gap_x: float = 1.2               # separacion entre productos distintos
    gap_facing: float = 0.3          # separacion entre caras del mismo producto
    max_gap_x: float = 10.0          # tope de separacion al justificar una fila

    # --- Caras (facings) ---
    max_facings: int = 4             # tope de caras que el auto-relleno puede asignar
    auto_facings: bool = True        # False = 1 cara por producto (o la columna "Caras")

    @property
    def usable_w(self) -> float:
        return self.module_w - 2 * self.side_margin
