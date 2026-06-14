from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import database, models
from fpdf import FPDF
import io
import unicodedata
from datetime import datetime

router = APIRouter(tags=["relatorios"])

class PDF(FPDF):
    def rounded_rect(self, x, y, w, h, r, style = ''):
        k = self.k
        hp = self.h
        if(style=='F'):
            op='f'
        elif(style=='FD' or style=='DF'):
            op='B'
        else:
            op='S'
        my_arc = 4/3 * (2**0.5 - 1) * r
        self._out('%.2F %.2F m' % ((x+r)*k,(hp-y)*k))
        xc = x+w-r
        yc = y+r
        self._out('%.2F %.2F l' % (xc*k,(hp-y)*k))
        self._arc(xc + r*my_arc, yc - r, xc + r, yc - r*my_arc, xc + r, yc)
        xc = x+w-r
        yc = y+h-r
        self._out('%.2F %.2F l' % ((x+w)*k,(hp-yc)*k))
        self._arc(xc + r, yc + r*my_arc, xc + r*my_arc, yc + r, xc, yc + r)
        xc = x+r
        yc = y+h-r
        self._out('%.2F %.2F l' % (xc*k,(hp-(y+h))*k))
        self._arc(xc - r*my_arc, yc + r, xc - r, yc + r*my_arc, xc - r, yc)
        xc = x+r
        yc = y+r
        self._out('%.2F %.2F l' % (x*k,(hp-yc)*k))
        self._arc(xc - r, yc - r*my_arc, xc - r*my_arc, yc - r, xc, yc - r)
        self._out(op)

    def _arc(self, x1, y1, x2, y2, x3, y3):
        h = self.h
        self._out('%.2F %.2F %.2F %.2F %.2F %.2F c ' % (x1*self.k, (h-y1)*self.k, 
            x2*self.k, (h-y2)*self.k, x3*self.k, (h-y3)*self.k))

    def header(self):
        if self.page_no() == 1:
            try:
                self.image('LogoCLACS.png', 10, 8, 45)
            except:
                pass
            self.set_font('times', 'B', 18)
            self.cell(0, 10, 'CLACS - SISTEMA DE SUPORTE', 0, 1, 'C')
            self.set_font('times', 'I', 12)
            self.cell(0, 7, 'Relatorio de Suporte Tecnico', 0, 1, 'C')
            self.set_draw_color(0, 0, 0)
            self.line(10, 35, 200, 35)
            self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('times', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Pagina {self.page_no()} de {{nb}}', 0, 0, 'C')


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
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('latin-1', errors='ignore').decode('latin-1')
    return text


@router.get("/intervencao/{id}/visualizar")
def gerar_pdf_intervencao(
    id: str,
    db: Session = Depends(database.get_db),
    tecnico: str = Query(default=""),
    data: str = Query(default=""),
    cliente: str = Query(default=""),       # ✅ novo
    data_cliente: str = Query(default="")   # ✅ novo
):
    print(f"--- REQUISICAO DE PDF RECEBIDA PARA ID: {id} ---")
    print(f"--- TECNICO: {tecnico} | DATA: {data} ---")
    print(f"--- CLIENTE: {cliente} | DATA CLIENTE: {data_cliente} ---")
    try:
        i = db.query(models.Intervencao).filter(models.Intervencao.id == id).first()
        if not i:
            raise HTTPException(status_code=404, detail="Intervencao nao encontrada")
        
        pdf = PDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        
        def draw_section_header(pdf, title):
            pdf.set_fill_color(200, 225, 255)
            curr_y = pdf.get_y()
            pdf.rect(10, curr_y, 190, 10, 'F')
            pdf.set_font('times', 'B', 12)
            pdf.cell(0, 10, clean_text(title), 0, 1, 'L')
            pdf.ln(2)

        # --- Dados da Intervencao ---
        draw_section_header(pdf, f"DADOS DA INTERVENCAO: {i.numero if i.numero else 'N/A'}")

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Titulo:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.titulo)), 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Status:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.status)), 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Prioridade:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.prioridade)), 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Data de Abertura:", 0)
        pdf.set_font('times', '', 10)
        data_formatada = i.data_criacao.strftime("%d/%m/%Y %H:%M") if i.data_criacao else "N/A"
        pdf.cell(0, 8, data_formatada, 0, 1)

        pdf.ln(5)

        # --- Cliente ---
        draw_section_header(pdf, "CLIENTE")

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Nome:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.nome if i.cliente else "N/A"), 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Empresa:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.empresa if i.cliente else "N/A"), 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Email:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.email if i.cliente else "N/A"), 0, 1)

        pdf.ln(5)

        # --- Tecnico ---
        draw_section_header(pdf, "TECNICO RESPONSAVEL")

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Nome:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(i.tecnico.nome if i.tecnico else "Nao atribuido"), 0, 1)

        pdf.ln(5)

        # --- Descricao do Problema ---
        draw_section_header(pdf, "DESCRICAO DO PROBLEMA")
        pdf.set_font('times', '', 10)
        pdf.multi_cell(0, 8, clean_text(str(i.descricao) if i.descricao else "Sem descricao do problema disponivel."))

        pdf.ln(5)

        # --- Descricao da Solucao ---
        draw_section_header(pdf, "DESCRICAO DA SOLUCAO")
        pdf.set_font('times', '', 10)

        if not i.registros_horas:
            pdf.multi_cell(0, 8, "Nenhuma tarefa registrada ate o momento.")
        else:
            for reg in i.registros_horas:
                data_reg = reg.data if reg.data else "N/A"
                nome_tec = clean_text(reg.tecnico.nome) if reg.tecnico else "N/A"
                descricao = clean_text(reg.descricao) if reg.descricao else ""
                texto_tarefa = f"- [{data_reg}] [{nome_tec}] {descricao}"
                pdf.multi_cell(0, 7, texto_tarefa)

        pdf.ln(10)

        # --- Resumo de Tempo ---
        draw_section_header(pdf, "RESUMO DE TEMPO")

        hora_inicio_str = "N/A"
        hora_fim_str = "N/A"

        if i.registros_horas:
          primeiro_reg = i.registros_horas[0]
          ultimo_reg = i.registros_horas[-1]

          hora_inicio_str = primeiro_reg.hora_inicio if primeiro_reg.hora_inicio else "N/A"
          hora_fim_str = ultimo_reg.hora_fim if ultimo_reg.hora_fim else "N/A"

        pdf.set_font('times', 'B', 10)
        pdf.cell(60, 10, "Hora de Inicio da intervencao:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 10, hora_inicio_str, 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(60, 10, "Hora de Termino da intervencao:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 10, hora_fim_str, 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(60, 10, "Total de Horas:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 10, f"{i.horas_gastas if i.horas_gastas else 0:.2f} horas", 0, 1)

        pdf.ln(5)

        # --- Assinaturas ---
        if pdf.get_y() > 210:
            pdf.add_page()

        pdf.ln(10)
        curr_y = pdf.get_y()

        pdf.set_draw_color(0, 0, 0)
        pdf.rect(10, curr_y, 190, 16)
        pdf.line(105, curr_y, 105, curr_y + 16)

        # Cabeçalho do bloco
        pdf.set_y(curr_y + 1)
        pdf.set_font('times', 'B', 8)
        pdf.cell(90, 4, 'ASSINATURA DO TECNICO', 0, 0, 'C')
        pdf.cell(10, 4, '', 0)
        pdf.cell(90, 4, 'ASSINATURA DO CLIENTE', 0, 1, 'C')

        # ✅ Nome do técnico lido da BD
        pdf.set_y(curr_y + 6)
        pdf.set_font('times', 'B', 9)
        nome_tec_assinatura = clean_text(i.nome_assinatura_tecnico or "")
        pdf.cell(90, 4, nome_tec_assinatura, 0, 0, 'C')
        pdf.cell(10, 4, '', 0)
        nome_cli_assinatura = clean_text(i.nome_assinatura_cliente or "")
        pdf.cell(90, 4, nome_cli_assinatura, 0, 1, 'C')

        # ✅ Data do técnico lida da BD
        pdf.set_y(curr_y + 11)
        pdf.set_font('times', 'I', 7)
        data_tec = clean_text(i.data_assinatura_tecnico or "")
        pdf.cell(90, 4, data_tec, 0, 0, 'C')
        pdf.cell(10, 4, '', 0)
        data_cli = clean_text(i.data_assinatura_cliente or "")
        pdf.cell(90, 4, data_cli, 0, 1, 'C')

        pdf.ln(10)

        pdf.set_x(10)
        pdf.set_font('times', 'B', 12)
        pdf.multi_cell(190, 6, "Caro Cliente faca sempre uma copia deste documento para atestar a veracidade dos factos, findo assistencia, o cliente dispoe de 2 dias uteis para eventuais reclamacoes.", 0, 'C')

        pdf.set_x(10)
        pdf.set_font('times', 'B', 12)
        pdf.multi_cell(190, 6, "Em caso de duvidas nao hesite em contactar-nos atraves dos seguintes terminais: Geral.clacstecnologia@gmail.com | 925 505 439 | 918 945 5", 0, 'C')

        pdf.ln(5)

        # --- Rodape ---
        pdf.set_y(-35)
        pdf.set_font('times', '', 7)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 4, "Endereco: Municipio de Luanda, Bairro: Cassenda, Rua: casa s/N", 0, 1, 'C')
        pdf.cell(0, 4, "NF: 541733079", 0, 1, 'C')
        pdf.cell(0, 4, "Tel. 92 505 439 / 918 94 78", 0, 1, 'C')

        pdf_bytes = pdf.output()
        pdf_stream = io.BytesIO(pdf_bytes)
        filename = f"intervencao_{i.id[:8]}.pdf"

        return StreamingResponse(
            pdf_stream,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )
    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno ao gerar PDF: {str(e)}")
    
@router.get("/intervencao/{id}/download")
def download_pdf_intervencao(
    id: str,
    db: Session = Depends(database.get_db),
    tecnico: str = Query(default=""),
    data: str = Query(default=""),
    cliente: str = Query(default=""),
    data_cliente: str = Query(default="")
):
    print(f"--- DOWNLOAD PDF ID: {id} ---")

    try:
        i = db.query(models.Intervencao).filter(models.Intervencao.id == id).first()

        if not i:
            raise HTTPException(status_code=404, detail="Intervencao nao encontrada")

        pdf = PDF()
        pdf.alias_nb_pages()
        pdf.add_page()

        def draw_section_header(pdf, title):
            pdf.set_fill_color(200, 225, 255)
            curr_y = pdf.get_y()
            pdf.rect(10, curr_y, 190, 10, 'F')
            pdf.set_font('times', 'B', 12)
            pdf.cell(0, 10, clean_text(title), 0, 1, 'L')
            pdf.ln(2)

        # --- Dados da Intervencao ---
        draw_section_header(pdf, f"DADOS DA INTERVENCAO: {i.numero if i.numero else 'N/A'}")

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Titulo:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.titulo)), 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Status:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.status)), 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Prioridade:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.prioridade)), 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Data de Abertura:", 0)
        pdf.set_font('times', '', 10)

        data_formatada = (
            i.data_criacao.strftime("%d/%m/%Y %H:%M")
            if i.data_criacao else "N/A"
        )

        pdf.cell(0, 8, data_formatada, 0, 1)

        pdf.ln(5)

        # --- Cliente ---
        draw_section_header(pdf, "CLIENTE")

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Nome:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.nome if i.cliente else "N/A"), 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Empresa:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.empresa if i.cliente else "N/A"), 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Email:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.email if i.cliente else "N/A"), 0, 1)

        pdf.ln(5)

        # --- Tecnico ---
        draw_section_header(pdf, "TECNICO RESPONSAVEL")

        pdf.set_font('times', 'B', 10)
        pdf.cell(40, 8, "Nome:", 0)
        pdf.set_font('times', '', 10)
        pdf.cell(0, 8, clean_text(i.tecnico.nome if i.tecnico else "Nao atribuido"), 0, 1)

        pdf.ln(5)

        # --- Descricao do Problema ---
        draw_section_header(pdf, "DESCRICAO DO PROBLEMA")

        pdf.set_font('times', '', 10)

        pdf.multi_cell(
            0,
            8,
            clean_text(
                str(i.descricao)
                if i.descricao
                else "Sem descricao do problema disponivel."
            )
        )

        pdf.ln(5)

        # --- Descricao da Solucao ---
        draw_section_header(pdf, "DESCRICAO DA SOLUCAO")

        pdf.set_font('times', '', 10)

        if not i.registros_horas:
            pdf.multi_cell(0, 8, "Nenhuma tarefa registrada ate o momento.")
        else:
            for reg in i.registros_horas:
                data_reg = reg.data if reg.data else "N/A"
                nome_tec = clean_text(reg.tecnico.nome) if reg.tecnico else "N/A"
                descricao = clean_text(reg.descricao) if reg.descricao else ""

                texto_tarefa = f"- [{data_reg}] [{nome_tec}] {descricao}"

                pdf.multi_cell(0, 7, texto_tarefa)

        pdf.ln(10)

        # --- Resumo de Tempo ---
        draw_section_header(pdf, "RESUMO DE TEMPO")

        hora_inicio_str = "N/A"
        hora_fim_str = "N/A"

        if i.registros_horas:
            primeiro_reg = i.registros_horas[0]
            ultimo_reg = i.registros_horas[-1]

            hora_inicio_str = (
                primeiro_reg.hora_inicio
                if primeiro_reg.hora_inicio else "N/A"
            )

            hora_fim_str = (
                ultimo_reg.hora_fim
                if ultimo_reg.hora_fim else "N/A"
            )

        pdf.set_font('times', 'B', 10)
        pdf.cell(60, 10, "Hora de Inicio da intervencao:", 0)

        pdf.set_font('times', '', 10)
        pdf.cell(0, 10, hora_inicio_str, 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(60, 10, "Hora de Termino da intervencao:", 0)

        pdf.set_font('times', '', 10)
        pdf.cell(0, 10, hora_fim_str, 0, 1)

        pdf.set_font('times', 'B', 10)
        pdf.cell(60, 10, "Total de Horas:", 0)

        pdf.set_font('times', '', 10)
        pdf.cell(
            0,
            10,
            f"{i.horas_gastas if i.horas_gastas else 0:.2f} horas",
            0,
            1
        )

        pdf.ln(5)

        # --- Assinaturas ---
        if pdf.get_y() > 210:
            pdf.add_page()

        # ✅ Se o técnico está a baixar agora, guarda na BD
        if tecnico and data:
            i.nome_assinatura_tecnico = tecnico
            i.data_assinatura_tecnico = data
            db.commit()

        if cliente and data_cliente:
            i.nome_assinatura_cliente = cliente
            i.data_assinatura_cliente = data_cliente
            db.commit()    

        pdf.ln(10)

        curr_y = pdf.get_y()

        pdf.set_draw_color(0, 0, 0)

        pdf.rect(10, curr_y, 190, 16)

        pdf.line(105, curr_y, 105, curr_y + 16)

        pdf.set_y(curr_y + 1)

        pdf.set_font('times', 'B', 8)

        pdf.cell(90, 4, 'ASSINATURA DO TECNICO', 0, 0, 'C')
        pdf.cell(10, 4, '', 0)
        pdf.cell(90, 4, 'ASSINATURA DO CLIENTE', 0, 1, 'C')

        pdf.set_y(curr_y + 6)

        pdf.set_font('times', 'B', 9)

        # ✅ Usa sempre o que está guardado na BD
        nome_tec_assinatura = clean_text(
            i.nome_assinatura_tecnico or (i.tecnico.nome if i.tecnico else "")
        )

        pdf.cell(90, 4, nome_tec_assinatura, 0, 0, 'C')

        pdf.cell(10, 4, '', 0)

        nome_cli_assinatura = clean_text(i.nome_assinatura_cliente or "")

        pdf.cell(90, 4, nome_cli_assinatura, 0, 1, 'C')

        pdf.set_y(curr_y + 11)

        pdf.set_font('times', 'I', 7)

        # ✅ Data do técnico vem sempre da BD — nunca muda
        data_tec = clean_text(i.data_assinatura_tecnico or "")
        data_cli = clean_text(i.data_assinatura_cliente or "")

        pdf.cell(90, 4, data_tec, 0, 0, 'C')

        pdf.cell(10, 4, '', 0)

        pdf.cell(90, 4, data_cli, 0, 1, 'C')

        pdf.ln(10)

        pdf.set_x(10)

        pdf.set_font('times', 'B', 10)

        pdf.multi_cell(
            190,
            6,
            "Caro Cliente faca sempre uma copia deste documento para atestar a veracidade dos factos, findo assistencia, o cliente dispoe de 2 dias uteis para eventuais reclamacoes.",
            0,
            'C'
        )

        pdf.set_x(10)

        pdf.set_font('times', 'B', 10)

        pdf.multi_cell(
            190,
            6,
            "Em caso de duvidas nao hesite em contactar-nos atraves dos seguintes terminais: Geral.clacstecnologia@gmail.com | 925 505 439 | 918 945 5",
            0,
            'C'
        )

        pdf.ln(5)

        # --- Rodape ---
        pdf.set_y(-35)

        pdf.set_font('times', '', 7)

        pdf.set_text_color(128, 128, 128)

        pdf.cell(
            0,
            4,
            "Endereco: Municipio de Luanda, Bairro: Cassenda, Rua: casa s/N",
            0,
            1,
            'C'
        )

        pdf.cell(0, 4, "NF: 541733079", 0, 1, 'C')

        pdf.cell(0, 4, "Tel. 92 505 439 / 918 94 78", 0, 1, 'C')

        pdf_bytes = bytes(pdf.output(dest='S'))

        pdf_stream = io.BytesIO(pdf_bytes)

        filename = f"intervencao_{i.id[:8]}.pdf"

        return StreamingResponse(
            pdf_stream,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        print(f"ERRO DOWNLOAD PDF: {e}")

        raise HTTPException(status_code=500, detail=str(e))