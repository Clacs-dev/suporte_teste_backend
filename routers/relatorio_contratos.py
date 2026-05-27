from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import database, models
from fpdf import FPDF
import io
import unicodedata
from datetime import datetime

router = APIRouter(tags=["relatorios"])


# ─── PDF base ────────────────────────────────────────────────────────────────
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
            self.cell(0, 7, 'Relatorio Mensal do Cliente', 0, 1, 'C')
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


def format_date_str(date_val, fallback="N/A"):
    """Formata datas de forma segura, quer sejam string ou datetime."""
    if not date_val:
        return fallback
    if isinstance(date_val, str):
        try:
            return datetime.fromisoformat(date_val.replace('Z', '+00:00')).strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return date_val  # retorna a string tal qual se nao conseguir parsear
    try:
        return date_val.strftime("%d/%m/%Y")
    except (AttributeError, TypeError):
        return str(date_val)


def clean_text(text):
    if not text:
        return ""
    special = {
        '\u2014': '-', '\u2013': '-', '\u2012': '-', '\u2015': '-',
        '\u2011': '-', '\u201c': '"', '\u201d': '"', '\u2018': "'",
        '\u2019': "'", '\u201e': '"', '\u00ab': '"', '\u00bb': '"',
        '\u2026': '...', '\u2022': '-', '\u00b7': '.', '\u00a9': '(c)',
        '\u00ae': '(R)', '\u2122': '(TM)', '\u00a0': ' ', '\u00b0': 'o',
        '\u20ac': 'EUR', '\u00a3': 'GBP', '\u00d7': 'x', '\u00f7': '/',
        '\u00ba': 'o', '\u00aa': 'a',
    }
    for char, replacement in special.items():
        text = text.replace(char, replacement)
    text = unicodedata.normalize('NFKD', str(text))
    text = text.encode('latin-1', errors='ignore').decode('latin-1')
    return text


def draw_section_header(pdf: PDF, title: str):
    """Barra azul com título branco — secção principal."""
    pdf.set_fill_color(30, 90, 180)
    pdf.set_text_color(255, 255, 255)
    curr_y = pdf.get_y()
    pdf.rect(10, curr_y, 190, 10, 'F')
    pdf.set_font('times', 'B', 12)
    pdf.set_x(12)
    pdf.cell(0, 10, clean_text(title), 0, 1, 'L')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def draw_progress_bar(pdf: PDF, percent: float):
    """Barra de progresso colorida conforme o percentual."""
    bar_x, bar_y, bar_w, bar_h = 10, pdf.get_y(), 190, 8
    # fundo cinzento
    pdf.set_fill_color(220, 220, 220)
    pdf.rect(bar_x, bar_y, bar_w, bar_h, 'F')
    # preenchimento
    fill_w = min(bar_w * percent / 100, bar_w)
    if percent > 90:
        pdf.set_fill_color(200, 50, 50)
    elif percent > 70:
        pdf.set_fill_color(230, 160, 30)
    else:
        pdf.set_fill_color(40, 160, 80)
    if fill_w > 0:
        pdf.rect(bar_x, bar_y, fill_w, bar_h, 'F')
    # contorno
    pdf.set_draw_color(180, 180, 180)
    pdf.rect(bar_x, bar_y, bar_w, bar_h)
    pdf.set_draw_color(0, 0, 0)
    # label
    pdf.set_y(bar_y + bar_h + 1)
    pdf.set_font('times', 'I', 8)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5, f'{percent:.1f}% utilizado', 0, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


