"""
Bot de Gerenciamento de Contas do Telegram.
Checklist interativo de contas do mês com checkboxes em Inline Keyboard,
reorganização automática de contas pagas para o final da lista, totais e persistência em SQLite.
"""

import sys
import os
import logging
import datetime
import zoneinfo
from typing import Optional

# Força codificação UTF-8 no stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
import database
import helpers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ContasBot")

# Sessões do assistente passo a passo (chave: user_id)
WIZARD_STATES = {}

# Sessões de edição de valor (chave: user_id)
EDIT_STATES = {}


def get_new_account_choice_markup(mes_ano: str) -> InlineKeyboardMarkup:
    """Menu para escolher entre cadastro Passo a Passo ou Comando Rápido."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Passo a Passo (Item a Item)", callback_data=f"wiz_start:{mes_ano}")],
        [InlineKeyboardButton("⚡ Comando Rápido (/nova)", callback_data=f"wiz_quick:{mes_ano}")],
        [InlineKeyboardButton("❌ Cancelar", callback_data=f"wiz_cancel:{mes_ano}")],
    ])

# Teclado fixo na parte inferior do chat
REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📋 Contas do Mês"), KeyboardButton("🔒 Contas Fixas"), KeyboardButton("📈 Investimentos")],
        [KeyboardButton("➕ Nova Conta"), KeyboardButton("📊 Resumo Financeiro")],
        [KeyboardButton("🔔 Alertas de Vencimento")],
    ],
    resize_keyboard=True,
)


def get_target_chat_id(update: Update) -> str:
    """
    Retorna o chat_id para persistência.
    Centraliza os dados do grupo 'Contas' sob o mesmo identificador (-1003987623111).
    """
    cid = update.effective_chat.id
    if cid in (-5370228319, -1003987623111):
        return "-1003987623111"
    return str(cid)


async def check_authorization(update: Update) -> bool:
    """Verifica se o chat está autorizado a interagir com o bot."""
    chat = update.effective_chat
    if not chat:
        return False
    if not config.is_chat_authorized(chat.id, chat.type):
        logger.warning(f"Acesso negado para chat {chat.id} ({chat.type})")
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start ou /ajuda."""
    if not await check_authorization(update):
        return

    texto = (
        "👋 <b>Olá! Eu sou o seu Bot de Gerenciamento de Contas!</b>\n\n"
        "Comigo você controla todas as contas a pagar do mês de forma rápida, interativa e organizada.\n\n"
        "📌 <b>Principais Recursos:</b>\n"
        "• <b>Checklist Interativo:</b> Clique no botão ⬜ para pagar uma conta.\n"
        "• <b>Organização Automática:</b> Contas marcadas como pagas vão direto para o <b>final da lista</b> sinalizadas com ✅ e data do pagamento.\n"
        "• <b>🔒 Contas Fixas & Filtros:</b> Filtre instantaneamente por <b>Fixos</b>, <b>Cartões</b> ou <b>Outros</b>.\n"
        "• <b>Totais em Tempo Real:</b> Referência detalhada dos valores fixos e balanço completo.\n"
        "• <b>Contas Recorrentes:</b> Replicadas mês a mês automaticamente.\n"
        "• <b>🔔 Alertas Diários:</b> Notificações de contas vencendo hoje ou em breve às 09:00.\n\n"
        "🚀 <b>Comandos Rápidos:</b>\n"
        "• /contas — Exibe o checklist interativo do mês\n"
        "• /fixos — Exibe a lista e referência de Contas Fixas\n"
        "• /nova <code>&lt;descrição&gt; &lt;valor&gt; &lt;dia&gt;</code> — Adiciona nova conta\n"
        "• /editar <code>&lt;conta&gt; &lt;novo_valor&gt;</code> — Altera o valor da conta\n"
        "• /resumo — Exibe o balanço e referências do mês\n"
        "• /alertas — Consulta contas vencendo hoje ou atrasadas\n\n"
        "<i>Clique nos botões abaixo para começar!</i>"
    )
    await update.message.reply_text(
        texto,
        parse_mode=ParseMode.HTML,
        reply_markup=REPLY_KEYBOARD,
    )


def parse_cat_filtro(filtro: str) -> Optional[str]:
    """Converte o filtro textual para a categoria do banco de dados."""
    if filtro == "fixos":
        return "Fixo"
    elif filtro == "cartoes":
        return "Cartão"
    elif filtro == "outros":
        return "Outros"
    return None


async def cmd_contas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o checklist de cartões e faturas do mês."""
    if not await check_authorization(update):
        return

    chat_id = get_target_chat_id(update)
    mes_ano = helpers.get_current_mes_ano()
    filtro = "cartoes"

    # Se o usuário passou argumentos (ex: /contas fixos ou /contas 2026-11)
    if context.args:
        for arg in context.args:
            arg_low = arg.strip().lower()
            if arg_low in ["fixos", "fixo"]:
                await cmd_fixos(update, context)
                return
            elif arg_low in ["invest", "investimento", "investimentos", "consorcios", "consorcio"]:
                await cmd_investimentos(update, context)
                return
            elif arg_low in ["cartoes", "cartões", "cartao", "cartão"]:
                filtro = "cartoes"
            elif len(arg) == 7 and "-" in arg:
                mes_ano = arg
            elif arg.isdigit() and 1 <= int(arg) <= 12:
                ano = datetime.datetime.now().year
                mes_ano = f"{ano}-{int(arg):02d}"

    contas = database.listar_contas(chat_id, mes_ano, filtro_categoria="Cartão")
    totais = database.obter_totais_mes(chat_id, mes_ano)
    texto, markup = helpers.render_contas_message(contas, totais, mes_ano, filtro=filtro, pagina=0)

    await update.message.reply_text(
        texto,
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )


async def cmd_fixos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe diretamente o painel de Contas Fixas e Variáveis do mês."""
    if not await check_authorization(update):
        return

    chat_id = get_target_chat_id(update)
    mes_ano = helpers.get_current_mes_ano()

    if context.args:
        for arg in context.args:
            if len(arg) == 7 and "-" in arg:
                mes_ano = arg
            elif arg.isdigit() and 1 <= int(arg) <= 12:
                ano = datetime.datetime.now().year
                mes_ano = f"{ano}-{int(arg):02d}"

    fixos = database.listar_contas(chat_id, mes_ano, filtro_categoria="Fixo")
    totais = database.obter_totais_mes(chat_id, mes_ano)
    texto, markup = helpers.render_fixos_message(fixos, totais, mes_ano)

    await update.message.reply_text(
        texto,
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )


