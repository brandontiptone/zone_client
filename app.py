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

# ── helpers ───────────────────────────────────────────────────────────────────

def parse_departments(raw: str) -> list[str]:
    parts = re.split(r"[,/\-\s]+", raw.strip())
    return [p.strip() for p in parts if p.strip()]


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
        depts  = parse_departments(parts[2].strip())
        if client and depts:
            rows.append({"client": client, "type": typ, "departments": depts})
    return rows


def sort_dept_key(d):
    return d.zfill(3)


def build_dept_table(rows):
    dept_map = defaultdict(list)
    for row in rows:
        for d in row["departments"]:
            dept_map[d].append(row["client"])
    return dict(sorted(dept_map.items(), key=lambda x: sort_dept_key(x[0])))


def build_zone_groups(rows):
    """Group clients that share the exact same set of departments."""
    map_ = {}
    for row in rows:
        sorted_depts = sorted(row["departments"], key=sort_dept_key)
        key = "-".join(sorted_depts)
        label = ", ".join(sorted_depts)
        if key not in map_:
            map_[key] = {"zone_label": label, "depts": sorted_depts, "clients": [], "nb_depts": len(sorted_depts)}
        map_[key]["clients"].append(row["client"])
    result = sorted(map_.values(), key=lambda x: -len(x["clients"]))
    for g in result:
        g["nb_clients"] = len(g["clients"])
    return result


# ── PDF generation ────────────────────────────────────────────────────────────

HDR_BG   = colors.HexColor("#1a3c5e")
HDR_FG   = colors.white
ROW_ALT  = colors.HexColor("#eaf2fb")
ROW_EVEN = colors.white
GRID     = colors.HexColor("#b0c4de")


def make_table(data, col_widths, col_headers, cell_style):
    hdr_para_style = ParagraphStyle(
        "hdr", parent=cell_style, textColor=HDR_FG, alignment=TA_CENTER
    )
    header_row = [Paragraph(f"<b>{h}</b>", hdr_para_style) for h in col_headers]
    table_data = [header_row]
    for r in data:
        table_data.append([Paragraph(str(c), cell_style) for c in r])

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    row_bg = []
    for i in range(1, len(table_data)):
        bg = ROW_ALT if i % 2 == 0 else ROW_EVEN
        row_bg.append(("BACKGROUND", (0, i), (-1, i), bg))

    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), HDR_BG),
        ("TEXTCOLOR",   (0, 0), (-1, 0), HDR_FG),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 9),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("GRID",        (0, 0), (-1, -1), 0.4, GRID),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        *row_bg,
    ]))
    return t


def generate_pdf(rows: list[dict]) -> bytes:
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
    sub_style = ParagraphStyle(
        "sub", parent=styles["Heading2"],
        fontSize=12, spaceBefore=16, spaceAfter=6
    )
    cell_style = ParagraphStyle(
        "cell", parent=styles["Normal"],
        fontSize=8, leading=11
    )
    cell_center = ParagraphStyle(
        "cellc", parent=cell_style, alignment=TA_CENTER
    )

    W = landscape(A4)[0] - 3*cm
    story = []

    story.append(Paragraph("Rapport – Groupes de Zones Départementales", title_style))
    story.append(Spacer(1, 0.3*cm))

    # ── Table 1 : Zone groups ─────────────────────────────────────────────────
    story.append(Paragraph("1. Groupes de Zones (clients avec les mêmes départements)", sub_style))

    zone_groups = build_zone_groups(rows)
    zone_data = []
    for g in zone_groups:
        zone_data.append([
            str(g["nb_clients"]),
            str(g["nb_depts"]),
            g["zone_label"],
            ", ".join(sorted(g["clients"])),
        ])

    t1 = make_table(
        zone_data,
        col_widths=[W*0.07, W*0.07, W*0.52, W*0.34],
        col_headers=["Nb clients", "Nb depts", "Départements (zone)", "Clients"],
        cell_style=cell_style,
    )
    story.append(t1)
    story.append(Spacer(1, 0.5*cm))

    # ── Table 2 : clients + their departments ─────────────────────────────────
    story.append(Paragraph("2. Récapitulatif par Client", sub_style))

    client_data = []
    for row in rows:
        depts_sorted = sorted(row["departments"], key=sort_dept_key)
        client_data.append([
            row["client"],
            row["type"],
            str(len(depts_sorted)),
            ", ".join(depts_sorted),
        ])

    t2 = make_table(
        client_data,
        col_widths=[W*0.20, W*0.07, W*0.07, W*0.66],
        col_headers=["Client", "Type", "Nb depts", "Départements"],
        cell_style=cell_style,
    )
    story.append(t2)
    story.append(Spacer(1, 0.5*cm))

    # ── Table 3 : department → clients ────────────────────────────────────────
    story.append(Paragraph("3. Récapitulatif par Département", sub_style))

    dept_map = build_dept_table(rows)
    dept_data = []
    for dept, clients in dept_map.items():
        unique_clients = sorted(set(clients))
        dept_data.append([dept, str(len(unique_clients)), ", ".join(unique_clients)])

    t3 = make_table(
        dept_data,
        col_widths=[W*0.10, W*0.10, W*0.80],
        col_headers=["Département", "Nb clients", "Clients"],
        cell_style=cell_style,
    )
    story.append(t3)

    doc.build(story)
    return buf.getvalue()


# ── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Clients & Zones", layout="wide", page_icon="🗺️")

st.title("🗺️ Gestionnaire Clients / Zones Départementales")
st.markdown(
    "Collez vos données au format **`CLIENT [tab] TYPE [tab] DÉPARTEMENTS`**  \n"
    "Séparateurs de départements acceptés : `,` `/` `-` ou espaces."
)

