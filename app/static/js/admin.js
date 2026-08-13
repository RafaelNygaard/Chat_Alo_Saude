// Console administrativo — ES6, sem frameworks (ADR-001/003).
'use strict';

const main = document.getElementById('admin-main');
const h = (tag, attrs = {}, ...filhos) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v;
    else if (k === 'html') e.innerHTML = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v != null) e.setAttribute(k, v);
  }
  for (const f of filhos) if (f != null) e.append(f.nodeType ? f : document.createTextNode(f));
  return e;
};
const pilula = (ok) => h('span', { class: `pilula ${ok ? 'sim' : 'nao'}` }, ok ? 'Ativo' : 'Inativo');
const aviso = (msg) => { const p = h('p', { class: 'modal-erro' }, msg); main.prepend(p); setTimeout(() => p.remove(), 4000); };

// -------------------------------------------------------------- navegação
const SECOES = {
  relatorios: renderRelatorios,
  cabecalho: renderCabecalho,
  servidores: renderServidores,
  funcoes: renderFuncoes,
  unidades: renderUnidades,
  intents: renderIntents,
  topicos: renderTopicos,
  encerramento: renderEncerramento,
  atendentes: renderAtendentes,
  email: renderEmail,
};

document.querySelectorAll('.admin-nav button').forEach((b) => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.admin-nav button').forEach((x) => x.classList.remove('ativa'));
    b.classList.add('ativa');
    SECOES[b.dataset.secao]?.();
  });
});

// -------------------------------------------------------------- Relatórios
async function renderRelatorios() {
  main.innerHTML = '';
  main.append(h('h2', { class: 'titulo' }, 'Relatórios de atendimento'));

  const de = h('input', { type: 'date' });
  const ate = h('input', { type: 'date' });
  const q = () => `?de=${de.value}&ate=${ate.value}`;
  const alvo = h('div');

  async function carregar() {
    const r = await api.get(`/api/admin/relatorios/atendimentos${q()}`);
    alvo.innerHTML = '';
    const cards = h('div', { class: 'cards' },
      h('div', { class: 'card' }, h('div', { class: 'valor' }, String(r.total)), h('div', { class: 'rotulo' }, 'Total de atendimentos')));
    for (const [k, v] of Object.entries(r.por_status))
      cards.append(h('div', { class: 'card' }, h('div', { class: 'valor' }, String(v)), h('div', { class: 'rotulo' }, k)));
    const sat = r.satisfacao || {};
    cards.append(h('div', { class: 'card' },
      h('div', { class: 'valor' }, sat.media != null ? `${sat.media} / 5` : '—'),
      h('div', { class: 'rotulo' }, `Satisfação (${sat.respostas || 0} respostas)`)));
    alvo.append(cards);
    alvo.append(tabelaSimples('Notas de satisfação', sat.distribuicao || {}));
    alvo.append(tabelaSimples('Por unidade', r.por_ubs));
    alvo.append(tabelaSimples('Por função', r.por_funcao));
    alvo.append(tabelaSimples('Handoffs por gatilho', r.handoffs_por_gatilho));
  }

  main.append(h('div', { class: 'admin-toolbar' },
    h('label', {}, 'De', de), h('label', {}, 'Até', ate),
    h('button', { class: 'btn mini', onclick: carregar }, 'Filtrar'),
    h('button', { class: 'btn mini secundario', onclick: () => location.href = `/api/admin/relatorios/atendimentos.csv${q()}` }, 'Exportar CSV'),
  ));
  main.append(alvo);
  carregar();
}

function tabelaSimples(titulo, obj) {
  const linhas = Object.entries(obj);
  const t = h('table', { class: 'grade' }, h('tr', {}, h('th', {}, titulo), h('th', {}, 'Qtde')));
  if (!linhas.length) t.append(h('tr', {}, h('td', { colspan: '2' }, 'Sem dados no período')));
  for (const [k, v] of linhas) t.append(h('tr', {}, h('td', {}, k), h('td', {}, String(v))));
  return h('div', { style: 'margin-bottom:1.2rem;max-width:520px' }, t);
}

// -------------------------------------------------------------- Servidores
let funcoesRef = [], ubsRef = [];
async function carregarRefs() {
  [funcoesRef, ubsRef] = await Promise.all([api.get('/api/admin/funcoes'), api.get('/api/admin/ubs')]);
}
const nomePor = (arr, id) => arr.find((x) => x.id === id)?.nome || '—';

