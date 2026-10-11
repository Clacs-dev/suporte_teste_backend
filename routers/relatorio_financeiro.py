from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import database, models
from routers.cobrancas import valores_contratuais
from fpdf import FPDF, FontFace
import io
import unicodedata
import os
from datetime import datetime

router = APIRouter(tags=["relatorios"])


class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.titulo = 'Relatório Financeiro'
        _fonts = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        self.add_font("Times", "", os.path.join(_fonts, "times.ttf"))
        self.add_font("Times", "B", os.path.join(_fonts, "timesbd.ttf"))
        self.add_font("Times", "I", os.path.join(_fonts, "timesi.ttf"))

    def header(self):
        if self.page_no() == 1:
            try:
                self.image('LogoCLACS.png', 10, 8, 45)
            except Exception:
                pass
            self.set_font('Times', 'B', 18)
            self.cell(0, 10, 'CLACS - SISTEMA DE SUPORTE', 0, 1, 'C')
            self.set_font('Times', 'I', 12)
            self.cell(0, 7, self.titulo, 0, 1, 'C')
            self.set_draw_color(0, 0, 0)
            self.line(self.l_margin, 35, self.w - self.r_margin, 35)
            self.ln(10)

    def footer(self):
        self.set_y(-25)
        self.set_font('Times', '', 7)
        self.set_text_color(128, 128, 128)
        self.cell(0, 4, "Endereco: Municipio de Luanda, Bairro: Cassenda, Rua: casa s/N", 0, 1, 'C')
        self.cell(0, 4, "NF: 541733079", 0, 1, 'C')
        self.cell(0, 4, "Tel. 92 505 439 / 918 94 78", 0, 1, 'C')
        self.set_font('Times', 'I', 8)
        self.cell(0, 6, f'Pagina {self.page_no()} de {{nb}}', 0, 0, 'C')


def clean_text(t):
    if t is None:
        return ""
    t = str(t)
    subs = {
        "\u2013": "-", "\u2014": "-", "\u2012": "-", "\u2015": "-", "\u2011": "-",
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"',
        "\u2026": "...", "\u2022": "-", "\u25cf": "-", "\u25aa": "-",
        "\u2023": "-", "\u2043": "-", "\u00b7": ".", "\u00ab": '"', "\u00bb": '"',
        "\u00a0": " ", "\u200b": "", "\ufeff": "",
    }
    for k, v in subs.items():
        t = t.replace(k, v)
    resultado = []
    for ch in t:
        if ord(ch) < 256 or ch in "áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ":
            resultado.append(ch)
        else:
            resultado.append("")
    return "".join(resultado)


def fmt_moeda(valor, decimais=2):
    """Formata um número no padrão português/angolano: 1.234.567,89"""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        n = 0.0
    s = f"{n:,.{decimais}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _fmt_data(d):
    if d is None:
        return "-"
    if isinstance(d, str):
        try:
            return datetime.fromisoformat(d.replace('Z', '+00:00')).strftime("%d/%m/%Y")
        except Exception:
            return d
    return d.strftime("%d/%m/%Y")


def draw_header(pdf, title):
    hm = pdf.l_margin
    if pdf.get_y() + 20 > pdf.h - 30:
        pdf.add_page()
    pdf.set_fill_color(30, 90, 180)
    pdf.set_text_color(255, 255, 255)
    curr_y = pdf.get_y()
    bw = pdf.w - hm - pdf.r_margin
    pdf.rect(hm, curr_y, bw, 10, 'F')
    pdf.set_font('Times', 'B', 12)
    pdf.set_xy(hm, curr_y)
    pdf.cell(bw, 10, clean_text(title), 0, 1, 'L')
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(255, 255, 255)
    pdf.ln(2)


NOMES_MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
               "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


