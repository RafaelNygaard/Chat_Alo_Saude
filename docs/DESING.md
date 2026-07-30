# Diretrizes do Projeto Gov.br (HTML/CSS/JS + Flask + PostgreSQL)

## 📌 Stack Tecnológica Fixa (Rígida)
- **Frontend:** HTML5 semântico, CSS3 Vanilla puro, JavaScript ES6 puro (Fetch API).
- **Restrição:** Proibido o uso de frameworks ou bibliotecas de UI (React, Vue, Tailwind, Bootstrap, etc.).
- **Backend:** Python 3.10+ / Flask 2.3.3.
- **Banco de Dados:** PostgreSQL (versão estável atual).

## 🎨 Diretrizes de Design & Código (Gov.br DS)
Sempre que gerar ou modificar códigos de interface, garanta a conformidade com o Padrão Digital de Governo:

### 1. Identidade Visual Básica
- **Tipografia:** Aplicar a fonte oficial **Rawline**. Alternativa padrão: `sans-serif`.
- **Paleta de Cores Primária:**
  - Azul Principal (Brand): `#0c326f`
  - Azul Interação (Links e Botões ativos): `#1351b4`
  - Fundo Geral do App: `#f8f8f8` ou `#ffffff`
  - Texto Principal: `#333333`

### 2. Estrutura de UI & Componentes
- **HTML Semântico:** Obrigatoriamente usar estruturas como `<header>`, `<nav>`, `<main>`, e `<footer>` seguindo o leiaute padrão gov.br (Barra de identidade visual no topo, cabeçalho do órgão, miolo centralizado, rodapé institucional).
- **CSS Vanilla:** Organizar os estilos por classes utilitárias e componentes puristas (ex: `.br-button`, `.br-input`). Evitar estilos inline.

### 3. Integração Frontend-Backend (Padrão de Comunicação)
- O Flask deve gerenciar as rotas e renderizar as páginas básicas (`render_template`).
- Toda manipulação dinâmica de dados e envio de formulários deve ser tratada no Frontend via JavaScript **Fetch API** assíncrono (`async/await`), enviando e recebendo dados estritamente em formato **JSON**.
- O Flask deve responder usando `jsonify()` nas rotas de API.

### 4. Banco de Dados (PostgreSQL)
- Persistência baseada em queries otimizadas em SQL puro ou drivers nativos (ex: `psycopg2`).
- Nomenclatura de tabelas e colunas obrigatoriamente em letras minúsculas e snake_case (`nome_usuario`, `data_cadastro`).

## 🛠️ Comandos de Desenvolvimento Comuns
- Iniciar Servidor Flask: `flask run` ou `python app.py`
- Executar Testes Backend: `pytest`

## 🤖 Arquitetura do Chatbot & Motor de NLP

### 1. Fluxo de Mensagens (Frontend ↔ Backend ↔ NLP)
- **Frontend:** Captura a entrada do usuário, renderiza no chat imediatamente em formato de "balão" e dispara um `fetch('/api/chat', { method: 'POST', body: JSON.json(payload) })`.
- **Backend (Flask):** Atua como gateway intermediário. Ele intercepta a requisição, envia ao Motor de NLP, recebe a intenção/resposta, registra a conversa no PostgreSQL e retorna o JSON para o cliente.
- **Formato do JSON de Resposta:** Sempre incluir `text`, `intent`, `confidence` e, se necessário, `actions` (para botões de resposta rápida).

### 2. Padrões Visuais de Chat (Gov.br DS)
- **Acessibilidade (WCAG/EMAG):** A área de mensagens deve usar `aria-live="polite"` e `role="log"` para que novas mensagens sejam lidas por deficientes visuais.
- **Estilos de Mensagem:**
  - Mensagem do Usuário: Alinhada à direita, fundo azul claro ou cinza neutro.
  - Mensagem do Bot: Alinhada à esquerda, fundo branco com borda sutil, ícone/avatar oficial do assistente do órgão.
- **Componentes Extras:** Gerar suporte a componentes ricos do gov.br dentro do chat (Ex: botões de feedback "Útil / Não útil", links de serviços públicos formatados).

### 3. Integração com o Motor de NLP
- O Claude deve priorizar chamadas assíncronas utilizando bibliotecas Python nativas ou clientes oficiais homologados (ex: requisições HTTP nativas para APIs externas ou SDK puro da tecnologia escolhida), mantendo o código do backend leve e modular.

