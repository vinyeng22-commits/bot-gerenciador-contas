"""
Painel Web Streamlit — Gerenciador Financeiro & Host do Bot Telegram
Permite visualizar e gerenciar contas, faturas e investimentos pela web,
além de manter o Bot do Telegram rodando em segundo plano na nuvem.
"""

import os
import sys
import subprocess
import datetime
import pandas as pd
import streamlit as st

# Configurações do Streamlit
st.set_page_config(
    page_title="Gerenciador Financeiro — Telegram Bot",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

import config
import database
import helpers

# ==========================================
# 1. GERENCIADOR DO PROCESSO DO BOT
# ==========================================
@st.cache_resource
def iniciar_bot_em_background():
    """
    Inicia o bot do Telegram em segundo plano como subprocesso independente.
    O decorador @st.cache_resource garante que o bot seja iniciado APENAS UMA VEZ
    e continue rodando mesmo quando a página do Streamlit for atualizada.
    """
    caminho_bot = os.path.join(os.path.dirname(__file__), "bot.py")
    cmd = [sys.executable, "-X", "utf8", caminho_bot]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        return proc
    except Exception as e:
        st.sidebar.error(f"Erro ao iniciar processo do Bot: {e}")
        return None

# Inicia o bot
bot_proc = iniciar_bot_em_background()

# ==========================================
# 2. AUTENTICAÇÃO DE ACESSO
# ==========================================
AUTH_USER = st.secrets.get("ADMIN_USER", "admin") if hasattr(st, "secrets") and "ADMIN_USER" in st.secrets else os.getenv("ADMIN_USER", "admin")
AUTH_PASS = str(st.secrets.get("ADMIN_PASSWORD", "32166137") if hasattr(st, "secrets") and "ADMIN_PASSWORD" in st.secrets else os.getenv("ADMIN_PASSWORD", "32166137"))

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.image("https://cdn-icons-png.flaticon.com/512/2344/2344132.png", width=64)
        st.title("Acesso Restrito")
        st.caption("Painel de Controle Financeiro & Bot Telegram")

        with st.form("form_login", clear_on_submit=False):
            usuario_input = st.text_input("👤 Usuário:", placeholder="Digite o usuário")
            senha_input = st.text_input("🔑 Senha:", type="password", placeholder="Digite a senha")
            btn_login = st.form_submit_button("Entrar no Painel", use_container_width=True)

            if btn_login:
                if usuario_input.strip() == AUTH_USER and senha_input.strip() == AUTH_PASS:
                    st.session_state["autenticado"] = True
                    st.success("✅ Autenticado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos.")

        st.info("🔒 Informe seu usuário e senha autorizados para acessar o sistema.")
    st.stop()

# ==========================================
# 3. BARRA LATERAL (SIDEBAR)
# ==========================================
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2344/2344132.png", width=70)
st.sidebar.title("Gerenciador de Contas")

# Status do Bot
if bot_proc and bot_proc.poll() is None:
    st.sidebar.success("🟢 Bot Telegram: **Online**")
    st.sidebar.caption(f"PID: `{bot_proc.pid}` | Polling ativo")
else:
    st.sidebar.error("🔴 Bot Telegram: **Parado**")
    if st.sidebar.button("🔄 Reiniciar Bot"):
        st.cache_resource.clear()
        st.rerun()

st.sidebar.markdown(f"👤 Logado como: **{AUTH_USER}**")
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
    st.session_state["autenticado"] = False
    st.rerun()

st.sidebar.markdown("---")

# Seletor de Mês e Ano
mes_atual = datetime.datetime.now().month
ano_atual = datetime.datetime.now().year

meses_opcoes = {
    1: "01 — Janeiro", 2: "02 — Fevereiro", 3: "03 — Março",
    4: "04 — Abril", 5: "05 — Maio", 6: "06 — Junho",
    7: "07 — Julho", 8: "08 — Agosto", 9: "09 — Setembro",
    10: "10 — Outubro", 11: "11 — Novembro", 12: "12 — Dezembro"
}

sel_mes = st.sidebar.selectbox("📅 Selecione o Mês:", list(meses_opcoes.keys()), index=mes_atual - 1, format_func=lambda x: meses_opcoes[x])
sel_ano = st.sidebar.number_input("Ano:", min_value=2024, max_value=2035, value=ano_atual, step=1)

mes_ano_ref = f"{sel_ano}-{sel_mes:02d}"
chat_id = config.TELEGRAM_GROUP_ID if config.TELEGRAM_GROUP_ID else "-1003987623111"

st.sidebar.markdown("---")
st.sidebar.markdown("### 📱 Comandos no Telegram")
st.sidebar.markdown(
    """
    - `/contas` — Faturas e Cartões
    - `/fixos` — Fixos e Variáveis
    - `/investimentos` — Consórcios
    - `/resumo` — Balanço Financeiro
    - `/alertas` — Vencimentos próximos
    """
)

# ==========================================
# 3. DADOS E MÉTRICAS PRINCIPAIS
# ==========================================
totais = database.obter_totais_mes(chat_id, mes_ano_ref)
contas_cartoes = database.listar_contas(chat_id, mes_ano_ref, filtro_categoria="Cartão")
contas_fixos = database.listar_contas(chat_id, mes_ano_ref, filtro_categoria="Fixo")
contas_invest = database.listar_contas(chat_id, mes_ano_ref, filtro_categoria="Investimento")

st.title(f"📊 Painel Financeiro — {helpers.format_mes_extenso(mes_ano_ref)}")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="💰 Total Comprometido",
        value=helpers.format_moeda(totais.get("total_geral_comprometido", 0.0)),
        help="Soma de faturas de cartão + fixos/variáveis lançados + investimentos lançados",
    )