# ─── Endpoint ────────────────────────────────────────────────────────────────
@router.get("/contrato/{contrato_id}/cliente")
def gerar_relatorio_mensal_cliente(contrato_id: str, db: Session = Depends(database.get_db)):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato nao encontrado")

    # intervenções ligadas ao cliente deste contrato
    intervencoes = (
        db.query(models.Intervencao)
        .filter(models.Intervencao.cliente_id == contrato.cliente_id)
        .order_by(models.Intervencao.data_criacao)
        .all()
    )

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # ── SECÇÃO: CONTRATO ─────────────────────────────────────────────────────
    draw_section_header(pdf, "CONTRATO")

    horas_contratadas = float(contrato.horas_contratadas or 0)

    # Calcular horas_usadas dinamicamente (igual ao endpoint /contratos)
    horas_usadas = db.query(func.sum(models.RegistroHoras.horas)).\
        select_from(models.RegistroHoras).\
        join(models.Intervencao).\
        filter(
            (models.Intervencao.contrato_id == contrato.id) |
            ((models.Intervencao.contrato_id == None) & (models.Intervencao.cliente_id == contrato.cliente_id))
        ).\
        scalar() or 0.0
    horas_usadas = float(horas_usadas)

    horas_restantes   = horas_contratadas - horas_usadas
    percent           = (horas_usadas / horas_contratadas * 100) if horas_contratadas > 0 else 0
    valor_mensal      = float(contrato.valor_mensal or 0)

    def row(pdf, label, value):
        pdf.set_font('times', 'B', 10)
        pdf.cell(60, 8, clean_text(label), 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(value), 0, 1)

    row(pdf, "Tipo:",           contrato.tipo or "N/A")
    row(pdf, "Status:",         contrato.status or "N/A")
    row(pdf, "Data de Inicio:", format_date_str(contrato.data_inicio, "N/A"))
    row(pdf, "Data de Fim:",    format_date_str(contrato.data_fim, "Indeterminado"))
    row(pdf, "Valor Mensal:",   f"Kz {valor_mensal:,.2f}")
    row(pdf, "Horas Contratadas:", f"{horas_contratadas:.2f}h")
    row(pdf, "Horas Usadas:",      f"{horas_usadas:.2f}h")
    row(pdf, "Horas Disponiveis:", f"{horas_restantes:.2f}h")

    pdf.ln(3)
    pdf.set_font('times', 'B', 10)
    pdf.cell(0, 6, "Progresso do Contrato:", 0, 1)
    pdf.ln(1)
    draw_progress_bar(pdf, percent)

    pdf.ln(4)

    # ── SECÇÃO: INTERVENÇÕES ─────────────────────────────────────────────────
    draw_section_header(pdf, "INTERVENCOES")

    if not intervencoes:
        pdf.set_font('times', 'I', 10)
        pdf.cell(0, 8, "Nenhuma intervencao registrada.", 0, 1)
    else:
        for idx, i in enumerate(intervencoes, start=1):
            # garante espaço suficiente para pelo menos o cabeçalho do item
            if pdf.get_y() > 240:
                pdf.add_page()

            # cabeçalho do item (fundo azul claro)
            pdf.set_fill_color(200, 220, 255)
            pdf.set_text_color(0, 0, 0)
            item_y = pdf.get_y()
            pdf.rect(10, item_y, 190, 9, 'F')
            pdf.set_font('times', 'B', 10)
            pdf.set_x(12)
            num = clean_text(i.numero or f"#{idx}")
            titulo = clean_text(i.titulo or "Sem titulo")
            pdf.cell(0, 9, f"{num}  |  {titulo}", 0, 1)
            pdf.ln(1)

            # campos
            def irow(label, value):
                pdf.set_font('times', 'B', 9)
                pdf.cell(55, 7, clean_text(label), 0)
                pdf.set_font('times', '', 9)
                pdf.cell(0, 7, clean_text(value), 0, 1)

            irow("Status:",     i.status or "N/A")
            irow("Prioridade:", i.prioridade or "N/A")
            irow("Data:",       format_date_str(i.data_criacao, "N/A"))

            # hora início / fim (primeiro e último registo)
            hora_inicio = "N/A"
            hora_fim    = "N/A"
            if i.registros_horas:
                primeiro = i.registros_horas[0]
                ultimo   = i.registros_horas[-1]
                hora_inicio = primeiro.hora_inicio if primeiro.hora_inicio else "N/A"
                hora_fim    = ultimo.hora_fim if ultimo.hora_fim else "N/A"

            irow("Hora de Inicio:", hora_inicio)
            irow("Hora de Fim:",    hora_fim)
            irow("Horas Gastas:",   f"{float(i.horas_gastas or 0):.2f}h")

            pdf.ln(2)

            # descrição do problema
            pdf.set_font('times', 'B', 9)
            pdf.cell(0, 7, "Descricao do Problema:", 0, 1)
            pdf.set_font('times', '', 9)
            pdf.multi_cell(0, 6, clean_text(i.descricao or "Sem descricao."))
            pdf.ln(1)

            # descrição da solução (registros de horas)
            pdf.set_font('times', 'B', 9)
            pdf.cell(0, 7, "Descricao da Solucao:", 0, 1)
            pdf.set_font('times', '', 9)
            if i.registros_horas:
                for reg in i.registros_horas:
                    desc = clean_text(reg.descricao or "Sem descricao da solucao.")
                    tec  = clean_text(reg.tecnico.nome if reg.tecnico else "N/A")
                    pdf.multi_cell(0, 6, f"[{tec}] {desc}")
            else:
                pdf.multi_cell(0, 6, "Nenhuma solucao registrada.")

            # separador entre intervenções
            pdf.ln(2)
            pdf.set_draw_color(180, 180, 180)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.set_draw_color(0, 0, 0)
            pdf.ln(4)

    # ── OUTPUT ───────────────────────────────────────────────────────────────
    pdf_output = pdf.output(dest='S')

    if isinstance(pdf_output, str):
       pdf_bytes = pdf_output.encode('latin-1')
    else:
       pdf_bytes = bytes(pdf_output)

    pdf_stream = io.BytesIO(pdf_bytes)
    
    
    cliente_nome = clean_text(contrato.cliente.nome if contrato.cliente else "cliente")
    filename = f"relatorio_mensal_{cliente_nome.replace(' ', '_')}.pdf"

    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
