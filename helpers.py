"""
Utilitários de Formatação de Moeda, Datas e Layout de Mensagens.
"""

import datetime
from typing import List, Dict, Tuple, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}


def get_current_mes_ano() -> str:
    """Retorna o mês/ano atual no formato YYYY-MM."""
    now = datetime.datetime.now()
    return f"{now.year}-{now.month:02d}"


def format_mes_extenso(mes_ano: str) -> str:
    """Converte '2026-10' em 'Outubro / 2026'."""
    try:
        ano, mes = map(int, mes_ano.split("-"))
        nome_mes = MESES_PT.get(mes, f"Mês {mes}")
        return f"{nome_mes.upper()} / {ano}"
    except Exception:
        return mes_ano


def get_mes_vizinho(mes_ano: str, delta_meses: int) -> str:
    """Calcula o mês anterior (-1) ou seguinte (+1)."""
    ano, mes = map(int, mes_ano.split("-"))
    mes += delta_meses
    while mes > 12:
        mes -= 12
        ano += 1
    while mes < 1:
        mes += 12
        ano -= 1
    return f"{ano}-{mes:02d}"


def format_moeda(valor: float) -> str:
    """Formata float como moeda brasileira (ex: 1500.50 -> R$ 1.500,50)."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


SHORT_NAMES = {
    "LANCHE/ALMOÇO LEVY": "🥪 Lanche Levy",
    "LANCHE GABRIEL": "🥪 Lanche Gabriel",
    "COMBUSTIVEL": "⛽ Combustível",
    "MERCADO CASAS": "🛒 Mercado",
    "ALMOÇO": "🍽️ Almoço",
    "AGUA": "💧 Água",
    "ALUGUEL": "🏠 Aluguel",
    "FAXINA": "🧹 Faxina",
    "DIZIMO/OFERTA": "⛪ Dízimo/Oferta",
    "CELULARES": "📱 Celulares",
    "MESADAS": "🪙 Mesadas",
    "ENTRETENIMENTO": "🎟️ Entretenimento",
    "CONDUÇÃO LEVY": "🚌 Condução Levy",
    "BANCA GABRIEL": "📰 Banca Gabriel",
    "FUTEBOL": "⚽ Futebol",
    "NATAÇÃO": "🏊 Natação",
    "ACORDO CONDOMINIO": "🏢 Condomínio",
    "CONS 01 (VI) HS100": "📑 Consórcio 01",
    "CONS 02 (VI) HS200": "📑 Consórcio 02",
    "CONS 03 (VI) Rodob100": "📑 Consórcio 03",
    "CONS 04 (RO) HS100": "📑 Consórcio 04",
    "CONS 05 (RO) HS100": "📑 Consórcio 05",
    "CONS 06 (CILA) HS100": "📑 Consórcio 06",
    "EMBASA": "🚰 Embasa",
    "ESCOLA LEVY": "🏫 Escola Levy",
    "TEL/INTERN": "🌐 Internet/Tel",
    "LIGHT": "💡 Light (Luz)",
    # Cartões
    "CT C6": "💳 C6",
    "CT RecargaPay vi": "💳 RecargaPay",
    "CT MERC PAGO": "💳 Merc Pago",
    "CT INTER": "💳 Inter",
    "CT NUBANK": "💳 Nubank",
    "CT BANESE": "💳 Banese",
    "CT CAIXA": "💳 Caixa",
    "CT BRBCARD": "💳 BRB",
    "CT CLICK": "💳 Click",
    "CT PICPAY": "💳 PicPay",
    "CT BRADESCO": "💳 Bradesco",
}


def get_cat_icon(categoria: str, descricao: str = "") -> str:
    """Retorna um emoji representativo para a categoria ou descrição."""
    cat = (categoria or "").lower()
    desc = (descricao or "").upper()
    if "cart" in cat or desc.startswith("CT ") or "CARTÃO" in desc or "CARTAO" in desc:
        return "💳"
    if "fix" in cat:
        return "🔒"
    return "📄"


def get_short_name(descricao: str) -> str:
    """Retorna o rótulo encurtado e amigável para botões lado a lado."""
    desc = descricao.strip()
    if desc in SHORT_NAMES:
        return SHORT_NAMES[desc]
    for k, v in SHORT_NAMES.items():
        if k.lower() == desc.lower():
            return v
    if desc.startswith("CT "):
        return f"💳 {desc.replace('CT ', '')[:10]}"
    return desc[:14]


def render_contas_message(
    contas: List[Dict[str, Any]],
    totais: Dict[str, Any],
    mes_ano: str,
    filtro: str = "cartoes",
    pagina: int = 0,
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Renderiza o checklist de CARTÕES / CONTAS A PAGAR:
    - Textos simplificados e botões LADO A LADO (2 por linha).
    - Evita múltiplas páginas.
    """
    mes_str = format_mes_extenso(mes_ano)
    pendentes = [c for c in contas if c["pago"] == 0]
    pagas = [c for c in contas if c["pago"] == 1]

    linhas = []
    linhas.append(f"📅 <b>FATURAS E CARTÕES — {mes_str}</b>")
    linhas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if not contas:
        linhas.append("\n<i>Nenhuma fatura cadastrada para este mês.</i>")
    else:
        # PENDENTES
        linhas.append(f"<b>⏳ A PAGAR ({len(pendentes)}):</b>")
        if not pendentes:
            linhas.append("<i>🎉 Todas as faturas deste mês foram pagas!</i>")
        else:
            for i, c in enumerate(pendentes, 1):
                dia = f"Dia {c['dia_vencimento']:02d}"
                valor = format_moeda(c["valor"])
                rec = " 🔁" if c.get("recorrente") else ""
                linhas.append(f"{i}. ⬜ <b>[{dia}]</b> {c['descricao']} — <code>{valor}</code>{rec}")

        # PAGAS
        if pagas:
            linhas.append("")
            linhas.append(f"<b>✅ PAGAS ({len(pagas)}):</b>")
            for j, c in enumerate(pagas, len(pendentes) + 1):
                dia = f"Dia {c['dia_vencimento']:02d}"
                valor = format_moeda(c["valor"])
                linhas.append(f"{j}. ✅ <s>[{dia}] {c['descricao']} — {valor}</s>")

    linhas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    linhas.append(f"💳 <b>Total Cartões:</b> {format_moeda(totais.get('total_cartoes', 0.0))}")
    linhas.append(f"🔒 <b>Total Fixos/Variáveis (Lançado):</b> {format_moeda(totais.get('total_fixos_lancado', 0.0))} <i>(Ref: {format_moeda(totais.get('total_fixos_referencia', 0.0))})</i>")
    linhas.append(f"💰 <b>Total Comprometido no Mês:</b> {format_moeda(totais.get('total_geral_comprometido', 0.0))}")

    texto_final = "\n".join(linhas)

    # BOTÕES LADO A LADO (2 colunas)
    botoes: List[List[InlineKeyboardButton]] = []

    # Checkboxes lado a lado para cada fatura pendente
    pend_chunk = []
    for c in pendentes:
        s_nome = get_short_name(c["descricao"])
        rotulo = f"⬜ {s_nome} ({format_moeda(c['valor'])})"
        btn = InlineKeyboardButton(rotulo, callback_data=f"chk_pay:{c['id']}:{mes_ano}:cartoes:0")
        pend_chunk.append(btn)
        if len(pend_chunk) == 2:
            botoes.append(pend_chunk)
            pend_chunk = []
    if pend_chunk:
        botoes.append(pend_chunk)

    if pagas:
        botoes.append([
            InlineKeyboardButton(f"👇 Desmarcar Paga ({len(pagas)})", callback_data=f"show_paid:{mes_ano}:cartoes:0")
        ])

    # Ações principais
    botoes.append([
        InlineKeyboardButton("🔒 Ver Fixos", callback_data=f"show_fixos:{mes_ano}"),
        InlineKeyboardButton("📈 Ver Investimentos", callback_data=f"show_invest:{mes_ano}"),
    ])
    botoes.append([
        InlineKeyboardButton("✏️ Editar Valor", callback_data=f"action_edit:{mes_ano}:cartoes:0"),
        InlineKeyboardButton("➕ Nova Conta", callback_data=f"action_new:{mes_ano}:cartoes:0"),
    ])
    botoes.append([
        InlineKeyboardButton("🗑️ Excluir", callback_data=f"action_del:{mes_ano}:cartoes:0"),
    ])

    # Navegação entre meses
    mes_anterior = get_mes_vizinho(mes_ano, -1)
    mes_seguinte = get_mes_vizinho(mes_ano, 1)
    botoes.append([
        InlineKeyboardButton(f"⬅️ {format_mes_extenso(mes_anterior).split('/')[0].strip()}", callback_data=f"nav_month:{mes_anterior}:cartoes"),
        InlineKeyboardButton(f"{format_mes_extenso(mes_seguinte).split('/')[0].strip()} ➡️", callback_data=f"nav_month:{mes_seguinte}:cartoes"),
    ])

    return texto_final, InlineKeyboardMarkup(botoes)


