FROM node:18-alpine

# Instalar dependências de build necessárias
RUN apk add --no-cache python3 make g++

WORKDIR /app

# Copia o package.json e package-lock.json primeiro para cache eficiente
COPY package*.json ./

# Instala as dependências (incluindo axios)
RUN npm install --only=production

# Copia o resto do código
COPY . .

# Expor porta
EXPOSE 3000

# Comando para iniciar a aplicação
CMD ["node", "fetch.js"]
