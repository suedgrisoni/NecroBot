"""Coletor: abre um navegador de verdade (com o seu login salvo) e visita os perfumes
devagar, um a cada 1–2 minutos, como uma pessoa navegando.

Não tenta burlar proteções: se o site pedir verificação, o coletor pausa e espera
você resolver na janela. Se o site sinalizar excesso de acessos, ele para.
"""
import json
import random
import threading
import time
import urllib.parse
from collections import deque
from datetime import datetime

from . import classify, db, fragrantica

PERFIL = db.DATA_DIR / "navegador"
INTERVALO = (60, 120)  # segundos entre perfumes
PARAR = threading.Event()   # acionado pelo botão "Parar" do painel
LOG = deque(maxlen=300)     # últimas mensagens, mostradas no painel
CONTA = db.DATA_DIR / "conta.json"
# O que está acontecendo agora, para a tela de progresso.
PROGRESSO = {"etapa": None, "perfume": None, "rodada": [0, 0], "ate": None}


class Interrompido(Exception):
    pass


def log(msg):
    linha = f"[{datetime.now():%H:%M:%S}] {msg}"
    LOG.append(linha)
    print(linha, flush=True)


def etapa(texto, segundos=None):
    PROGRESSO["etapa"] = texto
    PROGRESSO["ate"] = time.time() + segundos if segundos else None


def pausa(segundos):
    """Espera, mas acorda na hora se pedirem para parar."""
    if PARAR.wait(segundos):
        raise Interrompido()


def abrir_navegador(p):
    PERFIL.mkdir(parents=True, exist_ok=True)
    ctx = p.chromium.launch_persistent_context(
        str(PERFIL), headless=False, viewport={"width": 1366, "height": 850}, locale="en-US")
    return ctx, (ctx.pages[0] if ctx.pages else ctx.new_page())


def conta():
    try:
        return json.loads(CONTA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"logado": False}


def _salvar_conta(**dados):
    CONTA.parent.mkdir(parents=True, exist_ok=True)
    CONTA.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def esta_logado(page):
    """Logado = existe um link de sair/perfil na página e não estamos mais na tela de login."""
    if "/login" in page.url:
        return False
    return page.locator("a[href*='logout' i], a[href*='/member/']").count() > 0


def _preencher_login(page, usuario, senha):
    campo_usuario = page.locator("input[type=email], input[name*=user i], input[name*=email i], "
                                 "input[name*=login i], input[id*=user i]").first
    campo_senha = page.locator("input[type=password]").first
    if not campo_usuario.count() or not campo_senha.count():
        log("Não achei os campos de login; termine o login na janela do navegador.")
        return
    for campo, texto in ((campo_usuario, usuario), (campo_senha, senha)):
        campo.click()
        campo.press_sequentially(texto, delay=random.randint(60, 160))  # digita como uma pessoa
        page.wait_for_timeout(random.randint(400, 1200))
    campo_senha.press("Enter")
    log("Dados de login enviados. Se aparecer verificação, resolva na janela.")


def login(concluido=None, usuario=None, senha=None):
    """Abre o Fragrantica para você entrar na sua conta. A sessão fica salva no perfil local.

    Se `usuario` e `senha` forem informados, o app digita por você (a senha não é guardada).
    Termina quando o login é detectado, quando `concluido` (Event) é acionado, quando a
    janela é fechada ou, no terminal, quando você aperta ENTER.
    """
    from playwright.sync_api import sync_playwright
    etapa("Fazendo login")
    with sync_playwright() as p:
        ctx, page = abrir_navegador(p)
        try:
            page.goto(fragrantica.BASE + "/login/", wait_until="domcontentloaded")
            log("Janela de login aberta.")
            if usuario and senha:
                page.wait_for_timeout(random.randint(1500, 3000))
                _preencher_login(page, usuario, senha)
            if concluido is None:
                input("Faça login na janela do navegador e depois aperte ENTER aqui... ")
            else:
                limite = time.time() + 10 * 60
                while not concluido.is_set() and not PARAR.is_set() and not page.is_closed() \
                        and time.time() < limite:
                    page.wait_for_timeout(2000)
                    if esta_logado(page):
                        break
            logado = not page.is_closed() and esta_logado(page) or bool(concluido and concluido.is_set())
            _salvar_conta(logado=logado, usuario=usuario or conta().get("usuario"),
                          quando=datetime.now().strftime("%d/%m/%Y %H:%M"))
            log("Login confirmado. Pronto para coletar." if logado else "Login não confirmado.")
        finally:
            etapa(None)
            try:
                ctx.close()
            except Exception:  # noqa: BLE001 — a janela pode já ter sido fechada
                pass


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
            etapa("Aguardando você resolver a verificação na janela")
        pausa(5)
    else:
        raise PermissionError("Verificação não resolvida.")
    pausa(random.uniform(2, 4))
    etapa("Lendo a página")
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
    PROGRESSO["rodada"] = [0, len(fila)]
    with sync_playwright() as p:
        ctx, page = abrir_navegador(p)
        try:
            for i, perfume in enumerate(fila):
                if PARAR.is_set():
                    break
                if i:
                    espera = random.uniform(*intervalo)
                    log(f"Pausa de {espera:.0f}s...")
                    etapa("Pausa antes do próximo perfume", espera)
                    pausa(espera)
                PROGRESSO["rodada"] = [i + 1, len(fila)]
                PROGRESSO["perfume"] = {k: perfume[k] for k in ("id", "nome", "marca", "imagem")}
                rotulo = f"{perfume['marca']} {perfume['nome']}"
                try:
                    url = perfume["fragrantica_url"]
                    if not url:
                        etapa("Procurando no Fragrantica")
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
                    etapa("Abrindo a página do perfume")
                    dados = fragrantica.extrair_perfume(visitar(page, url))
                    etapa("Classificando e salvando")
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
            etapa(None)
            PROGRESSO["perfume"] = None
            ctx.close()
