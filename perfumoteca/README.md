# Perfumoteca

Biblioteca pessoal de perfumes que roda no seu computador. O app:

1. lê a lista de perfumes de um feed de loja (ex.: o XML da Lojabit);
2. procura cada perfume no Fragrantica e guarda acordes, pirâmide olfativa, nota,
   votações (fixação, projeção, estação) e os reviews;
3. classifica cada um (família olfativa, estações, fixação alta, sentimento dos reviews);
4. mostra tudo numa interface no navegador, como uma estante de biblioteca.

![Biblioteca](docs/biblioteca.png)
![Ficha do perfume](docs/perfume.png)

## Instalação (uma vez)

Precisa do [Python 3.10+](https://www.python.org/downloads/) (no Windows, marque "Add Python to PATH").

```bash
cd perfumoteca
python -m venv .venv
# Windows:  .venv\Scripts\activate      Mac/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Uso

```bash
python main.py importar   # baixa o feed da loja e monta a lista (≈540 perfumes únicos)
python main.py login      # abre o navegador: entre na sua conta do Fragrantica e aperte ENTER
python main.py coletar --limite 5   # primeira rodada pequena para conferir
python main.py web        # abra http://127.0.0.1:5000
```

Para deixar rodando sozinho (atualiza o feed uma vez por dia e coleta aos poucos):

```bash
python main.py auto --inicio 9 --fim 23
```

## Como a coleta se comporta

- Navegador de verdade, visível, com o **seu login salvo** em `dados/navegador/`.
- **1 a 2 minutos** (aleatório) entre perfumes; rola a página aos poucos, com pausas irregulares.
- No modo `auto`: rodadas de 8 a 15 perfumes, descanso de 20 a 60 minutos entre elas, e só no horário definido.
- Se aparecer verificação ("Just a moment…"/captcha), o coletor **pausa e espera você resolver** na janela.
  Se o site responder "muitas requisições" (429), ele **para** a rodada.
- Perfumes já coletados são revisitados a cada 30 dias (`--revisitar`) para buscar **reviews novos**,
  sem duplicar os antigos.
- Quando a busca não acha o perfume certo, ele fica como "não encontrado": abra a ficha na
  interface e cole o link correto do Fragrantica.

Uso pessoal: mantenha o ritmo baixo e não publique os textos dos reviews. Eles pertencem a quem escreveu.

## Onde ficam os dados

Tudo num único arquivo: `dados/perfumoteca.db` (SQLite).

- Fácil de fazer backup (é só copiar o arquivo).
- Dá para abrir e pesquisar com o [DB Browser for SQLite](https://sqlitebrowser.org/) ou exportar para CSV/Excel.
- Tem busca de texto completo (nome, marca, notas, acordes, família e reviews).
- Tabelas: `perfumes` (um por perfume, campos de listas em JSON) e `reviews` (um por review).

## Adicionar mais perfumes

Rode `python main.py importar <URL ou arquivo .xml>` com qualquer feed no formato Google Merchant.
Para outras fontes, basta inserir linhas na tabela `perfumes` com `status='pendente'`.

## Se o Fragrantica mudar o layout

Todos os seletores ficam em `perfumoteca/fragrantica.py`. Os testes (`python -m pytest tests`)
usam uma página de exemplo. Salve uma página real (Ctrl+S) para ajustar o parser se precisar.
