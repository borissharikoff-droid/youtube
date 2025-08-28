@echo off
echo Installing dependencies...
call .venv\Scripts\activate.bat
pip install aiohttp==3.9.1
pip install -r requirements.txt
echo Dependencies installed!
pause
