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
Bitte die drei Dateien hochladen:

1. **PMU.xlsx** (BS-Plan, blaue Linien)  
2. **MP.xlsx** (Interner Kalender)  
3. **Zeitbudget.xlsx** (berechnete Arbeitstage pro Film)  
""")

# ---------------------------------------------------------
# FILE UPLOADS
# ---------------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    pmu_file = st.file_uploader("📘 PMU (BS-Plan)", type=["xlsx"])

with col2:
    mp_file = st.file_uploader("📗 MP (interner Plan)", type=["xlsx"])

with col3:
    zb_file = st.file_uploader("📙 Zeitbudget (Arbeitstage)", type=["xlsx"])


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def extract_films_from_zeitbudget(zb_df):
    """Erkennt die Filmliste im Zeitbudget."""
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


def extract_date_columns(pmu_df):
    """Erkennt Datums-Spalten im PMU."""
    header = pmu_df.iloc[0]
    mapping = {}

    for col in pmu_df.columns[1:]:
        try:
            mapping[col] = pd.to_datetime(header[col]).date()
        except:
            pass

    return mapping


def extract_bs_windows(pmu_df, films):
    """Findet BS Start/Ende für jeden Film aus PMU."""
    date_map = extract_date_columns(pmu_df)
    records = []

    for film in films:
        used_dates = []

        for row in range(1, len(pmu_df)):
            label = str(pmu_df.iloc[row, 0])

            if film.lower() in label.lower():
                for col, date in date_map.items():
                    cell = pmu_df.loc[row, col]
                    if isinstance(cell, str) and cell.strip():
                        used_dates.append(date)
                    elif pd.notna(cell):
                        used_dates.append(date)

        if used_dates:
            start = min(used_dates)
            end = max(used_dates)
            span = (end - start).days + 1
        else:
            start = None
            end = None
            span = None

        records.append({
            "Film": film,
            "BS_Start": start,
            "BS_Ende": end,
            "BS_Tage": span
        })

    return pd.DataFrame(records)
def extract_people(mp_df):
    """Erkennt die Personen basierend auf den ersten Zeilen."""
    people = []
    for i in range(10):
        v = str(mp_df.iloc[i, 0]).strip()
        if v.endswith(":"):
            people.append(v[:-1])
    return people


def extract_date_columns_mp(mp_df):
    """Erkennt Datumsspalten im MP."""
    header = mp_df.iloc[1]
    mapping = {}

    for col in mp_df.columns:
        try:
            mapping[col] = pd.to_datetime(header[col]).date()
        except:
            pass

    return mapping


def build_person_calendar(mp_df, people, date_map):
    """Erstellt Person × Datum × Status Tabelle."""
    rows = []

    first_col = mp_df.iloc[:, 0].astype(str)

    person_indices = {
        p: first_col[first_col.str.startswith(p)].index[0]
        for p in people
    }

    for person, idx in person_indices.items():
        row = mp_df.loc[idx]

        for col, d in date_map.items():
            cell = row[col]
            if isinstance(cell, str) and cell.strip():
                txt = cell.strip().lower()

                if txt in ["u", "urlaub"]:
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


def greedy_assign(stationen_df, calendar):
    """Einfacher Zuteiler: Füllt BS-Fenster mit freien Tagen pro Person."""
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
            freie = calendar[
                (calendar.Datum == current) &
                (calendar.Status == "Frei")
            ]

            for idx, row in freie.iterrows():
                if remaining <= 0:
                    break

                assignments.append({
                    "Film": film,
                    "Person": row.Person,
                    "Datum": current,
                    "Anteil": 1
                })

                calendar.loc[idx, "Status"] = "Pergamon"
                calendar.loc[idx, "Projekt"] = film

                remaining -= 1

            current += timedelta(days=1)

        if remaining > 0:
            rest.append({"Film": film, "Rest": remaining})

    return pd.DataFrame(assignments), pd.DataFrame(rest)
# ---------------------------------------------------------
# MAIN EXECUTION LOGIC
# ---------------------------------------------------------

if pmu_file and mp_file and zb_file:
    st.success("Alle Dateien wurden erfolgreich geladen.")

    # Excel laden
    pmu_df = pd.read_excel(pmu_file)
    mp_df = pd.read_excel(mp_file)
    zb_df = pd.read_excel(zb_file)

    # FILME erkennen
    films = extract_films_from_zeitbudget(zb_df)
    st.subheader("🎬 Erkannte Filme / Stationen")
    st.write(films)

    # BS-Fenster erkennen
    bs_df = extract_bs_windows(pmu_df, films)
    st.subheader("📅 BS-Fenster je Film")
    st.dataframe(bs_df, use_container_width=True)

    # Arbeitstage eingeben
    st.subheader("📏 Arbeitstage je Film (Zeitbudget)")
    arbeitstage_df = st.data_editor(
        pd.DataFrame({
            "Film": films,
            "Arbeitstage": [0] * len(films)
        }),
        use_container_width=True
    )

    # Personen + Datumsspalten aus MP auslesen
    people = extract_people(mp_df)
    date_map_mp = extract_date_columns_mp(mp_df)
    calendar = build_person_calendar(mp_df, people, date_map_mp)

    st.subheader("👥 Personen-Kalender (Auszug)")
    st.dataframe(calendar.head(50), use_container_width=True)

    # Button zum Starten der Planung
    if st.button("🚀 Automatische Zuteilung starten"):
        stationen = bs_df.merge(arbeitstage_df, on="Film")

        assignments, rest = greedy_assign(stationen, calendar)

        st.success("Zuteilung abgeschlossen!")

        # Ergebnisse
        st.subheader("📘 Zuteilungen (Ergebnis)")
        st.dataframe(assignments, use_container_width=True)

        st.subheader("⚠️ Filme mit Restarbeitstagen")
        st.dataframe(rest, use_container_width=True)

        # EXCEL EXPORT
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            assignments.to_excel(writer, index=False, sheet_name="Zuteilungen")
            rest.to_excel(writer, index=False, sheet_name="Rest")
            calendar.to_excel(writer, index=False, sheet_name="Personenkalender")

        st.download_button(
            "📥 Excel-Ergebnis herunterladen",
            data=buffer.getvalue(),
            file_name="Pergamon_Planer_Ergebnis.xlsx"
        )

        # GANTT
        st.subheader("📊 Gantt-Visualisierung (Zuweisung)")

        if not assignments.empty:
            gantt = assignments.copy()
            gantt["Start"] = gantt["Datum"]
            gantt["End"] = gantt["Datum"]

            fig = px.timeline(
                gantt,
                x_start="Start",
                x_end="End",
                y="Film",
                color="Person",
                title="Pergamon – Automatische Zuweisung"
            )

            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Bitte alle drei Dateien hochladen, um zu beginnen.")
