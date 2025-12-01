import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
});

export async function getDocuments(userId) {
  const { data } = await api.get(`/documents?user_id=${userId}`);
  return data.items || [];
}

export async function postRecommend(payload) {
  const { data } = await api.post('/recommend', payload);
  return data;
}

export async function postParaphrase(payload) {
  const { data } = await api.post('/paraphrase', payload);
  return data;
}

export async function createDocument(payload) {
  const { data } = await api.post('/documents', payload);
  return data;
}

export async function updateDocument(docId, payload) {
  const { data } = await api.patch(`/documents/${docId}`, payload);
  return data;
}

export async function deleteDocument(docId, userId) {
  const { data } = await api.delete(`/documents/${docId}?user_id=${userId}`);
  return data;
}

export default api;

