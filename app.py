import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

# -------------------------------------------------------------------
# 페이지 기본 설정
# -------------------------------------------------------------------
st.set_page_config(
    page_title="온실가스 인벤토리 관리 시스템 (EcoScope)",
    page_icon="🌱",
    layout="wide"
)

# -------------------------------------------------------------------
# 세션 상태(Session State) 초기화
# -------------------------------------------------------------------
# 1. 배출계수 마스터 테이블 (기본값: IPCC AR5 및 국가 고유계수 기준)
if "emission_factors" not in st.session_state:
    st.session_state.emission_factors = pd.DataFrame([
        {"항목": "도시가스(LNG)", "구분": "Scope 1", "단위": "Nm³", "순발열량_MJ": 43.1, "CO2계수_kg_TJ": 56100, "CH4계수_kg_TJ": 1.0, "N2O계수_kg_TJ": 0.1, "간접계수_kg_kWh": 0.0},
        {"항목": "경유", "구분": "Scope 1", "단위": "L", "순발열량_MJ": 35.8, "CO2계수_kg_TJ": 74100, "CH4계수_kg_TJ": 3.0, "N2O계수_kg_TJ": 0.6, "간접계수_kg_kWh": 0.0},
        {"항목": "휘발유", "구분": "Scope 1", "단위": "L", "순발열량_MJ": 31.8, "CO2계수_kg_TJ": 69300, "CH4계수_kg_TJ": 3.0, "N2O계수_kg_TJ": 0.6, "간접계수_kg_kWh": 0.0},
        {"항목": "LPG(프로판)", "구분": "Scope 1", "단위": "kg", "순발열량_MJ": 46.3, "CO2계수_kg_TJ": 63100, "CH4계수_kg_TJ": 1.0, "N2O계수_kg_TJ": 0.1, "간접계수_kg_kWh": 0.0},
        {"항목": "전력(한전 계통)", "구분": "Scope 2", "단위": "kWh", "순발열량_MJ": 0.0, "CO2계수_kg_TJ": 0.0, "CH4계수_kg_TJ": 0.0, "N2O계수_kg_TJ": 0.0, "간접계수_kg_kWh": 0.4781},
    ])

# GWP 계수 (AR5 기준)
GWP = {"CO2": 1, "CH4": 28, "N2O": 265}

# 2. 샘플 활동 데이터
if "activity_data" not in st.session_state:
    st.session_state.activity_data = pd.DataFrame([
        {"id": 1, "사업장": "서울 본사", "연월": "2026-01", "항목": "전력(한전 계통)", "사용량": 125000.0, "상태": "승인완료", "비고": "정상 가동"},
        {"id": 2, "사업장": "울산 1공장", "연월": "2026-01", "항목": "도시가스(LNG)", "사용량": 18200.0, "상태": "승인완료", "비고": "보일러 가동"},
        {"id": 3, "사업장": "울산 1공장", "연월": "2026-01", "항목": "경유", "사용량": 3200.0, "상태": "승인완료", "비고": "지게차 및 비상발전"},
        {"id": 4, "사업장": "창원 2공장", "연월": "2026-01", "항목": "전력(한전 계통)", "사용량": 98000.0, "상태": "승인대기", "비고": "신규 라인 증설분"},
        {"id": 5, "사업장": "서울 본사", "연월": "2026-02", "항목": "전력(한전 계통)", "사용량": 118000.0, "상태": "승인대기", "비고": "절전 캠페인 시행"},
        {"id": 6, "사업장": "울산 1공장", "연월": "2026-02", "항목": "도시가스(LNG)", "사용량": 16900.0, "상태": "임시저장", "비고": "검침 확인 중"}
    ])

# -------------------------------------------------------------------
# 온실가스 배출량 계산 함수 (tCO2eq)
# -------------------------------------------------------------------
def calculate_emissions(df_activity, df_factors):
    if df_activity.empty:
        return df_activity.copy()

    merged = df_activity.merge(df_factors, on="항목", how="left")
    
    emissions = []
    scopes = []
    
    for _, row in merged.iterrows():
        scope = row["구분"]
        usage = float(row["사용량"])
        scopes.append(scope)
        
        if scope == "Scope 2":
            # 전력 간접배출: 사용량(kWh) * 계수(kgCO2eq/kWh) / 1,000 = tCO2eq
            t_co2eq = (usage * float(row["간접계수_kg_kWh"])) / 1000.0
        else:
            # Scope 1 직접배출: 연료 연소식
            # 에너지소비량(TJ) = 사용량 * 순발열량(MJ) / 10^6
            tj = (usage * float(row["순발열량_MJ"])) / 1_000_000.0
            co2_kg = tj * float(row["CO2계수_kg_TJ"])
            ch4_kg = tj * float(row["CH4계수_kg_TJ"])
            n2o_kg = tj * float(row["N2O계수_kg_TJ"])
            # 총 온실가스(tCO2eq) = (CO2*1 + CH4*28 + N2O*265) / 1,000
            t_co2eq = (co2_kg * GWP["CO2"] + ch4_kg * GWP["CH4"] + n2o_kg * GWP["N2O"]) / 1000.0
            
        emissions.append(round(t_co2eq, 2))
        
    merged["배출량(tCO2eq)"] = emissions
    merged["Scope"] = scopes
    
    return merged[["id", "사업장", "연월", "항목", "Scope", "사용량", "배출량(tCO2eq)", "상태", "비고"]]

