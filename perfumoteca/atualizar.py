"""Atualiza a Perfumoteca a partir do GitHub, preservando dados e instalação.

Roda sozinho pelo Perfumoteca.bat a cada abertura. Só usa a biblioteca padrão do Python.
"""
import io
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = "suedgrisoni/NecroBot"
RAMO = "ccr-e767118b-7h76n5"
PASTA_NO_REPO = "perfumoteca/"
AQUI = Path(__file__).resolve().parent
VERSAO = AQUI / "versao.txt"
PRESERVAR = {"dados", ".venv", "versao.txt"}
# O .bat está em execução enquanto isto roda; a versão nova é trocada por ele na próxima abertura.
EM_USO = {"Perfumoteca.bat": "Perfumoteca.novo.bat"}


def _baixar(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Perfumoteca-atualizador"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def versao_remota():
    dados = json.loads(_baixar(f"https://api.github.com/repos/{REPO}/commits/{RAMO}"))
    return dados["sha"], dados["commit"]["committer"]["date"][:10]


def atualizar():
    try:
        sha, data = versao_remota()
    except Exception as e:  # noqa: BLE001 — sem internet ou GitHub fora: abre a versão atual
        print(f"Não foi possível verificar atualizações ({e}). Abrindo a versão atual.")
        return
    atual = VERSAO.read_text().split()[0] if VERSAO.exists() else None
    if sha == atual:
        print("Perfumoteca já está atualizada.")
        return

    print(f"Baixando atualização de {data}...")
    pacote = zipfile.ZipFile(io.BytesIO(_baixar(f"https://github.com/{REPO}/archive/{sha}.zip", timeout=120)))
    req_antes = (AQUI / "requirements.txt").read_bytes() if (AQUI / "requirements.txt").exists() else b""
    for item in pacote.infolist():
        partes = item.filename.split("/", 1)  # "NecroBot-<sha>/perfumoteca/..."
        if len(partes) < 2 or not partes[1].startswith(PASTA_NO_REPO) or item.is_dir():
            continue
        relativo = partes[1][len(PASTA_NO_REPO):]
        if not relativo or relativo.split("/")[0] in PRESERVAR:
            continue
        destino = AQUI / EM_USO.get(relativo, relativo)
        destino.parent.mkdir(parents=True, exist_ok=True)
        with pacote.open(item) as origem, open(destino, "wb") as saida:
            shutil.copyfileobj(origem, saida)
    novo, atual_bat = AQUI / "Perfumoteca.novo.bat", AQUI / "Perfumoteca.bat"
    if novo.exists() and (not atual_bat.exists() or novo.read_bytes() == atual_bat.read_bytes()):
        novo.replace(atual_bat)  # igual ao atual (nada a trocar) ou não havia atalho

    if (AQUI / "requirements.txt").read_bytes() != req_antes:
        print("Instalando novas dependências...")
        subprocess.call([sys.executable, "-m", "pip", "install", "-q", "-r", str(AQUI / "requirements.txt")])
    VERSAO.write_text(f"{sha} {data}\n")
    print("Perfumoteca atualizada.")


if __name__ == "__main__":
    try:
        atualizar()
    except Exception as e:  # noqa: BLE001 — uma atualização com problema nunca impede o app de abrir
        print(f"Atualização falhou ({e}). Abrindo a versão atual.")
