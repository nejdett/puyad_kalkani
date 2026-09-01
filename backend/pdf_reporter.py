# Puyad Kalkanı
# PDF rapor uretici (reportlab + DejaVu Sans unicode font)
import io
import platform
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

import database
import remediation_engine


# --- Unicode Font Kaydi (Turkce karakter destegi) ---
FONT_NAME = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
_FONT_REGISTERED = False


def _register_fonts():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    _FONT_REGISTERED = True

    # Proje dizinindeki fonts/ klasoru (once yuklu gelen)
    project_dir = Path(__file__).parent / "fonts"
    local_regular = project_dir / "DejaVuSans.ttf"
    local_bold = project_dir / "DejaVuSans-Bold.ttf"
    if local_regular.exists():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(local_regular)))
        if local_bold.exists():
            pdfmetrics.registerFont(TTFont(FONT_BOLD, str(local_bold)))
        else:
            pdfmetrics.registerFont(TTFont(FONT_BOLD, str(local_regular)))
        addMapping(FONT_NAME, 0, 0, FONT_NAME)
        addMapping(FONT_NAME, 1, 0, FONT_BOLD)
        return

    # Sistem font dizinleri (Linux distrolari icin)
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
         "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ]

    for regular, bold in candidates:
        if Path(regular).exists():
            pdfmetrics.registerFont(TTFont(FONT_NAME, regular))
            if Path(bold).exists():
                pdfmetrics.registerFont(TTFont(FONT_BOLD, bold))
            else:
                pdfmetrics.registerFont(TTFont(FONT_BOLD, regular))
            addMapping(FONT_NAME, 0, 0, FONT_NAME)
            addMapping(FONT_NAME, 1, 0, FONT_BOLD)
            return

    # Font bulunamadi - Helvetica ile devam et
    _FONT_REGISTERED = False


_register_fonts()


def _font(bold=False):
    """Aktif fontu dondurur. Kayitli degilse Helvetica fallback.encoded str[]"""
    if _FONT_REGISTERED:
        return FONT_BOLD if bold else FONT_NAME
    return "Helvetica-Bold" if bold else "Helvetica"

C_BG        = colors.HexColor("#0f1117")
C_CARD      = colors.HexColor("#1a1d2e")
C_BORDER    = colors.HexColor("#2d3561")
C_ACCENT    = colors.HexColor("#7c8cf8")
C_GREEN     = colors.HexColor("#22c55e")
C_YELLOW    = colors.HexColor("#f59e0b")
C_RED       = colors.HexColor("#ef4444")
C_TEXT      = colors.HexColor("#e2e8f0")
C_MUTED     = colors.HexColor("#64748b")
C_WHITE     = colors.white
C_BLACK     = colors.black


def _score_color(score: int):
    if score >= 80:
        return C_GREEN
    elif score >= 50:
        return C_YELLOW
    return C_RED


def _score_label(score: int) -> str:
    if score >= 80:
        return "İYİ"
    elif score >= 50:
        return "ORTA"
    return "KRİTİK"


def _build_score_gauge(score: int, width: float = 300, height: float = 40) -> Drawing:
    d = Drawing(width, height)
    bar_w = width - 20
    bar_h = 18
    x0, y0 = 10, (height - bar_h) / 2

    d.add(Rect(x0, y0, bar_w, bar_h,
               fillColor=colors.HexColor("#1e2235"), strokeColor=C_BORDER, strokeWidth=1))
    fill_w = max(4, bar_w * score / 100)
    d.add(Rect(x0, y0, fill_w, bar_h,
               fillColor=_score_color(score), strokeColor=None))
    d.add(String(x0 + bar_w / 2, y0 + 4, f"{score}/100",
                 fontSize=10, fillColor=C_WHITE, textAnchor="middle",
                 fontName=_font()))
    return d


def _build_category_chart(category_stats: dict, width: float = 460, height: float = 160) -> Drawing:
    d = Drawing(width, height)
    cats = list(category_stats.items())
    if not cats:
        return d

    bar_w = min(40, (width - 60) / len(cats) - 8)
    spacing = (width - 60) / len(cats)
    max_val = max((v["total"] for _, v in cats), default=1)

    for i, (cat, vals) in enumerate(cats):
        x = 30 + i * spacing + spacing / 2 - bar_w / 2
        chart_h = height - 40

        ok_h = max(2, (vals["ok"] / max_val) * chart_h) if max_val else 2
        d.add(Rect(x, 20, bar_w * 0.45, ok_h,
                   fillColor=C_GREEN, strokeColor=None))

        fail_h = max(2, (vals["fail"] / max_val) * chart_h) if max_val else 2
        d.add(Rect(x + bar_w * 0.5, 20, bar_w * 0.45, fail_h,
                   fillColor=C_RED, strokeColor=None))

        short = cat[:8] if len(cat) > 8 else cat
        d.add(String(x + bar_w / 2, 8, short,
                     fontSize=6, fillColor=C_MUTED, textAnchor="middle",
                     fontName=_font()))

    return d


