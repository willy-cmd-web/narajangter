import requests
import pandas as pd
import streamlit as st
import os
from datetime import datetime, timedelta

API_KEY = os.environ.get("API_KEY", "")
URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getThptyUcntrctPrdctInfoList"
MAS_URL = "http://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getMASCntrctPrdctInfoList"

def get_all_data(품명):
    all_items = []
    페이지 = 1
    progress = st.empty()
    while True:
        params = {
            "ServiceKey": API_KEY,
            "numOfRows": 100,
            "pageNo": 페이지,
            "prdctClsfcNoNm": 품명,
            "type": "json"
        }
        res = requests.get(URL, params=params)
        data = res.json()
        body = data["response"]["body"]
        total = int(body.get("totalCount", 0))
        items = body.get("items", [])
        if total == 0 or not items:
            break
        if isinstance(items, dict):
            items = [items]
        all_items.extend(items)
        progress.info(f"데이터 수집 중... {len(all_items)} / {total} 건")
        if len(all_items) >= total:
            break
        페이지 += 1
    progress.empty()
    return all_items, total

def get_mas_업체목록(품명):
    params = {
        "ServiceKey": API_KEY,
        "numOfRows": 1,
        "pageNo": 1,
        "prdctClsfcNoNm": 품명,
        "type": "json"
    }
    res = requests.get(MAS_URL, params=params)
    data = res.json()
    body = data["response"]["body"]
    total = int(body.get("totalCount", 0))
    if total == 0:
        return set()
    params["numOfRows"] = total
    res = requests.get(MAS_URL, params=params)
    data = res.json()
    items = data["response"]["body"].get("items", [])
    if isinstance(items, dict):
        items = [items]
    st.write(f"첫번째 아이템 전체 필드: {items[0]}")
    filtered = [item for item in items if 품명 in item.get("prdctClsfcNoNm", "")]
    return set(item.get("cntrctCorpNm", "") for item in filtered)
    
def 데이터정리(items):
    결과 = []
    for item in items:
        결과.append({
            "업체명":     item.get("cntrctCorpNm", ""),
            "기업구분":   item.get("entrprsDivNm", ""),
            "제품규격":   item.get("prdctSpecNm", ""),
            "단가(원)":   item.get("cntrctPrceAmt", ""),
            "단위":       item.get("prdctUnit", ""),
            "우수제품":   item.get("exclncPrcrmntPrdctYn", ""),
            "계약시작일": item.get("cntrctBgnDate", ""),
            "계약종료일": item.get("cntrctEndDate", ""),
            "제조사":     item.get("prdctMakrNm", ""),
            "인증정보":   item.get("qltyRltnCertInfo", ""),
        })
    return 결과

def 하이라이트(row):
    styles = [""] * len(row)
    cols = list(row.index)

    if "아키페이스" in str(row["업체명"]):
        styles = ["background-color: #fff9c4"] * len(row)

    try:
        종료일 = datetime.strptime(str(row["계약종료일"]), "%Y-%m-%d")
        if 종료일 <= datetime.now() + timedelta(days=365):
            idx = cols.index("계약종료일")
            styles[idx] = "color: red; font-weight: bold"
    except:
        pass

    return styles

st.set_page_config(page_title="나라장터 우수제품 조회", layout="wide")
st.title("🏢 나라장터 우수제품 지정업체 조회")

품명 = st.text_input("세부품명 입력", placeholder="예: 합성목재, 기타조경시설물")

if st.button("🔍 조회", type="primary"):
    if not 품명.strip():
        st.warning("품명을 입력해주세요.")
    else:
        with st.spinner("조회 중..."):
            items, total = get_all_data(품명.strip())

        if total == 0:
            st.error(f"'{품명}' 검색 결과가 없습니다.")
        else:
            df = pd.DataFrame(데이터정리(items))
            # MAS 업체 수 계산 (필터 전)
            mas_업체목록 = get_mas_업체목록(품명.strip())
            우수_업체목록 = set(df[df["우수제품"] == "Y"]["업체명"].unique())
            우수_업체수 = len(우수_업체목록)
            mas_업체수 = len(mas_업체목록)
            전체_업체수 = len(우수_업체목록 | mas_업체목록)
            우수_업체수 = df[df["우수제품"] == "Y"]["업체명"].nunique()
            전체_업체수 = 우수_업체수 + mas_업체수

            # 요약 카드
            col1, col2, col3 = st.columns(3)
            col1.metric("🏆 우수제품 업체", f"{우수_업체수}개")
            col2.metric("🏪 MAS 업체", f"{mas_업체수}개")
            col3.metric("📊 전체 업체", f"{전체_업체수}개")

            df = df[df["우수제품"] == "Y"]

            if df.empty:
                st.warning("우수제품 지정 업체가 없습니다.")
            else:
                요약 = df.groupby(["업체명", "기업구분"]).agg(
                    제품수=("제품규격", "count"),
                    제조사=("제조사", lambda x: ", ".join(x.dropna().unique())),
                    인증정보=("인증정보", lambda x: ", ".join(x.dropna().unique())),
                    계약시작일=("계약시작일", "min"),
                    계약종료일=("계약종료일", "max"),
                ).reset_index()

                요약 = 요약[["업체명", "기업구분", "제품수", "제조사", "인증정보", "계약시작일", "계약종료일"]]
                요약 = 요약.sort_values("계약종료일").reset_index(drop=True)
                요약.insert(0, "No", range(1, len(요약) + 1))

                st.success(f"총 {len(요약)}개 우수제품 업체 조회 완료")
                st.dataframe(
                    요약.style.apply(하이라이트, axis=1),
                    use_container_width=True,
                    hide_index=True
                )

                import io
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    요약.to_excel(writer, sheet_name="업체별요약", index=False)
                    df.to_excel(writer, sheet_name="전체상세", index=False)
                st.download_button(
                    label="📥 엑셀 저장",
                    data=buf.getvalue(),
                    file_name=f"나라장터_{품명}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