async function renderServidores() {
  main.innerHTML = '';
  await carregarRefs();
  main.append(h('h2', { class: 'titulo' }, 'Servidores e usuários'));

  const filtro = h('select', {},
    h('option', { value: '' }, 'Todos os papéis'),
    ...['servidor', 'enfermeiro', 'atendente', 'admin'].map((p) => h('option', { value: p }, p)));
  filtro.addEventListener('change', carregar);
  main.append(h('div', { class: 'admin-toolbar' }, h('label', {}, 'Papel', filtro),
    h('button', { class: 'btn mini', onclick: () => formUsuario() }, '+ Novo usuário')));

  const alvo = h('div');
  main.append(alvo);

  async function carregar() {
    const us = await api.get(`/api/admin/usuarios${filtro.value ? '?papel=' + filtro.value : ''}`);
    const t = h('table', { class: 'grade' },
      h('tr', {}, ...['Nome', 'E-mail', 'Matrícula', 'Papel', 'Função', 'Unidade', 'Login', ''].map((c) => h('th', {}, c))));
    us.forEach((u) => t.append(h('tr', {},
      h('td', {}, u.nome), h('td', {}, u.email || '—'), h('td', {}, u.matricula || '—'),
      h('td', {}, u.papel), h('td', {}, nomePor(funcoesRef, u.funcao_id)),
      h('td', {}, nomePor(ubsRef, u.ubs_id)), h('td', {}, u.tem_senha ? 'sim' : '—'),
      h('td', {},
        h('button', { class: 'btn mini secundario', onclick: () => formUsuario(u) }, 'Editar'),
        h('button', {
          class: 'btn mini secundario', style: 'margin-left:.3rem',
          onclick: () => removerUsuario(u),
        }, 'Excluir')))));
    alvo.innerHTML = '';
    alvo.append(t);
  }

  async function removerUsuario(u) {
    if (!confirm(`Excluir o usuário "${u.nome}"?`)) return;
    try { await api.del(`/api/admin/usuarios/${u.id}`); carregar(); }
    catch (e) {
      aviso('Não foi possível excluir: o usuário possui atendimentos vinculados '
            + '(ou é o seu próprio usuário).');
    }
  }

  function formUsuario(u = null) {
    const nome = h('input', { type: 'text', value: u?.nome || '' });
    const email = h('input', { type: 'email', value: u?.email || '' });
    const matricula = h('input', { type: 'text', value: u?.matricula || '' });
    const papel = h('select', {}, ...['servidor', 'enfermeiro', 'atendente', 'admin'].map((p) => h('option', { value: p, selected: u?.papel === p ? '' : null }, p)));
    const funcao = h('select', {}, h('option', { value: '' }, '—'), ...funcoesRef.map((f) => h('option', { value: f.id, selected: u?.funcao_id === f.id ? '' : null }, f.nome)));
    const ubs = h('select', {}, h('option', { value: '' }, '—'), ...ubsRef.map((b) => h('option', { value: b.id, selected: u?.ubs_id === b.id ? '' : null }, b.nome)));
    const senha = h('input', { type: 'password', placeholder: u ? '(inalterada)' : 'senha (p/ login)' });
    const box = h('div', { style: 'background:#fff;border:1px solid var(--cinza-borda);border-radius:8px;padding:1rem;margin-bottom:1rem;max-width:640px' },
      h('h3', { class: 'titulo', style: 'margin-bottom:.6rem' }, u ? `Editar: ${u.nome}` : 'Novo usuário'),
      linha('Nome', nome), linha('E-mail', email), linha('Matrícula', matricula),
      linha('Papel', papel), linha('Função', funcao), linha('Unidade', ubs), linha('Senha', senha),
      h('div', { class: 'form-acoes' },
        h('button', {
          class: 'btn mini', onclick: async () => {
            const corpo = {
              nome: nome.value.trim(), email: email.value.trim(), matricula: matricula.value.trim(),
              papel: papel.value, funcao_id: Number(funcao.value) || null, ubs_id: Number(ubs.value) || null,
            };
            if (senha.value) corpo.senha = senha.value;
            try {
              if (u) await api.put(`/api/admin/usuarios/${u.id}`, corpo);
              else await api.post('/api/admin/usuarios', corpo);
              box.remove(); carregar();
            } catch (e) { aviso('Falha ao salvar usuário.'); }
          }
        }, 'Salvar'),
        h('button', { class: 'btn mini secundario', onclick: () => box.remove() }, 'Cancelar')));
    alvo.prepend(box);
  }

  carregar();
}

