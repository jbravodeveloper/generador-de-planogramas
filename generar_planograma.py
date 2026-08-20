# -*- coding: utf-8 -*-
"""Generador de Planogramas — punto de entrada (ventana o linea de comandos).

Uso rapido:
    doble clic en  "Generar Planograma.bat"

Linea de comandos:
    py generar_planograma.py Hogar.xlsx
    py generar_planograma.py Hogar.xlsx --categoria "Hogar" --caras 3 --no-gui
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from planograma.config import Config
from planograma.excel_reader import Workbook, ExcelError
from planograma.layout import build_modules
from planograma.pdf_render import generar_pdf

GENERICAS = {"hoja1", "hoja 1", "sheet1", "sheet 1", "hoja", "sheet", "datos", "hoja2"}


def categoria_sugerida(ruta: str, hoja: str) -> str:
    if hoja and hoja.strip().lower() not in GENERICAS:
        return hoja.strip()
    return os.path.splitext(os.path.basename(ruta))[0].replace("_", " ").strip()


def nombre_salida(ruta_excel: str, categoria: str) -> str:
    limpio = re.sub(r'[\\/:*?"<>|]', "-", categoria).strip() or "Planograma"
    return os.path.join(os.path.dirname(os.path.abspath(ruta_excel)),
                        "Planograma - %s.pdf" % limpio)


def generar(ruta_excel, categoria=None, hoja=None, cfg=None, salida=None, log=print):
    cfg = cfg or Config()
    wb = Workbook(ruta_excel)
    hoja = hoja or wb.sheet_names[0]
    productos, avisos = wb.read_products(hoja)
    log("Hoja '%s': %d productos leidos." % (hoja, len(productos)))
    sin_foto = sum(1 for p in productos if not p.image)
    if sin_foto:
        log("Aviso: %d producto(s) sin imagen." % sin_foto)

    modules, avisos_layout = build_modules(productos, cfg)
    for a in avisos + avisos_layout:
        log("  - " + a)

    categoria = (categoria or categoria_sugerida(ruta_excel, hoja)).strip()
    salida = salida or nombre_salida(ruta_excel, categoria)
    generar_pdf(salida, categoria, modules, cfg, origen=ruta_excel)

    for m in modules:
        log("Modulo %d: %d ganchos + %d tablillas, %d productos, %d caras (%.0f%% de ocupacion)."
            % (m.index, len(m.peg_levels), len(m.shelf_levels),
               len(m.products), m.total_facings, m.fill_pct))
    log("PDF generado: %s" % salida)
    return salida, modules


# --------------------------------------------------------------------------- #
#  Ventana
# --------------------------------------------------------------------------- #
def abrir_ventana(ruta_inicial=None):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("Generador de Planogramas")
    root.geometry("760x560")
    root.minsize(700, 520)

    v_archivo = tk.StringVar()
    v_hoja = tk.StringVar()
    v_categoria = tk.StringVar()
    v_ancho = tk.StringVar(value="122")
    v_alto = tk.StringVar(value="180")
    v_caras = tk.StringVar(value="4")
    v_auto = tk.BooleanVar(value=True)
    v_abrir = tk.BooleanVar(value=True)
    libro = {"wb": None}

    cont = ttk.Frame(root, padding=14)
    cont.pack(fill="both", expand=True)

    ttk.Label(cont, text="Generador de Planogramas",
              font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")
    ttk.Label(cont, text="Carga el Excel de productos y descarga el planograma en PDF.",
              foreground="#555").grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 12))

    def log(msg):
        salida.configure(state="normal")
        salida.insert("end", str(msg) + "\n")
        salida.see("end")
        salida.configure(state="disabled")
        root.update_idletasks()

    def cargar(ruta):
        try:
            wb = Workbook(ruta)
        except (ExcelError, OSError) as e:
            messagebox.showerror("No se pudo abrir", str(e))
            return
        libro["wb"] = wb
        v_archivo.set(ruta)
        combo_hoja["values"] = wb.sheet_names
        v_hoja.set(wb.sheet_names[0])
        v_categoria.set(categoria_sugerida(ruta, v_hoja.get()))
        log("Archivo cargado: %s  (%d hoja/s)" % (os.path.basename(ruta), len(wb.sheet_names)))

    def examinar():
        ruta = filedialog.askopenfilename(
            title="Selecciona el Excel de productos",
            filetypes=[("Excel", "*.xlsx *.xlsm"), ("Todos", "*.*")])
        if ruta:
            cargar(ruta)

    def cambio_hoja(*_):
        if v_archivo.get():
            v_categoria.set(categoria_sugerida(v_archivo.get(), v_hoja.get()))

    ttk.Label(cont, text="Archivo Excel").grid(row=2, column=0, sticky="w")
    ttk.Entry(cont, textvariable=v_archivo).grid(row=2, column=1, columnspan=2, sticky="ew", padx=6)
    ttk.Button(cont, text="Examinar...", command=examinar).grid(row=2, column=3, sticky="ew")

    ttk.Label(cont, text="Hoja").grid(row=3, column=0, sticky="w", pady=6)
    combo_hoja = ttk.Combobox(cont, textvariable=v_hoja, state="readonly", values=[])
    combo_hoja.grid(row=3, column=1, sticky="ew", padx=6, pady=6)
    combo_hoja.bind("<<ComboboxSelected>>", cambio_hoja)

    ttk.Label(cont, text="Categoria (titulo)").grid(row=3, column=2, sticky="e", padx=(10, 0))
    ttk.Entry(cont, textvariable=v_categoria).grid(row=3, column=3, sticky="ew", pady=6)

    med = ttk.LabelFrame(cont, text="Medidas del mueble", padding=8)
    med.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 4))
    ttk.Label(med, text="Ancho (cm)").grid(row=0, column=0, sticky="w")
    ttk.Entry(med, textvariable=v_ancho, width=8).grid(row=0, column=1, padx=(6, 18))
    ttk.Label(med, text="Alto (cm)").grid(row=0, column=2, sticky="w")
    ttk.Entry(med, textvariable=v_alto, width=8).grid(row=0, column=3, padx=(6, 18))
    ttk.Label(med, text="Maximo de caras").grid(row=0, column=4, sticky="w")
    ttk.Entry(med, textvariable=v_caras, width=8).grid(row=0, column=5, padx=6)

    ttk.Checkbutton(cont, text="Rellenar el mueble agregando caras automaticamente",
                    variable=v_auto).grid(row=5, column=0, columnspan=3, sticky="w")
    ttk.Checkbutton(cont, text="Abrir el PDF al terminar",
                    variable=v_abrir).grid(row=6, column=0, columnspan=3, sticky="w")

    def ejecutar():
        if not v_archivo.get():
            messagebox.showwarning("Falta el archivo", "Selecciona primero el Excel.")
            return
        try:
            cfg = Config(
                module_w=float(v_ancho.get().replace(",", ".")),
                module_h=float(v_alto.get().replace(",", ".")),
                max_facings=max(1, int(float(v_caras.get()))),
                auto_facings=bool(v_auto.get()),
            )
        except ValueError:
            messagebox.showerror("Medidas invalidas", "Ancho, alto y caras deben ser numeros.")
            return
        btn.configure(state="disabled")
        try:
            log("")
            ruta, _ = generar(v_archivo.get(), v_categoria.get(), v_hoja.get(), cfg, log=log)
            if v_abrir.get():
                os.startfile(ruta)
        except (ExcelError, ValueError) as e:
            log("ERROR: %s" % e)
            messagebox.showerror("No se pudo generar", str(e))
        except Exception as e:
            log(traceback.format_exc())
            messagebox.showerror("Error inesperado", str(e))
        finally:
            btn.configure(state="normal")

    btn = ttk.Button(cont, text="Generar PDF", command=ejecutar)
    btn.grid(row=5, column=3, rowspan=2, sticky="nsew", pady=4)

    ttk.Label(cont, text="Detalle").grid(row=7, column=0, sticky="w", pady=(10, 2))
    import tkinter.scrolledtext as st
    salida = st.ScrolledText(cont, height=12, state="disabled",
                             font=("Consolas", 9), background="#f6f7f9")
    salida.grid(row=8, column=0, columnspan=4, sticky="nsew")

    cont.columnconfigure(1, weight=1)
    cont.columnconfigure(3, weight=1)
    cont.rowconfigure(8, weight=1)

    log("Columnas esperadas: imagenes | C. Barra | Material | Descripcion | "
        "Tipo de Exhibicion | Alto (cm) | Ancho (cm) | Profundo/Largo (cm)")
    log("Opcional: una columna 'Caras' para fijar cuantas caras lleva cada producto.")
    if ruta_inicial and os.path.isfile(ruta_inicial):
        cargar(ruta_inicial)

    root.mainloop()


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Genera un planograma en PDF desde un Excel.")
    ap.add_argument("excel", nargs="?", help="archivo .xlsx de productos")
    ap.add_argument("--categoria", help="titulo que va arriba del planograma")
    ap.add_argument("--hoja", help="nombre de la hoja a leer")
    ap.add_argument("--ancho", type=float, default=122.0, help="ancho del mueble en cm")
    ap.add_argument("--alto", type=float, default=180.0, help="alto del mueble en cm")
    ap.add_argument("--caras", type=int, default=4, help="maximo de caras por producto")
    ap.add_argument("--sin-relleno", action="store_true",
                    help="no agregar caras automaticamente")
    ap.add_argument("--salida", help="ruta del PDF de salida")
    ap.add_argument("--no-gui", action="store_true", help="ejecutar sin ventana")
    args = ap.parse_args()

    if not args.no_gui:
        abrir_ventana(args.excel)
        return 0

    if not args.excel:
        ap.error("hace falta el archivo .xlsx (o quita --no-gui)")
    cfg = Config(module_w=args.ancho, module_h=args.alto,
                 max_facings=max(1, args.caras), auto_facings=not args.sin_relleno)
    try:
        generar(args.excel, args.categoria, args.hoja, cfg, args.salida)
    except (ExcelError, ValueError, OSError) as e:
        print("ERROR: %s" % e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
