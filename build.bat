@echo off
rem Builds dist\TuneCast.exe from sources.
cd /d "%~dp0"

if not exist ".venv-build\Scripts\python.exe" (
    echo [build] Creating build environment...
    python -m venv .venv-build || goto :error
)
".venv-build\Scripts\python.exe" -m pip install -q -r requirements.txt pyinstaller pillow || goto :error
".venv-build\Scripts\python.exe" tools\make_assets.py || goto :error

".venv-build\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --console ^
    --name TuneCast --icon assets\icon.ico ^
    --collect-submodules rich --collect-data certifi ^
    launcher.py || goto :error

echo.
echo [build] Done: dist\TuneCast.exe
goto :end

:error
echo [build] Build failed, see the message above.
exit /b 1

:end