function linha(rot, campo) {
  return h('label', { class: 'campo-form' }, rot, campo);
}

// -------------------------------------------------------------- Funções
async function renderFuncoes() {
  main.innerHTML = '';
  main.append(h('h2', { class: 'titulo' }, 'Funções'));
  const nova = h('input', { type: 'text', placeholder: 'Nova função' });
  main.append(h('div', { class: 'admin-toolbar' }, h('label', {}, 'Nome', nova),
    h('button', {
      class: 'btn mini', onclick: async () => {
        if (!nova.value.trim()) return;
        try { await api.post('/api/admin/funcoes', { nome: nova.value.trim() }); nova.value = ''; carregar(); }
        catch (e) { aviso('Função já existe ou inválida.'); }
      }
    }, '+ Adicionar')));
  const alvo = h('div'); main.append(alvo);
  async function carregar() {
    const fs = await api.get('/api/admin/funcoes');
    const t = h('table', { class: 'grade' }, h('tr', {}, h('th', {}, 'Função'), h('th', {}, 'Status'), h('th', {}, '')));
    fs.forEach((f) => t.append(h('tr', {}, h('td', {}, f.nome), h('td', {}, pilula(f.ativo)),
      h('td', {}, h('button', { class: 'btn mini secundario', onclick: async () => { await api.put(`/api/admin/funcoes/${f.id}`, { ativo: !f.ativo }); carregar(); } }, f.ativo ? 'Desativar' : 'Ativar')))));
    alvo.innerHTML = ''; alvo.append(t);
  }
  carregar();
}

// -------------------------------------------------------------- Unidades
async function renderUnidades() {
  main.innerHTML = '';
  main.append(h('h2', { class: 'titulo' }, 'Unidades de saúde'));
  const nome = h('input', { type: 'text', placeholder: 'Nome da unidade' });
  const mun = h('input', { type: 'text', placeholder: 'Município', value: 'Poços de Caldas' });
  main.append(h('div', { class: 'admin-toolbar' }, h('label', {}, 'Nome', nome), h('label', {}, 'Município', mun),
    h('button', {
      class: 'btn mini', onclick: async () => {
        if (!nome.value.trim()) return;
        try { await api.post('/api/admin/ubs', { nome: nome.value.trim(), municipio: mun.value.trim() }); nome.value = ''; carregar(); }
        catch (e) { aviso('Falha ao criar unidade.'); }
      }
    }, '+ Adicionar')));
  const alvo = h('div'); main.append(alvo);
  async function carregar() {
    const us = await api.get('/api/admin/ubs');
    const t = h('table', { class: 'grade' }, h('tr', {}, h('th', {}, 'Unidade'), h('th', {}, 'Município')));
    us.forEach((u) => t.append(h('tr', {}, h('td', {}, u.nome), h('td', {}, u.municipio))));
    alvo.innerHTML = ''; alvo.append(t);
  }
  carregar();
}

