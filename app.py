import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import xml.etree.ElementTree as ET

# --- 1. إعداد الصفحة والتصميم ---
st.set_page_config(page_title="مدير قطع الغيار الذكي", layout="wide", page_icon="⚙️")

st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #0068c9;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. نظام الحماية ---
if "password" not in st.session_state:
    st.session_state["password"] = ""

if st.session_state["password"] != st.secrets["PASSWORD"]:
    st.title("🔒 تسجيل الدخول")
    password = st.text_input("أدخل كلمة المرور للمتابعة", type="password")
    if password == st.secrets["PASSWORD"]:
        st.session_state["password"] = password
        st.rerun()
    else:
        st.stop()

# --- 3. دالة المعالجة الذكية ---
@st.cache_data(ttl=3600)
def load_data(file_header, file_items, cost_col_name):
    try:
        # قراءة الملفات
        tree_h = ET.parse(file_header)
        df_header = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_h.getroot()])
        
        tree_i = ET.parse(file_items)
        df_items = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_i.getroot()])
        
        # --- تنظيف البيانات ---
        
        # 1. التاريخ
        df_header['Date'] = pd.to_datetime(
            pd.to_numeric(df_header['TransDateValue'], errors='coerce'), 
            unit='D', 
            origin='1899-12-30'
        )
        
        # 2. تنظيف الأصناف
        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        df_items['Amount'] = pd.to_numeric(df_items['netStockAmount'], errors='coerce').fillna(0)
        
        # 🔥 ديناميكية التكلفة (حسب اختيارك) 🔥
        # إذا لم نجد العمود المختار، نعتبر التكلفة صفر
        if cost_col_name in df_items.columns:
            df_items['CostUnit'] = pd.to_numeric(df_items[cost_col_name], errors='coerce').fillna(0)
        else:
            df_items['CostUnit'] = 0
            
        df_items['TotalCost'] = df_items['CostUnit'] * df_items['Qty']
        df_items['Profit'] = df_items['Amount'] - df_items['TotalCost']

        # حذف SalesMan من الأصناف لمنع التصادم
        if 'SalesMan' in df_items.columns:
            df_items = df_items.drop(columns=['SalesMan'])

        # توحيد اسم البائع
        if 'SalesPerson' in df_header.columns:
            df_header['SalesMan'] = df_header['SalesPerson']
        else:
            df_header['SalesMan'] = 'غير محدد'

        # 3. الدمج
        full_data = pd.merge(
            df_items, 
            df_header[['TransCode', 'Date', 'LedgerName', 'InvoiceNo', 'SalesMan']], 
            on='TransCode', 
            how='inner'
        )
        
        full_data = full_data.dropna(subset=['Date'])
        return full_data
        
    except Exception as e:
        st.error(f"حدث خطأ في معالجة الملفات: {e}")
        return None

# --- 4. الواجهة الرئيسية ---
st.title("📊 لوحة القيادة: تحليل نشاط قطع الغيار")
st.markdown("---")

with st.sidebar:
    st.header("📂 إعدادات البيانات")
    uploaded_header = st.file_uploader("1. ملف الفواتير (InvoiceDetails)", type=['xml'])
    uploaded_items = st.file_uploader("2. ملف الأصناف (RowItems)", type=['xml'])
    
    st.markdown("---")
    st.header("⚙️ ضبط التكلفة")
    # القائمة السحرية لاختيار عمود التكلفة
    cost_option = st.selectbox(
        "اختر العمود الذي يمثل التكلفة:",
        ('CurrentStockRate', 'CostFactor', 'BasicPrice', 'StockRate'),
        index=0 # الافتراضي هو CurrentStockRate
    )
    st.caption("جرب تغيير الخيار حتى يظهر هامش الربح بشكل منطقي.")

if uploaded_header and uploaded_items:
    
    df_merged = load_data(uploaded_header, uploaded_items, cost_option)
    
    if df_merged is not None and not df_merged.empty:
        
        # الفلاتر
        col_fil1, col_fil2, col_fil3 = st.columns(3)
        with col_fil1:
            min_date = df_merged['Date'].min().date()
            max_date = df_merged['Date'].max().date()
            date_range = st.date_input("الفترة الزمنية", [min_date, max_date])
        
        with col_fil2:
            salesmen = ['الكل'] + list(df_merged['SalesMan'].unique())
            selected_salesman = st.selectbox("اختر البائع", salesmen)
            
        with col_fil3:
            groups = ['الكل'] + list(df_merged['stockgroup'].unique())
            selected_group = st.selectbox("مجموعة الأصناف", groups)

        # تطبيق الفلاتر
        filtered_df = df_merged.copy()
        
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
             filtered_df = filtered_df[
                (filtered_df['Date'].dt.date >= date_range[0]) & 
                (filtered_df['Date'].dt.date <= date_range[1])
            ]
        
        if selected_salesman != 'الكل':
            filtered_df = filtered_df[filtered_df['SalesMan'] == selected_salesman]
        if selected_group != 'الكل':
            filtered_df = filtered_df[filtered_df['stockgroup'] == selected_group]

        # KPIs
        st.markdown("### 📌 الأداء المالي")
        
        total_sales = filtered_df['Amount'].sum()
        total_profit = filtered_df['Profit'].sum()
        total_cost = filtered_df['TotalCost'].sum()
        profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
        
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("إجمالي المبيعات", f"{total_sales:,.0f} ر.س")
        # تلوين الربح حسب النتيجة
        kpi2.metric("صافي الربح", f"{total_profit:,.0f} ر.س", delta=f"{profit_margin:.1f}% هامش")
        kpi3.metric("إجمالي التكلفة", f"{total_cost:,.0f} ر.س", delta_color="inverse")

        st.markdown("---")
        
        # الرسوم البيانية
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("تحليل الربحية حسب المجموعة")
            # رسم يوضح أين تأتي أرباحك
            profit_by_group = filtered_df.groupby('stockgroup')['Profit'].sum().reset_index().sort_values('Profit', ascending=False).head(10)
            fig_p = px.bar(profit_by_group, x='stockgroup', y='Profit', color='Profit', title="أكثر المجموعات ربحية")
            st.plotly_chart(fig_p, use_container_width=True)
            
        with c2:
            st.subheader("أداء البائعين (مبيعات)")
            perf = filtered_df.groupby('SalesMan')['Amount'].sum().reset_index().sort_values('Amount', ascending=False)
            fig2 = px.bar(perf, x='SalesMan', y='Amount')
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        st.subheader("🔍 فحص تفصيلي (للتأكد من التكلفة)")
        st.dataframe(filtered_df[['Date', 'StockName', 'Qty', 'CostUnit', 'Amount', 'Profit']].head(50), use_container_width=True)

    elif df_merged is not None:
         st.warning("⚠️ لا توجد بيانات.")
else:
    st.info("👈 ارفع الملفات، ثم جرب تغيير 'عمود التكلفة' من القائمة الجانبية.")
