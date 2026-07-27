// Painel do atendente — ES6 + Fetch API + SSE. Sem frameworks (ADR-001).
'use strict';

// MVP sem autenticação: atendente via ?atendente_id= (padrão 2). Item futuro: login.
const ATENDENTE_ID = Number(new URLSearchParams(location.search).get('atendente_id') || 2);

const el = (id) => document.getElementById(id);
const mensagensEl = el('mensagens');

let conversaAtual = null;
let stream = null;
const afterRef = { valor: 0 };

// Identifica o atendente e reflete a disponibilidade real gravada no banco
async function carregarIdentidade() {
  try {
    const s = await api.get(`/api/atendente/${ATENDENTE_ID}/status`);
    el('atendente-info').textContent = s.nome
      ? `${s.nome}${s.matricula ? ` · ${s.matricula}` : ''}`
      : `Atendente ${ATENDENTE_ID}`;
    el('sel-status').value = s.status;
  } catch (e) {
    el('atendente-info').textContent = `Atendente ${ATENDENTE_ID}`;
  }
}

// ---------------------------------------------------------------- status

el('sel-status').addEventListener('change', async (ev) => {
  await api.post(`/api/atendente/${ATENDENTE_ID}/status`, { status: ev.target.value });
});

// ---------------------------------------------------------------- fila

async function carregarFila() {
  const fila = await api.get('/api/atendente/fila');
  const ul = el('lista-fila');
  ul.innerHTML = '';
  if (!fila.length) {
    const li = document.createElement('li');
    li.style.color = 'var(--cinza-texto)';
    li.textContent = 'Fila vazia';
    ul.appendChild(li);
  }
  fila.forEach((f) => {
    const li = document.createElement('li');
    const linha = document.createElement('div');
    linha.className = 'item-fila';
    const info = document.createElement('div');
    const assunto = document.createElement('div');
    assunto.className = 'assunto';
    assunto.textContent = f.assunto || 'Atendimento';
    const meta = document.createElement('div');
    meta.className = 'meta';
    const gat = document.createElement('span');
    gat.className = 'gatilho';
    gat.textContent = { pedido_explicito: 'pedido do usuário', baixa_confianca: 'bot sem resposta', topico_critico: 'TÓPICO CRÍTICO' }[f.gatilho] || f.gatilho;
    const espera = document.createElement('span');
    espera.textContent = `${f.protocolo} · ${f.espera_min} min`;
    meta.append(gat, espera);
    info.append(assunto, meta);
    const btn = document.createElement('button');
    btn.className = 'btn';
    btn.textContent = 'Assumir';
    btn.addEventListener('click', async () => {
      await api.post(`/api/conversas/${f.conversa_id}/assumir`, { atendente_id: ATENDENTE_ID });
      await Promise.all([carregarFila(), carregarMinhas()]);
      abrirConversa({ id: f.conversa_id, protocolo: f.protocolo, assunto: f.assunto, status_ui: 'Em atendimento' });
    });
    linha.append(info, btn);
    li.appendChild(linha);
    ul.appendChild(li);
  });
}

let idsMinhasConhecidos = null;   // null = ainda não carregou uma vez

async function carregarMinhas() {
  const minhas = await api.get(`/api/atendente/${ATENDENTE_ID}/conversas`);
  const ul = el('lista-minhas');
  ul.innerHTML = '';
  minhas.forEach((c) => {
    const li = document.createElement('li');
    li.dataset.id = c.id;
    if (conversaAtual?.id === c.id) li.classList.add('ativa');
    const assunto = document.createElement('div');
    assunto.className = 'assunto';
    assunto.textContent = c.assunto || 'Atendimento';
    const meta = document.createElement('div');
    meta.className = 'meta';
    const badge = document.createElement('span');
    badge.className = `badge ${badgeClasse(c.status_ui)}`;
    badge.textContent = c.status_ui;
    const proto = document.createElement('span');
    proto.textContent = c.protocolo;
    meta.append(badge, proto);
    li.append(assunto, meta);
    li.addEventListener('click', () => abrirConversa(c));
    ul.appendChild(li);
  });

  // Transferência em tempo real: se uma conversa nova foi atribuída a este
  // atendente e ele está ocioso, abre-a automaticamente (mostra o handoff).
  if (idsMinhasConhecidos !== null && !conversaAtual) {
    const nova = minhas.find((c) => !idsMinhasConhecidos.has(c.id));
    if (nova) abrirConversa(nova);
  }
  idsMinhasConhecidos = new Set(minhas.map((c) => c.id));
}

