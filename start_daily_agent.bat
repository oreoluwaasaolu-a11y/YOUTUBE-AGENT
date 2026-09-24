@echo off
title Autonomous YouTube Shorts & Long Documentary AI Agent
echo ==============================================================================
echo    AUTONOMOUS YOUTUBE PRODUCTION AGENT
echo    - Daily Shorts (>=45s): 10:00 AM, 2:00 PM, 10:00 PM
echo    - Weekly Long Documentary (>=20m): Every Sunday at 12:00 PM
echo    - Recurring Host: Dr. Julian Vance
echo ==============================================================================
cd /d "%~dp0"
python main.py --schedule --privacy public
pause
