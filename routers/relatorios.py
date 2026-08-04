from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import database, models
from fpdf import FPDF
import io
import requests
import tempfile, os
import unicodedata
from datetime import datetime

router = APIRouter(tags=["relatorios"])

class PDF(FPDF):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import os
        _fonts = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        self.add_font("Times", "", os.path.join(_fonts, "times.ttf"))
        self.add_font("Times", "B", os.path.join(_fonts, "timesbd.ttf"))
        self.add_font("Times", "I", os.path.join(_fonts, "timesi.ttf"))

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
            self.set_font('Times', 'B', 18)
            self.cell(0, 10, 'CLACS - SISTEMA DE SUPORTE', 0, 1, 'C')
            self.set_font('Times', 'I', 12)
            self.cell(0, 7, 'Relatório de Suporte Técnico', 0, 1, 'C')
            self.set_draw_color(0, 0, 0)
            self.line(10, 35, 200, 35)
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


def clean_text(text):
    if text is None:
        return ""
    text = str(text)
    subs = {
        "\u2013": "-", "\u2014": "-", "\u2012": "-", "\u2015": "-", "\u2011": "-",
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"',
        "\u2026": "...", "\u2022": "-", "\u00b7": ".",
        "\u00ab": '"', "\u00bb": '"', "\u00a0": " ",
    }
    for k, v in subs.items():
        text = text.replace(k, v)
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
        pdf.set_auto_page_break(auto=True, margin=35)
        pdf.alias_nb_pages()
        pdf.add_page()

        _fonts = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        pdf.add_font("Times", "", os.path.join(_fonts, "times.ttf"))
        pdf.add_font("Times", "B", os.path.join(_fonts, "timesbd.ttf"))
        pdf.add_font("Times", "I", os.path.join(_fonts, "timesi.ttf"))
        
        def draw_section_header(pdf, title):
             # se não couber o cabeçalho + pelo menos uma linha, salta de página
            if pdf.get_y() + 20 > pdf.h - 35:
                pdf.add_page()
            pdf.set_fill_color(200, 225, 255)
            curr_y = pdf.get_y()
            pdf.rect(10, curr_y, 190, 10, 'F')
            pdf.set_font('Times', 'B', 10)
            pdf.cell(0, 10, clean_text(title), 0, 1, 'L')
            pdf.ln(2)

        # --- Dados da Intervencao ---
        draw_section_header(pdf, f"DADOS DA INTERVENÇÃO: {i.numero if i.numero else 'N/A'}")

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Titulo:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.titulo)), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Status:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.status)), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Prioridade:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.prioridade)), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Data de Abertura:", 0)
        pdf.set_font('Times', '', 10)
        data_formatada = i.data_criacao.strftime("%d/%m/%Y %H:%M") if i.data_criacao else "Não definido"
        pdf.cell(0, 8, data_formatada, 0, 1)

        pdf.ln(5)

        # --- Cliente ---
        draw_section_header(pdf, "CLIENTE")

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Nome:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.nome if i.cliente else "Não definido"), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Empresa:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.empresa if i.cliente else "Não definido"), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Email:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.email if i.cliente else "Não definido"), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Telefone:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.telefone if i.cliente and i.cliente.telefone else "Não definido"), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Solicitante:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.solicitante or "Não definido"), 0, 1)

        pdf.ln(5)

        # --- Tecnico ---
        draw_section_header(pdf, "TÉCNICO RESPONSÁVEL")

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Nome:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.tecnico.nome if i.tecnico else "Não atribuido"), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Modo de Resolução:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.modo_resolucao or "Não definido"), 0, 1)

        pdf.ln(5)

        # --- Imagens Anexadas ---
        imagens = [a for a in i.anexos if a.tipo and a.tipo.startswith("image")]
        if imagens:
            draw_section_header(pdf, "IMAGENS ANEXADAS")

            BOX_W, BOX_H = 85, 60      # caixa de cada imagem (mm)
            COLS = [12, 108]           # x da coluna esquerda e direita
            col = 0
            y = pdf.get_y() + 4

            for anexo in imagens:
                try:
                    r = requests.get(anexo.url, timeout=10)
                    if r.status_code != 200:
                        continue
                    ext = ".png" if "png" in anexo.url.lower() else ".jpg"
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                    tmp.write(r.content)
                    tmp.close()

                    # nova página se não couber
                    if y + BOX_H > 265:
                        pdf.add_page()
                        y = pdf.get_y()
                        col = 0

                    pdf.image(tmp.name, x=COLS[col], y=y,
                              w=BOX_W, h=BOX_H, keep_aspect_ratio=True)
                    os.unlink(tmp.name)

                    col += 1
                    if col > 1:            # completou a linha
                        col = 0
                        y += BOX_H + 5
                except Exception as e:
                    print(f"Erro ao inserir imagem no PDF: {e}")

            if col == 1:                   # sobrou uma imagem na linha
                y += BOX_H + 5
            pdf.set_y(y + 3)
            pdf.ln(2)

        # --- Descricao do Problema ---
        draw_section_header(pdf, "DESCRIÇÃO DO PROBLEMA")
        pdf.set_font('Times', '', 10)
        pdf.multi_cell(0, 8, clean_text(str(i.descricao) if i.descricao else "Sem descricao do problema disponivel."))

        pdf.ln(5)

        # --- Descricao da Solucao ---
        draw_section_header(pdf, "DESCRIÇÃO DA SOLUÇÃO")
        pdf.set_font('Times', '', 10)

        if not i.registros_horas:
            pdf.multi_cell(0, 8, "Nenhuma tarefa registrada até o momento.")
        else:
            for reg in i.registros_horas:
                data_reg = reg.data if reg.data else "Não definido"
                nome_tec = clean_text(reg.tecnico.nome) if reg.tecnico else "Não definido"
                descricao = clean_text(reg.descricao) if reg.descricao else ""
                texto_tarefa = f"- [{data_reg}] [{nome_tec}] {descricao}"
                pdf.multi_cell(0, 7, texto_tarefa)

        pdf.ln(10)

        # --- Resumo de Tempo ---
        draw_section_header(pdf, "RESUMO DE TEMPO")

        hora_inicio_str = "Não definido"
        hora_fim_str = "Não definido"

        if i.registros_horas:
          primeiro_reg = i.registros_horas[0]
          ultimo_reg = i.registros_horas[-1]

          hora_inicio_str = primeiro_reg.hora_inicio if primeiro_reg.hora_inicio else "Não definido"
          hora_fim_str = ultimo_reg.hora_fim if ultimo_reg.hora_fim else "Não definido"

        pdf.set_font('Times', 'B', 10)
        pdf.cell(60, 10, "Hora de Início da intervenção:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 10, hora_inicio_str, 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(60, 10, "Hora de Término da intervenção:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 10, hora_fim_str, 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(60, 10, "Total de Horas:", 0)
        pdf.set_font('Times', '', 10)
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
        pdf.set_font('Times', 'B', 8)
        pdf.cell(90, 4, 'ASSINATURA DO TÉCNICO', 0, 0, 'C')
        pdf.cell(10, 4, '', 0)
        pdf.cell(90, 4, 'ASSINATURA DO CLIENTE', 0, 1, 'C')

        # ✅ Nome do técnico lido da BD
        pdf.set_y(curr_y + 6)
        pdf.set_font('Times', 'B', 9)
        nome_tec_assinatura = clean_text(i.nome_assinatura_tecnico or "")
        pdf.cell(90, 4, nome_tec_assinatura, 0, 0, 'C')
        pdf.cell(10, 4, '', 0)
        nome_cli_assinatura = clean_text(i.nome_assinatura_cliente or "")
        pdf.cell(90, 4, nome_cli_assinatura, 0, 1, 'C')

        # ✅ Data do técnico lida da BD
        pdf.set_y(curr_y + 11)
        pdf.set_font('Times', 'I', 7)
        data_tec = clean_text(i.data_assinatura_tecnico or "")
        pdf.cell(90, 4, data_tec, 0, 0, 'C')
        pdf.cell(10, 4, '', 0)
        data_cli = clean_text(i.data_assinatura_cliente or "")
        pdf.cell(90, 4, data_cli, 0, 1, 'C')

        pdf.ln(10)

        pdf.set_xy(10, pdf.get_y())
        pdf.set_font('Times', 'B', 10)
        pdf.multi_cell(190, 6, "Caro Cliente faça sempre uma cópia deste documento para atestar a veracidade dos factos, finda a assistência, o cliente dispõe de 2 dias úteis para eventuais reclamações.", 0, 'C')

        pdf.set_xy(10, pdf.get_y())
        pdf.set_font('Times', 'B', 10)
        pdf.multi_cell(190, 6, "Em caso de dúvidas não hesite em contactar-nos através dos seguintes terminais: Geral.clacstecnologia@gmail.com | 925 505 439", 0, 'C')
        pdf.ln(5)

    

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
        pdf.set_auto_page_break(auto=True, margin=35)
        pdf.alias_nb_pages()
        pdf.add_page()

        _fonts = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        pdf.add_font("Times", "", os.path.join(_fonts, "times.ttf"))
        pdf.add_font("Times", "B", os.path.join(_fonts, "timesbd.ttf"))
        pdf.add_font("Times", "I", os.path.join(_fonts, "timesi.ttf"))  

        def draw_section_header(pdf, title):
             # se não couber o cabeçalho + pelo menos uma linha, salta de página
            if pdf.get_y() + 20 > pdf.h - 35:
                pdf.add_page()
            pdf.set_fill_color(200, 225, 255)
            curr_y = pdf.get_y()
            pdf.rect(10, curr_y, 190, 10, 'F')
            pdf.set_font('Times', 'B', 10)
            pdf.cell(0, 10, clean_text(title), 0, 1, 'L')
            pdf.ln(2)

        # --- Dados da Intervencao ---
        draw_section_header(pdf, f"DADOS DA INTERVENÇÃO: {i.numero if i.numero else 'N/A'}")

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Título:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.titulo)), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Status:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.status)), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Prioridade:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(str(i.prioridade)), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Data de Abertura:", 0)
        pdf.set_font('Times', '', 10)

        data_formatada = (
            i.data_criacao.strftime("%d/%m/%Y %H:%M")
            if i.data_criacao else "Não definido"
        )

        pdf.cell(0, 8, data_formatada, 0, 1)

        pdf.ln(5)

        # --- Cliente ---
        draw_section_header(pdf, "CLIENTE")

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Nome:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.nome if i.cliente else "Não definido"), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Empresa:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.empresa if i.cliente else "Não definido"), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Email:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.cliente.email if i.cliente else "Não definido"), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Solicitante:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.solicitante or "Não definido"), 0, 1)

        pdf.ln(5)

        # --- Tecnico ---
        draw_section_header(pdf, "TECNICO RESPONSAVEL")

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Nome:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.tecnico.nome if i.tecnico else "Não atribuido"), 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(40, 8, "Modo de Resolução:", 0)
        pdf.set_font('Times', '', 10)
        pdf.cell(0, 8, clean_text(i.modo_resolucao or "Não definido"), 0, 1)

        pdf.ln(5)

        # --- Imagens Anexadas ---
        imagens = [a for a in i.anexos if a.tipo and a.tipo.startswith("image")]
        if imagens:
            draw_section_header(pdf, "IMAGENS ANEXADAS")

            BOX_W, BOX_H = 85, 60
            COLS = [12, 108]
            col = 0
            y = pdf.get_y() + 4

            for anexo in imagens:
                try:
                    r = requests.get(anexo.url, timeout=10)
                    if r.status_code != 200:
                        continue
                    ext = ".png" if "png" in anexo.url.lower() else ".jpg"
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                    tmp.write(r.content)
                    tmp.close()

                    if y + BOX_H > 265:
                        pdf.add_page()
                        y = pdf.get_y()
                        col = 0

                    pdf.image(tmp.name, x=COLS[col], y=y,
                              w=BOX_W, h=BOX_H, keep_aspect_ratio=True)
                    os.unlink(tmp.name)

                    col += 1
                    if col > 1:
                        col = 0
                        y += BOX_H + 5
                except Exception as e:
                    print(f"Erro ao inserir imagem no PDF: {e}")

            if col == 1:
                y += BOX_H + 5
            pdf.set_y(y + 3)
            pdf.ln(2)

        # --- Descricao do Problema ---
        draw_section_header(pdf, "DESCRIÇÃO DO PROBLEMA")

        pdf.set_font('Times', '', 10)

        pdf.multi_cell(
            0,
            8,
            clean_text(
                str(i.descricao)
                if i.descricao
                else "Sem descrição do problema disponível."
            )
        )

        pdf.ln(5)

        # --- Descricao da Solucao ---
        draw_section_header(pdf, "DESCRIÇÃO DA SOLUÇÃO")

        pdf.set_font('Times', '', 10)

        if not i.registros_horas:
            pdf.multi_cell(0, 8, "Nenhuma tarefa registrada até ao momento.")
        else:
            for reg in i.registros_horas:
                data_reg = reg.data if reg.data else "Não definido"
                nome_tec = clean_text(reg.tecnico.nome) if reg.tecnico else "Não definido"
                descricao = clean_text(reg.descricao) if reg.descricao else ""

                texto_tarefa = f"- [{data_reg}] [{nome_tec}] {descricao}"

                pdf.multi_cell(0, 7, texto_tarefa)

        pdf.ln(10)

        # --- Resumo de Tempo ---
        draw_section_header(pdf, "RESUMO DE TEMPO")

        hora_inicio_str = "Não definido"
        hora_fim_str = "Não definido"

        if i.registros_horas:
            primeiro_reg = i.registros_horas[0]
            ultimo_reg = i.registros_horas[-1]

            hora_inicio_str = (
                primeiro_reg.hora_inicio
                if primeiro_reg.hora_inicio else "Não definido"
            )

            hora_fim_str = (
                ultimo_reg.hora_fim
                if ultimo_reg.hora_fim else "Não definido"
            )

        pdf.set_font('Times', 'B', 10)
        pdf.cell(60, 10, "Hora de Início da intervenção:", 0)

        pdf.set_font('Times', '', 10)
        pdf.cell(0, 10, hora_inicio_str, 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(60, 10, "Hora de Término da intervenção:", 0)

        pdf.set_font('Times', '', 10)
        pdf.cell(0, 10, hora_fim_str, 0, 1)

        pdf.set_font('Times', 'B', 10)
        pdf.cell(60, 10, "Total de Horas:", 0)

        pdf.set_font('Times', '', 10)
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

        pdf.set_font('Times', 'B', 8)

        pdf.cell(90, 4, 'ASSINATURA DO TÉCNICO', 0, 0, 'C')
        pdf.cell(10, 4, '', 0)
        pdf.cell(90, 4, 'ASSINATURA DO CLIENTE', 0, 1, 'C')

        pdf.set_y(curr_y + 6)

        pdf.set_font('Times', 'B', 9)

        # ✅ Usa sempre o que está guardado na BD
        nome_tec_assinatura = clean_text(
            i.nome_assinatura_tecnico or (i.tecnico.nome if i.tecnico else "")
        )

        pdf.cell(90, 4, nome_tec_assinatura, 0, 0, 'C')

        pdf.cell(10, 4, '', 0)

        nome_cli_assinatura = clean_text(i.nome_assinatura_cliente or "")

        pdf.cell(90, 4, nome_cli_assinatura, 0, 1, 'C')

        pdf.set_y(curr_y + 11)

        pdf.set_font('Times', 'I', 7)

        # ✅ Data do técnico vem sempre da BD — nunca muda
        data_tec = clean_text(i.data_assinatura_tecnico or "")
        data_cli = clean_text(i.data_assinatura_cliente or "")

        pdf.cell(90, 4, data_tec, 0, 0, 'C')

        pdf.cell(10, 4, '', 0)

        pdf.cell(90, 4, data_cli, 0, 1, 'C')

        pdf.ln(10)

        pdf.set_xy(10, pdf.get_y())
        pdf.set_font('Times', 'B', 10)
        pdf.multi_cell(190, 6, "Caro Cliente faca sempre uma copia deste documento para atestar a veracidade dos factos, findo assistencia, o cliente dispoe de 2 dias uteis para eventuais reclamacoes.", 0, 'C')

        pdf.set_xy(10, pdf.get_y())
        pdf.set_font('Times', 'B', 10)
        pdf.multi_cell(190, 6, "Em caso de duvidas nao hesite em contactar-nos atraves dos seguintes terminais: Geral.clacstecnologia@gmail.com | 925 505 439 | 918 945 5", 0, 'C')

        pdf.ln(5)


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