import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "contas.db")
try:
    from config import TELEGRAM_GROUP_ID
    CHAT_ID = TELEGRAM_GROUP_ID if TELEGRAM_GROUP_ID else os.getenv("TELEGRAM_GROUP_ID", "-1003987623111")
except Exception:
    CHAT_ID = os.getenv("TELEGRAM_GROUP_ID", "-1003987623111")


MES_ANO = "2026-10"

# 11 Cartões de Crédito (Faturas do Mês)
CARTOES = [
    ("CT C6", 1, 23.00),
    ("CT RecargaPay vi", 6, 1.00),
    ("CT MERC PAGO", 10, 1.00),
    ("CT INTER", 11, 1.00),
    ("CT NUBANK", 14, 1.00),
    ("CT BANESE", 15, 1.00),
    ("CT CAIXA", 15, 1.00),
    ("CT BRBCARD", 17, 1.00),
    ("CT CLICK", 20, 1.00),
    ("CT PICPAY", 20, 1.00),
    ("CT BRADESCO", 28, 1.00),
]

# 6 Investimentos / Consórcios (Dia 10, Categoria 'Investimento', Iniciam em 0.00 com referência)
INVESTIMENTOS = [
    ("CONS 01 (VI) HS100", 10, 0.00, 345.00),
    ("CONS 02 (VI) HS200", 10, 0.00, 615.00),
    ("CONS 03 (VI) Rodob100", 10, 0.00, 610.00),
    ("CONS 04 (RO) HS100", 10, 0.00, 1.00),
    ("CONS 05 (RO) HS100", 10, 0.00, 1.00),
    ("CONS 06 (CILA) HS100", 10, 0.00, 1.00),
]

# 7 Contas Fixas com Valor e Data Fixa (Categoria 'Fixo', valor preenchido)
FIXOS_VALOR_DATA_FIXA = [
    ("ALUGUEL", 5, 400.00, 400.00),
    ("MESADAS", 5, 100.00, 100.00),
    ("CONDUÇÃO LEVY", 5, 550.00, 550.00),
    ("BANCA GABRIEL", 10, 100.00, 100.00),
    ("FUTEBOL", 10, 140.00, 140.00),
    ("NATAÇÃO", 10, 100.00, 100.00),
    ("ACORDO CONDOMINIO", 10, 1750.00, 1750.00),
]

# 14 Contas Variáveis / Acumuladoras (Categoria 'Fixo', iniciam em 0.00 no mês)
FIXOS_VARIAVEIS = [
    ("LANCHE/ALMOÇO LEVY", 1, 0.00, 400.00),
    ("LANCHE GABRIEL", 1, 0.00, 200.00),
    ("COMBUSTIVEL", 1, 0.00, 600.00),
    ("MERCADO CASAS", 1, 0.00, 1500.00),
    ("ALMOÇO", 1, 0.00, 400.00),
    ("AGUA", 1, 0.00, 150.00),
    ("FAXINA", 1, 0.00, 500.00),
    ("DIZIMO/OFERTA", 1, 0.00, 1000.00),
    ("CELULARES", 1, 0.00, 100.00),
    ("ENTRETENIMENTO", 1, 0.00, 500.00),
    ("EMBASA", 10, 0.00, 120.00),
    ("ESCOLA LEVY", 10, 0.00, 400.00),
    ("TEL/INTERN", 10, 0.00, 130.00),
    ("LIGHT", 11, 0.00, 350.00),
]

