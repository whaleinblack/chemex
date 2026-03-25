import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const configuredBase = env.CHEMEX_BASE_PATH || '/';
  const normalizedBase = configuredBase.endsWith('/') ? configuredBase : `${configuredBase}/`;

  return {
    base: normalizedBase,
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: 4173,
      proxy: {
        '/api': 'http://127.0.0.1:8000',
      },
    },
  };
});
