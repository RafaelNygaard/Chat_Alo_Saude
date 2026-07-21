-- ADR-001 — Treinamento do motor A1 (faq_intents)
-- Intents derivados do corpus real "Alô Saúde e Apoiadoras APS" (item de ação 148 do schema).
--
-- DE-IDENTIFICAÇÃO (obrigatória — ADR-001, itens 1,2,4): este arquivo contém
-- APENAS formulações genéricas das dúvidas. Nenhum nome de paciente, CPF, CNS,
-- telefone ou endereço real do corpus foi incluído. Os `padroes` são exemplos
-- de frase para o matching por trigramas do RulesEngine, não dados pessoais.
--
-- Idempotente: upsert por `intent` (UNIQUE). Rodar depois de schema.sql.

BEGIN;

INSERT INTO faq_intents (intent, padroes, resposta, chip_label, ativo) VALUES

-- ================= Intents novos, derivados do uso real =================

( 'localizar_esf_por_endereco',
  E'qual e o esf dessa rua e bairro\nqual ubs atende minha regiao\nqual esf atende o bairro\nqual e o esf desse endereco\nqual posto atende esse endereco\nqual unidade de saude atende essa rua',
  'Para localizar o ESF/UBS de referência, informe o endereço completo do paciente (rua, número e bairro). Consulto o território de abrangência e retorno a unidade responsável.',
  'ESF por endereço', TRUE ),

( 'lotacao_paciente',
  E'qual o postinho da paciente\nonde a paciente faz acompanhamento\nqual a unidade de referencia do paciente\nqual o esf de cadastro do paciente\npaciente sem lotacao definida',
  'Para confirmar a unidade de cadastro/lotação do paciente, informe o endereço atual. Casos de mudança de município ou pendência de lotação podem exigir análise da equipe — nesse caso registro a demanda para retorno.',
  NULL, TRUE ),

( 'especialista_atende_sus',
  E'esse especialista atende pelo sus\no medico atende pela rede sus\no doutor atende pelo sus\npsiquiatra atende pelo sus\ninfectologista atende pelo sus',
  'Para verificar se um profissional atende pelo SUS, informe o nome e a especialidade. A confirmação é feita com a Central/Policlínica, pois a agenda pode mudar; retorno assim que confirmado.',
  'Atende pelo SUS?', TRUE ),

( 'agendamento_especialista',
  E'como agendar especialista\nos esfs estao agendando\nagendamento de nefro pediatra\ncentral de marcacao de consultas\ncomo marcar consulta com especialista',
  'O agendamento de especialidades é feito pela Central de Marcação da Secretaria. Informe a especialidade e o CNS do paciente para orientar o encaminhamento correto.',
  'Agendar especialista', TRUE ),

( 'sala_vacina_campanha',
  E'campanha de vacinacao da gripe\nainda esta tendo campanha de vacina\ntem sala de vacina\nonde tomar vacina da gripe\nqual o horario da sala de vacina\nqual unidade tem sala de vacina',
  'Sobre vacinação: informe a vacina desejada e o bairro/endereço do paciente. Nem toda unidade possui sala de vacina; oriento a unidade mais próxima com o serviço e o horário de funcionamento.',
  'Vacinação', TRUE ),

( 'aplicacao_medicamento_psf',
  E'infusoes de medicamento sao feitas no psf\naplicar remedio intravenoso no psf\naplicacao de medicacao injetavel no psf\no psf aplica medicamento com receita\nprecisa de medico para aplicar medicamento',
  'Aplicações e infusões podem ser feitas no PSF quando não exigem ambiente hospitalar e conforme prescrição. Informe o medicamento e a via de administração para confirmação com a equipe da unidade.',
  NULL, TRUE ),

( 'pedido_exame',
  E'onde pego o pedido do exame\nliberacao de exame\no psf faz pedido de exame\nnao liberaram o pedido do exame\ncomo conseguir pedido de exame',
  'Sobre solicitação/liberação de exames, informe o exame e a unidade onde o paciente é acompanhado. Verifico com a unidade a orientação vigente e retorno.',
  NULL, TRUE ),

( 'visita_medica_domiciliar',
  E'solicitacao de visita medica\nvisita medica do psf\nagendar visita medica em casa\nvisita domiciliar do medico\npaciente precisa de visita medica',
  'As visitas médicas do PSF são programadas pela equipe. Informe o CNS do paciente e o motivo. Em eventualidade de urgência, oriente procurar a unidade de urgência de referência (UPA/pronto atendimento).',
  NULL, TRUE ),

-- ================= Intents originais (mantidos/ajustados) =================

( 'falar_com_atendente',
  E'quero falar com atendente\nfalar com humano\ntransferir para agente\npreciso de um atendente',
  'Certo, vou transferir você para um atendente humano.',
  NULL, TRUE ),

( 'encaminhamento_urgente',
  E'encaminhamento urgente\npreciso encaminhar paciente com urgencia\ncomo faco encaminhamento urgente',
  'Para encaminhamento urgente, informe o CNS do paciente e descreva brevemente o quadro clínico. Se for suspeita de agravo de notificação, use também o chip "Notificação compulsória".',
  'Encaminhamento urgente', TRUE ),

-- padroes ampliados: no corpus a notificação passa pela VEPI (vigilância epidemiológica)
( 'notificacao_compulsoria',
  E'notificacao compulsoria\nprazo para notificar dengue\ncomo notificar no sinan\nverificar com a vepi sobre a notificacao\nnotificacao de agravo\nprecisa notificar esse caso',
  'Doenças de notificação compulsória devem ser registradas no SINAN; a VEPI (vigilância epidemiológica) orienta os casos. O prazo padrão é de 24h para agravos imediatos e 7 dias para os demais. Precisa de ajuda com um agravo específico?',
  'Notificação compulsória', TRUE ),

( 'solicitacao_insumos',
  E'solicitar vacinas\nabastecimento de insumos\npedido de material\nfalta de vacina influenza',
  'Solicitações de abastecimento são registradas com protocolo e encaminhadas à central. Informe o insumo e a quantidade necessária.',
  'Solicitação de insumos', TRUE ),

( 'suporte_esus',
  E'acesso bloqueado e-sus\nnao consigo entrar no e-sus\nproblema no e-sus',
  'Para problemas de acesso ao e-SUS, informe sua matrícula e a mensagem de erro exibida. Vou registrar o chamado de suporte.',
  NULL, TRUE ),

( 'horario_atendimento',
  E'qual o horario de atendimento\nate que horas funciona o alo saude',
  'O Alô Saúde atende em dias úteis, das 7h às 19h. Fora desse horário, o assistente virtual registra sua solicitação para retorno no próximo expediente.',
  NULL, TRUE )

ON CONFLICT (intent) DO UPDATE SET
    padroes    = EXCLUDED.padroes,
    resposta   = EXCLUDED.resposta,
    chip_label = EXCLUDED.chip_label,
    ativo      = TRUE;

COMMIT;
