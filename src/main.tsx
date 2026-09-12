import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import { ThroneRoomVoicePortal } from './components/ThroneRoomVoicePortal';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <ThroneRoomVoicePortal />
  </StrictMode>,
);
