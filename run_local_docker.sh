#!/bin/bash

# run_local_docker.sh
# Docker Compose를 사용하여 모든 서비스를 실행하는 스크립트입니다.
# 이 스크립트를 실행하기 전에 Docker가 실행 중이어야 합니다.

# 색상 정의
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}Checking if Docker is running...${NC}"

# 1. Docker 실행 여부 확인
if ! docker info &> /dev/null; then
    echo -e "${RED}Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

echo -e "${GREEN}Docker is running.${NC}"

# 2. .env 파일 자동 생성 로직
if [ ! -f .env ]; then
    if [ -f "data/project_api_key.txt" ]; then
        echo -e "\n${CYAN}Found data/project_api_key.txt. Creating .env file...${NC}"
        API_KEY=$(cat data/project_api_key.txt | tr -d '[:space:]')
        # 만약 파일 내용이 OPENAI_API_KEY= 로 시작하지 않으면 붙여줌
        if [[ "$API_KEY" != OPENAI_API_KEY=* ]]; then
            echo "OPENAI_API_KEY=$API_KEY" > .env
        else
            echo "$API_KEY" > .env
        fi
        echo -e "${GREEN}.env file created successfully from data/project_api_key.txt.${NC}"
    else
        echo -e "\n${YELLOW}.env file not found.${NC}"
        echo -e "${CYAN}Please enter your OpenAI API Key to run the service:${NC}"
        read -r INPUT_KEY
        if [ -n "$INPUT_KEY" ]; then
            echo "OPENAI_API_KEY=$INPUT_KEY" > .env
            echo -e "${GREEN}.env file created.${NC}"
        else
            echo -e "${RED}No API Key provided. Skipping .env creation (Service might fail).${NC}"
        fi
    fi
fi

# 3. 환경 변수 확인 (OPENAI_API_KEY)
if [ -f .env ]; then
  echo -e "\n${CYAN}Loading environment variables from .env file...${NC}"
  export $(grep -v '^#' .env | xargs)
fi

# .env 파일 로드 후 다시 확인
if [ -z "${OPENAI_API_KEY}" ]; then
    echo -e "\n${YELLOW}Warning: OPENAI_API_KEY is not set. Some features may fail.${NC}"
    echo -e "${YELLOW}You can set it by running 'export OPENAI_API_KEY=your_key' before this script.${NC}"
fi

# 3. Docker Compose 실행
echo -e "\n${CYAN}Starting all services with Docker Compose...${NC}"
echo -e "This may take a while on the first run..."

docker-compose -f docker-compose.mini.yml up --build