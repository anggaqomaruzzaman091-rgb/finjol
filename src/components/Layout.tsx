import { Outlet, Link } from 'react-router-dom';
import ThemeToggle from './ThemeToggle';
import customLogo from '../assets/dreamina-2026-04-15-5813-Design_a_new_logo_for__find_jol_._Create...-removebg-preview.png'
export default function Layout() {
  return (
    <>
      <header className="header">
        <div className="container nav">
          <Link to="/" className="logo">
            {/* <img src={customLogo} alt="FindJol" className="logo-img logo-icon" /> */}
          </Link>
          <nav className="nav-links" aria-label="Primary">
            <Link to="/dispute">Dispute Generator</Link>
            <Link to="/guide">Takedown Guide</Link>
            <a href="https://github.com/findjol" target="_blank" rel="noreferrer">Open Source</a>
            <ThemeToggle />
            <Link to="/dispute" className="btn-primary">Get Started</Link>
          </nav>
        </div>
      </header>

      <main>
        <Outlet />
      </main>

      <footer className="footer">
        <div className="container">
          <div className="footer-logo">
            {/* <img src={customLogo} alt="FindJol" className="logo-img" /> */}
          </div>
          <div className="footer-nav">
            <Link to="/dispute">Dispute Generator</Link>
            <Link to="/guide">Takedown Guide</Link>
            <a href="https://github.com/findjol/findjol">GitHub</a>
          </div>
          <p>&copy; {new Date().getFullYear()} FindJol Open Source Project. All rights reserved.</p>
        </div>
      </footer>
    </>
  );
}
