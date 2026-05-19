import streamlit as st
import re
import io
from collections import defaultdict
import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ── Référentiel régions → départements ───────────────────────────────────────

REGIONS = {
    "Île-de-France":              ["75","77","78","91","92","93","94","95"],
    "Auvergne-Rhône-Alpes":       ["01","03","07","15","26","38","42","43","63","69","73","74"],
    "Bourgogne-Franche-Comté":    ["21","25","39","58","70","71","89","90"],
    "Bretagne":                   ["22","29","35","56"],
    "Centre-Val de Loire":        ["18","28","36","37","41","45"],
    "Corse":                      ["2A","2B"],
    "Grand Est":                  ["08","10","51","52","54","55","57","67","68","88"],
    "Hauts-de-France":            ["02","59","60","62","80"],
    "Normandie":                  ["14","27","50","61","76"],
    "Nouvelle-Aquitaine":         ["16","17","19","23","24","33","40","47","64","79","86","87"],
    "Occitanie":                  ["09","11","12","30","31","32","34","46","48","65","66","81","82"],
    "Pays de la Loire":           ["44","49","53","72","85"],
    "Provence-Alpes-Côte d'Azur": ["04","05","06","13","83","84"],
}

# Lookup inverse : dept → région
DEPT_TO_REGION = {}
for region, depts in REGIONS.items():
    for d in depts:
        DEPT_TO_REGION[d] = region

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_departments(raw: str) -> list[str]:
    parts = re.split(r"[,/\-\s]+", raw.strip())
    result = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.upper() in ("2A", "2B"):
            result.append(p.upper())
        elif p.isdigit():
            result.append(p.zfill(2))
        else:
            result.append(p)
    return list(dict.fromkeys(result))


def parse_input(text: str) -> list[dict]:
    rows = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"\t+", line)
        if len(parts) < 3:
            parts = re.split(r"  +", line)
        if len(parts) < 3:
            st.warning(f"Ligne ignorée (format invalide) : `{line}`")
            continue
        client = parts[0].strip()
        typ    = parts[1].strip()
        depts  = parse_departments(" ".join(parts[2:]).strip())
        if client and depts:
            rows.append({"client": client, "type": typ, "departments": depts})
    return rows


def build_region_table(rows: list[dict]) -> list[dict]:
    region_clients = defaultdict(set)
    region_depts   = defaultdict(set)

    for row in rows:
        for d in row["departments"]:
            region = DEPT_TO_REGION.get(d)
            if region:
                region_clients[region].add(row["client"])
                region_depts[region].add(d)

    result = []
    for region in REGIONS:
        if region not in region_clients:
            continue
        depts_sorted   = sorted(region_depts[region], key=lambda x: x.zfill(3))
        clients_sorted = sorted(region_clients[region])
        result.append({
            "Région":            region,
            "Départements":      ", ".join(depts_sorted),
            "Nb depts":          len(depts_sorted),
            "Nb clients":        len(clients_sorted),
            "Clients concernés": ", ".join(clients_sorted),
        })
    return result


# ── PDF ───────────────────────────────────────────────────────────────────────

HDR_BG   = colors.HexColor("#1a3c5e")
HDR_FG   = colors.white
ROW_ALT  = colors.HexColor("#eaf2fb")
ROW_EVEN = colors.white
GRID     = colors.HexColor("#b0c4de")


