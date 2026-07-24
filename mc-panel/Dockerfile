FROM node:22-slim
ENV NODE_ENV=production
WORKDIR /app

# klient docker CLI - panel steruje kontenerem serwera Minecraft
RUN apt-get update && apt-get install -y --no-install-recommends docker.io unzip \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./
RUN npm install --omit=dev && npm cache clean --force
COPY *.js ./

ENV PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:8080/healthz').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
