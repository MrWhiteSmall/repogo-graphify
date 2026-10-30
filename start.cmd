@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python
py -3.12 run.py
exit /b %errorlevel%
:python
python run.py
exit /b %errorlevel%
