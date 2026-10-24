"""Importa a lista de perfumes a acompanhar a partir de um feed Google Merchant (XML)."""
import html
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

from . import db

NS = {"g": "http://base.google.com/ns/1.0"}
CATEGORIAS_PERFUME = ("Perfumes", "Perfume")
PREFIXOS = re.compile(r"^(perfume|kit)\s+(árabe|arabe|importado|de nicho|nicho)?\s*", re.I)
CONCENTRACOES = ["Extrait de Parfum", "Elixir", "Parfum", "Eau de Parfum Intense", "Eau de Parfum",
                 "Eau de Toilette", "Eau de Cologne", "Eau Fraiche", "Body Mist"]
TAMANHO = re.compile(r"\b\d+\s?(ml|g)\b.*$", re.I)


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def limpar_titulo(titulo, marca):
    """'Perfume Árabe Lattafa Khamrah Eau de Parfum 100ml' -> ('Khamrah', 'Eau de Parfum')."""
    t = html.unescape(titulo).strip()
    t = PREFIXOS.sub("", t)
    t = TAMANHO.sub("", t).strip()
    concentracao = None
    for c in sorted(CONCENTRACOES, key=len, reverse=True):
        m = re.search(re.escape(c), t, re.I)
        if m:
            concentracao = c
            t = (t[:m.start()] + t[m.end():]).strip()
            break
    if marca and normalizar(t).startswith(normalizar(marca)):
        t = t[len(marca):].strip()
    return re.sub(r"\s{2,}", " ", t).strip(" -–"), concentracao


def baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Perfumoteca/1.0 (uso pessoal)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def importar(url_ou_arquivo, con=None):
    con = con or db.connect()
    dados = baixar(url_ou_arquivo) if url_ou_arquivo.startswith("http") else open(url_ou_arquivo, "rb").read()
    for item in ET.fromstring(dados).iter("item"):
        tipos = [e.text or "" for e in item.findall("g:product_type", NS)]
        if not any(t.startswith(CATEGORIAS_PERFUME) for t in tipos):
            continue  # ignora relógios, hidratantes, kits...
        marca = html.unescape(item.findtext("g:brand", "", NS)).strip()
        nome, conc = limpar_titulo(item.findtext("title", ""), marca)
        if not nome:
            continue
        chave = normalizar(f"{marca} {nome} {conc or ''}")
        preco = (item.findtext("g:sale_price", "", NS) or item.findtext("g:price", "", NS)).strip()
        con.execute(
            """INSERT INTO perfumes(chave, nome, marca, concentracao, categoria_loja, imagem, link_loja,
                                    preco, descricao_loja)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(chave) DO UPDATE SET preco=excluded.preco, imagem=excluded.imagem""",
            (chave, nome, marca, conc, tipos[0], item.findtext("g:image_link", "", NS),
             (item.findtext("link") or "").split("?")[0], preco, item.findtext("description", "")))
    con.commit()
    return con.execute("SELECT COUNT(*) FROM perfumes").fetchone()[0]
