import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from itertools import combinations
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import seaborn as sns
import streamlit as st
from bs4 import BeautifulSoup


st.set_page_config(page_title="Greek Kino Analyzer PRO", page_icon="🎯", layout="wide")
ATHENS = ZoneInfo("Europe/Athens")
GRKINO_URL = "https://grkino.com/arhiva.php"


# ==============================================
# PREUZIMANJE REZULTATA (NOVIJI PRVO)
# ==============================================
def valid_draw(numbers):
    return (
        isinstance(numbers, list)
        and len(numbers) == 20
        and len(set(numbers)) == 20
        and all(type(n) is int and 1 <= n <= 80 for n in numbers)
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_opap_day(day_iso):
    url = f"https://api.opap.gr/draws/v3.0/1100/draw-date/{day_iso}/{day_iso}"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
        raise ValueError("OPAP nije vratio ocekivani format podataka.")

    result = []
    for item in payload["content"]:
        nums = item.get("winningNumbers", {}).get("list", [])
        if not valid_draw(nums):
            continue

        timestamp = item.get("drawTime")
        if not isinstance(timestamp, (int, float)):
            continue

        local_dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).astimezone(ATHENS)
        result.append({
            "numbers": nums,
            "timestamp": int(timestamp),
            "date": local_dt.strftime("%d.%m.%Y %H:%M"),
            "id": str(item.get("drawId", int(timestamp))),
        })
    return result


