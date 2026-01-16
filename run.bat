@echo off
REM Finanzen App - Python Script Runner
REM Verwendung: run.bat script_name [arguments]

cd /d "C:\Users\Public\Workspaces\Finanzen"

if "%1"=="accounts" (
    .venv\Scripts\python.exe scripts/manage_accounts.py %2 %3 %4 %5
) else if "%1"=="postbank" (
    .venv\Scripts\python.exe scripts/fetch_postbank.py %2 %3 %4 %5
) else if "%1"=="categorize" (
    .venv\Scripts\python.exe scripts/categorize.py %2 %3 %4 %5
) else (
    echo Verwendung: run.bat [accounts^|postbank^|categorize] [parameter]
    echo.
    echo Beispiele:
    echo   run.bat accounts list
    echo   run.bat accounts test
    echo   run.bat postbank
    echo   run.bat categorize
)