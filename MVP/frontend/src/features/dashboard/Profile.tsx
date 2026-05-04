import { useEffect, useState } from 'react';
import { ProfileResponse } from '../../types/api';
import { api } from '../../services/api';

export function Profile() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const data = await api.getProfile();
        setProfile(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load profile');
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, []);

  if (loading) return <div>Loading profile...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!profile) return <div>No profile data</div>;

  return (
    <div className="profile">
      <h1>Profile</h1>
      <div className="profile-card">
        <h2>{profile.displayName}</h2>
        <p><strong>Primary Sport:</strong> {profile.primarySport}</p>
        <div>
          <strong>Active Goals:</strong>
          <ul>
            {profile.activeGoals.map((goal, index) => (
              <li key={index}>{goal}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}