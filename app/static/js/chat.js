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
  el('btn-sair-servidor').hidden = !servidor;
}

function sairServidor() {
  localStorage.removeItem('servidor');
  servidor = null;
  conversaAtual = null;
  stream?.close();
  listaEl.innerHTML = '';
  mensagensEl.innerHTML = '';
  el('chat-cabecalho').hidden = true;
  el('form-entrada').hidden = true;
  el('chips').hidden = true;
  atualizarIdentidade();
  abrirLogin();
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

// --------------------------------------------- feedback do bot (gov.br DS)

/** Renderiza a mensagem e, se for do bot, anexa o feedback "Útil/Não útil". */
function criarMsgChat(m) {
  const bolha = criarMsgEl(m);
  if (m.autor === 'bot' && m.id) anexarFeedback(bolha, m.id);
  return bolha;
}

function anexarFeedback(bolha, mensagemId) {
  const fb = document.createElement('div');
  fb.className = 'feedback';
  const rotulo = document.createElement('span');
  rotulo.textContent = 'Esta resposta foi útil?';
  fb.appendChild(rotulo);
  const criar = (texto, util) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'br-button feedback-btn';
    b.textContent = texto;
    b.addEventListener('click', async () => {
      try { await api.post(`/api/mensagens/${mensagemId}/feedback`, { util }); } catch (e) { /* silencioso */ }
      fb.textContent = 'Obrigado pelo feedback!';
    });
    return b;
  };
  fb.append(criar('\u{1F44D} Útil', true), criar('\u{1F44E} Não útil', false));
  bolha.appendChild(fb);
}

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
  msgs.forEach((m) => { mensagensEl.appendChild(criarMsgChat(m)); afterRef.valor = Math.max(afterRef.valor, m.id); });
  if (c.status_ui === 'Encerrado') {
    try { mostrarEncerramento(await api.get('/api/encerramento')); } catch (e) { /* card é opcional */ }
  }
  rolarParaFim();

  stream = assinarStream(c.id, afterRef, {
    onMensagem: (m) => {
      removerTyping();
      confirmarEco(m);   // remove o eco otimista, se a mensagem for a própria
      mensagensEl.appendChild(criarMsgChat(m));
      rolarParaFim();
    },
    onStatus: (s) => {
      const mudou = el('chat-badge').textContent !== s.status_ui;
      atualizarBadge(s.status_ui);
      if (mudou) carregarConversas();   // sincroniza o badge do item na lista lateral
    },
  });
  carregarConversas();
}

/** Remove o eco otimista correspondente quando a versão persistida chega via SSE. */
function confirmarEco(m) {
  if (m.autor !== 'usuario') return;
  [...mensagensEl.querySelectorAll('.msg-pendente')]
    .find((x) => x.dataset.pendente === m.texto)?.remove();
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

// "digitando" só faz sentido quando o bot vai responder (status "Aberto");
// após o handoff, quem responde é o atendente humano.
function modoBot() { return el('chat-badge').textContent === 'Aberto'; }

/** Eco otimista: a mensagem aparece na hora, antes da confirmação do servidor. */
function ecoLocal(texto) {
  const div = criarMsgEl({ autor: 'usuario', texto, criada_em: new Date().toISOString() });
  div.classList.add('msg-pendente');
  div.dataset.pendente = texto;
  mensagensEl.appendChild(div);
  rolarParaFim();
  return div;
}

async function enviar(texto) {
  texto = (texto || '').trim();
  if (!conversaAtual || !texto) return;
  const eco = ecoLocal(texto);
  if (modoBot()) mostrarTyping();
  try {
    await api.post(`/api/conversas/${conversaAtual.id}/mensagens`, { texto });
  } catch (e) {
    removerTyping();
    eco.classList.replace('msg-pendente', 'msg-falha');
    eco.dataset.pendente = '';   // não será deduplicada; fica marcada como falha
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

// ------------------------------------------------------------- tela de login

function abrirLogin() {
  el('login-servidor-erro').hidden = true;
  el('login-servidor-senha').value = '';
  if (servidor?.matricula) el('login-servidor-id').value = servidor.matricula;
  el('modal-login').hidden = false;
  el(el('login-servidor-id').value ? 'login-servidor-senha' : 'login-servidor-id').focus();
}

function fecharLogin() { el('modal-login').hidden = true; }

el('form-login-servidor').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const erro = el('login-servidor-erro');
  erro.hidden = true;
  const r = await fetch('/api/servidores/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      identificador: el('login-servidor-id').value.trim(),
      senha: el('login-servidor-senha').value,
    }),
  });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    erro.textContent = j.erro || 'Não foi possível entrar.';
    erro.hidden = false;
    return;
  }
  const s = await r.json();        // resposta já vem sem senha
  salvarServidor(s);
  atualizarIdentidade();
  fecharLogin();
  if (s.redirecionar) { location.href = s.redirecionar; return; }   // "Atendente chat"
  await carregarConversas();
});

