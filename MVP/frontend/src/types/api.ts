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

export interface ImportFileSummary {
  originalFilename: string;
  fileType: string | null;
  fileHash: string | null;
  importedAt: string;
  status: string;
  rawMetadata: Record<string, unknown>;
}

export interface ImportUploadResponse {
  importBatchId: number;
  importType: string;
  filesCount: number;
  status: string;
  files: ImportFileSummary[];
  notes: string | null;
}