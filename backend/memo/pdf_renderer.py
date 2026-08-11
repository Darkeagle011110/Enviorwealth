import io
import json
from typing import Dict, Any

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
except ImportError:
    pass

class PDFRenderer:
    """
    Renders the structured JSON memo into a downloadable PDF.
    Uses ReportLab.
    """
    
    @staticmethod
    def render_memo(memo_data: Dict[str, Any]) -> bytes:
        """Returns the PDF as a byte string."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            rightMargin=72, leftMargin=72,
            topMargin=72, bottomMargin=18
        )
        
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        h2_style = styles['Heading2']
        normal_style = styles['Normal']
        
        # We can define a custom style for the disclaimer
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=HexColor("#666666"),
            italic=True
        )
        
        elements = []
        
        # Header
        elements.append(Paragraph("Carbon Credit Eligibility Memo", title_style))
        elements.append(Paragraph(f"Generated at: {memo_data.get('generated_at')}", disclaimer_style))
        elements.append(Spacer(1, 12))
        
        # Verdict
        v = memo_data.get("verdict", {})
        elements.append(Paragraph(f"<b>Verdict:</b> {v.get('category')} (Confidence: {v.get('confidence')})", h2_style))
        elements.append(Spacer(1, 12))
        
        # Explanation
        elements.append(Paragraph("<b>Explanation</b>", h2_style))
        elements.append(Paragraph(memo_data.get("why", ""), normal_style))
        elements.append(Spacer(1, 12))
        
        # Financials
        fin = memo_data.get("financials")
        if fin:
            elements.append(Paragraph("<b>Indicative Estimates</b>", h2_style))
            elements.append(Paragraph(f"Annual Credits: {fin['annual_credits_range'][0]} - {fin['annual_credits_range'][1]} tonnes/yr", normal_style))
            elements.append(Paragraph(f"Estimated Revenue: ${fin['revenue_usd_range'][0]} - ${fin['revenue_usd_range'][1]} USD/yr", normal_style))
            elements.append(Paragraph(f"First Issuance: Year {fin['first_issuance_years'][0]} to {fin['first_issuance_years'][1]}", normal_style))
            elements.append(Spacer(1, 12))
            
        # Lists (Flags, Next Steps, etc.)
        list_sections = [
            ("Risk Flags", "risk_flags"),
            ("Next Steps", "next_steps"),
            ("Alternatives", "alternatives"),
            ("Questions for Developers", "developer_questions"),
            ("Unverified Fields", "unverified_fields")
        ]
        
        for title, key in list_sections:
            items = memo_data.get(key)
            if items:
                elements.append(Paragraph(f"<b>{title}</b>", h2_style))
                list_items = [ListItem(Paragraph(str(item), normal_style)) for item in items]
                elements.append(ListFlowable(list_items, bulletType='bullet'))
                elements.append(Spacer(1, 12))
                
        # Disclaimer at bottom
        elements.append(Spacer(1, 24))
        elements.append(Paragraph(memo_data.get("disclaimer", ""), disclaimer_style))
        
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
