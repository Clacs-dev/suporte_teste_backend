from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
import database, models
from fpdf import FPDF
import io
import unicodedata
from datetime import datetime


def texto(t):
    return str(t) if t is not None else ""

def _data_do_registo(r):
    from datetime import datetime
    val = r.data
    if not val:
        return None
    if isinstance(val, str):
        try:
            return datetime.strptime(val[:10], "%Y-%m-%d")
        except Exception:
            return None
    return val
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
            self.cell(0, 7, 'Relatório Mensal do Cliente', 0, 1, 'C')
            self.set_draw_color(0, 0, 0)
            self.line(10, 35, 200, 35)
            self.ln(10)

    def footer(self):
        pass


def format_date_str(date_val, fallback="Não definido"):
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
    pdf.set_fill_color(30, 90, 180)
    pdf.set_text_color(255, 255, 255)
    curr_y = pdf.get_y()
    pdf.rect(10, curr_y, 190, 10, 'F')
    pdf.set_font('times', 'B', 12)
    pdf.set_xy(12, curr_y)
    pdf.cell(186, 10, clean_text(title), 0, 1, 'L')
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
MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

@router.get("/contrato/{contrato_id}/cliente")
def gerar_relatorio_mensal_cliente(contrato_id: str, data_inicio: str = None, data_fim: str = None,
                                   db: Session = Depends(database.get_db)):
    from datetime import datetime
    hoje = datetime.now()
    di = datetime.strptime(data_inicio, "%Y-%m-%d") if data_inicio else None
    df = datetime.strptime(data_fim, "%Y-%m-%d") if data_fim else None

    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato nao encontrado")

    cliente = contrato.cliente
    empresa_nome = (cliente.empresa or cliente.nome) if cliente else "Cliente"

    # Registos de horas do mês, do cliente deste contrato
    registros = (
        db.query(models.RegistroHoras)
        .join(models.Intervencao)
        .filter(models.Intervencao.cliente_id == contrato.cliente_id)
        .all()
    )
    def _no_intervalo(r):
        d = _data_do_registo(r)
        if not d:
            return False
        if di and d < di:
            return False
        if df and d > df:
            return False
        return True
    registros = [r for r in registros if _no_intervalo(r)]

    registros.sort(key=lambda r: _data_do_registo(r))

    # Intervenções pendentes do mês (não resolvidas nem concluídas)
    intervencoes_cliente = (
        db.query(models.Intervencao)
        .filter(models.Intervencao.cliente_id == contrato.cliente_id)
        .all()
    )
    pendentes = [
        i for i in intervencoes_cliente
        if i.status not in ("Resolvido", "Concluído")
    ]

    total_min = sum(int(round(float(r.horas or 0) * 60)) for r in registros)
    horas_tot, min_tot = divmod(total_min, 60)
    n_interv = len(registros)

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_margins(left=20, top=15, right=20)
    pdf.alias_nb_pages()
    pdf.add_page()

    import os
    _fonts = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
    pdf.add_font("Times", "", os.path.join(_fonts, "times.ttf"))
    pdf.add_font("Times", "B", os.path.join(_fonts, "timesbd.ttf"))
    pdf.add_font("Times", "I", os.path.join(_fonts, "timesi.ttf"))

    # Título
    pdf.set_font('Times', 'B', 12)
    pdf.cell(0, 10, texto(f"Relatório Mensal - {empresa_nome}"), 0, 1, 'L')
    pdf.ln(4)

    def _fmt(d):
        return d.strftime("%d/%m/%Y") if d else "..."
    periodo_txt = f"o período de {_fmt(di)} a {_fmt(df)}" if (di or df) else "o período abrangido"

    # Introdução
    pdf.set_font('Times', 'B', 12)
    pdf.cell(0, 8, "Introdução", 0, 1, 'C')
    pdf.set_font('Times', '', 12)
    intro = (f"Dentro das obrigações da Clacs Tecnologia no suporte e assistência técnica "
             f"fornecida a {empresa_nome}, foram executadas durante {periodo_txt} "
             f"inúmeras intervenções a nível de correção e prevenção, tal como consultoria, "
             f"suporte e acompanhamento aos usuários dentro das ocorrências.")
    pdf.multi_cell(0, 7, texto(intro))
    pdf.ln(4)

