import streamlit as st
import requests
from bs4 import BeautifulSoup
from itertools import combinations
from collections import Counter
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# =====================
# FETCH KINO DATA
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
# ANALYSIS: COMBINATIONS
# =====================
def analyze_kino(draws, M, K):
    counter = Counter()
    for draw in draws:
        for combo in combinations(sorted(draw), M):
            counter[combo] += 1
    return [(c, cnt) for c, cnt in counter.items() if cnt > K]

# =====================
# ANALYSIS: MATRIX
# =====================
def number_to_matrix_pos(num, total_rows, total_cols):
    row = (num - 1) // total_cols
    col = (num - 1) % total_cols
    return row, col

def matrix_analysis(draws, n_rows, n_cols, block_rows, block_cols):
    max_row_start = n_rows - block_rows + 1
    max_col_start = n_cols - block_cols + 1
    counts = Counter()

    # Heatmap po broju izvlačenja
    heatmap_counts = np.zeros((n_rows, n_cols), dtype=int)
    # Heatmap sa brojevima 1-80
    heatmap_numbers = np.arange(1, n_rows*n_cols+1).reshape((n_rows, n_cols))

    for draw in draws:
        positions = [number_to_matrix_pos(n, n_rows, n_cols) for n in draw]
        for pos in positions:
            heatmap_counts[pos] += 1

        for r_start in range(max_row_start):
            for c_start in range(max_col_start):
                block = [(r_start + dr, c_start + dc)
                         for dr in range(block_rows)
                         for dc in range(block_cols)]
                hits = sum(1 for pos in positions if pos in block)
                counts[(r_start, c_start)] += hits

    # Najgušći blok
    if counts:
        max_block, max_hits = counts.most_common(1)[0]
    else:
        max_block, max_hits = None, 0

    return heatmap_counts, heatmap_numbers, max_block, max_hits

# =====================
# STREAMLIT GUI
# =====================
st.title("Greek Kino Analyzer - Heatmap Edition")

option = st.radio("Izaberi tip analize:", ("Najčešće kombinacije", "Matrica/Heatmap"))

# Parametri
N = st.number_input("Broj poslednjih izvlačenja (N)", min_value=10, max_value=200, value=50)

st.info("Učitavam podatke sa grkino.com...")
try:
    draws = fetch_kino_results("https://grkino.com/arhiva.php", N)
except Exception as e:
    st.error(f"Došlo je do greške: {e}")
    draws = []

if not draws:
    st.warning("Nema podataka za analizu.")
    st.stop()

if option == "Najčešće kombinacije":
    M = st.number_input("Veličina kombinacije (M)", min_value=2, max_value=10, value=5)
    K = st.number_input("Minimalno ponavljanje kombinacije (K)", min_value=1, max_value=10, value=1)

    if st.button("Analyze combinations"):
        result = analyze_kino(draws, M, K)
        if not result:
            st.warning("Nema kombinacija koje zadovoljavaju uslov.")
        else:
            st.success(f"Pronađeno {len(result)} kombinacija")
            for combo, count in sorted(result, key=lambda x: -x[1]):
                st.write(f"{combo} -> {count} puta")

elif option == "Matrica/Heatmap":
    n_rows = st.number_input("Broj redova matrice", min_value=2, max_value=20, value=8)
    n_cols = st.number_input("Broj kolona matrice", min_value=2, max_value=20, value=10)
    block_rows = st.number_input("Visina bloka", min_value=1, max_value=n_rows, value=3)
    block_cols = st.number_input("Širina bloka", min_value=1, max_value=n_cols, value=3)

    if st.button("Analyze matrix"):
        heatmap_counts, heatmap_numbers, max_block, max_hits = matrix_analysis(
            draws, n_rows, n_cols, block_rows, block_cols
        )

        st.write("**Heatmap: broj puta koliko je svaki broj izlazio**")
        fig, ax = plt.subplots(figsize=(n_cols, n_rows))
        sns.heatmap(heatmap_counts, annot=True, fmt="d", cmap="Reds", cbar=True, linewidths=.5, ax=ax)

        # Obeleži najgušći blok
        if max_block:
            rect = plt.Rectangle((max_block[1], max_block[0]), block_cols, block_rows,
                                 fill=False, edgecolor='blue', linewidth=3)
            ax.add_patch(rect)
            st.write(f"Najgušći blok {block_rows}x{block_cols} počinje na R{max_block[0]+1} C{max_block[1]+1}, ukupno {max_hits} izlazaka")

        st.pyplot(fig)

        st.write("**Heatmap: brojevi 1-80**")
        fig2, ax2 = plt.subplots(figsize=(n_cols, n_rows))
        sns.heatmap(heatmap_numbers, annot=True, fmt="d", cmap="Greys", linewidths=.5, ax=ax2)

        # Obeleži isti najgušći blok
        if max_block:
            rect2 = plt.Rectangle((max_block[1], max_block[0]), block_cols, block_rows,
                                  fill=False, edgecolor='blue', linewidth=3)
            ax2.add_patch(rect2)

        st.pyplot(fig2)
