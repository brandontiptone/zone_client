import streamlit as st
import io
import re
from collections import defaultdict
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm

st.set_page_config(page_title="Zones Partagées par Client", layout="wide")

st.title("🗺️ Zones Communes — Clients en concurrence")
st.markdown("Identifie quelles zones sont couvertes par plusieurs clients et lesquels.")

DEFAULT = """\
AS\tPV\t40,32,64,65
HA 1\tPV\t89,45,28,41
HA2\tPV\t71,58,89,21,39,70,25,90
EB\tPV\t24,46
RR\tPV\t28,61,53,35,44,49,72,37,86,79,85,36,18,41,28,45
YT1\tPV\t22,29,56,35
YT2\tPV\t44,49,85,53,72,79,86
AI\tPV\t49,35,72,53
ANL\tPV\t32,65,31,09,11
VER\tPV\t19,23,87,24
ZC GLOBAL\tPV\t81,12,37,41,36,18,85,44,26,07,38,70,25,90,15,63,43,03
ZC1\tPV\t70,25,90
ZC2\tPV\t85,44
ZC3\tPV\t36,18,37,41
ZC4\tPV\t26,07,38
ZC5\tPV\t15,63,43,03
ZC6\tPV\t81,12
SI\tPV\t46,12,81,82
SH\tPV\t54,55,57,88,51,52
OR\tPV\t15,12,48,43
FA\tPV\t38,01,83,04
EL\tPV\t31,66,09,11,34,30,48
IG1\tPV\t76,80,72,53,29,22,56,28,45
IG2\tPV\t55,08
ET1\tPV\t31,81,82,09,11,66,32
SIM\tPV\t30,34,84
AV1\tPV\t67,68,88
AV2\tPV\t57,54,70,88,90,67,68
RN\tPV\t24,47,66,11,09,64,65,87,23,19
DG\tPV\t11,34,31,82,81
LB\tPV\t85,79
AR2\tPV\t63,23,03
AR3\tPV\t53,72
NF\tPV\t60,80,02,28,45,27,76
ELIE PV 1\tPV\t29,22,35,56,44
ELIE PV 2\tPV\t85,79,86,17,16,49
BL\tPV\t16,17,33,64,65,40,47,32"""


def parse_lines(text):
    results = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            parts = [p.strip() for p in line.split("\t") if p.strip()]
        else:
            parts = re.split(r"\s{2,}", line)
            parts = [p.strip() for p in parts if p.strip()]
        if len(parts) < 2:
            continue
        if len(parts) == 2:
            client, zones = parts[0], parts[1]
        else:
            client = parts[0]
            zones = " ".join(parts[2:])
        dept_list = re.findall(r"\d{2}", zones)
        dept_list = [d.zfill(2) for d in dept_list]
        results.append((client, dept_list))
    return results


def compute_zone_map(rows):
    zone_clients = defaultdict(list)
    for client, depts in rows:
        for dept in depts:
            if client not in zone_clients[dept]:
                zone_clients[dept].append(client)
    return zone_clients