def migrar_e_popular():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Adiciona coluna valor_referencia se não existir
    cols_contas = [c[1] for c in cursor.execute("PRAGMA table_info(contas)").fetchall()]
    if "valor_referencia" not in cols_contas:
        cursor.execute("ALTER TABLE contas ADD COLUMN valor_referencia REAL DEFAULT 0.0")
        print("Coluna valor_referencia adicionada em contas.")

    cols_rec = [c[1] for c in cursor.execute("PRAGMA table_info(recorrentes)").fetchall()]
    if "valor_referencia" not in cols_rec:
        cursor.execute("ALTER TABLE recorrentes ADD COLUMN valor_referencia REAL DEFAULT 0.0")
        print("Coluna valor_referencia adicionada em recorrentes.")

    # Limpa base para aplicar nova estrutura
    cursor.execute("DELETE FROM contas")
    cursor.execute("DELETE FROM recorrentes")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('contas', 'recorrentes')")

    # 1. Inserir Cartões
    for desc, dia, val in CARTOES:
        cursor.execute(
            """
            INSERT INTO contas (chat_id, descricao, valor, dia_vencimento, mes_ano, pago, recorrente, categoria, valor_referencia)
            VALUES (?, ?, ?, ?, ?, 0, 1, 'Cartão', ?)
            """,
            (CHAT_ID, desc, val, dia, MES_ANO, val),
        )
        cursor.execute(
            """
            INSERT INTO recorrentes (chat_id, descricao, valor, dia_vencimento, categoria, ativo, valor_referencia)
            VALUES (?, ?, ?, ?, 'Cartão', 1, ?)
            """,
            (CHAT_ID, desc, val, dia, val),
        )

    # 2. Inserir Investimentos / Consórcios
    for desc, dia, val, val_ref in INVESTIMENTOS:
        cursor.execute(
            """
            INSERT INTO contas (chat_id, descricao, valor, dia_vencimento, mes_ano, pago, recorrente, categoria, valor_referencia)
            VALUES (?, ?, ?, ?, ?, 0, 1, 'Investimento', ?)
            """,
            (CHAT_ID, desc, val, dia, MES_ANO, val_ref),
        )
        cursor.execute(
            """
            INSERT INTO recorrentes (chat_id, descricao, valor, dia_vencimento, categoria, ativo, valor_referencia)
            VALUES (?, ?, ?, ?, 'Investimento', 1, ?)
            """,
            (CHAT_ID, desc, val, dia, val_ref),
        )

    # 3. Inserir Contas com Valor e Data Fixa
    for desc, dia, val, val_ref in FIXOS_VALOR_DATA_FIXA:
        cursor.execute(
            """
            INSERT INTO contas (chat_id, descricao, valor, dia_vencimento, mes_ano, pago, recorrente, categoria, valor_referencia)
            VALUES (?, ?, ?, ?, ?, 0, 1, 'Fixo', ?)
            """,
            (CHAT_ID, desc, val, dia, MES_ANO, val_ref),
        )
        cursor.execute(
            """
            INSERT INTO recorrentes (chat_id, descricao, valor, dia_vencimento, categoria, ativo, valor_referencia)
            VALUES (?, ?, ?, ?, 'Fixo', 1, ?)
            """,
            (CHAT_ID, desc, val, dia, val_ref),
        )

    # 4. Inserir Contas Variáveis / Acumuladoras
    for desc, dia, val, val_ref in FIXOS_VARIAVEIS:
        cursor.execute(
            """
            INSERT INTO contas (chat_id, descricao, valor, dia_vencimento, mes_ano, pago, recorrente, categoria, valor_referencia)
            VALUES (?, ?, ?, ?, ?, 0, 1, 'Fixo', ?)
            """,
            (CHAT_ID, desc, val, dia, MES_ANO, val_ref),
        )
        cursor.execute(
            """
            INSERT INTO recorrentes (chat_id, descricao, valor, dia_vencimento, categoria, ativo, valor_referencia)
            VALUES (?, ?, ?, ?, 'Fixo', 1, ?)
            """,
            (CHAT_ID, desc, val, dia, val_ref),
        )

    conn.commit()
    print(f"Sucesso! {len(CARTOES)} Cartões, {len(INVESTIMENTOS)} Investimentos, {len(FIXOS_VALOR_DATA_FIXA)} Fixos (Valor Fixo) e {len(FIXOS_VARIAVEIS)} Variáveis cadastrados.")
    conn.close()

if __name__ == "__main__":
    migrar_e_popular()
