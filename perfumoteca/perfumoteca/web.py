"""Interface local em formato de biblioteca: http://127.0.0.1:5000"""
from flask import Flask, abort, redirect, render_template, request, url_for

from . import db

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


def rodar(porta=5000):
    app.run(host="127.0.0.1", port=porta, debug=False)
