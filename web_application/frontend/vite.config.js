import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxyConfig = {
  target: 'https://127.0.0.1:7728',
  secure: false,
  changeOrigin: true,
}

// Routes to proxy to the backend
const apiRoutes = [
  '/upload',
  '/list_analyses',
  '/job',
  '/run_test',
  '/status',
  '/results',
  '/video',
  '/static',
  '/docs',
  '/openapi.json'
];

const proxy = {};
apiRoutes.forEach(route => {
  proxy[route] = proxyConfig;
});

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 7727,
    proxy: proxy
  },
  preview: {
    host: '0.0.0.0',
    port: 7727,
    proxy: proxy
  }
})