@st.cache_data(ttl=300, show_spinner=False)
def fetch_grkino_archive():
    response = requests.get(GRKINO_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    sections = re.split(r"\bExtragere\b", soup.get_text(separator="\n"))[1:]
    result = []

    for section in sections:
        lines = [line.strip() for line in section.splitlines() if line.strip()]
        heading = " ".join(lines[:3])
        match = re.search(r"(\d{2}:\d{2}:\d{2})\s+(\d{2}\.\d{2}\.\d{4})", heading)
        if not match:
            continue

        nums = [int(line) for line in lines if re.fullmatch(r"\d{1,2}", line)]
        nums = nums[:20]
        if not valid_draw(nums):
            continue

        dt = datetime.strptime(f"{match.group(2)} {match.group(1)}", "%d.%m.%Y %H:%M:%S")
        local_dt = dt.replace(tzinfo=ATHENS)
        result.append({
            "numbers": nums,
            "timestamp": int(local_dt.timestamp() * 1000),
            "date": local_dt.strftime("%d.%m.%Y %H:%M"),
            "id": local_dt.isoformat(),
        })

    return result


def newest_unique(draws, n):
    result = []
    seen = set()
    for item in sorted(draws, key=lambda x: x["timestamp"], reverse=True):
        if item["id"] not in seen:
            seen.add(item["id"])
            result.append(item)
        if len(result) >= n:
            break
    return result


def load_draws(n):
    """Prvo OPAP (vise dana), a zatim GrKino ako OPAP nije dostupan."""
    collected = []
    warning = ""
    empty_days = 0
    today = datetime.now(ATHENS).date()
    days_to_check = min(180, max(10, math.ceil(n / 100) + 10))

    try:
        for offset in range(days_to_check):
            day = today - timedelta(days=offset)
            daily = fetch_opap_day(day.isoformat())
            if daily:
                empty_days = 0
                collected.extend(daily)
            else:
                empty_days += 1
                if empty_days >= 3:
                    break
            if len(collected) >= n:
                break
    except (requests.RequestException, ValueError, TypeError, KeyError, OverflowError) as e:
        warning = f"OPAP pristup nije potpuno uspeo: {e}"

    if collected:
        if warning:
            warning += " Prikazuju se samo vec preuzeti rezultati."
        return newest_unique(collected, n), "OPAP API", warning

    try:
        result = newest_unique(fetch_grkino_archive(), n)
        return result, "GrKino (rezervni izvor)", (
            "OPAP nije dostupan; rezervna arhiva mozda nema dovoljno rezultata "
            "za trazeni N. " + warning
        )
    except (requests.RequestException, ValueError) as e:
        return [], "", f"Nije moguce ucitati podatke: {e}. {warning}"


# ==============================================
# KOMBINACIJE
# ==============================================
def analyze_kino(draws, m, k):
    counter = Counter()
    for item in draws:
        for combo in combinations(sorted(item["numbers"]), m):
            counter[combo] += 1
    return sorted(((c, cnt) for c, cnt in counter.items() if cnt > k), key=lambda x: -x[1])


# ==============================================
# MATRICE
# ==============================================
def number_to_matrix_pos(num, cols):
    return (num - 1) // cols, (num - 1) % cols


def draw_single_matrix(numbers, rows, cols):
    matrix = np.zeros((rows, cols))
    for num in numbers:
        r, c = number_to_matrix_pos(num, cols)
        matrix[r, c] = 1
    return matrix


def matrix_analysis(draws, rows, cols, br, bc):
    overlay = np.zeros((rows, cols))
    counts = Counter()
    for item in draws:
        positions = {number_to_matrix_pos(n, cols) for n in item["numbers"]}
        for r, c in positions:
            overlay[r, c] += 1
        for rs in range(rows - br + 1):
            for cs in range(cols - bc + 1):
                block = {(rs + i, cs + j) for i in range(br) for j in range(bc)}
                counts[(rs, cs)] += len(block & positions)
    best, hits = counts.most_common(1)[0] if counts else (None, 0)
    return overlay, best, hits


def show_heatmap(matrix, rows, cols, labels=None, cmap="Reds", best=None, br=None, bc=None):
    fig, ax = plt.subplots(figsize=(max(8, cols), max(5, rows)))
    sns.heatmap(matrix, annot=labels if labels is not None else True,
                fmt="d" if labels is not None else ".0f", cmap=cmap, ax=ax,
                cbar=labels is None)
    if best is not None:
        ax.add_patch(plt.Rectangle((best[1], best[0]), bc, br,
                                   fill=False, edgecolor="blue", linewidth=3))
    st.pyplot(fig)
    plt.close(fig)


# ==============================================
# ZAJEDNICKA STATISTIKA POGODAKA
# ==============================================
def count_hits(draws, selected, minimum=5):
    picks = set(selected)
    exact = Counter()
    events = []
    last_seen = None

    # draws su vec poredjani od najnovijeg ka najstarijem.
    for index, item in enumerate(draws):
        matched = sorted(picks & set(item["numbers"]))
        hits = len(matched)
        exact[hits] += 1
        if hits >= minimum:
            if last_seen is None:
                last_seen = index
            events.append({
                "Izvlacenje (#1 najnovije)": index + 1,
                "Datum i vreme": item["date"],
                "Broj pogodaka": hits,
                "Pogodjeni brojevi": ", ".join(map(str, matched)),
            })
    return exact, last_seen, events


def parse_user_numbers(raw):
    tokens = [p for p in re.split(r"[,;\s]+", raw.strip()) if p]
    if not all(p.isdigit() for p in tokens):
        raise ValueError("Koristi samo cele brojeve od 1 do 80, odvojene zarezom ili razmakom.")
    numbers = [int(p) for p in tokens]
    if not 5 <= len(numbers) <= 10:
        raise ValueError("Unesi izmedju 5 i 10 brojeva.")
    if len(set(numbers)) != len(numbers):
        raise ValueError("Brojevi ne smeju da se ponavljaju.")
    if not all(1 <= n <= 80 for n in numbers):
        raise ValueError("Svi brojevi moraju biti od 1 do 80.")
    return sorted(numbers)


def show_event_table(events, filename):
    if events:
        data = pd.DataFrame(events)
        st.dataframe(data, hide_index=True, use_container_width=True)
        st.download_button("Preuzmi CSV", data=data.to_csv(index=False).encode("utf-8-sig"),
                           file_name=filename, mime="text/csv")
    else:
        st.info("Nema izvlacenja sa 5 ili vise pogodaka u ucitanom uzorku.")


# ==============================================
# APLIKACIJA
# ==============================================
st.title("🎯 Greek Kino Analyzer PRO")
option = st.radio("Izaberi analizu:", (
    "Kombinacije", "Heatmap analiza", "Vizuelni prikaz",
    "Overlay + statistika", "Ista jedinica (5+ pogodaka)", "Moji brojevi (5-10)"
))

N = st.number_input("Broj poslednjih izvlacenja (N)",
                    min_value=10, max_value=10000, value=200, step=50)

with st.spinner("Ucitavam istorijske rezultate..."):
    draws, source, message = load_draws(int(N))

if message:
    st.warning(message)
if not draws:
    st.error("Nema validnih izvlačenja. Proveri internet vezu ili izvor podataka.")
    st.stop()

st.caption(f"Izvor: {source} | Ucitano: {len(draws)} od trazenih {N} | "
           f"Najnovije: {draws[0]['date']} | Najstarije: {draws[-1]['date']}")
if len(draws) < N:
    st.warning(f"Dostupno je samo {len(draws)} izvlačenja, iako si tražio {N}. "
               "Sve statistike koriste stvarno ucitana izvlacenja.")

if option == "Kombinacije":
    M = st.number_input("M (velicina kombinacije)", 2, 10, 5)
    K = st.number_input("K (minimalan broj ponavljanja, iskljucivo veci od K)", 1, 20, 1)
    operations = len(draws) * math.comb(20, M)
    if operations > 8_000_000:
        st.warning(f"Analiza bi zahtevala oko {operations:,} kombinacija. "
                   "Smanji N ili M da aplikacija ne bi potrosila previse memorije.")
    if st.button("Analiziraj kombinacije"):
        if operations > 8_000_000:
            st.error("Preveliki zahtev za ovu vrstu analize. Smanji N ili M.")
        else:
            results = analyze_kino(draws, M, K)
            if results:
                st.dataframe(pd.DataFrame([
                    {"Kombinacija": ", ".join(map(str, c)), "Broj puta": cnt}
                    for c, cnt in results
                ]), hide_index=True, use_container_width=True)
            else:
                st.info("Nema kombinacija koje ispunjavaju uslov.")

elif option == "Heatmap analiza":
    rows = st.number_input("Redovi", 2, 20, 8)
    cols = st.number_input("Kolone", 2, 20, 10)
    br = st.number_input("Visina bloka", 1, rows, min(3, rows))
    bc = st.number_input("Sirina bloka", 1, cols, min(3, cols))
    if rows * cols < 80:
        st.error("Matrica mora da ima najmanje 80 polja.")
    elif st.button("Analiziraj heatmap"):
        overlay, best, hits = matrix_analysis(draws, rows, cols, br, bc)
        st.write(f"Najgusci blok ima ukupno {hits} pogodaka kroz sva izvlacenja.")
        show_heatmap(overlay, rows, cols, best=best, br=br, bc=bc)
        labels = np.arange(1, rows * cols + 1).reshape(rows, cols)
        show_heatmap(labels, rows, cols, labels=labels, cmap="Greys", best=best, br=br, bc=bc)

elif option == "Vizuelni prikaz":
    rows = st.number_input("Redovi", 2, 20, 8)
    cols = st.number_input("Kolone", 2, 20, 10)
    if rows * cols < 80:
        st.error("Matrica mora da ima najmanje 80 polja.")
    else:
        index = st.slider("Izvlacenje (1 = najnovije)", 1, len(draws), 1)
        st.write("Datum i vreme:", draws[index - 1]["date"])
        matrix = draw_single_matrix(draws[index - 1]["numbers"], rows, cols)
        labels = np.arange(1, rows * cols + 1).reshape(rows, cols)
        show_heatmap(matrix, rows, cols, labels=labels, cmap="Reds")

elif option == "Overlay + statistika":
    rows = st.number_input("Redovi", 2, 20, 8)
    cols = st.number_input("Kolone", 2, 20, 10)
    if rows * cols < 80:
        st.error("Matrica mora da ima najmanje 80 polja.")
    else:
        overlay = np.zeros((rows, cols))
        for item in draws:
            overlay += draw_single_matrix(item["numbers"], rows, cols)
        labels = np.arange(1, rows * cols + 1).reshape(rows, cols)
        show_heatmap(overlay, rows, cols, labels=labels, cmap="coolwarm")
        a, b, c = st.columns(3)
        a.metric("Max", int(overlay.max()))
        b.metric("Min", int(overlay.min()))
        c.metric("Prosek", f"{overlay.mean():.2f}")

elif option == "Ista jedinica (5+ pogodaka)":
    st.header("Statistika grupa sa istom jedinicom")
    st.write("Grupa 1: 1, 11, ... 71; grupa 2: 2, 12, ... 72; ... grupa 0: 10, 20, ... 80.")

    detailed = []
    summary = []
    history = []
    for unit in range(1, 11):
        nums = list(range(unit, 81, 10))
        group = "0" if unit == 10 else str(unit)
        exact, last_seen, events = count_hits(draws, nums, minimum=5)
        total = sum(exact[h] for h in range(5, 9))
        for hits in range(5, 9):
            detailed.append({"Grupa": group, "Brojevi": ", ".join(map(str, nums)),
                             "Tacno pogodaka": hits, "Broj puta": exact[hits]})
        summary.append({
            "Grupa": group, "Brojevi": ", ".join(map(str, nums)),
            "5 pogodaka": exact[5], "6 pogodaka": exact[6],
            "7 pogodaka": exact[7], "8 pogodaka": exact[8],
            "Ukupno 5+": total,
            "Udeo (%)": round(100 * total / len(draws), 2),
            "Proslo izvlacenja": last_seen if last_seen is not None else "Nije bilo",
        })
        for event in events:
            history.append({"Grupa": group, **event})

    df_detailed = pd.DataFrame(detailed)
    df_summary = pd.DataFrame(summary).sort_values("Ukupno 5+", ascending=False)

    st.subheader("Tacno 5, 6, 7 ili 8 pogodaka")
    if st.checkbox("Samo redovi sa najmanje jednim pojavljivanjem", value=True):
        df_detailed = df_detailed[df_detailed["Broj puta"] > 0]
    st.dataframe(df_detailed, hide_index=True, use_container_width=True)

    st.subheader("Rang-lista grupa")
    st.dataframe(df_summary, hide_index=True, use_container_width=True)
    st.caption("Proslo izvlacenja: 0 znaci najnovije izvlacenje. "
               "'Nije bilo' znaci da nije pronadjen nijedan slucaj sa 5+ u uzorku.")

    st.subheader("Grafikon pogodaka po grupama")
    chart = pd.DataFrame(summary).set_index("Grupa")[
        ["5 pogodaka", "6 pogodaka", "7 pogodaka", "8 pogodaka"]]
    st.bar_chart(chart)

    st.subheader("Istorija izvlačenja sa 5+ pogodaka")
    history.sort(key=lambda x: x["Izvlacenje (#1 najnovije)"])
    show_event_table(history, "kino_iste_jedinice.csv")

elif option == "Moji brojevi (5-10)":
    st.header("Statistika za tvoje brojeve")
    raw = st.text_input("Unesi 5 do 10 razlicitih brojeva (1-80)",
                        value="1, 11, 21, 31, 41, 51, 61, 71",
                        help="Brojeve odvoji zarezom, razmakom ili tacka-zarezom.")
    try:
        selected = parse_user_numbers(raw)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    st.write("Izabrani brojevi:", ", ".join(map(str, selected)))
    exact, last_seen, events = count_hits(draws, selected, minimum=5)
    total = len(events)
    a, b, c = st.columns(3)
    a.metric("Ukupno 5+", total)
    b.metric("Udeo izvlačenja sa 5+", f"{100 * total / len(draws):.2f}%")
    c.metric("Proslo od poslednjeg 5+", last_seen if last_seen is not None else "Nije bilo")

    st.subheader("Koliko puta je bilo tacno 5, 6, ... pogodaka")
    table = pd.DataFrame([
        {"Broj pogodaka": h, "Broj puta": exact[h],
         "Udeo (%)": round(100 * exact[h] / len(draws), 2)}
        for h in range(5, len(selected) + 1)
    ])
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.bar_chart(table.set_index("Broj pogodaka")["Broj puta"])

    with st.expander("Kompletna raspodela (0 do broja izabranih brojeva)"):
        all_hits = pd.DataFrame([
            {"Broj pogodaka": h, "Broj puta": exact[h]}
            for h in range(len(selected) + 1)
        ])
        st.dataframe(all_hits, hide_index=True, use_container_width=True)

    st.subheader("Istorija svih izvlačenja sa 5+ pogodaka")
    show_event_table(events, "kino_moji_brojevi.csv")

st.caption("Istorijska ucestalost ne predvidja naredno nezavisno KINO izvlacenje.")
