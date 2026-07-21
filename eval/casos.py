"""Conjunto rotulado para avaliação do RulesEngine (ADR-001, Decisão A).

Frases derivadas do corpus real "Alô Saúde e Apoiadoras APS", **de-identificadas**
(paráfrases sem nome de paciente, CPF, CNS, telefone ou endereço real).

IMPORTANTE — conjunto HELD-OUT: estas frases foram redigidas com vocabulário e
estrutura **deliberadamente diferentes** dos `padroes` cadastrados em
db/seed_intents.sql (ex.: "imunização" vs. "vacina", "na veia" vs.
"intravenoso", "requisição" vs. "pedido", "equipe de saúde da família" vs.
"ESF"). O objetivo é medir a **generalização real** do matching por trigramas,
não a memorização dos padrões. Espera-se acurácia menor que a do conjunto de
autoria — e é isso que torna a medição honesta.

Cada caso mapeia um enunciado para a intent esperada. `None` = fora de escopo:
o bot deveria cair em fallback/handoff, não responder com confiança.
"""

# (texto_do_usuario, intent_esperada)  — intent_esperada=None => fora de escopo
CASOS: list[tuple[str, str | None]] = [

    # ---------- localizar_esf_por_endereco ----------
    ("Essa família mudou de casa, para qual posto ela deve ir agora?", "localizar_esf_por_endereco"),
    ("Preciso saber qual unidade cobre a área do Jardim dos Estados", "localizar_esf_por_endereco"),
    ("O paciente mora na zona sul, qual equipe de saúde da família responde por ele?", "localizar_esf_por_endereco"),
    ("Onde essa pessoa é atendida morando no centro da cidade?", "localizar_esf_por_endereco"),

    # ---------- lotacao_paciente ----------
    ("Esse usuário está cadastrado em qual postinho?", "lotacao_paciente"),
    ("Quero saber onde essa senhora acompanha a saúde dela", "lotacao_paciente"),
    ("A paciente veio de outra cidade, ainda não sei a lotação dela", "lotacao_paciente"),

    # ---------- especialista_atende_sus ----------
    ("Esse ortopedista pega paciente pelo SUS?", "especialista_atende_sus"),
    ("O cardiologista da Santa Casa faz atendimento pela rede pública?", "especialista_atende_sus"),
    ("A dermatologista está atendendo gratuito pela prefeitura?", "especialista_atende_sus"),

    # ---------- agendamento_especialista ----------
    ("Como faço para conseguir uma consulta com endocrinologista?", "agendamento_especialista"),
    ("A marcação de neurologista já está aberta?", "agendamento_especialista"),
    ("Quero encaixar o paciente numa vaga de oftalmo", "agendamento_especialista"),

    # ---------- sala_vacina_campanha ----------
    ("Ainda dá pra tomar a dose contra a influenza?", "sala_vacina_campanha"),
    ("Que horas abre a sala de imunização?", "sala_vacina_campanha"),
    ("Qual posto está aplicando a vacina da gripe?", "sala_vacina_campanha"),

    # ---------- aplicacao_medicamento_psf ----------
    ("Dá pra tomar a medicação na veia na unidade básica?", "aplicacao_medicamento_psf"),
    ("O posto faz soro e medicação endovenosa?", "aplicacao_medicamento_psf"),
    ("Tem que ter médico presente pra aplicar a injeção no postinho?", "aplicacao_medicamento_psf"),

    # ---------- pedido_exame ----------
    ("Como o paciente consegue a requisição do ultrassom?", "pedido_exame"),
    ("A unidade pode emitir a guia do exame de sangue?", "pedido_exame"),

    # ---------- visita_medica_domiciliar ----------
    ("O médico pode ir ver o paciente acamado na casa dele?", "visita_medica_domiciliar"),
    ("Como pedir atendimento em domicílio para um idoso que não sai de casa?", "visita_medica_domiciliar"),

    # ---------- notificacao_compulsoria ----------
    ("Tenho um caso suspeito de sarampo, para quem eu comunico?", "notificacao_compulsoria"),
    ("Qual o prazo pra registrar um agravo na vigilância epidemiológica?", "notificacao_compulsoria"),

    # ---------- encaminhamento_urgente ----------
    ("Tenho um paciente que precisa ser encaminhado com pressa", "encaminhamento_urgente"),

    # ---------- solicitacao_insumos ----------
    ("Estamos sem seringa na unidade, como faço pra repor?", "solicitacao_insumos"),
    ("Faltou material de curativo aqui, preciso pedir mais", "solicitacao_insumos"),

    # ---------- suporte_esus ----------
    ("Não estou conseguindo logar no PEC", "suporte_esus"),
    ("O prontuário eletrônico caiu, não abre de jeito nenhum", "suporte_esus"),

    # ---------- falar_com_atendente ----------
    ("Pode me passar para uma pessoa do time?", "falar_com_atendente"),
    ("Prefiro conversar com alguém de verdade", "falar_com_atendente"),

    # ---------- horario_atendimento ----------
    ("Vocês funcionam no sábado?", "horario_atendimento"),
    ("Até que horas posso mandar mensagem por aqui?", "horario_atendimento"),

    # ============ Fora de escopo (esperado None) ============
    # Saudações e encerramentos (muito comuns no corpus)
    ("Bom dia, tudo bem?", None),
    ("Boa tarde, meninas!", None),
    ("Muito obrigada!", None),
    ("Ok, obrigada, tá certo então", None),
    ("Pode deixar assim mesmo", None),
    ("Sem problemas!", None),

    # Coordenação interna do grupo (não é dúvida que o bot responda).
    # "ESF" aparece de propósito — testa falso positivo com localizar_esf_por_endereco.
    ("Você continua apoiadora do ESF São José?", None),
    ("Alguma de vocês está com a Regional Sul?", None),
    ("Tomei a liberdade de mudar o nome do grupo", None),
    ("Vou verificar na unidade e já retorno", None),

    # Totalmente fora do domínio
    ("Qual a previsão do tempo para amanhã?", None),
    ("Você recebeu meu e-mail sobre a reunião de ontem?", None),
]