// -------------------------------------------------------------- Intents
async function renderIntents() {
  main.innerHTML = '';
  main.append(h('h2', { class: 'titulo' }, 'Intents do bot (FAQ)'));
  main.append(h('button', { class: 'btn mini', onclick: () => form() }, '+ Novo intent'));
  const alvo = h('div', { style: 'margin-top:1rem' }); main.append(alvo);

  async function carregar() {
    const is = await api.get('/api/admin/intents');
    const t = h('table', { class: 'grade' }, h('tr', {}, ...['Intent', 'Chip', 'Status', 'Padrões', ''].map((c) => h('th', {}, c))));
    is.forEach((i) => t.append(h('tr', {},
      h('td', {}, i.intent), h('td', {}, i.chip_label || '—'), h('td', {}, pilula(i.ativo)),
      h('td', {}, String(i.padroes.split('\n').filter(Boolean).length) + ' frases'),
      h('td', {},
        h('button', { class: 'btn mini secundario', onclick: () => form(i) }, 'Editar'),
        h('button', { class: 'btn mini secundario', style: 'margin-left:.3rem', onclick: async () => { await api.put(`/api/admin/intents/${i.id}`, { ativo: !i.ativo }); carregar(); } }, i.ativo ? 'Desativar' : 'Ativar'),
        h('button', { class: 'btn mini secundario', style: 'margin-left:.3rem', onclick: async () => { if (confirm('Excluir intent?')) { await api.del(`/api/admin/intents/${i.id}`); carregar(); } } }, 'Excluir')))));
    alvo.innerHTML = ''; alvo.append(t);
  }

  function form(i = null) {
    const intent = h('input', { type: 'text', value: i?.intent || '', style: 'width:100%' });
    if (i) intent.disabled = true;
    const chip = h('input', { type: 'text', value: i?.chip_label || '', style: 'width:100%' });
    const padroes = h('textarea', { style: 'width:100%;min-height:90px', html: i?.padroes || '' });
    const resposta = h('textarea', { style: 'width:100%;min-height:70px', html: i?.resposta || '' });
    const box = h('div', { style: 'background:#fff;border:1px solid var(--cinza-borda);border-radius:8px;padding:1rem;margin-bottom:1rem;max-width:680px' },
      h('h3', { class: 'titulo', style: 'margin-bottom:.6rem' }, i ? `Editar: ${i.intent}` : 'Novo intent'),
      linha('Intent (id único)', intent), linha('Chip (opcional)', chip),
      linha('Padrões (uma frase por linha)', padroes), linha('Resposta', resposta),
      h('div', { class: 'form-acoes' },
        h('button', {
          class: 'btn mini', onclick: async () => {
            const corpo = { chip_label: chip.value.trim(), padroes: padroes.value, resposta: resposta.value };
            try {
              if (i) await api.put(`/api/admin/intents/${i.id}`, corpo);
              else await api.post('/api/admin/intents', { intent: intent.value.trim(), ...corpo });
              box.remove(); carregar();
            } catch (e) { aviso('Falha ao salvar intent (verifique campos/duplicidade).'); }
          }
        }, 'Salvar'),
        h('button', { class: 'btn mini secundario', onclick: () => box.remove() }, 'Cancelar')));
    alvo.prepend(box);
  }
  carregar();
}

// -------------------------------------------------------------- Tópicos críticos
async function renderTopicos() {
  main.innerHTML = '';
  main.append(h('h2', { class: 'titulo' }, 'Tópicos críticos (gatilho de handoff)'));
  const novo = h('input', { type: 'text', placeholder: 'Ex.: obito' });
  main.append(h('div', { class: 'admin-toolbar' }, h('label', {}, 'Termo', novo),
    h('button', {
      class: 'btn mini', onclick: async () => {
        if (!novo.value.trim()) return;
        try { await api.post('/api/admin/topicos', { termo: novo.value.trim() }); novo.value = ''; carregar(); }
        catch (e) { aviso('Termo já existe ou inválido.'); }
      }
    }, '+ Adicionar')));
  const alvo = h('div'); main.append(alvo);
  async function carregar() {
    const ts = await api.get('/api/admin/topicos');
    const t = h('table', { class: 'grade' }, h('tr', {}, h('th', {}, 'Termo'), h('th', {}, 'Status'), h('th', {}, '')));
    ts.forEach((x) => t.append(h('tr', {}, h('td', {}, x.termo), h('td', {}, pilula(x.ativo)),
      h('td', {},
        h('button', { class: 'btn mini secundario', onclick: async () => { await api.put(`/api/admin/topicos/${x.id}`, { ativo: !x.ativo }); carregar(); } }, x.ativo ? 'Desativar' : 'Ativar'),
        h('button', { class: 'btn mini secundario', style: 'margin-left:.3rem', onclick: async () => { if (confirm('Excluir termo?')) { await api.del(`/api/admin/topicos/${x.id}`); carregar(); } } }, 'Excluir')))));
    alvo.innerHTML = ''; alvo.append(t);
  }
  carregar();
}