def generate_report(scan_id: int = None) -> bytes:
    with database.get_connection() as conn:
        if scan_id:
            scan = conn.execute(
                "SELECT * FROM scan_history WHERE id = ?", (scan_id,)
            ).fetchone()
        else:
            scan = conn.execute(
                "SELECT * FROM scan_history ORDER BY created_at DESC LIMIT 1"
            ).fetchone()

        if not scan:
            scan = {"id": 0, "total": 0, "warnings": 0, "ok_count": 0,
                    "score": 0, "created_at": datetime.now().isoformat()}
            scan_results = []
        else:
            scan = dict(scan)
            scan_results = conn.execute(
                "SELECT * FROM scan_results WHERE scan_id = ? ORDER BY status",
                (scan["id"],)
            ).fetchall()
            scan_results = [dict(r) for r in scan_results]

        fixes = conn.execute(
            "SELECT * FROM fix_history ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        fixes = [dict(r) for r in fixes]

        trend = conn.execute(
            "SELECT score, created_at FROM scan_history ORDER BY created_at ASC LIMIT 10"
        ).fetchall()
        trend = [dict(r) for r in trend]

    category_stats = {}
    for r in scan_results:
        cat = r.get("rule_name", "").split(" ")[0] if r.get("rule_name") else "Diğer"
        if cat not in category_stats:
            category_stats[cat] = {"ok": 0, "fail": 0, "total": 0}
        category_stats[cat]["total"] += 1
        if r["status"] == "ok":
            category_stats[cat]["ok"] += 1
        else:
            category_stats[cat]["fail"] += 1

    score = scan.get("score", 0)
    report_date = datetime.now().strftime("%d.%m.%Y %H:%M")
    hostname = platform.node() or "Linux Sunucu"
    os_info = f"{platform.system()} {platform.release()}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Puyad Kalkanı Güvenlik Raporu",
        author="Puyad Kalkanı"
    )

    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        "Title", parent=styles["Normal"],
        fontSize=22, textColor=C_ACCENT,
        spaceAfter=4, alignment=TA_LEFT, fontName=_font(True)
    )
    sub_style = ParagraphStyle(
        "Sub", parent=styles["Normal"],
        fontSize=10, textColor=C_MUTED,
        spaceAfter=2, alignment=TA_LEFT, fontName=_font()
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=9, textColor=C_TEXT,
        spaceAfter=4, leading=14, fontName=_font()
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Normal"],
        fontSize=12, textColor=C_ACCENT,
        spaceBefore=12, spaceAfter=6, fontName=_font(True)
    )
    small_style = ParagraphStyle(
        "Small", parent=styles["Normal"],
        fontSize=8, textColor=C_MUTED, leading=12, fontName=_font()
    )

    story.append(Paragraph("Puyad Kalkanı", title_style))
    story.append(Paragraph("Linux Güvenlik Sıkılaştırma Raporu", sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=10))

    info_data = [
        ["Rapor Tarihi", report_date, "Sistem", hostname],
        ["İşletim Sistemi", os_info, "Standart", "CIS Benchmark / NIST"],
        ["Taranan Kural", str(scan.get("total", 0)), "Düzeltilen", str(len([f for f in fixes if f["status"] == "success"]))],
    ]
    info_table = Table(info_data, colWidths=[3.5 * cm, 6 * cm, 3.5 * cm, 5 * cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_CARD),
        ("TEXTCOLOR", (0, 0), (0, -1), C_MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), C_MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), C_TEXT),
        ("TEXTCOLOR", (3, 0), (3, -1), C_TEXT),
        ("FONTNAME", (0, 0), (0, -1), _font(True)),
        ("FONTNAME", (2, 0), (2, -1), _font(True)),
        ("FONTNAME", (1, 0), (1, -1), _font()),
        ("FONTNAME", (3, 0), (3, -1), _font()),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_CARD, colors.HexColor("#1e2235")]),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Güvenlik Skoru", section_style))

    score_data = [[
        Paragraph(f"<font name='{_font()}' size='32' color='#{_score_color(score).hexval()[2:]}'><b>{score}</b></font>", styles["Normal"]),
        Paragraph(
            f"<b>Durum: {_score_label(score)}</b><br/>"
            f"Guvenli Kural: {scan.get('ok_count', 0)}<br/>"
            f"Uyari: {scan.get('warnings', 0)}<br/>"
            f"Toplam: {scan.get('total', 0)}",
            body_style
        ),
        _build_score_gauge(score, width=220, height=40)
    ]]
    score_table = Table(score_data, colWidths=[2.5 * cm, 5 * cm, 10 * cm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_CARD),
        ("GRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 12))

    if scan_results:
        story.append(Paragraph("Kural Tarama Sonuçları", section_style))

        result_data = [["#", "Kural Adı", "Durum"]]
        for i, r in enumerate(scan_results, 1):
            status_text = "✓ Güvenli" if r["status"] == "ok" else "✗ Uyarı"
            result_data.append([
                str(i),
                r.get("rule_name", r.get("rule_id", "-"))[:60],
                status_text
            ])

            result_table = Table(result_data, colWidths=[1 * cm, 14 * cm, 3 * cm])
        result_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_BORDER),
            ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
            ("FONTNAME", (0, 0), (-1, 0), _font(True)),
            ("FONTNAME", (0, 1), (-1, -1), _font()),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_CARD, colors.HexColor("#1e2235")]),
            ("TEXTCOLOR", (0, 1), (-1, -1), C_TEXT),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ]))

        for i, r in enumerate(scan_results, 1):
            color = C_GREEN if r["status"] == "ok" else C_RED
            result_table.setStyle(TableStyle([
                ("TEXTCOLOR", (2, i), (2, i), color),
            ]))

        story.append(result_table)
        story.append(Spacer(1, 12))

    if fixes:
        story.append(Paragraph("Son Düzeltme İşlemleri", section_style))

        fix_data = [["Tarih", "Kural", "Durum"]]
        for f in fixes[:15]:
            dt = f.get("created_at", "-")
            if dt and dt != "-":
                try:
                    dt = datetime.fromisoformat(dt).strftime("%d.%m.%Y %H:%M")
                except Exception:
                    pass
            fix_data.append([
                dt,
                f.get("rule_name", "-")[:55],
                "✓ Başarılı" if f["status"] == "success" else "✗ Başarısız"
            ])

        fix_table = Table(fix_data, colWidths=[3.5 * cm, 12 * cm, 2.5 * cm])
        fix_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_BORDER),
            ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
            ("FONTNAME", (0, 0), (-1, 0), _font(True)),
            ("FONTNAME", (0, 1), (-1, -1), _font()),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_CARD, colors.HexColor("#1e2235")]),
            ("TEXTCOLOR", (0, 1), (-1, -1), C_TEXT),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ]))
        for i, f in enumerate(fixes[:15], 1):
            color = C_GREEN if f["status"] == "success" else C_RED
            fix_table.setStyle(TableStyle([("TEXTCOLOR", (2, i), (2, i), color)]))

        story.append(fix_table)
        story.append(Spacer(1, 12))

    if len(trend) >= 2:
        story.append(Paragraph("Güvenlik Skoru Trendi", section_style))
        trend_data = [["Tarama", "Tarih", "Skor", "Durum"]]
        for i, t in enumerate(trend, 1):
            dt = t.get("created_at", "-")
            try:
                dt = datetime.fromisoformat(dt).strftime("%d.%m.%Y %H:%M")
            except Exception:
                pass
            trend_data.append([
                f"#{i}",
                dt,
                str(t["score"]),
                _score_label(t["score"])
            ])

        trend_table = Table(trend_data, colWidths=[1.5 * cm, 5 * cm, 2 * cm, 3 * cm])
        trend_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_BORDER),
            ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
            ("FONTNAME", (0, 0), (-1, 0), _font(True)),
            ("FONTNAME", (0, 1), (-1, -1), _font()),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_CARD, colors.HexColor("#1e2235")]),
            ("TEXTCOLOR", (0, 1), (-1, -1), C_TEXT),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(trend_table)
        story.append(Spacer(1, 12))

    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceBefore=8))
    story.append(Paragraph(
        f"Bu rapor Puyad Kalkanı v2.1.0 tarafından {report_date} tarihinde otomatik olarak oluşturulmuştur. "
        "CIS Benchmark ve NIST standartlarına göre değerlendirilmiştir.",
        small_style
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
