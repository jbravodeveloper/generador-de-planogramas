@echo off
setlocal
cd /d "%~dp0"
title Actualizar el sitio

if not exist "planogramas-web.html" goto sin_fuente
if not exist "sitio" mkdir "sitio"
copy /Y "planogramas-web.html" "sitio\index.html" >nul
if errorlevel 1 goto fallo

echo.
echo  sitio\index.html actualizado con la ultima version.
echo  Volve a desplegar esa carpeta en Vercel para publicar el cambio.
echo.
pause
exit /b 0

:sin_fuente
echo.
echo  No se encontro planogramas-web.html en esta carpeta.
echo.
pause
exit /b 1

:fallo
echo.
echo  No se pudo copiar el archivo.
echo.
pause
exit /b 1
