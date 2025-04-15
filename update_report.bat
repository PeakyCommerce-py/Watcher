@echo off
REM Create a log file with timestamp
set LOGFILE=update_log.txt
echo. > %LOGFILE%
echo [%date% %time%] Starting update >> %LOGFILE%

REM Set Python path - Updated to your Python path
set PYTHON_PATH=C:\Users\Dejan\PycharmProjects\watcher\venv\Scripts\python.exe
set PATH=%PYTHON_PATH%;%PATH%

REM Check if ActivityWatch is running
tasklist | findstr "aw-qt" > nul
if errorlevel 1 (
    echo [%date% %time%] ActivityWatch is not running. Starting ActivityWatch... >> %LOGFILE%
    start "" "C:\Users\Dejan\AppData\Local\Programs\ActivityWatch\aw-qt.exe"
    REM Wait for ActivityWatch to start
    timeout /t 30
)

REM Install required packages if not already installed
"%PYTHON_PATH%" -m pip install aw-client pandas plotly requests >> %LOGFILE% 2>&1

REM Run Python script with error output redirection
"%PYTHON_PATH%" "C:\Users\Dejan\PycharmProjects\watcher\Watcher 2\export_activity Github.py" 2>> %LOGFILE%
if errorlevel 1 (
    echo [%date% %time%] Python script failed. Check %LOGFILE% for details >> %LOGFILE%
    exit /b 1
)

REM Navigate to project directory
cd "C:\Users\Dejan\PycharmProjects\watcher\Watcher 2"

REM Check Git configuration
echo [%date% %time%] Checking Git configuration... >> %LOGFILE%
git config --list >> %LOGFILE% 2>&1
git remote -v >> %LOGFILE% 2>&1

REM Pull latest changes
echo [%date% %time%] Pulling latest changes... >> %LOGFILE%
git pull origin master >> %LOGFILE% 2>&1
if errorlevel 1 (
    echo [%date% %time%] Git pull failed >> %LOGFILE%
    exit /b 1
)

REM Add index.html to Git
echo [%date% %time%] Adding index.html to Git... >> %LOGFILE%
git add index.html 2>> %LOGFILE%
if errorlevel 1 (
    echo [%date% %time%] Git add failed >> %LOGFILE%
    exit /b 1
)

REM Check Git status
echo [%date% %time%] Git status: >> %LOGFILE%
git status >> %LOGFILE% 2>&1

REM Commit changes
echo [%date% %time%] Committing changes... >> %LOGFILE%
git commit -m "Daily report update" 2>> %LOGFILE%
if errorlevel 1 (
    echo [%date% %time%] Git commit failed >> %LOGFILE%
    exit /b 1
)

REM Push to GitHub
echo [%date% %time%] Pushing to GitHub... >> %LOGFILE%
git push origin master 2>> %LOGFILE%
if errorlevel 1 (
    echo [%date% %time%] Git push failed. Check %LOGFILE% for details >> %LOGFILE%
    exit /b 1
)

echo [%date% %time%] Update completed successfully >> %LOGFILE%