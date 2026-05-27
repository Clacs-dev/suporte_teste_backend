from fpdf import FPDF
import io

pdf = FPDF()
pdf.add_page()
pdf.set_font('helvetica', 'B', 16)
pdf.cell(40, 10, 'Hello World!')
out = pdf.output()
print(f"Type of output: {type(out)}")
if isinstance(out, (bytes, bytearray)):
    print("Output is bytes/bytearray")
