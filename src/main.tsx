import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import { ThroneRoomVoicePortal } from './components/ThroneRoomVoicePortal';
import { ShadowSubspacePortal } from './components/ShadowSubspacePortal';
import { CamelotRuntimeProvider } from './runtime/CamelotRuntimeContext';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <CamelotRuntimeProvider>
      <App />
      <ThroneRoomVoicePortal />
      <ShadowSubspacePortal />
    </CamelotRuntimeProvider>
  </StrictMode>,
);