// "Cadastrar usuário" leva o novo profissional ao popup de cadastro
el('btn-ir-cadastro').addEventListener('click', () => { fecharLogin(); abrirModal(); });

// -------------------------------------------------------- modal de cadastro

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
  el('id-senha').value = '';  // nunca pré-preenche a senha
  el('modal-identificacao').hidden = false;
  (servidor ? el('id-senha') : el('id-nome')).focus();
}

function fecharModal() { el('modal-identificacao').hidden = true; }

function voltarParaLogin() { fecharModal(); abrirLogin(); }

el('id-voltar-login').addEventListener('click', voltarParaLogin);
el('modal-identificacao').addEventListener('click', (ev) => {
  if (ev.target !== el('modal-identificacao')) return;   // clique fora
  if (servidor) fecharModal(); else voltarParaLogin();   // sem identidade, volta ao login
});

el('form-identificacao').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const erro = el('id-erro');
  erro.hidden = true;
  const dados = {
    nome: el('id-nome').value.trim(),
    email: el('id-email').value.trim(),
    matricula: el('id-matricula').value.trim(),
    senha: el('id-senha').value,
    funcao_id: Number(el('id-funcao').value) || null,
    ubs_id: Number(el('id-ubs').value) || null,
  };

  // fetch direto para ler a mensagem de erro do servidor (ex.: senha incorreta)
  const r = await fetch('/api/servidores/identificar', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados),
  });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    erro.textContent = j.erro || 'Não foi possível identificar. Verifique os campos.';
    erro.hidden = false;
    return;
  }
  const s = await r.json();
  const ubsNome = el('id-ubs').selectedOptions[0]?.textContent || '';
  const { senha, ...semSenha } = dados;  // a senha nunca é persistida no navegador
  salvarServidor({ usuario_id: s.usuario_id, ...semSenha, ubs_nome: ubsNome });
  atualizarIdentidade();
  // Cadastrou-se como "Atendente chat": já entra no painel do atendente
  if (s.redirecionar) { location.href = s.redirecionar; return; }

  try {
    fecharModal();
    await criarAtendimento();
  } catch (e) {
    erro.textContent = 'Cadastro concluído, mas houve falha ao abrir o atendimento.';
    erro.hidden = false;
  }
});

// ---------------------------------------------------------------- ações

async function criarAtendimento(assunto = 'Atendimento') {
  const c = await api.post('/api/chat', { usuario_id: servidor.usuario_id, assunto });
  await carregarConversas();
  abrirConversa({ id: c.conversa_id, protocolo: c.protocolo, assunto, status_ui: c.status });
}

// Já logado: abre atendimento direto (a senha só é pedida no login/cadastro)
el('btn-novo').addEventListener('click', () => {
  if (servidor) criarAtendimento(); else abrirLogin();
});

el('btn-sair-servidor').addEventListener('click', (ev) => { ev.preventDefault(); sairServidor(); });

// Encerrar passa pela pesquisa de satisfação
el('btn-encerrar').addEventListener('click', () => { if (conversaAtual) abrirPesquisa(); });

