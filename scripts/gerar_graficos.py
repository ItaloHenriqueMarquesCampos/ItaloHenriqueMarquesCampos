#!/usr/bin/env python3
"""Gera os gráficos do README do perfil, em SVG claro e escuro.

- Contribuições: últimos 12 meses (o mês atual entra como "em andamento"). Lidas da API
  GraphQL do GitHub quando existe GITHUB_TOKEN (no GitHub Actions) e, se não, da página
  pública de contribuições do perfil.
- Números, linguagens e portfólio: graficos/dados.json. Atualize esse arquivo à mão quando
  os números mudarem e rode o script de novo.

Uso: python3 scripts/gerar_graficos.py
Só usa a biblioteca padrão do Python.
"""
import calendar
import datetime as dt
import html
import json
import os
import re
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "graficos"
README = RAIZ / "README.md"
USUARIO = "ItaloHenriqueMarquesCampos"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
FONTE = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
LARGURA = 840

# Paleta de referência (dataviz), validada nas superfícies do GitHub (#ffffff e #0d1117).
TEMAS = {
    "claro": {
        "tinta1": "#0b0b0b", "tinta2": "#52514e", "tinta3": "#898781",
        "grade": "#e1e0d9", "base": "#c3c2b7", "borda": "rgba(11,11,11,0.10)",
        "serie1": "#2a78d6", "serie2": "#eb6834", "sobre_cor": "#ffffff",
    },
    "escuro": {
        "tinta1": "#f0efec", "tinta2": "#c3c2b7", "tinta3": "#898781",
        "grade": "#2c2c2a", "base": "#383835", "borda": "rgba(255,255,255,0.10)",
        "serie1": "#3987e5", "serie2": "#d95926", "sobre_cor": "#ffffff",
    },
}


# ---------------------------------------------------------------- dados

def janela_12_meses(hoje):
    """(ano, mês) dos últimos 12 meses, terminando no mês atual."""
    ano, mes = hoje.year, hoje.month
    meses = []
    for _ in range(12):
        meses.append((ano, mes))
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
    return list(reversed(meses))


