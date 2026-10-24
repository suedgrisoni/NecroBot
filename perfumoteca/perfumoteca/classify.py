"""Classificação própria do app, feita a partir dos dados coletados.

Regras simples e transparentes. Mais tarde dá para trocar ou complementar com IA.
"""
FAMILIAS = {
    "Gourmand": ["vanilla", "caramel", "sweet", "chocolate", "honey", "cacao", "coffee", "nutty", "almond"],
    "Âmbar / Oriental": ["amber", "warm spicy", "balsamic", "oud", "resinous", "smoky", "incense"],
    "Amadeirado": ["woody", "earthy", "mossy", "patchouli"],
    "Floral": ["floral", "white floral", "rose", "yellow floral", "tuberose", "violet", "iris", "powdery"],
    "Fresco / Cítrico": ["citrus", "fresh", "green", "fresh spicy", "ozonic", "herbal"],
    "Aquático": ["aquatic", "marine", "salty"],
    "Aromático / Fougère": ["aromatic", "lavender", "fougere"],
    "Frutado": ["fruity", "tropical", "cherry"],
    "Couro / Animálico": ["leather", "animalic", "tobacco", "musky"],
}
POSITIVAS = {"love", "amazing", "beautiful", "great", "perfect", "excellent", "gorgeous", "compliments",
             "masterpiece", "favorite", "favourite", "wonderful", "best", "lovely", "incrível", "amo", "maravilhoso"}
NEGATIVAS = {"hate", "awful", "terrible", "cheap", "synthetic", "headache", "disappointed", "weak", "boring",
             "scrubber", "nauseating", "horrible", "ruim", "fraco", "enjoativo"}


def familia(acordes):
    pontos = {}
    for i, a in enumerate(acordes[:5]):
        peso = (a.get("forca") or 100 - i * 15)
        nome = (a.get("nome") or "").lower()
        for fam, chaves in FAMILIAS.items():
            if nome in chaves:
                pontos[fam] = pontos.get(fam, 0) + peso
    return max(pontos, key=pontos.get) if pontos else None


def estacoes(votacoes):
    v = votacoes.get("estacao", {})
    nomes = {"winter": "Inverno", "spring": "Primavera", "summer": "Verão", "fall": "Outono",
             "day": "Dia", "night": "Noite"}
    if not v:
        return []
    topo = max(v.values())
    return [nomes[k] for k, n in v.items() if n >= topo * 0.7]


def tags(dados):
    t = []
    lon = dados.get("votacoes", {}).get("longevidade", {})
    if lon and max(lon, key=lon.get) in ("long lasting", "eternal"):
        t.append("Alta fixação")
    proj = dados.get("votacoes", {}).get("projecao", {})
    if proj and max(proj, key=proj.get) in ("strong", "enormous"):
        t.append("Projeção forte")
    if (dados.get("nota") or 0) >= 4.2 and (dados.get("votos") or 0) >= 100:
        t.append("Muito bem avaliado")
    return t


def sentimento(texto):
    palavras = set(texto.lower().replace(",", " ").replace(".", " ").split())
    s = len(palavras & POSITIVAS) - len(palavras & NEGATIVAS)
    return "positivo" if s > 0 else "negativo" if s < 0 else "neutro"
