import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import DisputeGenerator from './pages/DisputeGenerator';
import Certificate from './pages/Certificate';
import TakedownGuide from './pages/TakedownGuide';
import './App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="dispute" element={<DisputeGenerator />} />
          <Route path="certificate/:id" element={<Certificate />} />
          <Route path="guide" element={<TakedownGuide />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
