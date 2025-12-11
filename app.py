import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import plotly.express as px
from openpyxl import load_workbook

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Pergamon Mini-Planer", layout="wide")
st.title("🕌 Pergamon Mini-Planer – Rollen, Personen, MP-Farben & Feiertage")

today = date.today()

st.markdown("""
Diese Version berücksichtigt:
- Personen & ihre Rollen  
- Multi-Rollen-Aufwand pro Film  
- BS-Start/Ende  
- MP-Kalender (Farbbalken → Person blockiert)  
- **Keine Wochenenden**  
- **Berliner Feiertage 2025/2026**  
""")


# ---------------------------------------------------------
# FEIERTAGE BERLIN 2025/2026
# ---------------------------------------------------------
BERLIN_HOLIDAYS = {
    2025: {
        date(2025, 1, 1),
        date(2025, 3, 8),
        date(2025, 4, 18),
        date(2025, 4, 21),
        date(2025, 5, 1),
        date(2025, 5, 8),
        date(2025, 5, 29),
        date(2025, 6, 9),
        date(2025, 10, 3),
        date(2025, 12, 25),
        date(2025, 12, 26)
    },
    2026: {
        date(2026, 1, 1),
        date(2026, 3, 8),
        date(2026, 4, 3),
        date(2026, 4, 6),
        date(2026, 5, 1),
        date(2026, 5, 14),
        date(2026, 5, 25),
        date(2026, 10, 3),
        date(2026, 12, 25),
        date(2026, 12, 26)
    }
}

def is_berlin_holiday(d: date) -> bool:
    return d in BERLIN_HOLIDAYS.get(d.year, set())


# ---------------------------------------------------------
# MP-KALENDER PER FARBE EINLESEN
# ---------------------------------------------------------
def load_mp_availability_by_color(mp_file, personen):
    wb = load_workbook(mp_file, data_only=True)
    ws = wb.active

    max_row = ws.max_row
    max_col = ws.max_column

    # Datumszeile finden
    date_row_idx = None
    best_count = -1
    for r in range(1, max_row + 1):
        c_count = 0
        for c in range(2, max_col + 1):
            if isinstance(ws.cell(row=r, column=c).value, datetime):
                c_count += 1
        if c_count > best_count:
            best_count = c_count
            date_row_idx = r

    if date_row_idx is None:
        return {}

    date_cols = {}
    for c in range(2, max_col + 1):
        v = ws.cell(row=date_row_idx, column=c).value
        if isinstance(v, datetime):
            date_cols[c] = v.date()

    def norm(s):
        return s.split(":")[0].strip().lower()

    person_colors = {}
    for r in range(1, 25):
        raw = ws.cell(row=r, column=1).value
        if isinstance(raw, str):
            nm = norm(raw)
            for p in personen:
                if nm == p.lower():
                    fill = ws.cell(row=r, column=2).fill
                    if fill and fill.fgColor and fill.fgColor.type != "indexed":
                        person_colors[p] = fill.fgColor.rgb

    availability = {}

    for c, d in date_cols.items():
        for r in range(1, max_row + 1):
            cell = ws.cell(row=r, column=c)
            fill = cell.fill
            rgb = None
            if fill and fill.fgColor and fill.fgColor.type != "indexed":
                rgb = fill.fgColor.rgb

            if not rgb:
                continue

            for p, pc in person_colors.items():
                if pc == rgb:
                    availability[(p, d)] = "Blockiert"

    return availability


# ---------------------------------------------------------
# 1) PERSONEN & ROLLEN
# ---------------------------------------------------------
st.subheader("1️⃣ Personen & Rollen")

# neue Default-Personen
personen_input = st.text_input(
    "Personen (Komma)",
    "Sonja, Mareike, Sophia, Ruta, Xenia, Anna"
)
personen = [p.strip() for p in personen_input.split(",") if p.strip()]

# neue Default-Rollen (inkl. Lead)
rollen_input = st.text_input(
    "Rollen (Komma)",
    "Storyboard, Keyframes, Animation, Lead"
)
rollen = [r.strip() for r in rollen_input.split(",") if r.strip()]

person_roles = {}
for p in personen:
    person_roles[p] = st.multiselect(
        f"Rollen von {p}",
        rollen,
        default=rollen
    )


