@echo off
cd /d D:\Jarvis
set PYTHONPATH=D:\Jarvis
set QT_QPA_PLATFORM=offscreen
venv\Scripts\python.exe -m compileall App Core Plugins UI Tests
if errorlevel 1 exit /b 1
venv\Scripts\python.exe -m unittest Tests.test_phase1_unittest -v
