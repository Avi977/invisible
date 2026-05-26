import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <div style={{ padding: 24, color: '#fff' }}>frontend-vite scaffold OK</div>
  </StrictMode>
);
