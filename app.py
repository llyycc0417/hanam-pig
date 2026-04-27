import streamlit as st
import pandas as pd
import pulp
import requests
import io
import re
import time

# 웹페이지 설정
st.set_page_config(page_title="하남돼지집 조종실", layout="wide")

# 1. 시트 ID 설정 (캡틴의 시트 ID로 확인!)
SHEET_ID = '1w_BHaPFVSDITINM-QhTSEa9H2VXPO3m-KiFblP3z02Y' 

st.title("🔥 하남돼지집 차주 스케줄 조종실")

# 2. 데이터 로드 함수
def load_data():
    url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&t={int(time.time())}'
    res = requests.get(url)
    df = pd.read_csv(io.BytesIO(res.content))
    df.columns = df.columns.str.strip()
    name_col, time_col = df.columns[1], df.columns[0]
    df[name_col] = df[name_col].astype(str).str.strip()
    return df.sort_values(time_col).drop_duplicates(name_col, keep='last'), name_col

# 데이터 먼저 불러오기 (가중치 설정을 위해)
try:
    df, name_col = load_data()
    workers = sorted(df[name_col].unique())
except:
    st.error("구글 시트를 불러올 수 없습니다. ID를 확인해주세요.")
    st.stop()

# 3. 매니저 설정 (사이드바)
st.sidebar.header("🛠️ 매니저 조종실")
peak_cap = st.sidebar.slider("6시 이후 필요 인원", 1, 5, 3)

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ 알바생별 가중치 설정")
st.sidebar.caption("숫자가 높을수록 우선 배정됩니다.")

# 개별 가중치 입력창 생성 (기본값은 모두 1)
user_weights = {}
for w in workers:
    user_weights[w] = st.sidebar.number_input(f"{w}의 가중치", min_value=1, max_value=100, value=1, step=1)

# 4. 스케줄 생성 실행
if st.button("🚀 최적 스케줄 자동 생성", use_container_width=True):
    days = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    
    prob = pulp.LpProblem("Hanam_Dynamic_Priority", pulp.LpMaximize)
    slots = [3, 4, 5, 6]
    choices = [(w, d, s) for d in days for s in slots for w in workers]
    x = pulp.LpVariable.dicts("x", choices, cat='Binary')
    
    # 가능 시간 추출
    avail = {}
    for _, row in df.iterrows():
        name = row[name_col]
        avail[name] = {d: (int(re.findall(r'\d+', str(row[d]))[0]) if re.findall(r'\d+', str(row[d])) else None) for d in days}

    # 목적 함수: (사이드바에서 입력한 가중치) * (희망시간 점수)
    score_items = []
    for w, d, s in choices:
        min_t = avail[w].get(d)
        if min_t is not None and s >= min_t:
            # 설정된 가중치를 곱함
            match_score = (1000 - (s - min_t) * 10) * user_weights[w]
            score_items.append(match_score * x[(w, d, s)])
    prob += pulp.lpSum(score_items)

    # 제약 조건
    for d in days:
        for s in slots:
            cap = peak_cap if s >= 6 else 1
            prob += pulp.lpSum(x[(w, d, s)] for w in workers) <= cap
    for w in workers:
        for d in days:
            prob += pulp.lpSum(x[(w, d, s)] for s in slots) <= 1
    for w, d, s in choices:
        min_t = avail[w].get(d)
        if min_t is None or s < min_t:
            prob += x[(w, d, s)] == 0

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    # 결과 출력
    cols = st.columns(7)
    for i, d in enumerate(days):
        with cols[i]:
            st.subheader(d)
            for s in slots:
                res = [w for w in workers if pulp.value(x[(w, d, s)]) > 0.5]
                if res: st.success(f"**{s}시**: {', '.join(res)}")
                else: st.error(f"**{s}시**: 인원부족")