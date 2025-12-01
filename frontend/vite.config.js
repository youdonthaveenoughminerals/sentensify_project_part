// frontend/vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  css: {
    postcss: './postcss.config.cjs',
  },
  // base: '/sentencifyMVP-teamproject/', // GitHub Pages 배포용이므로 주석 처리

  // ✅ [수정됨] Docker 컨테이너에서 실행하기 위한 설정
  server: {
    // 1. Docker 컨테이너가 외부 접속을 허용하도록 설정
    host: '0.0.0.0', 
    port: 5173, // 포트 고정
    
    proxy: {
      // 2. 프록시 타겟을 localhost가 아닌 'api' (백엔드 서비스 이름)로 변경
      '/recommend': {
        target: 'http://api:8000',
        changeOrigin: true,
      },
      '/log': {
        target: 'http://api:8000',
        changeOrigin: true,
      },
    },
  },
});