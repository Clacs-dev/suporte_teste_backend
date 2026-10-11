from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import database, models
from fpdf import FPDF
import io
import unicodedata
from datetime import datetime

router = APIRouter(tags=["relatorios"])

class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            try:
                self.image('LogoCLACS.png', 10, 8, 45)
            except:
                pass
            self.set_font('times', 'B', 18)
            self.cell(0, 10, 'CLACS - SISTEMA DE SUPORTE', 0, 1, 'C')
            self.set_font('times', 'I', 12)
            self.cell(0, 7, 'Relatorio Geral do Sistema', 0, 1, 'C')
            self.set_draw_color(0, 0, 0)
            self.line(10, 35, 200, 35)
            self.ln(10)

    def footer(self):
        self.set_y(-35)
        self.set_font('times', '', 7)
        self.set_text_color(128, 128, 128)
        self.cell(0, 4, "Endereco: Municipio de Luanda, Bairro: Cassenda, Rua: casa s/N", 0, 1, 'C')
        self.cell(0, 4, "NF: 541733079", 0, 1, 'C')
        self.cell(0, 4, "Tel. 92 505 439 / 918 94 78", 0, 1, 'C')
        self.set_text_color(0, 0, 0)
        self.set_font('times', 'I', 8)
        self.cell(0, 4, f'Pagina {self.page_no()} de {{nb}}', 0, 0, 'C')


def clean_text(text):
    if not text:
        return ""
    special = {
        '\u2014': '-', '\u2013': '-', '\u201c': '"', '\u201d': '"',
        '\u2018': "'", '\u2019': "'", '\u2026': '...', '\u2022': '-',
        '\u00a0': ' ', '\u20ac': 'EUR', '\u00a3': 'GBP',
    }
    for char, replacement in special.items():
        text = text.replace(char, replacement)
    text = unicodedata.normalize('NFKD', str(text))
    text = text.encode('latin-1', errors='ignore').decode('latin-1')
    return text


def fmt_moeda(valor, decimais=2):
    """Formata um número no padrão português/angolano: 1.234.567,89"""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        n = 0.0
    s = f"{n:,.{decimais}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def draw_section_header(pdf, title):
    pdf.set_fill_color(30, 90, 180)
    pdf.set_text_color(255, 255, 255)
    curr_y = pdf.get_y()
    pdf.rect(10, curr_y, 190, 10, 'F')
    pdf.set_font('times', 'B', 12)
    pdf.set_xy(12, curr_y)
    pdf.cell(186, 10, clean_text(title), 0, 1, 'L')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def row(pdf, label, value):
    pdf.set_font('times', 'B', 10)
    pdf.cell(70, 8, clean_text(label), 0)
    pdf.set_font('times', '', 10)
    pdf.set_xy(80, pdf.get_y())
    pdf.cell(0, 8, clean_text(str(value)), 0, 1)


@router.get("/geral")
def gerar_relatorio_geral(db: Session = Depends(database.get_db)):
    hoje = datetime.now()

    # Dados
    clientes = db.query(models.Cliente).all()
    contratos = db.query(models.Contrato).all()
    intervencoes = db.query(models.Intervencao).all()
    tecnicos = db.query(models.Tecnico).all()
    registros = db.query(models.RegistroHoras).all()

    total_horas = sum(float(r.horas or 0) for r in registros)
    faturamento = sum(float(c.valor_mensal or 0) for c in contratos if c.status == "Ativo")

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Data do relatório
    pdf.set_font('times', 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f'Gerado em: {hoje.strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    # ── RESUMO GERAL ─────────────────────────────────────────────────────────
    draw_section_header(pdf, "RESUMO GERAL")
    row(pdf, "Total de Clientes:", len(clientes))
    row(pdf, "Clientes Activos:", sum(1 for c in clientes if c.status == "Ativo"))
    row(pdf, "Total de Contratos:", len(contratos))
    row(pdf, "Contratos Activos:", sum(1 for c in contratos if c.status == "Ativo"))
    row(pdf, "Faturamento Mensal:", f"Kz {fmt_moeda(faturamento)}")
    row(pdf, "Total de Tecnicos:", len(tecnicos))
    row(pdf, "Total de Intervencoes:", len(intervencoes))
    row(pdf, "Total de Horas Registadas:", f"{total_horas:.2f}h")
    pdf.ln(4)

    # ── INTERVENÇÕES POR STATUS ───────────────────────────────────────────────
    draw_section_header(pdf, "INTERVENCOES POR STATUS")
    status_list = ["Aberto", "Em Andamento", "Aguardando Cliente", "Resolvido", "Concluido", "Fechado"]
    for s in status_list:
        count = sum(1 for i in intervencoes if i.status == s)
        row(pdf, f"{s}:", count)
    pdf.ln(4)

    # ── INTERVENÇÕES POR PRIORIDADE ───────────────────────────────────────────
    draw_section_header(pdf, "INTERVENCOES POR PRIORIDADE")
    for p in ["Baixa", "Media", "Alta"]:
        count = sum(1 for i in intervencoes if i.prioridade == p)
        row(pdf, f"{p}:", count)
    pdf.ln(4)

    # ── DESEMPENHO POR TÉCNICO ────────────────────────────────────────────────
    draw_section_header(pdf, "DESEMPENHO POR TECNICO")
    pdf.set_font('times', 'B', 9)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(70, 8, "Nome", 1, 0, 'L', True)
    pdf.cell(40, 8, "Intervencoes", 1, 0, 'C', True)
    pdf.cell(40, 8, "Resolvidas", 1, 0, 'C', True)
    pdf.cell(40, 8, "Horas", 1, 1, 'C', True)

    for t in tecnicos:
        intervs = [i for i in intervencoes if i.tecnico_id == t.id]
        resolvidas = sum(1 for i in intervs if i.status in ["Resolvido", "Concluido"])
        horas = sum(float(r.horas or 0) for i in intervs for r in i.registros_horas)
        pdf.set_font('times', '', 9)
        pdf.cell(70, 7, clean_text(t.nome or "N/A"), 1, 0, 'L')
        pdf.cell(40, 7, str(len(intervs)), 1, 0, 'C')
        pdf.cell(40, 7, str(resolvidas), 1, 0, 'C')
        pdf.cell(40, 7, f"{horas:.2f}h", 1, 1, 'C')
    pdf.ln(4)

    # ── TOP CLIENTES ──────────────────────────────────────────────────────────
    draw_section_header(pdf, "TOP CLIENTES POR INTERVENCOES")
    clientes_sorted = sorted(
        clientes,
        key=lambda c: sum(1 for i in intervencoes if i.cliente_id == c.id),
        reverse=True
    )[:5]

    pdf.set_font('times', 'B', 9)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(80, 8, "Cliente", 1, 0, 'L', True)
    pdf.cell(55, 8, "Email", 1, 0, 'L', True)
    pdf.cell(55, 8, "Intervencoes", 1, 1, 'C', True)

    for c in clientes_sorted:
        total = sum(1 for i in intervencoes if i.cliente_id == c.id)
        pdf.set_font('times', '', 9)
        pdf.cell(80, 7, clean_text(c.nome or "N/A"), 1, 0, 'L')
        pdf.cell(55, 7, clean_text(c.email or "N/A"), 1, 0, 'L')
        pdf.cell(55, 7, str(total), 1, 1, 'C')
    pdf.ln(4)

    # OUTPUT
    pdf_bytes = bytes(pdf.output())
    pdf_stream = io.BytesIO(pdf_bytes)
    filename = f"relatorio_geral_{hoje.strftime('%Y%m%d_%H%M')}.pdf"

    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
