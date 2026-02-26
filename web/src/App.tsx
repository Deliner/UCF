import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { CatalogPage } from './pages/CatalogPage';
import { DetailPage } from './pages/DetailPage';
import { GraphPage } from './pages/GraphPage';

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="sidebar">
          <div className="sidebar-brand">
            <span className="brand-mark">UCF</span>
            <span className="brand-sub">Dashboard</span>
          </div>
          <div className="nav-links">
            <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
              <span className="nav-icon">◫</span>
              Spec Catalog
            </NavLink>
            <NavLink to="/graph" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
              <span className="nav-icon">⬡</span>
              Dependency Graph
            </NavLink>
          </div>
        </nav>
        <main className="content">
          <Routes>
            <Route path="/" element={<CatalogPage />} />
            <Route path="/specs/:kind/:name" element={<DetailPage />} />
            <Route path="/graph" element={<GraphPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
