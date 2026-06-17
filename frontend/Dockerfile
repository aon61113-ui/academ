# Dev-образ фронтенда (Vite dev-server с проксированием /api на backend).
FROM node:20-alpine

WORKDIR /app
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
