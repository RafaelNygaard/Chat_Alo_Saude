// Chat do enfermeiro — ES6 + Fetch API + SSE. Sem frameworks (ADR-001).
'use strict';

// Identidade do servidor (ADR-003): coletada no popup e persistida entre atendimentos.
let servidor = carregarServidor();  // {usuario_id, nome, email, matricula, funcao_id, ubs_id} | null

const el = (id) => document.getElementById(id);
const listaEl = el('lista-conversas');
const mensagensEl = el('mensagens');

let conversaAtual = null;      // {id, protocolo, assunto, status_ui}
let stream = null;
const afterRef = { valor: 0 };

// -------------------------------------------------------------- identidade

function carregarServidor() {
  try { return JSON.parse(localStorage.getItem('servidor')) || null; }
  catch { return null; }
}
function salvarServidor(s) { localStorage.setItem('servidor', JSON.stringify(s)); servidor = s; }

function atualizarIdentidade() {
  el('usuario-nome').textContent = servidor ? servidor.nome : 'Não identificado';
  el('usuario-ubs').textContent = servidor?.ubs_nome || '';
}

// ---------------------------------------------------------------- sidebar

async function carregarConversas(filtro = '') {
  if (!servidor) { listaEl.innerHTML = ''; return; }
  const conversas = await api.get(`/api/conversas?usuario_id=${servidor.usuario_id}`);
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

// -------------------------------------------------------- modal identificação

let combosCarregados = false;

async function carregarCombos() {
  if (combosCarregados) return;
  const [funcoes, ubs] = await Promise.all([api.get('/api/funcoes'), api.get('/api/ubs')]);
  const opts = (arr, ph) => `<option value="" disabled selected>${ph}</option>` +
    arr.map((o) => `<option value="${o.id}">${o.nome}</option>`).join('');
  el('id-funcao').innerHTML = opts(funcoes, 'Selecione a função...');
  el('id-ubs').innerHTML = opts(ubs, 'Selecione a unidade...');
  combosCarregados = true;
}

async function abrirModal() {
  el('id-erro').hidden = true;
  await carregarCombos();
  if (servidor) {  // pré-preenche com a última identidade
    el('id-nome').value = servidor.nome || '';
    el('id-email').value = servidor.email || '';
    el('id-matricula').value = servidor.matricula || '';
    if (servidor.funcao_id) el('id-funcao').value = servidor.funcao_id;
    if (servidor.ubs_id) el('id-ubs').value = servidor.ubs_id;
  }
  el('id-assunto').value = '';
  el('modal-identificacao').hidden = false;
  el('id-nome').focus();
}

function fecharModal() { el('modal-identificacao').hidden = true; }

el('id-cancelar').addEventListener('click', fecharModal);
el('modal-identificacao').addEventListener('click', (ev) => {
  if (ev.target === el('modal-identificacao')) fecharModal();  // clique fora fecha
});

el('form-identificacao').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const dados = {
    nome: el('id-nome').value.trim(),
    email: el('id-email').value.trim(),
    matricula: el('id-matricula').value.trim(),
    funcao_id: Number(el('id-funcao').value) || null,
    ubs_id: Number(el('id-ubs').value) || null,
  };
  const erro = el('id-erro');
  try {
    const s = await api.post('/api/servidores/identificar', dados);
    const ubsNome = el('id-ubs').selectedOptions[0]?.textContent || '';
    salvarServidor({ usuario_id: s.usuario_id, ...dados, ubs_nome: ubsNome });
    atualizarIdentidade();

    const assunto = el('id-assunto').value.trim() || 'Atendimento';
    const c = await api.post('/api/chat', { usuario_id: s.usuario_id, assunto });
    fecharModal();
    await carregarConversas();
    abrirConversa({ id: c.conversa_id, protocolo: c.protocolo, assunto, status_ui: c.status });
  } catch (e) {
    erro.textContent = 'Não foi possível identificar. Verifique os campos e tente novamente.';
    erro.hidden = false;
  }
});

// ---------------------------------------------------------------- ações

el('btn-novo').addEventListener('click', abrirModal);

el('btn-encerrar').addEventListener('click', async () => {
  if (!conversaAtual || !confirm('Encerrar este atendimento?')) return;
  await api.post(`/api/conversas/${conversaAtual.id}/encerrar`);
  carregarConversas();
});

// ---------------------------------------------------------------- init

atualizarIdentidade();
carregarConversas();
carregarChips();
if (!servidor) abrirModal();  // primeira visita: já pede identificação
