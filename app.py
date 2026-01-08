import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET

# --- 1. إعداد الصفحة ---
st.set_page_config(page_title="مدير قطع الغيار", layout="wide", page_icon="⚙️")
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
        
        # 1. فلترة المحذوفات
        if 'IsDelete' in df_header.columns:
            df_header = df_header[~df_header['IsDelete'].isin(['True', 'true', '1'])]

        # 2. تنظيف التاريخ
        df_header['Date'] = pd.to_datetime(pd.to_numeric(df_header['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
        
        # 3. الأرقام (الضريبة)
        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        
        # محاولة قراءة المبلغ الصافي (بدون ضريبة)
        if 'TaxbleAmount' in df_items.columns:
            df_items['Amount'] = pd.to_numeric(df_items['TaxbleAmount'], errors='coerce').fillna(0)
        elif 'BasicStockAmount' in df_items.columns:
            df_items['Amount'] = pd.to_numeric(df_items['BasicStockAmount'], errors='coerce').fillna(0)
        else:
            # الخطة البديلة: خصم 15% يدوياً
            df_items['Amount'] = pd.to_numeric(df_items['netStockAmount'], errors='coerce').fillna(0) / 1.15

        # --- 🔴 معالجة التكلفة (ديناميكية) ---
        if cost_col_name in df_items.columns: 
            df_items['CostUnit'] = pd.to_numeric(df_items[cost_col_name], errors='coerce').fillna(0)
        else: 
            df_items['CostUnit'] = 0
            
        df_items['TotalCost'] = df_items['CostUnit'] * df_items['Qty']
        
        # حذف الأعمدة المكررة
        cols_to_drop = ['SalesMan', 'VoucherName']
        for col in cols_to_drop:
            if col in df_items.columns: df_items = df_items.drop(columns=[col])

        if 'SalesPerson' in df_header.columns: df_header['SalesMan'] = df_header['SalesPerson']
        else: df_header['SalesMan'] = 'غير محدد'

        # 4. الدمج
        full_data = pd.merge(df_items, df_header[['TransCode', 'Date', 'LedgerName', 'InvoiceNo', 'SalesMan', 'VoucherName']], on='TransCode', how='inner')
        
        # 🔴 معالجة المرتجعات
        mask_return = full_data['VoucherName'].str.contains('Return|مرتجع', case=False, na=False)
        full_data.loc[mask_return, 'Amount'] = full_data.loc[mask_return, 'Amount'] * -1
        full_data.loc[mask_return, 'TotalCost'] = full_data.loc[mask_return, 'TotalCost'] * -1
        
        # حساب الربح النهائي
        full_data['Profit'] = full_data['Amount'] - full_data['TotalCost']
        
        return full_data.dropna(subset=['Date'])
    except Exception as e: st.error(f"Error: {e}"); return None

# --- 4. الواجهة ---
st.title("📊 لوحة القيادة: تحليل نشاط قطع الغيار")
with st.sidebar:
    st.header("📂 رفع البيانات")
    # تثبيت أسماء الملفات كما طلبت
    f1 = st.file_uploader("1. ملف الفواتير (StockInvoiceDetails.xml)", type=['xml'])
    f2 = st.file_uploader("2. ملف الأصناف (StockInvoiceRowItems.xml)", type=['xml'])
    
    st.markdown("---")
    st.header("⚙️ ضبط الحسابات")
    # القائمة المحدثة
    cost_opt = st.selectbox("مصدر التكلفة", ('PresetRate', 'CurrentStockRate', 'CostFactor', 'StockRate', 'PresetRate2'))

if f1 and f2:
    df = load_data(f1, f2, cost_opt)
    if df is not None:
        
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 نوع الفواتير")
        all_vouchers = list(df['VoucherName'].unique())
        
        # الفلتر الذكي الافتراضي
        default_selection = [v for v in all_vouchers if 'Sale' in str(v) or 'Cash' in str(v) or 'Invoice' in str(v) or 'Return' in str(v) or 'مرتجع' in str(v)]
        
        selected_vouchers = st.sidebar.multiselect(
            "تصفية السندات:",
            options=all_vouchers,
            default=default_selection
        )
        
        filtered_df = df[df['VoucherName'].isin(selected_vouchers)]
        
        # الفلاتر الزمنية
        min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
        c1, c2 = st.columns(2)
        with c1: d_range = st.date_input("الفترة الزمنية", [min_d, max_d])
        with c2: salesman_filter = st.selectbox("تصفية حسب البائع", ['الكل'] + list(filtered_df['SalesMan'].unique()))

        if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
            filtered_df = filtered_df[(filtered_df['Date'].dt.date >= d_range[0]) & (filtered_df['Date'].dt.date <= d_range[1])]
        if salesman_filter != 'الكل':
            filtered_df = filtered_df[filtered_df['SalesMan'] == salesman_filter]

        # الحسابات النهائية
        total_sales = filtered_df['Amount'].sum()
        total_profit = filtered_df['Profit'].sum()
        total_cost = filtered_df['TotalCost'].sum()
        margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
        
        # عرض النتائج
        st.markdown("### 📌 النتائج المالية (الصافي)")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("صافي المبيعات", f"{total_sales:,.0f} ر.س")
        k2.metric("تكلفة المبيعات", f"{total_cost:,.0f} ر.س")
        k3.metric("صافي الربح", f"{total_profit:,.0f} ر.س")
        k4.metric("نسبة الربح", f"{margin:.1f}%")

        st.markdown("---")
        
        # الرسوم البيانية
        col_g1, col_g2 = st.columns(2)
        with col_g1: 
            st.subheader("تحليل الربحية")
            st.plotly_chart(px.line(filtered_df.groupby('Date')['Profit'].sum().reset_index(), x='Date', y='Profit', title="الأرباح اليومية"), use_container_width=True)
        with col_g2: 
            st.subheader("أداء البائعين")
            st.plotly_chart(px.bar(filtered_df.groupby('SalesMan')['Amount'].sum().reset_index(), x='SalesMan', y='Amount'), use_container_width=True)

        # جدول التنبيهات (الخسائر)
        st.markdown("---")
        st.subheader("⚠️ مراقبة الأصناف (خسارة أو هامش ضعيف)")
        loss_items = filtered_df[filtered_df['Profit'] < 0].groupby(['StockName', 'InvoiceNo'])[['Qty', 'Amount', 'TotalCost', 'Profit']].sum().reset_index()
        if not loss_items.empty:
            st.dataframe(loss_items.style.format("{:.2f}").background_gradient(subset=['Profit'], cmap='Reds_r'), use_container_width=True)
        else:
            st.success("ممتاز! لا توجد مبيعات بخسارة في هذه الفترة.")
