# Correção do Content Security Policy (CSP)

## Problema Identificado

O navegador estava bloqueando recursos do CDN (Chart.js, Bootstrap) e eventos inline devido a políticas de segurança muito restritivas no Content Security Policy.

### Erros originais:
```
Connecting to 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js.map' violates CSP
Connecting to 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js.map' violates CSP
Executing inline event handler violates CSP directive 'script-src-attr 'none''
GET http://localhost:8081/favicon.ico 404 (Not Found)
```

## Solução Implementada

### 1. **Atualização do CSP no server.js**

**Arquivo:** `/frontend/server.js`

**Mudanças:**
```javascript
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net", "https://unpkg.com"],
      scriptSrcAttr: ["'unsafe-inline'"],  // ✅ ADICIONADO - permite onclick, onload, etc.
      styleSrc: ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"],
      imgSrc: ["'self'", "data:", "https:"],
      connectSrc: ["'self'", API_GATEWAY_URL, "http://localhost:3007", "ws://localhost:3002", "https://cdn.jsdelivr.net"],  // ✅ ATUALIZADO
      fontSrc: ["'self'", "https://cdnjs.cloudflare.com", "https://cdn.jsdelivr.net"],  // ✅ ATUALIZADO
    },
  },
}));
```

**Diretivas adicionadas/modificadas:**
- `scriptSrcAttr: ["'unsafe-inline'"]` - Permite eventos inline como `onclick="runAllStrategies()"`
- `scriptSrc` - Adicionado `'unsafe-eval'` para suportar Chart.js que usa `eval()` internamente
- `connectSrc` - Adicionado `https://cdn.jsdelivr.net` para permitir download de source maps
- `fontSrc` - Adicionado `https://cdn.jsdelivr.net` para fontes do CDN

### 2. **Criação do favicon.ico**

**Arquivo:** `/frontend/public/favicon.ico`

Criado arquivo de ícone básico para eliminar erro 404.

### 3. **Reconstrução do Container**

Comandos executados:
```bash
docker compose stop frontend
docker compose rm -f frontend
docker compose up -d --build frontend
```

## Verificação da Solução

### Status dos Containers:
```
✅ aitrading-frontend          Up (healthy)    0.0.0.0:8081->3000/tcp
✅ aitrading-backtesting-engine Up (healthy)    0.0.0.0:3007->8000/tcp
✅ aitrading-api-gateway        Up (healthy)    0.0.0.0:3000->8080/tcp
✅ Todos os 11 containers operacionais
```

### CSP Headers Verificados:
```http
Content-Security-Policy: 
  default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com;
  script-src-attr 'unsafe-inline';
  style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com;
  connect-src 'self' http://api-gateway:8080 http://localhost:3007 ws://localhost:3002 https://cdn.jsdelivr.net;
  font-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net
```

## Como Testar

1. **Abrir o navegador:**
   ```bash
   xdg-open "http://localhost:8081/strategies"
   ```

2. **Forçar recarregamento sem cache:**
   - Pressione `Ctrl + Shift + R` (Linux/Windows)
   - Ou `Cmd + Shift + R` (Mac)

3. **Verificar Console do Navegador:**
   - Abrir DevTools (F12)
   - Aba Console deve estar limpa (sem erros de CSP)
   - Aba Network deve mostrar 200 OK para todos os recursos

4. **Testar Funcionalidade:**
   - Clicar em "Executar Todas as Estratégias"
   - Verificar que os gráficos renderizam
   - Confirmar que as tabelas de métricas aparecem

## Considerações de Segurança

### ⚠️ Diretivas Relaxadas:
- `'unsafe-inline'` - Necessário para eventos inline e scripts embutidos
- `'unsafe-eval'` - Necessário para Chart.js (usa `Function()` internamente)

### ✅ Recomendações para Produção:
1. **Migrar eventos inline para event listeners:**
   ```javascript
   // Em vez de: <button onclick="runAllStrategies()">
   // Usar:
   document.getElementById('run-btn').addEventListener('click', runAllStrategies);
   ```

2. **Usar nonces para scripts inline:**
   ```javascript
   // Gerar nonce único por requisição
   const nonce = crypto.randomBytes(16).toString('base64');
   res.locals.nonce = nonce;
   
   // No CSP:
   scriptSrc: ["'self'", `'nonce-${nonce}'`, "https://cdn.jsdelivr.net"]
   ```

3. **Considerar hospedar bibliotecas localmente:**
   ```bash
   npm install chart.js bootstrap
   # Servir de /public ao invés de CDN
   ```

## Arquivos Modificados

1. ✅ `/frontend/server.js` - CSP atualizado
2. ✅ `/frontend/public/favicon.ico` - Criado
3. ✅ Container frontend - Reconstruído

## Próximos Passos

- [ ] Testar todas as 9 estratégias na interface
- [ ] Verificar renderização dos gráficos Chart.js
- [ ] Confirmar que as métricas são calculadas corretamente
- [ ] Implementar Phase 2: Advanced Metrics (opcional)

## Links Úteis

- 🌐 Frontend: http://localhost:8081/strategies
- 🔧 API Backtesting: http://localhost:3007/strategies/professional
- 📊 API Gateway: http://localhost:3000/health

## Data da Correção
**9 de dezembro de 2025**
