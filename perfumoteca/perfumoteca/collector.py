"""Coletor: abre um navegador de verdade (com o seu login salvo) e visita os perfumes
devagar, um a cada 1–2 minutos, como uma pessoa navegando.

Não tenta burlar proteções: se o site pedir verificação, o coletor pausa e espera
você resolver na janela. Se o site sinalizar excesso de acessos, ele para.
"""
import json
import random
import threading
import urllib.parse
from collections import deque
from datetime import datetime

from . import classify, db, fragrantica

PERFIL = db.DATA_DIR / "navegador"
INTERVALO = (60, 120)  # segundos entre perfumes
PARAR = threading.Event()   # acionado pelo botão "Parar" do painel
LOG = deque(maxlen=300)     # últimas mensagens, mostradas no painel


class Interrompido(Exception):
    pass


def log(msg):
    linha = f"[{datetime.now():%H:%M:%S}] {msg}"
    LOG.append(linha)
    print(linha, flush=True)


def pausa(segundos):
    """Espera, mas acorda na hora se pedirem para parar."""
    if PARAR.wait(segundos):
        raise Interrompido()


def abrir_navegador(p):
    PERFIL.mkdir(parents=True, exist_ok=True)
    ctx = p.chromium.launch_persistent_context(
        str(PERFIL), headless=False, viewport={"width": 1366, "height": 850}, locale="en-US")
    return ctx, (ctx.pages[0] if ctx.pages else ctx.new_page())


def login(concluido=None):
    """Abre o Fragrantica para você entrar na sua conta. A sessão fica salva no perfil local.

    Termina quando `concluido` (Event) é acionado, quando você fecha a janela ou, no
    terminal, quando aperta ENTER.
    """
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx, page = abrir_navegador(p)
        page.goto(fragrantica.BASE + "/login/", wait_until="domcontentloaded")
        log("Janela de login aberta: entre na sua conta do Fragrantica.")
        if concluido is None:
            input("Faça login na janela do navegador e depois aperte ENTER aqui... ")
        else:
            while not concluido.is_set() and not PARAR.is_set() and ctx.pages:
                page.wait_for_timeout(1000) if not page.is_closed() else concluido.wait(1)
        try:
            ctx.close()
        except Exception:  # noqa: BLE001 — a janela pode já ter sido fechada
            pass
    log("Sessão salva. Pronto para coletar.")


def navegar_como_pessoa(page):
    """Rola a página aos poucos, com pausas irregulares, como quem está lendo."""
    for _ in range(random.randint(3, 7)):
        page.mouse.wheel(0, random.randint(250, 700))
        pausa(random.uniform(1.5, 5))
    if random.random() < 0.3:
        page.mouse.wheel(0, -random.randint(200, 600))
        pausa(random.uniform(1, 3))


def visitar(page, url):
    resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
    if resp is not None and resp.status == 429:
        raise PermissionError("O site pediu para diminuir o ritmo (HTTP 429).")
    for _ in range(60):  # até ~5 min para você resolver uma verificação
        html = page.content()
        if not fragrantica.pagina_bloqueada(html):
            break
        if _ == 0:
            log("Verificação na tela: resolva na janela do navegador; aguardando...")
        pausa(5)
    else:
        raise PermissionError("Verificação não resolvida.")
    pausa(random.uniform(2, 4))
    navegar_como_pessoa(page)
    return page.content()


