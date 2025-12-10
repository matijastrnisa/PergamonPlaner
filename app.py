import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px

st.set_page_config(page_title="Pergamon Mini-Planer", layout="wide")
st.title("🕌 Pergamon Mini-Planer – Rollen & Personen (Multi-Rolle pro Film)")

st.markdown("""
Diese Version erlaubt dir:

- Personen zu definieren und ihnen Rollen zuzuweisen  
- Filme zu definieren mit **BS-Fenster**  
- Pro Film für **jede Rolle unterschiedliche Arbeitstage** einzutragen  
- Die App verteilt dann pro Film & Rolle die Tage auf passende Personen  
""")

today = date.today()

# ---------------------------------------------------------
# 1️⃣ Personen & Rollen definieren
# ---------------------------------------------------------
st.subheader("1️⃣ Personen & Rollen")

default_personen = "Anna, Mareike, Sonja, Sophia"
personen_input = st.text_input(
    "Personen (Komma-getrennt)",
    value=default_personen
)
personen = [p.strip() for p in personen_input.split(",") if p.strip()]

if not personen:
    st.warning("Bitte mindestens eine Person eintragen.")

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
        default=rollen,  # erstmal: alle können alles, du kannst abwählen
        key=f"roles_{person}"
    )

# ---------------------------------------------------------
# 2️⃣ Filme definieren
# ---------------------------------------------------------
st.subheader("2️⃣ Filme definieren")

num_films = st.number_input(
    "Wie viele Filme möchtest du testen?",
    min_value=1,
    max_value=5,
    value=2,
    step=1
)

filme = []

for i in range(num_films):
    st.markdown(f"**Film {i+1}**")
    col1, col2, col3 = st.columns(3)

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

    if bs_ende < bs_start:
        st.error(f"Film {i+1}: BS-Ende darf nicht vor BS-Start liegen.")

    st.markdown(f"_Arbeitstage je Rolle für **{name}**:_")
    role_days = {}
    cols = st.columns(len(rollen)) if rollen else []
    for j, rolle in enumerate(rollen):
        with cols[j]:
            tage = st.number_input(
                f"{rolle}",
                min_value=0,
                max_value=365,
                value=0,
                step=1,
                key=f"film_{i}_role_{rolle}"
            )
            role_days[rolle] = tage

    filme.append({
        "Film": name,
        "BS_Start": bs_start,
        "BS_Ende": bs_ende,
        "Role_Days": role_days
    })

# ---------------------------------------------------------
# 3️⃣ Planungs-Parameter
# ---------------------------------------------------------
st.subheader("3️⃣ Planungs-Parameter")

max_tage_pro_tag = st.number_input(
    "Max. Einheiten pro Person und Tag (über alle Filme/Rollen)",
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
            role_days = film["Role_Days"]

            # gültige Tage im BS-Fenster ab heute
            tage = []
            current = start
            while current <= ende:
                if current >= today:
                    tage.append(current)
                current += timedelta(days=1)

            if not tage:
                st.warning(f"⚠️ Film „{film_name}“: keine planbaren Tage (alles in der Vergangenheit?).")
                continue

            # pro Rolle planen
            for rolle, needed_days in role_days.items():
                remaining = int(needed_days)
                if remaining <= 0:
                    continue

                # Personen, die diese Rolle können
                passende_personen = [
                    p for p in personen
                    if rolle in person_roles.get(p, [])
                ]

                if not passende_personen:
                    st.warning(f"⚠️ Film „{film_name}“: keine Person hat die Rolle „{rolle}“.")
                    continue

                # Greedy: über Tage iterieren
                t_index = 0
                load = {}  # (person, datum) -> belegte Einheiten

                while remaining > 0 and t_index < len(tage):
                    d = tage[t_index]
                    for person in passende_personen:
                        key = (person, d)
                        used = load.get(key, 0)
                        if used < max_tage_pro_tag and remaining > 0:
                            assignments.append({
                                "Film": film_name,
                                "Rolle": rolle,
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
                    st.warning(f"⚠️ Film „{film_name}“ / Rolle „{rolle}“: {remaining} Tage konnten nicht untergebracht werden.")

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
                    title="Pergamon Mini-Planer – Verteilung nach Film/Rolle"
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
                file_name="Pergamon_MultiRole_Zuteilungen.csv",
                mime="text/csv"
            )
