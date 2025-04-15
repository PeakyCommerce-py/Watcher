@echo off
REM Create a log file with timestamp
set LOGFILE=update_log.txt
echo. > %LOGFILE%
echo [%date% %time%] Starting update >> %LOGFILE%

REM --- CONFIGURATION ---
REM Set project base directory
set PROJECT_DIR=C:\Users\Dejan\PycharmProjects\watcher

REM Set Python path (inside the venv)
set PYTHON_PATH=%PROJECT_DIR%\venv\Scripts\python.exe

REM Set path to the Python script to run
set SCRIPT_TO_RUN=%PROJECT_DIR%\export_activity Github.py

REM Set path to ActivityWatch executable
set ACTIVITYWATCH_EXE=C:\Users\Dejan\AppData\Local\Programs\ActivityWatch\aw-qt.exe

REM Set GitHub branch name
set GIT_BRANCH=master
REM --------------------

REM Add Python's Scripts directory to PATH (optional but good practice)
set PATH=%PROJECT_DIR%\venv\Scripts;%PATH%

REM Check if ActivityWatch is running
tasklist | findstr "aw-qt" > nul
if errorlevel 1 (
    echo [%date% %time%] ActivityWatch is not running. Starting ActivityWatch... >> %LOGFILE%
    start "" "%ACTIVITYWATCH_EXE%"
    REM Wait for ActivityWatch to start
    echo [%date% %time%] Waiting 30 seconds for ActivityWatch to potentially start... >> %LOGFILE%
    timeout /t 30 /nobreak > nul
) else (
    echo [%date% %time%] ActivityWatch is already running. >> %LOGFILE%
)

REM Install required packages if not already installed
echo [%date% %time%] Ensuring Python packages are installed... >> %LOGFILE%
"%PYTHON_PATH%" -m pip install aw-client pandas plotly requests >> %LOGFILE% 2>&1

REM Navigate to the main project directory (IMPORTANT FIX)
cd /d "%PROJECT_DIR%"
if errorlevel 1 (
    echo [%date% %time%] Failed to change directory to %PROJECT_DIR% >> %LOGFILE%
    exit /b 1
)
echo [%date% %time%] Changed directory to %PROJECT_DIR% >> %LOGFILE%

REM Run Python script with error output redirection (CORRECTED PATH)
echo [%date% %time%] Running Python script: %SCRIPT_TO_RUN% >> %LOGFILE%
"%PYTHON_PATH%" "%SCRIPT_TO_RUN%" >> %LOGFILE% 2>&1
if errorlevel 1 (
    echo [%date% %time%] Python script failed. Check %LOGFILE% for details. >> %LOGFILE%
    exit /b 1
)
echo [%date% %time%] Python script finished. >> %LOGFILE%


REM --- Git Operations ---

REM Check Git configuration (for debugging)
echo [%date% %time%] Checking Git configuration... >> %LOGFILE%
git config --list >> %LOGFILE% 2>&1
git remote -v >> %LOGFILE% 2>&1

REM Pull latest changes (optional, but good practice)
echo [%date% %time%] Pulling latest changes from %GIT_BRANCH%... >> %LOGFILE%
git pull origin %GIT_BRANCH% >> %LOGFILE% 2>&1
REM Don't exit on pull failure, maybe just log it, as push might still work
if errorlevel 1 (
    echo [%date% %time%] WARNING: Git pull failed. Proceeding anyway... >> %LOGFILE%
)

REM Add index.html to Git staging area
echo [%date% %time%] Staging index.html for Git... >> %LOGFILE%
git add index.html >> %LOGFILE% 2>&1
if errorlevel 1 (
    echo [%date% %time%] Git add index.html failed >> %LOGFILE%
    exit /b 1
)

REM Check Git status to see if there are changes to commit
echo [%date% %time%] Checking Git status for changes... >> %LOGFILE%
git status --porcelain >> %LOGFILE% 2>&1
git status --porcelain > git_status_check.tmp

REM Check if the temporary status file has content (meaning changes exist)
for %%A in (git_status_check.tmp) do if %%~zA equ 0 (
    echo [%date% %time%] No changes detected to commit. Skipping commit and push. >> %LOGFILE%
    del git_status_check.tmp
    goto SkipCommitPush
)

del git_status_check.tmp
echo [%date% %time%] Changes detected. Proceeding with commit. >> %LOGFILE%

REM Commit changes
echo [%date% %time%] Committing changes... >> %LOGFILE%
git commit -m "Daily report update" >> %LOGFILE% 2>&1
REM Error level check might be tricky here if ONLY index.html was added and it didn't change.
REM A more robust check involves parsing 'git status'. The check above is simpler.

:SkipCommitPush

REM Push to GitHub
echo [%date% %time%] Pushing to GitHub (%GIT_BRANCH% branch)... >> %LOGFILE%
git push origin %GIT_BRANCH% >> %LOGFILE% 2>&1
if errorlevel 1 (
    echo [%date% %time%] Git push failed. Check %LOGFILE% for authentication or other errors. >> %LOGFILE%
    exit /b 1
)

echo [%date% %time%] Update completed successfully >> %LOGFILE%