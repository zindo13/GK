
import streamlit as st
import requests
from bs4 import BeautifulSoup
from itertools import combinations
from collections import Counter
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# =====================
# STREAMLIT CONFIG
# =====================
st.set_page_config(
    page_title="Greek Kino Analyzer PRO",
    page_icon="🎯",
    layout="wide"
)

# =====================
# FETCH DATA
# =====================
@st.cache_data(ttl=300)
def fetch_kino_results(url, max_draws):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        draws = []

        sections = soup.get_text(separator="\n").split("Extragere")[1:]

        for section in sections:
            if len(draws) >= max_draws:
                break

            lines = [
                l.strip()
                for l in section.split("\n")
                if l.strip()
            ]

            nums = []

            for line in lines[1:]:
                for p in line.split():
                    if p.isdigit():
                        nums.append(int(p))

            # Validno KINO izvlacenje: 20 jedinstvenih brojeva 1-80
            if (
                len(nums) == 20
                and len(set(nums)) == 20
                and all(1 <= n <= 80 for n in nums)
            ):
                draws.append(nums)

        return draws

    except requests.RequestException as e:
        st.error(f"Greska prilikom ucitavanja podataka: {e}")
        return []


# =====================
# COMBINATIONS
# =====================
def analyze_kino(draws, M, K):
    counter = Counter()

    for draw in draws:
        for combo in combinations(sorted(draw), M):
            counter[combo] += 1

    return [
        (c, cnt)
        for c, cnt in counter.items()
        if cnt > K
    ]


# =====================
# MATRIX UTILS
# =====================
def number_to_matrix_pos(num, rows, cols):
    return (num - 1) // cols, (num - 1) % cols


def draw_single_matrix(draw, rows, cols):
    matrix = np.zeros((rows, cols))

    for num in draw:
        r, c = number_to_matrix_pos(num, rows, cols)
        matrix[r, c] = 1

    return matrix


# =====================
# MATRIX ANALYSIS
# =====================
def matrix_analysis(draws, rows, cols, br, bc):
    counts = Counter()

    heatmap_counts = np.zeros((rows, cols))

    heatmap_numbers = np.arange(
        1, rows * cols + 1
    ).reshape(rows, cols)

    for draw in draws:
        positions = [
            number_to_matrix_pos(n, rows, cols)
            for n in draw
        ]

        for r, c in positions:
            heatmap_counts[r, c] += 1

        for rs in range(rows - br + 1):
            for cs in range(cols - bc + 1):

                block = {
                    (rs + i, cs + j)
                    for i in range(br)
                    for j in range(bc)
                }

                hits = sum(
                    1 for p in positions if p in block
                )

                counts[(rs, cs)] += hits

    max_block, max_hits = (
        counts.most_common(1)[0]
        if counts
        else (None, 0)
    )

    return (
        heatmap_counts,
        heatmap_numbers,
        max_block,
        max_hits
    )


# =====================
# SAME UNIT ANALYSIS
# =====================
def analyze_same_units(draws, min_hits=5):

    # Grupa 1: 1,11,21,...71
    # Grupa 2: 2,12,22,...72
    # ...
    # Grupa 0: 10,20,30,...80

    groups = {
        unit: list(range(unit, 81, 10))
        for unit in range(1, 11)
    }

    # (grupa, tacan broj pogodaka) -> broj pojavljivanja
    statistics = Counter()

    # Poslednje pojavljivanje 5+ pogodaka
    last_seen = {}

    # Istorija svih dogadjaja sa 5+ pogodaka
    events = []

    # Pretpostavka: draws[0] je najnovije izvlacenje
    for draw_index, draw in enumerate(draws):

        drawn_numbers = set(draw)

        for unit, group_numbers in groups.items():

            matched_numbers = sorted(
                drawn_numbers.intersection(group_numbers)
            )

            hits = len(matched_numbers)

            if hits >= min_hits:

                statistics[(unit, hits)] += 1

                # Prvo pronadjeno pojavljivanje je najnovije
                if unit not in last_seen:
                    last_seen[unit] = draw_index

                events.append({
                    "Izvlacenje": draw_index + 1,
                    "Grupa": "0" if unit == 10 else str(unit),
                    "Broj pogodaka": hits,
                    "Pogodjeni brojevi": ", ".join(
                        map(str, matched_numbers)
                    )
                })

    return statistics, groups, last_seen, events


