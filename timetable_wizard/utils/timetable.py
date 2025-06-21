import pandas as pd

def generate_timetables(groups, constraints, top_k=3):
    """지금은 빈 시간표 더미 DataFrame만 돌려준다."""
    dummy = pd.DataFrame(
        {
            "과목": ["PLACEHOLDER"],
            "월": ["10:00-11:30"],
            "화": [""],
            "수": [""],
            "목": [""],
            "금": [""],
        }
    )
    return [dummy] * top_k

