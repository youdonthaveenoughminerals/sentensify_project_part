# 1. 기본 이미지 (Vite/React에 권장되는 Node 20)
FROM node:20-alpine

# 2. 작업 디렉터리 설정
WORKDIR /app

# 3. 의존성 설치 (소스코드 복사 전에 실행해야 Docker 캐시 활용)
COPY package.json package-lock.json ./
RUN npm install

# 4. 나머지 소스 코드 복사
COPY . .

# 5. Vite 개발 서버 포트 노출
EXPOSE 5173

# 6. Vite 개발 서버 실행 (중요: --host 0.0.0.0)
#    --host 0.0.0.0 플래그는 컨테이너 외부(PC)에서 접속을 허용합니다.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
