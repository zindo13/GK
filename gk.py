import streamlit as st
import requests
from bs4 import BeautifulSoup
from itertools import combinations
from collections import Counter

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
# ANALYSIS
# =====================
def analyze_kino(draws, M, K):
    counter = Counter()
    for draw in draws:
        for combo in combinations(sorted(draw), M):
            counter[combo] += 1
    return [(c, cnt) for c, cnt in counter.items() if cnt > K]

# =====================
# STREAMLIT GUI
# =====================
st.title("Greek Kino Analyzer")

N = st.number_input("Broj poslednjih izvlačenja (N)", min_value=10, max_value=200, value=50)
M = st.number_input("Veličina kombinacije (M)", min_value=2, max_value=10, value=5)
K = st.number_input("Minimalno ponavljanje kombinacije (K)", min_value=1, max_value=10, value=1)

if st.button("Analyze"):
    st.info("Učitavam podatke sa grkino.com...")
    try:
        draws = fetch_kino_results("https://grkino.com/arhiva.php", N)
        result = analyze_kino(draws, M, K)
    except Exception as e:
        st.error(f"Došlo je do greške: {e}")
        result = []

    if not result:
        st.warning("Nema kombinacija koje zadovoljavaju uslov.")
    else:
        st.success(f"Pronađeno {len(result)} kombinacija")
        for combo, count in sorted(result, key=lambda x: -x[1]):
            st.write(f"{combo} -> {count} puta")