// ./src/auth/AuthContext.jsx
import { createContext, useContext, useEffect, useState } from 'react';

const AuthCtx = createContext(null);
const KEY = 'auth:user:v1';

// 백엔드 연결
const AUTH_BASE = 'http://localhost:8000';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // { id, email, name }

  // 앱 시작 시 localStorage에서 유저 복원
  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setUser(JSON.parse(raw));
    } catch (e) {
      console.error('auth load error', e);
    }
  }, []);

  // ✅ 로그인: /auth/login
  const login = async ({ email, password }) => {
    if (!email || !password) throw new Error('이메일/비밀번호를 입력하세요');

    const res = await fetch(`${AUTH_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      credentials: 'include',
    });

    if (!res.ok) {
      let msg = '로그인에 실패했습니다';
      try {
        const errBody = await res.json();
        if (errBody?.detail) {
          if (Array.isArray(errBody.detail)) {
            msg = errBody.detail.map((e) => e.msg).join(', ');
          } else {
            msg = errBody.detail;
          }
        } else if (errBody?.message) {
          msg = errBody.message;
        }
      } catch {
        // 에러 응답이 JSON이 아니면 기본 메시지 사용
      }
      throw new Error(msg);
    }

    // ⚠️ 아직 백엔드 응답 형식이 정확히 안 나왔으니까,
    // 일단은 status 200만 확인하고 프론트에서 user 객체 구성
    let data = null;
    try {
      data = await res.json(); // 나중에 필요하면 사용
    } catch {
      // body가 없을 수도 있으니 실패해도 무시
    }

    const userData = {
      // 백엔드가 id를 내려주면 우선 사용, 아니면 임시 id
      id: data?.user_id ?? data?.id ?? crypto.randomUUID(),
      email, // 우리가 보낸 이메일 그대로 사용
      name: email.split('@')[0],
    };

    setUser(userData);
    localStorage.setItem(KEY, JSON.stringify(userData));
  };

  // ✅ 회원가입: /auth/signup
  const signup = async ({ email, password }) => {
    if (!email || !password) throw new Error('이메일/비밀번호를 입력하세요');

    const res = await fetch(`${AUTH_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      credentials: 'include',
    });

    if (!res.ok) {
      let msg = '회원가입에 실패했습니다';
      try {
        const errBody = await res.json();
        if (errBody?.detail) {
          if (Array.isArray(errBody.detail)) {
            msg = errBody.detail.map((e) => e.msg).join(', ');
          } else {
            msg = errBody.detail;
          }
        } else if (errBody?.message) {
          msg = errBody.message;
        }
      } catch {}
      throw new Error(msg);
    }

    let data = null;
    try {
      data = await res.json();
    } catch {}

    const userData = {
      id: data?.id ?? crypto.randomUUID(),
      email,
      name: email.split('@')[0],
    };

    setUser(userData);
    localStorage.setItem(KEY, JSON.stringify(userData));
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(KEY);
    // 필요하면 백엔드 logout API도 호출 가능
    // fetch(`${AUTH_BASE}/logout`, { method: 'POST', credentials: 'include' }).catch(() => {});
  };

  return (
    <AuthCtx.Provider value={{ user, login, signup, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
