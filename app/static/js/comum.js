// Utilidades compartilhadas (chat do enfermeiro + painel do atendente) — ES6.
'use strict';

const api = {
  async get(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`GET ${url}: ${r.status}`);
    return r.json();
  },
  async post(url, corpo) { return this._enviar('POST', url, corpo); },
  async put(url, corpo) { return this._enviar('PUT', url, corpo); },
  async del(url) { return this._enviar('DELETE', url); },
  async _enviar(metodo, url, corpo) {
    const r = await fetch(url, {
      method: metodo,
      headers: { 'Content-Type': 'application/json' },
      body: corpo === undefined ? undefined : JSON.stringify(corpo ?? {}),
    });
    if (!r.ok) throw new Error(`${metodo} ${url}: ${r.status}`);
    return r.json();
  },
};

const badgeClasse = (statusUi) => ({
  'Aberto': 'aberto',
  'Aguardando': 'aguardando',
  'Em atendimento': 'em-atendimento',
  'Encerrado': 'encerrado',
}[statusUi] || 'aberto');

const horaDe = (iso) => new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

function criarMsgEl(m) {
  const div = document.createElement('div');
  if (m.autor === 'sistema') {
    div.className = 'msg-sistema';
    div.textContent = m.texto;
    return div;
  }
  div.className = `msg msg-${m.autor}`;
  const autor = document.createElement('div');
  autor.className = 'autor';
  autor.textContent = { usuario: 'Você', bot: 'Assistente Alô Saúde', atendente: 'Agente Alô Saúde' }[m.autor] || m.autor;
  const texto = document.createElement('div');
  texto.textContent = m.texto;
  const hora = document.createElement('div');
  hora.className = 'hora';
  hora.textContent = horaDe(m.criada_em);
  div.append(autor, texto, hora);
  return div;
}

/**
 * Assina o stream SSE de uma conversa (Decisão C do ADR-001).
 *
 * Cada mensagem é entregue UMA única vez. A URL do EventSource é imutável, então
 * a reconexão automática do navegador reenviaria tudo a partir do `after`
 * original (mensagens repetindo em ciclo). Por isso:
 *   1. ao receber `fim_ciclo`, fechamos e reassinamos com o `after` atualizado;
 *   2. `vistos` descarta qualquer id repetido (rede caindo, reconexão do browser).
 * Retorna um objeto com `close()`.
 */
function assinarStream(conversaId, afterRef, { onMensagem, onStatus }) {
  let es = null;
  let ativo = true;
  const vistos = new Set();

  function conectar() {
    if (!ativo) return;
    es = new EventSource(`/api/conversas/${conversaId}/stream?after=${afterRef.valor}`);

    es.addEventListener('mensagem', (ev) => {
      const m = JSON.parse(ev.data);
      afterRef.valor = Math.max(afterRef.valor, m.id);
      if (vistos.has(m.id)) return;   // já renderizada: nunca duplica
      vistos.add(m.id);
      onMensagem(m);
    });
    es.addEventListener('status', (ev) => onStatus?.(JSON.parse(ev.data)));
    // Fim do ciclo do servidor: reabre já a partir da última mensagem recebida
    es.addEventListener('fim_ciclo', () => { es.close(); conectar(); });
  }

  conectar();
  return { close() { ativo = false; es?.close(); } };
}

// Alto contraste, persistido em localStorage
function iniciarContraste() {
  const btn = document.getElementById('btn-contraste');
  const aplicar = (ligado) => {
    document.body.classList.toggle('alto-contraste', ligado);
    btn?.setAttribute('aria-pressed', String(ligado));
  };
  aplicar(localStorage.getItem('altoContraste') === '1');
  btn?.addEventListener('click', () => {
    const ligado = !document.body.classList.contains('alto-contraste');
    localStorage.setItem('altoContraste', ligado ? '1' : '0');
    aplicar(ligado);
  });
}
iniciarContraste();
