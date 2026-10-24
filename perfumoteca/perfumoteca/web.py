"""Interface local em formato de biblioteca: http://127.0.0.1:5000"""
from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from . import db, feed
from .painel import FEED_PADRAO, painel

app = Flask(__name__)
POR_PAGINA = 48


@app.route("/")
def biblioteca():
    con = db.connect()
    q = request.args.get("q", "").strip()
    marca = request.args.get("marca", "")
    familia = request.args.get("familia", "")
    status = request.args.get("status", "")
    ordem = request.args.get("ordem", "nome")
    pagina = max(1, request.args.get("p", 1, type=int))

    where, params = [], []
    if q:
        termos = " ".join(f'"{t}"*' for t in q.replace('"', "").split())
        where.append("id IN (SELECT rowid FROM busca WHERE busca MATCH ?)")
        params.append(termos)
        # perfumes ainda não coletados não estão no índice: busca simples pelo nome também
        where[-1] = f"({where[-1]} OR nome LIKE ? OR marca LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    for campo, valor in (("marca", marca), ("familia", familia), ("status", status)):
        if valor:
            where.append(f"{campo} = ?")
            params.append(valor)
    sql_where = ("WHERE " + " AND ".join(where)) if where else ""
    ordem_sql = {"nome": "nome", "marca": "marca, nome", "nota": "nota IS NULL, nota DESC",
                 "recentes": "coletado_em IS NULL, coletado_em DESC"}.get(ordem, "nome")

    total = con.execute(f"SELECT COUNT(*) FROM perfumes {sql_where}", params).fetchone()[0]
    perfumes = [db.row_to_dict(r) for r in con.execute(
        f"SELECT * FROM perfumes {sql_where} ORDER BY {ordem_sql} LIMIT ? OFFSET ?",
        params + [POR_PAGINA, (pagina - 1) * POR_PAGINA])]
    contagem = dict(con.execute("SELECT status, COUNT(*) FROM perfumes GROUP BY status").fetchall())
    return render_template(
        "biblioteca.html", perfumes=perfumes, total=total, pagina=pagina,
        paginas=max(1, -(-total // POR_PAGINA)), contagem=contagem,
        n_reviews=con.execute("SELECT COUNT(*) FROM reviews").fetchone()[0],
        marcas=[r[0] for r in con.execute("SELECT DISTINCT marca FROM perfumes WHERE marca<>'' ORDER BY marca")],
        familias=[r[0] for r in con.execute(
            "SELECT DISTINCT familia FROM perfumes WHERE familia IS NOT NULL ORDER BY familia")],
        filtros=request.args)


@app.route("/perfume/<int:pid>")
def perfume(pid):
    con = db.connect()
    row = con.execute("SELECT * FROM perfumes WHERE id=?", (pid,)).fetchone()
    if not row:
        abort(404)
    reviews = con.execute("SELECT * FROM reviews WHERE perfume_id=? ORDER BY data DESC, id DESC", (pid,)).fetchall()
    sent = dict(con.execute(
        "SELECT sentimento, COUNT(*) FROM reviews WHERE perfume_id=? GROUP BY sentimento", (pid,)).fetchall())
    return render_template("perfume.html", p=db.row_to_dict(row), reviews=reviews, sent=sent)


@app.post("/perfume/<int:pid>/link")
def definir_link(pid):
    """Permite colar manualmente o link do Fragrantica quando a busca automática erra."""
    url = request.form.get("url", "").strip()
    con = db.connect()
    if url.startswith("https://www.fragrantica.com/perfume/"):
        con.execute("UPDATE perfumes SET fragrantica_url=?, status='pendente', tentativas=0 WHERE id=?", (url, pid))
        con.commit()
    return redirect(url_for("perfume", pid=pid))


@app.route("/painel")
def tela_painel():
    con = db.connect()
    contagem = dict(con.execute("SELECT status, COUNT(*) FROM perfumes GROUP BY status").fetchall())
    perfil_existe = (db.DATA_DIR / "navegador").exists()
    return render_template("painel.html", contagem=contagem, feed_padrao=FEED_PADRAO,
                           perfil_existe=perfil_existe, msg=request.args.get("msg"))


@app.get("/painel/estado")
def painel_estado():
    return jsonify(painel.estado())


@app.post("/painel/<acao>")
def painel_acao(acao):
    f = request.form
    if acao == "login":
        ok = painel.login()
    elif acao == "login-ok":
        painel.concluir_login()
        ok = True
    elif acao == "coletar":
        ok = painel.coletar(f.get("limite", 5, type=int))
    elif acao == "auto":
        ok = painel.auto(f.get("inicio", 9, type=int), f.get("fim", 23, type=int), f.get("limite", 15, type=int))
    elif acao == "parar":
        painel.parar()
        ok = True
    elif acao == "importar":
        try:
            total = feed.importar(f.get("url") or FEED_PADRAO)
            return redirect(url_for("tela_painel", msg=f"Feed importado: {total} perfumes na biblioteca."))
        except Exception as e:  # noqa: BLE001
            return redirect(url_for("tela_painel", msg=f"Não consegui importar o feed: {e}"))
    else:
        abort(404)
    return redirect(url_for("tela_painel", msg=None if ok else "Já existe uma tarefa rodando. Pare-a antes."))


@app.post("/perfume/novo")
def novo_perfume():
    """Adiciona um perfume à fila: pelo link do Fragrantica ou por marca + nome."""
    f = request.form
    url = f.get("url", "").strip()
    marca, nome = f.get("marca", "").strip(), f.get("nome", "").strip()
    if url.startswith("https://www.fragrantica.com/perfume/") and not nome:
        partes = url.rstrip("/").split("/")
        marca = marca or partes[-2].replace("-", " ")
        nome = partes[-1].rsplit("-", 1)[0].replace("-", " ")
    if not nome:
        return redirect(url_for("tela_painel", msg="Informe o nome do perfume ou o link do Fragrantica."))
    con = db.connect()
    con.execute("""INSERT INTO perfumes(chave, nome, marca, categoria_loja, fragrantica_url) VALUES (?,?,?,?,?)
                   ON CONFLICT(chave) DO UPDATE SET fragrantica_url=COALESCE(excluded.fragrantica_url, fragrantica_url)""",
                (feed.normalizar(f"{marca} {nome}"), nome, marca, "Adicionado à mão", url or None))
    con.commit()
    pid = con.execute("SELECT id FROM perfumes WHERE chave=?", (feed.normalizar(f"{marca} {nome}"),)).fetchone()[0]
    return redirect(url_for("perfume", pid=pid))


def rodar(porta=5000):
    app.run(host="127.0.0.1", port=porta, debug=False)