def contribuicoes_graphql(token, inicio, fim):
    consulta = """query($login: String!, $de: DateTime!, $ate: DateTime!) {
      user(login: $login) { contributionsCollection(from: $de, to: $ate) {
        contributionCalendar { weeks { contributionDays { date contributionCount } } } } } }"""
    corpo = json.dumps({"query": consulta, "variables": {
        "login": USUARIO, "de": f"{inicio}T00:00:00Z", "ate": f"{fim}T23:59:59Z"}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=corpo, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "perfil-graficos"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dados = json.load(r)
    if dados.get("errors"):
        raise RuntimeError(dados["errors"])
    semanas = dados["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for s in semanas for d in s["contributionDays"]}


def contribuicoes_pagina_publica():
    req = urllib.request.Request(f"https://github.com/users/{USUARIO}/contributions",
                                 headers={"User-Agent": "perfil-graficos"})
    with urllib.request.urlopen(req, timeout=60) as r:
        pagina = r.read().decode("utf-8")
    datas = dict(re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*?id="([^"]+)"', pagina))
    datas.update({v: k for k, v in re.findall(r'id="([^"]+)"[^>]*?data-date="(\d{4}-\d{2}-\d{2})"', pagina)})
    dicas = dict(re.findall(r'<tool-tip[^>]*?for="([^"]+)"[^>]*>([^<]*)</tool-tip>', pagina))
    por_dia = {}
    for data, ident in datas.items():
        m = re.match(r"\s*(\d+|No) contribution", dicas.get(ident, ""))
        if m:
            por_dia[data] = 0 if m.group(1) == "No" else int(m.group(1))
    if not por_dia:
        raise RuntimeError("não encontrei os dias na página de contribuições")
    return por_dia


def contribuicoes_por_mes(hoje):
    meses = janela_12_meses(hoje)
    inicio = dt.date(meses[0][0], meses[0][1], 1)
    token = os.environ.get("GITHUB_TOKEN")
    try:
        por_dia = contribuicoes_graphql(token, inicio, hoje) if token else contribuicoes_pagina_publica()
        fonte = "API do GitHub" if token else "página pública do GitHub"
    except Exception as erro:  # a API pode falhar; a página pública é o plano B
        print(f"API indisponível ({erro}); usando a página pública")
        por_dia, fonte = contribuicoes_pagina_publica(), "página pública do GitHub"
    totais = []
    for ano, mes in meses:
        prefixo = f"{ano}-{mes:02d}"
        totais.append(sum(v for d, v in por_dia.items() if d.startswith(prefixo) and d <= hoje.isoformat()))
    ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
    return {"meses": meses, "totais": totais, "parcial": hoje.day < ultimo_dia, "fonte": fonte}


# ---------------------------------------------------------------- SVG

def esc(texto):
    return html.escape(str(texto), quote=True)


def num(n, casas=0):
    """Número no formato brasileiro."""
    texto = f"{n:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def svg(largura, altura, titulo, descricao, corpo):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
            f'viewBox="0 0 {largura} {altura}" role="img" aria-labelledby="t d">'
            f'<title id="t">{esc(titulo)}</title><desc id="d">{esc(descricao)}</desc>'
            f'<g font-family="{esc(FONTE)}">{corpo}</g></svg>\n')


def texto(x, y, conteudo, cor, tamanho=13, peso=400, ancora="start", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{cor}" font-size="{tamanho}" font-weight="{peso}" '
            f'text-anchor="{ancora}"{extra}>{esc(conteudo)}</text>')


def barra_h(x, y, comprimento, espessura, cor, ponta_redonda=True):
    """Barra horizontal: base reta à esquerda, ponta arredondada (4px) à direita."""
    if comprimento <= 0:
        return ""
    r = min(4, espessura / 2, comprimento) if ponta_redonda else 0
    x2 = x + comprimento
    return (f'<path d="M{x:.1f},{y:.1f} H{x2 - r:.1f} Q{x2:.1f},{y:.1f} {x2:.1f},{y + r:.1f} '
            f'V{y + espessura - r:.1f} Q{x2:.1f},{y + espessura:.1f} {x2 - r:.1f},{y + espessura:.1f} '
            f'H{x:.1f} Z" fill="{cor}"/>')


def coluna(x, base, altura, largura, cor):
    """Coluna: base reta embaixo, topo arredondado (4px)."""
    if altura <= 0:
        return ""
    r = min(4, largura / 2, altura)
    topo = base - altura
    return (f'<path d="M{x:.1f},{base:.1f} V{topo + r:.1f} Q{x:.1f},{topo:.1f} {x + r:.1f},{topo:.1f} '
            f'H{x + largura - r:.1f} Q{x + largura:.1f},{topo:.1f} {x + largura:.1f},{topo + r:.1f} '
            f'V{base:.1f} Z" fill="{cor}"/>')


def passo_redondo(maximo, divisoes=4):
    bruto = max(maximo, 1) / divisoes
    potencia = 10 ** len(str(int(bruto))) / 10
    for fator in (1, 2, 2.5, 5, 10):
        if bruto <= fator * potencia:
            return fator * potencia
    return 10 * potencia


def cabecalho(t, titulo, subtitulo):
    return texto(0, 20, titulo, t["tinta1"], 16, 600) + texto(0, 42, subtitulo, t["tinta2"], 13)


def grafico_numeros(t, dados, contrib):
    total = sum(contrib["totais"])
    blocos = [
        ("Contribuições", num(total), "nos últimos 12 meses"),
        ("Dashboards", num(dados["portfolio"]["total"]), "no portfólio público"),
        ("Consultas", num(dados["consultas"]["total"]), dados["consultas"]["nota"]),
        ("Repositórios", num(dados["repositorios"]["total"]), dados["repositorios"]["nota"]),
    ]
    vao, altura = 16, 104
    largura = (LARGURA - 2 - vao * 3) / 4
    corpo = ""
    for i, (rotulo, valor, nota) in enumerate(blocos):
        x = 1 + i * (largura + vao)
        corpo += (f'<rect x="{x:.1f}" y="1" width="{largura:.1f}" height="{altura}" rx="8" fill="none" '
                  f'stroke="{t["borda"]}"/>')
        corpo += texto(x + 16, 28, rotulo, t["tinta2"], 13)
        corpo += texto(x + 16, 66, valor, t["tinta1"], 32, 600)
        corpo += texto(x + 16, 90, nota, t["tinta3"], 12)
    descricao = "; ".join(f"{r}: {v} {n}" for r, v, n in blocos)
    return svg(LARGURA, altura + 2, "Em números", descricao, corpo)


def grafico_contribuicoes(t, contrib, hoje):
    meses, totais = contrib["meses"], contrib["totais"]
    topo_plot, base = 78, 238
    x0, x1 = 44, LARGURA - 8
    passo = passo_redondo(max(totais))
    limite = passo * max(1, -(-max(totais) // passo))
    escala = (base - topo_plot) / limite
    faixa = (x1 - x0) / len(meses)
    largura = min(24, faixa * 0.5)
    total = sum(totais)
    inicio = f"{MESES[meses[0][1] - 1]}/{meses[0][0]}"
    fim = f"{MESES[meses[-1][1] - 1]}/{meses[-1][0]}"
    corpo = cabecalho(t, "Contribuições por mês",
                      f"{num(total)} contribuições de {inicio} a {fim}, incluindo as privadas (exibidas sem detalhes)")
    valor = 0
    while valor <= limite + 0.001:
        y = base - valor * escala
        cor = t["base"] if valor == 0 else t["grade"]
        corpo += f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{cor}" stroke-width="1"/>'
        corpo += texto(x0 - 8, y + 4, num(valor), t["tinta3"], 11, ancora="end", extra=' font-variant-numeric="tabular-nums"')
        valor += passo
    destaque = {totais.index(max(totais)), len(totais) - 1}
    for i, ((ano, mes), qtd) in enumerate(zip(meses, totais)):
        cx = x0 + faixa * i + faixa / 2
        corpo += coluna(cx - largura / 2, base, qtd * escala, largura, t["serie1"])
        rotulo = MESES[mes - 1] + ("*" if i == len(meses) - 1 and contrib["parcial"] else "")
        corpo += texto(cx, base + 18, rotulo, t["tinta2"], 12, ancora="middle")
        if i == 0 or mes == 1:
            corpo += texto(cx, base + 33, str(ano), t["tinta3"], 11, ancora="middle")
        if i in destaque:
            corpo += texto(cx, base - qtd * escala - 7, num(qtd), t["tinta1"], 12, 600, ancora="middle")
    nota = f"Atualizado em {hoje.strftime('%d/%m/%Y')} · fonte: {contrib['fonte']}"
    if contrib["parcial"]:
        nota = "* mês em andamento · " + nota
    corpo += texto(LARGURA - 8, base + 52, nota, t["tinta3"], 11, ancora="end")
    descricao = ", ".join(f"{MESES[m - 1]}/{a}: {q}" for (a, m), q in zip(meses, totais))
    return svg(LARGURA, base + 60, "Contribuições por mês", descricao, corpo)


def grafico_linguagens(t, dados):
    itens = sorted(dados["linguagens"]["itens"], key=lambda i: -i["linhas"])
    total = sum(i["linhas"] for i in itens)
    x0, rotulos, espessura, linha = 0, 150, 16, 36
    disponivel = LARGURA - rotulos - 190
    corpo = cabecalho(t, "Linguagens", dados["linguagens"]["subtitulo"])
    maior = itens[0]["linhas"]
    y = 72
    partes = []
    for item in itens:
        comprimento = disponivel * item["linhas"] / maior
        corpo += texto(x0, y + 12, item["nome"], t["tinta1"], 13)
        corpo += barra_h(rotulos, y, comprimento, espessura, t["serie1"])
        pct = 100 * item["linhas"] / total
        rotulo = f"{num(pct)}% · {num(item['linhas'] / 1000, 1)} mil linhas"
        corpo += texto(rotulos + comprimento + 8, y + 12, rotulo, t["tinta2"], 12)
        partes.append(f"{item['nome']}: {num(pct)}% ({num(item['linhas'])} linhas)")
        y += linha
    corpo += texto(LARGURA - 8, y + 8, dados["linguagens"]["nota"], t["tinta3"], 11, ancora="end")
    return svg(LARGURA, y + 16, "Linguagens", "; ".join(partes), corpo)


def grafico_portfolio(t, dados):
    p = dados["portfolio"]
    ferramentas = p["ferramentas"]
    cores = [t["serie1"], t["serie2"]]
    areas = sorted(p["areas"], key=lambda a: (-sum(a["por_ferramenta"]), a["nome"]))
    rotulos, espessura, linha, vao = 230, 16, 32, 2
    maior = max(sum(a["por_ferramenta"]) for a in areas)
    disponivel = LARGURA - rotulos - 60
    unidade = disponivel / maior
    corpo = cabecalho(t, "Portfólio de dashboards", p["subtitulo"])
    # legenda: nomes e totais em tinta; a cor fica na amostra
    x = 0
    for i, nome in enumerate(ferramentas):
        qtd = sum(a["por_ferramenta"][i] for a in areas)
        corpo += f'<rect x="{x}" y="60" width="12" height="12" rx="3" fill="{cores[i]}"/>'
        legenda = f"{nome} · {qtd}"
        corpo += texto(x + 18, 70, legenda, t["tinta1"], 13)
        x += 18 + len(legenda) * 7.4 + 24
    y = 92
    partes = []
    for area in areas:
        corpo += texto(0, y + 12, area["nome"], t["tinta1"], 13)
        xi = rotulos
        valores = area["por_ferramenta"]
        ultimo = max(i for i, v in enumerate(valores) if v > 0)
        for i, v in enumerate(valores):
            if v == 0:
                continue
            comprimento = v * unidade - (vao if i < ultimo else 0)
            if i == ultimo:
                corpo += barra_h(xi, y, comprimento, espessura, cores[i])
            else:
                corpo += f'<rect x="{xi:.1f}" y="{y}" width="{comprimento:.1f}" height="{espessura}" fill="{cores[i]}"/>'
            xi += comprimento + (vao if i < ultimo else 0)
        corpo += texto(xi + 8, y + 12, num(sum(valores)), t["tinta2"], 12, 600)
        partes.append(f"{area['nome']}: " + ", ".join(f"{ferramentas[i]} {v}" for i, v in enumerate(valores) if v))
        y += linha
    corpo += texto(LARGURA - 8, y + 8, p["nota"], t["tinta3"], 11, ancora="end")
    return svg(LARGURA, y + 16, "Portfólio de dashboards", "; ".join(partes), corpo)


# ---------------------------------------------------------------- README

def tabela_contribuicoes(contrib):
    linhas = ["| Mês | Contribuições |", "|---|---:|"]
    for i, ((ano, mes), qtd) in enumerate(zip(contrib["meses"], contrib["totais"])):
        marca = " (em andamento)" if i == len(contrib["meses"]) - 1 and contrib["parcial"] else ""
        linhas.append(f"| {MESES[mes - 1]}/{ano}{marca} | {qtd} |")
    linhas.append(f"| **Total** | **{sum(contrib['totais'])}** |")
    return "\n".join(linhas)


def atualizar_readme(contrib):
    if not README.exists():
        return
    conteudo = README.read_text(encoding="utf-8")
    novo = re.sub(r"(<!-- contribuicoes:inicio -->).*?(<!-- contribuicoes:fim -->)",
                  lambda m: m.group(1) + "\n" + tabela_contribuicoes(contrib) + "\n" + m.group(2),
                  conteudo, flags=re.S)
    if novo != conteudo:
        README.write_text(novo, encoding="utf-8")


def main():
    hoje = dt.date.fromisoformat(os.environ["DATA_REFERENCIA"]) if os.environ.get("DATA_REFERENCIA") else dt.date.today()
    dados = json.loads((PASTA / "dados.json").read_text(encoding="utf-8"))
    contrib = contribuicoes_por_mes(hoje)
    for nome, t in TEMAS.items():
        (PASTA / f"numeros-{nome}.svg").write_text(grafico_numeros(t, dados, contrib), encoding="utf-8")
        (PASTA / f"contribuicoes-{nome}.svg").write_text(grafico_contribuicoes(t, contrib, hoje), encoding="utf-8")
        (PASTA / f"linguagens-{nome}.svg").write_text(grafico_linguagens(t, dados), encoding="utf-8")
        (PASTA / f"portfolio-{nome}.svg").write_text(grafico_portfolio(t, dados), encoding="utf-8")
    atualizar_readme(contrib)
    print(f"Contribuições ({contrib['fonte']}): " +
          ", ".join(f"{MESES[m - 1]}/{a}={q}" for (a, m), q in zip(contrib["meses"], contrib["totais"])))


if __name__ == "__main__":
    main()
