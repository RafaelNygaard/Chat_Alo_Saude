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
  servidores: renderServidores,
  funcoes: renderFuncoes,
  unidades: renderUnidades,
  intents: renderIntents,
  topicos: renderTopicos,
  atendentes: renderAtendentes,
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
    alvo.append(cards);
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
      h('td', {}, h('button', { class: 'btn mini secundario', onclick: () => formUsuario(u) }, 'Editar')))));
    alvo.innerHTML = '';
    alvo.append(t);
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
      h('button', { class: 'btn mini secundario', style: 'margin-left:.5rem', onclick: () => box.remove() }, 'Cancelar'));
    alvo.prepend(box);
  }

  carregar();
}

function linha(rot, campo) {
  return h('label', { style: 'display:flex;flex-direction:column;font-size:.78rem;font-weight:600;color:var(--azul-escuro);gap:.2rem;margin-bottom:.5rem' }, rot, campo);
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
      h('button', { class: 'btn mini secundario', style: 'margin-left:.5rem', onclick: () => box.remove() }, 'Cancelar'));
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

// -------------------------------------------------------------- Atendentes
async function renderAtendentes() {
  main.innerHTML = '';
  main.append(h('h2', { class: 'titulo' }, 'Atendentes'));
  const alvo = h('div'); main.append(alvo);
  async function carregar() {
    const as = await api.get('/api/admin/atendentes');
    const t = h('table', { class: 'grade' }, h('tr', {}, ...['Nome', 'E-mail', 'Disponibilidade', ''].map((c) => h('th', {}, c))));
    if (!as.length) t.append(h('tr', {}, h('td', { colspan: '4' }, 'Nenhum atendente cadastrado (crie em Servidores com papel "atendente").')));
    as.forEach((a) => {
      const sel = h('select', {}, ...['disponivel', 'ocupado', 'ausente'].map((s) => h('option', { value: s, selected: a.status === s ? '' : null }, s)));
      sel.addEventListener('change', async () => { await api.post(`/api/admin/atendentes/${a.id}/status`, { status: sel.value }); });
      t.append(h('tr', {}, h('td', {}, a.nome), h('td', {}, a.email || '—'), h('td', {}, sel), h('td', {})));
    });
    alvo.innerHTML = ''; alvo.append(t);
  }
  carregar();
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
