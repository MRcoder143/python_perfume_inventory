@echo off
title Perfumes ERP Launcher 💎
echo Waking up Perfumes ERP Manager v3.0...
echo Connecting to isolated Python 3.14 Core Environment...
echo --------------------------------------------------

:: 1. Force use of your explicit Python 3.14 executable path to run Streamlit
"C:\Users\user\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m streamlit run app.py --global.developmentMode=false

pause
