"""
Pure-Python PDF generation using reportlab.
Replaces WeasyPrint which requires system libraries.
"""
import io
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def generate_invoice_pdf(invoice) -> io.BytesIO:
    """Generate PDF for an invoice using reportlab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#0f172a'))
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#64748b'))
    value_style = ParagraphStyle('Value', parent=styles['Normal'], fontSize=12, textColor=colors.HexColor('#0f172a'))
    
    elements = []
    
    # Header
    business = invoice.business
    elements.append(Paragraph(f"INVOICE", title_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"#{invoice.invoice_number}", header_style))
    elements.append(Spacer(1, 20))
    
    # Business info
    elements.append(Paragraph(f"<b>From:</b> {business.name}", value_style))
    elements.append(Spacer(1, 12))
    
    # Customer info
    customer = invoice.customer
    elements.append(Paragraph(f"<b>Bill To:</b>", header_style))
    elements.append(Paragraph(f"{customer.name}", value_style))
    if customer.email:
        elements.append(Paragraph(f"{customer.email}", header_style))
    elements.append(Spacer(1, 20))
    
    # Dates table
    date_data = [
        ['Issue Date', 'Due Date', 'Status'],
        [
            invoice.issue_date.strftime('%b %d, %Y') if invoice.issue_date else '-',
            invoice.due_date.strftime('%b %d, %Y') if invoice.due_date else '-',
            invoice.get_status_display()
        ]
    ]
    date_table = Table(date_data, colWidths=[2*inch, 2*inch, 2*inch])
    date_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#64748b')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    elements.append(date_table)
    elements.append(Spacer(1, 20))
    
    # Description
    if invoice.description:
        elements.append(Paragraph(f"<b>Description:</b>", header_style))
        elements.append(Paragraph(invoice.description, value_style))
        elements.append(Spacer(1, 20))
    
    # Amounts
    currency = getattr(business, 'currency', 'CAD') or 'CAD'
    amounts = [
        ['Subtotal', f"{invoice.net_total or invoice.total_amount:.2f} {currency}"],
        ['Tax', f"{invoice.tax_total or Decimal('0.00'):.2f} {currency}"],
        ['Total', f"{invoice.grand_total or invoice.total_amount:.2f} {currency}"],
    ]
    
    if invoice.status == 'PAID':
        amounts.append(['Amount Paid', f"{invoice.amount_paid:.2f} {currency}"])
        amounts.append(['Balance Due', f"{invoice.balance:.2f} {currency}"])
    
    amount_table = Table(amounts, colWidths=[4*inch, 2*inch])
    amount_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
    ]))
    elements.append(amount_table)
    
    # Notes
    if invoice.notes:
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(f"<b>Notes:</b>", header_style))
        elements.append(Paragraph(invoice.notes, value_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_expense_pdf(expense) -> io.BytesIO:
    """Generate PDF for an expense using reportlab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#dc2626'))
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#64748b'))
    value_style = ParagraphStyle('Value', parent=styles['Normal'], fontSize=12, textColor=colors.HexColor('#0f172a'))
    
    elements = []
    
    # Header
    business = expense.business
    elements.append(Paragraph(f"EXPENSE", title_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"#{expense.pk}", header_style))
    elements.append(Spacer(1, 20))
    
    # Business info
    elements.append(Paragraph(f"<b>Business:</b> {business.name}", value_style))
    elements.append(Spacer(1, 12))
    
    # Supplier info
    if expense.supplier:
        elements.append(Paragraph(f"<b>Supplier:</b> {expense.supplier.name}", value_style))
        elements.append(Spacer(1, 12))
    
    # Category
    if expense.category:
        elements.append(Paragraph(f"<b>Category:</b> {expense.category.name}", value_style))
        elements.append(Spacer(1, 12))
    
    # Date and Status
    date_data = [
        ['Date', 'Status'],
        [
            expense.date.strftime('%b %d, %Y') if expense.date else '-',
            expense.get_status_display()
        ]
    ]
    date_table = Table(date_data, colWidths=[3*inch, 3*inch])
    date_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#64748b')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    elements.append(date_table)
    elements.append(Spacer(1, 20))
    
    # Description
    if expense.description:
        elements.append(Paragraph(f"<b>Description:</b>", header_style))
        elements.append(Paragraph(expense.description, value_style))
        elements.append(Spacer(1, 20))
    
    # Amounts
    currency = getattr(business, 'currency', 'CAD') or 'CAD'
    amounts = [
        ['Amount', f"{expense.amount:.2f} {currency}"],
        ['Tax', f"{expense.tax_amount or Decimal('0.00'):.2f} {currency}"],
        ['Total', f"{expense.grand_total or expense.amount:.2f} {currency}"],
    ]
    
    amount_table = Table(amounts, colWidths=[4*inch, 2*inch])
    amount_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
    ]))
    elements.append(amount_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
