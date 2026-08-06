# monorepo/web: React + Vite frontend served in dev mode.
# Connects to the API service via VITE_API_URL environment variable.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]