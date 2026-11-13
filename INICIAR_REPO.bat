@echo off
rem ============================================================
rem  INICIAR_REPO.bat  -  deja esta carpeta como repositorio git
rem
rem  Solo se corre UNA VEZ. Despues publicas en GitHub con los
rem  dos comandos que imprime al final.
rem ============================================================
setlocal
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
  echo  No tienes git instalado. Bajalo de https://git-scm.com/download/win
  pause & exit /b 1
)

if exist ".git" (
  echo  Esta carpeta ya es un repositorio. No hago nada.
  pause & exit /b 0
)

git init
git add -A
git -c user.name="Nehemias Leiva" -c user.email="leivanehemias64@gmail.com" commit -m "Prototipo de resolucion probabilistica de restricciones espaciales narrativas"

echo.
echo  ====================================================
echo   Repositorio creado con el primer commit.
echo  ====================================================
echo.
echo  Para publicarlo en GitHub:
echo.
echo   1. Crea un repositorio VACIO en github.com/new
echo      (sin README, sin .gitignore, sin licencia)
echo      Nombre sugerido: mapas-probabilisticos
echo.
echo   2. Pega aqui los dos comandos, con TU usuario:
echo.
echo      git remote add origin https://github.com/TU_USUARIO/mapas-probabilisticos.git
echo      git push -u origin master
echo.
pause
endlocal
