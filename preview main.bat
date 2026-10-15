@echo off
rem Book preview viewer: the main book (book\out\book.pdf): two-page spreads, nine ribbons, the Ordinary card.
rem Switch to the experimental version with Main ^| Experiment in the viewer, or use "preview experiment.bat".
rem   preview main.bat         opens book\out\book.pdf
rem   preview main.bat poc     opens book\out\poc.pdf
rem Close this window (or press Ctrl+C) to stop the viewer.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if "%~1"=="" (set "WHICH=book") else (set "WHICH=%~1")
if exist "%PY%" (
  "%PY%" tools\viewer\serve.py %WHICH% %2 %3 %4
) else (
  py -3 tools\viewer\serve.py %WHICH% %2 %3 %4
)
if errorlevel 1 pause
endlocal
