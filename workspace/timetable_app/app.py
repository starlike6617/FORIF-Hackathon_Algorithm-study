"""
Streamlit Timetable Wizard – modal‑free
• Robust column auto‑detect (key/title/prof/time)
• ET‑ratings merge → user‑weighted preference score
• Title search ⇒ 여러 분반(학수번호) 중 선택 UI
• Simple schedule builder (no clash check yet)
"""

# ────────────────── Imports ──────────────────
import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from itertools import product

# ────────────────── Page config ──────────────────
st.set_page_config(page_title="시간표 마법사", page_icon="🧭", layout="centered")

# ────────────────── Session init ──────────────────
ss = st.session_state
for key, default in {
    "groups":          [{"name": "그룹 1", "courses": []}],
    "required":        [],
    "constraints":     {"blocked_slots": set(), "must_lunch": False},
    "constraint_open": False,
    "catalog":         None,
    "weights":         {"과제": 1.0, "조모임": 1.0, "성적": 1.0},
    "search_df":       None,
    "search_target":   None,
}.items():
    ss.setdefault(key, default)

# ────────────────── Constants ──────────────────
PALETTE = ["#FDE2E2", "#FFF5CC", "#DFF6F5", "#E8E4FF"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
START, END = time(8, 0), time(22, 30)
RATING_COLS = ["성적 후함", "과제 적음", "조모임 적음"]
KEY_COL = "강좌ID"
NAME_COL = "교과목명"
PROF_COL = "교강사"
TIME_COL = "시간"
DISPLAY_COLS = [KEY_COL, NAME_COL, PROF_COL, TIME_COL] + RATING_COLS

# ────────────────── Catalog helpers ──────────────────

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if KEY_COL not in df.columns:
        if "학수번호-수업번호" in df.columns:
            df[KEY_COL] = df["학수번호-수업번호"].astype(str)
        elif {"학수번호", "분반"}.issubset(df.columns):
            df[KEY_COL] = df["학수번호"].astype(str) + "-" + df["분반"].astype(str)
        elif "학수번호" in df.columns:
            df[KEY_COL] = df["학수번호"].astype(str)
        else:
            df[KEY_COL] = df.index.astype(str)

    rename_map = {
        NAME_COL: ["교과목명", "과목명", "title"],
        PROF_COL: ["교강사", "담당교수", "교수명", "professor"],
        TIME_COL: ["시간", "수업시간", "시간표"],
    }
    for std, variants in rename_map.items():
        if std not in df.columns:
            for v in variants:
                if v in df.columns:
                    df = df.rename(columns={v: std}); break
        if std not in df.columns:
            df[std] = ""

    for col in RATING_COLS:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def load_catalog(files):
    frames = []
    for f in files:
        try:
            if f.name.endswith("xlsx"):
                df = pd.read_excel(f, dtype=str)
            else:
                sep = "\t" if f.name.endswith("tsv") else ","
                df = pd.read_csv(f, sep=sep, dtype=str)
            frames.append(_normalize_columns(df))
        except Exception as e:
            st.error(f"{f.name} 읽기 실패: {e}")
    if not frames:
        return
    ss.catalog = pd.concat(frames, ignore_index=True)
    update_preference_scores()
    st.success(f"✅ 편람 {len(frames)}개, {len(ss.catalog)}행 불러옴")

# ────────────────── Metric → preference ──────────────────

def compute_metric_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Flexible parsing: tolerate extra spaces/()% in column names."""
    df = df.copy()

    # helper to find matching column
    col_lookup = {}
    for col in df.columns:
        col_lookup[col.strip().replace(" ", "").replace("%", "")] = col

    def _get(col_alias: str):
        key = col_alias.replace(" ", "").replace("%", "")
        orig = col_lookup.get(key)
        if orig is None:
            df[col_alias] = 0  # create empty
            orig = col_alias
        df[orig] = pd.to_numeric(df[orig], errors="coerce").fillna(0)
        return df[orig]

    # 과제
    hw_none = _get("과제없음")
    hw_mid  = _get("과제보통")
    df["과제_score"] = (2*hw_none + 1*hw_mid) / 100
    # 조모임
    team_none = _get("조모임없음")
    team_mid  = _get("조모임보통")
    df["조모임_score"] = (2*team_none + 1*team_mid) / 100
    # 성적
    grade_easy = _get("성적너그러움")
    grade_mid  = _get("성적보통")
    df["성적_score"] = (2*grade_easy + 1*grade_mid) / 100

    return df


def update_preference_scores():
    if ss.catalog is None:
        return
    cat = compute_metric_scores(ss.catalog)
    w = ss.weights
    cat["_pref"] = w["과제"]*cat["과제_score"] + w["조모임"]*cat["조모임_score"] + w["성적"]*cat["성적_score"]
    ss.catalog = cat

# ────────────────── Recommendation & schedules ──────────────────

def get_recommendations(k=5):
    if ss.catalog is None:
        return pd.DataFrame()
    chosen = set(ss.required)
    for g in ss.groups:
        chosen.update(g["courses"])
    cat = ss.catalog[~ss.catalog[KEY_COL].astype(str).isin(chosen)]
    return cat.sort_values("_pref", ascending=False).head(k)[DISPLAY_COLS+["_pref"]]


def build_schedules(top_k=3):
    if ss.catalog is None:
        return []
    pref = ss.catalog.set_index(KEY_COL)["_pref"].to_dict()
    group_lists = [g["courses"] for g in ss.groups if g["courses"]]
    if not group_lists:
        return []
    combos = []
    for combo in product(*group_lists):
        score = sum(pref.get(c,0) for c in combo) + sum(pref.get(c,0) for c in ss.required)
        combos.append((score, combo))
    combos.sort(reverse=True, key=lambda x: x[0])
    return [(s, list(ss.required)+list(c)) for s,c in combos[:top_k]]

# ────────────────── Search helpers ──────────────────

def trigger_search(target:str, gi:int|None, key:str):
    if ss.catalog is None:
        st.warning("먼저 편람을 로드하세요"); return
    q = ss.get(key, "").strip()
    if not q:
        st.warning("검색어를 입력하세요"); return
    df = ss.catalog
    hits = df[df[KEY_COL].astype(str).str.contains(q, case=False, na=False) | df[NAME_COL].str.contains(q, case=False, na=False)]
    if hits.empty:
        st.info("일치하는 과목이 없습니다"); return
    ss.search_df = hits[DISPLAY_COLS+["_pref"]]
    ss.search_target = (target, gi)


def select_search_row(i:int):
    row = ss.search_df.iloc[i]; code = row[KEY_COL]
    tgt, gi = ss.search_target
    if tgt == "required":
        if code not in ss.required:
            ss.required.append(code)
    else:
        if code not in ss.groups[gi]["courses"]:
            ss.groups[gi]["courses"].append(code)
    ss.search_df = ss.search_target = None

# ────────────────── Sidebar – uploads & weights ──────────────────
st.sidebar.header("📂 편람 업로드")
files = st.sidebar.file_uploader("csv / tsv / xlsx", accept_multiple_files=True)
if st.sidebar.button("⬆️ 불러오기", disabled=not files):
    load_catalog(files)

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ 가중치 설정")
for k in ss.weights:
    ss.weights[k] = st.sidebar.number_input(k, value=float(ss.weights[k]), min_value=0.0)
if st.sidebar.button("✅ 재계산"):
    update_preference_scores()

# ────────────────── Required section ──────────────────
st.header("📌 필수 과목")
req_key = "req_input"
st.text_input("코드/강의명 입력", key=req_key)
st.button("🔍 검색", on_click=trigger_search, args=("required", None, req_key))
for code in ss.required:
    st.write("•", code)

st.markdown("---")

# ────────────────── Group cards ──────────────────
st.markdown("<style>.card{border-radius:12px;padding:1rem;margin-bottom:1rem;}</style>", unsafe_allow_html=True)
for gi, g in enumerate(ss.groups):
    bg = PALETTE[gi % len(PALETTE)]
    with st.container():
        st.markdown(f'<div class="card" style="background:{bg}">', unsafe_allow_html=True)
        g["name"] = st.text_input("그룹 이름", g["name"], key=f"gname_{gi}")
        for code in g["courses"]:
            st.write("•", code)
        inp = f"gquery_{gi}"
        st.text_input("코드/강의명 입력", key=inp)
        st.button("🔍 검색", key=f"gbtn_{gi}", on_click=trigger_search, args=("group", gi, inp))
        st.markdown("</div>", unsafe_allow_html=True)

if st.button("➕ 새 그룹"):
    ss.groups.append({"name": f"그룹 {len(ss.groups)+1}", "courses": []})

st.markdown("---")

# ────────────────── Search overlay ──────────────────
if ss.search_df is not None:
    st.subheader("검색 결과 – 과목 선택")
    for i, r in ss.search_df.reset_index(drop=True).iterrows():
        c = st.columns([5,2,2,1])
        c[0].write(f"{r[NAME_COL]} ({r[KEY_COL]})")
        c[1].write(r[PROF_COL])
        c[2].write(f"선호도 {r['_pref']:.2f}")
        c[3].button("선택", key=f"sel_{i}", on_click=select_search_row, args=(i,))
    st.button("❌ 닫기", on_click=lambda: (ss.pop("search_df",None), ss.pop("search_target",None)))

# ────────────────── Recommendations & schedules ──────────────────
if ss.catalog is not None:
    st.subheader("🌟 추천 강의 TOP5")
    st.dataframe(get_recommendations(), hide_index=True)

    st.subheader("🗓️ 시간표 제안")
    if st.button("생성"):
        schedules = build_schedules(3)
        if not schedules:
            st.info("필수/그룹 과목을 먼저 선택하세요")
        else:
            for i, (score, codes) in enumerate(schedules, 1):
                st.write(f"### 안 {i} – 합계 {score:.2f}")
                st.write(", ".join(codes))
else:
    st.info("먼저 편람을 업로드하세요")

# ────────────────── Constraint editor ──────────────────
if st.button("⏲️ 제약조건 설정"):
    ss.constraint_open = True
if ss.constraint_open:
    with st.expander("요일/30분 단위 제약조건", True):
        hdr = st.columns(len(DAYS) + 1)
        hdr[0].markdown("**Time**")
        for j, d in enumerate(DAYS):
            hdr[j+1].markdown(f"**{d}")
        slots, cur = [], START
        while cur <= END:
            slots.append(cur.strftime("%H:%M"))
            cur = (datetime.combine(date.today(), cur) + timedelta(minutes=30)).time()
        for t in slots:
            row = st.columns(len(DAYS) + 1)
            row[0].write(t)
            for j, d in enumerate(DAYS):
                key = f"{d}_{t}"
                ch = key in ss.constraints["blocked_slots"]
                if row[j+1].checkbox("", ch, key=key):
                    ss.constraints["blocked_slots"].add(key)
                else:
                    ss.constraints["blocked_slots"].discard(key)
        ss.constraints["must_lunch"] = st.checkbox("12-13시 점심 비우기", value=ss.constraints["must_lunch"])
        if st.button("✅ 저장/닫기"):
            ss.constraint_open = False

# ────────────────── Debug ──────────────────
with st.expander("🪛 디버그", False):
    st.json({k: str(v)[:200] for k, v in ss.items()})
