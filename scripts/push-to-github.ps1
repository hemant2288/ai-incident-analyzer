# Push AI Incident Analyzer to a new public GitHub repository.
# Usage:
#   .\scripts\push-to-github.ps1 -GitHubUsername YOUR_USERNAME
#   .\scripts\push-to-github.ps1 -GitHubUsername YOUR_USERNAME -RepoName ai-incident-analyzer

param(
    [Parameter(Mandatory = $true)]
    [string]$GitHubUsername,

    [string]$RepoName = "ai-incident-analyzer",

    [string]$CommitMessage = "Initial commit: enterprise AI incident root cause analyzer"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

function Find-Git {
    $candidates = @(
        "git",
        "$env:ProgramFiles\Git\bin\git.exe",
        "${env:ProgramFiles(x86)}\Git\bin\git.exe"
    )
    foreach ($c in $candidates) {
        if (Get-Command $c -ErrorAction SilentlyContinue) {
            return (Get-Command $c).Source
        }
        if (Test-Path $c) { return $c }
    }
    return $null
}

$git = Find-Git
if (-not $git) {
    Write-Host "Git is not installed." -ForegroundColor Red
    Write-Host "Install: winget install Git.Git" -ForegroundColor Yellow
    Write-Host "Then restart PowerShell and run this script again."
    exit 1
}

Write-Host "Using Git: $git" -ForegroundColor Cyan

if (Test-Path ".env") {
    Write-Host "Note: .env is gitignored and will NOT be pushed (secrets stay local)." -ForegroundColor Green
}

if (-not (Test-Path ".git")) {
    & $git init
    & $git branch -M main
}

& $git add -A
$status = & $git status --porcelain
if ($status) {
    & $git commit -m $CommitMessage
} else {
    Write-Host "No changes to commit." -ForegroundColor Yellow
}

$remoteUrl = "https://github.com/$GitHubUsername/$RepoName.git"
$existing = & $git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    & $git remote add origin $remoteUrl
} elseif ($existing -ne $remoteUrl) {
    & $git remote set-url origin $remoteUrl
}

Write-Host ""
Write-Host "=== Create the public repo on GitHub (one-time) ===" -ForegroundColor Cyan
Write-Host "1. Open: https://github.com/new"
Write-Host "2. Repository name: $RepoName"
Write-Host "3. Visibility: Public"
Write-Host "4. Do NOT add README, .gitignore, or license (this project already has them)"
Write-Host "5. Click Create repository"
Write-Host ""
$confirm = Read-Host "Press Enter after you created the repo (or type 'skip' if it already exists)"

if ($confirm -eq "skip") { Write-Host "Skipping wait..." }

Write-Host "Pushing to $remoteUrl ..." -ForegroundColor Cyan
& $git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Success! Repository:" -ForegroundColor Green
    Write-Host "https://github.com/$GitHubUsername/$RepoName"
} else {
    Write-Host ""
    Write-Host "Push failed. Common fixes:" -ForegroundColor Red
    Write-Host "- Create the repo at https://github.com/new (public, empty)"
    Write-Host "- Sign in: gh auth login   OR use Git Credential Manager when prompted"
    Write-Host "- Retry: git push -u origin main"
    exit 1
}
