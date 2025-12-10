import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px

st.set_page_config(page_title="Pergamon Mini-Planer", layout="wide")
st.title("🕌 Pergamon Mini-Planer – Rollen & Personen")

st.markdown("""
Diese Mini-Version ist nur zum **Testen der Logik** gedacht:

- Keine Excel-Uploads  
- Du definierst **Personen** und gibst ihnen **Rollen**  
- Du definierst 1–2 **Filme** mit BS-Fenster und Arbeitstagen  
- Die App verteilt Arbeitstage automatisch auf passende Personen
""")

today = date.today()

# ---------------------------------------------------------
# 1️⃣ Personen & Rollen definieren
# ---------------------------------------------------------
st.subheader("1️⃣ Personen & Rollen")

# Standardpersonen
default_personen = "Anna, Mareike, Sonja, Sophia"
personen_input = st.text_input(
    "Personen (Komma-getrennt)",
    value=default_personen
)
personen = [p.strip() for p in personen_input.split(",") if p.strip()]

if not personen:
    st.warning("Bitte mindestens eine Person eintragen.")

# Standardrollen
default_roles = ["Storyboard", "Keyframes", "Animation"]
rollen_input = st.text_input(
    "Rollen (Komma-getrennt)",
    value=", ".join(default_roles)
)
rollen = [r.strip() for r in rollen_input.split(",") if r.strip()]

if not rollen:
    st.warning("Bitte mindestens eine Rolle eintragen.")

st.markdown("#### Rollen pro Person")

person_roles = {}
for person in personen:
    person_roles[person] = st.multiselect(
        f"Rollen für **{person}**",
        options=rollen,
        default=rollen,  # standard: alle können alles, kannst du anpassen
        key=f"roles_{person}"
    )

# ---------------------------------------------------------
# 2️⃣ Filme definieren
# ---------------------------------------------------------
st.subheader("2️⃣ Filme definieren")

num_films = st.number_input(
    "Wie viele Filme möchtest du testen?",
    min_value=1,
    max_value=2,
    value=1,
    step=1
)

filme = []

for i in range(num_films):
    st.markdown(f"**Film {i+1}**")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        name = st.text_input(f"Name Film {i+1}", value=f"Film {i+1}", key=f"film_name_{i}")
    with col2:
        bs_start = st.date_input(
            f"BS-Start {i+1}",
            value=today + timedelta(days=7),
            key=f"bs_start_{i}"
        )
    with col3:
        bs_ende = st.date_input(
            f"BS-Ende {i+1}",
            value=today + timedelta(days=37),
            key=f"bs_ende_{i}"
        )
    with col4:
        arbeitstage = st.number_input(
            f"Arbeitstage {i+1}",
            min_value=1,
            max_value=365,
            value=10,
            step=1,
            key=f"arbeitstage_{i}"
        )
    with col5:
        rolle = st.selectbox(
            f"Benötigte Rolle {i+1}",
            options=rollen,
            key=f"rolle_{i}"
        )

    if bs_ende < bs_start:
        st.error(f"Film {i+1}: BS-Ende darf nicht vor BS-Start liegen.")

    filme.append({
        "Film": name,
        "BS_Start": bs_start,
        "BS_Ende": bs_ende,
        "Arbeitstage": arbeitstage,
        "Rolle": rolle
    })

# ---------------------------------------------------------
# 3️⃣ Planungs-Parameter
# ---------------------------------------------------------
st.subheader("3️⃣ Planungs-Parameter")

max_tage_pro_tag = st.number_input(
    "Max. Filme/Tage, die eine Person pro Tag machen darf",
    min_value=1,
    max_value=3,
    value=1
)

st.markdown("_Hinweis: Es wird **nicht in der Vergangenheit** geplant (nur ab heute)._")

# ---------------------------------------------------------
# 4️⃣ Planung starten
# ---------------------------------------------------------
st.subheader("4️⃣ Planung ausführen")

if st.button("🚀 Planung berechnen"):
    if not personen:
        st.error("Keine Personen definiert.")
    elif not rollen:
        st.error("Keine Rollen definiert.")
    else:
        assignments = []

        for film in filme:
            film_name = film["Film"]
            start = film["BS_Start"]
            ende = film["BS_Ende"]
            remaining = film["Arbeitstage"]
            needed_role = film["Rolle"]

            # Personen, die diese Rolle können
            passende_personen = [
                p for p in personen
                if needed_role in person_roles.get(p, [])
            ]

            if not passende_personen:
                st.warning(f"⚠️ Film „{film_name}“: Keine Person hat die Rolle „{needed_role}“.")
                continue

            # Alle Tage im BS-Fenster ab heute
            tage = []
            current = start
            while current <= ende:
                if current >= today:
                    tage.append(current)
                current += timedelta(days=1)

            if not tage:
                st.warning(f"⚠️ Film „{film_name}“: Keine planbaren Tage (alles in der Vergangenheit?).")
                continue

            # Greedy-Planung
            t_index = 0
            load = {}  # (person, datum) -> belegte Slots

            while remaining > 0 and t_index < len(tage):
                d = tage[t_index]
                for person in passende_personen:
                    key = (person, d)
                    used = load.get(key, 0)
                    if used < max_tage_pro_tag and remaining > 0:
                        assignments.append({
                            "Film": film_name,
                            "Rolle": needed_role,
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
                st.warning(f"⚠️ Film „{film_name}“: {remaining} Arbeitstage konnten NICHT untergebracht werden.")

        if not assignments:
            st.error("Es konnten keine Zuteilungen erzeugt werden.")
        else:
            df_assign = pd.DataFrame(assignments)
            st.subheader("📘 Ergebnis – Zuteilungen")
            st.dataframe(df_assign, use_container_width=True)

            # Gantt
            st.subheader("📊 Gantt-Diagramm")
            df_gantt = df_assign.copy()
            df_gantt["Start"] = df_gantt["Datum"]
            df_gantt["Ende"] = df_gantt["Datum"]

            try:
                fig = px.timeline(
                    df_gantt,
                    x_start="Start",
                    x_end="Ende",
                    y="Film",
                    color="Person",
                    title="Pergamon Mini-Planer – Verteilung nach Rollen"
                )
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Fehler beim Erzeugen des Gantt-Diagramms: {e}")

            # CSV-Export
            st.subheader("📥 Export")
            out = df_assign.copy()
            out["Datum"] = out["Datum"].astype(str)
            csv_bytes = out.to_csv(index=False).encode("utf-8")

            st.download_button(
                "Zuteilungen als CSV herunterladen",
                data=csv_bytes,
                file_name="Pergamon_Mini_Zuteilungen.csv",
                mime="text/csv"
            )
