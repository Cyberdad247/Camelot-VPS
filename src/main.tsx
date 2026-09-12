import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import { BifrostScrollExperience } from './components/BifrostScrollExperience';
import { BattleWorldAssimilation } from './components/BattleWorldAssimilation';
import { SovereignTerminalCommandCenter } from './components/SovereignTerminalCommandCenter';
import { ThroneRoomVoicePortal } from './components/ThroneRoomVoicePortal';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <ThroneRoomVoicePortal />
    <BifrostScrollExperience />
    <BattleWorldAssimilation />
    <SovereignTerminalCommandCenter />
  </StrictMode>,
);
