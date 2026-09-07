const fs = require('fs');

let content = fs.readFileSync('src/components/MasterWorldTreeDeck.tsx', 'utf-8');

// Fix imports
content = content.replace("import React, { useState, useEffect, useRef } from 'react';", "import React, { useState, useEffect, useRef, Suspense, lazy } from 'react';");

const originalImports = `import { MemcastleModal } from './MemcastleModal';
import { TwinBrainsModal } from './TwinBrainsModal';
import { VikingRefractionsModal } from './VikingRefractionsModal';
import { OuroborosModal } from './OuroborosModal';`;

const lazyImports = `const MemcastleModal = lazy(() => import('./MemcastleModal').then(m => ({ default: m.MemcastleModal })));
const TwinBrainsModal = lazy(() => import('./TwinBrainsModal').then(m => ({ default: m.TwinBrainsModal })));
const VikingRefractionsModal = lazy(() => import('./VikingRefractionsModal').then(m => ({ default: m.VikingRefractionsModal })));
const OuroborosModal = lazy(() => import('./OuroborosModal').then(m => ({ default: m.OuroborosModal })));`;

content = content.replace(originalImports, lazyImports);

// Fix the useState for activeModal
content = content.replace(
  "const [activeModal, setActiveModal] = useState<'memcastle' | 'twin_brains' | 'viking' | null>(null);",
  "const [activeModal, setActiveModal] = useState<'memcastle' | 'twin_brains' | 'viking' | 'ouroboros' | null>(null);"
);

// Fix the typo in onOpenOuroboros
content = content.replace(
  "onOpenOuroboros={() => setActiveModal('twin_brains')}",
  "onOpenOuroboros={() => setActiveModal('ouroboros')}"
);

// Fix the rendering section
const modalSectionOld = `{activeModal === 'memcastle' && (
        <MemcastleModal isOpen={true} onClose={() => setActiveModal(null)} />
      )}
      {activeModal === 'twin_brains' && (
        <TwinBrainsModal isOpen={true} onClose={() => setActiveModal(null)} />
      )}
      {activeModal === 'viking' && (
        <VikingRefractionsModal isOpen={true} onClose={() => setActiveModal(null)} />
      )}
      {activeModal === 'ouroboros' && (
        <OuroborosModal isOpen={true} onClose={() => setActiveModal(null)} />
      )}`;

const modalSectionNew = `<Suspense fallback={
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 backdrop-blur-md">
          <div className="flex flex-col items-center gap-4 text-cyan-400 font-mono">
            <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
            <div className="text-xs uppercase tracking-widest font-bold">Dynamically Loading Matrix...</div>
          </div>
        </div>
      }>
        {activeModal === 'memcastle' && (
          <MemcastleModal isOpen={true} onClose={() => setActiveModal(null)} />
        )}
        {activeModal === 'twin_brains' && (
          <TwinBrainsModal isOpen={true} onClose={() => setActiveModal(null)} />
        )}
        {activeModal === 'viking' && (
          <VikingRefractionsModal isOpen={true} onClose={() => setActiveModal(null)} />
        )}
        {activeModal === 'ouroboros' && (
          <OuroborosModal isOpen={true} onClose={() => setActiveModal(null)} />
        )}
      </Suspense>`;

content = content.replace(modalSectionOld, modalSectionNew);

fs.writeFileSync('src/components/MasterWorldTreeDeck.tsx', content);