// ---------------------------------------------------------------- conversa

async function abrirConversa(c) {
  conversaAtual = c;
  stream?.close();
  el('vazio')?.remove();

  el('chat-cabecalho').hidden = false;
  el('form-entrada').hidden = false;
  el('chat-assunto').textContent = c.assunto || 'Atendimento';
  el('chat-protocolo').textContent = `Protocolo: ${c.protocolo}`;
  atualizarBadge(c.status_ui);

  mensagensEl.innerHTML = '';
  afterRef.valor = 0;
  const msgs = await api.get(`/api/conversas/${c.id}/mensagens`);
  msgs.forEach((m) => { mensagensEl.appendChild(criarMsgAtendente(m)); afterRef.valor = Math.max(afterRef.valor, m.id); });
  rolarParaFim();

  stream = assinarStream(c.id, afterRef, {
    onMensagem: (m) => {
      if (m.autor === 'atendente') {   // remove o eco otimista da própria resposta
        [...mensagensEl.querySelectorAll('.msg-pendente')]
          .find((x) => x.dataset.pendente === m.texto)?.remove();
      }
      mensagensEl.appendChild(criarMsgAtendente(m));
      rolarParaFim();
    },
    onStatus: (s) => atualizarBadge(s.status_ui),
  });
  carregarMinhas();
}

// No painel, a perspectiva inverte: mensagem do enfermeiro à esquerda, do atendente à direita.
function criarMsgAtendente(m) {
  const elMsg = criarMsgEl(m);
  if (m.autor === 'atendente') { elMsg.classList.remove('msg-atendente'); elMsg.classList.add('msg-usuario'); }
  else if (m.autor === 'usuario') { elMsg.classList.remove('msg-usuario'); elMsg.classList.add('msg-atendente'); }
  return elMsg;
}

function atualizarBadge(statusUi) {
  const b = el('chat-badge');
  b.className = `badge ${badgeClasse(statusUi)}`;
  b.textContent = statusUi;
  el('form-entrada').hidden = statusUi === 'Encerrado';
}

function rolarParaFim() { mensagensEl.scrollTop = mensagensEl.scrollHeight; }

// ---------------------------------------------------------------- envio

/** Eco otimista da resposta do atendente (aparece na hora; confirmada via SSE). */
function ecoLocalAtendente(texto) {
  const div = criarMsgAtendente({ autor: 'atendente', texto, criada_em: new Date().toISOString() });
  div.classList.add('msg-pendente');
  div.dataset.pendente = texto;
  mensagensEl.appendChild(div);
  rolarParaFim();
  return div;
}

el('form-entrada').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const campo = el('campo-texto');
  const texto = campo.value.trim();
  if (!conversaAtual || !texto) return;
  campo.value = '';
  const eco = ecoLocalAtendente(texto);
  try {
    await api.post(`/api/conversas/${conversaAtual.id}/responder`, { atendente_id: ATENDENTE_ID, texto });
  } catch (e) {
    eco.classList.replace('msg-pendente', 'msg-falha');
    eco.dataset.pendente = '';
    alert('Falha ao enviar. Tente novamente.');
  }
});

el('campo-texto').addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter' && !ev.shiftKey) {
    ev.preventDefault();
    el('form-entrada').requestSubmit();
  }
});

el('btn-encerrar').addEventListener('click', async () => {
  if (!conversaAtual || !confirm('Encerrar este atendimento?')) return;
  await api.post(`/api/conversas/${conversaAtual.id}/encerrar`);
  // Libera o painel: fica ocioso e pronto para receber o próximo em tempo real
  stream?.close();
  conversaAtual = null;
  el('chat-cabecalho').hidden = true;
  el('form-entrada').hidden = true;
  mensagensEl.innerHTML = '';
  await Promise.all([carregarFila(), carregarMinhas()]);
});

// ---------------------------------------------------------------- init

carregarIdentidade();
carregarFila();
carregarMinhas();
// Polling leve: fila e atendimentos atribuídos (transferência em tempo real)
setInterval(() => { carregarFila(); carregarMinhas(); }, 4000);