# =====================
# STREAMLIT MAIN
# =====================
st.title("🎯 Greek Kino Analyzer PRO")

option = st.radio(
    "Izaberi analizu:",
    (
        "Kombinacije",
        "Heatmap analiza",
        "Vizuelni prikaz",
        "Overlay + statistika",
        "Ista jedinica (5+ pogodaka)"
    )
)

N = st.number_input(
    "Broj poslednjih izvlacenja",
    min_value=10,
    max_value=200,
    value=50,
    step=10
)

with st.spinner("Ucitavam podatke..."):
    draws = fetch_kino_results(
        "https://grkino.com/arhiva.php",
        int(N)
    )

if not draws:
    st.warning("Nema podataka ili podaci nisu ucitani.")
    st.stop()

st.success(f"Ucitano {len(draws)} izvlacenja.")

if len(draws) < N:
    st.warning(
        f"Trazeno je {N} izvlacenja, "
        f"ali je pronadjeno samo {len(draws)}."
    )


# =====================
# 1. KOMBINACIJE
# =====================
if option == "Kombinacije":

    M = st.number_input(
        "M (velicina kombinacije)",
        min_value=2,
        max_value=10,
        value=5
    )

    K = st.number_input(
        "K (min ponavljanja)",
        min_value=1,
        max_value=10,
        value=1
    )

    if st.button("Analyze"):

        result = analyze_kino(
            draws,
            int(M),
            int(K)
        )

        if result:
            for combo, count in sorted(
                result,
                key=lambda x: -x[1]
            ):
                st.write(combo, "->", count)
        else:
            st.info("Nema kombinacija koje ispunjavaju uslov.")


# =====================
# 2. HEATMAP ANALIZA
# =====================
elif option == "Heatmap analiza":

    rows = st.number_input(
        "Redovi", 2, 20, 8
    )

    cols = st.number_input(
        "Kolone", 2, 20, 10
    )

    br = st.number_input(
        "Visina bloka", 1, int(rows), 3
    )

    bc = st.number_input(
        "Sirina bloka", 1, int(cols), 3
    )

    if st.button("Analyze heatmap"):

        if rows * cols < 80:
            st.error(
                "Matrica mora imati najmanje 80 polja."
            )
            st.stop()

        (
            heatmap_counts,
            heatmap_numbers,
            max_block,
            max_hits
        ) = matrix_analysis(
            draws,
            int(rows),
            int(cols),
            int(br),
            int(bc)
        )

        fig, ax = plt.subplots(
            figsize=(cols, rows)
        )

        sns.heatmap(
            heatmap_counts,
            annot=True,
            fmt=".0f",
            cmap="Reds",
            ax=ax
        )

        if max_block is not None:

            rect = plt.Rectangle(
                (max_block[1], max_block[0]),
                bc,
                br,
                fill=False,
                edgecolor="blue",
                linewidth=3
            )

            ax.add_patch(rect)

            st.write(
                f"Najgusci blok: {max_hits} pogodaka"
            )

        st.pyplot(fig)
        plt.close(fig)

        # Prikaz brojeva
        fig2, ax2 = plt.subplots(
            figsize=(cols, rows)
        )

        sns.heatmap(
            heatmap_numbers,
            annot=True,
            fmt="d",
            cmap="Greys",
            ax=ax2
        )

        if max_block is not None:

            rect2 = plt.Rectangle(
                (max_block[1], max_block[0]),
                bc,
                br,
                fill=False,
                edgecolor="blue",
                linewidth=3
            )

            ax2.add_patch(rect2)

        st.pyplot(fig2)
        plt.close(fig2)


# =====================
# 3. VIZUELNI PRIKAZ
# =====================
elif option == "Vizuelni prikaz":

    rows = st.number_input(
        "Redovi", 2, 20, 8
    )

    cols = st.number_input(
        "Kolone", 2, 20, 10
    )

    if rows * cols < 80:
        st.error(
            "Matrica mora imati najmanje 80 polja."
        )
        st.stop()

    index = st.slider(
        "Izvlacenje",
        1,
        len(draws),
        1
    )

    matrix = draw_single_matrix(
        draws[index - 1],
        int(rows),
        int(cols)
    )

    numbers = np.arange(
        1, rows * cols + 1
    ).reshape(rows, cols)

    fig, ax = plt.subplots(
        figsize=(cols, rows)
    )

    sns.heatmap(
        matrix,
        annot=numbers,
        fmt="d",
        cmap="Reds",
        cbar=False,
        ax=ax
    )

    st.pyplot(fig)
    plt.close(fig)