// ------------------------------------------------------ Cabeçalho e logo
async function renderCabecalho() {
  main.innerHTML = '';
  main.append(h('h2', { class: 'titulo' }, 'Cabeçalho e logo'));
  main.append(h('p', { style: 'color:var(--cinza-texto);font-size:.86rem;margin-bottom:1rem;max-width:640px' },
    'Identidade exibida no topo de todas as telas. O subtítulo aparece no chat; os painéis internos mantêm o próprio rótulo ("Painel do Atendente", "Console técnico-administrativo").'));

  const cfg = await api.get('/api/admin/cabecalho');
  const titulo = h('input', { type: 'text', value: cfg.titulo || '', style: 'width:100%' });
  const subtitulo = h('input', { type: 'text', value: cfg.subtitulo || '', style: 'width:100%' });
  const orgao = h('input', { type: 'text', value: cfg.orgao || '', style: 'width:100%' });
  const cor = h('input', { type: 'color', value: cfg.cor_fundo || '#1351b4' });
  const arquivo = h('input', { type: 'file', accept: 'image/png,image/jpeg,image/gif,image/webp,image/svg+xml,image/x-icon' });
  let logoAtual = cfg.logo || null;

  const alvoPrevia = h('div');
  function previa() {
    alvoPrevia.innerHTML = '';
    const barra = h('div', { class: 'barra-gov' },
      h('span', {}, h('strong', {}, orgao.value), ' | Sistema ', titulo.value));
    const cab = h('div', { class: 'cabecalho' },
      h('div', { class: 'marca' },
        logoAtual ? h('img', { class: 'logo-icone', src: logoAtual, alt: '' })
                  : h('div', { class: 'logo-icone sem-imagem' }, '+'),
        h('div', {},
          h('div', { class: 'titulo' }, h('strong', {}, titulo.value)),
          h('div', { class: 'subtitulo' }, subtitulo.value))));
    cab.style.background = cor.value;
    alvoPrevia.append(h('div', { style: 'max-width:640px;border:1px solid var(--cinza-borda);border-radius:8px;overflow:hidden' }, barra, cab));
  }
  [titulo, subtitulo, orgao, cor].forEach((c) => c.addEventListener('input', previa));

  const statusLogo = h('span', { style: 'font-size:.8rem;color:var(--cinza-texto)' },
    logoAtual ? 'logo definido' : 'sem logo (usa o "+")');

  main.append(h('div', { style: 'background:#fff;border:1px solid var(--cinza-borda);border-radius:8px;padding:1rem;max-width:660px' },
    linha('Título', titulo),
    linha('Subtítulo (tela do chat)', subtitulo),
    linha('Órgão (barra superior)', orgao),
    linha('Cor de fundo do cabeçalho', cor),
    linha('Logo (PNG/JPG/GIF/WEBP/SVG/ICO, até 2 MB)', arquivo),
    h('div', { style: 'display:flex;gap:.5rem;align-items:center;margin-bottom:.8rem' },
      h('button', {
        class: 'btn mini secundario', onclick: async () => {
          if (!arquivo.files?.[0]) return aviso('Selecione um arquivo primeiro.');
          const fd = new FormData();
          fd.append('logo', arquivo.files[0]);
          const r = await fetch('/api/admin/cabecalho/logo', { method: 'POST', body: fd });
          const j = await r.json().catch(() => ({}));
          if (!r.ok) return aviso(j.erro || 'Falha no upload.');
          logoAtual = j.logo;
          statusLogo.textContent = 'logo enviado';
          previa();
        }
      }, 'Enviar logo'),
      h('button', {
        class: 'btn mini secundario', onclick: () => {
          logoAtual = null; arquivo.value = '';
          statusLogo.textContent = 'sem logo (usa o "+")';
          previa();
        }
      }, 'Remover logo'),
      statusLogo),
    h('button', {
      class: 'btn mini', onclick: async () => {
        try {
          await api.put('/api/admin/cabecalho', {
            titulo: titulo.value, subtitulo: subtitulo.value, orgao: orgao.value,
            cor_fundo: cor.value, logo: logoAtual,
          });
          aviso('Cabeçalho salvo. Recarregue as telas para ver a mudança.');
        } catch (e) { aviso('Falha ao salvar o cabeçalho.'); }
      }
    }, 'Salvar')));

  main.append(h('h3', { class: 'titulo', style: 'margin:1.2rem 0 .5rem' }, 'Pré-visualização'));
  main.append(alvoPrevia);
  previa();
}

// ------------------------------------------------- Mensagem de encerramento
const EMOJIS = ['😊', '🙏', '💙', '🌟', '🩺', '✅', '👏', '🌻', '🤝', '💚'];

