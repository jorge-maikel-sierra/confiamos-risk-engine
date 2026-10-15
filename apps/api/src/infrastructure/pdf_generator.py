"""Generador de legajos crediticios oficiales en PDF (SPEC-07)."""

import io
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class PdfDossierGenerator:
    """Construye el documento PDF formal del dictamen de riesgo bancario."""

    def __init__(self) -> None:
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()

    def _init_custom_styles(self) -> None:
        self.title_style = ParagraphStyle(
            "DocTitle",
            parent=self.styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=4,
        )
        self.subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=self.styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#2563EB"),
            spaceAfter=8,
        )
        self.section_header = ParagraphStyle(
            "SectionHeader",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=8,
            spaceAfter=4,
        )
        self.body_style = ParagraphStyle(
            "Body",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
        self.body_bold = ParagraphStyle(
            "BodyBold",
            parent=self.body_style,
            fontName="Helvetica-Bold",
        )
        self.hash_style = ParagraphStyle(
            "HashStyle",
            parent=self.styles["Normal"],
            fontName="Courier",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#64748B"),
        )

    def generate(self, data: dict[str, Any]) -> bytes:
        """Renderiza la información de la solicitud en un buffer binario PDF."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
            pageCompression=0,
        )

        story = []

        # 1. Membrete Institucional
        story.append(Paragraph("COOPERATIVA CONFIAMOS", self.title_style))
        story.append(
            Paragraph(
                "DICTAMEN TÉCNICO DE EVALUACIÓN CREDITICIA PyME",
                self.subtitle_style,
            )
        )
        story.append(
            Paragraph(
                f"Folio de Solicitud: {escape(str(data.get('id', 'N/A')))} | "
                f"Fecha: {escape(str(data.get('created_at', 'N/A')))}",
                self.hash_style,
            )
        )
        story.append(
            HRFlowable(
                width="100%",
                thickness=1,
                color=colors.HexColor("#CBD5E1"),
                spaceAfter=10,
            )
        )

        # 2. Información del Asociado y Crédito
        story.append(Paragraph("1. INFORMACIÓN DEL ASOCIADO Y SOLICITUD", self.section_header))
        biz_name = escape(str(data.get("business_name", "N/A")))
        asoc_id = escape(str(data.get("associated_id", "N/A")))
        amount = f"${data.get('requested_amount_usd', 0.0):,.2f} USD"
        term = f"{data.get('term_months', 0)} Meses"

        info_data = [
            [
                Paragraph("<b>Razón Social:</b>", self.body_style),
                Paragraph(biz_name, self.body_style),
                Paragraph("<b>Identificación / NIT:</b>", self.body_style),
                Paragraph(asoc_id, self.body_style),
            ],
            [
                Paragraph("<b>Monto Solicitado:</b>", self.body_style),
                Paragraph(amount, self.body_style),
                Paragraph("<b>Plazo Amortización:</b>", self.body_style),
                Paragraph(term, self.body_style),
            ],
        ]
        info_table = Table(info_data, colWidths=[110, 160, 120, 150])
        info_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(info_table)
        story.append(Spacer(1, 8))

        # 3. Matriz de Solvencia Financiera Determinística
        story.append(
            Paragraph("2. MATRIZ DE SOLVENCIA FINANCIERA (CÁLCULO EXACTO)", self.section_header)
        )
        metrics = data.get("metrics") or {}
        dscr_val = metrics.get("dscr")
        dscr_str = f"{dscr_val:.2f}x" if dscr_val is not None else "N/A (Sin deuda)"
        curr_ratio = metrics.get("current_ratio", 0.0)
        curr_ratio_str = f"{curr_ratio:.2f}x"
        runway = metrics.get("runway_months")
        runway_str = f"{runway:.1f} meses" if runway is not None else "N/A"
        ocf = f"${metrics.get('operating_cash_flow', 0.0):,.2f} USD"
        ads = f"${metrics.get('annual_debt_service', 0.0):,.2f} USD"

        dscr_diag = "Solvente" if (dscr_val or 0) >= 1.25 else "Riesgo Ajustado"
        metrics_data = [
            [
                Paragraph("<b>Métrica Financiera</b>", self.body_bold),
                Paragraph("<b>Valor Obtenido</b>", self.body_bold),
                Paragraph("<b>Benchmark Bancario</b>", self.body_bold),
                Paragraph("<b>Diagnóstico</b>", self.body_bold),
            ],
            [
                Paragraph("DSCR (Cobertura de Deuda)", self.body_style),
                Paragraph(dscr_str, self.body_bold),
                Paragraph("≥ 1.25x", self.body_style),
                Paragraph(dscr_diag, self.body_style),
            ],
            [
                Paragraph("Ratio de Liquidez Corriente", self.body_style),
                Paragraph(curr_ratio_str, self.body_bold),
                Paragraph("≥ 1.30x", self.body_style),
                Paragraph("Óptimo" if curr_ratio >= 1.30 else "Liquidez Ajustada", self.body_style),
            ],
            [
                Paragraph("Runway (Meses de Caja)", self.body_style),
                Paragraph(runway_str, self.body_bold),
                Paragraph("≥ 6.0 meses", self.body_style),
                Paragraph("Holgado" if (runway or 0) >= 6.0 else "Vulnerable", self.body_style),
            ],
            [
                Paragraph("Flujo de Caja Operativo Anual", self.body_style),
                Paragraph(ocf, self.body_style),
                Paragraph("Positivo (> 0)", self.body_style),
                Paragraph("Genera Caja Operativa", self.body_style),
            ],
            [
                Paragraph("Servicio Anual de la Deuda", self.body_style),
                Paragraph(ads, self.body_style),
                Paragraph("Capacidad de pago", self.body_style),
                Paragraph("Compromisos financieros", self.body_style),
            ],
        ]
        metrics_table = Table(metrics_data, colWidths=[160, 110, 120, 150])
        metrics_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(metrics_table)
        story.append(Spacer(1, 8))

        # 4. Dictamen Cualitativo del Asistente de IA (Gemini)
        story.append(
            Paragraph("3. DICTAMEN DE RIESGO Y RECOMENDACIÓN TÉCNICA", self.section_header)
        )
        ai = data.get("ai_verdict") or {}
        rec = str(ai.get("recommendation", "RECHAZADO"))
        conf = f"{ai.get('confidence_score', 0.0) * 100:.1f}%"
        summary = escape(str(ai.get("executive_summary", "Sin dictamen.")))

        rec_color = colors.HexColor("#059669") if "APROBADO" in rec else colors.HexColor("#E11D48")

        rec_html = f"<b>Recomendación:</b> <font color='{rec_color.hexval()}'>{escape(rec)}</font>"
        verdict_data = [
            [
                Paragraph(rec_html, self.body_bold),
                Paragraph(f"<b>Nivel de Confianza:</b> {conf}", self.body_bold),
            ],
            [
                Paragraph(f"<b>Resumen Ejecutivo:</b> {summary}", self.body_style),
                "",
            ],
        ]
        verdict_table = Table(verdict_data, colWidths=[270, 270])
        verdict_table.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 1), (1, 1)),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(verdict_table)
        story.append(Spacer(1, 8))

        # 5. Cuestionario de Due Diligence
        dd_questions = ai.get("due_diligence_questions") or []
        if dd_questions:
            story.append(
                Paragraph("4. CUESTIONARIO MANDATORIO DE DUE DILIGENCE", self.section_header)
            )
            for i, q in enumerate(dd_questions, 1):
                story.append(
                    Paragraph(
                        f"<b>{i}.</b> {escape(str(q))}",
                        self.body_style,
                    )
                )
            story.append(Spacer(1, 8))

        # 6. Precedentes Históricos de Cartera (pgvector)
        precedents = data.get("precedents") or []
        if precedents:
            story.append(
                Paragraph("5. PRECEDENTES HISTÓRICOS DE CARTERA (pgvector)", self.section_header)
            )
            prec_rows = [
                [
                    Paragraph("<b>Asociado Precedente</b>", self.body_bold),
                    Paragraph("<b>Monto Histórico</b>", self.body_bold),
                    Paragraph("<b>Comportamiento</b>", self.body_bold),
                    Paragraph("<b>Similitud</b>", self.body_bold),
                ]
            ]
            for p in precedents[:3]:
                outcome_str = escape(str(p.get("outcome", "PAGADO")))
                prec_rows.append(
                    [
                        Paragraph(escape(str(p.get("business_name", "N/A"))), self.body_style),
                        Paragraph(f"${p.get('loan_amount_usd', 0.0):,.2f}", self.body_style),
                        Paragraph(outcome_str, self.body_style),
                        Paragraph(f"{p.get('similarity_score', 0.0):.2f}", self.body_style),
                    ]
                )
            prec_table = Table(prec_rows, colWidths=[180, 120, 120, 120])
            prec_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            story.append(prec_table)
            story.append(Spacer(1, 10))

        # 7. Sello Criptográfico de Integridad y Firmas del Comité
        story.append(
            Paragraph("6. CERTIFICACIÓN DE INTEGRIDAD Y FIRMAS DEL COMITÉ", self.section_header)
        )
        hash_val = escape(str(data.get("crypto_hash", "NO_HASH_GENERATED")))
        story.append(
            Paragraph(
                f"<b>Sello Criptográfico de Integridad (SHA-256):</b><br/>{hash_val}",
                self.hash_style,
            )
        )
        story.append(Spacer(1, 20))

        sig_left = (
            "___________________________________<br/>"
            "<b>Presidente del Comité de Crédito</b><br/>"
            "Cooperativa Confiamos"
        )
        sig_right = (
            "___________________________________<br/>"
            "<b>Oficial Principal de Riesgo</b><br/>"
            "Cooperativa Confiamos"
        )
        sig_data = [
            [
                Paragraph(sig_left, self.body_style),
                Paragraph(sig_right, self.body_style),
            ]
        ]
        sig_table = Table(sig_data, colWidths=[270, 270])
        sig_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(sig_table)

        doc.build(story)
        return buffer.getvalue()
