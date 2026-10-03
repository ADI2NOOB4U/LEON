import { defineConfig } from 'vite'
export default defineConfig({
  resolve: { dedupe: ['react', 'react-dom', 'three'] },
  server: { port: 5173, host: '127.0.0.1', fs: { allow: ['..'] } },
})
