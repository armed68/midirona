@echo off
title Midirona - SF2 Piano Game
echo ========================================================
echo                 MIDIRONA - SF2 PIANO GAME
echo ========================================================
echo.
echo Your midi keyboard etc. Keystep will automatşcly connected 
echo Use the menu or TAB key for changing soundfonts.
echo.
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An unknown eroor has ben occured.
    pause
)
