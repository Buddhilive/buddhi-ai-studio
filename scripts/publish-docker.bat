@echo off
setlocal enabledelayedexpansion

:: Change directory to project root
cd /d "%~dp0.."

echo ==========================================
echo  Buddhi AI Studio - Docker Publish Script 
echo ==========================================

:: Check if docker is available
where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: 'docker' command not found. Please install Docker and ensure it is in your PATH.
    exit /b 1
)

:: Check if Docker daemon is running
docker info >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Docker daemon is not running. Please start Docker Desktop.
    exit /b 1
)

:: Detect current version from package.json if node is available
set DETECTED_VERSION=
if exist package.json (
    for /f "delims=" %%v in ('node -p "require('./package.json').version" 2^>nul') do (
        set DETECTED_VERSION=%%v
    )
)

:: Get version from argument or prompt
set VERSION=%1
if "%VERSION%"=="" (
    if not "%DETECTED_VERSION%"=="" (
        set /p VERSION="Enter version tag [default: %DETECTED_VERSION%]: "
        if "!VERSION!"=="" set VERSION=%DETECTED_VERSION%
    ) else (
        set /p VERSION="Enter version tag (e.g. 0.2.0): "
    )
)

if "%VERSION%"=="" (
    echo Error: Version cannot be empty.
    exit /b 1
)

:: Strip leading 'v' if present
if "!VERSION:~0,1!"=="v" set "VERSION=!VERSION:~1!"

set BACKEND_IMAGE=buddhilive/ai-studio-service
set FRONTEND_IMAGE=buddhilive/ai-studio-ui

echo.
echo Target Images:
echo   Backend:  %BACKEND_IMAGE%:%VERSION% ^& %BACKEND_IMAGE%:latest
echo   Frontend: %FRONTEND_IMAGE%:%VERSION% ^& %FRONTEND_IMAGE%:latest
echo.

:: 1. Build Backend
echo --^> Building Backend image...
docker build -t %BACKEND_IMAGE%:%VERSION% -t %BACKEND_IMAGE%:latest -f backend/Dockerfile ./backend
if %ERRORLEVEL% neq 0 (
    echo Error: Backend image build failed.
    exit /b %ERRORLEVEL%
)

:: 2. Build Frontend
echo --^> Building Frontend image...
docker build -t %FRONTEND_IMAGE%:%VERSION% -t %FRONTEND_IMAGE%:latest -f Dockerfile .
if %ERRORLEVEL% neq 0 (
    echo Error: Frontend image build failed.
    exit /b %ERRORLEVEL%
)

:: 3. Publish Backend
echo --^> Pushing Backend images to Docker Hub...
docker push %BACKEND_IMAGE%:%VERSION%
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to push %BACKEND_IMAGE%:%VERSION%. Ensure you ran 'docker login'.
    exit /b %ERRORLEVEL%
)

docker push %BACKEND_IMAGE%:latest
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to push %BACKEND_IMAGE%:latest.
    exit /b %ERRORLEVEL%
)

:: 4. Publish Frontend
echo --^> Pushing Frontend images to Docker Hub...
docker push %FRONTEND_IMAGE%:%VERSION%
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to push %FRONTEND_IMAGE%:%VERSION%. Ensure you ran 'docker login'.
    exit /b %ERRORLEVEL%
)

docker push %FRONTEND_IMAGE%:latest
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to push %FRONTEND_IMAGE%:latest.
    exit /b %ERRORLEVEL%
)

echo.
echo ==========================================
echo  Successfully published Buddhi AI Studio!
echo   - %BACKEND_IMAGE%:%VERSION%
echo   - %BACKEND_IMAGE%:latest
echo   - %FRONTEND_IMAGE%:%VERSION%
echo   - %FRONTEND_IMAGE%:latest
echo ==========================================
exit /b 0
