import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px

st.set_page_config(page_title="Pergamon Mini-Planer", layout="wide")
st.title("🕌 Pergamon Mini-Planer – Test für 1–2 Filme")

st.markdown("""
Diese kleine Version ist nur zum **Testen der Logik** gedacht:

- Keine Excel-Uploads
- Du definierst 1–2 Filme manuell (Name, BS-Zeitraum, Arbeitstage)
- Du definierst die Personen
- Die App verteilt automatisch die Arbeitstage auf freie Tage im BS-Zeitraum
""")

# ---------------------------------------------------------
# 1. Filme definieren
# ---------------------------------------------------------
st.subheader("1️⃣ Filme definieren")

num_films = st.number_input(
    "Wie viele Filme möchtest du testen?",
    min_value=1,
    max_value=2,
    value=1,
    step=1
)

filme = []
today = date.today()

for i in range(num_films):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        name = st.text_input(f"Film {i+1} – Name", value=f"Film {i+1}")
    with col2:
        bs_start = st.date_input(f"Film {i+1} – BS-Start", value=today + timedelta(days=7), key=f"start_{i}")
    with col3:
        bs_ende = st.date_input(f"Film {i+1} – BS-Ende", value=today + timedelta(days=37), key=f"ende_{i}")
    with col4:
        arbeitstage = st.number_input(f"Film {i+1} – Arbeitstage", min_value=1, max_value=365, value=10, step=1, key=f"tage_{i}")

    if bs_ende < bs_start:
        st.error(f"Film {i+1}: BS-Ende darf nicht vor BS-Start liegen.")
    filme.append({
        "Film": name,
        "BS_Start": bs_start,
        "BS_Ende": bs_ende,
        "Arbeitstage": arbeitstage
    })

# ---------------------------------------------------------
# 2. Personen definieren
# ---------------------------------------------------------
st.subheader("2️⃣ Personen definieren")

personen_input = st.text_input(
    "Personen (Komma-getrennt, z. B. „Ana, Anna, Mareike“)",
    value="Ana, Anna, Mareike"
)

personen = [p.strip() for p in personen_input.split(",") if p.strip()]

if not personen:
    st.warning("Bitte mindestens eine Person eintragen.")

max_tage_pro_tag = st.number_input(
    "Max. Anzahl Filme, die eine Person pro Tag machen darf",
    min_value=1,
    max_value=3,
    value=1
)

# ---------------------------------------------------------
# 3. Planung ausführen
# ---------------------------------------------------------
st.subheader("3️⃣ Planung starten")

if st.button("🚀 Planung berechnen"):
    if not personen:
        st.error("Keine Personen definiert.")
    else:
        # Kalender: für jeden Film die Tage im BS-Fenster
        assignments = []

        for film in filme:
            film_name = film["Film"]
            start = film["BS_Start"]
            ende = film["BS_Ende"]
            remaining = film["Arbeitstage"]

            # Alle Tage im Zeitraum
            tage = []
            current = start
            while current <= ende:
                if current >= today:  # NICHT in der Vergangenheit planen
                    tage.append(current)
                current += timedelta(days=1)

            if not tage:
                st.warning(f"Für {film_name} gibt es keine Tage (alles in der Vergangenheit?).")
                continue

            # Greedy: jeden Tag Personen durchgehen
            t_index = 0
            load = {}  # (person, datum) -> belegung

            while remaining > 0 and t_index < len(tage):
                d = tage[t_index]
                for person in personen:
                    key = (person, d)
                    used = load.get(key, 0)
                    if used < max_tage_pro_tag and remaining > 0:
                        assignments.append({
                            "Film": film_name,
                            "Person": person,
                            "Datum": d,
                            "Anteil": 1
                        })
                        load[key] = used + 1
                        remaining -= 1
                        if remaining <= 0:
                            break
                t_index += 1

            if remaining > 0:
                st.warning(f"⚠️ Film „{film_name}“: {remaining} Arbeitstage konnten NICHT untergebracht werden (Fenster zu klein / zu wenig Personen).")

        if not assignments:
            st.error("Es konnten keine Zuteilungen erzeugt werden.")
        else:
            df_assign = pd.DataFrame(assignments)
            st.subheader("📘 Ergebnis – Zuteilungen")
            st.dataframe(df_assign, use_container_width=True)

            # Gantt vorbereiten
            df_gantt = df_assign.copy()
            df_gantt["Start"] = df_gantt["Datum"]
            df_gantt["Ende"] = df_gantt["Datum"]

            st.subheader("📊 Gantt-Diagramm")

            fig = None
            try:
                fig = px.timeline(
                    df_gantt,
                    x_start="Start",
                    x_end="Ende",
                    y="Film",
                    color="Person",
                    title="Pergamon Mini-Planer – Verteilung"
                )
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Fehler beim Zeichnen des Gantt-Diagramms: {e}")

            # Excel-Export
            st.subheader("📥 Export")

            output = df_assign.copy()
            output["Datum"] = output["Datum"].astype(str)
            csv_bytes = output.to_csv(index=False).encode("utf-8")

            st.download_button(
                "Zuteilungen als CSV herunterladen",
                data=csv_bytes,
                file_name="Pergamon_Mini_Zuteilungen.csv",
                mime="text/csv"
            )
