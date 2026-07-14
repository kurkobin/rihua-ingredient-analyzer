"""PDF 报告生成服务

用 reportlab 生成成分分析报告 PDF。
支持中文(内置 STSong-Light 字体)。
"""
import io
import json
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 注册中文字体(ReportLab 内置,无需额外字体文件)
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

# 颜色定义
COLOR_GOOD = HexColor("#00b894")
COLOR_MID = HexColor("#fdcb6e")
COLOR_BAD = HexColor("#d63031")
COLOR_PRIMARY = HexColor("#0984e3")
COLOR_GRAY = HexColor("#636e72")
COLOR_LIGHT = HexColor("#f8f9fa")


def generate_report_pdf(result_json: str, created_at: str | None = None) -> bytes:
    """生成 PDF 报告,返回 PDF 字节流

    参数:
        result_json: AnalysisResponse 的 JSON 字符串
        created_at: 分析时间(ISO 格式),可选

    返回:
        PDF 文件的字节内容
    """
    data = json.loads(result_json)

    # 准备数据
    product_type = data.get("product_type", "") or "未知产品"
    score = data.get("score", 0)
    summary = data.get("summary", "") or "暂无简评"
    pros = data.get("pros", [])
    cons = data.get("cons", [])
    ingredients = data.get("ingredients", [])
    ocr_text = data.get("ocr_text", "")

    # 创建 PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    # 样式
    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "ChTitle", parent=styles["Title"],
        fontName="STSong-Light", fontSize=22, leading=30,
        textColor=COLOR_PRIMARY, alignment=1,  # 居中
    )
    style_h2 = ParagraphStyle(
        "ChH2", parent=styles["Heading2"],
        fontName="STSong-Light", fontSize=14, leading=20,
        textColor=HexColor("#2d3436"), spaceBefore=12, spaceAfter=6,
    )
    style_normal = ParagraphStyle(
        "ChNormal", parent=styles["Normal"],
        fontName="STSong-Light", fontSize=10, leading=16,
        textColor=HexColor("#2d3436"),
    )
    style_small = ParagraphStyle(
        "ChSmall", parent=styles["Normal"],
        fontName="STSong-Light", fontSize=8, leading=12,
        textColor=COLOR_GRAY,
    )
    style_ocr = ParagraphStyle(
        "ChOCR", parent=styles["Normal"],
        fontName="STSong-Light", fontSize=8, leading=12,
        textColor=COLOR_GRAY, backColor=COLOR_LIGHT,
        borderPadding=8, leftIndent=4, rightIndent=4,
    )
    # 成分表格样式(表头白字 + 单元格自动换行)
    style_th = ParagraphStyle(
        "TableHeader", parent=styles["Normal"],
        fontName="STSong-Light", fontSize=9, leading=12,
        textColor=HexColor("#ffffff"), alignment=1,  # 居中
    )
    style_td = ParagraphStyle(
        "TableCell", parent=styles["Normal"],
        fontName="STSong-Light", fontSize=8, leading=11,
        textColor=HexColor("#2d3436"),
    )

    story = []

    # ===== 标题 =====
    story.append(Paragraph("成分分析报告", style_title))
    story.append(Spacer(1, 6 * mm))

    # ===== 基本信息 =====
    time_str = ""
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            time_str = created_at
    else:
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    info_data = [
        ["产品品类", product_type],
        ["分析时间", time_str],
        ["成分数量", f"{len(ingredients)} 种"],
    ]
    info_table = Table(info_data, colWidths=[30 * mm, 120 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_GRAY),
        ("TEXTCOLOR", (1, 0), (1, -1), HexColor("#2d3436")),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, HexColor("#dfe6e9")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6 * mm))

    # ===== 评分 =====
    score_color = COLOR_GOOD if score >= 86 else (COLOR_MID if score >= 60 else COLOR_BAD)
    # reportlab Paragraph 的 <font color> 需要 #RRGGBB 格式,hexval() 返回 0xRRGGBB
    score_hex = "#%02X%02X%02X" % (
        int(score_color.red * 255), int(score_color.green * 255), int(score_color.blue * 255)
    )
    score_data = [[
        Paragraph(f'<font size="36" color="{score_hex}"><b>{score}</b></font>', style_normal),
        Paragraph(f'<font size="10" color="#636e72">综合评分(满分100)</font><br/><font size="9">{escape(summary)}</font>', style_normal),
    ]]
    score_table = Table(score_data, colWidths=[40 * mm, 110 * mm])
    score_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 6 * mm))

    # ===== 优缺点 =====
    story.append(Paragraph("优缺点分析", style_h2))

    pros_text = "<br/>".join(f"✅ {escape(str(p))}" for p in pros) if pros else '<font color="#b2bec3">暂无</font>'
    cons_text = "<br/>".join(f"⚠️ {escape(str(c))}" for c in cons) if cons else '<font color="#b2bec3">暂无</font>'

    pc_data = [[
        Paragraph(f'<font color="#00b894"><b>优点</b></font><br/>{pros_text}', style_small),
        Paragraph(f'<font color="#d63031"><b>缺点</b></font><br/>{cons_text}', style_small),
    ]]
    pc_table = Table(pc_data, colWidths=[75 * mm, 75 * mm])
    pc_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, 0), HexColor("#e6fffa")),
        ("BACKGROUND", (1, 0), (1, 0), HexColor("#fff0f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(pc_table)
    story.append(Spacer(1, 6 * mm))

    # ===== 成分列表 =====
    story.append(Paragraph(f"成分清单(共{len(ingredients)}项)", style_h2))

    # 表头(用 Paragraph 以便与其他单元格一致,颜色由样式控制)
    ing_header = [
        Paragraph("成分名称", style_th),
        Paragraph("分类", style_th),
        Paragraph("风险", style_th),
        Paragraph("说明", style_th),
        Paragraph("法规出处", style_th),
    ]
    ing_rows = [ing_header]
    for ing in ingredients:
        # 单元格用 Paragraph 包裹,实现自动换行(不再需要手动截断)
        # 所有动态文本都需 escape,避免 & < > 导致 paraparser 错误
        ing_rows.append([
            Paragraph(escape(ing.get("name", "") or "-"), style_td),
            Paragraph(escape(ing.get("category") or "-"), style_td),
            Paragraph(escape(ing.get("risk_level") or "-"), style_td),
            Paragraph(escape(ing.get("description") or "-"), style_td),
            Paragraph(escape(ing.get("reference") or "-"), style_td),
        ])

    ing_table = Table(ing_rows, colWidths=[25 * mm, 20 * mm, 15 * mm, 55 * mm, 35 * mm], repeatRows=1)
    ing_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTSIZE", (0, 0), (-1, 0), 9),  # 表头稍大
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#dfe6e9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#ffffff"), COLOR_LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(ing_table)
    story.append(Spacer(1, 6 * mm))

    # ===== OCR 原文 =====
    if ocr_text:
        story.append(Paragraph("识别原文", style_h2))
        # 截断过长的 OCR 文本
        display_text = ocr_text if len(ocr_text) < 1000 else ocr_text[:997] + "..."
        # 先 escape 再替换换行,避免文本中的 & < > 导致解析错误
        story.append(Paragraph(escape(display_text).replace("\n", "<br/>"), style_ocr))
        story.append(Spacer(1, 6 * mm))

    # ===== 页脚 =====
    story.append(Spacer(1, 8 * mm))
    footer = ParagraphStyle(
        "Footer", parent=style_small,
        alignment=1,  # 居中
        fontSize=8,
        textColor=COLOR_GRAY,
    )
    story.append(Paragraph("本报告由「成分扫一扫」生成,仅供参考", footer))
    story.append(Paragraph(f"生成时间:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer))

    # 构建 PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
