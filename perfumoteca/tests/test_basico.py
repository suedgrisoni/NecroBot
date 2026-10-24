"""Testes com uma página de exemplo (estrutura semelhante à do Fragrantica)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from perfumoteca import classify, collector, db, feed, fragrantica  # noqa: E402

PAGINA = """
<html><body>
<h1 itemprop="name">Khamrah Lattafa Perfumes <small>for women and men</small></h1>
<span itemprop="ratingValue">4.21</span><span itemprop="ratingCount">12,345</span>
<div class="accord-bar" style="width: 100%;">warm spicy</div>
<div class="accord-bar" style="width: 80%;">sweet</div>
<div class="accord-bar" style="width: 60%;">vanilla</div>
<div itemprop="description">Khamrah by Lattafa is an Amber Spicy fragrance. Khamrah was launched in 2022.</div>
<a href="/noses/Someone.html">Someone</a>
<div id="pyramid">
  <h4>Top Notes</h4><div><a href="/notes/Cinnamon-1.html">Cinnamon</a><a href="/notes/Nutmeg-2.html">Nutmeg</a></div>
  <h4>Middle Notes</h4><div><a href="/notes/Dates-3.html">Dates</a></div>
  <h4>Base Notes</h4><div><a href="/notes/Vanilla-4.html">Vanilla</a></div>
</div>
<div><span>long lasting</span><span>900</span><span>eternal</span><span>300</span><span>weak</span><span>20</span></div>
<div><span>winter</span><span>800</span><span>fall</span><span>700</span><span>summer</span><span>100</span></div>
<div itemprop="review"><span itemprop="author" content="ana"></span><span itemprop="datePublished" content="2024-01-02"></span>
  <div itemprop="reviewBody">I love this, amazing in winter and lots of compliments.</div></div>
<div itemprop="review"><div itemprop="reviewBody">Too sweet for me, gave me a headache.</div></div>
</body></html>
"""
BUSCA = """<a href="/perfume/Lattafa-Perfumes/Khamrah-Qahwa-80000.html">Khamrah Qahwa</a>
<a href="/perfume/Lattafa-Perfumes/Khamrah-75805.html">Khamrah Lattafa Perfumes</a>
<a href="/perfume/Other/Unrelated-1.html">Unrelated</a>"""


def test_limpar_titulo():
    assert feed.limpar_titulo("Perfume Árabe Lattafa Khamrah Eau de Parfum 100ml", "Lattafa") == \
        ("Khamrah", "Eau de Parfum")


def test_ignora_kits():
    assert feed.KIT.search("Perfume Árabe Lattafa Pride 5x20ml Affection, Tharwah Gold e mais")
    assert not feed.KIT.search("Perfume Árabe Lattafa Khamrah Eau de Parfum 100ml")


def test_melhor_resultado():
    assert fragrantica.melhor_resultado(BUSCA, "Lattafa", "Khamrah").endswith("Khamrah-75805.html")


def test_extrair_e_salvar(tmp_path):
    d = fragrantica.extrair_perfume(PAGINA)
    assert d["nota"] == 4.21 and d["votos"] == 12345 and d["ano"] == 2022
    assert d["notas_topo"] == ["Cinnamon", "Nutmeg"] and d["notas_fundo"] == ["Vanilla"]
    assert d["votacoes"]["longevidade"]["long lasting"] == 900
    assert len(d["reviews"]) == 2
    assert classify.familia(d["acordes"]) == "Gourmand"  # sweet + vanilla pesam mais que warm spicy
    assert "Alta fixação" in classify.tags(d) and "Inverno" in classify.estacoes(d["votacoes"])

    con = db.connect(tmp_path / "t.db")
    con.execute("INSERT INTO perfumes(chave, nome, marca) VALUES ('k', 'Khamrah', 'Lattafa')")
    p = con.execute("SELECT * FROM perfumes").fetchone()
    assert collector.salvar(con, p, "https://x", d) == 2
    assert collector.salvar(con, p, "https://x", d) == 0  # reviews repetidos não duplicam
    assert con.execute("SELECT rowid FROM busca WHERE busca MATCH 'dates'").fetchone()[0] == p["id"]
    sents = [r[0] for r in con.execute("SELECT sentimento FROM reviews ORDER BY id")]
    assert sents == ["positivo", "negativo"]


def test_dados_da_descricao():
    """Página sem pirâmide/acordes no HTML: usa a descrição (caso real do Hypnotic Poison)."""
    html = """<h1 itemprop="name">Hypnotic Poison Dior</h1>
    <a href="/noses/">Perfumers</a><a href="/noses/Annick-Menardo.html">Annick Menardo</a>
    <div itemprop="description">Hypnotic Poison by Dior is a Oriental Vanilla fragrance for women. Hypnotic Poison
    was launched in 1998. The nose behind this fragrance is Annick Menardo. Top notes are Coconut, Plum and Apricot;
    middle notes are Brazilian Rosewood, Jasmine, Tuberose, Caraway, Rose and Lily-of-the-Valley; base notes are
    Vanilla, Almond, Sandalwood and Musk.</div>"""
    d = fragrantica.extrair_perfume(html)
    assert d["perfumista"] == "Annick Menardo"
    assert d["genero"] == "for women" and d["ano"] == 1998
    assert d["notas_topo"] == ["Coconut", "Plum", "Apricot"]
    assert d["notas_coracao"][-1] == "Lily-of-the-Valley" and d["notas_fundo"][0] == "Vanilla"
    assert d["notas_gerais"] == []
    assert classify.familia(d["acordes"], d["familia_site"]) == "Âmbar / Oriental"
