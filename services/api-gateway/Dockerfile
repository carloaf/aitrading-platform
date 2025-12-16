FROM node:18-alpine

# Instalar dependências do sistema
RUN apk add --no-cache dumb-init wget

# Criar diretório da aplicação
WORKDIR /app

# Copiar arquivos de dependência
COPY package*.json ./

# Instalar dependências
RUN npm install --only=production && npm cache clean --force

# Copiar código fonte
COPY . .

# Criar usuário não-root
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nodejs -u 1001

# Criar diretório de logs
RUN mkdir -p logs && chown -R nodejs:nodejs /app
USER nodejs

# Expor porta
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/health

# Usar dumb-init para gerenciamento de sinais
ENTRYPOINT ["dumb-init", "--"]

# Comando de inicialização
CMD ["npm", "start"]