def build_pdf(zone_clients, titre):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=styles["Title"], fontSize=14,
                                  textColor=colors.HexColor("#1a3a5c"), spaceAfter=4,
                                  fontName="Helvetica-Bold")
    subtitle_style = ParagraphStyle("S", parent=styles["Normal"], fontSize=8,
                                     textColor=colors.HexColor("#555555"), spaceAfter=10)
    header_style = ParagraphStyle("H", parent=styles["Normal"], fontSize=9,
                                   fontName="Helvetica-Bold", textColor=colors.white, leading=12)
    cell_style = ParagraphStyle("C", parent=styles["Normal"], fontSize=8, leading=11)
    cell_center = ParagraphStyle("CC", parent=cell_style, alignment=1)

    sorted_zones = sorted(zone_clients.keys())

    header = [
        Paragraph("DÉPARTEMENT", header_style),
        Paragraph("NB CLIENTS", header_style),
        Paragraph("CLIENTS PRÉSENTS SUR CETTE ZONE", header_style),
    ]
    table_data = [header]

    for dept in sorted_zones:
        clients = zone_clients[dept]
        nb = len(clients)
        table_data.append([
            Paragraph(f"<b>{dept}</b>", cell_center),
            Paragraph(f"<b>{nb}</b>", cell_center),
            Paragraph(" • ".join(clients), cell_style),
        ])

    col_widths = [30 * mm, 28 * mm, 215 * mm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    row_styles = []
    for i, dept in enumerate(sorted_zones, start=1):
        nb = len(zone_clients[dept])
        if nb >= 5:
            bg = colors.HexColor("#f8d7da")
        elif nb >= 3:
            bg = colors.HexColor("#fff3cd")
        elif nb >= 2:
            bg = colors.HexColor("#d4edda")
        else:
            bg = colors.white if i % 2 == 0 else colors.HexColor("#f8f9fa")
        row_styles.append(("BACKGROUND", (0, i), (-1, i), bg))

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("ALIGN", (0, 0), (1, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0c4de")),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, colors.HexColor("#1a3a5c")),
    ] + row_styles))

    legend_style = ParagraphStyle("L", parent=styles["Normal"], fontSize=8,
                                   textColor=colors.HexColor("#555555"), spaceBefore=8)
    story = [
        Paragraph(titre, title_style),
        Paragraph("Nombre de clients présents par département — code couleur selon le niveau de concurrence", subtitle_style),
        table,
        Spacer(1, 6),
        Paragraph(
            "Rouge : 5 clients ou plus  |  Jaune : 3 ou 4 clients  |  Vert : 2 clients  |  Blanc/gris : 1 client",
            legend_style
        ),
    ]
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# ── UI ────────────────────────────────────────────────────────────────────────
raw_text = st.text_area("✏️ Données clients", value=DEFAULT, height=350)
titre_pdf = st.text_input("Titre du PDF", value="Zones Communes — Clients en concurrence (Campagnes PV)")

rows = parse_lines(raw_text)

if rows:
    zone_clients = compute_zone_map(rows)
    sorted_zones = sorted(zone_clients.keys())

    st.markdown(f"**{len(rows)} clients · {len(sorted_zones)} départements couverts**")

    col1, col2 = st.columns(2)
    with col1:
        min_clients = st.slider("Afficher les zones avec au moins X clients", 1, 10, 1)
    with col2:
        search_client = st.text_input("🔍 Filtrer par client", "")

    filtered = {
        dept: clients
        for dept, clients in zone_clients.items()
        if len(clients) >= min_clients
        and (not search_client or any(search_client.upper() in c.upper() for c in clients))
    }

    import pandas as pd
    df = pd.DataFrame([
        {"Département": dept, "Nb clients": len(clients), "Clients": " • ".join(clients)}
        for dept, clients in sorted(filtered.items())
    ])

    def color_rows(row):
        nb = row["Nb clients"]
        if nb >= 5:
            return ["background-color: #f8d7da"] * len(row)
        elif nb >= 3:
            return ["background-color: #fff3cd"] * len(row)
        elif nb >= 2:
            return ["background-color: #d4edda"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df.style.apply(color_rows, axis=1),
        use_container_width=True,
        hide_index=True,
        height=420,
    )

    st.markdown("🔴 5+ clients &nbsp;|&nbsp; 🟡 3-4 clients &nbsp;|&nbsp; 🟢 2 clients &nbsp;|&nbsp; ⬜ 1 client", unsafe_allow_html=True)

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    all_counts = [len(v) for v in zone_clients.values()]
    c1.metric("Depts couverts", len(zone_clients))
    c2.metric("1 seul client", sum(1 for x in all_counts if x == 1))
    c3.metric("2 à 4 clients", sum(1 for x in all_counts if 2 <= x <= 4))
    c4.metric("5+ clients", sum(1 for x in all_counts if x >= 5))

    st.divider()
    if st.button("🖨️ Générer le PDF (toutes les zones)", type="primary", use_container_width=True):
        with st.spinner("Génération…"):
            pdf_bytes = build_pdf(zone_clients, titre_pdf)
        st.success(f"✅ PDF généré — {len(zone_clients)} départements")
        st.download_button(
            label="⬇️ Télécharger le PDF",
            data=pdf_bytes,
            file_name="zones_concurrence.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
else:
    st.warning("Aucune donnée valide détectée.")
