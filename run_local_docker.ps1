# run_local_docker.ps1
# Docker Compose를 사용하여 모든 서비스를 실행하는 스크립트입니다.
# 이 스크립트를 실행하기 전에 Docker Desktop이 실행 중이어야 합니다.

# ==========================================
# 1. Docker 실행 여부 확인
# ==========================================
Write-Host "Checking if Docker is running..." -ForegroundColor Cyan

# docker info 명령어 실행 후, 성공 여부를 나타내는 $? 변수를 확인합니다.
# 2>$null 은 에러 메시지를 숨겨 깔끔한 출력을 보장합니다.
docker info > $null 2>$null
if (-not $?) {
    Write-Error "Docker is not running. Please start Docker Desktop and try again."
    exit 1
}

Write-Host "Docker is running." -ForegroundColor Green

# ==========================================
# 2. .env 파일 자동 생성 로직
# ==========================================
if (-not (Test-Path ".env")) {
    if (Test-Path "data/project_api_key.txt") {
        Write-Host "`nFound data/project_api_key.txt. Creating .env file..." -ForegroundColor Cyan
        $apiKey = (Get-Content "data/project_api_key.txt" -Raw).Trim()
        
        if ($apiKey -notmatch "^OPENAI_API_KEY=") {
            "OPENAI_API_KEY=$apiKey" | Out-File ".env" -Encoding utf8
        } else {
            $apiKey | Out-File ".env" -Encoding utf8
        }
        Write-Host ".env file created successfully from data/project_api_key.txt." -ForegroundColor Green
    } else {
        Write-Host "`n.env file not found." -ForegroundColor Yellow
        Write-Host "Please enter your OpenAI API Key to run the service:" -ForegroundColor Cyan
        $inputKey = Read-Host
        if (-not [string]::IsNullOrWhiteSpace($inputKey)) {
            "OPENAI_API_KEY=$inputKey" | Out-File ".env" -Encoding utf8
            Write-Host ".env file created." -ForegroundColor Green
        } else {
            Write-Host "No API Key provided. Skipping .env creation (Service might fail)." -ForegroundColor Red
        }
    }
}

# ==========================================
# 3. .env 파일 로드 및 환경 변수 확인
# ==========================================
if (Test-Path ".env") {
    Write-Host "`nLoading environment variables from .env file..." -ForegroundColor Cyan
    Get-Content .env | ForEach-Object {
        $line = $_.Trim()
        if ($line -and $line -notlike '#*') {
            $parts = $line -split '=', 2
            Set-Item -Path "env:$($parts[0])" -Value $parts[1]
        }
    }
}

if (-not $env:OPENAI_API_KEY) {
    Write-Warning "OPENAI_API_KEY is not set. Some features may fail. You can set it before running this script."
}

# ==========================================
# 4. Docker Compose 실행
# ==========================================
Write-Host "`nStarting all services with Docker Compose..." -ForegroundColor Cyan
Write-Host "This may take a while on the first run..."

docker-compose -f docker-compose.mini.yml up --build