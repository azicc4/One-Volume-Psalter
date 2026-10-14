@echo off
rem Book preview viewer: two-page spreads, 10 ribbons, page turning.
rem   preview.bat          opens book\out\book.pdf
rem   preview.bat poc      opens book\out\poc.pdf
rem Close this window (or press Ctrl+C) to stop the viewer.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if exist "%PY%" (
  "%PY%" tools\viewer\serve.py %*
) else (
  py -3 tools\viewer\serve.py %*
)
if errorlevel 1 pause
endlocal
