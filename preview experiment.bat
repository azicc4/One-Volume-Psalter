@echo off
rem Book preview viewer: the experimental version (book\out\book-weekly.pdf; lh\config.py VARIANTS "weekly"):
rem the psalms and hymns of the four-week cycle printed at each hour. Build it first:
rem   .venv\Scripts\python -m lh book --variant weekly
rem Switch back to the main book with Main ^| Experiment in the viewer.
rem Close this window (or press Ctrl+C) to stop the viewer.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if exist "%PY%" (
  "%PY%" tools\viewer\serve.py book-weekly %*
) else (
  py -3 tools\viewer\serve.py book-weekly %*
)
if errorlevel 1 pause
endlocal
