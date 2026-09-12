import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import { BifrostScrollExperience } from './components/BifrostScrollExperience';
import { BattleModeCommandCenter } from './components/BattleModeCommandCenter';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <BifrostScrollExperience />
    <BattleModeCommandCenter />
  </StrictMode>,
);
