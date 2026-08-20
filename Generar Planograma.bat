@echo off
setlocal
cd /d "%~dp0"
title Generador de Planogramas

where py >nul 2>nul
if errorlevel 1 goto sin_python

py -c "import reportlab, PIL" >nul 2>nul
if errorlevel 1 goto instalar
goto ejecutar

:instalar
echo.
echo  Primera vez: instalando los componentes necesarios...
echo  (solo ocurre una vez, puede tardar un minuto)
echo.
py -m pip install --disable-pip-version-check reportlab pillow
if errorlevel 1 goto sin_paquetes
goto ejecutar

:ejecutar
where pyw >nul 2>nul
if errorlevel 1 (
    py "generar_planograma.py" %*
) else (
    start "" pyw "generar_planograma.py" %*
)
exit /b 0

:sin_python
echo.
echo  No se encontro Python en esta computadora.
echo  Instalalo desde https://www.python.org/downloads/  (marca "Add python.exe to PATH")
echo.
pause
exit /b 1

:sin_paquetes
echo.
echo  No se pudieron instalar los componentes (revisa la conexion a internet).
echo.
pause
exit /b 1
