import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon-32.png', 'icon-64.png', 'icon-192.png', 'icon-512.png'],
      manifest: {
        name: 'Smart Job Platform',
        short_name: 'SmartJobs',
        description: 'Find jobs, upload CV, and get AI-powered matching.',
        theme_color: '#0f6ab4',
        background_color: '#eff8ff',
        display: 'standalone',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: '/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
    }),
  ],
})