raw = st.text_area(
    "📥 Données clients",
    height=280,
    placeholder="HA2\tPV\t89,45,28,41\nEB\tPV\t71,58,89,21,39,70,25,90\n..."
)

col_btn1, col_btn2 = st.columns([1, 5])
with col_btn1:
    run = st.button("🔍 Analyser", type="primary", use_container_width=True)

if run:
    if not raw.strip():
        st.error("Veuillez coller des données avant d'analyser.")
        st.stop()

    rows = parse_input(raw)

    if not rows:
        st.error("Aucune donnée valide trouvée. Vérifiez le format.")
        st.stop()

    dept_map    = build_dept_table(rows)
    zone_groups = build_zone_groups(rows)

    # ── Metrics ────────────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👤 Clients", len(rows))
    m2.metric("🗺️ Départements uniques", len(dept_map))
    m3.metric("📌 Affectations totales", sum(len(r["departments"]) for r in rows))
    m4.metric("🔗 Groupes de zones", len(zone_groups))

    st.divider()

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["🔗 Groupes de Zones", "👤 Par Client", "📍 Par Département"])

    # ── TAB 1 : ZONE GROUPS ────────────────────────────────────────────────────
    with tab1:
        st.subheader("Groupes de zones — clients partageant les mêmes départements")
        st.caption("Trié par nombre de clients décroissant. Chaque ligne = un groupe unique de départements.")

        search_zone = st.text_input("🔎 Filtrer par département ou client", key="sz")

        zone_rows = []
        for g in zone_groups:
            clients_str = ", ".join(sorted(g["clients"]))
            if search_zone:
                s = search_zone.lower()
                if s not in g["zone_label"].lower() and s not in clients_str.lower():
                    continue
            zone_rows.append({
                "Nb clients": g["nb_clients"],
                "Nb depts": g["nb_depts"],
                "Départements (zone)": g["zone_label"],
                "Clients": clients_str,
            })

        if zone_rows:
            df_zones = pd.DataFrame(zone_rows)
            st.dataframe(
                df_zones,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Nb clients": st.column_config.NumberColumn(width="small"),
                    "Nb depts":   st.column_config.NumberColumn(width="small"),
                    "Départements (zone)": st.column_config.TextColumn(width="large"),
                    "Clients": st.column_config.TextColumn(width="large"),
                }
            )
        else:
            st.info("Aucun groupe trouvé pour ce filtre.")

        st.divider()
        st.subheader("Détail par groupe")
        for g in zone_groups:
            clients_str = ", ".join(sorted(g["clients"]))
            if search_zone:
                s = search_zone.lower()
                if s not in g["zone_label"].lower() and s not in clients_str.lower():
                    continue
            label = f"**{g['nb_clients']} client(s)** — `{g['zone_label']}` ({g['nb_depts']} depts)"
            with st.expander(label):
                for c in sorted(g["clients"]):
                    st.markdown(f"• {c}")

    # ── TAB 2 : PAR CLIENT ─────────────────────────────────────────────────────
    with tab2:
        st.subheader("Récapitulatif par Client")
        search_client = st.text_input("🔎 Filtrer par client ou département", key="sc")

        client_rows = []
        for row in rows:
            depts_sorted = sorted(row["departments"], key=sort_dept_key)
            depts_str = ", ".join(depts_sorted)
            if search_client:
                s = search_client.lower()
                if s not in row["client"].lower() and s not in depts_str.lower():
                    continue
            client_rows.append({
                "Client": row["client"],
                "Type": row["type"],
                "Nb depts": len(depts_sorted),
                "Départements": depts_str,
            })

        if client_rows:
            df_clients = pd.DataFrame(client_rows)
            st.dataframe(df_clients, use_container_width=True, hide_index=True,
                column_config={
                    "Nb depts": st.column_config.NumberColumn(width="small"),
                    "Départements": st.column_config.TextColumn(width="large"),
                })
        else:
            st.info("Aucun client trouvé pour ce filtre.")

    # ── TAB 3 : PAR DÉPARTEMENT ────────────────────────────────────────────────
    with tab3:
        st.subheader("Récapitulatif par Département")
        search_dept = st.text_input("🔎 Filtrer par département ou client", key="sd")

        dept_rows = []
        for dept, clients in dept_map.items():
            unique = sorted(set(clients))
            clients_str = ", ".join(unique)
            if search_dept:
                s = search_dept.lower()
                if s not in dept.lower() and s not in clients_str.lower():
                    continue
            dept_rows.append({
                "Département": dept,
                "Nb clients": len(unique),
                "Clients": clients_str,
            })

        if dept_rows:
            df_depts = pd.DataFrame(dept_rows)
            st.dataframe(df_depts, use_container_width=True, hide_index=True,
                column_config={
                    "Département": st.column_config.TextColumn(width="small"),
                    "Nb clients": st.column_config.NumberColumn(width="small"),
                    "Clients": st.column_config.TextColumn(width="large"),
                })
        else:
            st.info("Aucun département trouvé pour ce filtre.")

    st.divider()

    # ── PDF Export ─────────────────────────────────────────────────────────────
    with st.spinner("Génération du PDF…"):
        pdf_bytes = generate_pdf(rows)

    st.download_button(
        label="📄 Télécharger le rapport PDF",
        data=pdf_bytes,
        file_name="rapport_clients_zones.pdf",
        mime="application/pdf",
        type="primary",
    )
    st.success("✅ Analyse terminée — PDF prêt à télécharger !")