def render_fixos_message(
    fixos: List[Dict[str, Any]],
    totais: Dict[str, Any],
    mes_ano: str,
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Renderiza o painel de CONTAS FIXAS / VARIÁVEIS:
    - Divide em Contas com Valor e Data Fixa e Contas Variáveis a lançar.
    - Exibe total acumulado no mês vs referência.
    - Botões lado a lado.
    """
    mes_str = format_mes_extenso(mes_ano)
    tot_lancado = totais.get("total_fixos_lancado", 0.0)
    tot_ref = totais.get("total_fixos_referencia", 0.0)

    # Separa contas com valor/data fixa e variáveis
    nomes_fixos = {'ALUGUEL', 'MESADAS', 'CONDUÇÃO LEVY', 'BANCA GABRIEL', 'FUTEBOL', 'NATAÇÃO', 'ACORDO CONDOMINIO'}
    lista_fixos_valor = [c for c in fixos if c["descricao"].strip().upper() in nomes_fixos]
    lista_variaveis = [c for c in fixos if c["descricao"].strip().upper() not in nomes_fixos]

    linhas = []
    linhas.append(f"📊 <b>CONTAS FIXAS E VARIÁVEIS — {mes_str}</b>")
    linhas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    linhas.append(f"💰 <b>TOTAL GASTO/COMPROMETIDO:</b> <code>{format_moeda(tot_lancado)}</code>")
    linhas.append(f"🎯 <b>Orçamento Total / Referência:</b> <code>{format_moeda(tot_ref)}</code>")
    linhas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if lista_fixos_valor:
        subtot_fixos = sum(c["valor"] for c in lista_fixos_valor)
        linhas.append(f"<b>🔒 Contas com Valor e Data Fixa ({len(lista_fixos_valor)}):</b>")
        for i, c in enumerate(lista_fixos_valor, 1):
            s_nome = get_short_name(c["descricao"])
            v_val = format_moeda(c["valor"])
            dia = f"Dia {c['dia_vencimento']:02d}"
            linhas.append(f"{i}. {s_nome}: <b>{v_val}</b> <i>[{dia}]</i>")
        linhas.append(f"<i>Subtotal Fixo: {format_moeda(subtot_fixos)}</i>\n")

    if lista_variaveis:
        linhas.append(f"<b>📊 Despesas Variáveis / Gastos no Mês ({len(lista_variaveis)}):</b>")
        for j, c in enumerate(lista_variaveis, 1):
            s_nome = get_short_name(c["descricao"])
            v_gasto = format_moeda(c["valor"])
            v_ref = format_moeda(c.get("valor_referencia", 0.0))
            dia_info = f" [Dia {c['dia_vencimento']:02d}]" if c['dia_vencimento'] > 1 else ""
            linhas.append(f"{j}. {s_nome}: <b>{v_gasto}</b> <i>(Ref: {v_ref}{dia_info})</i>")
        linhas.append("")

    linhas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    linhas.append(f"💳 <b>Total Cartões:</b> {format_moeda(totais.get('total_cartoes', 0.0))}")
    linhas.append(f"📈 <b>Total Investimentos:</b> {format_moeda(totais.get('total_invest_lancado', 0.0))} <i>(Ref: {format_moeda(totais.get('total_invest_referencia', 0.0))})</i>")
    linhas.append(f"💰 <b>Total Geral Comprometido:</b> {format_moeda(totais.get('total_geral_comprometido', 0.0))}")

    texto_final = "\n".join(linhas)

    botoes: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("➕ Lançar Valor", callback_data=f"prompt_val:{mes_ano}"),
            InlineKeyboardButton("🔄 Zerar Mês", callback_data=f"confirm_reset_fixos:{mes_ano}"),
        ],
        [
            InlineKeyboardButton("📈 Ver Investimentos", callback_data=f"show_invest:{mes_ano}"),
            InlineKeyboardButton("💳 Ver Cartões", callback_data=f"nav_month:{mes_ano}:cartoes"),
        ],
        [
            InlineKeyboardButton("📊 Resumo Geral", callback_data=f"show_resumo:{mes_ano}"),
        ],
    ]

    mes_anterior = get_mes_vizinho(mes_ano, -1)
    mes_seguinte = get_mes_vizinho(mes_ano, 1)
    botoes.append([
        InlineKeyboardButton(f"⬅️ {format_mes_extenso(mes_anterior).split('/')[0].strip()}", callback_data=f"nav_month:{mes_anterior}:fixos"),
        InlineKeyboardButton(f"{format_mes_extenso(mes_seguinte).split('/')[0].strip()} ➡️", callback_data=f"nav_month:{mes_seguinte}:fixos"),
    ])

    return texto_final, InlineKeyboardMarkup(botoes)


def render_investimentos_message(
    investimentos: List[Dict[str, Any]],
    totais: Dict[str, Any],
    mes_ano: str,
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Renderiza o painel de INVESTIMENTOS E CONSÓRCIOS:
    - Exibe os 6 consórcios com vencimento no dia 10.
    - Exibe total investido no mês vs referência.
    - Botões lado a lado.
    """
    mes_str = format_mes_extenso(mes_ano)
    tot_lancado = totais.get("total_invest_lancado", 0.0)
    tot_ref = totais.get("total_invest_referencia", 0.0)

    linhas = []
    linhas.append(f"📈 <b>INVESTIMENTOS E CONSÓRCIOS — {mes_str}</b>")
    linhas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    linhas.append(f"💰 <b>TOTAL INVESTIDO NO MÊS:</b> <code>{format_moeda(tot_lancado)}</code>")
    linhas.append(f"🎯 <b>Total Previsto / Referência:</b> <code>{format_moeda(tot_ref)}</code>")
    linhas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    linhas.append("<i>💡 Digite qualquer valor no chat para lançar direto no consórcio desejado!</i>\n")

    linhas.append("<b>📋 Extrato dos Consórcios (Dia 10):</b>")
    for i, c in enumerate(investimentos, 1):
        s_nome = get_short_name(c["descricao"])
        v_gasto = format_moeda(c["valor"])
        v_ref = format_moeda(c.get("valor_referencia", 0.0))
        dia = f"Dia {c['dia_vencimento']:02d}"
        linhas.append(f"{i}. {s_nome}: <b>{v_gasto}</b> <i>(Ref: {v_ref} — {dia})</i>")

    linhas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    linhas.append(f"🔒 <b>Total Fixos/Variáveis:</b> {format_moeda(totais.get('total_fixos_lancado', 0.0))}")
    linhas.append(f"💳 <b>Total Cartões:</b> {format_moeda(totais.get('total_cartoes', 0.0))}")
    linhas.append(f"💰 <b>Total Geral Comprometido:</b> {format_moeda(totais.get('total_geral_comprometido', 0.0))}")

    texto_final = "\n".join(linhas)

    botoes: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("➕ Lançar Valor", callback_data=f"prompt_val:{mes_ano}"),
            InlineKeyboardButton("🔄 Zerar Mês", callback_data=f"confirm_reset_inv:{mes_ano}"),
        ],
        [
            InlineKeyboardButton("🔒 Ver Contas Fixas", callback_data=f"show_fixos:{mes_ano}"),
            InlineKeyboardButton("💳 Ver Cartões", callback_data=f"nav_month:{mes_ano}:cartoes"),
        ],
        [
            InlineKeyboardButton("📊 Resumo Geral", callback_data=f"show_resumo:{mes_ano}"),
        ],
    ]

    mes_anterior = get_mes_vizinho(mes_ano, -1)
    mes_seguinte = get_mes_vizinho(mes_ano, 1)
    botoes.append([
        InlineKeyboardButton(f"⬅️ {format_mes_extenso(mes_anterior).split('/')[0].strip()}", callback_data=f"nav_month:{mes_anterior}:invest"),
        InlineKeyboardButton(f"{format_mes_extenso(mes_seguinte).split('/')[0].strip()} ➡️", callback_data=f"nav_month:{mes_seguinte}:invest"),
    ])

    return texto_final, InlineKeyboardMarkup(botoes)


