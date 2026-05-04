import { useEffect, useState } from 'react';
import { DashboardTodayResponse } from '../../types/api';
import { api } from '../../services/api';

export function Dashboard() {
  const [dashboard, setDashboard] = useState<DashboardTodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const data = await api.getTodayDashboard();
        setDashboard(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    };

    loadDashboard();
  }, []);

  if (loading) return <div>Loading dashboard...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!dashboard) return <div>No dashboard data</div>;

  return (
    <div className="dashboard">
      <h1>Training Dashboard</h1>
      <div className="dashboard-card">
        <h2>Today's Status</h2>
        <p><strong>Date:</strong> {dashboard.date}</p>
        <p><strong>Status:</strong> {dashboard.dayStatus}</p>
        <p><strong>Objective:</strong> {dashboard.primaryObjective}</p>
        <div>
          <strong>Pending Fields:</strong>
          <ul>
            {dashboard.pendingFields.map((field, index) => (
              <li key={index}>{field}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}