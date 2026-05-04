import { ProfileResponse, DashboardTodayResponse, WeekResponse } from '../types/api';

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
};