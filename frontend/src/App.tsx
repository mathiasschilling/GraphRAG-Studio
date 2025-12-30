import { Link, Outlet, useLocation } from 'react-router-dom';

export default function App() {
  const location = useLocation();

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>GraphRAG Studio</h1>
        <nav>
          <Link to="/" className={location.pathname === '/' ? 'active' : ''}>
            Flows
          </Link>
        </nav>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
