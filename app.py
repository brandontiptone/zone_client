import streamlit as st
import re
import io
from collections import defaultdict
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ── helpers ──────────────────────────────────────────────────────────────────

def parse_departments(raw: str) -> list[str]:
    """Split a department string by , / - or spaces, keep non-empty tokens."""
    parts = re.split(r"[,/\-\s]+", raw.strip())
    return [p.strip() for p in parts if p.strip()]


def parse_input(text: str) -> list[dict]:
    """
    Parse pasted data. Expected format per line:
        CLIENT_NAME  <tab or spaces>  TYPE  <tab or spaces>  DEPARTMENTS
    Returns a list of dicts with keys: client, type, departments.
    """
    rows = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Split on tabs first; fall back to 2+ spaces
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


def build_dept_table(rows: list[dict]) -> dict[str, list[str]]:
    """Return {department: [client1, client2, …]}."""
    dept_map = defaultdict(list)
    for row in rows:
        for d in row["departments"]:
            dept_map[d].append(row["client"])
    return dict(sorted(dept_map.items(), key=lambda x: x[0].zfill(3)))


def build_client_table(rows: list[dict]) -> dict[str, list[str]]:
    """Return {client: [dept1, dept2, …]}."""
    client_map = defaultdict(list)
    for row in rows:
        for d in row["departments"]:
            if d not in client_map[row["client"]]:
                client_map[row["client"]].append(d)
    return dict(sorted(client_map.items()))


# ── PDF generation ────────────────────────────────────────────────────────────

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

    # ── colour palette ────────────────────────────────────────────────────────
    HDR_BG   = colors.HexColor("#1a3c5e")   # dark navy
    HDR_FG   = colors.white
    ROW_ALT  = colors.HexColor("#eaf2fb")   # light blue
    ROW_EVEN = colors.white
    GRID     = colors.HexColor("#b0c4de")

    def make_table(data, col_widths, col_headers):
        header_row = [Paragraph(f"<b>{h}</b>", ParagraphStyle(
            "hdr", parent=cell_style, textColor=HDR_FG, alignment=TA_CENTER
        )) for h in col_headers]

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
            ("ROWBACKGROUND", (0, 1), (-1, -1), [ROW_EVEN, ROW_ALT]),
            ("LEFTPADDING",  (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            *row_bg,
        ]))
        return t

    story = []

    # ── Title ─────────────────────────────────────────────────────────────────
    story.append(Paragraph("Rapport – Clients & Zones Départementales", title_style))
    story.append(Spacer(1, 0.3*cm))

    # ── Table 1 : clients + their departments ─────────────────────────────────
    story.append(Paragraph("1. Récapitulatif par Client", sub_style))

    client_data = []
    for row in rows:
        depts_sorted = sorted(row["departments"], key=lambda x: x.zfill(3))
        client_data.append([
            row["client"],
            row["type"],
            len(depts_sorted),
            ", ".join(depts_sorted),
        ])

    W = landscape(A4)[0] - 3*cm
    t1 = make_table(
        client_data,
        col_widths=[W*0.25, W*0.08, W*0.07, W*0.60],
        col_headers=["Client", "Type", "Nb dépts", "Départements"],
    )
    story.append(t1)
    story.append(Spacer(1, 0.5*cm))

    # ── Table 2 : department → clients ────────────────────────────────────────
    story.append(Paragraph("2. Récapitulatif par Département", sub_style))

    dept_map = build_dept_table(rows)
    dept_data = []
    for dept, clients in dept_map.items():
        dept_data.append([dept, len(clients), ", ".join(sorted(clients))])

    t2 = make_table(
        dept_data,
        col_widths=[W*0.10, W*0.10, W*0.80],
        col_headers=["Département", "Nb clients", "Clients"],
    )
    story.append(t2)
    story.append(Spacer(1, 0.5*cm))

    # ── Table 3 : department × client matrix (pivot) ──────────────────────────
    story.append(Paragraph("3. Matrice Département × Client (aperçu – max 30 clients)", sub_style))

    all_clients = [r["client"] for r in rows][:30]
    all_depts   = sorted(dept_map.keys(), key=lambda x: x.zfill(3))

    client_set_map = {r["client"]: set(r["departments"]) for r in rows}

    matrix_header = ["Dépt"] + all_clients
    matrix_data   = []
    for dept in all_depts:
        r = [dept]
        for c in all_clients:
            r.append("✓" if dept in client_set_map.get(c, set()) else "")
        matrix_data.append(r)

    # dynamic col widths for matrix
    n_cols   = len(all_clients) + 1
    dept_w   = 1.2*cm
    cell_w   = max(0.7*cm, (W - dept_w) / max(len(all_clients), 1))

    mat_cell = ParagraphStyle(
        "matcell", parent=cell_style, fontSize=7, alignment=TA_CENTER
    )
    hdr_cell = ParagraphStyle(
        "mathdr", parent=cell_style, fontSize=6.5,
        textColor=HDR_FG, alignment=TA_CENTER
    )

    mat_rows  = [[Paragraph(str(v), hdr_cell) for v in matrix_header]]
    for row in matrix_data:
        mat_rows.append([Paragraph(str(v), mat_cell) for v in row])

    t3 = Table(mat_rows, colWidths=[dept_w] + [cell_w]*len(all_clients), repeatRows=1)

    row_bg3 = []
    for i in range(1, len(mat_rows)):
        bg = ROW_ALT if i % 2 == 0 else ROW_EVEN
        row_bg3.append(("BACKGROUND", (0, i), (-1, i), bg))

    t3.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), HDR_BG),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",         (0, 0), (-1, -1), 0.3, GRID),
        ("FONTSIZE",     (0, 1), (-1, -1), 7),
        ("LEFTPADDING",  (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING",   (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
        ("TEXTCOLOR",    (0, 1), (0, -1), colors.HexColor("#1a3c5e")),
        ("FONTNAME",     (0, 1), (0, -1), "Helvetica-Bold"),
        *row_bg3,
    ]))
    story.append(t3)

    doc.build(story)
    return buf.getvalue()


# ── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Clients & Zones", layout="wide")

st.title("📋 Gestionnaire Clients / Zones Départementales")
st.markdown(
    "Collez vos données ci-dessous au format **`CLIENT\\tTYPE\\tDÉPARTEMENTS`** "
    "(tabulations ou espaces multiples comme séparateur de colonnes ; "
    "virgules, `/` ou `-` pour séparer les départements)."
)

# ── Editable default data ──────────────────────────────────────────────────────
DEFAULT = """\
HA2\tPV\t89,45,28,41
EB\tPV\t71,58,89,21,39,70,25,90
RR\tPV\t24/46
YT1\tPV\t28/61/53/35/44/49/72/37/86/79/85/36/18/41/28/45
YT2\tPV\t22-29-56-35
VER\tPV\t44-49-85-53-72-79-86
ZC GLOBAL\tPV\t49,35,72,53
ZC1\tPV\t32,65,31,09,11
ZC2\tPV\t19,23,87,24
ZC3\tPV\t81,12,37,41,36,18, 85,44,26, 07, 38, 70,25,90, 15, 63, 43, 03
ZC4\tPV\t70,25,90
ZC5\tPV\t85,44
ZC6\tPV\t36,18, 37,41
SI\tPV\t26,07,38
SI PAC\tPV\t15,63,43,03
SH\tPV\t81,12
OR\tPV\t46,12,81,82
HA PAC\tPV\t40,32, 64, 65
ELUX\tPV\t54,55,57,88,51,52
IG1\tPV\t15 / 12 / 48 / 43
IG2\tPV\t38,01,83,04
ET1\tPV\t31, 66, 09, 11, 34, 30, 48
AV1\tPV\t76,80,72,53,29,22,56,28,45
AV2\tPV\t55,08
AR2 (SOL + VER)\tPV\t31,81,82,09,11,66,32
AR3\tPV\t30,34,84
EL\tPV\t67,68,88
RN\tPV\t57,54,70,88,90,67,68
ELIE PV  1\tPV\t29,22,35,56,44
ELIE PV  2\tPV\t85,79,86,17,16,49
BL\tPV\t16 17 33 64 65 40 47 32
ACV PV 1\tPV\t32 , 65 , 31 , 09 , 11
ACV PV 2\tPV\t32, 33, 40, 47, 82"""

raw = st.text_area("📥 Données clients", value=DEFAULT, height=320)

if st.button("🔍 Analyser & Générer le PDF", type="primary"):
    rows = parse_input(raw)

    if not rows:
        st.error("Aucune donnée valide trouvée. Vérifiez le format.")
        st.stop()

    # ── Summary metrics ────────────────────────────────────────────────────────
    dept_map   = build_dept_table(rows)
    client_map = build_client_table(rows)

    col1, col2, col3 = st.columns(3)
    col1.metric("👤 Clients", len(rows))
    col2.metric("🗺️ Départements uniques", len(dept_map))
    col3.metric("📌 Affectations totales", sum(len(r["departments"]) for r in rows))

    st.divider()

    # ── Tab layout ─────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["Par Client", "Par Département", "Matrice"])

    with tab1:
        st.subheader("Récapitulatif par Client")
        for row in rows:
            depts = sorted(row["departments"], key=lambda x: x.zfill(3))
            st.markdown(
                f"**{row['client']}** ({row['type']}) — "
                f"{len(depts)} dépt(s) : `{'  ·  '.join(depts)}`"
            )

    with tab2:
        st.subheader("Récapitulatif par Département")
        for dept, clients in dept_map.items():
            st.markdown(f"**Dept {dept}** — {len(clients)} client(s) : `{'  ·  '.join(sorted(clients))}`")

    with tab3:
        st.subheader("Matrice Département × Client")
        all_clients = [r["client"] for r in rows]
        client_set  = {r["client"]: set(r["departments"]) for r in rows}
        all_depts   = sorted(dept_map.keys(), key=lambda x: x.zfill(3))

        import pandas as pd
        matrix = {}
        for dept in all_depts:
            matrix[dept] = {c: "✓" if dept in client_set.get(c, set()) else "" for c in all_clients}
        df = pd.DataFrame(matrix).T
        df.index.name = "Dept"
        st.dataframe(df, use_container_width=True)

    st.divider()

    # ── PDF download ────────────────────────────────────────────────────────────
    with st.spinner("Génération du PDF…"):
        pdf_bytes = generate_pdf(rows)

    st.download_button(
        label="📄 Télécharger le rapport PDF",
        data=pdf_bytes,
        file_name="rapport_clients_zones.pdf",
        mime="application/pdf",
        type="primary",
    )
    st.success("✅ PDF prêt à télécharger !")