// --------------------------------------------------- pesquisa de satisfação

const ROTULOS_NOTA = ['Muito ruim', 'Ruim', 'Regular', 'Boa', 'Ótima'];
const EMOJI_NOTA = ['\u{1F61E}', '\u{1F641}', '\u{1F610}', '\u{1F642}', '\u{1F604}'];
let notaSelecionada = null;

function montarNotas() {
  const fs = el('notas');
  if (fs.querySelector('.notas-botoes')) return;
  const cont = document.createElement('div');
  cont.className = 'notas-botoes';
  for (let n = 1; n <= 5; n++) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'nota-btn';
    b.setAttribute('aria-pressed', 'false');
    b.setAttribute('aria-label', `Nota ${n} — ${ROTULOS_NOTA[n - 1]}`);
    b.append(EMOJI_NOTA[n - 1]);
    const r = document.createElement('span');
    r.className = 'rotulo';
    r.textContent = ROTULOS_NOTA[n - 1];
    b.appendChild(r);
    b.addEventListener('click', () => {
      notaSelecionada = n;
      cont.querySelectorAll('.nota-btn')
        .forEach((x, i) => x.setAttribute('aria-pressed', String(i + 1 === n)));
    });
    cont.appendChild(b);
  }
  fs.appendChild(cont);
}

function abrirPesquisa() {
  montarNotas();
  notaSelecionada = null;
  el('notas').querySelectorAll('.nota-btn').forEach((x) => x.setAttribute('aria-pressed', 'false'));
  el('pesquisa-comentario').value = '';
  el('pesquisa-erro').hidden = true;
  el('modal-pesquisa').hidden = false;
}

function fecharPesquisa() { el('modal-pesquisa').hidden = true; }

async function finalizarEncerramento(resposta) {
  fecharPesquisa();
  atualizarBadge(resposta.status);
  if (resposta.encerramento) mostrarEncerramento(resposta.encerramento);
  await carregarConversas();
}

el('form-pesquisa').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const erro = el('pesquisa-erro');
  if (!notaSelecionada) {
    erro.textContent = 'Selecione uma nota de 1 a 5.';
    erro.hidden = false;
    return;
  }
  try {
    finalizarEncerramento(await api.post(`/api/conversas/${conversaAtual.id}/pesquisa`, {
      nota: notaSelecionada, comentario: el('pesquisa-comentario').value.trim(),
    }));
  } catch (e) {
    erro.textContent = 'Falha ao enviar a pesquisa. Tente novamente.';
    erro.hidden = false;
  }
});

el('pesquisa-pular').addEventListener('click', async () => {
  finalizarEncerramento(await api.post(`/api/conversas/${conversaAtual.id}/encerrar`));
});

/** Cartão final configurável (texto/emoji, imagem, cores) — ver área admin. */
function mostrarEncerramento(cfg) {
  el('cartao-encerramento')?.remove();
  const card = document.createElement('div');
  card.className = 'cartao-encerramento';
  card.id = 'cartao-encerramento';
  const comFundo = Boolean(cfg.imagem && cfg.imagem_como_fundo);
  if (comFundo) {
    card.classList.add('com-fundo');
    card.style.backgroundImage = `url("${cfg.imagem}")`;
  } else {
    card.style.background = cfg.cor_fundo || '';
    if (cfg.imagem) {
      const img = document.createElement('img');
      img.className = 'ilustracao';
      img.src = cfg.imagem;
      img.alt = '';
      card.appendChild(img);
    }
  }
  const t = document.createElement('div');
  t.className = 'texto';
  if (!comFundo) t.style.color = cfg.cor_texto || '';
  t.textContent = cfg.texto;   // textContent: emojis ok, sem risco de injeção
  card.appendChild(t);
  mensagensEl.appendChild(card);
  rolarParaFim();
}

// ---------------------------------------------------------------- init

atualizarIdentidade();
carregarConversas();
carregarChips();
if (!servidor) abrirLogin();  // sem identidade: tela de login (com opção de cadastro)
