import database
from sqlalchemy import text


def main():
    with database.engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE movimentos ADD COLUMN numero VARCHAR"))
            print("OK: coluna 'numero' adicionada")
        except Exception as e:
            print("numero (talvez ja exista):", e)
        try:
            conn.execute(text("ALTER TABLE movimentos ADD COLUMN forma_pagamento VARCHAR"))
            print("OK: coluna 'forma_pagamento' adicionada")
        except Exception as e:
            print("forma_pagamento (talvez ja exista):", e)
        try:
            conn.execute(text("ALTER TABLE movimentos ADD COLUMN conta_bancaria_id VARCHAR"))
            print("OK: coluna 'conta_bancaria_id' adicionada")
        except Exception as e:
            print("conta_bancaria_id (talvez ja exista):", e)
        try:
            conn.execute(text("ALTER TABLE movimentos ALTER COLUMN descricao DROP NOT NULL"))
            print("OK: 'descricao' aceita NULL")
        except Exception as e:
            print("descricao (ignorado em SQLite):", e)


if __name__ == "__main__":
    main()