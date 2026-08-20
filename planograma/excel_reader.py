# -*- coding: utf-8 -*-
"""Lectura del Excel de productos, incluyendo las imagenes que estan DENTRO de la celda.

Excel guarda las "imagenes en celda" (Insertar > Imagen > Colocar en celda) como
*rich values*: la celda queda con t="e" / #VALUE! y un atributo vm="N" que apunta a
xl/metadata.xml -> xl/richData/rdrichvalue.xml -> xl/richData/richValueRel.xml ->
xl/media/imageN.png.  openpyxl todavia no lee ese formato, asi que se parsea a mano.

Tambien se soporta el formato clasico (imagenes flotantes ancladas a una celda,
xl/drawings/drawingN.xml) para archivos hechos con versiones viejas de Excel.
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_RD = "{http://schemas.microsoft.com/office/spreadsheetml/2017/richdata}"
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_XDR = "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

COLGADO = "Colgado"
TABLILLA = "Tablilla"


class ExcelError(Exception):
    pass


# --------------------------------------------------------------------------- #
#  Producto
# --------------------------------------------------------------------------- #
@dataclass
class Product:
    idx: int                       # posicion original en el Excel (clave unica)
    excel_row: int
    barcode: str
    material: str
    description: str
    display_type: str              # "Colgado" o "Tablilla"
    alto: float
    ancho: float
    largo: float
    image: Optional[bytes] = None
    facings_fixed: Optional[int] = None
    number: int = 0                # numero de ubicacion asignado por el layout
    location: str = ""             # p.ej. "G2" (gancho fila 2) o "T1" (tablilla 1)

    @property
    def is_shelf(self) -> bool:
        return self.display_type == TABLILLA

    @property
    def face_w(self) -> float:
        """Ancho de la cara visible en el mueble."""
        return self.ancho

    @property
    def face_h(self) -> float:
        """Alto de la cara visible.

        Colgado : el empaque cuelga de un gancho, se ve el largo en vertical.
        Tablilla: el producto se para sobre la tablilla, se ve su alto real.
        """
        return self.largo if not self.is_shelf else self.alto

    @property
    def depth(self) -> float:
        """Fondo que ocupa dentro del mueble."""
        return self.alto if not self.is_shelf else self.largo

    @property
    def medidas(self) -> str:
        return "%s × %s × %s" % (_num(self.alto), _num(self.ancho), _num(self.largo))


def _num(v: float) -> str:
    return ("%g" % round(float(v), 2)) if v is not None else ""


# --------------------------------------------------------------------------- #
#  Utilidades
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    """minusculas, sin acentos, sin puntuacion ni espacios extra."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", " ").replace("/", " ").replace("-", " ")
    s = re.sub(r"[()\[\]]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _col_letters(ref: str) -> str:
    m = re.match(r"([A-Z]+)", ref or "")
    return m.group(1) if m else ""


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    if not s or s in ("-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _clean_code(v) -> str:
    """Los codigos vienen como numero; evita que salgan como 7.70207e+12."""
    if v is None:
        return ""
    s = str(v).strip()
    if re.fullmatch(r"-?\d+\.0+", s):
        s = s.split(".")[0]
    elif re.fullmatch(r"\d+(\.\d+)?[eE]\+?\d+", s):
        s = "%.0f" % float(s)
    return s


# --------------------------------------------------------------------------- #
#  Sinonimos de encabezado
# --------------------------------------------------------------------------- #
HEADERS = {
    "image": ["imagenes", "imagen", "foto", "fotos", "img", "picture"],
    "barcode": ["c barra", "codigo de barra", "codigo de barras", "cod barra",
                "codigo barra", "barra", "ean", "upc", "codigo ean"],
    "material": ["material", "codigo", "cod", "sku", "item", "articulo",
                 "codigo material", "cod material"],
    "description": ["descripcion", "descripcion producto", "producto",
                    "nombre", "detalle"],
    "display_type": ["tipo de exhibicion", "tipo exhibicion", "exhibicion",
                     "tipo", "display"],
    "alto": ["alto cm", "alto", "altura cm", "altura", "alto centimetros"],
    "ancho": ["ancho cm", "ancho", "anchura cm", "anchura"],
    "largo": ["profundo largo cm", "profundo largo", "profundidad cm",
              "profundo cm", "profundo", "largo cm", "largo", "fondo cm",
              "fondo", "profundidad"],
    "facings": ["caras", "cara", "facings", "facing", "frentes", "frente"],
}


def _match_header(text: str) -> Optional[str]:
    n = _norm(text)
    if not n:
        return None
    for field_name, options in HEADERS.items():
        if n in options:
            return field_name
    for field_name, options in HEADERS.items():
        for opt in options:
            if n.startswith(opt) or opt.startswith(n):
                return field_name
    return None


# --------------------------------------------------------------------------- #
#  Libro
# --------------------------------------------------------------------------- #
class Workbook:
    def __init__(self, path: str):
        self.path = path
        try:
            self.zf = zipfile.ZipFile(path)
        except zipfile.BadZipFile:
            raise ExcelError(
                "El archivo no es un .xlsx valido. Si es .xls o .csv, abrelo en "
                "Excel y guardalo como 'Libro de Excel (*.xlsx)'."
            )
        self._names = set(self.zf.namelist())
        self._shared = self._read_shared_strings()
        self.sheets = self._read_sheet_index()      # [(nombre, ruta interna)]
        if not self.sheets:
            raise ExcelError("El libro no tiene hojas legibles.")
        self._rich_images = None                    # cache: indice vm -> bytes

    # ---------------- infraestructura ---------------- #
    def _read(self, name: str) -> Optional[bytes]:
        return self.zf.read(name) if name in self._names else None

    def _read_shared_strings(self):
        data = self._read("xl/sharedStrings.xml")
        if not data:
            return []
        out = []
        for si in ET.fromstring(data).findall(NS_MAIN + "si"):
            out.append("".join(t.text or "" for t in si.iter(NS_MAIN + "t")))
        return out

    def _read_sheet_index(self):
        wb = self._read("xl/workbook.xml")
        rels = self._read("xl/_rels/workbook.xml.rels")
        if not wb or not rels:
            return []
        target = {}
        for rel in ET.fromstring(rels).findall(NS_REL + "Relationship"):
            t = rel.get("Target", "")
            t = t[1:] if t.startswith("/") else "xl/" + t.replace("../", "")
            target[rel.get("Id")] = t
        sheets = []
        for sh in ET.fromstring(wb).iter(NS_MAIN + "sheet"):
            if sh.get("state") in ("hidden", "veryHidden"):
                continue
            path = target.get(sh.get(NS_R + "id"))
            if path and path in self._names:
                sheets.append((sh.get("name"), path))
        return sheets

    @property
    def sheet_names(self):
        return [n for n, _ in self.sheets]

    # ---------------- imagenes en celda (rich values) ---------------- #
    def _load_rich_images(self):
        """Devuelve {indice_vm (1-based) -> bytes de la imagen}."""
        if self._rich_images is not None:
            return self._rich_images
        self._rich_images = {}
        meta = self._read("xl/metadata.xml")
        rv = self._read("xl/richData/rdrichvalue.xml")
        rel = self._read("xl/richData/richValueRel.xml")
        rel_rels = self._read("xl/richData/_rels/richValueRel.xml.rels")
        if not (meta and rv and rel and rel_rels):
            return self._rich_images

        # rId -> archivo en xl/media
        media = {}
        for r in ET.fromstring(rel_rels).findall(NS_REL + "Relationship"):
            t = r.get("Target", "").replace("../", "")
            media[r.get("Id")] = t if t.startswith("xl/") else "xl/" + t

        # indice de richValueRel -> rId
        rel_ids = [e.get(NS_R + "id") for e in ET.fromstring(rel)]

        # indice de rich value -> indice de richValueRel (1er <v> de la estructura _localImage)
        rv_to_rel = []
        for entry in ET.fromstring(rv).findall(NS_RD + "rv"):
            vals = [v.text for v in entry.findall(NS_RD + "v")]
            rv_to_rel.append(int(vals[0]) if vals and vals[0] is not None else None)

        # valueMetadata (1-based, lo que apunta vm=) -> futureMetadata -> rich value
        mroot = ET.fromstring(meta)
        rich_type = None
        for i, mt in enumerate(mroot.iter(NS_MAIN + "metadataType"), start=1):
            if mt.get("name") == "XLRICHVALUE":
                rich_type = i
        future = []
        for fm in mroot.iter(NS_MAIN + "futureMetadata"):
            if fm.get("name") != "XLRICHVALUE":
                continue
            for bk in fm.findall(NS_MAIN + "bk"):
                rvb = next(iter(bk.iter(NS_RD + "rvb")), None)
                future.append(int(rvb.get("i")) if rvb is not None else None)

        vm_index = 0
        for vmeta in mroot.iter(NS_MAIN + "valueMetadata"):
            for bk in vmeta.findall(NS_MAIN + "bk"):
                vm_index += 1
                rc = bk.find(NS_MAIN + "rc")
                if rc is None:
                    continue
                if rich_type is not None and rc.get("t") not in (None, str(rich_type)):
                    continue
                fi = int(rc.get("v"))
                if fi >= len(future) or future[fi] is None:
                    continue
                ri = future[fi]
                if ri >= len(rv_to_rel) or rv_to_rel[ri] is None:
                    continue
                rel_i = rv_to_rel[ri]
                if rel_i >= len(rel_ids):
                    continue
                path = media.get(rel_ids[rel_i])
                if path and path in self._names:
                    self._rich_images[vm_index] = self.zf.read(path)
        return self._rich_images

    # ---------------- imagenes flotantes (formato clasico) ---------------- #
    def _load_anchored_images(self, sheet_path: str):
        """Devuelve {(fila, columna) 0-based -> bytes} para imagenes ancladas."""
        out = {}
        base = sheet_path.rsplit("/", 1)[-1]
        rels_path = sheet_path.rsplit("/", 1)[0] + "/_rels/" + base + ".rels"
        rels = self._read(rels_path)
        if not rels:
            return out
        drawings = [r.get("Target", "").replace("../", "")
                    for r in ET.fromstring(rels).findall(NS_REL + "Relationship")
                    if r.get("Type", "").endswith("/drawing")]
        for d in drawings:
            dpath = d if d.startswith("xl/") else "xl/" + d
            ddata = self._read(dpath)
            if not ddata:
                continue
            dbase = dpath.rsplit("/", 1)[-1]
            drels = self._read(dpath.rsplit("/", 1)[0] + "/_rels/" + dbase + ".rels")
            embed = {}
            if drels:
                for r in ET.fromstring(drels).findall(NS_REL + "Relationship"):
                    t = r.get("Target", "").replace("../", "")
                    embed[r.get("Id")] = t if t.startswith("xl/") else "xl/" + t
            for anchor in ET.fromstring(ddata):
                frm = anchor.find(NS_XDR + "from")
                blip = next(iter(anchor.iter(NS_A + "blip")), None)
                if frm is None or blip is None:
                    continue
                row = int(frm.find(NS_XDR + "row").text)
                col = int(frm.find(NS_XDR + "col").text)
                path = embed.get(blip.get(NS_R + "embed"))
                if path and path in self._names:
                    out[(row, col)] = self.zf.read(path)
        return out

    # ---------------- hoja -> productos ---------------- #
    def read_products(self, sheet_name: Optional[str] = None):
        """Devuelve (productos, avisos)."""
        path = dict(self.sheets).get(sheet_name) if sheet_name else self.sheets[0][1]
        if path is None:
            raise ExcelError("No existe la hoja '%s'." % sheet_name)

        rich = self._load_rich_images()
        anchored = self._load_anchored_images(path)

        root = ET.fromstring(self.zf.read(path))
        data = root.find(NS_MAIN + "sheetData")
        rows = []
        for row in (data.findall(NS_MAIN + "row") if data is not None else []):
            r_num = int(row.get("r"))
            cells = {}
            for c in row.findall(NS_MAIN + "c"):
                letters = _col_letters(c.get("r", ""))
                if not letters:
                    continue
                cells[letters] = self._cell_value(c, rich)
            rows.append((r_num, cells))

        header_row, mapping = self._find_header(rows)
        if not mapping:
            raise ExcelError(
                "No se encontraron los encabezados esperados. La hoja debe tener "
                "columnas como: imagenes, C. Barra, Material, Descripcion, "
                "Tipo de Exhibicion, Alto (cm), Ancho (cm), Profundo/Largo (cm)."
            )
        faltan = [f for f in ("description", "display_type", "ancho", "alto", "largo")
                  if f not in mapping]
        if faltan:
            raise ExcelError("Faltan columnas obligatorias: " + ", ".join(faltan))

        img_col = mapping.get("image")
        products, warnings = [], []
        for r_num, cells in rows:
            if r_num <= header_row:
                continue
            get = lambda f: cells.get(mapping[f]) if f in mapping else None

            desc = (get("description") or "").strip()
            alto = _to_float(get("alto"))
            ancho = _to_float(get("ancho"))
            largo = _to_float(get("largo"))
            if not desc and alto is None and ancho is None:
                continue                                   # fila vacia
            if not desc:
                warnings.append("Fila %d: sin descripcion, se omite." % r_num)
                continue
            if not ancho or ancho <= 0:
                warnings.append("Fila %d (%s): 'Ancho' invalido, se omite." % (r_num, desc))
                continue
            if alto is None or alto <= 0:
                alto = 1.0
            if largo is None or largo <= 0:
                largo = alto

            tipo_raw = _norm(get("display_type"))
            if tipo_raw.startswith("colg") or tipo_raw in ("gancho", "peg", "hook"):
                tipo = COLGADO
            elif tipo_raw.startswith("tabl") or tipo_raw in ("estante", "repisa", "shelf"):
                tipo = TABLILLA
            else:
                tipo = TABLILLA
                warnings.append(
                    "Fila %d (%s): tipo de exhibicion '%s' no reconocido, se usa Tablilla."
                    % (r_num, desc, get("display_type"))
                )

            img = None
            if img_col:
                v = cells.get(img_col)
                if isinstance(v, bytes):
                    img = v
            if img is None:
                col_i = _col_index(img_col) if img_col else 0
                img = anchored.get((r_num - 1, col_i))
            if img is None:
                warnings.append("Fila %d (%s): sin imagen." % (r_num, desc))

            caras = _to_float(get("facings"))
            products.append(Product(
                idx=len(products),
                excel_row=r_num,
                barcode=_clean_code(get("barcode")),
                material=_clean_code(get("material")),
                description=desc,
                display_type=tipo,
                alto=alto, ancho=ancho, largo=largo,
                image=img,
                facings_fixed=int(caras) if caras and caras >= 1 else None,
            ))

        if not products:
            raise ExcelError("No se encontro ningun producto debajo de los encabezados.")
        return products, warnings

    def _cell_value(self, c, rich):
        vm = c.get("vm")
        if vm:
            img = rich.get(int(vm))
            if img is not None:
                return img
        t = c.get("t")
        if t == "inlineStr":
            is_el = c.find(NS_MAIN + "is")
            return "".join(x.text or "" for x in is_el.iter(NS_MAIN + "t")) if is_el is not None else None
        v = c.find(NS_MAIN + "v")
        if v is None or v.text is None:
            return None
        if t == "s":
            i = int(v.text)
            return self._shared[i] if i < len(self._shared) else None
        if t == "e":
            return None
        return v.text

    @staticmethod
    def _find_header(rows):
        """Busca la fila de encabezados con mas coincidencias (primeras 20 filas)."""
        best, best_map, best_score = 0, {}, 0
        for r_num, cells in rows[:20]:
            mapping, score = {}, 0
            for letters, val in cells.items():
                if isinstance(val, bytes):
                    continue
                f = _match_header(val)
                if f and f not in mapping:
                    mapping[f] = letters
                    score += 1
            if score > best_score:
                best, best_map, best_score = r_num, mapping, score
        return (best, best_map) if best_score >= 3 else (0, {})
