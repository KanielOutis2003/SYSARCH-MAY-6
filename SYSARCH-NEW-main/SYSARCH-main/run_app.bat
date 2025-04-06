@echo off
echo ======================================================
echo    Student Lab Session Management System Launcher
echo ======================================================
echo.
echo IMPORTANT: Before continuing, please make sure:
echo 1. XAMPP Control Panel is open
echo 2. Apache and MySQL services are STARTED (green)
echo.
echo If XAMPP is not running:
echo 1. Open XAMPP Control Panel
echo 2. Click START next to Apache and MySQL
echo 3. Wait until both show as running (green)
echo.
echo The application can run without XAMPP, but database
echo features will be disabled (offline mode).
echo.
echo Press any key when XAMPP is running or to continue in offline mode...
pause > nul
echo.
echo Starting application...
echo.

python app.py 