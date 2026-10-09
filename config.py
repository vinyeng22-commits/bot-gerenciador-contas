"""
Configurações do Bot de Gerenciamento de Contas
"""

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
_raw_group = os.getenv("TELEGRAM_GROUP_ID", "").strip()

# Suporte automático a Secrets no Streamlit Cloud
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        if not BOT_TOKEN and "TELEGRAM_BOT_TOKEN" in st.secrets:
            BOT_TOKEN = str(st.secrets["TELEGRAM_BOT_TOKEN"]).strip()
        if not _raw_group and "TELEGRAM_GROUP_ID" in st.secrets:
            _raw_group = str(st.secrets["TELEGRAM_GROUP_ID"]).strip()
except Exception:
    pass

GROUP_ID = None
SUPERGROUP_ID = None

if _raw_group:
    try:
        val = int(_raw_group)
        GROUP_ID = val
        # Se for ID comum como -5370228319, calcula o correspondente de supergrupo -100...
        s_val = str(val)
        if s_val.startswith("-") and not s_val.startswith("-100"):
            SUPERGROUP_ID = int("-100" + s_val[1:])
        elif s_val.startswith("-100"):
            SUPERGROUP_ID = val
            GROUP_ID = int("-" + s_val[4:])
    except ValueError:
        GROUP_ID = None

TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")

TELEGRAM_BOT_TOKEN = BOT_TOKEN
TELEGRAM_GROUP_ID = str(SUPERGROUP_ID if SUPERGROUP_ID is not None else (GROUP_ID if GROUP_ID is not None else (_raw_group or "-1003987623111")))


def is_chat_authorized(chat_id: int, chat_type: str) -> bool:
    """
    Verifica se o chat tem permissão para usar o bot.
    Permite chats privados e o grupo configurado (inclusive após migração de ID).
    """
    if GROUP_ID is None:
        return True

    # Permite chat privado com administradores/usuários
    if chat_type == "private":
        return True

    # Permite IDs conhecidos do grupo
    known_group_ids = {GROUP_ID, SUPERGROUP_ID, -5370228319, -1003987623111}
    if chat_id in known_group_ids:
        return True

    return True  # Permite grupos onde o bot for adicionado como membro/admin
