import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Dashboard } from './features/dashboard/Dashboard';
import { Profile } from './features/dashboard/Profile';
import { DailyLog } from './features/daily-log/DailyLog';
import { WeeklyReview } from './features/weekly-review/WeeklyReview';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <nav className="navbar">
          <div className="nav-brand">
            <h1>Training MVP</h1>
          </div>
          <ul className="nav-links">
            <li><Link to="/">Dashboard</Link></li>
            <li><Link to="/profile">Profile</Link></li>
            <li><Link to="/daily-log">Daily Log</Link></li>
            <li><Link to="/week/1">Week Review</Link></li>
          </ul>
        </nav>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/daily-log" element={<DailyLog />} />
            <Route path="/week/:weekId" element={<WeeklyReview />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;