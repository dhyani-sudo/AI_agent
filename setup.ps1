# setup.ps1 - one-time setup for the AI Video Reels Agent (Windows)
# Run with:  powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"

function Write-Step($msg)  { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "    $msg" -ForegroundColor Green }

# --- 1. Check Python -------------------------------------------------------
Write-Step "Checking Python..."
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "Python was not found on PATH." -ForegroundColor Red
    Write-Host "Install it from https://www.python.org/downloads/ and make sure"
    Write-Host "the checkbox 'Add Python to PATH' is ticked during installation."
    exit 1
}
$pyVersion = (& python --version) 2>&1
Write-Ok "Found $pyVersion"

# --- 2. Install FFmpeg via winget ------------------------------------------
Write-Step "Checking FFmpeg..."
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Ok "FFmpeg already installed: $((& ffmpeg -version)[0])"
} else {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "winget not found. Install FFmpeg manually:" -ForegroundColor Red
        Write-Host "  https://www.gyan.dev/ffmpeg/builds/  (add the bin folder to PATH)"
        exit 1
    }
    Write-Host "    Installing FFmpeg with winget (this can take a minute)..."
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "winget install failed. You can install FFmpeg manually from" -ForegroundColor Red
        Write-Host "https://www.gyan.dev/ffmpeg/builds/ and add its bin folder to PATH."
        exit 1
    }
    # Refresh PATH so ffmpeg works in this same window
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Write-Ok "FFmpeg installed. Open a NEW PowerShell window later if it is still not found."
    } else {
        Write-Host "FFmpeg installed, but PATH was not refreshed. Close and reopen" -ForegroundColor Yellow
        Write-Host "PowerShell, then check with: ffmpeg -version"
    }
}

# --- 3. Done ---------------------------------------------------------------

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  1. Start the app:        python app.py"
Write-Host "     (or double-click start_app.bat)"
Write-Host "  2. In the web page, point the input folder to where your videos are"
