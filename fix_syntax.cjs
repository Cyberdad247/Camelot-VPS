const fs = require('fs');

function fixSyntax(file) {
  let content = fs.readFileSync(file, 'utf-8');
  content = content.replace(/\\\`\\\$\{(.*?)\}\\\`/g, '`${$1}`');
  fs.writeFileSync(file, content);
}

fixSyntax('src/components/MemcastleModal.tsx');
fixSyntax('src/components/TwinBrainsModal.tsx');
