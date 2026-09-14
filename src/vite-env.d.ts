/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BIFROST_URL?: string;
  readonly VITE_BATTLE_CINEMATIC_MEDIA?: string;
  readonly VITE_PUTER_SHADOW_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
