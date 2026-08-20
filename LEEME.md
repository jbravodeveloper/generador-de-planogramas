# Generador de Planogramas

Convierte un Excel de productos en un planograma listo para imprimir (PDF).

- **Hoja 1** — el plano del mueble de **122 × 180 cm** con el nombre de la categoría arriba
  y un número de ubicación sobre cada producto.
- **Hojas siguientes** — el detalle: número, foto, código de barra, material, descripción,
  ubicación, medidas y cantidad de caras.

---

## Tres formas de usarlo

| | Cuándo |
|---|---|
| **Enlace de Claude** — https://claude.ai/code/artifact/84094874-3c95-4134-b86b-7bcbc73175e0 | para compartir con alguien más; no hace falta instalar nada |
| **`planogramas-web.html`** (doble clic) | lo mismo, pero como archivo local: funciona sin internet y sin Python |
| **`Abrir Generador.bat`** | la versión con Python; el PDF sale idéntico |

Las tres arman el mismo planograma. La versión HTML hace todo dentro del navegador
—lee el .xlsx, extrae las fotos y escribe el PDF— así que el archivo nunca sale de
la computadora, **y además deja reacomodar los productos a mano** (ver abajo).

---

## Cómo se usa

**Doble clic en `Abrir Generador.bat`.** Se abre el navegador con la aplicación.

1. **Soltá el Excel** en el recuadro de la izquierda (o hacé clic para buscarlo).
2. El planograma aparece al instante. Ajustá **Categoría**, **medidas** o **caras**:
   se redibuja solo.
3. **Descargar PDF**.

La primera vez instala lo necesario (`reportlab` y `pillow`); después abre directo.
El servidor corre en `localhost` y el archivo nunca sale de la computadora — se cierra
cerrando la ventana negra.

### La pantalla

| Zona | Qué hay |
|---|---|
| **Izquierda** | carga del Excel, hoja, categoría, medidas del mueble, caras, y el resumen (módulos, productos, caras, ocupación) |
| **Centro** | el planograma a escala, con la regleta de alturas y el zoom (`−` `Ajustar` `+`). Si hay varios módulos aparecen pestañas arriba |
| **Derecha** | el detalle de productos, con buscador |

Hacé clic en un producto del plano y se marca su fila en el detalle; hacé clic en una
fila y se marca en el plano (si está en otro módulo, salta a ese módulo). `Esc` deselecciona.

### Acomodar a mano

En la versión HTML (el enlace o el archivo local), **arrastrá cualquier producto** a
donde lo quieras. Mientras arrastrás se marcan las zonas donde se puede soltar:

- **sobre una fila de ganchos o una tablilla** → entra ahí, y una línea roja muestra
  entre qué productos va a quedar;
- **sobre un hueco vacío** (punteado, dice *fila nueva*) → se crea una fila o una
  tablilla nueva a esa altura.

Al soltarlo se recalcula todo: las filas se vuelven a centrar, las tablillas se
reubican y **los números se renumeran** de arriba a abajo, así que el PDF y la hoja
de detalle siempre coinciden con lo que ves.

Si soltás un producto colgado sobre una tablilla (o al revés), **cambia su forma de
exhibirse**: pasa a dibujarse parado (Ancho × Alto) en vez de colgando
(Ancho × Profundo/Largo). La app te lo avisa con las medidas nuevas.

**Las caras se cambian desde la columna «Caras» del listado**, con los botones `−` y `+`
de cada producto. Si en esa fila del mueble ya no cabe otra cara, te lo avisa y no la
agrega.

Al hacer clic en un producto aparece además una barra con su ficha, donde podés:

| | |
|---|---|
| `−` `+` | quitar o agregar caras a ese producto |
| `←` `→` | correrlo dentro de su fila |
| `↑` `↓` | pasarlo a la fila de arriba o de abajo |
| **Quitar** | sacarlo del plano |

Las flechas del teclado y las teclas `+` / `−` hacen lo mismo, y **`Supr` saca del plano
el producto seleccionado**; `Esc` deselecciona.

Lo que sacás no se pierde: arriba aparece *«N productos fuera»* con el botón **Devolver
al plano**, que los trae de vuelta al lugar que tenían.

### Cómo se reparten en la fila

Los productos quedan **repartidos parejo**: el sobrante de la fila se divide en huecos
iguales, contando también los de las orillas. Cuando la fila viene llena y no alcanza
para eso, usa la separación mínima y centra el conjunto.

Desde el primer cambio aparece el sello **Ajustado a mano** y el acomodo automático
deja de correr: podés seguir cambiando medidas del mueble y se respeta lo que armaste.
**Volver al automático** descarta los cambios (incluidos los de zona) y rearma todo.

Si algo no entra —una fila se pasaría del ancho útil o el mueble se quedaría sin
alto— el movimiento se rechaza y te lo dice, en vez de dejar un plano imposible de
montar en tienda.

### Sin navegador

Si preferís una ventana de escritorio simple, **`Generar Planograma.bat`** abre la versión
en tkinter: elegís el archivo, la hoja y la categoría, y el PDF queda guardado en la misma
carpeta del Excel como `Planograma - <Categoría>.pdf`. También podés arrastrar el `.xlsx`
encima de ese `.bat`.

---

## El Excel

La primera fila con encabezados manda. Se reconocen estas columnas (sin importar
mayúsculas, acentos ni el orden):

| Columna | Obligatoria | Qué es |
|---|---|---|
| `imágenes` | recomendada | la foto **dentro de la celda** (Insertar ▸ Imagen ▸ *Colocar en celda*) |
| `C. Barra` | no | código de barra |
| `Material` | no | código interno |
| `Descripcion` | **sí** | nombre del producto |
| `Tipo de Exhibicion` | **sí** | `Colgado` o `Tablilla` |
| `Alto (cm)` | **sí** | |
| `Ancho (cm)` | **sí** | |
| `Profundo/Largo (cm)` | **sí** | |
| `Caras` | no | si la agregás, fija cuántas caras lleva ese producto |

Las fotos también se leen si están **flotando** sobre la celda (formato viejo de Excel).

### Cómo se interpretan las medidas

| Exhibición | Cara visible en el mueble | Fondo |
|---|---|---|
| **Colgado** | `Ancho` × `Profundo/Largo` — cuelga del gancho, el largo se ve en vertical | `Alto` |
| **Tablilla** | `Ancho` × `Alto` — se para sobre la tablilla | `Profundo/Largo` |

Ejemplo: un sartén de 24 cm (`7 × 25 × 44`) colgado se dibuja de **25 cm de ancho por
44 cm de alto**; una olla sopera (`12 × 19 × 28`) en tablilla se dibuja de **19 × 12**.

---

## Cómo arma el planograma

1. **Arriba, zona de ganchos** con los productos `Colgado`. Cuelgan de una barra, todos
   alineados por el borde superior.
2. **Abajo, zona de tablillas** con los `Tablilla`. Se ordenan por altura: **lo más alto
   y pesado queda al piso**.
3. **Dentro de cada zona se respeta el orden del Excel**, así las familias quedan juntas.
   *Si querés cambiar el acomodo, reordená las filas del Excel.*
4. **Relleno automático de caras**: cada producto arranca con 1 cara y el sobrante se
   reparte de forma pareja hasta llenar el mueble (tope configurable, 4 por defecto).
5. Si no entra todo, se generan **módulos adicionales** (una hoja por módulo) con la
   numeración corrida.

En el plano, la regleta de la izquierda marca cada barra de ganchos (`G1`, `G2`, …) y
cada tablilla (`T1`, `T2`, …); ese código es el que aparece en la columna *Ubicación*
del detalle. El plano no lleva cotas: no muestra ni el ancho ni el alto del mueble ni
la altura de cada nivel.

---

## Opciones

| Opción | Para qué |
|---|---|
| Título del planograma | el texto de la cenefa, del encabezado de cada hoja del PDF y del nombre del archivo. Sale tal cual lo escribas |
| Ancho / Alto (cm) | cambiar la medida del mueble (por defecto 122 × 180) |
| Gancheras / Tablillas | cuántas filas de cada tipo querés. Vacío = las decide solo, usando las menos posibles. Con un número, reparte los productos parejo en esa cantidad de filas; si no entran todas, te avisa cuántas entraron |
| Máximo de caras | tope de caras que el relleno automático puede asignar |
| Rellenar automáticamente | destildalo para dejar 1 cara por producto (o lo que diga la columna `Caras`) |

---

## Línea de comandos

```bat
py generar_planograma.py Hogar.xlsx --no-gui
py generar_planograma.py Hogar.xlsx --categoria "Cocina" --caras 3 --no-gui
py generar_planograma.py Hogar.xlsx --ancho 90 --alto 200 --sin-relleno --no-gui

py servidor.py --puerto 9000 --sin-navegador
```

`--salida ruta.pdf` fuerza el nombre del archivo; `--hoja` elige la hoja del libro.

---

## Requisitos

Python 3.9 o superior (probado en 3.14) más `reportlab` y `pillow`, que el `.bat`
instala solo la primera vez. El front usa solo la librería estándar de Python y
navegador sin dependencias externas — funciona sin internet.

## Archivos

```
planogramas-web.html        versión autónoma: todo en el navegador, un solo archivo
Abrir Generador.bat         lanzador del front web
Generar Planograma.bat      lanzador de la ventana de escritorio
servidor.py                 servidor local (stdlib) del front
web/index.html              pantalla
web/estilos.css             estilos
web/app.js                  dibujo del plano y controles
generar_planograma.py       ventana de escritorio y línea de comandos
planograma/config.py        medidas del mueble y separaciones
planograma/excel_reader.py  lectura del Excel y de las imágenes en celda
planograma/layout.py        motor de acomodo
planograma/api.py           el acomodo en JSON, para el front
planograma/images.py        recorte y ajuste de las fotos
planograma/pdf_render.py    dibujo del PDF
```
