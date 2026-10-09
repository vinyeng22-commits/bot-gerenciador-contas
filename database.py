"""
Camada de Persistência com SQLite para o Gerenciador de Contas.
"""

import os
import sqlite3
import datetime
from typing import List, Dict, Optional, Tuple, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "contas.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH):
    """Inicializa as tabelas do banco de dados SQLite."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Tabela de contas
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                dia_vencimento INTEGER NOT NULL,
                mes_ano TEXT NOT NULL,
                pago INTEGER DEFAULT 0,
                data_pagamento TEXT,
                recorrente INTEGER DEFAULT 0,
                categoria TEXT DEFAULT 'Geral',
                valor_referencia REAL DEFAULT 0.0,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Tabela de modelos recorrentes
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS recorrentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                dia_vencimento INTEGER NOT NULL,
                categoria TEXT DEFAULT 'Geral',
                valor_referencia REAL DEFAULT 0.0,
                ativo INTEGER DEFAULT 1,
                UNIQUE(chat_id, descricao)
            )
            """
        )
        
        # Migração defensiva: garante que a coluna valor_referencia existe caso a tabela seja pré-existente
        cols_contas = [c[1] for c in cursor.execute("PRAGMA table_info(contas)").fetchall()]
        if "valor_referencia" not in cols_contas:
            cursor.execute("ALTER TABLE contas ADD COLUMN valor_referencia REAL DEFAULT 0.0")

        cols_rec = [c[1] for c in cursor.execute("PRAGMA table_info(recorrentes)").fetchall()]
        if "valor_referencia" not in cols_rec:
            cursor.execute("ALTER TABLE recorrentes ADD COLUMN valor_referencia REAL DEFAULT 0.0")

        conn.commit()

        # Auto-seed caso o banco seja criado limpo na nuvem
        cursor.execute("SELECT count(*) as total FROM recorrentes")
        row_tot = cursor.fetchone()
        if row_tot and row_tot["total"] == 0:
            try:
                import atualizar_banco_e_dados
                atualizar_banco_e_dados.migrar_e_popular()
            except Exception as e:
                print(f"[DB] Auto-seed inicial: {e}")


def adicionar_conta(
    chat_id: str,
    descricao: str,
    valor: float,
    dia_vencimento: int,
    mes_ano: str,
    recorrente: int = 0,
    categoria: str = "Geral",
    valor_referencia: float = 0.0,
    db_path: str = DB_PATH,
) -> int:
    """Insere uma nova conta no banco de dados com valor_referencia."""
    desc_up = descricao.strip().upper()
    if categoria == "Geral":
        if desc_up.startswith("CT ") or "CARTAO" in desc_up or "CARTÃO" in desc_up:
            categoria = "Cartão"
        elif "FIXO" in desc_up:
            categoria = "Fixo"

    if categoria == "Fixo" and valor_referencia == 0.0:
        valor_referencia = valor
        valor = 0.0  # Fixos começam zerados no mês para ir acumulando lançamentos

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO contas (chat_id, descricao, valor, dia_vencimento, mes_ano, pago, recorrente, categoria, valor_referencia)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (str(chat_id), descricao.strip(), float(valor), int(dia_vencimento), mes_ano.strip(), int(recorrente), categoria.strip(), float(valor_referencia)),
        )
        conta_id = cursor.lastrowid
        
        # Se marcada como recorrente, cadastra no template e replica nos próximos 12 meses
        if recorrente:
            cursor.execute(
                """
                INSERT INTO recorrentes (chat_id, descricao, valor, dia_vencimento, categoria, ativo, valor_referencia)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(chat_id, descricao) DO UPDATE SET
                    valor=excluded.valor,
                    dia_vencimento=excluded.dia_vencimento,
                    categoria=excluded.categoria,
                    valor_referencia=excluded.valor_referencia,
                    ativo=1
                """,
                (str(chat_id), descricao.strip(), float(valor), int(dia_vencimento), categoria.strip(), float(valor_referencia)),
            )
        conn.commit()

        if recorrente:
            try:
                ano, mes = map(int, mes_ano.split("-"))
                for i in range(1, 13):
                    prox_mes = mes + i
                    prox_ano = ano
                    while prox_mes > 12:
                        prox_mes -= 12
                        prox_ano += 1
                    gerar_contas_recorrentes(chat_id, f"{prox_ano}-{prox_mes:02d}", db_path=db_path)
            except Exception as e:
                print(f"[DB] Erro ao replicar futuros: {e}")

        return conta_id