async def cmd_investimentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe diretamente o painel de Investimentos e Consórcios do mês."""
    if not await check_authorization(update):
        return

    chat_id = get_target_chat_id(update)
    mes_ano = helpers.get_current_mes_ano()

    if context.args:
        for arg in context.args:
            if len(arg) == 7 and "-" in arg:
                mes_ano = arg
            elif arg.isdigit() and 1 <= int(arg) <= 12:
                ano = datetime.datetime.now().year
                mes_ano = f"{ano}-{int(arg):02d}"

    invest = database.listar_contas(chat_id, mes_ano, filtro_categoria="Investimento")
    totais = database.obter_totais_mes(chat_id, mes_ano)
    texto, markup = helpers.render_investimentos_message(invest, totais, mes_ano)

    await update.message.reply_text(
        texto,
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )


async def cmd_nova(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Adiciona uma nova conta ao sistema.
    Exemplo: /nova Aluguel 1500 10 fixo
             /nova CT Santander 1 10 cartao
    """
    if not await check_authorization(update):
        return

    # Obtém argumentos de context.args ou extrai diretamente do texto da mensagem
    args = list(context.args) if context.args else []
    if not args and update.message and update.message.text:
        raw_tokens = update.message.text.strip().split()
        if len(raw_tokens) > 1:
            args = raw_tokens[1:]

    if not args or len(args) < 3:
        mes_ano = helpers.get_current_mes_ano()
        msg_escolha = (
            "➕ <b>COMO DESEJA CADASTRAR A CONTA?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Escolha o formato que preferir:\n\n"
            "1️⃣ <b>Passo a Passo:</b> O bot pergunta item por item (Nome, Valor, Dia, Recorrente, Categoria).\n"
            "2️⃣ <b>Comando Rápido:</b> Digite tudo em uma linha só (ex: <code>/nova Aluguel 1500 10 fixo</code>)."
        )
        await update.message.reply_text(
            msg_escolha,
            parse_mode=ParseMode.HTML,
            reply_markup=get_new_account_choice_markup(mes_ano),
        )
        return

    # Processa os argumentos
    recorrente = 0
    categoria = "Geral"

    remaining = []
    for a in args:
        al = a.lower()
        if al in ["recorrente", "rec", "mensal", "sim"]:
            recorrente = 1
        elif al in ["fixo", "fixos"]:
            categoria = "Fixo"
            recorrente = 1
        elif al in ["cartao", "cartão", "cartoes", "cartões"]:
            categoria = "Cartão"
            recorrente = 1
        else:
            remaining.append(a)

    args = remaining

    try:
        dia_vencimento = int(args[-1])
        if dia_vencimento < 1 or dia_vencimento > 31:
            await update.message.reply_text("❌ O dia de vencimento deve estar entre 1 e 31.")
            return
        args = args[:-1]
    except (ValueError, IndexError):
        await update.message.reply_text("❌ O dia de vencimento deve ser um número inteiro válido (ex: 10).")
        return

    try:
        raw_val = args[-1].replace("R$", "").replace("r$", "").replace(",", ".").strip()
        valor = float(raw_val)
        if valor <= 0:
            await update.message.reply_text("❌ O valor da conta deve ser maior que zero.")
            return
        args = args[:-1]
    except (ValueError, IndexError):
        await update.message.reply_text("❌ O valor informado é inválido. Exemplo: <code>1500</code> ou <code>120.50</code>", parse_mode=ParseMode.HTML)
        return

    descricao = " ".join(args).strip()
    if not descricao:
        await update.message.reply_text("❌ Por favor, informe o nome/descrição da conta.")
        return

    if descricao.upper().startswith("CT ") or "CARTAO" in descricao.upper() or "CARTÃO" in descricao.upper():
        if categoria == "Geral":
            categoria = "Cartão"

    chat_id = get_target_chat_id(update)
    mes_ano = helpers.get_current_mes_ano()

    conta_id = database.adicionar_conta(
        chat_id=chat_id,
        descricao=descricao,
        valor=valor,
        dia_vencimento=dia_vencimento,
        mes_ano=mes_ano,
        recorrente=recorrente,
        categoria=categoria,
    )

    rec_tag = " (🔁 Recorrente para os próximos meses)" if recorrente else ""
    await update.message.reply_text(
        f"✅ <b>Conta adicionada com sucesso!</b>\n\n"
        f"📌 <b>{descricao}</b>\n"
        f"📁 Categoria: <b>{categoria}</b>\n"
        f"💰 Valor: <code>{helpers.format_moeda(valor)}</code>\n"
        f"📅 Vencimento: Dia {dia_vencimento:02d} ({helpers.format_mes_extenso(mes_ano)}){rec_tag}\n\n"
        f"<i>Digite /contas para ver a lista atualizada!</i>",
        parse_mode=ParseMode.HTML,
    )


async def cmd_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o resumo financeiro consolidado do mês com referências de Fixos e Cartões."""
    if not await check_authorization(update):
        return

    chat_id = get_target_chat_id(update)
    mes_ano = helpers.get_current_mes_ano()
    totais = database.obter_totais_mes(chat_id, mes_ano)

    pct_pago = 0.0
    if totais["total_geral"] > 0:
        pct_pago = (totais["total_pago"] / totais["total_geral"]) * 100

    msg = (
        f"📊 <b>RESUMO FINANCEIRO — {helpers.format_mes_extenso(mes_ano)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔒 <b>Contas Fixas (Referência):</b> <code>{helpers.format_moeda(totais.get('total_fixos', 0.0))}</code>\n"
        f"   └ Quantidade: {totais.get('qtd_fixos', 0)} contas\n\n"
        f"💳 <b>Cartões de Crédito:</b> <code>{helpers.format_moeda(totais.get('total_cartoes', 0.0))}</code>\n"
        f"   └ Faturas: {totais.get('qtd_cartoes', 0)} cartões (base R$ 1,00)\n\n"
        f"📄 <b>Outras Despesas:</b> <code>{helpers.format_moeda(totais.get('total_outros', 0.0))}</code>\n"
        f"   └ Quantidade: {totais.get('qtd_outros', 0)} contas\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔴 <b>A Pagar (Pendentes):</b> {helpers.format_moeda(totais['total_pendente'])}\n"
        f"   └ Quantidade: {totais['qtd_pendente']} conta(s)\n\n"
        f"🟢 <b>Já Pago (Quitadas):</b> {helpers.format_moeda(totais['total_pago'])}\n"
        f"   └ Quantidade: {totais['qtd_paga']} conta(s)\n\n"
        f"💰 <b>Total Geral do Mês:</b> {helpers.format_moeda(totais['total_geral'])}\n"
        f"📈 <b>Progresso de Pagamento:</b> {pct_pago:.1f}%\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Digite /contas ou /fixos para visualizar ou pagar as contas!</i>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def cmd_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o alerta manual de contas vencendo hoje, em breve ou atrasadas."""
    if not await check_authorization(update):
        return

    chat_id = get_target_chat_id(update)
    mes_ano = helpers.get_current_mes_ano()
    alertas_data = database.obter_contas_alerta(chat_id, dias_antecedencia=5)
    texto, markup = helpers.render_alert_message(alertas_data, mes_ano)

    await update.message.reply_text(
        texto,
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )


