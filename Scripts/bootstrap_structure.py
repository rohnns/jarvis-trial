from pathlib import Path

ROOT = Path('D:/Jarvis')
DIRS = ['App','Assets','Cache','Config','Core','Docs','Downloads','Installer','Logs','Memory','Models','Plugins','Scripts','Temp','Tests','UI','Voices']
for directory in DIRS:
    (ROOT / directory).mkdir(parents=True, exist_ok=True)
for package in ['Core','Plugins','UI','Memory','App','Tests']:
    (ROOT / package / '__init__.py').touch()
print('Jarvis folder structure ready')