def salvar(con, perfume, url, dados):
    fam = classify.familia(dados["acordes"])
    con.execute(
        """UPDATE perfumes SET fragrantica_url=?, status='coletado', ano=?, perfumista=?, genero=?, nota=?,
               votos=?, acordes=?, notas_topo=?, notas_coracao=?, notas_fundo=?, notas_gerais=?, votacoes=?,
               descricao=?, familia=?, estacoes=?, tags=?, coletado_em=CURRENT_TIMESTAMP WHERE id=?""",
        (url, dados["ano"], dados["perfumista"], dados.get("genero"), dados["nota"], dados["votos"],
         json.dumps(dados["acordes"], ensure_ascii=False), json.dumps(dados["notas_topo"], ensure_ascii=False),
         json.dumps(dados["notas_coracao"], ensure_ascii=False), json.dumps(dados["notas_fundo"], ensure_ascii=False),
         json.dumps(dados["notas_gerais"], ensure_ascii=False), json.dumps(dados["votacoes"], ensure_ascii=False),
         dados["descricao"], fam, json.dumps(classify.estacoes(dados["votacoes"]), ensure_ascii=False),
         json.dumps(classify.tags(dados), ensure_ascii=False), perfume["id"]))
    novos = 0
    for r in dados["reviews"]:
        cur = con.execute(
            "INSERT OR IGNORE INTO reviews(perfume_id, hash, autor, data, texto, sentimento) VALUES (?,?,?,?,?,?)",
            (perfume["id"], r["hash"], r["autor"], r["data"], r["texto"], classify.sentimento(r["texto"])))
        novos += cur.rowcount
    db.reindex(con, perfume["id"])
    con.commit()
    return novos


def proximos(con, limite, revisitar_dias):
    """Primeiro os nunca coletados; depois os mais antigos, para buscar reviews novos."""
    return con.execute(
        """SELECT * FROM perfumes
           WHERE (status='pendente' AND tentativas < 3)
              OR (status='coletado' AND coletado_em < datetime('now', ?))
           ORDER BY status='coletado', coletado_em, id LIMIT ?""",
        (f"-{revisitar_dias} days", limite)).fetchall()


def coletar(limite=20, revisitar_dias=30, intervalo=INTERVALO):
    from playwright.sync_api import sync_playwright
    con = db.connect()
    fila = proximos(con, limite, revisitar_dias)
    if not fila:
        log("Nada para coletar agora.")
        return
    log(f"{len(fila)} perfume(s) na fila desta rodada.")
    with sync_playwright() as p:
        ctx, page = abrir_navegador(p)
        try:
            for i, perfume in enumerate(fila):
                if PARAR.is_set():
                    break
                if i:
                    espera = random.uniform(*intervalo)
                    log(f"Pausa de {espera:.0f}s...")
                    pausa(espera)
                rotulo = f"{perfume['marca']} {perfume['nome']}"
                try:
                    url = perfume["fragrantica_url"]
                    if not url:
                        q = urllib.parse.quote(f"{perfume['marca']} {perfume['nome']}")
                        visitar(page, f"{fragrantica.BASE}/search/?query={q}")
                        page.wait_for_timeout(3000)  # resultados carregam via JavaScript
                        url = fragrantica.melhor_resultado(page.content(), perfume["marca"], perfume["nome"],
                                                           perfume["concentracao"])
                        if not url:
                            con.execute("UPDATE perfumes SET status='nao_encontrado' WHERE id=?", (perfume["id"],))
                            con.commit()
                            log(f"Não encontrado: {rotulo} (dá para colar o link manualmente na interface)")
                            continue
                        pausa(random.uniform(4, 12))  # "lendo" os resultados antes de clicar
                    dados = fragrantica.extrair_perfume(visitar(page, url))
                    novos = salvar(con, perfume, url, dados)
                    log(f"OK: {rotulo} — {len(dados['acordes'])} acordes, {novos} review(s) novo(s)")
                except Interrompido:
                    log("Coleta interrompida.")
                    break
                except PermissionError as e:
                    log(f"Parando a rodada: {e}")
                    break
                except Exception as e:  # noqa: BLE001 — um perfume com problema não derruba a rodada
                    con.execute("UPDATE perfumes SET tentativas=tentativas+1 WHERE id=?", (perfume["id"],))
                    con.commit()
                    log(f"Erro em {rotulo}: {e}")
        except Interrompido:
            log("Coleta interrompida.")
        finally:
            ctx.close()
