"""
Testes automatizados da lógica de negócio e renderização do Bot de Contas.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import database
import helpers

def test_full_flow():
    chat_id = "TESTE_GRUPO"
    mes_ano = "2026-10"

    print("--- 1. Inserindo contas de teste ---")
    id_luz = database.adicionar_conta(chat_id, "Luz Cemig", 180.0, 5, mes_ano)
    id_aluguel = database.adicionar_conta(chat_id, "Aluguel Apartamento", 1500.0, 10, mes_ano, recorrente=1)
    id_net = database.adicionar_conta(chat_id, "Internet Fibra", 120.0, 15, mes_ano)

    contas = database.listar_contas(chat_id, mes_ano)
    totais = database.obter_totais_mes(chat_id, mes_ano)
    texto, markup = helpers.render_contas_message(contas, totais, mes_ano)

    print("\n--- MENSAGEM ANTES DO PAGAMENTO ---")
    print(texto)

    assert "PENDENTES (3)" in texto
    assert "PAGAS (0)" in texto
    assert totais["total_pendente"] == 1800.0
    assert totais["total_pago"] == 0.0

    print("\n--- 2. Pagando o Aluguel (deve ir para o final da lista) ---")
    database.alternar_status_pago(id_aluguel)

    contas_apos = database.listar_contas(chat_id, mes_ano)
    totais_apos = database.obter_totais_mes(chat_id, mes_ano)
    texto_apos, markup_apos = helpers.render_contas_message(contas_apos, totais_apos, mes_ano)

    print("\n--- MENSAGEM APÓS PAGAMENTO ---")
    print(texto_apos)

    # Verifica se as pendentes agora são 2 e pagas são 1
    assert "PENDENTES (2)" in texto_apos
    assert "PAGAS (1)" in texto_apos
    assert "Aluguel Apartamento" in texto_apos
    assert totais_apos["total_pendente"] == 300.0
    assert totais_apos["total_pago"] == 1500.0

    # Verifica se Aluguel aparece após Luz e Internet
    pos_luz = texto_apos.find("Luz Cemig")
    pos_net = texto_apos.find("Internet Fibra")
    pos_aluguel = texto_apos.find("Aluguel Apartamento")

    assert pos_luz < pos_aluguel, "Luz deve aparecer antes de Aluguel"
    assert pos_net < pos_aluguel, "Internet deve aparecer antes de Aluguel (que foi pro final)"

    # Limpeza
    database.excluir_conta(id_luz)
    database.excluir_conta(id_aluguel)
    database.excluir_conta(id_net)

    print("\n✅ Todos os testes de fluxo, ordenação e recálculo passaram com sucesso!")

if __name__ == "__main__":
    test_full_flow()
