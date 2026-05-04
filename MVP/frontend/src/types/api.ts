// API Response Types
export interface ProfileResponse {
  displayName: string;
  primarySport: string;
  activeGoals: string[];
}

export interface DashboardTodayResponse {
  date: string;
  dayStatus: string;
  primaryObjective: string;
  pendingFields: string[];
}

export interface WeekResponse {
  weekId: number;
  objective: string;
  status: string;
  riskToWatch: string;
}