# Números e horas
    EXTENSO = ["zero","uma","duas","tres","quatro","cinco","seis","sete","oito","nove","dez",
               "onze","doze","treze","catorze","quinze","dezasseis","dezassete","dezoito","dezanove","vinte"]

    presenciais = [r for r in registros if r.intervencao and r.intervencao.modo_resolucao != "Remoto"]
    remotas     = [r for r in registros if r.intervencao and r.intervencao.modo_resolucao == "Remoto"]

    n_pres = len(presenciais)
    n_rem  = len(remotas)

    min_pres = sum(int(round(float(r.horas or 0) * 60)) for r in presenciais)
    h_pres, m_pres = divmod(min_pres, 60)
    min_rem = sum(int(round(float(r.horas or 0) * 60)) for r in remotas)
    h_rem, m_rem = divmod(min_rem, 60)
    pres_ext = EXTENSO[n_pres] if n_pres < len(EXTENSO) else str(n_pres)
    palavra_int = "intervenção presencial" if n_pres == 1 else "intervenções presenciais"
    frase_remota = f" e ({n_rem}) remotamente" if n_rem > 0 else ""
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Times', 'B', 12)
    pdf.cell(0, 8, "Números e horas de intervenção efectuadas", 0, 1, 'C')
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Times', '', 12)
    resumo = (f"Foram realizados um total de {pres_ext} ({n_pres}) {palavra_int}"
              f"{frase_remota} ao longo do mês, tendo contabilizado {h_pres} horas e {m_pres} minutos "
              f"de assistências presenciais e {h_rem} horas e {m_rem} minutos de assistências remotas.")
    pdf.multi_cell(0, 7, texto(resumo), align='J', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Principais intervenções
    pdf.set_font('Times', 'B', 12)
    pdf.cell(0, 8, "Principais Intervenções realizadas", 0, 1, 'C')
    pdf.ln(2)

    for r in registros:
        d = _data_do_registo(r)
        hi = r.hora_inicio or "--:--"
        hf = r.hora_fim or "--:--"
        tecnico_nome = r.tecnico.nome if r.tecnico else "Não definido"
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Times', 'B', 12)
        pdf.set_font('Times', 'B', 12)
        parte1 = "Tempo de trabalho: "
        pdf.set_font('Times', '', 12)
        parte2 = texto(f"{hi} as {hf}   ")
        pdf.set_font('Times', 'B', 12)
        parte3 = "Consultor: "
        pdf.set_font('Times', '', 12)
        parte4 = texto(f"{tecnico_nome}   ")
        pdf.set_font('Times', 'B', 12)
        parte5 = "Dia "
        pdf.set_font('Times', 'I', 12)
        parte6 = texto(f"{d.day:02d} de {MESES_PT[d.month]} de {d.year}:")

        solic = r.intervencao.solicitante if r.intervencao else None
        partes = [(parte1, 'B'), (parte2, ''), (parte3, 'B'), (parte4, '')]
        if solic:
            partes.append(("Solicitante: ", 'B'))
            partes.append((texto(f"{solic}   "), ''))
        partes.append((parte5, 'B'))
        partes.append((parte6, 'I'))
        total_w = 0
        for txt, estilo in partes:
            pdf.set_font('Times', estilo, 12)
            total_w += pdf.get_string_width(txt)

        pdf.set_xy((pdf.w - total_w) / 2, pdf.get_y())
        for txt, estilo in partes:
            pdf.set_font('Times', estilo, 12)
            pdf.write(7, txt)
        pdf.ln(10)
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Times', '', 12)
        pdf.multi_cell(0, 7, texto(r.descricao or "Sem descricão."), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # Solicitações e Pendentes
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Times', 'B', 12)
    pdf.cell(0, 8, texto("Solicitações e Pendentes"), 0, 1, 'L')
    pdf.set_x(pdf.l_margin)
    pdf.set_font('Times', '', 12)
    if pendentes:
        for i in pendentes:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 7, texto(f'- Intervenção "{i.titulo}" por fechar'), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 7, "- Nenhum.", 0, 1, 'L')
    pdf.ln(6)

    # Local e data
    pdf.set_font('Times', '', 12)
    pdf.cell(0, 7, texto(f"Luanda, aos {hoje.day:02d} de {MESES_PT[hoje.month]} de {hoje.year}"), 0, 1, 'C')
    pdf.ln(8)

    # Validado por
    pdf.set_font('Times', 'B', 12)
    pdf.cell(0, 7, "Validado por:", 0, 1, 'L')
    pdf.ln(2)
    pdf.cell(0, 7, "Dinis Jombe", 0, 1, 'C')
    pdf.ln(10)
    pdf.cell(0, 7, "Director Geral", 0, 1, 'C')

    import os
    assinatura_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assinatura.png")
    if os.path.exists(assinatura_path):
        pdf.image(assinatura_path, x=(210 - 50) / 2, w=50)

    pdf_bytes = bytes(pdf.output())
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="relatorio_{empresa_nome}.pdf"'})