@router.get("/financeiro")
def relatorio_financeiro(
    tipo: str = Query(default="Todas"),
    conta: str = Query(default=""),
    data_inicio: str = Query(default=""),
    data_fim: str = Query(default=""),
    db: Session = Depends(database.get_db),
):
    hoje = datetime.now()

    q = db.query(models.Movimento)
    if tipo in ("Entrada", "Saida"):
        q = q.filter(models.Movimento.tipo == tipo)
    if conta:
        q = q.filter(models.Movimento.conta_bancaria_id == conta)

    movimentos = q.order_by(models.Movimento.data.asc()).all()

    di = None
    df = None
    if data_inicio:
        try:
            di = datetime.strptime(data_inicio[:10], "%Y-%m-%d")
        except Exception:
            di = None
    if data_fim:
        try:
            df = datetime.strptime(data_fim[:10], "%Y-%m-%d")
        except Exception:
            df = None

    def _no_intervalo(m):
        d = m.data
        if di and (d is None or d < di):
            return False
        if df and (d is None or d > df):
            return False
        return True

    movimentos = [m for m in movimentos if _no_intervalo(m)]

    contas = {c.id: c for c in db.query(models.ContaBancaria).all()}

    entradas = sum(float(m.valor or 0) for m in movimentos if m.tipo == "Entrada")
    saidas = sum(float(m.valor or 0) for m in movimentos if m.tipo == "Saida")
    saldo = entradas - saidas

    pdf = PDF(orientation="L", format="A4")
    pdf.titulo = "Relatório Financeiro"
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font('Times', 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f'Gerado em: {hoje.strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    # ── Filtros aplicados ──────────────────────────────────────────────────────
    draw_header(pdf, "FILTROS APLICADOS")
    pdf.set_font('Times', '', 10)
    pdf.cell(0, 7, f"Tipo: {clean_text(tipo)}", 0, 1)
    pdf.cell(0, 7, f"Conta bancária: {clean_text(contas[conta].banco + (' · ' + contas[conta].numero_conta if contas[conta].numero_conta else '') if conta in contas else 'Todas')}", 0, 1)
    pdf.cell(0, 7, clean_text(f"Período: {data_inicio[:10] if data_inicio else 'Início'} a {data_fim[:10] if data_fim else 'Hoje'}"), 0, 1)
    pdf.ln(4)

    # ── Resumo ─────────────────────────────────────────────────────────────────
    draw_header(pdf, "RESUMO")
    pdf.set_font('Times', '', 10)
    pdf.cell(0, 7, f"Total de movimentos: {len(movimentos)}", 0, 1)
    pdf.cell(0, 7, f"Total de Entradas: Kz {fmt_moeda(entradas)}", 0, 1)
    pdf.cell(0, 7, f"Total de Saídas: Kz {fmt_moeda(saidas)}", 0, 1)
    pdf.cell(0, 7, f"Saldo do período: Kz {fmt_moeda(saldo)}", 0, 1)
    pdf.ln(4)

    # ── Tabela de movimentos ───────────────────────────────────────────────────
    draw_header(pdf, "MOVIMENTOS")
    pdf.set_font('Times', '', 10)

    if not movimentos:
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 7, "Nenhum movimento encontrado para os filtros selecionados.", 1, 1, 'C')
    else:
        linhas_mov = []
        for m in movimentos:
            conta_nome = contas[m.conta_bancaria_id].banco if m.conta_bancaria_id in contas else ""
            linhas_mov.append([
                clean_text(m.numero or ""),
                clean_text(_fmt_data(m.data)),
                clean_text(conta_nome),
                clean_text(m.descricao or ""),
                clean_text(m.destinatario or ""),
                clean_text(m.categoria or ""),
                clean_text(m.forma_pagamento or ""),
                clean_text(m.tipo),
                fmt_moeda(m.valor),
            ])
        rows_mov = [
            ["Nº", "Data", "Conta", "Descrição", "Destinatário", "Categoria", "Forma de pagamento", "Tipo", "Valor"],
            *linhas_mov,
        ]
        with pdf.table(
            rows=rows_mov,
            headings_style=FontFace(emphasis="BOLD", family="Times", size_pt=8, fill_color=(230, 230, 230), color=(0, 0, 0)),
            col_widths=(20, 26, 30, 42, 30, 24, 36, 20, 49),
            text_align=("CENTER", "CENTER", "CENTER", "LEFT", "LEFT", "LEFT", "LEFT", "CENTER", "RIGHT"),
            line_height=5,
            padding=1,
        ):
            pass

    pdf_bytes = bytes(pdf.output())
    pdf_stream = io.BytesIO(pdf_bytes)
    filename = f"relatorio_financeiro_{hoje.strftime('%Y%m%d_%H%M')}.pdf"

    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/cobrancas")
