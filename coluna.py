import sqlite3
c = sqlite3.connect('clacs.db')

# Clientes marcados "Sem Contrato" que TÊM contrato real → corrigir para "Com Contrato"
clientes_com_contrato = c.execute("""
    SELECT DISTINCT cliente_id FROM contratos
""").fetchall()
ids = [row[0] for row in clientes_com_contrato]

corrigidos = 0
for cid in ids:
    cur = c.execute("SELECT tipo_cliente FROM clientes WHERE id = ?", (cid,)).fetchone()
    if cur and cur[0] == "Sem Contrato":
        c.execute("UPDATE clientes SET tipo_cliente = 'Com Contrato' WHERE id = ?", (cid,))
        corrigidos += 1

c.commit()
print(f"{corrigidos} cliente(s) corrigido(s) para 'Com Contrato'")