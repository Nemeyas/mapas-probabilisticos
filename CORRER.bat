@echo off
rem ============================================================
rem  CORRER.bat  -  prototipo de resolucion probabilistica
rem
rem  Corre los cuatro pasos. NO necesita clave de API.
rem  Demora alrededor de medio minuto.
rem ============================================================
setlocal
cd /d "%~dp0"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8:replace"

if not exist ".venv" (
  echo  Creando el entorno de Python...
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto error

echo  [1/5] Verificando dependencias...
python -m pip install -q -r requirements.txt
if errorlevel 1 goto error

echo  [2/5] Pruebas del modelo...
python pruebas\test_modelo.py
if errorlevel 1 goto error_pruebas

echo  [3/5] Preparando el subgrafo...
python pipeline\1_preparar_subgrafo.py
if errorlevel 1 goto error

echo  [4/5] Muestreando (4 cadenas, ~12 s)...
python pipeline\2_muestrear.py
if errorlevel 1 goto error

echo  [5/5] Mapas de calor y metricas...
python pipeline\3_mapas_calor.py
if errorlevel 1 goto error
python pipeline\4_comparar.py
if errorlevel 1 goto error

echo.
echo  ====================================================
echo   LISTO. Las figuras y los numeros estan en salida\
echo  ====================================================
echo.
goto fin

:error_pruebas
echo.
echo  FALLARON LAS PRUEBAS DEL MODELO. No sigas: revisa que cambio.
echo.
goto fin

:error
echo.
echo  ALGO FALLO. Copia el mensaje de arriba.
echo.

:fin
pause
endlocal
