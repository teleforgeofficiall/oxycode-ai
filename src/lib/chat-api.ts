import { useAuth } from '@/contexts/auth-context';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export interface Chat {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  last_message?: string;
  last_role?: string;
  last_message_at?: string;
  message_count: number;
}

export interface ChatMessage {
  id: number;
  role: string;
  content: string;
  model?: string;
  created_at: string;
}

export interface ChatResponse {
  chat: Chat;
  messages: ChatMessage[];
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('oxycode_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getChats(): Promise<Chat[]> {
  const res = await fetch(`${API_BASE}/api/chats`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch chats');
  const data = await res.json();
  return data.chats;
}

export async function createChat(title: string = 'New Chat'): Promise<Chat> {
  const res = await fetch(`${API_BASE}/api/chats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to create chat');
  const data = await res.json();
  return data.chat;
}

export async function getChat(chatId: number): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chats/${chatId}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch chat');
  return res.json();
}

export async function deleteChat(chatId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chats/${chatId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to delete chat');
}

export async function renameChat(chatId: number, title: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chats/${chatId}/rename`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to rename chat');
}

export async function sendChatMessage(
  chatId: number,
  message: string,
): Promise<{ response: string; model: string; remaining: number }> {
  const res = await fetch(`${API_BASE}/api/chats/${chatId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Send failed' }));
    throw new Error(err.detail || 'Failed to send message');
  }
  return res.json();
}