async def scheduled_daily_alert(context: ContextTypes.DEFAULT_TYPE):
    """Executado diariamente para enviar alertas de vencimento no grupo às 09:00."""
    target_chat_id = "-1003987623111"
    mes_ano = helpers.get_current_mes_ano()
    alertas_data = database.obter_contas_alerta(target_chat_id, dias_antecedencia=3)

    # Só envia alerta no grupo se houver alguma conta pendente (hoje, em breve ou vencida)
    if alertas_data.get("total_alerta", 0) > 0:
        texto, markup = helpers.render_alert_message(alertas_data, mes_ano)
        try:
            await context.bot.send_message(
                chat_id=int(target_chat_id),
                text=texto,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
            logger.info(f"Alerta diário enviado com sucesso para {target_chat_id}")
        except Exception as e:
            logger.error(f"Erro ao disparar alerta diário para {target_chat_id}: {e}")


async def cmd_gerar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gera as contas recorrentes para o mês atual."""
    if not await check_authorization(update):
        return

    chat_id = get_target_chat_id(update)
    mes_ano = helpers.get_current_mes_ano()
    adicionadas = database.gerar_contas_recorrentes(chat_id, mes_ano)

    if adicionadas > 0:
        await update.message.reply_text(
            f"🔁 <b>{adicionadas} conta(s) recorrente(s)</b> gerada(s) para {helpers.format_mes_extenso(mes_ano)}!\n\n"
            f"Use /contas para visualizar.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"ℹ️ Nenhuma nova conta recorrente para gerar em {helpers.format_mes_extenso(mes_ano)}.\n"
            f"<i>(Todas as contas recorrentes já existem no mês).</i>",
            parse_mode=ParseMode.HTML,
        )


async def cmd_editar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Permite editar o valor de uma conta cadastrada.
    Pode ser usado via comando direto: /editar <nome_ou_id> <novo_valor> [todos]
    Ou digitando apenas /editar para abrir a lista interativa de contas.
    """
    if not await check_authorization(update):
        return

    chat_id = get_target_chat_id(update)
    mes_ano = helpers.get_current_mes_ano()
    args = context.args

    # Se passou argumentos direto (ex: /editar Energia 380)
    if args and len(args) >= 2:
        atualizar_futuros = False
        if args[-1].lower() in ["todos", "futuros", "recorrente", "sim"]:
            atualizar_futuros = True
            args = args[:-1]

        raw_val = args[-1].replace("R$", "").replace("r$", "").replace(",", ".").strip()
        try:
            novo_valor = float(raw_val)
            if novo_valor <= 0:
                await update.message.reply_text("❌ O valor deve ser maior que zero.")
                return
            termo = " ".join(args[:-1]).strip()
        except ValueError:
            termo = " ".join(args).strip()
            novo_valor = None

        if novo_valor is not None and termo:
            conta = database.buscar_conta_por_nome_ou_id(chat_id, termo, mes_ano)
            if not conta:
                await update.message.reply_text(f"❌ Conta '{termo}' não encontrada neste mês.")
                return

            valor_antigo = conta["valor"]
            database.atualizar_valor_conta(conta["id"], novo_valor, atualizar_futuros=atualizar_futuros)
            escopo_txt = " (e em todos os próximos meses)" if atualizar_futuros else " (apenas neste mês)"
            await update.message.reply_text(
                f"✅ <b>Valor atualizado com sucesso!</b>\n\n"
                f"📌 <b>{conta['descricao']}</b>\n"
                f"De: <s>{helpers.format_moeda(valor_antigo)}</s> ➡️ Para: <code>{helpers.format_moeda(novo_valor)}</code>{escopo_txt}\n\n"
                f"<i>Digite /contas para ver a lista atualizada!</i>",
                parse_mode=ParseMode.HTML,
            )
            return

    # Se não passou argumentos completos, exibe teclado com as contas para selecionar
    contas = database.listar_contas(chat_id, mes_ano)
    if not contas:
        await update.message.reply_text("ℹ️ Nenhuma conta cadastrada para editar neste mês.")
        return

    markup = helpers.render_edit_accounts_keyboard(contas, mes_ano)
    await update.message.reply_text(
        "✏️ <b>Selecione qual conta deseja alterar o valor:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )


async def cmd_excluir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe teclado para excluir contas."""
    if not await check_authorization(update):
        return

    chat_id = get_target_chat_id(update)
    mes_ano = helpers.get_current_mes_ano()
    contas = database.listar_contas(chat_id, mes_ano)

    if not contas:
        await update.message.reply_text("ℹ️ Nenhuma conta cadastrada para excluir neste mês.")
        return

    markup = helpers.render_delete_accounts_keyboard(contas, mes_ano)
    await update.message.reply_text(
        "🗑️ <b>Selecione qual conta deseja EXCLUIR:</b>\n"
        "<i>Clique no botão da conta para apagá-la.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )


async def safe_edit_message(query, text: str, markup):
    """Edita a mensagem ignorando o erro caso o conteúdo seja idêntico."""
    try:
        await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception as e:
        if "Message is not modified" in str(e):
            pass
        else:
            logger.error(f"Erro ao editar mensagem: {e}")


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gerencia cliques nos botões de checkbox e ações inline.
    Quando uma conta é marcada como paga:
    1. Alterna o status no banco de dados.
    2. Recalcula a lista (a conta vai para o FINAL da lista).
    3. Edita a mensagem em tempo real sem criar nova mensagem!
    """
    query = update.callback_query
    if not query:
        return

    data = query.data
    chat_id = get_target_chat_id(update)

    # 0. AÇÃO NO-OP (INDICADOR DE PÁGINA)
    if data == "noop":
        await query.answer()
        return

    # 0.1 FILTRO DE CATEGORIA E NAVEGAÇÃO DE MÊS
    elif data.startswith("flt:") or data.startswith("nav_month:"):
        parts = data.split(":")
        filtro = parts[1] if data.startswith("flt:") else (parts[2] if len(parts) > 2 else "cartoes")
        mes_ano = parts[2] if data.startswith("flt:") else parts[1]
        page = int(parts[3]) if len(parts) > 3 else 0

        await query.answer()
        if filtro in ["invest", "investimento", "investimentos"]:
            invest = database.listar_contas(chat_id, mes_ano, filtro_categoria="Investimento")
            totais = database.obter_totais_mes(chat_id, mes_ano)
            texto, markup = helpers.render_investimentos_message(invest, totais, mes_ano)
        elif filtro in ["fixo", "fixos"]:
            fixos = database.listar_contas(chat_id, mes_ano, filtro_categoria="Fixo")
            totais = database.obter_totais_mes(chat_id, mes_ano)
            texto, markup = helpers.render_fixos_message(fixos, totais, mes_ano)
        else:
            contas = database.listar_contas(chat_id, mes_ano, filtro_categoria="Cartão")
            totais = database.obter_totais_mes(chat_id, mes_ano)
            texto, markup = helpers.render_contas_message(contas, totais, mes_ano, filtro="cartoes", pagina=page)
        await safe_edit_message(query, texto, markup)

    # 0.2 MOSTRAR PAINEL DE FIXOS / VARIÁVEIS
    elif data.startswith("show_fixos:"):
        mes_ano = data.split(":")[1]
        await query.answer()
        fixos = database.listar_contas(chat_id, mes_ano, filtro_categoria="Fixo")
        totais = database.obter_totais_mes(chat_id, mes_ano)
        texto, markup = helpers.render_fixos_message(fixos, totais, mes_ano)
        await safe_edit_message(query, texto, markup)

    # 0.2.1 MOSTRAR PAINEL DE INVESTIMENTOS / CONSÓRCIOS
    elif data.startswith("show_invest:"):
        mes_ano = data.split(":")[1]
        await query.answer()
        invest = database.listar_contas(chat_id, mes_ano, filtro_categoria="Investimento")
        totais = database.obter_totais_mes(chat_id, mes_ano)
        texto, markup = helpers.render_investimentos_message(invest, totais, mes_ano)
        await safe_edit_message(query, texto, markup)

    # 0.2.2 MENU SELEÇÃO DE CONSÓRCIO / INVESTIMENTO
    elif data.startswith("inv_menu:"):
        parts = data.split(":")
        valor = float(parts[1])
        mes_ano = parts[2]
        await query.answer()
        invest = database.listar_contas(chat_id, mes_ano, filtro_categoria="Investimento")
        markup = helpers.render_choose_invest_keyboard(valor, mes_ano, invest)
        await safe_edit_message(
            query,
            f"📈 <b>LANÇAMENTO EM CONSÓRCIO — {helpers.format_moeda(valor)}</b>\n\n"
            f"Selecione o consórcio onde deseja lançar este valor:",
            markup,
        )

    # 0.2.3 ZERAR CONSÓRCIOS / INVESTIMENTOS
    elif data.startswith("confirm_reset_inv:"):
        mes_ano = data.split(":")[1]
        await query.answer()
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚠️ Sim, Zerar Consórcios", callback_data=f"do_reset_inv:{mes_ano}"),
                InlineKeyboardButton("❌ Cancelar", callback_data=f"show_invest:{mes_ano}"),
            ]
        ])
        await safe_edit_message(
            query,
            f"⚠️ <b>Deseja ZERAR os valores lançados em Consórcios para {helpers.format_mes_extenso(mes_ano)}?</b>\n\n"
            f"<i>Os valores acumulados voltarão para R$ 0,00 mantendo os valores de referência.</i>",
            markup,
        )

    elif data.startswith("do_reset_inv:"):
        mes_ano = data.split(":")[1]
        qtd = database.zerar_mes_investimentos(chat_id, mes_ano)
        await query.answer(f"🔄 {qtd} consórcios zerados!", show_alert=True)
        invest = database.listar_contas(chat_id, mes_ano, filtro_categoria="Investimento")
        totais = database.obter_totais_mes(chat_id, mes_ano)
        texto, markup = helpers.render_investimentos_message(invest, totais, mes_ano)
        await safe_edit_message(query, texto, markup)

    # 0.3 PROMPT DE VALOR
    elif data.startswith("prompt_val:"):
        await query.answer()
        await query.message.reply_text(
            "💬 <b>LANÇAMENTO RÁPIDO</b>\n\n"
            "Basta digitar o valor no chat (ex: <code>50</code> ou <code>120,50</code>) "
            "que exibirei os botões lado a lado para você escolher a categoria!",
            parse_mode=ParseMode.HTML,
        )

    # 0.4 ZERAR VALORES FIXOS DO MÊS
    elif data.startswith("confirm_reset_fixos:"):
        mes_ano = data.split(":")[1]
        await query.answer()
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚠️ Sim, Zerar Tudo", callback_data=f"do_reset_fixos:{mes_ano}"),
                InlineKeyboardButton("❌ Cancelar", callback_data=f"show_fixos:{mes_ano}"),
            ]
        ])
        await safe_edit_message(
            query,
            f"⚠️ <b>Tem certeza que deseja ZERAR os gastos acumulados de {helpers.format_mes_extenso(mes_ano)}?</b>\n\n"
            f"<i>Os valores acumulados voltarão para R$ 0,00. As referências orçamentárias serão mantidas.</i>",
            markup,
        )

    elif data.startswith("do_reset_fixos:"):
        mes_ano = data.split(":")[1]
        qtd = database.zerar_mes_fixos(chat_id, mes_ano)
        await query.answer(f"🔄 {qtd} categorias zeradas!", show_alert=True)
        fixos = database.listar_contas(chat_id, mes_ano, filtro_categoria="Fixo")
        totais = database.obter_totais_mes(chat_id, mes_ano)
        texto, markup = helpers.render_fixos_message(fixos, totais, mes_ano)
        await safe_edit_message(query, texto, markup)

    # 0.5 RESUMO GERAL
    elif data.startswith("show_resumo:"):
        mes_ano = data.split(":")[1]
        await query.answer()
        totais = database.obter_totais_mes(chat_id, mes_ano)
        msg = (
            f"📊 <b>RESUMO FINANCEIRO — {helpers.format_mes_extenso(mes_ano)}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 <b>Fixos/Variáveis (Lançados):</b> <code>{helpers.format_moeda(totais.get('total_fixos_lancado', 0.0))}</code>\n"
            f"   └ <i>Orçamento / Referência: {helpers.format_moeda(totais.get('total_fixos_referencia', 0.0))} ({totais.get('qtd_fixos', 0)} contas)</i>\n\n"
            f"📈 <b>Investimentos (Consórcios):</b> <code>{helpers.format_moeda(totais.get('total_invest_lancado', 0.0))}</code>\n"
            f"   └ <i>Previsão / Referência: {helpers.format_moeda(totais.get('total_invest_referencia', 0.0))} ({totais.get('qtd_invest', 0)} consórcios)</i>\n\n"
            f"💳 <b>Faturas de Cartões:</b> <code>{helpers.format_moeda(totais.get('total_cartoes', 0.0))}</code>\n"
            f"   └ <i>{totais.get('qtd_cartoes', 0)} cartões (Pendentes: {helpers.format_moeda(totais.get('cartoes_pendentes', 0.0))} | Pagas: {helpers.format_moeda(totais.get('cartoes_pagos', 0.0))})</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Total Comprometido no Mês:</b> <code>{helpers.format_moeda(totais.get('total_geral_comprometido', 0.0))}</code>\n"
            f"🎯 <b>Total Geral Orçado:</b> <code>{helpers.format_moeda(totais.get('total_geral_referencia', 0.0))}</code>\n"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔒 Ver Fixos", callback_data=f"show_fixos:{mes_ano}"),
                InlineKeyboardButton("📈 Ver Investimentos", callback_data=f"show_invest:{mes_ano}"),
            ],
            [
                InlineKeyboardButton("💳 Ver Cartões", callback_data=f"nav_month:{mes_ano}:cartoes"),
            ]
        ])
        await safe_edit_message(query, msg, markup)

    # 0.6 ADICIONAR VALOR RECEBIDO À CATEGORIA
    elif data.startswith("add_val:"):
        parts = data.split(":")
        conta_id = int(parts[1])
        valor = float(parts[2])
        mes_ano = parts[3]

        conta = database.acrescentar_valor_fixo(conta_id, valor)
        if not conta:
            await query.answer("Conta não encontrada.", show_alert=True)
            return

        desc = conta["descricao"]
        novo_tot = conta["valor"]
        ref = conta.get("valor_referencia", 0.0)

        is_invest = (conta.get("categoria") in ["Investimento", "Investimentos"])
        btn_voltar = (
            InlineKeyboardButton("📈 Ver Investimentos", callback_data=f"show_invest:{mes_ano}")
            if is_invest else
            InlineKeyboardButton("📊 Ver Fixos", callback_data=f"show_fixos:{mes_ano}")
        )
        markup_conf = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("↩️ Desfazer", callback_data=f"undo_val:{conta_id}:{valor}:{mes_ano}"),
                btn_voltar,
            ],
            [
                InlineKeyboardButton("💳 Ver Cartões", callback_data=f"nav_month:{mes_ano}:cartoes"),
            ]
        ])

        await query.answer(f"➕ {helpers.format_moeda(valor)} em {desc}!")
        ref_txt = f" <i>(Ref: {helpers.format_moeda(ref)})</i>" if ref > 0 else ""
        msg_txt = (
            f"✅ <b>Lançamento registrado com sucesso!</b>\n\n"
            f"📌 Categoria: <b>{desc}</b>\n"
            f"➕ Adicionado agora: <code>{helpers.format_moeda(valor)}</code>\n"
            f"📈 Total no mês: <b>{helpers.format_moeda(novo_tot)}</b>{ref_txt}"
        )
        await safe_edit_message(query, msg_txt, markup_conf)

    # 0.7 DESFAZER ADIÇÃO DE VALOR
    elif data.startswith("undo_val:"):
        parts = data.split(":")
        conta_id = int(parts[1])
        valor = float(parts[2])
        mes_ano = parts[3]

        conta = database.subtrair_valor_fixo(conta_id, valor)
        if not conta:
            await query.answer("Erro ao desfazer.", show_alert=True)
            return

        desc = conta["descricao"]
        novo_tot = conta["valor"]
        await query.answer("↩️ Lançamento desfeito!")
        is_invest = (conta.get("categoria") in ["Investimento", "Investimentos"])
        btn_voltar = (
            InlineKeyboardButton("📈 Ver Investimentos", callback_data=f"show_invest:{mes_ano}")
            if is_invest else
            InlineKeyboardButton("📊 Ver Fixos", callback_data=f"show_fixos:{mes_ano}")
        )
        markup = InlineKeyboardMarkup([
            [btn_voltar]
        ])
        await safe_edit_message(
            query,
            f"↩️ <b>Lançamento desfeito!</b>\n\n"
            f"📌 <b>{desc}</b> retornou para <b>{helpers.format_moeda(novo_tot)}</b>.",
            markup
        )

    # 0.8 MENU PARA ESCOLHER CARTÃO
    elif data.startswith("card_menu:"):
        parts = data.split(":")
        valor = float(parts[1])
        mes_ano = parts[2]
        await query.answer()
        cartoes = database.listar_contas(chat_id, mes_ano, filtro_categoria="Cartão")
        markup = helpers.render_choose_card_keyboard(valor, mes_ano, cartoes)
        await safe_edit_message(
            query,
            f"💳 <b>ATUALIZAR FATURA DE CARTÃO — {helpers.format_moeda(valor)}</b>\n\n"
            f"Selecione qual cartão terá sua fatura definida para <b>{helpers.format_moeda(valor)}</b>:",
            markup
        )

    # 0.9 VOLTAR DO MENU DE CARTÕES PARA FIXOS
    elif data.startswith("back_to_fixos_val:"):
        parts = data.split(":")
        valor = float(parts[1])
        mes_ano = parts[2]
        await query.answer()
        fixos = database.listar_contas(chat_id, mes_ano, filtro_categoria="Fixo")
        markup = helpers.render_choose_category_keyboard(valor, mes_ano, fixos)
        await safe_edit_message(
            query,
            f"💰 <b>LANÇAMENTO: {helpers.format_moeda(valor)}</b>\n\n"
            f"Onde deseja acrescentar ou alterar esse valor?",
            markup
        )

    # 0.10 DEFINIR VALOR DA FATURA DO CARTÃO
    elif data.startswith("set_card:"):
        parts = data.split(":")
        conta_id = int(parts[1])
        valor = float(parts[2])
        mes_ano = parts[3]

        conta = database.obter_conta(conta_id)
        if not conta:
            await query.answer("Cartão não encontrado.", show_alert=True)
            return

        v_antigo = conta["valor"]
        desc = conta["descricao"]
        database.atualizar_valor_conta(conta_id, valor, atualizar_futuros=False)
        await query.answer(f"💳 Fatura de {desc} atualizada!")

        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📋 Ver Cartões", callback_data=f"nav_month:{mes_ano}:cartoes"),
                InlineKeyboardButton("🔒 Ver Fixos", callback_data=f"show_fixos:{mes_ano}"),
            ]
        ])
        await safe_edit_message(
            query,
            f"💳 <b>Fatura atualizada com sucesso!</b>\n\n"
            f"📌 Cartão: <b>{desc}</b>\n"
            f"De: <s>{helpers.format_moeda(v_antigo)}</s> ➡️ Para: <b>{helpers.format_moeda(valor)}</b>\n"
            f"📅 Vencimento: Dia {conta['dia_vencimento']:02d}",
            markup
        )

    # 0.11 CANCELAR ENTRADA
    elif data == "cancel_entry":
        await query.answer("Cancelado.")
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_text("❌ Cancelado.")

    # 1. CHECKBOX DE PAGAMENTO (MARCAR COMO PAGO)
    elif data.startswith("chk_pay:"):
        parts = data.split(":")
        conta_id = int(parts[1])
        mes_ano = parts[2]
        filtro = parts[3] if len(parts) > 3 else "cartoes"
        page = int(parts[4]) if len(parts) > 4 else 0

        novo_status, conta = database.alternar_status_pago(conta_id)
        desc = conta["descricao"] if conta else "Conta"
        await query.answer(f"✅ '{desc}' marcada como PAGA! (Movida para o final)")

        contas = database.listar_contas(chat_id, mes_ano, filtro_categoria="Cartão")
        totais = database.obter_totais_mes(chat_id, mes_ano)
        texto, markup = helpers.render_contas_message(contas, totais, mes_ano, filtro="cartoes", pagina=page)
        await safe_edit_message(query, texto, markup)

    # 2. CHECKBOX DE DESMARCAR (VOLTAR PARA PENDENTE)
    elif data.startswith("chk_unpay:"):
        parts = data.split(":")
        conta_id = int(parts[1])
        mes_ano = parts[2]
        filtro = parts[3] if len(parts) > 3 else "cartoes"
        page = int(parts[4]) if len(parts) > 4 else 0

        novo_status, conta = database.alternar_status_pago(conta_id)
        desc = conta["descricao"] if conta else "Conta"
        await query.answer(f"↩️ '{desc}' desmarcada e retornada para Pendentes!")

        contas = database.listar_contas(chat_id, mes_ano, filtro_categoria="Cartão")
        totais = database.obter_totais_mes(chat_id, mes_ano)
        texto, markup = helpers.render_contas_message(contas, totais, mes_ano, filtro="cartoes", pagina=page)
        await safe_edit_message(query, texto, markup)

    # 3. MOSTRAR LISTA DE PAGAS PARA DESMARCAR
    elif data.startswith("show_paid:"):
        parts = data.split(":")
        mes_ano = parts[1]
        filtro = parts[2] if len(parts) > 2 else "cartoes"
        page = int(parts[3]) if len(parts) > 3 else 0

        contas = database.listar_contas(chat_id, mes_ano, filtro_categoria="Cartão")
        pagas = [c for c in contas if c["pago"] == 1]
        
        if not pagas:
            await query.answer("Nenhuma conta paga para desmarcar.", show_alert=True)
            return

        await query.answer()
        markup = helpers.render_paid_accounts_keyboard(pagas, mes_ano, filtro=filtro, pagina=page)
        await query.edit_message_reply_markup(reply_markup=markup)

    # 5. ATUALIZAR MÊS ATUAL
    elif data.startswith("refresh:"):
        mes_ano = data.split(":")[1]
        await query.answer("🔄 Atualizado!")
        contas = database.listar_contas(chat_id, mes_ano)
        totais = database.obter_totais_mes(chat_id, mes_ano)
        texto, markup = helpers.render_contas_message(contas, totais, mes_ano)
        await safe_edit_message(query, texto, markup)

    # 5.1 ATUALIZAR ALERTAS
    elif data.startswith("alert_refresh:"):
        mes_ano = data.split(":")[1]
        await query.answer("🔄 Alertas atualizados!")
        alertas_data = database.obter_contas_alerta(chat_id, dias_antecedencia=5)
        texto, markup = helpers.render_alert_message(alertas_data, mes_ano)
        await safe_edit_message(query, texto, markup)

    # 6. GERAR CONTAS RECORRENTES
    elif data.startswith("gen_rec:"):
        parts = data.split(":")
        mes_ano = parts[1]
        filtro = parts[2] if len(parts) > 2 else "todos"
        page = int(parts[3]) if len(parts) > 3 else 0

        adicionadas = database.gerar_contas_recorrentes(chat_id, mes_ano)
        if adicionadas > 0:
            await query.answer(f"🔁 {adicionadas} conta(s) recorrente(s) gerada(s)!", show_alert=True)
        else:
            await query.answer("ℹ️ Nenhuma nova conta recorrente para gerar.", show_alert=True)

        f_cat = parse_cat_filtro(filtro)
        contas = database.listar_contas(chat_id, mes_ano, filtro_categoria=f_cat)
        totais = database.obter_totais_mes(chat_id, mes_ano, filtro_categoria=f_cat)
        texto, markup = helpers.render_contas_message(contas, totais, mes_ano, filtro=filtro, pagina=page)
        await safe_edit_message(query, texto, markup)

    # 7. AÇÃO NOVA CONTA
    elif data.startswith("action_new:"):
        mes_ano = data.split(":")[1]
        await query.answer()
        msg_escolha = (
            "➕ <b>COMO DESEJA CADASTRAR A CONTA?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Escolha o formato que preferir:\n\n"
            "1️⃣ <b>Passo a Passo:</b> O bot pergunta item por item (Nome, Valor, Dia, Recorrente, Categoria).\n"
            "2️⃣ <b>Comando Rápido:</b> Digite tudo em uma linha só (ex: <code>/nova Aluguel 1500 10 fixo</code>)."
        )
        await query.message.reply_text(
            msg_escolha,
            parse_mode=ParseMode.HTML,
            reply_markup=get_new_account_choice_markup(mes_ano),
        )

    # 7.1 WIZARD: COMANDO RÁPIDO
    elif data.startswith("wiz_quick:"):
        await query.answer()
        exemplo = (
            "⚡ <b>COMANDO RÁPIDO DE CADASTRO:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Envie uma mensagem no formato:\n"
            "<code>/nova &lt;descrição&gt; &lt;valor&gt; &lt;dia&gt; [recorrente] [fixo/cartao]</code>\n\n"
            "📝 <b>Exemplos prontos para copiar:</b>\n"
            "• <code>/nova Aluguel 1500 10 fixo</code>\n"
            "• <code>/nova Internet Fibra 120.50 15</code>\n"
            "• <code>/nova CT Nubank 1 20 cartao</code>\n"
            "• <code>/nova Luz Cemig 185 5</code>\n\n"
            "💡 <i>Dica: Se adicionar 'fixo', ela terá status de Conta Fixa de referência!</i>"
        )
        await query.message.reply_text(exemplo, parse_mode=ParseMode.HTML)

    # 7.2 WIZARD: CANCELAR
    elif data.startswith("wiz_cancel:"):
        await query.answer("Cancelado.")
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_text("❌ Cancelado.")

    # 7.3 WIZARD: INICIAR PASSO A PASSO
    elif data.startswith("wiz_start:"):
        mes_ano = data.split(":")[1]
        user_id = query.from_user.id
        nome_user = query.from_user.first_name or "Amigo"

        WIZARD_STATES[user_id] = {
            "step": "CONTA",
            "chat_id": chat_id,
            "mes_ano": mes_ano,
            "data": {},
        }
        await query.answer()
        msg_passo1 = (
            f"📝 <b>PASSO 1 DE 5 — CONTA:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Olá, {nome_user}!</i>\n\n"
            f"Digite o <b>NOME ou DESCRIÇÃO</b> da conta:\n"
            f"<i>(Ex: Aluguel, Luz, Internet, Cartão Nubank, Escola Levy)</i>\n\n"
            f"<i>Envie /cancelar para desistir a qualquer momento.</i>"
        )
        await query.message.reply_text(msg_passo1, parse_mode=ParseMode.HTML)

    # 7.4 WIZARD: RESPOSTA RECORRENTE (SIM / NÃO) -> VAI PARA PASSO 5 (CATEGORIA)
    elif data.startswith("wiz_rec_yes:") or data.startswith("wiz_rec_no:"):
        target_uid = int(data.split(":")[1])
        if query.from_user.id != target_uid:
            await query.answer("Apenas o usuário que iniciou o cadastro pode responder este botão.", show_alert=True)
            return

        if target_uid not in WIZARD_STATES:
            await query.answer("Sessão de cadastro expirada.", show_alert=True)
            return

        is_rec = 1 if "yes" in data else 0
        WIZARD_STATES[target_uid]["data"]["recorrente"] = is_rec
        WIZARD_STATES[target_uid]["step"] = "CATEGORIA"

        d = WIZARD_STATES[target_uid]["data"]
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔒 Fixo", callback_data=f"wiz_cat:Fixo:{target_uid}"),
                InlineKeyboardButton("💳 Cartão", callback_data=f"wiz_cat:Cartão:{target_uid}"),
                InlineKeyboardButton("📄 Geral / Outro", callback_data=f"wiz_cat:Geral:{target_uid}"),
            ],
            [
                InlineKeyboardButton("🚫 Cancelar", callback_data=f"wiz_cancel_btn:{target_uid}"),
            ]
        ])

        await query.answer()
        await query.message.reply_text(
            f"📁 <b>PASSO 5 DE 5 — CATEGORIA DA CONTA:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Conta: <b>{d['descricao']}</b>\n"
            f"💰 Valor: <code>{helpers.format_moeda(d['valor'])}</code>\n"
            f"📅 Vencimento: Todo dia {d['dia_vencimento']:02d}\n\n"
            f"Selecione a <b>CATEGORIA</b> da conta:\n"
            f"• 🔒 <b>Fixo:</b> Despesa fixa mensal de referência\n"
            f"• 💳 <b>Cartão:</b> Fatura de cartão de crédito\n"
            f"• 📄 <b>Geral:</b> Outras despesas e boletos diversos",
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )

    # 7.4.1 WIZARD: ESCOLHA DA CATEGORIA (FINALIZAÇÃO)
    elif data.startswith("wiz_cat:"):
        parts = data.split(":")
        cat = parts[1]
        target_uid = int(parts[2])

        if query.from_user.id != target_uid:
            await query.answer("Apenas o usuário que iniciou o cadastro pode responder este botão.", show_alert=True)
            return

        if target_uid not in WIZARD_STATES:
            await query.answer("Sessão de cadastro expirada.", show_alert=True)
            return

        session = WIZARD_STATES.pop(target_uid)
        d = session["data"]
        target_chat_id = session["chat_id"]
        target_mes_ano = session["mes_ano"]
        is_rec = d.get("recorrente", 0)

        database.adicionar_conta(
            chat_id=target_chat_id,
            descricao=d["descricao"],
            valor=d["valor"],
            dia_vencimento=d["dia_vencimento"],
            mes_ano=target_mes_ano,
            recorrente=is_rec,
            categoria=cat,
        )

        await query.answer("✅ Conta cadastrada com sucesso!")

        rec_txt = "✅ <b>SIM</b> (incluída automaticamente em todos os próximos meses)" if is_rec else "❌ <b>NÃO</b> (apenas neste mês)"
        confirm_msg = (
            f"🎉 <b>CONTA CADASTRADA COM SUCESSO!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>{d['descricao']}</b>\n"
            f"📁 Categoria: <b>{cat}</b>\n"
            f"💰 Valor: <code>{helpers.format_moeda(d['valor'])}</code>\n"
            f"📅 Vencimento: Dia {d['dia_vencimento']:02d} ({helpers.format_mes_extenso(target_mes_ano)})\n"
            f"🔁 Recorrente: {rec_txt}\n\n"
            f"<i>Abaixo está a lista atualizada com o checkbox:</i>"
        )
        await query.message.reply_text(confirm_msg, parse_mode=ParseMode.HTML)

        # Exibe checklist atualizado
        contas = database.listar_contas(target_chat_id, target_mes_ano)
        totais = database.obter_totais_mes(target_chat_id, target_mes_ano)
        texto, markup = helpers.render_contas_message(contas, totais, target_mes_ano)
        await query.message.reply_text(texto, parse_mode=ParseMode.HTML, reply_markup=markup)

    # 7.5 WIZARD: CANCELAR VIA BOTÃO
    elif data.startswith("wiz_cancel_btn:"):
        target_uid = int(data.split(":")[1])
        if query.from_user.id == target_uid and target_uid in WIZARD_STATES:
            del WIZARD_STATES[target_uid]
        await query.answer("Cadastro cancelado.")
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_text("❌ Cadastro cancelado.")

    # 7.6 AÇÃO EDITAR VALOR
    elif data.startswith("action_edit:"):
        parts = data.split(":")
        mes_ano = parts[1]
        filtro = parts[2] if len(parts) > 2 else "todos"
        page = int(parts[3]) if len(parts) > 3 else 0

        f_cat = parse_cat_filtro(filtro)
        contas = database.listar_contas(chat_id, mes_ano, filtro_categoria=f_cat)
        if not contas:
            await query.answer("Nenhuma conta para editar neste mês.", show_alert=True)
            return
        await query.answer()
        markup = helpers.render_edit_accounts_keyboard(contas, mes_ano, filtro=filtro, pagina=page)
        await safe_edit_message(query, "✏️ <b>Selecione qual conta deseja alterar o valor:</b>", markup)

    # 7.7 SELEÇÃO DE CONTA PARA EDIÇÃO
    elif data.startswith("sel_edit:"):
        parts = data.split(":")
        conta_id = int(parts[1])
        mes_ano = parts[2]
        filtro = parts[3] if len(parts) > 3 else "todos"
        page = int(parts[4]) if len(parts) > 4 else 0

        conta = database.obter_conta(conta_id)
        if not conta:
            await query.answer("Conta não encontrada.", show_alert=True)
            return

        user_id = query.from_user.id
        EDIT_STATES[user_id] = {
            "conta_id": conta_id,
            "chat_id": chat_id,
            "mes_ano": mes_ano,
            "filtro": filtro,
            "page": page,
            "descricao": conta["descricao"],
            "valor_atual": conta["valor"],
            "recorrente": conta.get("recorrente", 0),
        }

        await query.answer()
        msg_pedir_valor = (
            f"💰 <b>ALTERAR VALOR — {conta['descricao']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Valor Atual: <code>{helpers.format_moeda(conta['valor'])}</code>\n"
            f"Vencimento: Dia {conta['dia_vencimento']:02d}\n\n"
            f"Digite o <b>NOVO VALOR</b> em reais (R$):\n"
            f"<i>(Exemplos: 380 ou 380,50 ou 1200)</i>\n\n"
            f"<i>Envie /cancelar para desistir.</i>"
        )
        await query.message.reply_text(msg_pedir_valor, parse_mode=ParseMode.HTML)

    # 7.8 ESCOPO DE EDIÇÃO (APENAS ESTE MÊS OU TODOS OS PRÓXIMOS)
    elif data.startswith("edit_scope_single:") or data.startswith("edit_scope_all:"):
        parts = data.split(":")
        target_uid = int(parts[1])
        novo_valor = float(parts[2])

        if query.from_user.id != target_uid:
            await query.answer("Apenas quem iniciou a edição pode responder este botão.", show_alert=True)
            return

        if target_uid not in EDIT_STATES:
            await query.answer("Sessão de edição expirada.", show_alert=True)
            return

        edit_session = EDIT_STATES.pop(target_uid)
        conta_id = edit_session["conta_id"]
        descricao = edit_session["descricao"]
        valor_antigo = edit_session["valor_atual"]
        target_chat_id = edit_session["chat_id"]
        target_mes_ano = edit_session["mes_ano"]
        filtro = edit_session.get("filtro", "todos")
        page = edit_session.get("page", 0)
        is_all = "edit_scope_all" in data

        database.atualizar_valor_conta(conta_id, novo_valor, atualizar_futuros=is_all)
        await query.answer("✅ Valor atualizado!")

        escopo_txt = " (e em todos os próximos meses)" if is_all else " (apenas neste mês)"
        confirm_msg = (
            f"✅ <b>Valor atualizado com sucesso!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>{descricao}</b>\n"
            f"De: <s>{helpers.format_moeda(valor_antigo)}</s> ➡️ Para: <code>{helpers.format_moeda(novo_valor)}</code>{escopo_txt}\n\n"
            f"<i>Abaixo está a lista atualizada:</i>"
        )
        await query.message.reply_text(confirm_msg, parse_mode=ParseMode.HTML)

        f_cat = parse_cat_filtro(filtro)
        contas = database.listar_contas(target_chat_id, target_mes_ano, filtro_categoria=f_cat)
        totais = database.obter_totais_mes(target_chat_id, target_mes_ano, filtro_categoria=f_cat)
        texto, markup = helpers.render_contas_message(contas, totais, target_mes_ano, filtro=filtro, pagina=page)
        await query.message.reply_text(texto, parse_mode=ParseMode.HTML, reply_markup=markup)

    # 8. AÇÃO DE EXCLUIR
    elif data.startswith("action_del:"):
        parts = data.split(":")
        mes_ano = parts[1]
        filtro = parts[2] if len(parts) > 2 else "todos"
        page = int(parts[3]) if len(parts) > 3 else 0

        f_cat = parse_cat_filtro(filtro)
        contas = database.listar_contas(chat_id, mes_ano, filtro_categoria=f_cat)
        if not contas:
            await query.answer("Nenhuma conta para excluir.", show_alert=True)
            return
        await query.answer()
        markup = helpers.render_delete_accounts_keyboard(contas, mes_ano, filtro=filtro, pagina=page)
        await query.edit_message_reply_markup(reply_markup=markup)

    # 9. CONFIRMAÇÃO DE EXCLUSÃO
    elif data.startswith("confirm_del:"):
        parts = data.split(":")
        conta_id = int(parts[1])
        mes_ano = parts[2]
        filtro = parts[3] if len(parts) > 3 else "todos"
        page = int(parts[4]) if len(parts) > 4 else 0

        conta = database.obter_conta(conta_id)
        desc = conta["descricao"] if conta else "Conta"
        database.excluir_conta(conta_id)
        await query.answer(f"🗑️ '{desc}' excluída com sucesso!", show_alert=True)

        f_cat = parse_cat_filtro(filtro)
        contas = database.listar_contas(chat_id, mes_ano, filtro_categoria=f_cat)
        totais = database.obter_totais_mes(chat_id, mes_ano, filtro_categoria=f_cat)
        texto, markup = helpers.render_contas_message(contas, totais, mes_ano, filtro=filtro, pagina=page)
        await safe_edit_message(query, texto, markup)


