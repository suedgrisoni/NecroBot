"""Perfumoteca — biblioteca pessoal de perfumes.

Uso:
  python main.py importar [URL_OU_ARQUIVO]   importa/atualiza a lista de perfumes do feed
  python main.py login                       abre o navegador para você entrar no Fragrantica
  python main.py coletar [--limite 20]       coleta uma rodada (1–2 min entre perfumes)
  python main.py auto                        roda sozinho: atualiza o feed e coleta aos poucos
  python main.py web                         abre a biblioteca em http://127.0.0.1:5000

Sem argumentos (ou com duplo clique), abre o app direto no navegador: dá para fazer
login, buscar, coletar e navegar pela biblioteca por botões.
"""
import argparse
import threading
import webbrowser

from perfumoteca import collector, feed, painel, web

FEED_PADRAO = painel.FEED_PADRAO


def auto(args):
    try:
        painel.Painel._auto(args.inicio, args.fim, args.limite, args.feed)
    except collector.Interrompido:
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("importar")
    s.add_argument("feed", nargs="?", default=FEED_PADRAO)
    sub.add_parser("login")
    s = sub.add_parser("coletar")
    s.add_argument("--limite", type=int, default=20)
    s.add_argument("--revisitar", type=int, default=30, help="dias até buscar reviews novos de novo")
    s = sub.add_parser("auto")
    s.add_argument("--feed", default=FEED_PADRAO)
    s.add_argument("--limite", type=int, default=15, help="máximo de perfumes por rodada")
    s.add_argument("--inicio", type=int, default=9, help="hora de começar (0–23)")
    s.add_argument("--fim", type=int, default=23, help="hora de parar (0–23)")
    s = sub.add_parser("web")
    s.add_argument("--porta", type=int, default=5000)
    args = ap.parse_args()

    if args.cmd == "importar":
        print(f"{feed.importar(args.feed)} perfumes na biblioteca.")
    elif args.cmd == "login":
        collector.login()
    elif args.cmd == "coletar":
        collector.coletar(limite=args.limite, revisitar_dias=args.revisitar)
    elif args.cmd == "auto":
        auto(args)
    else:
        porta = getattr(args, "porta", 5000)
        if args.cmd is None:
            threading.Timer(1.5, webbrowser.open, (f"http://127.0.0.1:{porta}/painel",)).start()
        web.rodar(porta)


if __name__ == "__main__":
    main()