def generate_pdf(region_rows: list[dict]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm,   bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Title"],
        fontSize=16, spaceAfter=12, alignment=TA_CENTER
    )
    cell_style = ParagraphStyle(
        "cell", parent=styles["Normal"], fontSize=8, leading=11
    )
    cell_center = ParagraphStyle(
        "cellc", parent=cell_style, alignment=TA_CENTER
    )
    hdr_style = ParagraphStyle(
        "hdr", parent=cell_style, textColor=HDR_FG, alignment=TA_CENTER
    )

    W = landscape(A4)[0] - 3*cm
    col_headers = ["Région", "Départements", "Nb\ndepts", "Nb\nclients", "Clients concernés"]
    col_widths  = [W*0.17, W*0.28, W*0.06, W*0.06, W*0.43]

    header_row = [Paragraph(f"<b>{h}</b>", hdr_style) for h in col_headers]
    table_data = [header_row]

    for i, r in enumerate(region_rows):
        table_data.append([
            Paragraph(r["Région"],            cell_style),
            Paragraph(r["Départements"],      cell_style),
            Paragraph(str(r["Nb depts"]),     cell_center),
            Paragraph(str(r["Nb clients"]),   cell_center),
            Paragraph(r["Clients concernés"], cell_style),
        ])

    row_bg = [
        ("BACKGROUND", (0, i+1), (-1, i+1), ROW_ALT if i % 2 == 0 else ROW_EVEN)
        for i in range(len(region_rows))
    ]

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), HDR_BG),
        ("TEXTCOLOR",    (0, 0), (-1, 0), HDR_FG),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0), 9),
        ("ALIGN",        (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("GRID",         (0, 0), (-1, -1), 0.4, GRID),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        *row_bg,
    ]))

    story = [
        Paragraph("Régions – Départements – Clients", title_style),
        Spacer(1, 0.4*cm),
        t,
    ]
    doc.build(story)
    return buf.getvalue()


# ── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Clients & Régions", layout="wide", page_icon="🗺️")

st.title("🗺️ Clients par Région & Département")
st.markdown(
    "Collez vos données au format **`CLIENT [tab] TYPE [tab] DÉPARTEMENTS`**  \n"
    "Séparateurs de départements : `,` `/` `-` ou espaces."
)

raw = st.text_area(
    "📥 Données clients",
    height=280,
    placeholder="HA2\tPV\t89,45,28,41\nEB\tPV\t71,58,89,21,39,70,25,90\n..."
)

if st.button("🔍 Analyser", type="primary"):
    if not raw.strip():
        st.error("Veuillez coller des données avant d'analyser.")
        st.stop()

    rows = parse_input(raw)
    if not rows:
        st.error("Aucune donnée valide trouvée.")
        st.stop()

    region_rows = build_region_table(rows)

    # ── Métriques ──────────────────────────────────────────────────────────────
    all_depts = set(d for r in rows for d in r["departments"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👤 Clients",             len(rows))
    m2.metric("🗺️ Départements uniques", len(all_depts))
    m3.metric("🏛️ Régions couvertes",    len(region_rows))
    m4.metric("📌 Affectations totales", sum(len(r["departments"]) for r in rows))

    st.divider()

    # ── Tableau principal ──────────────────────────────────────────────────────
    st.subheader("Régions – Départements – Clients")

    df = pd.DataFrame(region_rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Région":            st.column_config.TextColumn("Région",            width="medium"),
            "Départements":      st.column_config.TextColumn("Départements",      width="large"),
            "Nb depts":          st.column_config.NumberColumn("Nb depts",        width="small"),
            "Nb clients":        st.column_config.NumberColumn("Nb clients",      width="small"),
            "Clients concernés": st.column_config.TextColumn("Clients concernés", width="large"),
        }
    )

    st.divider()

    # ── Détail par région ──────────────────────────────────────────────────────
    st.subheader("Détail par région")
    for r in region_rows:
        with st.expander(f"**{r['Région']}** — {r['Nb clients']} client(s) · {r['Nb depts']} dept(s)"):
            c1, c2 = st.columns(2)
            c1.markdown(f"**Départements :** {r['Départements']}")
            c2.markdown(f"**Clients :** {r['Clients concernés']}")

    st.divider()

    # ── Export PDF ─────────────────────────────────────────────────────────────
    with st.spinner("Génération du PDF…"):
        pdf_bytes = generate_pdf(region_rows)

    st.download_button(
        label="📄 Télécharger le rapport PDF",
        data=pdf_bytes,
        file_name="rapport_regions_clients.pdf",
        mime="application/pdf",
        type="primary",
    )
    st.success("✅ Analyse terminée — PDF prêt !")
