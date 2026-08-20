# -*- coding: utf-8 -*-
"""Servidor local del front web del Generador de Planogramas.

Levanta un sitio en http://localhost:8765 desde donde se carga el Excel, se ve el
planograma en pantalla y se descarga el PDF. Todo corre en esta computadora: el
archivo nunca sale de aca.

    py servidor.py            (abre el navegador solo)
    py servidor.py --puerto 9000 --sin-navegador
"""

from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import re
import secrets
import socket
import sys
import tempfile
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
sys.path.insert(0, BASE_DIR)

from planograma.api import resultado_a_dict
from planograma.config import Config
from planograma.excel_reader import Workbook, ExcelError
from planograma.images import prepare
from planograma.layout import build_modules
from planograma.pdf_render import generar_pdf

MAX_SUBIDA = 60 * 1024 * 1024          # 60 MB
SESIONES = {}                          # token -> {"nombre", "ruta", "wb", "productos"}
CANDADO = threading.Lock()
TMP = tempfile.mkdtemp(prefix="planogramas_")


class ErrorPeticion(Exception):
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.codigo = codigo


# --------------------------------------------------------------------------- #
#  Logica
# --------------------------------------------------------------------------- #
def _sesion(token):
    ses = SESIONES.get(token or "")
    if not ses:
        raise ErrorPeticion("La sesion expiro. Volve a cargar el Excel.", 404)
    return ses


def _productos(ses, hoja):
    """Lee (y cachea) los productos de una hoja."""
    if hoja not in ses["productos"]:
        ses["productos"][hoja] = ses["wb"].read_products(hoja)
    return ses["productos"][hoja]


def _config(datos) -> Config:
    def num(clave, defecto):
        try:
            return float(str(datos.get(clave, defecto)).replace(",", "."))
        except (TypeError, ValueError):
            return float(defecto)

    ancho, alto = num("ancho", 122), num("alto", 180)
    if not (20 <= ancho <= 600) or not (40 <= alto <= 400):
        raise ErrorPeticion("El ancho debe estar entre 20 y 600 cm, y el alto entre 40 y 400.")
    return Config(
        module_w=ancho,
        module_h=alto,
        max_facings=max(1, min(12, int(num("caras", 4)))),
        auto_facings=bool(datos.get("auto", True)),
    )


def _armar(datos):
    ses = _sesion(datos.get("token"))
    hoja = datos.get("hoja") or ses["wb"].sheet_names[0]
    if hoja not in ses["wb"].sheet_names:
        raise ErrorPeticion("No existe la hoja '%s'." % hoja)
    cfg = _config(datos)
    with CANDADO:
        productos, avisos_excel = _productos(ses, hoja)
        modules, avisos_layout = build_modules(productos, cfg)
        salida = resultado_a_dict(modules, cfg, avisos_excel + avisos_layout,
                                  hoja, (datos.get("categoria") or hoja).strip())
    return ses, cfg, modules, salida


def _nombre_archivo(categoria):
    limpio = re.sub(r'[\\/:*?"<>|]+', "-", categoria).strip(" .") or "Planograma"
    return "Planograma - %s.pdf" % limpio


