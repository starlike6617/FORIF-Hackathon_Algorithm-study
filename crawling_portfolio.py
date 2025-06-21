from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import time
import requests

driver = webdriver.Chrome()

# 1. 포털 로그인
driver.get("https://portal.hanyang.ac.kr/sso/lgin.do")
driver.find_element(By.NAME, "userId").send_keys("id")
driver.find_element(By.NAME, "password").send_keys("pw" + Keys.RETURN)
time.sleep(3)

# 2. 과목 조회 페이지 진입
driver.get(
    "https://portal.hanyang.ac.kr/port.do#!UDMyMDMxNiRAXmhha3NhLyRAXjAkQF5NMzE5NDc3JEBe6rWQ6rO866qp7Y+s7Yq47Y+066as7JikJEBeTTAwMzc5NCRAXjJmMTEwMmViM2MyZjMyYjY3NzMxYjg5M2E1ODc4NTI0ODBhNTA2NDljNmNmN2M5M2ZmMGQ4MTYwZmE2ZmVkYjc="
)
time.sleep(3)

# 3. 캠퍼스 선택
Select(driver.find_element(By.ID, "cbCampus")).select_by_visible_text("대학(학부/서울)")

# 4. 학과 리스트
target_departments = [
    "산업공학과",
    "도시공학과",
    "전기·생체공학부",
    "건축공학부",
    "유기나노공학과",
    "에너지공학과",
    "기계공학부",
    "생명공학과",
    "건설환경공학과",
    "융합전자공학부",
    "정보시스템학과",
    "건축학부",
    "컴퓨터소프트웨어학부",
    "신소재공학부",
    "화학공학과",
    "데이터사이언스학부",
]

# 5. 중복 학수번호 방지용 Set
processed_haksu_numbers = set()

for department in target_departments:
    try:
        Select(driver.find_element(By.ID, "cbHakgwa")).select_by_visible_text(
            department
        )
        driver.find_element(By.ID, "btn_Find").click()
        time.sleep(3)

        main_window = driver.current_window_handle
        rows = driver.find_elements(By.CSS_SELECTOR, "#gdMain > tbody > tr")

        for i, tr in enumerate(rows, 1):
            try:
                num = tr.find_element(By.CSS_SELECTOR, "#haksuNo").text.strip()
                name = tr.find_element(By.CSS_SELECTOR, "#gwamokNm").text.strip()

                # 이미 처리한 학수번호 건너뛰기
                if num in processed_haksu_numbers:
                    print(f"⚠️ 중복 감지: {num} - {name} → 건너뜀")
                    continue
                processed_haksu_numbers.add(num)

                haksu_elem = tr.find_element(By.CSS_SELECTOR, "td:nth-child(1)")
                driver.execute_script("arguments[0].scrollIntoView();", haksu_elem)
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(haksu_elem)
                ).click()

                # 첫 번째 팝업 기다림
                WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
                popup1 = [w for w in driver.window_handles if w != main_window][0]
                driver.switch_to.window(popup1)

                # 리포트출력 탭 클릭
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            "#ggpf0200Chart > div:nth-child(9) > a:nth-child(2)",
                        )
                    )
                ).click()

                # 두 번째 팝업 기다림
                WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(3))
                popup2 = [
                    w for w in driver.window_handles if w not in [main_window, popup1]
                ][0]
                driver.switch_to.window(popup2)

                # PDF 다운로드
                try:
                    pdf_embed = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.TAG_NAME, "embed"))
                    )
                    pdf_url = pdf_embed.get_attribute("src")
                    print("📎 PDF URL:", pdf_url)

                    session = requests.Session()
                    for cookie in driver.get_cookies():
                        session.cookies.set(cookie["name"], cookie["value"])

                    res = session.get(pdf_url)
                    with open(f"{num}_{name}.pdf", "wb") as f:
                        f.write(res.content)
                    print("✅ PDF 저장 완료")

                except Exception as e:
                    print("❌ PDF 추출 실패:", e)

                # 창 닫기 순서
                driver.close()  # 팝업2
                driver.switch_to.window(popup1)
                driver.close()  # 팝업1
                driver.switch_to.window(main_window)

            except Exception as e:
                print(f"{department} {i}번째 row 처리 실패: {e}")

    except Exception as e:
        print(f"{department} 선택 실패: {e}")
