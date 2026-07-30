"""Génération de reçus PDF (fpdf2)."""

from fpdf import FPDF

from nzassa.models.business import Branch, Business
from nzassa.models.sales import Sale


def build_receipt_pdf(sale: Sale, business: Business, branch: Branch) -> bytes:
    pdf = FPDF(format=(80, 200))  # format ticket 80mm
    pdf.set_auto_page_break(auto=True, margin=8)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 5, business.trade_name, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 7)
    if branch.receipt_header:
        pdf.multi_cell(0, 3.5, branch.receipt_header, align="C")
    if branch.address:
        pdf.cell(0, 3.5, branch.address, align="C", new_x="LMARGIN", new_y="NEXT")
    if branch.phone:
        pdf.cell(0, 3.5, f"Tel: {branch.phone}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 2, "-" * 48, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, f"Recu N. {sale.number}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 4, f"Date : {sale.sold_at:%d/%m/%Y %H:%M}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 2, "-" * 48, align="C", new_x="LMARGIN", new_y="NEXT")

    for item in sale.items:
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(0, 4, item.label[:38], new_x="LMARGIN", new_y="NEXT")
        line = f"  {item.quantity} x {item.unit_price:,.0f}"
        pdf.cell(40, 4, line)
        pdf.cell(0, 4, f"{item.line_total:,.0f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.cell(0, 2, "-" * 48, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(40, 5, "TOTAL")
    pdf.cell(
        0, 5, f"{sale.total:,.0f} {business.currency}", align="R", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(40, 4, "Paye")
    pdf.cell(0, 4, f"{sale.amount_paid:,.0f}", align="R", new_x="LMARGIN", new_y="NEXT")
    if sale.amount_due > 0:
        pdf.cell(40, 4, "Reste du")
        pdf.cell(0, 4, f"{sale.amount_due:,.0f}", align="R", new_x="LMARGIN", new_y="NEXT")
    for payment in sale.payments:
        pdf.cell(40, 4, f"  {payment.method}")
        pdf.cell(0, 4, f"{payment.amount:,.0f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 2, "-" * 48, align="C", new_x="LMARGIN", new_y="NEXT")
    footer = branch.receipt_footer or "Merci de votre visite !"
    pdf.set_font("Helvetica", "I", 7)
    pdf.multi_cell(0, 3.5, footer, align="C")
    return bytes(pdf.output())