with col2:
    st.metric(
        label="💳 Faturas de Cartão",
        value=helpers.format_moeda(totais.get("total_cartoes", 0.0)),
        delta=f"{totais.get('qtd_cartoes_pagos', 0)}/{totais.get('qtd_cartoes', 0)} pagas",
    )

with col3:
    st.metric(
        label="🔒 Fixos & Variáveis",
        value=helpers.format_moeda(totais.get("total_fixos_lancado", 0.0)),
        delta=f"Meta: {helpers.format_moeda(totais.get('total_fixos_referencia', 0.0))}",
    )

with col4:
    st.metric(
        label="📈 Investimentos (Consórcios)",
        value=helpers.format_moeda(totais.get("total_invest_lancado", 0.0)),
        delta=f"Ref: {helpers.format_moeda(totais.get('total_invest_referencia', 0.0))}",
    )

st.markdown("---")

# ==========================================
# 4. ABAS DE VISUALIZAÇÃO E AÇÕES
# ==========================================
tab_cartoes, tab_fixos, tab_invest, tab_novo_lancamento, tab_nova_conta = st.tabs([
    "💳 Faturas de Cartão",
    "🔒 Contas Fixas & Variáveis",
    "📈 Investimentos",
    "➕ Lançar Valor Rápido",
    "📝 Cadastrar Conta",
])

# ------------------------------------------
# TAB 1: CARTÕES DE CRÉDITO
# ------------------------------------------
with tab_cartoes:
    st.subheader(f"💳 Faturas de Cartões — {helpers.format_mes_extenso(mes_ano_ref)}")
    if not contas_cartoes:
        st.info("Nenhuma fatura cadastrada para este mês.")
    else:
        # Prepara dados para exibição
        dados_cartoes = []
        for c in contas_cartoes:
            dados_cartoes.append({
                "ID": c["id"],
                "Status": "✅ Pago" if c["pago"] else "⏳ Pendente",
                "Descrição": c["descricao"],
                "Vencimento": f"Dia {c['dia_vencimento']:02d}",
                "Valor": helpers.format_moeda(c["valor"]),
                "Data Pagamento": c.get("data_pagamento") or "—",
            })
        df_c = pd.DataFrame(dados_cartoes)
        st.dataframe(df_c[["Status", "Descrição", "Vencimento", "Valor", "Data Pagamento"]], use_container_width=True)

        st.markdown("#### ⚡ Ações Rápidas de Pagamento:")
        cols_botoes = st.columns(3)
        for idx, c in enumerate(contas_cartoes):
            col_target = cols_botoes[idx % 3]
            with col_target:
                label_btn = f"{'✅ Desmarcar' if c['pago'] else '⬜ Pagar'}: {c['descricao']} ({helpers.format_moeda(c['valor'])})"
                if st.button(label_btn, key=f"pay_c_{c['id']}"):
                    database.alternar_status_pago(c["id"])
                    st.rerun()

# ------------------------------------------
# TAB 2: CONTAS FIXAS & VARIÁVEIS
# ------------------------------------------
with tab_fixos:
    st.subheader(f"🔒 Contas Fixas e Gastos Variáveis — {helpers.format_mes_extenso(mes_ano_ref)}")

    nomes_fixos = {'ALUGUEL', 'MESADAS', 'CONDUÇÃO LEVY', 'BANCA GABRIEL', 'FUTEBOL', 'NATAÇÃO', 'ACORDO CONDOMINIO'}
    lista_fixos_valor = [c for c in contas_fixos if c["descricao"].strip().upper() in nomes_fixos]
    lista_variaveis = [c for c in contas_fixos if c["descricao"].strip().upper() not in nomes_fixos]

    col_fix1, col_fix2 = st.columns(2)

    with col_fix1:
        st.markdown(f"#### 🔒 Contas com Valor e Data Fixa ({len(lista_fixos_valor)})")
        if lista_fixos_valor:
            df_fix = pd.DataFrame([{
                "Conta": helpers.get_short_name(c["descricao"]),
                "Vencimento": f"Dia {c['dia_vencimento']:02d}",
                "Valor": helpers.format_moeda(c["valor"]),
            } for c in lista_fixos_valor])
            st.dataframe(df_fix, use_container_width=True)

    with col_fix2:
        st.markdown(f"#### 📊 Despesas Variáveis / Acumuladas ({len(lista_variaveis)})")
        if lista_variaveis:
            df_var = pd.DataFrame([{
                "Categoria": helpers.get_short_name(c["descricao"]),
                "Gasto Atual": helpers.format_moeda(c["valor"]),
                "Teto / Ref": helpers.format_moeda(c.get("valor_referencia", 0.0)),
                "Vencimento": f"Dia {c['dia_vencimento']:02d}" if c['dia_vencimento'] > 1 else "Dia 01",
            } for c in lista_variaveis])
            st.dataframe(df_var, use_container_width=True)

    if st.button("🔄 Zerar Lançamentos de Fixos do Mês", help="Zera as variáveis e restaura fixos com valor padrão"):
        qtd = database.zerar_mes_fixos(chat_id, mes_ano_ref)
        st.success(f"{qtd} contas/categorias resetadas com sucesso!")
        st.rerun()

