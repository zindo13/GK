import streamlit as st
import requests
from bs4 import BeautifulSoup
from itertools import combinations
from collections import Counter
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# =====================
# FETCH DATA
# =====================
def fetch_kino_results(url, max_draws):
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    draws = []
    sections = soup.text.split("Extragere")[1:]

    for section in sections[:max_draws]:
        lines = [l.strip() for l in section.split("\n") if l.strip()]
        nums = []
        for line in lines[1:]:
            for p in line.split():
                if p.isdigit():
                    nums.append(int(p))
        if len(nums) == 20:
            draws.append(nums)

    return draws

# =====================
# COMBINATIONS
# =====================
def analyze_kino(draws, M, K):
    counter = Counter()
    for draw in draws:
        for combo in combinations(sorted(draw), M):
            counter[combo] += 1
    return [(c, cnt) for c, cnt in counter.items() if cnt > K]

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
    heatmap_numbers = np.arange(1, rows*cols+1).reshape(rows, cols)

    for draw in draws:
        positions = [number_to_matrix_pos(n, rows, cols) for n in draw]

        for r, c in positions:
            heatmap_counts[r, c] += 1

        for rs in range(rows - br + 1):
            for cs in range(cols - bc + 1):
                block = [(rs+i, cs+j) for i in range(br) for j in range(bc)]
                hits = sum(1 for p in positions if p in block)
                counts[(rs, cs)] += hits

    max_block, max_hits = counts.most_common(1)[0] if counts else (None, 0)
    return heatmap_counts, heatmap_numbers, max_block, max_hits

# =====================
# STREAMLIT
# =====================
st.title("🎯 Greek Kino Analyzer PRO")

option = st.radio("Izaberi analizu:",
    ("Kombinacije", "Heatmap analiza", "Vizuelni prikaz", "Overlay + statistika"))

N = st.number_input("Broj poslednjih izvlačenja", 10, 200, 50)

st.info("Učitavam podatke...")
draws = fetch_kino_results("https://grkino.com/arhiva.php", N)

if not draws:
    st.warning("Nema podataka")
    st.stop()

# =====================
# 1. KOMBINACIJE
# =====================
if option == "Kombinacije":
    M = st.number_input("M (veličina kombinacije)", 2, 10, 5)
    K = st.number_input("K (min ponavljanja)", 1, 10, 1)

    if st.button("Analyze"):
        result = analyze_kino(draws, M, K)
        for combo, count in sorted(result, key=lambda x: -x[1]):
            st.write(combo, "->", count)

# =====================
# 2. HEATMAP
# =====================
elif option == "Heatmap analiza":
    rows = st.number_input("Redovi", 2, 20, 8)
    cols = st.number_input("Kolone", 2, 20, 10)
    br = st.number_input("Visina bloka", 1, rows, 3)
    bc = st.number_input("Širina bloka", 1, cols, 3)

    if st.button("Analyze heatmap"):
        heatmap_counts, heatmap_numbers, max_block, max_hits = matrix_analysis(draws, rows, cols, br, bc)

        fig, ax = plt.subplots(figsize=(cols, rows))
        sns.heatmap(heatmap_counts, annot=True, fmt=".0f", cmap="Reds", ax=ax)

        if max_block:
            rect = plt.Rectangle((max_block[1], max_block[0]), bc, br,
                                 fill=False, edgecolor='blue', linewidth=3)
            ax.add_patch(rect)
            st.write(f"Najgušći blok: {max_hits} pogodaka")

        st.pyplot(fig)

        # brojevi
        fig2, ax2 = plt.subplots(figsize=(cols, rows))
        sns.heatmap(heatmap_numbers, annot=True, fmt="d", cmap="Greys", ax=ax2)

        if max_block:
            rect2 = plt.Rectangle((max_block[1], max_block[0]), bc, br,
                                  fill=False, edgecolor='blue', linewidth=3)
            ax2.add_patch(rect2)

        st.pyplot(fig2)

# =====================
# 3. VIZUELNI PRIKAZ
# =====================
elif option == "Vizuelni prikaz":
    rows = st.number_input("Redovi", 2, 20, 8)
    cols = st.number_input("Kolone", 2, 20, 10)

    index = st.slider("Izvlačenje", 1, len(draws), 1)

    matrix = draw_single_matrix(draws[index-1], rows, cols)

    numbers = np.arange(1, rows*cols+1).reshape(rows, cols)

    fig, ax = plt.subplots(figsize=(cols, rows))
    sns.heatmap(matrix, annot=numbers, fmt="d", cmap="Reds", cbar=False, ax=ax)

    st.pyplot(fig)

# =====================
# 4. OVERLAY + STATISTIKA
# =====================
elif option == "Overlay + statistika":
    rows = st.number_input("Redovi", 2, 20, 8)
    cols = st.number_input("Kolone", 2, 20, 10)

    overlay = np.zeros((rows, cols))

    for draw in draws:
        for num in draw:
            r, c = number_to_matrix_pos(num, rows, cols)
            overlay[r, c] += 1

    numbers = np.arange(1, rows*cols+1).reshape(rows, cols)

    fig, ax = plt.subplots(figsize=(cols, rows))
    sns.heatmap(overlay, annot=numbers, fmt="d", cmap="coolwarm", ax=ax)

    st.pyplot(fig)

    st.write("📊 Statistika:")
    st.write("Max:", int(np.max(overlay)))
    st.write("Min:", int(np.min(overlay)))
    st.write("Prosek:", float(np.mean(overlay)))