def render_choose_category_keyboard(
    valor: float,
    mes_ano: str,
    fixos: List[Dict[str, Any]],
) -> InlineKeyboardMarkup:
    """
    Gera o teclado com todas as categorias lado a lado (2 por linha)
    para escolher onde acrescentar o valor recebido.
    """
    botoes: List[List[InlineKeyboardButton]] = []
    chunk = []

    for c in fixos:
        s_nome = get_short_name(c["descricao"])
        btn = InlineKeyboardButton(s_nome, callback_data=f"add_val:{c['id']}:{valor}:{mes_ano}")
        chunk.append(btn)
        if len(chunk) == 2:
            botoes.append(chunk)
            chunk = []
    if chunk:
        botoes.append(chunk)

    botoes.append([
        InlineKeyboardButton("📈 Consórcios / Investimentos ➡️", callback_data=f"inv_menu:{valor}:{mes_ano}"),
        InlineKeyboardButton("💳 Fatura de Cartão ➡️", callback_data=f"card_menu:{valor}:{mes_ano}"),
    ])
    botoes.append([
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_entry"),
    ])

    return InlineKeyboardMarkup(botoes)


def render_choose_invest_keyboard(
    valor: float,
    mes_ano: str,
    investimentos: List[Dict[str, Any]],
) -> InlineKeyboardMarkup:
    """Gera o teclado com os consórcios lado a lado para lançar o valor."""
    botoes: List[List[InlineKeyboardButton]] = []
    chunk = []

    for c in investimentos:
        s_nome = get_short_name(c["descricao"])
        btn = InlineKeyboardButton(s_nome, callback_data=f"add_val:{c['id']}:{valor}:{mes_ano}")
        chunk.append(btn)
        if len(chunk) == 2:
            botoes.append(chunk)
            chunk = []
    if chunk:
        botoes.append(chunk)

    botoes.append([
        InlineKeyboardButton("🔙 Voltar para Fixos", callback_data=f"back_to_fixos_val:{valor}:{mes_ano}"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_entry"),
    ])
    return InlineKeyboardMarkup(botoes)


def render_choose_card_keyboard(
    valor: float,
    mes_ano: str,
    cartoes: List[Dict[str, Any]],
) -> InlineKeyboardMarkup:
    """Gera o teclado para selecionar qual cartão deseja atualizar com o valor informado."""
    botoes: List[List[InlineKeyboardButton]] = []
    chunk = []

    for c in cartoes:
        s_nome = get_short_name(c["descricao"])
        btn = InlineKeyboardButton(s_nome, callback_data=f"set_card:{c['id']}:{valor}:{mes_ano}")
        chunk.append(btn)
        if len(chunk) == 2:
            botoes.append(chunk)
            chunk = []
    if chunk:
        botoes.append(chunk)

    botoes.append([
        InlineKeyboardButton("🔙 Voltar para Fixos/Variáveis", callback_data=f"back_to_fixos_val:{valor}:{mes_ano}"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel_entry"),
    ])

    return InlineKeyboardMarkup(botoes)


def render_paid_accounts_keyboard(
    pagas: List[Dict[str, Any]],
    mes_ano: str,
    filtro: str = "todos",
    pagina: int = 0,
) -> InlineKeyboardMarkup:
    """Gera o teclado para desmarcar uma conta paga (lado a lado)."""
    botoes: List[List[InlineKeyboardButton]] = []
    chunk = []

    for c in pagas:
        s_nome = get_short_name(c["descricao"])
        rotulo = f"↩️ {s_nome}"
        btn = InlineKeyboardButton(rotulo, callback_data=f"chk_unpay:{c['id']}:{mes_ano}:{filtro}:{pagina}")
        chunk.append(btn)
        if len(chunk) == 2:
            botoes.append(chunk)
            chunk = []
    if chunk:
        botoes.append(chunk)

    botoes.append([
        InlineKeyboardButton("🔙 Voltar para a Lista Principal", callback_data=f"flt:{filtro}:{mes_ano}:{pagina}")
    ])
    return InlineKeyboardMarkup(botoes)


def render_delete_accounts_keyboard(
    contas: List[Dict[str, Any]],
    mes_ano: str,
    filtro: str = "todos",
    pagina: int = 0,
) -> InlineKeyboardMarkup:
    """Gera o teclado para excluir contas (lado a lado)."""
    botoes: List[List[InlineKeyboardButton]] = []
    chunk = []

    for c in contas:
        s_nome = get_short_name(c["descricao"])
        rotulo = f"🗑️ {s_nome}"
        btn = InlineKeyboardButton(rotulo, callback_data=f"confirm_del:{c['id']}:{mes_ano}:{filtro}:{pagina}")
        chunk.append(btn)
        if len(chunk) == 2:
            botoes.append(chunk)
            chunk = []
    if chunk:
        botoes.append(chunk)

    botoes.append([
        InlineKeyboardButton("🔙 Concluído / Voltar", callback_data=f"flt:{filtro}:{mes_ano}:{pagina}")
    ])
    return InlineKeyboardMarkup(botoes)


def render_edit_accounts_keyboard(
    contas: List[Dict[str, Any]],
    mes_ano: str,
    filtro: str = "todos",
    pagina: int = 0,
) -> InlineKeyboardMarkup:
    """Gera o teclado para selecionar qual conta deseja alterar o valor (lado a lado)."""
    botoes: List[List[InlineKeyboardButton]] = []
    chunk = []

    for c in contas:
        s_nome = get_short_name(c["descricao"])
        rotulo = f"✏️ {s_nome}"
        btn = InlineKeyboardButton(rotulo, callback_data=f"sel_edit:{c['id']}:{mes_ano}:{filtro}:{pagina}")
        chunk.append(btn)
        if len(chunk) == 2:
            botoes.append(chunk)
            chunk = []
    if chunk:
        botoes.append(chunk)

    botoes.append([
        InlineKeyboardButton("🔙 Voltar para a Lista", callback_data=f"flt:{filtro}:{mes_ano}:{pagina}")
    ])
    return InlineKeyboardMarkup(botoes)


def render_alert_message(alertas_data: Dict[str, Any], mes_ano: str) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Formata a mensagem de alertas de vencimento com botões para pagamento rápido.
    """
    data_hoje = alertas_data.get("data_hoje", "")
    hoje_list = alertas_data.get("hoje", [])
    em_breve_list = alertas_data.get("em_breve", [])
    vencidas_list = alertas_data.get("vencidas", [])

    total_qtd = len(hoje_list) + len(em_breve_list) + len(vencidas_list)

    linhas = []
    linhas.append("🔔 <b>ALERTA DE VENCIMENTO DE CONTAS!</b>")
    linhas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    linhas.append(f"📅 Data de Hoje: <b>{data_hoje}</b>\n")

    if total_qtd == 0:
        linhas.append("🎉 <b>Nenhuma conta vencendo hoje ou nos próximos dias!</b>")
        linhas.append("Todas as contas estão em dia ou já foram quitadas.")
    else:
        # 1. VENCENDO HOJE
        if hoje_list:
            linhas.append(f"🚨 <b>VENCENDO HOJE ({len(hoje_list)}):</b>")
            for c in hoje_list:
                linhas.append(f"• <b>{c['descricao']}</b> — <code>{format_moeda(c['valor'])}</code>")
            linhas.append("")

        # 2. VENCENDO EM BREVE
        if em_breve_list:
            linhas.append(f"⚠️ <b>VENCENDO EM BREVE ({len(em_breve_list)}):</b>")
            for c in em_breve_list:
                dias = c.get("dias_restantes", 1)
                dias_txt = "amanhã" if dias == 1 else f"em {dias} dias"
                linhas.append(f"• <b>{c['descricao']}</b> — <code>{format_moeda(c['valor'])}</code> (Dia {c['dia_vencimento']:02d} — {dias_txt})")
            linhas.append("")

        # 3. VENCIDAS (EM ATRASO)
        if vencidas_list:
            linhas.append(f"🔴 <b>VENCIDAS / EM ATRASO ({len(vencidas_list)}):</b>")
            for c in vencidas_list:
                if c.get("mes_anterior"):
                    linhas.append(f"• <b>{c['descricao']}</b> — <code>{format_moeda(c['valor'])}</code> (Mês anterior: {c['mes_ano']})")
                else:
                    dias_atraso = c.get("dias_atraso", 1)
                    dias_txt = "ontem" if dias_atraso == 1 else f"há {dias_atraso} dias"
                    linhas.append(f"• <b>{c['descricao']}</b> — <code>{format_moeda(c['valor'])}</code> (Venceu dia {c['dia_vencimento']:02d} — {dias_txt})")
            linhas.append("")

        total_valor = sum(c["valor"] for c in hoje_list + em_breve_list + vencidas_list)
        linhas.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        linhas.append(f"💰 <b>Total em alerta:</b> <code>{format_moeda(total_valor)}</code>")

    linhas.append("\n<i>Clique nos botões abaixo para dar baixa ou ver o mês completo:</i>")
    texto_final = "\n".join(linhas)

    # Botões inline
    botoes: List[List[InlineKeyboardButton]] = []

    # Botões de pagamento rápido
    contas_para_pagar = hoje_list + vencidas_list + em_breve_list
    for c in contas_para_pagar[:6]:
        rotulo = f"⬜ Pagar: {c['descricao']} ({format_moeda(c['valor'])})"
        if len(rotulo) > 38:
            rotulo = f"⬜ Pagar: {c['descricao'][:18]}... ({format_moeda(c['valor'])})"
        botoes.append([
            InlineKeyboardButton(rotulo, callback_data=f"chk_pay:{c['id']}:{mes_ano}")
        ])

    botoes.append([
        InlineKeyboardButton("📋 Ver Todas as Contas do Mês", callback_data=f"nav_month:{mes_ano}"),
        InlineKeyboardButton("🔄 Atualizar Alertas", callback_data=f"alert_refresh:{mes_ano}"),
    ])

    return texto_final, InlineKeyboardMarkup(botoes)