async function renderEncerramento() {
  main.innerHTML = '';
  main.append(h('h2', { class: 'titulo' }, 'Mensagem de encerramento'));
  main.append(h('p', { style: 'color:var(--cinza-texto);font-size:.86rem;margin-bottom:1rem;max-width:640px' },
    'Exibida ao profissional depois que ele responde a pesquisa de satisfação. Aceita emojis, imagem e cores personalizadas.'));

  const cfg = await api.get('/api/admin/encerramento');

  const texto = h('textarea', { style: 'width:100%;min-height:90px' });
  texto.value = cfg.texto || '';
  const corFundo = h('input', { type: 'color', value: cfg.cor_fundo || '#e8f0fe' });
  const corTexto = h('input', { type: 'color', value: cfg.cor_texto || '#071d41' });
  const arquivo = h('input', { type: 'file', accept: 'image/png,image/jpeg,image/gif,image/webp' });
  const comoFundo = h('input', { type: 'checkbox' });
  comoFundo.checked = Boolean(cfg.imagem_como_fundo);
  let imagemAtual = cfg.imagem || null;

  // barra de emojis: insere no ponto do cursor
  const barra = h('div', { style: 'display:flex;flex-wrap:wrap;gap:.3rem;margin:.4rem 0' },
    ...EMOJIS.map((e) => h('button', {
      class: 'btn mini secundario', type: 'button', title: `Inserir ${e}`,
      onclick: () => {
        const i = texto.selectionStart ?? texto.value.length;
        texto.value = texto.value.slice(0, i) + e + texto.value.slice(texto.selectionEnd ?? i);
        texto.focus();
        texto.selectionStart = texto.selectionEnd = i + e.length;
        previa();
      },
    }, e)));

  const alvoPrevia = h('div');
  function previa() {
    alvoPrevia.innerHTML = '';
    const card = h('div', { class: 'cartao-encerramento' });
    const usaFundo = imagemAtual && comoFundo.checked;
    if (usaFundo) {
      card.classList.add('com-fundo');
      card.style.backgroundImage = `url("${imagemAtual}")`;
    } else {
      card.style.background = corFundo.value;
      if (imagemAtual) card.append(h('img', { class: 'ilustracao', src: imagemAtual, alt: '' }));
    }
    const t = h('div', { class: 'texto' }, texto.value);
    if (!usaFundo) t.style.color = corTexto.value;
    card.append(t);
    alvoPrevia.append(card);
  }
  [texto, corFundo, corTexto].forEach((c) => c.addEventListener('input', previa));
  comoFundo.addEventListener('change', previa);

  const statusImg = h('span', { style: 'font-size:.8rem;color:var(--cinza-texto)' },
    imagemAtual ? 'imagem definida' : 'sem imagem');

  const form = h('div', { style: 'background:#fff;border:1px solid var(--cinza-borda);border-radius:8px;padding:1rem;max-width:660px' },
    linha('Texto da mensagem (aceita emojis)', texto), barra,
    h('div', { style: 'display:flex;gap:1rem;flex-wrap:wrap' },
      linha('Cor de fundo', corFundo), linha('Cor do texto', corTexto)),
    linha('Imagem (PNG/JPG/GIF/WEBP, até 2 MB)', arquivo),
    h('label', { style: 'display:flex;align-items:center;gap:.4rem;font-size:.82rem;font-weight:600;color:var(--azul-escuro);margin-bottom:.6rem' },
      comoFundo, 'Usar a imagem como plano de fundo'),
    h('div', { style: 'display:flex;gap:.5rem;align-items:center;margin-bottom:.8rem' },
      h('button', {
        class: 'btn mini secundario', onclick: async () => {
          if (!arquivo.files?.[0]) return aviso('Selecione um arquivo primeiro.');
          const fd = new FormData();
          fd.append('imagem', arquivo.files[0]);
          const r = await fetch('/api/admin/encerramento/imagem', { method: 'POST', body: fd });
          const j = await r.json().catch(() => ({}));
          if (!r.ok) return aviso(j.erro || 'Falha no upload.');
          imagemAtual = j.imagem;
          statusImg.textContent = 'imagem enviada';
          previa();
        }
      }, 'Enviar imagem'),
      h('button', {
        class: 'btn mini secundario', onclick: () => {
          imagemAtual = null; arquivo.value = '';
          statusImg.textContent = 'sem imagem';
          previa();
        }
      }, 'Remover imagem'),
      statusImg),
    h('button', {
      class: 'btn mini', onclick: async () => {
        try {
          await api.put('/api/admin/encerramento', {
            texto: texto.value, cor_fundo: corFundo.value, cor_texto: corTexto.value,
            imagem: imagemAtual, imagem_como_fundo: comoFundo.checked,
          });
          aviso('Mensagem de encerramento salva.');
        } catch (e) { aviso('Falha ao salvar (o texto é obrigatório).'); }
      }
    }, 'Salvar'));

  main.append(form);
  main.append(h('h3', { class: 'titulo', style: 'margin:1.2rem 0 .5rem' }, 'Pré-visualização'));
  main.append(alvoPrevia);
  previa();
}

