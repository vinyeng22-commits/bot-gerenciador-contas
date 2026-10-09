# 💳 Projeto 02: Bot de Gerenciamento de Contas no Telegram

Bot inteligente para controle financeiro e gerenciamento de contas a pagar no Telegram (`@conas2026_bot`).

Quando solicitado no grupo ou em chat privado, o bot envia o **checklist de contas do mês** com botões interativos de **checkbox**. Ao marcar uma conta como paga, ela é **automaticamente movida para o final da lista**, tachada e sinalizada com ✅ e data do pagamento, recalculando os totais em tempo real sem poluir o chat!

---

## 🚀 Principais Funcionalidades

1. **Checklist Interativo com Checkbox**:
   - Cada conta pendente possui um botão `[ ⬜ Pagar: Nome (R$ Valor) ]`.
   - Ao clicar, o bot edita a mensagem no mesmo lugar (sem enviar novas mensagens repetidas).
2. **Reorganização Automática (Pagas ao Final)**:
   - Contas não pagas ficam no topo, ordenadas pelo dia de vencimento.
   - Assim que uma conta é marcada como paga, ela vai para a seção **PAGAS no final da lista**.
3. **Totais e Balanço em Tempo Real**:
   - Exibe o valor total a pagar (pendente), total já pago e total geral do mês.
4. **Contas Recorrentes / Fixas**:
   - Cadastre despesas recorrentes (ex: Aluguel, Internet, Condomínio) e gere automaticamente todo início de mês com um clique (`/gerar`).
5. **Navegação de Meses**:
   - Botões interativos `[ ⬅️ Mês Ant. ]` e `[ Mês Seg. ➡️ ]` para consultar ou lançar despesas de outros meses.
6. **Desfazer / Desmarcar**:
   - Se marcar uma conta por engano, você pode desmarcá-la e ela volta instantaneamente para a seção de pendentes.
7. **Banco de Dados SQLite**:
   - Todos os dados ficam salvos de forma segura em `contas.db`, persistindo mesmo se o bot for reiniciado.
8. **Alertas Automáticos de Vencimento**:
   - Envio diário automático às **09:00** no grupo com resumo de contas vencendo hoje, nos próximos dias e atrasadas.
   - Botões inline de baixa rápida para pagar direto na notificação.
   - Pode ser consultado a qualquer momento com `/alertas` ou no botão `🔔 Alertas de Vencimento`.

---

## 🤖 Comandos do Bot

| Comando | Descrição | Exemplo |
|---|---|---|
| `/contas` | Exibe a lista interativa com os checkboxes do mês atual | `/contas` ou `/contas 11` |
| `/nova` | Adiciona uma nova conta (passo a passo ou comando rápido) | `/nova Aluguel 1500 10 recorrente` |
| `/alertas` | Exibe o relatório de contas vencendo hoje, em breve ou atrasadas | `/alertas` ou clique em `🔔 Alertas de Vencimento` |
| `/resumo` | Exibe o resumo financeiro detalhado com porcentagem paga | `/resumo` |
| `/gerar` | Gera as contas recorrentes para o mês atual | `/gerar` |
| `/excluir` | Abre o menu com botões para apagar uma conta | `/excluir` |
| `/ajuda` | Mostra as instruções de uso e atalhos | `/ajuda` |

### 📝 Duas Formas de Cadastrar Novas Contas:

1. **✍️ Modo Passo a Passo (Guiado):**
   - Ao clicar no botão **`➕ Nova Conta`** ou digitar **/nova**, escolha **`Passo a Passo`**.
   - O bot fará perguntas sequenciais e aguardará cada resposta:
     - **CONTA:** Digite o nome da conta (ex: `Aluguel`)
     - **VALOR:** Digite o valor (ex: `1500`)
     - **DIA:** Digite o dia do vencimento (ex: `10`)
     - **RECORRENTE:** Clique nos botões **`[ ✅ SIM ]`** ou **`[ ❌ NÃO ]`**
   - Se escolher **SIM**, a conta é **automaticamente replicada para todos os próximos meses**!

2. **⚡ Modo Comando Rápido:**
   ```text
   /nova <Nome da Conta> <Valor> <Dia do Vencimento> [recorrente]
   ```
   Exemplos prontos:
   - `/nova Internet Fibra 120.50 15`
   - `/nova Aluguel 1500 10 recorrente`
   - `/nova Cartão de Crédito 850,90 20`
   - `/nova Conta de Luz 185 5`

---

## 👥 Como Adicionar ao Grupo Telegram

1. Abra o seu grupo no Telegram.
2. Adicione o bot como membro pesquisando por: **`@conas2026_bot`**.
3. **Recomendado**: Dê permissão de Administrador ao bot (ou no `@BotFather`, envie `/setprivacy` -> selecione `@conas2026_bot` -> escolha `Disable` para que ele possa ler todos os comandos no grupo).
4. Envie `/contas` ou `/start` no grupo!

---

## 🌐 Como Executar na Web / Streamlit Cloud

### Opção 1: Localmente
- Dê dois cliques em [**`iniciar_painel_web.bat`**](./iniciar_painel_web.bat) ou execute:
  ```powershell
  streamlit run app.py
  ```
- O painel abrirá automaticamente no navegador em `http://localhost:8501`, e o bot do Telegram iniciará junto em segundo plano.

### Opção 2: 100% na Nuvem (Streamlit Cloud 24/7)
1. Acesse [share.streamlit.io](https://share.streamlit.io).
2. Conecte com sua conta GitHub.
3. Selecione o repositório `bot-gerenciador-contas`, branch `main`, arquivo principal `app.py`.
4. Em **Advanced Settings > Secrets**, adicione:
   ```toml
   TELEGRAM_BOT_TOKEN = "seu_token_aqui"
   TELEGRAM_GROUP_ID = "seu_id_do_grupo"
   TIMEZONE = "America/Sao_Paulo"
   ```
5. Clique em **Deploy**! O painel web e o bot Telegram rodarão na nuvem.

---

## 💻 Como Iniciar o Bot pelo Terminal (Apenas Bot)

```powershell
python bot.py
```

---

## 📁 Estrutura de Arquivos

```text
02-GERENCIADOR-CONTAS/
├── app.py                      # Painel Web interativo Streamlit + background runner do bot
├── bot.py                      # Bot do Telegram (handlers, botões inline, automação)
├── database.py                 # Camada SQLite (CRUD de contas, totais e categorias)
├── helpers.py                  # Formatação de mensagens, moedas e teclados inline
├── config.py                   # Configuração e leitura de variáveis (.env e st.secrets)
├── atualizar_banco_e_dados.py  # Estrutura base de cartões, fixos e investimentos
├── requirements.txt            # Dependências (streamlit, python-telegram-bot, etc.)
├── .streamlit/config.toml      # Configuração de tema e servidor do Streamlit
├── .env.example                # Modelo de variáveis de ambiente
├── iniciar_bot.bat             # Atalho para rodar apenas o bot
├── iniciar_painel_web.bat      # Atalho para rodar painel Streamlit local
└── README.md                   # Documentação do projeto
```
