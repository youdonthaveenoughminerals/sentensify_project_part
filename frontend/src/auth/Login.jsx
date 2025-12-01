import { useState } from 'react';
import { useAuth } from './AuthContext.jsx';

export default function Login() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState('login'); // 'login' | 'signup'
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [err, setErr] = useState('');

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr('');
    try {
      if (mode === 'login') await login({ email, password: pw });
      else await signup({ email, password: pw });
    } catch (e) {
      setErr(e.message || '오류가 발생했습니다');
    }
  };

  return (
    <div className="flex-1 grid place-items-center">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm border rounded-lg p-6 space-y-4"
      >
        <h2 className="text-lg font-semibold">
          {mode === 'login' ? '로그인' : '회원가입'}
        </h2>
        <input
          className="w-full border rounded-md p-2"
          placeholder="이메일"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          type="password"
          className="w-full border rounded-md p-2"
          placeholder="비밀번호"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
        />
        {err && <div className="text-xs text-red-600">{err}</div>}
        <button className="w-full h-10 bg-purple-600 text-white rounded-md">
          {mode === 'login' ? '로그인' : '회원가입'}
        </button>
        <button
          type="button"
          className="w-full h-10 bg-gray-100 rounded-md"
          onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
        >
          {mode === 'login' ? '회원가입으로' : '로그인으로'}
        </button>
      </form>
    </div>
  );
}
