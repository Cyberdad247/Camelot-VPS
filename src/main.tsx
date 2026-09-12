import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import { BifrostScrollExperience } from './components/BifrostScrollExperience';
import { BattleWorldAssimilation } from './components/BattleWorldAssimilation';
import { SovereignTerminalCommandCenter } from './components/SovereignTerminalCommandCenter';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <BifrostScrollExperience />
    <BattleWorldAssimilation />
    <SovereignTerminalCommandCenter />
  </StrictMode>,
);
