from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import database, models
from fpdf import FPDF
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
            self.line(10, 35, self.w - 10, 35)
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
    if pdf.get_y() + 20 > pdf.h - 30:
        pdf.add_page()
    pdf.set_fill_color(30, 90, 180)
    pdf.set_text_color(255, 255, 255)
    curr_y = pdf.get_y()
    pdf.rect(10, curr_y, pdf.w - 20, 10, 'F')
    pdf.set_font('Times', 'B', 12)
    pdf.set_xy(12, curr_y)
    pdf.cell(pdf.w - 20, 10, clean_text(title), 0, 1, 'L')
    pdf.set_text_color(0, 0, 0)
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
    pdf.cell(0, 7, f"Total de Entradas: Kz {entradas:,.2f}", 0, 1)
    pdf.cell(0, 7, f"Total de Saídas: Kz {saidas:,.2f}", 0, 1)
    pdf.cell(0, 7, f"Saldo do período: Kz {saldo:,.2f}", 0, 1)
    pdf.ln(4)

    # ── Tabela de movimentos ───────────────────────────────────────────────────
    draw_header(pdf, "MOVIMENTOS")
    pdf.set_font('Times', 'B', 8)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(20, 7, "Nº", 1, 0, 'C', True)
    pdf.cell(26, 7, "Data", 1, 0, 'C', True)
    pdf.cell(30, 7, "Conta", 1, 0, 'C', True)
    pdf.cell(42, 7, "Descrição", 1, 0, 'C', True)
    pdf.cell(30, 7, "Destinatário", 1, 0, 'C', True)
    pdf.cell(24, 7, "Categoria", 1, 0, 'C', True)
    pdf.cell(36, 7, "Forma de pagamento", 1, 0, 'C', True)
    pdf.cell(20, 7, "Tipo", 1, 0, 'C', True)
    pdf.cell(49, 7, "Valor", 1, 1, 'C', True)

    pdf.set_font('Times', '', 8)
    if not movimentos:
        pdf.cell(0, 7, "Nenhum movimento encontrado para os filtros selecionados.", 1, 1, 'C')
    for m in movimentos:
        conta_nome = contas[m.conta_bancaria_id].banco if m.conta_bancaria_id in contas else ""
        pdf.cell(20, 7, clean_text(m.numero or ""), 1, 0, 'C')
        pdf.cell(26, 7, clean_text(_fmt_data(m.data)), 1, 0, 'C')
        pdf.cell(30, 7, clean_text(conta_nome), 1, 0, 'C')
        pdf.cell(42, 7, clean_text(m.descricao or ""), 1, 0, 'C')
        pdf.cell(30, 7, clean_text(m.destinatario or ""), 1, 0, 'C')
        pdf.cell(24, 7, clean_text(m.categoria or ""), 1, 0, 'C')
        pdf.cell(36, 7, clean_text(m.forma_pagamento or ""), 1, 0, 'C')
        pdf.cell(20, 7, clean_text(m.tipo), 1, 0, 'C')
        pdf.cell(49, 7, f"{float(m.valor or 0):,.0f}", 1, 1, 'C')

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

    linhas = []
    for cli in clientes:
        cob = registos.get(cli.id)
        linhas.append({
            "nome": cli.nome,
            "email": cli.email or "",
            "empresa": cli.empresa or "",
            "pago": bool(cob.pago) if cob else False,
            "valor": float(cob.valor or 0) if cob else 0.0,
            "data_pagamento": cob.data_pagamento if cob else None,
            "observacao": cob.observacao if cob else "",
        })

    pagantes = sum(1 for l in linhas if l["pago"])
    total_cobrado = sum(l["valor"] for l in linhas)
    total_pago = sum(l["valor"] for l in linhas if l["pago"])

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
    pdf.cell(0, 7, f"Pagantes: {pagantes}   |   Não pagantes: {len(linhas) - pagantes}", 0, 1)
    pdf.cell(0, 7, f"Total a cobrar: Kz {total_cobrado:,.2f}   |   Total recebido: Kz {total_pago:,.2f}", 0, 1)
    pdf.ln(4)

    pdf.set_font('Times', 'B', 8)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(55, 7, "Cliente", 1, 0, 'C', True)
    pdf.cell(50, 7, "Email", 1, 0, 'C', True)
    pdf.cell(40, 7, "Empresa", 1, 0, 'C', True)
    pdf.cell(15, 7, "Pago?", 1, 0, 'C', True)
    pdf.cell(30, 7, "Valor", 1, 0, 'C', True)
    pdf.cell(27, 7, "Data pago", 1, 0, 'C', True)
    pdf.cell(45, 7, "Observações", 1, 1, 'C', True)

    pdf.set_font('Times', '', 8)
    for l in linhas:
        pdf.cell(55, 7, clean_text(l["nome"]), 1, 0, 'L')
        pdf.cell(50, 7, clean_text(l.get("email") or ""), 1, 0, 'L')
        pdf.cell(40, 7, clean_text(l["empresa"]), 1, 0, 'L')
        pdf.cell(15, 7, "Sim" if l["pago"] else "Não", 1, 0, 'C')
        pdf.cell(30, 7, f"{l['valor']:,.0f}", 1, 0, 'R')
        pdf.cell(27, 7, clean_text(_fmt_data(l["data_pagamento"])), 1, 0, 'C')
        pdf.cell(45, 7, clean_text(l["observacao"]), 1, 1, 'L')

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
    mw = max(12, min(24, int((pdf.w - 20 - 95) / max(nm, 1))))
    pdf.set_font('Times', 'B', 7)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(55, 7, "Cliente", 1, 0, 'C', True)
    pdf.cell(40, 7, "Empresa", 1, 0, 'C', True)
    for m, a in meses:
        pdf.cell(mw, 7, f"{m:02d}/{a}", 1, 0, 'C', True)
    pdf.cell(mw, 7, "Total", 1, 1, 'C', True)

    pdf.set_font('Times', '', 7)
    for cli in clientes:
        regs = {(c.mes, c.ano): c for c in por_cliente.get(cli.id, [])}
        nome = (cli.nome or "").strip()
        empresa = (cli.empresa or "").strip()
        total = sum(float(regs[k].valor or 0) for k in regs if regs[k].pago)
        if len(nome) * 1.9 > 52:
            nome = nome[:int(52 / 1.9)] + "..."
        if len(empresa) * 1.9 > 37:
            empresa = empresa[:int(37 / 1.9)] + "..."
        pdf.cell(55, 7, clean_text(nome), 1, 0, 'L')
        pdf.cell(40, 7, clean_text(empresa), 1, 0, 'L')
        for m, a in meses:
            cob = regs.get((m, a))
            if cob and cob.pago:
                texto = "Sim"
            elif cob:
                texto = "Não"
            else:
                texto = ""
            pdf.cell(mw, 7, clean_text(texto), 1, 0, 'C')
        pdf.cell(mw, 7, f"{total:,.0f}", 1, 1, 'C')

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