# Generador de Planogramas

Convierte un Excel de productos —con las fotos **dentro de la celda**— en un planograma
de 122 × 180 cm listo para imprimir en PDF.

- Los productos **colgados** van arriba, en el panel de ganchos.
- Los de **tablilla** van abajo, lo más alto y pesado al piso.
- Después se pueden **reacomodar arrastrando**, cambiar caras, quitar productos y fijar
  cuántas gancheras y tablillas querés.

El detalle sale en las hojas siguientes del PDF: número de ubicación, foto, código de
barra, material, descripción y caras.

## Qué hay acá

| | |
|---|---|
| [`planogramas-web.html`](planogramas-web.html) | **La aplicación completa en un solo archivo.** Doble clic y funciona, sin instalar nada |
| [`sitio/`](sitio/) | lo que se publica en Vercel (`index.html` es una copia del anterior) |
| `Actualizar sitio.bat` | refresca `sitio/index.html` con la última versión |
| [`planograma/`](planograma/), `servidor.py`, `generar_planograma.py` | la versión con Python: ventana de escritorio y servidor local |
| [`LEEME.md`](LEEME.md) | el manual completo |

La versión HTML hace todo dentro del navegador: lee el `.xlsx`, extrae las imágenes en
celda y escribe el PDF. **El archivo nunca sale de la computadora de quien lo usa.**

## Publicar

El sitio es estático. En Vercel se importa este repositorio con:

- **Framework Preset:** Other
- **Root Directory:** `sitio`

Cada `push` a `main` vuelve a desplegar. Para actualizar el sitio después de tocar
`planogramas-web.html`, corré `Actualizar sitio.bat` y comiteá el cambio.

## Requisitos

La versión HTML no tiene ninguno: cualquier navegador actual (Chrome, Edge, Firefox o
Safari). La versión con Python necesita Python 3.9 o superior más `reportlab` y
`pillow`, que los `.bat` instalan la primera vez.

## Nota sobre los datos

El `.gitignore` deja fuera los `.xlsx` y los PDF generados, así que los códigos y las
fotos de producto no se suben al repositorio.
