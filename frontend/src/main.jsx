import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import { EffectsProvider } from './effects/Effects.jsx';
import './styles/index.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <EffectsProvider>
      <App />
    </EffectsProvider>
  </React.StrictMode>,
);
