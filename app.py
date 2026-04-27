import streamlit as st
import pandas as pd
import pulp
import requests
import io
import re
import time

# 웹페이지 설정
st.set_page_config(page_title="하남돼지집 조종실", layout="wide")

# 1. 시트 ID 설정 (이 부분에 유찬 캡틴의 ID를 정확히 넣어줘!)
SHEET_ID = '1w_BHaPFVSDITINM-QhTSEa9H2VXPO3m-KiFblP3z02Y' 

st.title("🔥 하남돼지집 차주 스케줄 조종실")

# 2. 데이터 로드 함수
def load_data(sheet_id):
    try:
        # t=time.time()을 붙여서 구글 시트의 최신 데이터를 강제로 새로고침함
        url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&t={int(time.time())}'
        res = requests.get(url)
        res.raise_for_status() # 에러 발생 시 예외 처리
        df = pd.read_csv(io.BytesIO(res.content))
        df.columns = df.columns.str.strip()
        name_col = df.columns[1]
        time_col = df.columns[0]
        df[name_col] = df[name_col].astype(str).str.strip()
        return df.sort_values(time_col).drop_duplicates(name_col, keep='last'), name_col
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return None, None

# 3. 데이터 먼저 시도
df, name_col = load_data(SHEET_ID)

if df is not None:
    workers = sorted(df[name_col].unique())

    # 사이드바 설정
    st.sidebar.header("🛠️ 매니저 조종실")
    peak_cap = st.sidebar.slider("6시 이후 필요 인원", 1, 5, 3)

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚖️ 알바생별 가중치 설정")
    
    # 개별 가중치 입력창 생성
    user_weights = {}
    for w in workers:
        user_weights[w] = st.sidebar.number_input(f"{w}의 가중치", min_value=1, max_value=100, value=1, step=1)

    # 4. 스케줄 생성 실행
    if st.button("🚀 최적 스케줄 자동 생성", use_container_width=True):
        days = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        prob = pulp.LpProblem("Hanam_Final", pulp.LpMaximize)
        slots = [3, 4, 5, 6]
        choices = [(w, d, s) for d in days for s in slots for w in workers]
        x = pulp.LpVariable.dicts("x", choices, cat='Binary')
        
        avail = {}
        for _, row in df.iterrows():
            name = row[name_col]
            avail[name] = {d: (int(re.findall(r'\d+', str(row[d]))[0]) if re.findall(r'\d+', str(row[d])) else None) for d in days}

        score_items = []
        for w, d, s in choices:
            min_t = avail[w].get(d)
            if min_t is not None and s >= min_t:
                match_score = (1000 - (s - min_t) * 10) * user_weights[w]
                score_items.append(match_score * x[(w, d, s)])
        prob += pulp.lpSum(score_items)

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

        cols = st.columns(7)
        for i, d in enumerate(days):
            with cols[i]:
                st.subheader(d)
                for s in slots:
                    res = [w for w in workers if pulp.value(x[(w, d, s)]) > 0.5]
                    if res: st.success(f"**{s}시**: {', '.join(res)}")
                    else: st.error(f"**{s}시**: 인원부족")
else:
    st.warning("스프레드시트에서 데이터를 읽어오지 못했습니다. ID와 공유 설정을 확인해주세요.")