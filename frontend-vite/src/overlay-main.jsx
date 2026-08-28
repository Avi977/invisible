// Entry point for overlay.html. Named overlay-main.jsx rather than
// overlay.jsx because Windows is case-insensitive and the latter collides
// with the Overlay.jsx component next to it.
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './overlay.css';
import Overlay from './Overlay.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Overlay/>
  </StrictMode>
);
