# install_git.ps1 - installs Git on Windows via winget
# Run with:  powershell -ExecutionPolicy Bypass -File .\install_git.ps1

$ErrorActionPreference = "Stop"

if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Host "Git is already installed: $((& git --version))" -ForegroundColor Green
    exit 0
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "winget was not found on this system." -ForegroundColor Red
    Write-Host "Install Git manually from https://git-scm.com/download/win"
    Write-Host "(accept the default options during installation)"
    exit 1
}

Write-Host "Installing Git with winget (this can take a minute)..." -ForegroundColor Cyan
winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements
if ($LASTEXITCODE -ne 0) {
    Write-Host "winget install failed (exit code $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Install Git manually from https://git-scm.com/download/win"
    exit 1
}

# Refresh PATH so git works in this same window
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "Git installed: $((& git --version))" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Git was installed, but this window does not see it yet." -ForegroundColor Yellow
    Write-Host "Close PowerShell, open a NEW window, then check with: git --version"
}
