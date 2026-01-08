import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET

# --- 1. إعداد الصفحة ---
st.set_page_config(page_title="مدير قطع الغيار الذكي", layout="wide", page_icon="⚙️")
st.markdown("""<style>[data-testid="stMetricValue"] {font-size: 24px; color: #0068c9;}</style>""", unsafe_allow_html=True)

# --- 2. الحماية ---
if "password" not in st.session_state: st.session_state["password"] = ""
if st.session_state["password"] != st.secrets["PASSWORD"]:
    st.title("🔒 تسجيل الدخول"); password = st.text_input("كلمة المرور", type="password")
    if password == st.secrets["PASSWORD"]: st.session_state["password"] = password; st.rerun()
    else: st.stop()

# --- 3. المعالجة ---
@st.cache_data(ttl=3600)
def load_data(file_header, file_items, cost_col_name):
    try:
        tree_h = ET.parse(file_header); df_header = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_h.getroot()])
        tree_i = ET.parse(file_items); df_items = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_i.getroot()])
        
        # 1. فلترة المحذوفات (أهم خطوة)
        if 'IsDelete' in df_header.columns:
            # نتأكد أن القيم ليست "True" أو "1"
            df_header = df_header[~df_header['IsDelete'].isin(['True', 'true', '1'])]

        # 2. تنظيف التاريخ
        df_header['Date'] = pd.to_datetime(pd.to_numeric(df_header['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
        
        # 3. الأرقام
        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        df_items['Amount'] = pd.to_numeric(df_items['netStockAmount'], errors='coerce').fillna(0)
        
        # التكلفة
        if cost_col_name in df_items.columns: df_items['CostUnit'] = pd.to_numeric(df_items[cost_col_name], errors='coerce').fillna(0)
        else: df_items['CostUnit'] = 0
            
        df_items['TotalCost'] = df_items['CostUnit'] * df_items['Qty']
        df_items['Profit'] = df_items['Amount'] - df_items['TotalCost']

        if 'SalesMan' in df_items.columns: df_items = df_items.drop(columns=['SalesMan'])
        if 'SalesPerson' in df_header.columns: df_header['SalesMan'] = df_header['SalesPerson']
        else: df_header['SalesMan'] = 'غير محدد'

        # 4. الدمج (مع جلب VoucherName للفلترة)
        full_data = pd.merge(df_items, df_header[['TransCode', 'Date', 'LedgerName', 'InvoiceNo', 'SalesMan', 'VoucherName']], on='TransCode', how='inner')
        return full_data.dropna(subset=['Date'])
    except Exception as e: st.error(f"Error: {e}"); return None

# --- 4. الواجهة ---
st.title("📊 مطابقة الأرقام: لوحة التحليل المالي")
with st.sidebar:
    st.header("📂 البيانات"); f1 = st.file_uploader("ملف الفواتير", type=['xml']); f2 = st.file_uploader("ملف الأصناف", type=['xml'])
    st.markdown("---"); cost_opt = st.selectbox("مصدر التكلفة", ('CurrentStockRate', 'CostFactor', 'BasicPrice'))

if f1 and f2:
    df = load_data(f1, f2, cost_opt)
    if df is not None:
        
        # --- 🔴 الفلتر الذهبي: أنواع الفواتير ---
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 تصفية نوع السند (هام جداً)")
        
        # نجمع كل الأنواع الموجودة
        all_vouchers = list(df['VoucherName'].unique())
        
        # نحاول تخمين المبيعات (نبحث عن كلمة Sales أو Cash)
        default_selection = [v for v in all_vouchers if 'Sale' in str(v) or 'Cash' in str(v) or 'Invoice' in str(v)]
        
        selected_vouchers = st.sidebar.multiselect(
            "حدد فقط الفواتير التي تحسب كـ 'مبيعات':",
            options=all_vouchers,
            default=default_selection
        )
        
        # تطبيق الفلتر
        filtered_df = df[df['VoucherName'].isin(selected_vouchers)]
        
        # --- الفلاتر الزمنية ---
        min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
        c1, c2 = st.columns(2)
        with c1: d_range = st.date_input("الفترة", [min_d, max_d])
        with c2: 
            salesman_filter = st.selectbox("البائع", ['الكل'] + list(filtered_df['SalesMan'].unique()))

        # فلترة التاريخ والبائع
        if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
            filtered_df = filtered_df[(filtered_df['Date'].dt.date >= d_range[0]) & (filtered_df['Date'].dt.date <= d_range[1])]
        if salesman_filter != 'الكل':
            filtered_df = filtered_df[filtered_df['SalesMan'] == salesman_filter]

        # --- عرض الأرقام للمطابقة ---
        total_sales = filtered_df['Amount'].sum()
        total_profit = filtered_df['Profit'].sum()
        
        st.markdown("### 🔢 النتائج الحالية (للمطابقة مع البرنامج)")
        k1, k2, k3 = st.columns(3)
        k1.metric("إجمالي المبيعات", f"{total_sales:,.2f}")
        k2.metric("صافي الربح", f"{total_profit:,.2f}")
        k3.metric("عدد الفواتير", len(filtered_df['TransCode'].unique()))

        # عرض ما تم استبعاده (للتأكد)
        excluded_df = df[~df['VoucherName'].isin(selected_vouchers)]
        if not excluded_df.empty:
            with st.expander("🗑️ السندات المستبعدة (تأكد أن المشتريات والمرتجعات هنا)"):
                st.write(excluded_df.groupby('VoucherName')['Amount'].sum().reset_index())

        # الرسوم
        st.markdown("---")
        col_g1, col_g2 = st.columns(2)
        with col_g1: st.plotly_chart(px.line(filtered_df.groupby('Date')['Amount'].sum().reset_index(), x='Date', y='Amount', title="المبيعات اليومية"), use_container_width=True)
        with col_g2: st.plotly_chart(px.bar(filtered_df.groupby('SalesMan')['Amount'].sum().reset_index(), x='SalesMan', y='Amount', title="أداء البائعين"), use_container_width=True)
