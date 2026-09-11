"""Utility to generate a rich multimodal enterprise PDF with text, tables, and charts."""

import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_enterprise_report(output_path: Path):
    """Generates a professional 3-page enterprise PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_path.parent / "temp_charts"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate Segment Growth Chart (Matplotlib)
    chart1_path = temp_dir / "segment_growth_chart.png"
    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=150)
    years = ["FY2024", "FY2025", "FY2026"]
    cloud = [31.2, 42.0, 58.5]
    hardware = [28.0, 30.1, 31.4]
    software = [26.2, 30.2, 34.7]

    x = range(len(years))
    width = 0.25
    ax.bar([p - width for p in x], cloud, width=width, label="Cloud & AI", color="#4285F4")
    ax.bar(x, hardware, width=width, label="Hardware Systems", color="#34A853")
    ax.bar([p + width for p in x], software, width=width, label="Enterprise Software", color="#FBBC05")

    ax.set_ylabel("Revenue ($ Billions)")
    ax.set_title("Alphabetical Enterprise Group: Revenue by Segment (FY2024 - FY2026)", fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.legend(frameon=True, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(chart1_path)
    plt.close()

    # 2. Generate CapEx Allocation Donut Chart (Matplotlib)
    chart2_path = temp_dir / "capex_allocation_chart.png"
    fig, ax = plt.subplots(figsize=(6.0, 3.0), dpi=150)
    categories = ["AI GPU Clusters ($19.2B)", "Network & Fiber ($5.8B)", "Green Energy ($3.5B)"]
    sizes = [19.2, 5.8, 3.5]
    colors_list = ["#4285F4", "#EA4335", "#34A853"]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=categories, autopct="%1.1f%%",
        startangle=140, colors=colors_list, pctdistance=0.75,
        textprops=dict(color="black", fontsize=9)
    )
    centre_circle = plt.Circle((0, 0), 0.50, fc="white")
    ax.add_artist(centre_circle)
    ax.set_title("FY2026 Capital Expenditures ($28.5 Billion Total)", fontsize=11, fontweight="bold")
    plt.tight_layout()
    plt.savefig(chart2_path)
    plt.close()

    # 3. Assemble PDF using ReportLab
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1A73E8"),
        spaceAfter=8,
    )
    h2_style = ParagraphStyle(
        "Heading2",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#202124"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#3C4043"),
        spaceAfter=8,
    )

    story = []

    # Page 1: Overview and Financial Summary Table
    story.append(Paragraph("Alphabetical Enterprise Group", title_style))
    story.append(Paragraph("<b>Annual Operational and Financial Performance Report (Fiscal Year 2026)</b>", h2_style))
    story.append(Paragraph(
        "Alphabetical Enterprise Group delivered outstanding financial performance in fiscal year 2026. "
        "Consolidated total operating revenue expanded to <b>$124.6 billion</b>, representing a <b>21.8% year-over-year increase</b>. "
        "Operating margins expanded by 110 basis points to reach <b>29.1%</b>, while consolidated net income climbed to <b>$29.8 billion</b>.",
        body_style,
    ))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Table 1: Consolidated Financial Performance (FY2024 - FY2026)</b>", h2_style))

    table1_data = [
        ["Financial Metric", "FY2024", "FY2025", "FY2026", "YoY Growth"],
        ["Total Operating Revenue", "$85.4 B", "$102.3 B", "$124.6 B", "+21.8%"],
        ["Cloud & AI Infrastructure", "$31.2 B", "$42.0 B", "$58.5 B", "+39.3%"],
        ["Hardware Systems", "$28.0 B", "$30.1 B", "$31.4 B", "+4.3%"],
        ["Enterprise Software", "$26.2 B", "$30.2 B", "$34.7 B", "+14.9%"],
        ["Operating Income", "$22.1 B", "$28.6 B", "$36.2 B", "+26.6%"],
        ["Operating Margin", "25.9%", "28.0%", "29.1%", "+110 bps"],
        ["Net Income", "$17.8 B", "$23.1 B", "$29.8 B", "+29.0%"],
    ]
    t1 = Table(table1_data, colWidths=[160, 80, 80, 80, 90])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A73E8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8F9FA")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DADCE0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F3F4")]),
    ]))
    story.append(t1)

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "<b>Strategic Growth Commentary:</b> Cloud & AI Infrastructure represented 46.9% of consolidated net revenue, "
        "growing at 39.3% year-over-year. The hardware segment maintained single-digit resilience, while software margins broadened.",
        body_style,
    ))

    story.append(PageBreak())

    # Page 2: Segment Breakdown and Chart
    story.append(Paragraph("Segment Revenue Performance & Visual Progression", title_style))
    story.append(Paragraph(
        "Figure 1 illustrates the comparative revenue trajectory across our three principal reporting business segments. "
        "Cloud & AI Infrastructure has scaled from $31.2 billion in FY2024 to $58.5 billion in FY2026.",
        body_style,
    ))
    story.append(Spacer(1, 8))
    story.append(RLImage(str(chart1_path), width=500, height=240))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Figure 1: Revenue Trajectory by Business Segment (FY2024 - FY2026).</b> "
        "The accelerating slope of Cloud & AI reflects substantial multi-year commitments from global enterprise customers.",
        body_style,
    ))

    story.append(PageBreak())

    # Page 3: CapEx Breakdown and Risk Outlook
    story.append(Paragraph("Capital Expenditure Allocation & Strategic Risk Factors", title_style))
    story.append(Paragraph(
        "To support exponential computing demand, Alphabetical Enterprise Group increased capital deployment to <b>$28.5 billion</b> in FY2026. "
        "The pie chart below details the strategic capital distribution across compute, optical networking, and sustainable energy.",
        body_style,
    ))
    story.append(Spacer(1, 6))
    story.append(RLImage(str(chart2_path), width=460, height=220))
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Table 2: FY2026 Capital Allocation Breakdown</b>", h2_style))
    table2_data = [
        ["Investment Category", "FY2025 Spent", "FY2026 Allocated", "Primary Focus"],
        ["AI GPU Clusters & Datacenters", "$12.5 B", "$19.2 B", "High-density compute buildouts"],
        ["Network & Dark Fiber Backbone", "$4.2 B", "$5.8 B", "Inter-datacenter throughput"],
        ["Green Energy & Clean Power", "$2.1 B", "$3.5 B", "24/7 carbon-free operations"],
        ["Total Capital Deployments", "$18.8 B", "$28.5 B", "Multi-region capacity expansion"],
    ]
    t2 = Table(table2_data, colWidths=[160, 85, 95, 160])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34A853")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8F9FA")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DADCE0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F3F4")]),
    ]))
    story.append(t2)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Identified Risk Factors:</b> Silicon supply chain bottlenecks, specialized high-bandwidth memory lead times, "
        "and electrical power grid interconnection schedules remain primary headwinds to rapid delivery.",
        body_style,
    ))

    # Build document
    doc.build(story)
    print(f"Generated enterprise PDF at: {output_path}")


if __name__ == "__main__":
    target = Path("data/raw/alphabetical_corp_2026_10k.pdf")
    generate_enterprise_report(target)
