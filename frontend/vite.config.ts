import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Домен, под которым сайт показывается через Cloudflare Tunnel.
const TUNNEL_HOST = "msdig.kz";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true, // всегда 5173: если порт занят — упасть, а не прыгать на 5174
    host: true,       // слушать все интерфейсы (нужно для туннеля/локальной сети)
    // Vite по умолчанию блокирует «чужой» Host — разрешаем наш домен.
    allowedHosts: [TUNNEL_HOST, `www.${TUNNEL_HOST}`, "localhost", "127.0.0.1"],
    // HMR через https-туннель: указываем браузеру ходить на wss://msdig.kz:443.
    // Запускать так:  $env:TUNNEL=1; npm run dev   (PowerShell)
    ...(process.env.TUNNEL
      ? { hmr: { host: TUNNEL_HOST, protocol: "wss", clientPort: 443 } }
      : {}),
    // прокси на бэкенд в dev, чтобы cookie и CORS работали без хлопот.
    // В Docker фронтенд — отдельный контейнер, поэтому цель задаётся через
    // BACKEND_ORIGIN=http://backend:8000 (имя сервиса), а на хосте — localhost.
    proxy: {
      "/api": {
        target: process.env.BACKEND_ORIGIN || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
