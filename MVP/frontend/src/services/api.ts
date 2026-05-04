import {
  ProfileResponse,
  DashboardTodayResponse,
  WeekResponse,
  ImportUploadResponse,
} from '../types/api';

const API_BASE = 'http://localhost:8000/api/v1';

export const api = {
  async getProfile(): Promise<ProfileResponse> {
    const response = await fetch(`${API_BASE}/profile`);
    if (!response.ok) throw new Error('Failed to fetch profile');
    return response.json();
  },

  async getTodayDashboard(): Promise<DashboardTodayResponse> {
    const response = await fetch(`${API_BASE}/dashboard/today`);
    if (!response.ok) throw new Error('Failed to fetch dashboard');
    return response.json();
  },

  async getWeek(weekId: number): Promise<WeekResponse> {
    const response = await fetch(`${API_BASE}/weeks/${weekId}`);
    if (!response.ok) throw new Error('Failed to fetch week');
    return response.json();
  },

  async uploadImport(formData: FormData): Promise<ImportUploadResponse> {
    const response = await fetch(`${API_BASE}/imports/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      const message = errorBody?.detail || 'Failed to upload files';
      throw new Error(message);
    }

    return response.json();
  },
};