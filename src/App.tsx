import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import './App.css';

// Code-split each route — keeps initial bundle small so Home paints fast.
const Home = lazy(() => import('./pages/Home'));
const DisputeGenerator = lazy(() => import('./pages/DisputeGenerator'));
const Certificate = lazy(() => import('./pages/Certificate'));
const TakedownGuide = lazy(() => import('./pages/TakedownGuide'));

function RouteFallback() {
  return (
    <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="route-loader" aria-label="Loading" />
    </div>
  );
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route
            index
            element={
              <Suspense fallback={<RouteFallback />}>
                <Home />
              </Suspense>
            }
          />
          <Route
            path="dispute"
            element={
              <Suspense fallback={<RouteFallback />}>
                <DisputeGenerator />
              </Suspense>
            }
          />
          <Route
            path="certificate/:id"
            element={
              <Suspense fallback={<RouteFallback />}>
                <Certificate />
              </Suspense>
            }
          />
          <Route
            path="guide"
            element={
              <Suspense fallback={<RouteFallback />}>
                <TakedownGuide />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