# ------------------------------------------
# TAB 3: INVESTIMENTOS (CONSÓRCIOS)
# ------------------------------------------
with tab_invest:
    st.subheader(f"📈 Consórcios e Investimentos — {helpers.format_mes_extenso(mes_ano_ref)}")
    if not contas_invest:
        st.info("Nenhum consórcio/investimento cadastrado.")
    else:
        df_inv = pd.DataFrame([{
            "Consórcio": helpers.get_short_name(c["descricao"]),
            "Vencimento": f"Dia {c['dia_vencimento']:02d}",
            "Valor Lançado": helpers.format_moeda(c["valor"]),
            "Parcela Prevista (Ref)": helpers.format_moeda(c.get("valor_referencia", 0.0)),
        } for c in contas_invest])
        st.dataframe(df_inv, use_container_width=True)

    if st.button("🔄 Zerar Lançamentos de Consórcios", help="Zera os valores acumulados em consórcios"):
        qtd = database.zerar_mes_investimentos(chat_id, mes_ano_ref)
        st.success(f"{qtd} consórcios zerados com sucesso!")
        st.rerun()

# ------------------------------------------
# TAB 4: LANÇAR VALOR RÁPIDO
# ------------------------------------------
with tab_novo_lancamento:
    st.subheader("💰 Lançar Gasto em uma Categoria ou Consórcio")
    st.caption("Insira o valor que deseja somar na categoria (idêntico ao lançamento pelo Telegram).")

    todas_categorias = contas_fixos + contas_invest
    opcoes_cat = {c["id"]: f"{helpers.get_short_name(c['descricao'])} (Atual: {helpers.format_moeda(c['valor'])})" for c in todas_categorias}

    with st.form("form_add_valor"):
        conta_sel_id = st.selectbox("Selecione a Categoria:", list(opcoes_cat.keys()), format_func=lambda x: opcoes_cat[x])
        val_add = st.number_input("Valor a Adicionar (R$):", min_value=0.01, step=10.0, format="%.2f")
        sub_add = st.form_submit_button("➕ Lançar Valor")

        if sub_add and val_add > 0:
            res = database.acrescentar_valor_fixo(conta_sel_id, val_add)
            if res:
                st.success(f"Adicionado {helpers.format_moeda(val_add)} em {res['descricao']}! Novo total: {helpers.format_moeda(res['valor'])}")
                st.rerun()
            else:
                st.error("Erro ao registrar lançamento.")

# ------------------------------------------
# TAB 5: CADASTRAR NOVA CONTA
# ------------------------------------------
with tab_nova_conta:
    st.subheader("📝 Cadastrar Nova Conta / Despesa")
    with st.form("form_nova_conta"):
        nome_conta = st.text_input("Nome da Conta / Despesa:", placeholder="Ex: Academia, Dentista...")
        col_n1, col_n2, col_n3 = st.columns(3)
        with col_n1:
            val_conta = st.number_input("Valor (R$):", min_value=0.0, step=10.0, format="%.2f")
        with col_n2:
            dia_venc = st.number_input("Dia do Vencimento:", min_value=1, max_value=31, value=10, step=1)
        with col_n3:
            categoria_sel = st.selectbox("Categoria:", ["Fixo", "Cartão", "Investimento", "Geral"])

        rec_check = st.checkbox("Recorrente (repetir automaticamente nos próximos meses)", value=True)
        sub_nova = st.form_submit_button("✅ Cadastrar Conta")

        if sub_nova:
            if not nome_conta.strip():
                st.error("Por favor, informe o nome da conta.")
            else:
                cid = database.adicionar_conta(
                    chat_id=chat_id,
                    descricao=nome_conta.strip(),
                    valor=val_conta,
                    dia_vencimento=dia_venc,
                    mes_ano=mes_ano_ref,
                    recorrente=1 if rec_check else 0,
                    categoria=categoria_sel,
                )
                st.success(f"Conta '{nome_conta}' cadastrada com sucesso (ID: {cid})!")
                st.rerun()
