@echo off
rem ============================================================
rem  SUBIR.bat  -  manda a GitHub los cambios de esta carpeta
rem
rem  Doble clic cada vez que quieras publicar lo que haya nuevo.
rem  Se configura solo la primera vez.
rem ============================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul 2>&1

set "REPO=https://github.com/Nemeyas/mapas-probabilisticos.git"

where git >nul 2>&1
if errorlevel 1 (
  echo  No tienes git instalado: https://git-scm.com/download/win
  pause & exit /b 1
)

if not exist ".git" (
  echo  Esta carpeta todavia no es un repositorio. Corre INICIAR_REPO.bat
  pause & exit /b 1
)

rem --- remoto: si falta, se agrega solo ---
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  echo  Configurando el remoto: %REPO%
  git remote add origin "%REPO%"
  if errorlevel 1 goto error
)

rem --- mensaje del commit ---
set "MSG=%~1"
if "%MSG%"=="" set /p "MSG=Mensaje del commit (Enter para usar la fecha): "
if "%MSG%"=="" set "MSG=Avance del %DATE%"

echo.
echo  Cambios por subir:
git status --short
echo.

git add -A
git diff --cached --quiet
if not errorlevel 1 (
  echo  No hay commits nuevos que crear.
  goto empujar
)

git -c user.name="Nehemias Leiva" -c user.email="leivanehemias64@gmail.com" commit -m "%MSG%"
if errorlevel 1 goto error

:empujar
rem --- primera subida: pasar a main y fijar el upstream ---
git rev-parse --abbrev-ref --symbolic-full-name @{u} >nul 2>&1
if errorlevel 1 (
  echo.
  echo  Primera subida. Renombrando la rama a main...
  git branch -M main
  echo  Te va a pedir iniciar sesion en GitHub, en el navegador.
  git push -u origin main
) else (
  git push
)
if errorlevel 1 goto error

echo.
echo  ====================================================
echo   LISTO. Tu repositorio:
echo   https://github.com/Nemeyas/mapas-probabilisticos
echo  ====================================================
echo.
goto fin

:error
echo.
echo  FALLO. Copia el mensaje de arriba y mandamelo.
echo.

:fin
pause
endlocal
