"""Leitura das páginas do Fragrantica.

O parser trabalha só com HTML (fácil de testar com páginas salvas). Os seletores ficam
juntos aqui: se o site mudar o layout, é neste arquivo que se ajusta.
"""
import hashlib
import re
from bs4 import BeautifulSoup

from .feed import normalizar

BASE = "https://www.fragrantica.com"
VOTACOES = {
    "longevidade": ["very weak", "weak", "moderate", "long lasting", "eternal"],
    "projecao": ["intimate", "moderate", "strong", "enormous"],
    "genero": ["female", "more female", "unisex", "more male", "male"],
    "custo_beneficio": ["way overpriced", "overpriced", "ok", "good value", "great value"],
    "estacao": ["winter", "spring", "summer", "fall", "day", "night"],
}


def pagina_bloqueada(html):
    """Desafio do Cloudflare ou captcha — exige ação humana na janela do navegador."""
    t = html[:5000].lower()
    return "just a moment" in t or "cf-challenge" in t or ("captcha" in t and "<h1" not in t)


def melhor_resultado(html, marca, nome, concentracao=None):
    """Escolhe, entre os links de perfume de uma página de busca, o mais parecido.

    Compara as palavras do nome com o "slug" do link (/perfume/Marca/Nome-123.html):
    o nome precisa bater bem e a marca dá um bônus.
    """
    soup = BeautifulSoup(html, "html.parser")
    alvo_nome = set(normalizar(nome).split())
    alvo_marca = set(normalizar(marca or "").split())
    melhor, nota = None, 0.0
    for a in soup.select("a[href*='/perfume/']"):
        m = re.search(r"/perfume/([^/]+)/(.+)-\d+\.html", a.get("href", ""))
        if not m:
            continue
        slug_marca = set(normalizar(m.group(1)).split())
        slug_nome = set(normalizar(m.group(2)).split())
        s = len(alvo_nome & slug_nome) / len(alvo_nome | slug_nome) if alvo_nome else 0
        if alvo_marca & slug_marca:
            s += 0.2
        if concentracao and set(normalizar(concentracao).split()) <= slug_nome:
            s += 0.1
        if s > nota:
            href = a["href"]
            melhor, nota = (href if href.startswith("http") else BASE + href), s
    return melhor if nota >= 0.6 else None


def _texto(el):
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else None


def _notas_da_secao(titulo):
    notas, el = [], titulo.find_next_sibling()
    while el is not None and el.name not in ("h4", "h3"):
        for n in el.select("a[href*='/notes/']") or []:
            nome = _texto(n) or (n.img.get("alt") if n.img else None)
            if nome and nome not in notas:
                notas.append(nome)
        el = el.find_next_sibling()
    return notas


def extrair_perfume(html):
    soup = BeautifulSoup(html, "html.parser")
    d = {}
    h1 = soup.select_one("h1[itemprop=name]") or soup.find("h1")
    d["titulo"] = _texto(h1)
    if h1 and h1.small:
        d["genero"] = _texto(h1.small)
    nota = soup.select_one("[itemprop=ratingValue]")
    votos = soup.select_one("[itemprop=ratingCount]")
    d["nota"] = float(_texto(nota).replace(",", ".")) if nota and _texto(nota) else None
    d["votos"] = int(re.sub(r"\D", "", _texto(votos))) if votos and re.search(r"\d", _texto(votos)) else None

    acordes = []
    for bar in soup.select(".accord-bar"):
        m = re.search(r"width:\s*([\d.]+)%", bar.get("style", ""))
        acordes.append({"nome": _texto(bar), "forca": float(m.group(1)) if m else None})
    d["acordes"] = acordes

    d["notas_topo"] = d["notas_coracao"] = d["notas_fundo"] = []
    d["notas_gerais"] = []
    piramide = soup.select_one("#pyramid") or soup
    for h4 in piramide.find_all("h4"):
        t = _texto(h4).lower()
        campo = ("notas_topo" if "top" in t else "notas_coracao" if "middle" in t or "heart" in t
                 else "notas_fundo" if "base" in t else None)
        if campo:
            d[campo] = _notas_da_secao(h4)
    if not (d["notas_topo"] or d["notas_coracao"] or d["notas_fundo"]):
        d["notas_gerais"] = list(dict.fromkeys(
            _texto(a) for a in piramide.select("a[href*='/notes/']") if _texto(a)))

    d["perfumista"] = ", ".join(dict.fromkeys(_texto(a) for a in soup.select("a[href*='/noses/']") if _texto(a))) or None
    desc = soup.select_one("[itemprop=description]")
    d["descricao"] = _texto(desc)
    m = re.search(r"launched in (\d{4})", d["descricao"] or "")
    d["ano"] = int(m.group(1)) if m else None
    d["votacoes"] = extrair_votacoes(soup)
    d["reviews"] = extrair_reviews(soup)
    return d


def extrair_votacoes(soup):
    """Procura rótulos conhecidos ('long lasting', 'winter'...) seguidos de um número de votos."""
    textos = [t.strip() for t in soup.stripped_strings]
    res = {}
    for grupo, rotulos in VOTACOES.items():
        g = {}
        for i, t in enumerate(textos[:-1]):
            if t.lower() in rotulos and t.lower() not in g and re.fullmatch(r"\d[\d,.]*", textos[i + 1]):
                g[t.lower()] = int(re.sub(r"\D", "", textos[i + 1]))
        if g:
            res[grupo] = g
    return res


def extrair_reviews(soup):
    reviews = []
    for r in soup.select("[itemprop=review], .fragrance-review"):
        corpo = r.select_one("[itemprop=reviewBody]") or r
        texto = _texto(corpo)
        if not texto or len(texto) < 15:
            continue
        autor = r.select_one("[itemprop=author]")
        data = r.select_one("[itemprop=datePublished]")
        reviews.append({
            "autor": (autor.get("content") or _texto(autor)) if autor else None,
            "data": (data.get("content") or _texto(data)) if data else None,
            "texto": texto,
            "hash": hashlib.sha1(texto.encode()).hexdigest(),
        })
    return reviews
