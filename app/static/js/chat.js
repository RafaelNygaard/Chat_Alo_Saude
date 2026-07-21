// Chat do enfermeiro — ES6 + Fetch API + SSE. Sem frameworks (ADR-001).
'use strict';

// MVP sem autenticação: usuário via ?usuario_id= (padrão 1). Item futuro: login.
const USUARIO_ID = Number(new URLSearchParams(location.search).get('usuario_id') || 1);

const el = (id) => document.getElementById(id);
const listaEl = el('lista-conversas');
const mensagensEl = el('mensagens');

let conversaAtual = null;      // {id, protocolo, assunto, status_ui}
let stream = null;
const afterRef = { valor: 0 };

// ---------------------------------------------------------------- sidebar

async function carregarConversas(filtro = '') {
  const conversas = await api.get(`/api/conversas?usuario_id=${USUARIO_ID}`);
  listaEl.innerHTML = '';
  conversas
    .filter((c) => !filtro || (c.assunto || '').toLowerCase().includes(filtro) || c.protocolo.toLowerCase().includes(filtro))
    .forEach((c) => {
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
      listaEl.appendChild(li);
    });
}

el('busca').addEventListener('input', (ev) => carregarConversas(ev.target.value.trim().toLowerCase()));

// ---------------------------------------------------------------- conversa

async function abrirConversa(c) {
  conversaAtual = c;
  stream?.close();
  el('vazio')?.remove();

  el('chat-cabecalho').hidden = false;
  el('form-entrada').hidden = false;
  el('chips').hidden = false;
  el('chat-assunto').textContent = c.assunto || 'Atendimento';
  el('chat-protocolo').textContent = `Protocolo: ${c.protocolo}`;
  atualizarBadge(c.status_ui);

  mensagensEl.innerHTML = '';
  afterRef.valor = 0;
  const msgs = await api.get(`/api/conversas/${c.id}/mensagens`);
  msgs.forEach((m) => { mensagensEl.appendChild(criarMsgEl(m)); afterRef.valor = Math.max(afterRef.valor, m.id); });
  rolarParaFim();

  stream = assinarStream(c.id, afterRef, {
    onMensagem: (m) => { removerTyping(); mensagensEl.appendChild(criarMsgEl(m)); rolarParaFim(); },
    onStatus: (s) => atualizarBadge(s.status_ui),
  });
  carregarConversas();
}

function atualizarBadge(statusUi) {
  const b = el('chat-badge');
  b.className = `badge ${badgeClasse(statusUi)}`;
  b.textContent = statusUi;
  el('form-entrada').hidden = statusUi === 'Encerrado';
  el('chips').hidden = statusUi === 'Encerrado';
}

function rolarParaFim() { mensagensEl.scrollTop = mensagensEl.scrollHeight; }

// ---------------------------------------------------------------- envio

function mostrarTyping() {
  removerTyping();
  const t = document.createElement('div');
  t.className = 'typing';
  t.id = 'typing';
  t.innerHTML = '<span></span><span></span><span></span>';
  mensagensEl.appendChild(t);
  rolarParaFim();
}
function removerTyping() { document.getElementById('typing')?.remove(); }

async function enviar(texto) {
  if (!conversaAtual || !texto.trim()) return;
  // Eco local imediato; a mensagem persistida chega também via SSE (deduplicada por id)
  mostrarTyping();
  try {
    await api.post(`/api/conversas/${conversaAtual.id}/mensagens`, { texto });
  } catch (e) {
    removerTyping();
    alert('Falha ao enviar. Tente novamente.');
  }
}

el('form-entrada').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const campo = el('campo-texto');
  enviar(campo.value);
  campo.value = '';
});

el('campo-texto').addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter' && !ev.shiftKey) {
    ev.preventDefault();
    el('form-entrada').requestSubmit();
  }
});

// ---------------------------------------------------------------- chips

async function carregarChips() {
  const chips = await api.get('/api/chips');
  const cont = el('chips');
  cont.innerHTML = '';
  chips.forEach((ch) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.textContent = ch.label;
    b.addEventListener('click', () => enviar(ch.texto));
    cont.appendChild(b);
  });
}

// ---------------------------------------------------------------- ações

el('btn-novo').addEventListener('click', async () => {
  const assunto = prompt('Assunto do atendimento:');
  if (assunto === null) return;
  const c = await api.post('/api/chat', { usuario_id: USUARIO_ID, assunto: assunto || 'Atendimento' });
  await carregarConversas();
  abrirConversa({ id: c.conversa_id, protocolo: c.protocolo, assunto: assunto || 'Atendimento', status_ui: c.status });
});

el('btn-encerrar').addEventListener('click', async () => {
  if (!conversaAtual || !confirm('Encerrar este atendimento?')) return;
  await api.post(`/api/conversas/${conversaAtual.id}/encerrar`);
  carregarConversas();
});

// ---------------------------------------------------------------- init

carregarConversas();
carregarChips();
