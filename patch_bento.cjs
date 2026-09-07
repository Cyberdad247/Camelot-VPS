const fs = require('fs');

let content = fs.readFileSync('src/components/BentoGridOverview.tsx', 'utf-8');

// Fix imports
content = content.replace(
  "import React, { useState, useEffect } from 'react';", 
  "import React, { useState, useEffect, Suspense, lazy } from 'react';"
);

const originalImports = `import { MemcastleModal } from './MemcastleModal';
import { TwinBrainsModal } from './TwinBrainsModal';`;

const lazyImports = `const MemcastleModal = lazy(() => import('./MemcastleModal').then(m => ({ default: m.MemcastleModal })));
const TwinBrainsModal = lazy(() => import('./TwinBrainsModal').then(m => ({ default: m.TwinBrainsModal })));`;

content = content.replace(originalImports, lazyImports);

// Find the modals section
const modalSectionOld = `{/* Exploration Modals */}
      <MemcastleModal 
        isOpen={isMemcastleOpen} 
        onClose={() => setIsMemcastleOpen(false)} 
      />
      <TwinBrainsModal 
        isOpen={isTwinBrainsOpen} 
        onClose={() => setIsTwinBrainsOpen(false)} 
      />`;

const modalSectionNew = `{/* Exploration Modals */}
      <Suspense fallback={null}>
        {isMemcastleOpen && (
          <MemcastleModal 
            isOpen={isMemcastleOpen} 
            onClose={() => setIsMemcastleOpen(false)} 
          />
        )}
        {isTwinBrainsOpen && (
          <TwinBrainsModal 
            isOpen={isTwinBrainsOpen} 
            onClose={() => setIsTwinBrainsOpen(false)} 
          />
        )}
      </Suspense>`;

content = content.replace(modalSectionOld, modalSectionNew);

fs.writeFileSync('src/components/BentoGridOverview.tsx', content);

