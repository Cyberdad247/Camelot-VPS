import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: [
        { find: '@', replacement: path.resolve(__dirname, '.') },
        { find: /^three\/webgpu$/, replacement: path.resolve(__dirname, 'node_modules/three/build/three.webgpu.js') },
        { find: /^three\/examples\/jsm\/(.*)/, replacement: path.resolve(__dirname, 'node_modules/three/examples/jsm/$1') },
        { find: /^three$/, replacement: path.resolve(__dirname, 'node_modules/three/build/three.module.js') },
      ],
    },
    server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modifyâfile watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
  };
});
