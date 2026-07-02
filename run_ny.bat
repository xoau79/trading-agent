@echo off
rem Manual/debug launcher for the New York session (shows a console window).
rem The scheduled tasks run pythonw.exe directly instead (no window).
cd /d "C:\CLAUDE CODE\Sessions\trading-agent"
"C:\Users\Anthony Phung\AppData\Local\Python\pythoncore-3.14-64\python.exe" bot.py --session newyork
pause
