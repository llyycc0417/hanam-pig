import streamlit as st
import pandas as pd
import pulp
import requests
import io
import re
import time

# 1. 시트 ID 설정 (유찬, 네 시트 ID로 꼭 바꿔!)
SHEET_ID = '1w_BHaPFVSDITINM-QhTSEa9H2VXPO3m-KiFblP3z02Y'

st.set_page_config(page_title="하남돼지집 조종실", layout="wide")
st.title("🔥 하남돼지집 차주 스케줄 조종실")

# 2. 매니저 설정 (사이드바)
st.sidebar.header("🛠️ 매니저 설정")
peak_cap = st.sidebar.slider("6시 이후 필요 인원", 1, 5, 3)

# 3. 데이터 로드
def load_data():
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&t={int(time.time())}'
    res = requests.get(url)
    df = pd.read_csv(io.BytesIO(res.content))
    df.columns = df.columns.str.strip()
    name_col, time_col = df.columns[1], df.columns[0]
    df[name_col] = df[name_col].astype(str).str.strip()
    return df.sort_values(time_col).drop_duplicates(name_col, keep='last'), name_col

if st.button("🚀 스케줄 생성하기", use_container_width=True):
    df, name_col = load_data()
    days = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    workers = df[name_col].tolist()
    
    # 최적화 로직 (우리가 만든 거랑 똑같음)
    prob = pulp.LpProblem("Hanam", pulp.LpMaximize)
    slots = [3, 4, 5, 6]
    choices = [(w, d, s) for d in days for s in slots for w in workers]
    x = pulp.LpVariable.dicts("x", choices, cat='Binary')
    
    avail = {}
    for _, row in df.iterrows():
        name = row[name_col]
        avail[name] = {d: (int(re.findall(r'\d+', str(row[d]))[0]) if re.findall(r'\d+', str(row[d])) else None) for d in days}

    prob += pulp.lpSum([(1000 - (s - avail[w][d])*10) * x[(w, d, s)] for w, d, s in choices if avail[w][d] is not None and s >= avail[w][d]])

    for d in days:
        for s in slots:
            cap = peak_cap if s >= 6 else 1
            prob += pulp.lpSum(x[(w, d, s)] for w in workers) <= cap
    for w in workers:
        for d in days:
            prob += pulp.lpSum(x[(w, d, s)] for s in slots) <= 1
    for w, d, s in choices:
        if avail[w][d] is None or s < avail[w][d]:
            prob += x[(w, d, s)] == 0

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    # 화면에 예쁘게 뿌리기
    cols = st.columns(7)
    for i, d in enumerate(days):
        with cols[i]:
            st.subheader(d)
            for s in slots:
                res = [w for w in workers if pulp.value(x[(w, d, s)]) > 0.5]
                if res: st.success(f"**{s}시**: {', '.join(res)}")
                else: st.error(f"**{s}시**: 인원부족")
