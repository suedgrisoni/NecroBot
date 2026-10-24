"""Banco SQLite local: um único arquivo, fácil de copiar, abrir e pesquisar."""
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "dados"
DB_PATH = DATA_DIR / "perfumoteca.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS perfumes (
    id INTEGER PRIMARY KEY,
    chave TEXT UNIQUE NOT NULL,          -- marca + nome normalizados
    nome TEXT NOT NULL,
    marca TEXT,
    concentracao TEXT,
    categoria_loja TEXT,
    imagem TEXT,
    link_loja TEXT,
    preco TEXT,
    descricao_loja TEXT,
    fragrantica_url TEXT,
    status TEXT NOT NULL DEFAULT 'pendente',  -- pendente | coletado | nao_encontrado | erro
    tentativas INTEGER NOT NULL DEFAULT 0,
    ano INTEGER,
    perfumista TEXT,
    genero TEXT,
    nota REAL,
    votos INTEGER,
    acordes TEXT,       -- JSON [{"nome":..., "forca":...}]
    notas_topo TEXT,    -- JSON [..]
    notas_coracao TEXT,
    notas_fundo TEXT,
    notas_gerais TEXT,
    votacoes TEXT,      -- JSON {"longevidade": {...}, "projecao": {...}, ...}
    descricao TEXT,
    familia TEXT,       -- classificação gerada pelo app
    estacoes TEXT,      -- JSON
    tags TEXT,          -- JSON
    criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
    coletado_em TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    perfume_id INTEGER NOT NULL REFERENCES perfumes(id) ON DELETE CASCADE,
    hash TEXT UNIQUE NOT NULL,
    autor TEXT,
    data TEXT,
    texto TEXT NOT NULL,
    sentimento TEXT,
    coletado_em TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_reviews_perfume ON reviews(perfume_id);
CREATE VIRTUAL TABLE IF NOT EXISTS busca USING fts5(
    nome, marca, notas, acordes, familia, reviews,
    tokenize='unicode61 remove_diacritics 2'
);
"""

JSON_FIELDS = {"acordes", "notas_topo", "notas_coracao", "notas_fundo",
               "notas_gerais", "votacoes", "estacoes", "tags"}


def connect(path=DB_PATH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con


def row_to_dict(row):
    d = dict(row)
    for k in JSON_FIELDS & d.keys():
        d[k] = json.loads(d[k]) if d[k] else ([] if k != "votacoes" else {})
    return d


def reindex(con, perfume_id):
    """Atualiza o índice de busca de texto completo de um perfume."""
    p = row_to_dict(con.execute("SELECT * FROM perfumes WHERE id=?", (perfume_id,)).fetchone())
    notas = " ".join(p["notas_topo"] + p["notas_coracao"] + p["notas_fundo"] + p["notas_gerais"])
    acordes = " ".join(a["nome"] for a in p["acordes"])
    reviews = " ".join(r[0] for r in con.execute(
        "SELECT texto FROM reviews WHERE perfume_id=?", (perfume_id,)))
    con.execute("DELETE FROM busca WHERE rowid=?", (perfume_id,))
    con.execute("INSERT INTO busca(rowid, nome, marca, notas, acordes, familia, reviews) VALUES (?,?,?,?,?,?,?)",
                (perfume_id, p["nome"], p["marca"] or "", notas, acordes, p["familia"] or "", reviews))