async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerencia cliques nos botões do teclado persistente inferior e o fluxo Passo a Passo."""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    raw = update.message.text.strip()
    texto = raw.lower()

    # 1. Se o usuário estiver no fluxo PASSO A PASSO
    if user_id in WIZARD_STATES:
        state = WIZARD_STATES[user_id]

        if texto in ["/cancelar", "cancelar", "sair"]:
            del WIZARD_STATES[user_id]
            await update.message.reply_text("❌ Cadastro cancelado.")
            return

        # PASSO 1: CONTA
        if state["step"] == "CONTA":
            state["data"]["descricao"] = raw
            state["step"] = "VALOR"
            await update.message.reply_text(
                f"💰 <b>PASSO 2 DE 4 — VALOR:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 Conta: <b>{raw}</b>\n\n"
                f"Agora digite o <b>VALOR</b> em reais (R$):\n"
                f"<i>(Exemplos: 350 ou 1500,50 ou 120.00)</i>",
                parse_mode=ParseMode.HTML,
            )
            return

        # PASSO 2: VALOR
        elif state["step"] == "VALOR":
            clean_val = raw.replace("R$", "").replace("r$", "").replace(",", ".").strip()
            try:
                valor = float(clean_val)
                if valor <= 0:
                    await update.message.reply_text("❌ O valor deve ser maior que zero. Digite novamente:")
                    return
            except ValueError:
                await update.message.reply_text("❌ Valor inválido. Digite apenas o número (ex: 350 ou 1500,50):")
                return

            state["data"]["valor"] = valor
            state["step"] = "DIA"
            await update.message.reply_text(
                f"📅 <b>PASSO 3 DE 4 — DIA DO VENCIMENTO:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 Conta: <b>{state['data']['descricao']}</b>\n"
                f"💰 Valor: <code>{helpers.format_moeda(valor)}</code>\n\n"
                f"Agora digite o <b>DIA</b> do vencimento (1 a 31):\n"
                f"<i>(Exemplo: 10)</i>",
                parse_mode=ParseMode.HTML,
            )
            return

        # PASSO 3: DIA
        elif state["step"] == "DIA":
            try:
                dia = int(raw)
                if dia < 1 or dia > 31:
                    await update.message.reply_text("❌ O dia deve estar entre 1 e 31. Digite novamente:")
                    return
            except ValueError:
                await update.message.reply_text("❌ Dia inválido. Digite um número de 1 a 31 (ex: 10):")
                return

            state["data"]["dia_vencimento"] = dia
            state["step"] = "RECORRENTE"

            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ SIM, todo mês", callback_data=f"wiz_rec_yes:{user_id}"),
                    InlineKeyboardButton("❌ NÃO, só este mês", callback_data=f"wiz_rec_no:{user_id}"),
                ],
                [
                    InlineKeyboardButton("🚫 Cancelar", callback_data=f"wiz_cancel_btn:{user_id}"),
                ]
            ])

            await update.message.reply_text(
                f"🔁 <b>PASSO 4 DE 4 — CONTA RECORRENTE:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 Conta: <b>{state['data']['descricao']}</b>\n"
                f"💰 Valor: <code>{helpers.format_moeda(state['data']['valor'])}</code>\n"
                f"📅 Vencimento: Todo dia {dia:02d}\n\n"
                f"Essa conta é <b>RECORRENTE</b>?\n"
                f"<i>(Se clicar em SIM, ela será incluída automaticamente em todos os próximos meses!)</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
            return

    # 2. Se o usuário estiver no fluxo de EDIÇÃO DE VALOR
    if user_id in EDIT_STATES:
        state = EDIT_STATES[user_id]
        if texto in ["/cancelar", "cancelar", "sair"]:
            del EDIT_STATES[user_id]
            await update.message.reply_text("❌ Edição de valor cancelada.")
            return

        clean_val = raw.replace("R$", "").replace("r$", "").replace(",", ".").strip()
        try:
            novo_valor = float(clean_val)
            if novo_valor <= 0:
                await update.message.reply_text("❌ O valor deve ser maior que zero. Digite novamente:")
                return
        except ValueError:
            await update.message.reply_text("❌ Valor inválido. Digite apenas o número (ex: 380 ou 380,50):")
            return

        # Se a conta for recorrente, pergunta se deseja aplicar em todos os próximos meses
        if state.get("recorrente"):
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📌 Apenas este mês", callback_data=f"edit_scope_single:{user_id}:{novo_valor}"),
                    InlineKeyboardButton("🔁 Em todos os próximos meses", callback_data=f"edit_scope_all:{user_id}:{novo_valor}"),
                ],
                [
                    InlineKeyboardButton("🚫 Cancelar", callback_data=f"wiz_cancel_btn:{user_id}"),
                ]
            ])
            await update.message.reply_text(
                f"🔁 <b>A conta '{state['descricao']}' é recorrente!</b>\n\n"
                f"Novo Valor: <code>{helpers.format_moeda(novo_valor)}</code>\n\n"
                f"Como deseja aplicar a alteração?",
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
            return
        else:
            del EDIT_STATES[user_id]
            database.atualizar_valor_conta(state["conta_id"], novo_valor, atualizar_futuros=False)
            confirm_msg = (
                f"✅ <b>Valor atualizado com sucesso!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 <b>{state['descricao']}</b>\n"
                f"De: <s>{helpers.format_moeda(state['valor_atual'])}</s> ➡️ Para: <code>{helpers.format_moeda(novo_valor)}</code>\n\n"
                f"<i>Abaixo está a lista atualizada:</i>"
            )
            await update.message.reply_text(confirm_msg, parse_mode=ParseMode.HTML)
            contas = database.listar_contas(state["chat_id"], state["mes_ano"])
            totais = database.obter_totais_mes(state["chat_id"], state["mes_ano"])
            texto, markup = helpers.render_contas_message(contas, totais, state["mes_ano"])
            await update.message.reply_text(texto, parse_mode=ParseMode.HTML, reply_markup=markup)
            return

    # 3. Se não estiver em nenhum fluxo guiado, processa cliques nos botões do teclado e atalhos
    if texto in ["📋 contas do mês", "contas"]:
        await cmd_contas(update, context)
        return
    elif texto in ["🔒 contas fixas", "contas fixas", "fixos", "fixo"]:
        await cmd_fixos(update, context)
        return
    elif texto in ["📈 investimentos", "investimentos", "investimento", "consorcios", "consorcio"]:
        await cmd_investimentos(update, context)
        return
    elif texto in ["➕ nova conta", "nova conta"]:
        await cmd_nova(update, context)
        return
    elif texto in ["🔔 alertas de vencimento", "alertas", "alerta", "lembretes", "lembrete"]:
        await cmd_alertas(update, context)
        return
    elif texto in ["📊 resumo financeiro", "resumo"]:
        await cmd_resumo(update, context)
        return
    elif texto in ["🔁 gerar recorrentes", "gerar recorrentes"]:
        await cmd_gerar(update, context)
        return
    elif raw.startswith("/nova ") or raw.startswith("nova "):
        await cmd_nova(update, context)
        return
    elif raw.startswith("/editar ") or raw.startswith("editar "):
        await cmd_editar(update, context)
        return

    # 4. Interceptação de valor numérico direto no chat (ex: 50, 120.00, R$ 35,50, 1.500,00)
    val_cleaned = raw.replace("R$", "").replace("r$", "").strip()
    val_cleaned = val_cleaned.replace(".", "").replace(",", ".") if "," in val_cleaned else val_cleaned
    try:
        val_float = float(val_cleaned)
        if val_float > 0:
            chat_id = get_target_chat_id(update)
            mes_ano = helpers.get_current_mes_ano()
            fixos = database.listar_contas(chat_id, mes_ano, filtro_categoria="Fixo")
            if fixos:
                markup = helpers.render_choose_category_keyboard(val_float, mes_ano, fixos)
                await update.message.reply_text(
                    f"💰 <b>LANÇAMENTO: {helpers.format_moeda(val_float)}</b>\n\n"
                    f"Onde deseja acrescentar ou alterar esse valor?\n"
                    f"<i>Clique na categoria abaixo:</i>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=markup,
                )
                return
    except ValueError:
        pass


def main():
    if not config.BOT_TOKEN:
        print("[ERRO FATAL] TELEGRAM_BOT_TOKEN não configurado no arquivo .env!")
        sys.exit(1)

    print("=" * 60)
    print(" 🚀 INICIANDO BOT DE GERENCIAMENTO DE CONTAS TELEGRAM")
    print(f" Token: {config.BOT_TOKEN[:10]}... (configurado)")
    if config.GROUP_ID:
        print(f" Grupo Autorizado: {config.GROUP_ID}")
    print("=" * 60)

    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # Handlers de comandos
    app.add_handler(CommandHandler(["start", "ajuda", "help"], cmd_start))
    app.add_handler(CommandHandler(["contas", "mes"], cmd_contas))
    app.add_handler(CommandHandler(["fixos", "fixo"], cmd_fixos))
    app.add_handler(CommandHandler(["investimentos", "investimento", "invest", "consorcios", "consorcio"], cmd_investimentos))
    app.add_handler(CommandHandler(["nova", "add", "adicionar"], cmd_nova))
    app.add_handler(CommandHandler(["editar", "edit", "alterar"], cmd_editar))
    app.add_handler(CommandHandler(["alertas", "alerta", "lembretes", "lembrete"], cmd_alertas))
    app.add_handler(CommandHandler(["resumo", "balanco"], cmd_resumo))
    app.add_handler(CommandHandler(["gerar", "recorrentes"], cmd_gerar))
    app.add_handler(CommandHandler(["excluir", "deletar", "remover"], cmd_excluir))

    # Handler de cliques nos botões inline (Checkboxes e ações)
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Handler de texto do teclado fixo
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    # Agendamento diário automático às 09:00
    if app.job_queue:
        try:
            tz = zoneinfo.ZoneInfo(config.TIMEZONE)
            horario_alerta = datetime.time(hour=9, minute=0, tzinfo=tz)
            app.job_queue.run_daily(
                scheduled_daily_alert,
                time=horario_alerta,
                name="alerta_diario_vencimentos",
            )
            print(f"⏰ Alerta automático diário agendado para 09:00 ({config.TIMEZONE})")
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível agendar alerta diário: {e}")

    print("✅ Bot iniciado com sucesso e aguardando comandos no Telegram...")
    app.run_polling()


if __name__ == "__main__":
    main()