// -------------------------------------------------------------- Atendentes
async function renderAtendentes() {
  main.innerHTML = '';
  await carregarRefs();   // ubsRef para o combo de unidade
  main.append(h('h2', { class: 'titulo' }, 'Atendentes'));
  main.append(h('div', { class: 'admin-toolbar' },
    h('button', { class: 'btn mini', onclick: () => form() }, '+ Novo atendente')));
  const alvo = h('div'); main.append(alvo);

  async function carregar() {
    const as = await api.get('/api/admin/atendentes');
    const t = h('table', { class: 'grade' },
      h('tr', {}, ...['Nome', 'E-mail', 'Matrícula', 'Unidade', 'Login', 'Disponibilidade', ''].map((c) => h('th', {}, c))));
    if (!as.length) t.append(h('tr', {}, h('td', { colspan: '7' }, 'Nenhum atendente cadastrado.')));
    as.forEach((a) => {
      const sel = h('select', {}, ...['disponivel', 'ocupado', 'ausente'].map((s) => h('option', { value: s, selected: a.status === s ? '' : null }, s)));
      sel.addEventListener('change', async () => {
        try { await api.post(`/api/admin/atendentes/${a.id}/status`, { status: sel.value }); }
        catch (e) { aviso('Falha ao alterar disponibilidade.'); }
      });
      t.append(h('tr', {},
        h('td', {}, a.nome), h('td', {}, a.email || '—'), h('td', {}, a.matricula || '—'),
        h('td', {}, a.ubs_nome || '—'), h('td', {}, a.tem_senha ? 'sim' : '—'),
        h('td', {}, sel),
        h('td', {},
          h('button', { class: 'btn mini secundario', onclick: () => form(a) }, 'Editar'),
          h('button', {
            class: 'btn mini secundario', style: 'margin-left:.3rem',
            onclick: () => remover(a),
          }, 'Excluir'))));
    });
    alvo.innerHTML = ''; alvo.append(t);
  }

  async function remover(a) {
    if (!confirm(`Excluir o atendente "${a.nome}"?`)) return;
    try { await api.del(`/api/admin/atendentes/${a.id}`); carregar(); }
    catch (e) {
      // 409: possui atendimentos vinculados
      aviso('Não foi possível excluir: o atendente possui atendimentos vinculados. '
            + 'Deixe-o como "ausente" em vez de excluir.');
    }
  }

  function form(a = null) {
    const nome = h('input', { type: 'text', value: a?.nome || '' });
    const email = h('input', { type: 'email', value: a?.email || '' });
    const matricula = h('input', { type: 'text', value: a?.matricula || '' });
    const ubs = h('select', {}, h('option', { value: '' }, '—'),
      ...ubsRef.map((b) => h('option', { value: b.id, selected: a?.ubs_id === b.id ? '' : null }, b.nome)));
    const senha = h('input', { type: 'password', placeholder: a ? '(inalterada)' : 'senha p/ login' });
    const box = h('div', { style: 'background:#fff;border:1px solid var(--cinza-borda);border-radius:8px;padding:1rem;margin-bottom:1rem;max-width:640px' },
      h('h3', { class: 'titulo', style: 'margin-bottom:.6rem' }, a ? `Editar: ${a.nome}` : 'Novo atendente'),
      linha('Nome', nome), linha('E-mail', email), linha('Matrícula', matricula),
      linha('Unidade', ubs), linha('Senha', senha),
      h('div', { class: 'form-acoes' },
        h('button', {
          class: 'btn mini', onclick: async () => {
            const corpo = {
              nome: nome.value.trim(), email: email.value.trim(),
              matricula: matricula.value.trim(), ubs_id: Number(ubs.value) || null,
            };
            if (senha.value) corpo.senha = senha.value;
            try {
              if (a) await api.put(`/api/admin/atendentes/${a.id}`, corpo);
              else await api.post('/api/admin/atendentes', corpo);
              box.remove(); carregar();
            } catch (e) { aviso('Falha ao salvar (nome obrigatório; matrícula não pode repetir).'); }
          }
        }, 'Salvar'),
        h('button', { class: 'btn mini secundario', onclick: () => box.remove() }, 'Cancelar')));
    alvo.prepend(box);
  }

  carregar();
}

