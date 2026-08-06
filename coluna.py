import sqlite3
c = sqlite3.connect('clacs.db')
try:
    c.execute("ALTER TABLE intervencoes ADD COLUMN data_resolucao DATETIME")
    c.commit()
    print("Coluna adicionada")
except Exception as e:
    print("Erro (talvez ja exista):", e)