# =====================
# 4. OVERLAY + STATISTIKA
# =====================
elif option == "Overlay + statistika":

    rows = st.number_input(
        "Redovi", 2, 20, 8
    )

    cols = st.number_input(
        "Kolone", 2, 20, 10
    )

    if rows * cols < 80:
        st.error(
            "Matrica mora imati najmanje 80 polja."
        )
        st.stop()

    overlay = np.zeros((rows, cols))

    for draw in draws:
        for num in draw:

            r, c = number_to_matrix_pos(
                num,
                int(rows),
                int(cols)
            )

            overlay[r, c] += 1

    numbers = np.arange(
        1, rows * cols + 1
    ).reshape(rows, cols)

    fig, ax = plt.subplots(
        figsize=(cols, rows)
    )

    sns.heatmap(
        overlay,
        annot=numbers,
        fmt="d",
        cmap="coolwarm",
        ax=ax
    )

    st.pyplot(fig)
    plt.close(fig)

    st.write("📊 Statistika:")

    st.write("Max:", int(np.max(overlay)))
    st.write("Min:", int(np.min(overlay)))
    st.write("Prosek:", float(np.mean(overlay)))


# =====================
# 5. ISTA JEDINICA - 5+ POGODAKA
# =====================
elif option == "Ista jedinica (5+ pogodaka)":

    st.header("📊 Statistika brojeva sa istom jedinicom")

    st.write(
        "Analiza grupa brojeva koji imaju istu jedinicu, "
        "sa najmanje 5 pogodaka u jednom izvlacenju."
    )

    (
        statistics,
        groups,
        last_seen,
        events
    ) = analyze_same_units(
        draws,
        min_hits=5
    )

    total_draws = len(draws)

    # =====================
    # DETALJNA STATISTIKA
    # =====================
    st.subheader("1. Broj pogodaka i broj pojavljivanja")

    detailed_data = []

    for unit, numbers in groups.items():

        group_label = ", ".join(
            map(str, numbers)
        )

        for hits in range(5, 9):

            count = statistics.get(
                (unit, hits),
                0
            )

            detailed_data.append({
                "Grupa": group_label,
                "Broj pogodaka": hits,
                "Broj puta": count
            })

    df_detailed = pd.DataFrame(
        detailed_data
    )

    show_only_hits = st.checkbox(
        "Prikazi samo rezultate koji su se pojavili",
        value=True
    )

    if show_only_hits:
        df_detailed = df_detailed[
            df_detailed["Broj puta"] > 0
        ]

    if not df_detailed.empty:

        st.dataframe(
            df_detailed,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info(
            "Nema pojavljivanja sa 5 ili vise pogodaka."
        )

    # =====================
    # SUMARNA STATISTIKA
    # =====================
    st.subheader("2. Ukupna statistika po grupama")

    summary_data = []

    for unit, numbers in groups.items():

        counts = {
            hits: statistics.get(
                (unit, hits),
                0
            )
            for hits in range(5, 9)
        }

        total = sum(counts.values())

        percentage = (
            total / total_draws * 100
            if total_draws > 0
            else 0
        )

        # Broj izvlacenja od poslednjeg pojavljivanja
        if unit in last_seen:
            last_occurrence = last_seen[unit]
        else:
            last_occurrence = None

        summary_data.append({
            "Grupa": (
                "0" if unit == 10 else str(unit)
            ),
            "Brojevi": ", ".join(
                map(str, numbers)
            ),
            "5 pogodaka": counts[5],
            "6 pogodaka": counts[6],
            "7 pogodaka": counts[7],
            "8 pogodaka": counts[8],
            "Ukupno 5+": total,
            "Udeo (%)": round(percentage, 2),
            "Proslo izvlacenja": (
                last_occurrence
                if last_occurrence is not None
                else "-"
            )
        })

    df_summary = pd.DataFrame(
        summary_data
    )

    df_summary = df_summary.sort_values(
        by="Ukupno 5+",
        ascending=False
    )

    st.dataframe(
        df_summary,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "'Proslo izvlacenja' oznacava koliko je "
        "izvlacenja proslo od poslednjeg pojavljivanja "
        "5+ pogodaka. Vrednost 0 znaci da se dogodilo "
        "u najnovijem izvlacenju. "
        "Izvlacenja se posmatraju redosledom "
        "kojim ih vraca arhiva, od najnovijeg."
    )

    # =====================
    # UKUPNI REZULTATI
    # =====================
    st.subheader("3. Ukupni rezultati")

    total_5 = sum(
        statistics.get((unit, 5), 0)
        for unit in groups
    )

    total_6 = sum(
        statistics.get((unit, 6), 0)
        for unit in groups
    )

    total_7 = sum(
        statistics.get((unit, 7), 0)
        for unit in groups
    )

    total_8 = sum(
        statistics.get((unit, 8), 0)
        for unit in groups
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("5 pogodaka", total_5)
    col2.metric("6 pogodaka", total_6)
    col3.metric("7 pogodaka", total_7)
    col4.metric("8 pogodaka", total_8)

    st.info(
        f"Ukupno evidentirano {len(events)} "
        f"pojavljivanja grupa sa 5+ pogodaka "
        f"u poslednjih {total_draws} izvlacenja."
    )

    # =====================
    # GRAFIKON PO GRUPAMA
    # =====================
    st.subheader("4. Grafikon ucestalosti po grupama")

    labels = []
    values = []

    for unit in groups:

        label = "0" if unit == 10 else str(unit)

        total = sum(
            statistics.get((unit, hits), 0)
            for hits in range(5, 9)
        )

        labels.append(label)
        values.append(total)

    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    bars = ax.bar(
        labels,
        values,
        color="steelblue",
        edgecolor="black"
    )

    ax.set_xlabel("Grupa / poslednja cifra")
    ax.set_ylabel("Broj pojavljivanja")
    ax.set_title(
        "Broj izvlacenja sa 5+ pogodaka po grupama"
    )

    ax.bar_label(
        bars,
        padding=3
    )

    ax.set_ylim(
        0,
        max(values, default=0) + 2
    )

    ax.grid(
        axis="y",
        alpha=0.3
    )

    st.pyplot(fig)
    plt.close(fig)

    # =====================
    # GRAFIKON 5, 6, 7, 8
    # =====================
    st.subheader("5. Raspodela broja pogodaka")

    hit_labels = ["5", "6", "7", "8"]

    hit_values = [
        total_5,
        total_6,
        total_7,
        total_8
    ]

    fig2, ax2 = plt.subplots(
        figsize=(9, 4)
    )

    bars2 = ax2.bar(
        hit_labels,
        hit_values,
        color="coral",
        edgecolor="black"
    )

    ax2.set_xlabel("Broj pogodaka")
    ax2.set_ylabel("Broj pojavljivanja")
    ax2.set_title(
        "Ukupna raspodela 5, 6, 7 i 8 pogodaka"
    )

    ax2.bar_label(
        bars2,
        padding=3
    )

    ax2.set_ylim(
        0,
        max(hit_values, default=0) + 2
    )

    ax2.grid(
        axis="y",
        alpha=0.3
    )

    st.pyplot(fig2)
    plt.close(fig2)

    # =====================
    # ISTORIJA POGODAKA
    # =====================
    st.subheader("6. Istorija svih 5+ pogodaka")

    st.write(
        "Prikaz svih izvlacenja u kojima je "
        "neka grupa imala najmanje 5 pogodaka."
    )

    if events:

        df_events = pd.DataFrame(events)

        st.dataframe(
            df_events,
            use_container_width=True,
            hide_index=True
        )

        csv = df_events.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            label="Preuzmi istoriju kao CSV",
            data=csv,
            file_name="kino_same_unit_history.csv",
            mime="text/csv"
        )

    else:
        st.info(
            "Nema izvlacenja sa 5+ pogodaka."
        )

    # =====================
    # NAJCESCA GRUPA
    # =====================
    st.subheader("7. Najcesca grupa")

    best_group = df_summary.iloc[0]

    if best_group["Ukupno 5+"] > 0:

        st.success(
            f"Najcesca grupa: {best_group['Grupa']} "
            f"({best_group['Brojevi']})"
        )

        st.write(
            f"Ukupno pojavljivanja sa 5+ pogodaka: "
            f"{best_group['Ukupno 5+']}"
        )

        st.write(
            f"Udeo u analiziranim izvlacenjima: "
            f"{best_group['Udeo (%)']}%"
        )

    else:
        st.info(
            "Nijedna grupa nije imala 5+ pogodaka."
        )