// ------------------------------------------------- Servidor de e-mail (SMTP)
async function renderEmail() {
  main.innerHTML = '';
  main.append(h('h2', { class: 'titulo' }, 'Servidor de e-mail'));
  const cfg = await api.get('/api/admin/email');

  const host = h('input', { type: 'text', value: cfg.host || '', style: 'width:100%', placeholder: 'mail.exemplo.gov.br' });
  const porta = h('input', { type: 'number', value: cfg.porta || 587, style: 'width:100%' });
  const email = h('input', { type: 'email', value: cfg.email || '', style: 'width:100%', placeholder: 'no-reply@exemplo.gov.br' });
  const senha = h('input', { type: 'password', style: 'width:100%', placeholder: cfg.tem_senha ? '•••••••• (definida)' : 'senha / app password', autocomplete: 'new-password' });
  const status = h('span', { style: 'font-size:.82rem;margin-left:.6rem' });

  const bloco = (titulo, ...campos) => h('div', { style: 'background:#fff;border:1px solid var(--cinza-borda);border-radius:8px;padding:1rem;max-width:680px;margin-bottom:1rem' },
    h('h3', { class: 'titulo', style: 'margin-bottom:.6rem;font-size:1rem' }, titulo), ...campos);

  main.append(bloco('Servidor SMTP',
    h('div', { style: 'display:flex;gap:1rem;flex-wrap:wrap' },
      h('div', { style: 'flex:2;min-width:220px' }, linha('Host do servidor', host)),
      h('div', { style: 'flex:1;min-width:110px' }, linha('Porta', porta))),
    h('div', { style: 'display:flex;gap:1rem;flex-wrap:wrap' },
      h('div', { style: 'flex:1;min-width:220px' }, linha('E-mail de envio', email)),
      h('div', { style: 'flex:1;min-width:220px' }, linha('Senha / App Password', senha))),
    h('div', { style: 'display:flex;align-items:center' },
      h('button', {
        class: 'btn mini', onclick: async () => {
          status.textContent = 'Testando...'; status.style.color = 'var(--cinza-texto)';
          try {
            const r = await api.post('/api/admin/email/testar', {
              host: host.value.trim(), porta: Number(porta.value) || 587,
              email: email.value.trim(), senha: senha.value,
            });
            status.textContent = r.mensagem;
            status.style.color = r.ok ? 'var(--verde)' : '#b00';
          } catch (e) { status.textContent = 'Erro ao testar.'; status.style.color = '#b00'; }
        }
      }, 'Testar Conexão'), status)));

  const assunto = h('input', { type: 'text', value: cfg.assunto || '', style: 'width:100%' });
  const corpo = h('textarea', { style: 'width:100%;min-height:150px' });
  corpo.value = cfg.corpo || '';
  main.append(bloco('Modelo de recuperação',
    linha('Assunto do e-mail', assunto),
    linha('Corpo da mensagem', corpo),
    h('p', { style: 'font-size:.8rem;color:var(--cinza-texto)' },
      'Use ', h('code', {}, '{{senha_temp}}'), ' para a senha gerada e ',
      h('code', {}, '{{username}}'), ' para o nome do usuário.')));

  main.append(h('button', {
    class: 'btn', onclick: async () => {
      try {
        await api.put('/api/admin/email', {
          host: host.value.trim(), porta: Number(porta.value) || 587,
          email: email.value.trim(), senha: senha.value || undefined,
          assunto: assunto.value, corpo: corpo.value,
        });
        senha.value = '';
        aviso('Configurações salvas.');
      } catch (e) { aviso('Falha ao salvar (assunto e corpo são obrigatórios).'); }
    }
  }, 'Salvar Configurações'));
}

// -------------------------------------------------------------- init
document.getElementById('btn-sair').addEventListener('click', async (ev) => {
  ev.preventDefault();
  await api.post('/api/logout');
  location.href = '/login';
});

(async function init() {
  try {
    const s = await api.get('/api/sessao');
    document.getElementById('admin-nome').textContent = s.nome || 'Administrador';
    renderRelatorios();
  } catch (e) {
    location.href = '/login?next=/admin';
  }
})();
