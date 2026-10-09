import sqlite3
import os
import database
import helpers

CHAT_ID = "-1003987623111"
MES_ANO = "2026-10"

# 1. Contas da Planilha (Imagem)
CONTAS_PLANILHA = [
    # (Descricao, Dia, Valor, Categoria)
    ("CT C6", 1, 23.00, "Cartão"),
    ("CONDUÇÃO LEVY", 5, 550.00, "Geral"),
    ("CT RecargaPay vi", 6, 1.00, "Cartão"),
    ("BANCA GABRIEL", 10, 100.00, "Geral"),
    ("FUTEBOL", 10, 140.00, "Geral"),
    ("NATAÇÃO", 10, 100.00, "Geral"),
    ("ACORDO CONDOMINIO", 10, 1750.00, "Geral"),
    ("CONS 01 (VI) HS100", 10, 345.00, "Geral"),
    ("CONS 02 (VI) HS200", 10, 615.00, "Geral"),
    ("CONS 03 (VI) Rodob100", 10, 610.00, "Geral"),
    ("CONS 04 (RO) HS100", 10, 1.00, "Geral"),
    ("CONS 05 (RO) HS100", 10, 1.00, "Geral"),
    ("CONS 06 (CILA) HS100", 10, 1.00, "Geral"),
    ("EMBASA", 10, 120.00, "Geral"),
    ("ESCOLA LEVY", 10, 400.00, "Geral"),
    ("CT MERC PAGO", 10, 1.00, "Cartão"),
    ("TEL/INTERN", 10, 130.00, "Geral"),
    ("CT INTER", 11, 1.00, "Cartão"),
    ("LIGHT", 11, 350.00, "Geral"),
    ("CT NUBANK", 14, 1.00, "Cartão"),
    ("CT BANESE", 15, 1.00, "Cartão"),
    ("CT CAIXA", 15, 1.00, "Cartão"),
    ("CT BRBCARD", 17, 1.00, "Cartão"),
    ("CT CLICK", 20, 1.00, "Cartão"),
    ("CT PICPAY", 20, 1.00, "Cartão"),
    ("CT BRADESCO", 28, 1.00, "Cartão"),
]

# 2. Contas Fixas Mensais (Texto do Usuário)
CONTAS_FIXAS = [
    # (Descricao, Dia, Valor, Categoria)
    ("LANCHE/ALMOÇO LEVY", 1, 400.00, "Fixo"),
    ("LANCHE GABRIEL", 1, 200.00, "Fixo"),
    ("COMBUSTIVEL", 1, 600.00, "Fixo"),
    ("MERCADO CASAS", 1, 1500.00, "Fixo"),
    ("ALMOÇO", 1, 400.00, "Fixo"),
    ("AGUA", 1, 150.00, "Fixo"),
    ("ALUGUEL", 1, 400.00, "Fixo"),
    ("FAXINA", 1, 500.00, "Fixo"),
    ("DIZIMO/OFERTA", 1, 1000.00, "Fixo"),
    ("CELULARES", 1, 100.00, "Fixo"),
    ("MESADAS", 1, 100.00, "Fixo"),
    ("ENTRETENIMENTO", 1, 500.00, "Fixo"),
]

def main():
    db_file = os.path.join(os.path.dirname(__file__), "contas.db")
    print(f"Conectando a {db_file}...")

    # Limpa contas de testes anteriores
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contas")
        cursor.execute("DELETE FROM recorrentes")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('contas', 'recorrentes')")
        conn.commit()
    print("Base limpa para inserção oficial.")

    total_inseridas = 0
    # Inserir Planilha
    for desc, dia, valor, cat in CONTAS_PLANILHA:
        database.adicionar_conta(
            chat_id=CHAT_ID,
            descricao=desc,
            valor=valor,
            dia_vencimento=dia,
            mes_ano=MES_ANO,
            recorrente=1,
            categoria=cat,
            db_path=db_file,
        )
        total_inseridas += 1

    # Inserir Fixas
    for desc, dia, valor, cat in CONTAS_FIXAS:
        database.adicionar_conta(
            chat_id=CHAT_ID,
            descricao=desc,
            valor=valor,
            dia_vencimento=dia,
            mes_ano=MES_ANO,
            recorrente=1,
            categoria=cat,
            db_path=db_file,
        )
        total_inseridas += 1

    print(f"Sucesso! Total de {total_inseridas} contas inseridas.")

    # Validar listagem e totais
    contas = database.listar_contas(CHAT_ID, MES_ANO)
    totais = database.obter_totais_mes(CHAT_ID, MES_ANO)
    print(f"\nContas listadas para {MES_ANO}: {len(contas)}")
    print(f"Totais gerais: {totais}")
    
    # Validar filtro Fixos
    fixos = database.listar_contas(CHAT_ID, MES_ANO, filtro_categoria="Fixo")
    print(f"\nFixos listados: {len(fixos)}")
    for f in fixos:
        print(f" - {f['descricao']}: R$ {f['valor']:.2f}")

    # Validar filtro Cartões
    cartoes = database.listar_contas(CHAT_ID, MES_ANO, filtro_categoria="Cartão")
    print(f"\nCartões listados: {len(cartoes)}")
    for c in cartoes:
        print(f" - {c['descricao']}: R$ {c['valor']:.2f}")

if __name__ == "__main__":
    main()