# ---------------------------------------------------------
# 2) MP FILE
# ---------------------------------------------------------
st.subheader("2️⃣ MP-Kalender hochladen")
mp_file = st.file_uploader("MP.xlsx", type=["xlsx"])

mp_availability = {}
if mp_file:
    try:
        mp_availability = load_mp_availability_by_color(mp_file, personen)
        st.success("MP-Farben erfolgreich erkannt.")
    except Exception as e:
        st.error(f"Fehler beim MP-Parsing: {e}")


# ---------------------------------------------------------
# 3) FILME
# ---------------------------------------------------------
st.subheader("3️⃣ Filme definieren")

# bis zu 20 Filme, Default = 20
anz = st.number_input("Wie viele Filme?", 1, 20, 20)
filme = []

for i in range(anz):
    st.markdown(f"**Film {i+1}**")
    col1, col2, col3 = st.columns(3)

    name = col1.text_input(f"Name {i+1}", f"Film {i+1}")
    bs_start = col2.date_input(f"BS-Start {i+1}", today + timedelta(days=5))
    bs_end = col3.date_input(f"BS-Ende {i+1}", today + timedelta(days=25))

    role_days = {}
    cols = st.columns(len(rollen))
    for j, r in enumerate(rollen):
        role_days[r] = cols[j].number_input(
            f"{r} (Tage)",
            min_value=0,
            max_value=200,
            value=0,
            key=f"{i}_{r}"
        )

    filme.append({
        "Film": name,
        "BS_Start": bs_start,
        "BS_Ende": bs_end,
        "Role_Days": role_days
    })


# ---------------------------------------------------------
# 4) PARAMETER
# ---------------------------------------------------------
st.subheader("4️⃣ Parameter")
max_per_day = st.number_input("Max. Einheiten pro Person pro Tag", 1, 3, 1)


# ---------------------------------------------------------
# 5) PLANUNG
# ---------------------------------------------------------
st.subheader("5️⃣ Planung")

if st.button("🚀 Start"):
    assignments = []

    for film in filme:
        name = film["Film"]
        start = film["BS_Start"]
        end = film["BS_Ende"]
        rdays = film["Role_Days"]

        # gültige Tage filtern:
        valid_days = []
        cur = start
        while cur <= end:
            if cur >= today:
                if cur.weekday() < 5:  # Mo-Fr
                    if not is_berlin_holiday(cur):
                        valid_days.append(cur)
            cur += timedelta(days=1)

        for rolle, needed in rdays.items():
            remaining = int(needed)
            if remaining <= 0:
                continue

            candidates = [p for p in personen if rolle in person_roles[p]]

            if not candidates:
                st.warning(f"{name}: Niemand kann {rolle}")
                continue

            load = {}
            idx = 0

            while remaining > 0 and idx < len(valid_days):
                d = valid_days[idx]
                for p in candidates:

                    # MP check
                    if mp_availability.get((p, d)) == "Blockiert":
                        continue

                    used = load.get((p, d), 0)
                    if used < max_per_day:
                        assignments.append({
                            "Film": name,
                            "Rolle": rolle,
                            "Person": p,
                            "Datum": d,
                            "Anteil": 1
                        })
                        load[(p, d)] = used + 1
                        remaining -= 1
                        if remaining <= 0:
                            break
                idx += 1

            if remaining > 0:
                st.warning(f"{name} / {rolle}: {remaining} unzugeordnet.")

    if not assignments:
        st.error("Nichts zuzuordnen.")
    else:
        df = pd.DataFrame(assignments)
        df["Film_Rolle"] = df["Film"] + " – " + df["Rolle"]

        st.subheader("📘 Ergebnis")
        st.dataframe(df, use_container_width=True)

        # GANTT
        st.subheader("📊 Gantt")

        df_g = df.copy()
        df_g["Start"] = pd.to_datetime(df_g["Datum"])
        df_g["Ende"] = df_g["Start"] + pd.to_timedelta(1, "D")

        fig = px.timeline(
            df_g,
            x_start="Start",
            x_end="Ende",
            y="Film_Rolle",
            color="Person",
            title="Pergamon – Planung"
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

        # EXPORT
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("CSV herunterladen", csv, "planung.csv")
