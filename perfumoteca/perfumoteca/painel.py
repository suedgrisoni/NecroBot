"""Controla, a partir da interface, as tarefas que usam o navegador (login e coleta).

Só uma tarefa roda por vez, porque o perfil do navegador não pode ser aberto duas vezes.
"""
import random
import threading
import time
from datetime import datetime

from . import collector, db, feed

FEED_PADRAO = "https://www.lojabit.com/xml/2cabf/googlemerchant.xml"


class Painel:
    def __init__(self):
        self.tarefa = None          # "login" | "coleta" | "auto" | None
        self.thread = None
        self.login_ok = threading.Event()
        self.lock = threading.Lock()

    @property
    def ocupado(self):
        return self.thread is not None and self.thread.is_alive()

    def _iniciar(self, nome, alvo, *args):
        with self.lock:
            if self.ocupado:
                return False
            collector.PARAR.clear()
            self.tarefa = nome
            self.thread = threading.Thread(target=self._rodar, args=(alvo, args), daemon=True)
            self.thread.start()
            return True

    def _rodar(self, alvo, args):
        try:
            alvo(*args)
        except collector.Interrompido:
            collector.log("Interrompido.")
        except Exception as e:  # noqa: BLE001 — mostrar o erro no painel em vez de derrubar o app
            if "Executable doesn't exist" in str(e):
                collector.log("Navegador da coleta não instalado. Rode: python -m playwright install chromium")
            else:
                collector.log(f"Erro: {e}")
        finally:
            self.tarefa = None

    def login(self, usuario=None, senha=None):
        self.login_ok.clear()
        return self._iniciar("login", collector.login, self.login_ok, usuario, senha)

    def concluir_login(self):
        self.login_ok.set()

    def coletar(self, limite):
        return self._iniciar("coleta", collector.coletar, limite)

    def auto(self, inicio=9, fim=23, limite=15, url_feed=FEED_PADRAO):
        return self._iniciar("auto", self._auto, inicio, fim, limite, url_feed)

    def parar(self):
        collector.PARAR.set()
        self.login_ok.set()

    @staticmethod
    def _auto(inicio, fim, limite, url_feed):
        """Rodadas pequenas com descansos longos, só no horário escolhido."""
        ultimo_feed = None
        collector.log(f"Modo automático ligado ({inicio}h às {fim}h).")
        while not collector.PARAR.is_set():
            agora = datetime.now()
            if ultimo_feed != agora.date():
                try:
                    collector.log(f"Feed atualizado: {feed.importar(url_feed)} perfumes na biblioteca.")
                except Exception as e:  # noqa: BLE001 — sem feed hoje, segue coletando o que já existe
                    collector.log(f"Não consegui atualizar o feed: {e}")
                ultimo_feed = agora.date()
            if inicio <= agora.hour < fim:
                collector.coletar(limite=random.randint(min(8, limite), limite))
                descanso = random.uniform(20, 60) * 60
            else:
                descanso = 30 * 60
            if collector.PARAR.is_set():
                break
            collector.log(f"Descansando {descanso / 60:.0f} min até a próxima rodada.")
            collector.pausa(descanso)

    def estado(self):
        con = db.connect()
        contagem = dict(con.execute("SELECT status, COUNT(*) FROM perfumes GROUP BY status").fetchall())
        prog = dict(collector.PROGRESSO)
        if prog["ate"]:
            prog["restante"] = max(0, round(prog.pop("ate") - time.time()))
        return {
            "tarefa": self.tarefa if self.ocupado else None,
            "conta": collector.conta(),
            "progresso": prog,
            "contagem": contagem,
            "total": sum(contagem.values()),
            "reviews": con.execute("SELECT COUNT(*) FROM reviews").fetchone()[0],
            "log": list(collector.LOG)[-80:],
        }


painel = Painel()
