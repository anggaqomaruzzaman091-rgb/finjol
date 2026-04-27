import { Outlet, Link } from 'react-router-dom';
import ThemeToggle from './ThemeToggle';
import customLogo from '../assets/dreamina-2026-04-15-5813-Design_a_new_logo_for__find_jol_._Create...-removebg-preview.png';

export default function Layout() {
  return (
    <>
      <header className="header" style={{ height: '90px' }}>
        <div className="container nav">
          <Link to="/" className="logo" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center' }}>
            <img src={customLogo} alt="FindJol Logo" style={{ height: '50px', transform: 'scale(3.3)', transformOrigin: 'left center', objectFit: 'contain' }} className="logo-icon" />
          </Link>
          <div className="nav-links" style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
            <Link to="/dispute">Dispute Generator</Link>
            <Link to="/guide">Takedown Guide</Link>
            <a href="https://github.com/findjol" target="_blank" rel="noreferrer">Open Source</a>
            <ThemeToggle />
            <Link to="/dispute" className="btn-primary" style={{ textDecoration: 'none' }}>Get Started</Link>
          </div>
        </div>
      </header>

      <main>
        <Outlet />
      </main>

      <footer className="footer" style={{ marginTop: 'auto' }}>
        <div className="container" style={{ marginTop: '10px' }}>
          <div className="footer-logo" style={{ display: 'flex', alignItems: 'center' }}>
            <img src={customLogo} alt="FindJol Logo" style={{ height: '50px', transform: 'scale(3.3)', transformOrigin: 'left center', objectFit: 'contain' }} />
          </div>
          <div className="footer-nav" style={{ display: 'flex', alignItems: 'center', gap: '2rem', marginTop: '20px' }}>
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
