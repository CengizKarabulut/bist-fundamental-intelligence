@echo off
chcp 65001 >nul
title BIST Fundamental Intelligence
echo ============================================
echo       BIST FUNDAMENTAL INTELLIGENCE
echo ============================================
echo.
set /p "SYMBOL=Analiz edilecek hisse kodu: "
echo.
python analyze.py "%SYMBOL%"
echo.
pause