# -------------------------------------------------------------------
# 사이드바: 사용자 역할 및 사업장 필터
# -------------------------------------------------------------------
st.sidebar.title("🌱 EcoScope")
st.sidebar.markdown("**사업장 온실가스 관리 시스템**")

role = st.sidebar.radio("접속 권한 선택", ["본사 총괄 관리자", "사업장 담당자"])

selected_site = "전체"
if role == "사업장 담당자":
    user_site = st.sidebar.selectbox("담당 사업장", ["서울 본사", "울산 1공장", "창원 2공장"])
else:
    user_site = "본사"

menu = st.sidebar.selectbox("메뉴 이동", ["통합 대시보드", "데이터 입력 및 관리", "배출계수 마스터(관리자)", "엑셀 일괄 업로드"])

# 계산된 전체 데이터셋 생성
calc_df = calculate_emissions(st.session_state.activity_data, st.session_state.emission_factors)

# -------------------------------------------------------------------
# 1. 통합 대시보드
# -------------------------------------------------------------------
if menu == "통합 대시보드":
    st.title("📊 온실가스 배출량 모니터링 대시보드")
    st.caption("사업장별 Scope 1(직접배출)과 Scope 2(간접배출) 산정 현황")
    
    # 상단 요약 KPI 카드
    total_emission = calc_df["배출량(tCO2eq)"].sum()
    scope1_emission = calc_df[calc_df["Scope"] == "Scope 1"]["배출량(tCO2eq)"].sum()
    scope2_emission = calc_df[calc_df["Scope"] == "Scope 2"]["배출량(tCO2eq)"].sum()
    annual_target = 350.0  # 연간 목표치 예시
    achievement_rate = (total_emission / annual_target) * 100
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 배출량", f"{total_emission:,.2f} tCO₂eq")
    col2.metric("Scope 1 (직접)", f"{scope1_emission:,.2f} tCO₂eq")
    col3.metric("Scope 2 (간접)", f"{scope2_emission:,.2f} tCO₂eq")
    col4.metric("연간 목표 달성률", f"{achievement_rate:.1f} %", delta=f"{annual_target - total_emission:.1f} t 잔여")

    st.markdown("---")
    
    # 차트 영역
    c1, c2 = st.columns(2)
    
    with c1:
        # 월별 배출량 추이
        monthly_df = calc_df.groupby(["연월", "Scope"])["배출량(tCO2eq)"].sum().reset_index()
        fig_monthly = px.bar(
            monthly_df, x="연월", y="배출량(tCO2eq)", color="Scope",
            barmode="group", title="월별 배출 추이 (Scope 1 vs Scope 2)",
            text_auto=True, color_discrete_map={"Scope 1": "#F97316", "Scope 2": "#3B82F6"}
        )
        st.plotly_chart(fig_monthly, use_container_width=True)
        
    with c2:
        # 사업장별 배출량 분포
        site_df = calc_df.groupby("사업장")["배출량(tCO2eq)"].sum().reset_index()
        fig_site = px.pie(
            site_df, values="배출량(tCO2eq)", names="사업장",
            title="사업장별 배출 비중", hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_site, use_container_width=True)

    # 리포트 다운로드 버튼
    csv_buffer = io.BytesIO()
    calc_df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 온실가스 인벤토리 보고서 다운로드 (CSV)",
        data=csv_buffer.getvalue(),
        file_name="GHG_Inventory_Report_2026.csv",
        mime="text/csv"
    )

