import streamlit as st
import pandas as pd

st.title("🗓️  추천 시간표")

if not st.session_state.get("timetable_suggestions"):
    st.warning("먼저 조건을 입력해 주세요!")
    if st.button("조건 입력으로"):
        st.switch_page("app.py")
    st.stop()

for i, df in enumerate(st.session_state.timetable_suggestions, 1):
    st.subheader(f"추천안 #{i}")
    st.dataframe(df, hide_index=True)

