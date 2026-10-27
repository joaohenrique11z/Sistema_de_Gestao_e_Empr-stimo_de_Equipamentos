import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-container">
          <NavLink to="/" className="brand" onClick={() => setMenuOpen(false)}>
            <span className="brand-badge">GE</span>
            <span>Gestão de Equipamentos</span>
          </NavLink>

          <button
            type="button"
            className="menu-toggle"
            aria-expanded={menuOpen}
            aria-label="Alternar menu de navegação"
            onClick={() => setMenuOpen((prev) => !prev)}
          >
            {menuOpen ? 'Fechar ✕' : 'Menu ☰'}
          </button>

          <nav className={`nav-links ${menuOpen ? 'open' : ''}`} aria-label="Navegação principal">
            <NavLink
              to="/"
              end
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMenuOpen(false)}
            >
              Início
            </NavLink>
            <NavLink
              to="/sobre"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMenuOpen(false)}
            >
              Sobre
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="app-main">
        <Outlet />
      </main>

      <footer className="app-footer">
        Sistema de Gestão e Empréstimo de Equipamentos &bull; Monorepo FastAPI + React
      </footer>
    </div>
  );
}