# -------------------------------------------------------------------
# 2. 데이터 입력 및 관리
# -------------------------------------------------------------------
elif menu == "데이터 입력 및 관리":
    st.title("📝 활동 데이터 입력 및 승인")
    
    if role == "사업장 담당자":
        st.subheader(f"📍 {user_site} 신규 배출원 활동량 등록")
        with st.form("input_form", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                input_month = st.text_input("연월 (YYYY-MM)", value="2026-03")
            with f_col2:
                items = st.session_state.emission_factors["항목"].tolist()
                input_item = st.selectbox("항목(에너지원)", items)
            with f_col3:
                input_qty = st.number_input("사용량", min_value=0.0, step=100.0)
                
            input_memo = st.text_input("비고", placeholder="설비명, 계측기 번호 등")
            submit = st.form_submit_button("승인 요청 제출")
            
            if submit:
                new_id = int(st.session_state.activity_data["id"].max() + 1) if not st.session_state.activity_data.empty else 1
                new_row = {
                    "id": new_id,
                    "사업장": user_site,
                    "연월": input_month,
                    "항목": input_item,
                    "사용량": input_qty,
                    "상태": "승인대기",
                    "비고": input_memo
                }
                st.session_state.activity_data = pd.concat([st.session_state.activity_data, pd.DataFrame([new_row])], ignore_index=True)
                st.success("데이터가 성공적으로 등록되었으며 본사 승인 요청 상태로 전환되었습니다.")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 배출 활동 데이터 목록")
    
    # 관리자는 전체 승인 권한, 담당자는 본인 사업장 확인
    view_df = calc_df.copy()
    if role == "사업장 담당자":
        view_df = view_df[view_df["사업장"] == user_site]

    st.dataframe(view_df, use_container_width=True)

    if role == "본사 총괄 관리자":
        st.subheader("⚡ 본사 승인 처리 센터")
        pending_records = st.session_state.activity_data[st.session_state.activity_data["상태"] == "승인대기"]
        
        if pending_records.empty:
            st.info("현재 승인 대기 중인 데이터가 없습니다.")
        else:
            selected_ids = st.multiselect("승인할 데이터 ID 선택", pending_records["id"].tolist())
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("선택 항목 승인 완료", type="primary"):
                    st.session_state.activity_data.loc[st.session_state.activity_data["id"].isin(selected_ids), "상태"] = "승인완료"
                    st.success("선택한 항목이 승인되었습니다.")
                    st.rerun()
            with col_b2:
                if st.button("선택 항목 반려"):
                    st.session_state.activity_data.loc[st.session_state.activity_data["id"].isin(selected_ids), "상태"] = "반려"
                    st.warning("선택한 항목이 반려되었습니다.")
                    st.rerun()

# -------------------------------------------------------------------
# 3. 배출계수 마스터 (관리자 전용)
# -------------------------------------------------------------------
elif menu == "배출계수 마스터(관리자)":
    st.title("⚙️ 국가 표준 배출계수 마스터 테이블")
    
    if role != "본사 총괄 관리자":
        st.error("배출계수 테이블 편집 권한이 없습니다. 본사 총괄 관리자로 역할을 변경해 주세요.")
    else:
        st.info("수정 후 엔터를 치거나 표 바깥을 클릭하면 전체 배출량이 자동 재산정됩니다.")
        
        # Streamlit Data Editor로 계수 직접 편집
        edited_factors = st.data_editor(
            st.session_state.emission_factors,
            num_rows="dynamic",
            use_container_width=True,
            key="factor_editor"
        )
        
        if st.button("수정된 배출계수 저장 및 전체 반영"):
            st.session_state.emission_factors = edited_factors
            st.success("배출계수가 업데이트되었습니다.")
            st.rerun()

# -------------------------------------------------------------------
# 4. 엑셀 일괄 업로드
# -------------------------------------------------------------------
elif menu == "엑셀 일괄 업로드":
    st.title("📤 엑셀/CSV 일괄 업로드")
    st.caption("대량의 월별 에너지 사용 데이터를 일괄 입력할 수 있습니다.")
    
    # 템플릿 다운로드
    template_df = pd.DataFrame([{
        "사업장": "서울 본사",
        "연월": "2026-04",
        "항목": "도시가스(LNG)",
        "사용량": 15000,
        "비고": "공조기 가동"
    }])
    
    t_buffer = io.BytesIO()
    template_df.to_csv(t_buffer, index=False, encoding="utf-8-sig")
    st.download_button("양식 템플릿 다운로드 (CSV)", data=t_buffer.getvalue(), file_name="업로드_표준_템플릿.csv")
    
    uploaded_file = st.file_uploader("파일 업로드 (CSV 또는 Excel)", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                upload_data = pd.read_csv(uploaded_file)
            else:
                upload_data = pd.read_excel(uploaded_file)
                
            st.write("업로드된 데이터 미리보기:")
            st.dataframe(upload_data)
            
            if st.button("데이터베이스에 병합하기"):
                start_id = int(st.session_state.activity_data["id"].max() + 1) if not st.session_state.activity_data.empty else 1
                upload_data["id"] = range(start_id, start_id + len(upload_data))
                upload_data["상태"] = "승인대기"
                
                st.session_state.activity_data = pd.concat([st.session_state.activity_data, upload_data], ignore_index=True)
                st.success("데이터 일괄 등록이 완료되었습니다.")
                st.rerun()
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
