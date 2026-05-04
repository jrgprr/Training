import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { WeekResponse } from '../../types/api';
import { api } from '../../services/api';

export function WeeklyReview() {
  const { weekId } = useParams<{ weekId: string }>();
  const [week, setWeek] = useState<WeekResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadWeek = async () => {
      if (!weekId) return;

      try {
        const data = await api.getWeek(parseInt(weekId));
        setWeek(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load week');
      } finally {
        setLoading(false);
      }
    };

    loadWeek();
  }, [weekId]);

  if (loading) return <div>Loading week review...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!week) return <div>No week data</div>;

  return (
    <div className="weekly-review">
      <h1>Week {week.weekId} Review</h1>
      <div className="week-card">
        <h2>Weekly Summary</h2>
        <p><strong>Objective:</strong> {week.objective}</p>
        <p><strong>Status:</strong> {week.status}</p>
        <p><strong>Risk to Watch:</strong> {week.riskToWatch}</p>
      </div>
    </div>
  );
}