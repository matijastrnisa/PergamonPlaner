import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
import plotly.express as px
import io

# ---------------------------------------------------------
# PASSWORD PROTECTION
# ---------------------------------------------------------
APP_PASSWORD = "PergamonSecure2024"

password_input = st.sidebar.text_input("🔒 Passwort:", type="password")
if password_input != APP_PASSWORD:
    st.error("Falsches Passwort.")
    st.stop()

# ---------------------------------------------------------
# PAGE SETUP
# ---------------------------------------------------------
st.set_page_config(page_title="Pergamon Planer", layout="wide")
st.title("🕌 Pergamon Planer – Automatische Kapazitäts- & Terminplanung")

st.markdown("""
### Bitte die drei Dateien hochladen:
1. **PMU.xlsx** (BS-Plan)  
2. **MP.xlsx** (interner Kalender)  
3. **Zeitbudget.xlsx** (berechnete Arbeitstage)  
""")

# ---------------------------------------------------------
# UPLOADS
# ---------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    pmu_file = st.file_uploader("📘 PMU (BS-Plan)", type=["xlsx"])
with col2:
    mp_file = st.file_uploader("📗 MP (interner Plan)", type=["xlsx"])
with col3:
    zb_file = st.file_uploader("📙 Zeitbudget", type=["xlsx"])

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def extract_films_from_zeitbudget(zb_df):
    col0 = zb_df.iloc[:, 0].astype(str)
    at_row = col0[col0 == "AT"].index[0]
    films = []
    for i in range(at_row + 1, len(zb_df)):
        name = str(zb_df.iloc[i, 0]).strip()
        if not name:
            break
        if "∑" in name or "Laufzeit" in name or "GESAMT" in name:
            continue
        films.append(name)
    return films


def extract_bs_windows(pmu_df, films):
    header = pmu_df.iloc[0]
    date_map = {}
    for col in pmu_df.columns[1:]:
        try:
            date_map[col] = pd.to_datetime(header[col]).date()
        except:
            pass

    records = []
    for film in films:
        dates = []
        for i in range(1, len(pmu_df)):
            label = str(pmu_df.iloc[i, 0])
            if film.lower() in label.lower():
                for col, d in date_map.items():
                    val = pmu_df.loc[i, col]
                    if isinstance(val, str) and val.strip():
                        dates.append(d)
                    elif pd.notna(val):
                        dates.append(d)

        if dates:
            start = min(dates)
            end = max(dates)
            span = (end - start).days + 1
        else:
            start = None
            end = None
            span = None

        records.append({
            "Film": film,
            "BS_Start": start,
            "BS_Ende": end,
            "BS_Tage": span,
        })
    return pd.DataFrame(records)


def extract_people(mp_df):
    people = []
    for i in range(10):
        v = str(mp_df.iloc[i, 0]).strip()
        if v.endswith(":"):
            people.append(v[:-1])
    return people


def extract_date_columns(mp_df):
    date_map = {}
    header = mp_df.iloc[1]
    for col in mp_df.columns:
        try:
            date_map[col] = pd.to_datetime(header[col]).date()
        except:
            pass
    return date_map


def build_person_calendar(mp_df, people, date_map):
    rows = []
    colA = mp_df.iloc[:, 0].astype(str)

    person_row_index = {
        p: colA[colA.str.startswith(p)].index[0]
        for p in people
    }

    for person, idx in person_row_index.items():
        row = mp_df.loc[idx]
        for col, d in date_map.items():
            cell = row[col]
            if isinstance(cell, str) and cell.strip():
                txt = cell.strip().lower()
                if "u" == txt or "urlaub" in txt:
                    status = "Urlaub"
                    proj = "Urlaub"
                else:
                    status = "Blockiert"
                    proj = cell
            else:
                status = "Frei"
                proj = ""
            rows.append({
                "Person": person,
                "Datum": d,
                "Status": status,
                "Projekt": proj
            })
    return pd.DataFrame(rows)


def greedy_assign(stationen_df, cal):
    assignments = []
    rest = []

    for _, st in stationen_df.iterrows():
        film = st.Film
        remaining = st.Arbeitstage
        start = st.BS_Start
        end = st.BS_Ende

        if pd.isna(start) or pd.isna(end) or remaining <= 0:
            rest.append({"Film": film, "Rest": remaining})
            continue

        current = start
        while current <= end and remaining > 0:
            mask = (cal.Datum == current) & (cal.Status == "Frei")
            freie = cal[mask]

            for idx, row in freie.iterrows():
                if remaining <= 0:
                    break

                assignments.append({
                    "Film": film,
                    "Person": row.Person,
                    "Datum": current,
                    "Anteil": 1
                })

                cal.loc[idx, "Status"] = "Pergamon"
                cal.loc[idx, "Projekt"] = film
                remaining -= 1

            current += timedelta(days=1)

        if remaining > 0:
            rest.append({"Film": film, "Rest": remaining})

    return pd.DataFrame(assignments), pd.DataFrame(rest)


# ---------------------------------------------------------
# MAIN LOGIC
# ---------------------------------------------------------

if pmu_file and mp_file and zb_file:
    st.success("Alle Dateien geladen.")

    pmu = pd.read_excel(pmu_file)
    mp = pd.read_excel(mp_file)
    zb = pd.read_excel(zb_file)

    films = extract_films_from_zeitbudget(zb)
    st.subheader("🎬 Erkannte Filme")
    st.write(films)

    bs_df = extract_bs_windows(pmu, films)
    st.subheader("📅 BS-Fenster")
    st.dataframe(bs_df)

    st.subheader("📏 Arbeitstage pro Film")
    arbeitstage_df = st.data_editor(
        pd.DataFrame({"Film": films, "Arbeitstage": [0]*len(films)}),
        use_container_width=True
    )

    people = extract_people(mp)
    date_map = extract_date_columns(mp)
    calendar = build_person_calendar(mp, people, date_map)

    st.subheader("👥 Personen-Kapazitäten")
    st.dataframe(calendar.head(50))

    if st.button("🚀 Zuteilung starten"):
        merged = bs_df.merge(arbeitstage_df, on="Film")
        assignments, rest = greedy_assign(merged, calendar)

        st.success("Zuteilung abgeschlossen.")

        st.subheader("📘 Zuteilungen")
        st.dataframe(assignments)

        st.subheader("⚠️ Nicht vollständig geplant")
        st.dataframe(rest)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as w:
            assignments.to_excel(w, index=False, sheet_name="Zuteilungen")
            rest.to_excel(w, index=False, sheet_name="Rest")
            calendar.to_excel(w, index=False, sheet_name="Kalender")

        st.download_button(
            "📥 Excel herunterladen",
            data=buffer.getvalue(),
            file_name="Pergamon_Planer_Ergebnis.xlsx"
        )

        st.subheader("📊 Gantt-Visualisierung")
        if not assignments.empty:
            gantt = assignments.copy()
            gantt["Start"] = gantt["Datum"]
            gantt["Ende"] = gantt["Datum"]

            fig = px.timeline(
                gantt,
                x_start="Start",
                x_end="Ende",
                y="Film",
                color="Person"
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Bitte alle Dateien hochladen.")