def listar_contas(
    chat_id: str,
    mes_ano: str,
    filtro_categoria: Optional[str] = None,
    auto_sync_recorrentes: bool = True,
    db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    """
    Lista as contas do mês:
    1. Sincroniza automaticamente contas recorrentes para o mês caso não existam.
    2. Por padrão (filtro_categoria is None ou 'cartoes'): retorna apenas CARTÕES / FATURAS do mês.
    3. Quando filtro_categoria == 'fixo' ou 'fixos': retorna as contas fixas/variáveis.
    4. Quando filtro_categoria == 'todos': retorna todas.
    """
    if auto_sync_recorrentes:
        try:
            gerar_contas_recorrentes(chat_id, mes_ano, db_path=db_path)
        except Exception as e:
            print(f"[DB] Erro ao auto-sincronizar: {e}")

    params: List[Any] = [str(chat_id), mes_ano.strip()]

    if filtro_categoria is None or filtro_categoria.lower() in ["geral", "cartao", "cartão", "cartoes", "cartões"]:
        where_cat = "AND (categoria IN ('Cartão', 'Cartao') OR descricao LIKE 'CT %')"
    elif filtro_categoria.lower() in ["fixo", "fixos"]:
        where_cat = "AND categoria = 'Fixo'"
    elif filtro_categoria.lower() in ["investimento", "investimentos", "invest"]:
        where_cat = "AND categoria IN ('Investimento', 'Investimentos')"
    elif filtro_categoria.lower() == "todos":
        where_cat = ""
    else:
        where_cat = "AND (categoria NOT IN ('Fixo', 'Cartão', 'Cartao', 'Investimento', 'Investimentos') AND descricao NOT LIKE 'CT %')"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT * FROM contas
            WHERE (chat_id = ? OR chat_id = 'GLOBAL') AND mes_ano = ?
            {where_cat}
            ORDER BY 
                pago ASC,
                CASE WHEN pago = 0 THEN dia_vencimento ELSE 999 END ASC,
                data_pagamento ASC,
                id ASC
            """,
            params,
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def obter_conta(conta_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Obtém os dados de uma conta específica."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        row = cursor.fetchone()
        return dict(row) if row else None


def alternar_status_pago(conta_id: int, db_path: str = DB_PATH) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Alterna o status da conta entre Pago (1) e Pendente (0).
    Ao pagar, registra a data e hora do pagamento.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pago FROM contas WHERE id = ?", (int(conta_id),))
        row = cursor.fetchone()
        if not row:
            return False, None

        atual_pago = row["pago"]
        novo_pago = 0 if atual_pago == 1 else 1
        data_pagamento = datetime.datetime.now().strftime("%d/%m/%Y %H:%M") if novo_pago == 1 else None

        cursor.execute(
            """
            UPDATE contas
            SET pago = ?, data_pagamento = ?
            WHERE id = ?
            """,
            (novo_pago, data_pagamento, int(conta_id)),
        )
        conn.commit()

        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        updated_row = cursor.fetchone()
        return bool(novo_pago), dict(updated_row) if updated_row else None


def excluir_conta(conta_id: int, db_path: str = DB_PATH) -> bool:
    """Exclui uma conta pelo ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contas WHERE id = ?", (int(conta_id),))
        conn.commit()
        return cursor.rowcount > 0


def atualizar_valor_conta(conta_id: int, novo_valor: float, atualizar_futuros: bool = False, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """
    Atualiza o valor de uma conta específica.
    Se atualizar_futuros for True, também atualiza nos modelos recorrentes e meses futuros não pagos.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        conta = cursor.fetchone()
        if not conta:
            return None

        conta_dict = dict(conta)
        chat_id = conta_dict["chat_id"]
        descricao = conta_dict["descricao"]
        mes_ano = conta_dict["mes_ano"]

        # 1. Atualiza a conta selecionada
        cursor.execute(
            "UPDATE contas SET valor = ? WHERE id = ?",
            (float(novo_valor), int(conta_id)),
        )

        # 2. Se for para atualizar futuros e template recorrente
        if atualizar_futuros:
            cursor.execute(
                """
                UPDATE recorrentes SET valor = ?
                WHERE (chat_id = ? OR chat_id = 'GLOBAL') AND LOWER(descricao) = LOWER(?)
                """,
                (float(novo_valor), str(chat_id), descricao.strip()),
            )
            # Atualiza também nos meses posteriores onde ainda não foi pago
            cursor.execute(
                """
                UPDATE contas SET valor = ?
                WHERE (chat_id = ? OR chat_id = 'GLOBAL')
                  AND LOWER(descricao) = LOWER(?)
                  AND mes_ano > ?
                  AND pago = 0
                """,
                (float(novo_valor), str(chat_id), descricao.strip(), mes_ano),
            )

        conn.commit()

        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        updated_row = cursor.fetchone()
        return dict(updated_row) if updated_row else None


def buscar_conta_por_nome_ou_id(chat_id: str, termo: str, mes_ano: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Localiza uma conta pelo ID numérico ou pelo nome/descrição no mês."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        termo = termo.strip()
        if termo.isdigit():
            cursor.execute("SELECT * FROM contas WHERE id = ?", (int(termo),))
            row = cursor.fetchone()
            if row:
                return dict(row)

        cursor.execute(
            """
            SELECT * FROM contas
            WHERE (chat_id = ? OR chat_id = 'GLOBAL')
              AND mes_ano = ?
              AND LOWER(descricao) LIKE LOWER(?)
            ORDER BY id DESC LIMIT 1
            """,
            (str(chat_id), mes_ano.strip(), f"%{termo}%"),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def obter_totais_mes(
    chat_id: str,
    mes_ano: str,
    filtro_categoria: Optional[str] = None,
    auto_sync_recorrentes: bool = True,
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """Calcula os totais financeiros do mês especificado e os subtotais de Cartões e Fixos."""
    if auto_sync_recorrentes:
        try:
            gerar_contas_recorrentes(chat_id, mes_ano, db_path=db_path)
        except Exception:
            pass

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Totais consolidados por categoria
        cursor.execute(
            """
            SELECT 
                COALESCE(SUM(CASE WHEN categoria = 'Fixo' THEN valor ELSE 0 END), 0) AS total_fixos_lancado,
                COALESCE(SUM(CASE WHEN categoria = 'Fixo' THEN valor_referencia ELSE 0 END), 0) AS total_fixos_referencia,
                COUNT(CASE WHEN categoria = 'Fixo' THEN 1 END) AS qtd_fixos,

                COALESCE(SUM(CASE WHEN categoria IN ('Investimento', 'Investimentos') THEN valor ELSE 0 END), 0) AS total_invest_lancado,
                COALESCE(SUM(CASE WHEN categoria IN ('Investimento', 'Investimentos') THEN valor_referencia ELSE 0 END), 0) AS total_invest_referencia,
                COUNT(CASE WHEN categoria IN ('Investimento', 'Investimentos') THEN 1 END) AS qtd_invest,

                COALESCE(SUM(CASE WHEN (categoria IN ('Cartão', 'Cartao') OR descricao LIKE 'CT %') THEN valor ELSE 0 END), 0) AS total_cartoes,
                COALESCE(SUM(CASE WHEN (categoria IN ('Cartão', 'Cartao') OR descricao LIKE 'CT %') AND pago = 0 THEN valor ELSE 0 END), 0) AS cartoes_pendentes,
                COALESCE(SUM(CASE WHEN (categoria IN ('Cartão', 'Cartao') OR descricao LIKE 'CT %') AND pago = 1 THEN valor ELSE 0 END), 0) AS cartoes_pagos,
                COUNT(CASE WHEN (categoria IN ('Cartão', 'Cartao') OR descricao LIKE 'CT %') AND pago = 0 THEN 1 END) AS qtd_cartoes_pendentes,
                COUNT(CASE WHEN (categoria IN ('Cartão', 'Cartao') OR descricao LIKE 'CT %') AND pago = 1 THEN 1 END) AS qtd_cartoes_pagos,
                COUNT(CASE WHEN (categoria IN ('Cartão', 'Cartao') OR descricao LIKE 'CT %') THEN 1 END) AS qtd_cartoes
            FROM contas
            WHERE (chat_id = ? OR chat_id = 'GLOBAL') AND mes_ano = ?
            """,
            (str(chat_id), mes_ano.strip()),
        )
        row = cursor.fetchone()
        res = dict(row) if row else {
            "total_fixos_lancado": 0.0,
            "total_fixos_referencia": 0.0,
            "qtd_fixos": 0,
            "total_invest_lancado": 0.0,
            "total_invest_referencia": 0.0,
            "qtd_invest": 0,
            "total_cartoes": 0.0,
            "cartoes_pendentes": 0.0,
            "cartoes_pagos": 0.0,
            "qtd_cartoes_pendentes": 0,
            "qtd_cartoes_pagos": 0,
            "qtd_cartoes": 0,
        }

        # Para compatibilidade com os painéis
        res["total_fixos"] = res["total_fixos_lancado"]
        res["total_invest"] = res.get("total_invest_lancado", 0.0)
        res["total_pendente"] = res["cartoes_pendentes"]
        res["total_pago"] = res["cartoes_pagos"]
        res["total_geral"] = res["total_cartoes"]
        res["qtd_pendente"] = res["qtd_cartoes_pendentes"]
        res["qtd_paga"] = res["qtd_cartoes_pagos"]
        res["total_geral_comprometido"] = (
            res["total_cartoes"] + res["total_fixos_lancado"] + res.get("total_invest_lancado", 0.0)
        )
        res["total_geral_referencia"] = (
            res["total_cartoes"] + res["total_fixos_referencia"] + res.get("total_invest_referencia", 0.0)
        )

        return res


def acrescentar_valor_fixo(conta_id: int, valor_adicional: float, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Adiciona um valor ao total acumulado de um item fixo/variável ou investimento no mês."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        conta = cursor.fetchone()
        if not conta:
            return None
        novo_valor = round(float(conta["valor"]) + float(valor_adicional), 2)
        cursor.execute("UPDATE contas SET valor = ? WHERE id = ?", (novo_valor, int(conta_id)))
        conn.commit()
        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        updated = cursor.fetchone()
        return dict(updated) if updated else None


def subtrair_valor_fixo(conta_id: int, valor_subtrair: float, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Subtrai um valor do total acumulado de um item fixo/variável ou investimento no mês (para desfazer)."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        conta = cursor.fetchone()
        if not conta:
            return None
        novo_valor = max(0.0, round(float(conta["valor"]) - float(valor_subtrair), 2))
        cursor.execute("UPDATE contas SET valor = ? WHERE id = ?", (novo_valor, int(conta_id)))
        conn.commit()
        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        updated = cursor.fetchone()
        return dict(updated) if updated else None


def zerar_mes_fixos(chat_id: str, mes_ano: str, db_path: str = DB_PATH) -> int:
    """Zera os valores variáveis e restaura fixos com valor pré-definido."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE contas 
            SET valor = CASE 
                WHEN descricao IN ('ALUGUEL', 'MESADAS', 'CONDUÇÃO LEVY', 'BANCA GABRIEL', 'FUTEBOL', 'NATAÇÃO', 'ACORDO CONDOMINIO') 
                THEN valor_referencia 
                ELSE 0.0 
            END,
            pago = 0,
            data_pagamento = NULL
            WHERE (chat_id = ? OR chat_id = 'GLOBAL') AND mes_ano = ? AND categoria = 'Fixo'
            """,
            (str(chat_id), mes_ano.strip()),
        )
        conn.commit()
        return cursor.rowcount


def zerar_mes_investimentos(chat_id: str, mes_ano: str, db_path: str = DB_PATH) -> int:
    """Zera todos os valores acumulados de investimentos/consórcios no mês."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE contas 
            SET valor = 0.0, pago = 0, data_pagamento = NULL
            WHERE (chat_id = ? OR chat_id = 'GLOBAL') AND mes_ano = ? AND categoria IN ('Investimento', 'Investimentos')
            """,
            (str(chat_id), mes_ano.strip()),
        )
        conn.commit()
        return cursor.rowcount


def atualizar_dia_conta(conta_id: int, novo_dia: int, atualizar_futuros: bool = False, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Atualiza o dia de vencimento de uma conta e opcionalmente nos meses futuros."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        conta = cursor.fetchone()
        if not conta:
            return None

        conta_dict = dict(conta)
        chat_id = conta_dict["chat_id"]
        descricao = conta_dict["descricao"]
        mes_ano = conta_dict["mes_ano"]

        cursor.execute(
            "UPDATE contas SET dia_vencimento = ? WHERE id = ?",
            (int(novo_dia), int(conta_id)),
        )

        if atualizar_futuros:
            cursor.execute(
                """
                UPDATE recorrentes SET dia_vencimento = ?
                WHERE (chat_id = ? OR chat_id = 'GLOBAL') AND LOWER(descricao) = LOWER(?)
                """,
                (int(novo_dia), str(chat_id), descricao.strip()),
            )
            cursor.execute(
                """
                UPDATE contas SET dia_vencimento = ?
                WHERE (chat_id = ? OR chat_id = 'GLOBAL')
                  AND LOWER(descricao) = LOWER(?)
                  AND mes_ano > ?
                  AND pago = 0
                """,
                (int(novo_dia), str(chat_id), descricao.strip(), mes_ano),
            )

        conn.commit()
        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        updated = cursor.fetchone()
        return dict(updated) if updated else None


def atualizar_categoria_conta(conta_id: int, nova_categoria: str, atualizar_futuros: bool = False, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Atualiza a categoria de uma conta e opcionalmente nos modelos futuros."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        conta = cursor.fetchone()
        if not conta:
            return None

        conta_dict = dict(conta)
        chat_id = conta_dict["chat_id"]
        descricao = conta_dict["descricao"]
        mes_ano = conta_dict["mes_ano"]

        cursor.execute(
            "UPDATE contas SET categoria = ? WHERE id = ?",
            (nova_categoria.strip(), int(conta_id)),
        )

        if atualizar_futuros:
            cursor.execute(
                """
                UPDATE recorrentes SET categoria = ?
                WHERE (chat_id = ? OR chat_id = 'GLOBAL') AND LOWER(descricao) = LOWER(?)
                """,
                (nova_categoria.strip(), str(chat_id), descricao.strip()),
            )
            cursor.execute(
                """
                UPDATE contas SET categoria = ?
                WHERE (chat_id = ? OR chat_id = 'GLOBAL')
                  AND LOWER(descricao) = LOWER(?)
                  AND mes_ano > ?
                  AND pago = 0
                """,
                (nova_categoria.strip(), str(chat_id), descricao.strip(), mes_ano),
            )

        conn.commit()
        cursor.execute("SELECT * FROM contas WHERE id = ?", (int(conta_id),))
        updated = cursor.fetchone()
        return dict(updated) if updated else None


def gerar_contas_recorrentes(chat_id: str, mes_ano_destino: str, db_path: str = DB_PATH) -> int:
    """
    Cria as contas fixas/recorrentes para o mês solicitado caso ainda não existam.
    Retorna o número de contas adicionadas.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Busca todas as recorrentes ativas para este chat
        cursor.execute(
            """
            SELECT descricao, valor, dia_vencimento, categoria, valor_referencia
            FROM recorrentes
            WHERE (chat_id = ? OR chat_id = 'GLOBAL') AND ativo = 1
            """,
            (str(chat_id),),
        )
        templates = cursor.fetchall()

        adicionadas = 0
        for t in templates:
            # Verifica se já existe uma conta com o mesmo nome neste mês
            cursor.execute(
                """
                SELECT id FROM contas
                WHERE (chat_id = ? OR chat_id = 'GLOBAL')
                  AND mes_ano = ?
                  AND LOWER(descricao) = LOWER(?)
                """,
                (str(chat_id), mes_ano_destino.strip(), t["descricao"].strip()),
            )
            if not cursor.fetchone():
                is_fixo = (t["categoria"] == "Fixo")
                val_inicial = 0.0 if is_fixo else t["valor"]
                val_ref = t["valor_referencia"] if t["valor_referencia"] else (t["valor"] if is_fixo else 0.0)
                cursor.execute(
                    """
                    INSERT INTO contas (chat_id, descricao, valor, dia_vencimento, mes_ano, pago, recorrente, categoria, valor_referencia)
                    VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?)
                    """,
                    (str(chat_id), t["descricao"], val_inicial, t["dia_vencimento"], mes_ano_destino.strip(), t["categoria"], val_ref),
                )
                adicionadas += 1

        conn.commit()
        return adicionadas


def listar_recorrentes(chat_id: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Lista as contas cadastradas como recorrentes."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM recorrentes
            WHERE (chat_id = ? OR chat_id = 'GLOBAL') AND ativo = 1
            ORDER BY dia_vencimento ASC
            """,
            (str(chat_id),),
        )
        return [dict(r) for r in cursor.fetchall()]


def obter_contas_alerta(chat_id: str, dias_antecedencia: int = 3, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Retorna contas não pagas categorizadas em:
    - 'hoje': vencem no dia atual
    - 'em_breve': vencem nos próximos 'dias_antecedencia' dias
    - 'vencidas': venceram em dias anteriores do mês atual (ou meses anteriores)
    """
    hoje = datetime.date.today()
    mes_ano_atual = f"{hoje.year}-{hoje.month:02d}"

    # Garante que as contas recorrentes do mês atual estejam sincronizadas
    gerar_contas_recorrentes(chat_id, mes_ano_atual, db_path=db_path)

    vencidas = []
    vencem_hoje = []
    vencem_em_breve = []

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Contas não pagas do mês atual
        cursor.execute(
            """
            SELECT * FROM contas
            WHERE (chat_id = ? OR chat_id = 'GLOBAL')
              AND mes_ano = ?
              AND pago = 0
            ORDER BY dia_vencimento ASC
            """,
            (str(chat_id), mes_ano_atual),
        )
        contas_mes = [dict(r) for r in cursor.fetchall()]

        for c in contas_mes:
            dia = c["dia_vencimento"]
            if dia < hoje.day:
                c["dias_atraso"] = hoje.day - dia
                vencidas.append(c)
            elif dia == hoje.day:
                vencem_hoje.append(c)
            elif hoje.day < dia <= hoje.day + dias_antecedencia:
                c["dias_restantes"] = dia - hoje.day
                vencem_em_breve.append(c)

        # 2. Verifica se há contas não pagas de meses anteriores
        cursor.execute(
            """
            SELECT * FROM contas
            WHERE (chat_id = ? OR chat_id = 'GLOBAL')
              AND mes_ano < ?
              AND pago = 0
            ORDER BY mes_ano ASC, dia_vencimento ASC
            """,
            (str(chat_id), mes_ano_atual),
        )
        anteriores = [dict(r) for r in cursor.fetchall()]
        for c in anteriores:
            c["mes_anterior"] = True
            vencidas.append(c)

    return {
        "hoje": vencem_hoje,
        "em_breve": vencem_em_breve,
        "vencidas": vencidas,
        "data_hoje": hoje.strftime("%d/%m/%Y"),
        "total_alerta": len(vencem_hoje) + len(vencem_em_breve) + len(vencidas),
    }


# Inicializa o banco de dados na importação
init_db()
