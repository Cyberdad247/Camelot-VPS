const fs = require('fs');
let content = fs.readFileSync('src/components/MasterWorldTreeDeck.tsx', 'utf-8');

// 1. Add Import
content = content.replace(
  "import { VikingRefractionsModal } from './VikingRefractionsModal';",
  "import { VikingRefractionsModal } from './VikingRefractionsModal';\nimport { OuroborosModal } from './OuroborosModal';"
);

// 2. Change active modal string check inside handleOuroborosTrigger
// Currently handleOuroborosTrigger just pulses the UI. I should add setActiveModal('ouroboros')
const handleOuroborosTriggerOrig = `  const handleOuroborosTrigger = () => {
    audioEngine.playStatePulse();
    setEnergyPulseTrigger((prev) => prev + 1);
    showFeedback('⚡ OUROBOROS SSM: 1.58-BIT TERNARY STATE LOOP PULSED');
    if (onExecuteCommand) {
      onExecuteCommand('ouroboros --pulse-ssm --ternary-step');
    }
  };`;

const handleOuroborosTriggerNew = `  const handleOuroborosTrigger = () => {
    audioEngine.playStatePulse();
    setEnergyPulseTrigger((prev) => prev + 1);
    setActiveModal('ouroboros');
    showFeedback('⚡ OUROBOROS SSM: 1.58-BIT TERNARY STATE LOOP PULSED');
    if (onExecuteCommand) {
      onExecuteCommand('ouroboros --pulse-ssm --ternary-step');
    }
  };`;

content = content.replace(handleOuroborosTriggerOrig, handleOuroborosTriggerNew);

// 3. Add Modal Render block
const modalRenderBlock = `{activeModal === 'viking' && (
        <VikingRefractionsModal isOpen={true} onClose={() => setActiveModal(null)} />
      )}`;

const modalRenderBlockNew = `{activeModal === 'viking' && (
        <VikingRefractionsModal isOpen={true} onClose={() => setActiveModal(null)} />
      )}
      {activeModal === 'ouroboros' && (
        <OuroborosModal isOpen={true} onClose={() => setActiveModal(null)} />
      )}`;

content = content.replace(modalRenderBlock, modalRenderBlockNew);

fs.writeFileSync('src/components/MasterWorldTreeDeck.tsx', content);