def relatorio_cobrancas(
    mes: int = Query(default=None),
    ano: int = Query(default=None),
    db: Session = Depends(database.get_db),
):
    hoje = datetime.now()
    mes = mes or hoje.month
    ano = ano or hoje.year

    clientes = (
        db.query(models.Cliente)
        .filter(models.Cliente.status == "Ativo")
        .order_by(models.Cliente.nome.asc())
        .all()
    )
    registos = {
        c.cliente_id: c
        for c in db.query(models.Cobranca).filter(
            models.Cobranca.mes == mes, models.Cobranca.ano == ano
        ).all()
    }
    contratuais = valores_contratuais(db)

    linhas = []
    for cli in clientes:
        cob = registos.get(cli.id)
        linhas.append({
            "nome": cli.nome,
            "email": cli.email or "",
            "empresa": cli.empresa or "",
            "valor_contratual": contratuais.get(cli.id, 0.0),
            "pago": bool(cob.pago) if cob else False,
            "valor": float(cob.valor or 0) if cob else 0.0,
            "data_pagamento": cob.data_pagamento if cob else None,
            "observacao": cob.observacao if cob else "",
        })

    pagantes = sum(1 for l in linhas if l["pago"])
    total_cobrado = sum(l["valor"] for l in linhas)
    total_pago = sum(l["valor"] for l in linhas if l["pago"])
    total_nao_pago = sum(l["valor_contratual"] for l in linhas if not l["pago"])

    pdf = PDF(orientation="L", format="A4")
    pdf.titulo = "Mapa de Cobranças"
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font('Times', 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f'Gerado em: {hoje.strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    draw_header(pdf, f"MAPAS DE COBRANÇAS — {NOMES_MESES[mes].upper()} {ano}")
    pdf.set_font('Times', '', 10)
    pdf.cell(0, 7, f"Total de clientes: {len(linhas)}", 0, 1)
    pdf.cell(0, 7, f"Pago: {pagantes}   |   Não pago: {len(linhas) - pagantes}", 0, 1)
    pdf.cell(0, 7, f"Total a cobrar: Kz {fmt_moeda(total_cobrado)}   |   Total recebido: Kz {fmt_moeda(total_pago)}   |   Total não pago: Kz {fmt_moeda(total_nao_pago)}", 0, 1)
    pdf.ln(4)

    linhas_cob = []
    for l in linhas:
        linhas_cob.append([
            clean_text(l["empresa"]),
            clean_text(l.get("email") or ""),
            clean_text(l["nome"]),
            "Sim" if l["pago"] else "Não",
            fmt_moeda(l['valor_contratual']),
            fmt_moeda(l['valor']),
            clean_text(_fmt_data(l["data_pagamento"])),
            clean_text(l["observacao"]),
        ])
    rows_cob = [
        ["Cliente", "Email", "Responsável", "Pago?", "Valor contratual", "Valor", "Data pago", "Observações"],
        *linhas_cob,
    ]
    with pdf.table(
        rows=rows_cob,
        headings_style=FontFace(emphasis="BOLD", family="Times", size_pt=8, fill_color=(230, 230, 230), color=(0, 0, 0)),
        col_widths=(55, 42, 35, 15, 30, 30, 27, 40),
        text_align=("LEFT", "LEFT", "LEFT", "CENTER", "RIGHT", "RIGHT", "CENTER", "LEFT"),
        line_height=5,
        padding=1,
    ):
        pass

    pdf_bytes = bytes(pdf.output())
    pdf_stream = io.BytesIO(pdf_bytes)
    filename = f"relatorio_cobrancas_{ano}_{mes:02d}_{hoje.strftime('%H%M')}.pdf"

    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/cobrancas/historico")
def relatorio_cobrancas_historico(db: Session = Depends(database.get_db)):
    registos = db.query(models.Cobranca).all()

    hoje = datetime.now().replace(day=1)

    # Mês a mês desde o primeiro registo até ao mais recente (incluindo o mês atual)
    ano_meses = sorted({(c.ano, c.mes) for c in registos})
    if ano_meses:
        inicio = (ano_meses[0][1], ano_meses[0][0])
        fim = (ano_meses[-1][1], ano_meses[-1][0])
    else:
        inicio = fim = (hoje.month, hoje.year)

    atual = (hoje.month, hoje.year)
    if fim < atual:
        fim = atual

    meses = []
    m, a = inicio
    while (m, a) <= fim:
        meses.append((m, a))
        m += 1
        if m > 12:
            m = 1
            a += 1

    clientes = (
        db.query(models.Cliente)
        .filter(models.Cliente.status == "Ativo")
        .order_by(models.Cliente.nome.asc())
        .all()
    )
    por_cliente = {}
    for c in registos:
        por_cliente.setdefault(c.cliente_id, []).append(c)

    agora = datetime.now()
    pdf = PDF(orientation="L", format="A4")
    pdf.titulo = "Histórico de Cobranças por Cliente"
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font('Times', 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f'Gerado em: {agora.strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    draw_header(pdf, "HISTÓRICO DE PAGAMENTOS POR CLIENTE")

    nm = len(meses)
    mw = max(12, min(26, int((pdf.w - 20 - 95) / max(nm + 1, 1))))
    headings = ["Cliente", "Empresa"] + [f"{m:02d}/{a}" for m, a in meses] + ["Total"]
    widths = [55, 40] + [mw] * nm + [mw]

    linhas_hist = []
    for cli in clientes:
        regs = {(c.mes, c.ano): c for c in por_cliente.get(cli.id, [])}
        nome = clean_text((cli.nome or "").strip())
        empresa = clean_text((cli.empresa or "").strip())
        total = sum(float(regs[k].valor or 0) for k in regs if regs[k].pago)
        celulas = [nome, empresa]
        for m, a in meses:
            cob = regs.get((m, a))
            if cob and cob.pago:
                texto = "Sim"
            elif cob:
                texto = "Não"
            else:
                texto = ""
            celulas.append(clean_text(texto))
        celulas.append(fmt_moeda(total))
        linhas_hist.append(celulas)

    rows_hist = [headings, *linhas_hist]
    with pdf.table(
        rows=rows_hist,
        headings_style=FontFace(emphasis="BOLD", family="Times", size_pt=7, fill_color=(230, 230, 230)),
        col_widths=tuple(widths),
        text_align="CENTER",
        line_height=4,
        padding=0.5,
    ):
        pass

    pdf.ln(3)
    pdf.set_font('Times', 'I', 8)
    pdf.cell(0, 5, clean_text("Legenda: Sim = pagou no mês; Não = não pagou no mês; vazio = sem registo no mês."), 0, 1)

    pdf_bytes = bytes(pdf.output())
    pdf_stream = io.BytesIO(pdf_bytes)
    filename = f"relatorio_cobrancas_historico_{agora.strftime('%Y%m%d_%H%M')}.pdf"

    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )