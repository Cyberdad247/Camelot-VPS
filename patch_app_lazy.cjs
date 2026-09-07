const fs = require('fs');

let content = fs.readFileSync('src/App.tsx', 'utf-8');

// Add Suspense and lazy
content = content.replace("import React, { useState } from 'react';", "import React, { useState, Suspense, lazy } from 'react';");

const importsToReplace = [
  "import { MasterWorldTreeDeck } from './components/MasterWorldTreeDeck';",
  "import { BentoGridOverview } from './components/BentoGridOverview';",
  "import { BootstrapTerminal } from './components/BootstrapTerminal';",
  "import { VKGHud } from './components/VKGHud';",
  "import { MissionArena } from './components/MissionArena';",
  "import { SovereignLaws } from './components/SovereignLaws';",
  "import { ScarcityProtocol } from './components/ScarcityProtocol';",
  "import { MasterBootstrapScript } from './components/MasterBootstrapScript';",
  "import { OperatorConsoleHtmx } from './components/OperatorConsoleHtmx';",
  "import { VpsHubInitiationConsole } from './components/VpsHubInitiationConsole';",
  "import { DocumentationForge } from './components/DocumentationForge';"
];

const lazyImports = `
const MasterWorldTreeDeck = lazy(() => import('./components/MasterWorldTreeDeck').then(m => ({ default: m.MasterWorldTreeDeck })));
const BentoGridOverview = lazy(() => import('./components/BentoGridOverview').then(m => ({ default: m.BentoGridOverview })));
const BootstrapTerminal = lazy(() => import('./components/BootstrapTerminal').then(m => ({ default: m.BootstrapTerminal })));
const VKGHud = lazy(() => import('./components/VKGHud').then(m => ({ default: m.VKGHud })));
const MissionArena = lazy(() => import('./components/MissionArena').then(m => ({ default: m.MissionArena })));
const SovereignLaws = lazy(() => import('./components/SovereignLaws').then(m => ({ default: m.SovereignLaws })));
const ScarcityProtocol = lazy(() => import('./components/ScarcityProtocol').then(m => ({ default: m.ScarcityProtocol })));
const MasterBootstrapScript = lazy(() => import('./components/MasterBootstrapScript').then(m => ({ default: m.MasterBootstrapScript })));
const OperatorConsoleHtmx = lazy(() => import('./components/OperatorConsoleHtmx').then(m => ({ default: m.OperatorConsoleHtmx })));
const VpsHubInitiationConsole = lazy(() => import('./components/VpsHubInitiationConsole').then(m => ({ default: m.VpsHubInitiationConsole })));
const DocumentationForge = lazy(() => import('./components/DocumentationForge').then(m => ({ default: m.DocumentationForge })));
`;

importsToReplace.forEach(imp => {
  content = content.replace(imp, '');
});

// Insert lazy imports after the OmarchyManager import
content = content.replace("import { OmarchyManager } from './utils/OmarchyManager';", "import { OmarchyManager } from './utils/OmarchyManager';\n" + lazyImports);

// Wrap main content in Suspense
const mainStart = '<main className={`flex-1 w-full ${(activeTab === \'vps_init\' || activeTab === \'docs\' || activeTab === \'deck\' || activeTab === \'operator\') ? \'p-0\' : \'p-2 sm:p-4\'}`}>';
const suspenseStart = `<Suspense fallback={
          <div className="flex-1 flex flex-col items-center justify-center min-h-[500px]">
            <div className="w-12 h-12 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
            <div className="mt-4 text-cyan-500 font-mono text-sm tracking-widest font-bold animate-pulse">INITIATING DMA TRANSFER...</div>
          </div>
        }>`;

content = content.replace(mainStart + '        {isCurrentTabMinimized ? (', mainStart + '\n        ' + suspenseStart + '\n        {isCurrentTabMinimized ? (');

content = content.replace('          </>\n        )}\n      </main>', '          </>\n        )}\n        </Suspense>\n      </main>');

fs.writeFileSync('src/App.tsx', content);