# --------------------------------------------------------------------------- #
#  Rutas
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    server_version = "Planogramas"
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *args):
        pass                                  # sin ruido en la consola

    # ---------- helpers ---------- #
    def _enviar(self, cuerpo, tipo="application/json; charset=utf-8", codigo=200,
                extra=None):
        if isinstance(cuerpo, str):
            cuerpo = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, datos, codigo=200):
        self._enviar(json.dumps(datos, ensure_ascii=False), codigo=codigo)

    def _error(self, mensaje, codigo=400):
        self._json({"error": str(mensaje)}, codigo)

    def _cuerpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_SUBIDA:
            raise ErrorPeticion("El archivo supera los 60 MB.", 413)
        return self.rfile.read(n) if n else b""

    def _cuerpo_json(self):
        try:
            return json.loads(self._cuerpo() or b"{}")
        except ValueError:
            raise ErrorPeticion("Peticion mal formada.")

    # ---------- GET ---------- #
    def do_GET(self):
        ruta = urlparse(self.path)
        try:
            if ruta.path in ("/", "/index.html"):
                return self._estatico("index.html")
            if ruta.path == "/api/img":
                return self._imagen(parse_qs(ruta.query))
            if ruta.path == "/api/salud":
                return self._json({"ok": True})
            nombre = ruta.path.lstrip("/")
            if nombre and "/" not in nombre and ".." not in nombre:
                return self._estatico(nombre)
            self._error("No encontrado", 404)
        except ErrorPeticion as e:
            self._error(e, e.codigo)
        except Exception:
            traceback.print_exc()
            self._error("Error interno", 500)

    def _estatico(self, nombre):
        ruta = os.path.join(WEB_DIR, nombre)
        if not os.path.isfile(ruta):
            return self._error("No encontrado", 404)
        tipo = mimetypes.guess_type(ruta)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo.endswith("javascript"):
            tipo += "; charset=utf-8"
        with open(ruta, "rb") as f:
            self._enviar(f.read(), tipo)

    def _imagen(self, q):
        ses = _sesion((q.get("t") or [""])[0])
        hoja = (q.get("h") or [""])[0]
        try:
            idx = int((q.get("i") or ["-1"])[0])
        except ValueError:
            raise ErrorPeticion("Indice invalido.")
        productos, _ = _productos(ses, hoja)
        if not (0 <= idx < len(productos)):
            raise ErrorPeticion("Producto inexistente.", 404)
        im = prepare(productos[idx].image)
        if im is None:
            raise ErrorPeticion("Sin imagen.", 404)
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        self._enviar(buf.getvalue(), "image/png",
                     extra={"Cache-Control": "private, max-age=600"})

    # ---------- POST ---------- #
    def do_POST(self):
        ruta = urlparse(self.path).path
        try:
            if ruta == "/api/cargar":
                return self._cargar()
            if ruta == "/api/generar":
                return self._generar()
            if ruta == "/api/pdf":
                return self._pdf()
            self._error("No encontrado", 404)
        except (ErrorPeticion, ExcelError, ValueError) as e:
            self._error(e, getattr(e, "codigo", 400))
        except Exception:
            traceback.print_exc()
            self._error("Error interno del generador", 500)

    def _cargar(self):
        datos = self._cuerpo()
        if not datos:
            raise ErrorPeticion("No llego ningun archivo.")
        nombre = self.headers.get("X-Nombre") or "libro.xlsx"
        try:
            nombre = os.path.basename(bytes(nombre, "latin-1").decode("utf-8"))
        except (UnicodeDecodeError, UnicodeEncodeError):
            nombre = os.path.basename(nombre)

        token = secrets.token_urlsafe(12)
        ruta = os.path.join(TMP, token + ".xlsx")
        with open(ruta, "wb") as f:
            f.write(datos)
        wb = Workbook(ruta)                      # lanza ExcelError si no sirve
        SESIONES[token] = {"nombre": nombre, "ruta": ruta, "wb": wb, "productos": {}}

        hoja = wb.sheet_names[0]
        self._json({
            "token": token,
            "nombre": nombre,
            "hojas": wb.sheet_names,
            "hoja": hoja,
            "categoria": categoria_sugerida(nombre, hoja),
        })

    def _generar(self):
        datos = self._cuerpo_json()
        _, _, _, salida = _armar(datos)
        salida["token"] = datos.get("token")
        self._json(salida)

    def _pdf(self):
        datos = self._cuerpo_json()
        ses, cfg, modules, salida = _armar(datos)
        ruta = os.path.join(TMP, secrets.token_urlsafe(8) + ".pdf")
        generar_pdf(ruta, salida["categoria"], modules, cfg, origen=ses["nombre"])
        with open(ruta, "rb") as f:
            contenido = f.read()
        os.remove(ruta)
        nombre = _nombre_archivo(salida["categoria"])
        self._enviar(contenido, "application/pdf", extra={
            "Content-Disposition": "attachment; filename*=UTF-8''%s"
                                   % _porcentaje(nombre),
        })


def _porcentaje(texto):
    from urllib.parse import quote
    return quote(texto, safe="")


GENERICAS = {"hoja1", "hoja 1", "sheet1", "sheet 1", "hoja", "sheet", "datos", "hoja2"}


def categoria_sugerida(nombre_archivo, hoja):
    if hoja and hoja.strip().lower() not in GENERICAS:
        return hoja.strip()
    return os.path.splitext(nombre_archivo)[0].replace("_", " ").strip()


# --------------------------------------------------------------------------- #
def puerto_libre(preferido):
    for p in [preferido] + [preferido + i for i in range(1, 20)]:
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise SystemExit("No hay puertos libres entre %d y %d." % (preferido, preferido + 19))


def main():
    ap = argparse.ArgumentParser(description="Front web del Generador de Planogramas.")
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--sin-navegador", action="store_true")
    args = ap.parse_args()

    puerto = puerto_libre(args.puerto)
    url = "http://localhost:%d/" % puerto
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Handler)

    print("")
    print("  Generador de Planogramas")
    print("  " + "-" * 46)
    print("  Abierto en:  %s" % url)
    print("  Para cerrar: Ctrl+C  (o cerra esta ventana)")
    print("")
    if not args.sin_navegador:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("  Cerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
