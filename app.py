import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="مدير قطع الغيار", layout="wide", page_icon="🏎️")

# CSS لتحسين المظهر
st.markdown("""
<style>
    [data-testid="stMetricValue"] {font-size: 26px; color: #0068c9; font-weight: bold;}
    div[data-testid="stSidebarUserContent"] {padding-top: 20px;}
    .big-font {font-size:18px !important;}
</style>
""", unsafe_allow_html=True)

# --- 2. الحماية ---
if "password" not in st.session_state: st.session_state["password"] = ""
if st.session_state["password"] != st.secrets["PASSWORD"]:
    st.title("🔒 تسجيل الدخول الآمن"); password = st.text_input("أدخل كلمة المرور", type="password")
    if password == st.secrets["PASSWORD"]: st.session_state["password"] = password; st.rerun()
    else: st.stop()

# --- 3. المعالجة الذكية ---
@st.cache_data(ttl=3600)
def load_final_data(file_header, file_items):
    try:
        # قراءة الملفات
        tree_h = ET.parse(file_header); df_header = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_h.getroot()])
        tree_i = ET.parse(file_items); df_items = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_i.getroot()])
        
        # 1. فلترة المحذوفات
        if 'IsDelete' in df_header.columns:
            df_header = df_header[~df_header['IsDelete'].isin(['True', 'true', '1'])]

        # 2. تنظيف التاريخ
        df_header['Date'] = pd.to_datetime(pd.to_numeric(df_header['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
        
        # 3. توحيد اسم البائع (إصلاح مشكلة الترتيب)
        if 'SalesPerson' in df_header.columns: 
            df_header['SalesMan'] = df_header['SalesPerson'].fillna('غير محدد').astype(str)
        else: 
            df_header['SalesMan'] = 'غير محدد'

        # 4. معالجة الأرقام
        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        
        # حساب المبيعات (الصافي)
        if 'TaxbleAmount' in df_items.columns:
            df_items['Amount'] = pd.to_numeric(df_items['TaxbleAmount'], errors='coerce').fillna(0)
        elif 'BasicStockAmount' in df_items.columns:
            df_items['Amount'] = pd.to_numeric(df_items['BasicStockAmount'], errors='coerce').fillna(0)
        else:
            df_items['Amount'] = pd.to_numeric(df_items['netStockAmount'], errors='coerce').fillna(0) / 1.15

        # حساب التكلفة (PresetRate)
        cost_col = 'PresetRate'
        if cost_col in df_items.columns:
            df_items['CostUnit'] = pd.to_numeric(df_items[cost_col], errors='coerce').fillna(0)
        elif 'PresetRate2' in df_items.columns:
             df_items['CostUnit'] = pd.to_numeric(df_items['PresetRate2'], errors='coerce').fillna(0)
        else:
            df_items['CostUnit'] = 0
            
        df_items['TotalCost'] = df_items['CostUnit'] * df_items['Qty']
        
        # تنظيف الأعمدة المكررة
        cols_to_drop = ['SalesMan', 'VoucherName', 'SalesPerson']
        for col in cols_to_drop:
            if col in df_items.columns: df_items = df_items.drop(columns=[col])

        # 5. الدمج النهائي
        full_data = pd.merge(df_items, df_header[['TransCode', 'Date', 'LedgerName', 'InvoiceNo', 'SalesMan', 'VoucherName']], on='TransCode', how='inner')
        
        # 6. معالجة المرتجعات
        mask_return = full_data['VoucherName'].str.contains('Return|مرتجع', case=False, na=False)
        full_data.loc[mask_return, 'Amount'] = full_data.loc[mask_return, 'Amount'] * -1
        full_data.loc[mask_return, 'TotalCost'] = full_data.loc[mask_return, 'TotalCost'] * -1
        
        # الربح النهائي
        full_data['Profit'] = full_data['Amount'] - full_data['TotalCost']
        
        if 'stockgroup' not in full_data.columns: full_data['stockgroup'] = 'عام'

        return full_data.dropna(subset=['Date'])
    except Exception as e: st.error(f"خطأ فني: {e}"); return None

# --- 4. الواجهة ---
st.title("🏎️ لوحة القيادة: الأداء المالي والربحية")
st.caption("النسخة النهائية - معتمدة")

with st.sidebar:
    st.header("📂 رفع الملفات")
    f1 = st.file_uploader("1. ملف الفواتير (StockInvoiceDetails.xml)", type=['xml'])
    f2 = st.file_uploader("2. ملف الأصناف (StockInvoiceRowItems.xml)", type=['xml'])

if f1 and f2:
    df = load_final_data(f1, f2)
    if df is not None:
        
        # الفلاتر
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 أدوات التصفية")
        
        all_vouchers = list(df['VoucherName'].unique())
        # تحديد المبيعات والمرتجعات افتراضياً
        default_selection = [v for v in all_vouchers if any(x in str(v) for x in ['Sale', 'Cash', 'Invoice', 'Return', 'مرتجع'])]
        selected_vouchers = st.sidebar.multiselect("نوع الحركة:", options=all_vouchers, default=default_selection)
        
        df_filtered = df[df['VoucherName'].isin(selected_vouchers)]

        min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
        c1, c2 = st.columns(2)
        with c1: d_range = st.date_input("📅 الفترة الزمنية", [min_d, max_d])
        with c2: 
            # هنا الإصلاح: تحويل القائمة لنصوص قبل الترتيب لمنع الخطأ
            salesman_list = ['الكل'] + sorted(list(df_filtered['SalesMan'].astype(str).unique()))
            salesman_filter = st.selectbox("👤 البائع", salesman_list)

        if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
            df_filtered = df_filtered[(df_filtered['Date'].dt.date >= d_range[0]) & (df_filtered['Date'].dt.date <= d_range[1])]
        
        if salesman_filter != 'الكل':
            df_filtered = df_filtered[df_filtered['SalesMan'] == salesman_filter]

        st.markdown("---")

        # KPIs
        total_sales = df_filtered['Amount'].sum()
        total_profit = df_filtered['Profit'].sum()
        total_cost = df_filtered['TotalCost'].sum()
        margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
        inv_count = df_filtered['TransCode'].nunique()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 صافي المبيعات", f"{total_sales:,.0f} ر.س")
        k2.metric("📉 تكلفة المبيعات", f"{total_cost:,.0f} ر.س")
        k3.metric("📈 صافي الربح", f"{total_profit:,.0f} ر.س", delta=f"{margin:.1f}% هامش")
        k4.metric("🧾 عدد العمليات", f"{inv_count}")

        # Charts
        st.markdown("### 📊 التحليل البياني")
        tab1, tab2, tab3 = st.tabs(["المبيعات اليومية", "أداء البائعين", "تحليل المجموعات"])
        
        with tab1:
            daily_data = df_filtered.groupby('Date')[['Amount', 'Profit']].sum().reset_index()
            fig_trend = px.line(daily_data, x='Date', y=['Amount', 'Profit'], markers=True)
            st.plotly_chart(fig_trend, use_container_width=True)
            
        with tab2:
            salesman_perf = df_filtered.groupby('SalesMan')[['Amount', 'Profit']].sum().reset_index().sort_values('Amount', ascending=False)
            fig_bar = px.bar(salesman_perf, x='SalesMan', y=['Amount', 'Profit'], barmode='group', text_auto='.2s')
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with tab3:
            group_perf = df_filtered.groupby('stockgroup')[['Amount', 'Profit']].sum().reset_index().sort_values('Profit', ascending=False).head(10)
            fig_pie = px.pie(group_perf, values='Profit', names='stockgroup', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        # Tables
        st.markdown("---")
        c_tbl1, c_tbl2 = st.columns(2)
        
        with c_tbl1:
            st.subheader("🔥 الأكثر مبيعاً (كميات)")
            top_qty = df_filtered.groupby(['StockName', 'StockCode'])[['Qty', 'Amount']].sum().reset_index().sort_values('Qty', ascending=False).head(10)
            st.dataframe(top_qty.style.format({'Amount': '{:,.0f}'}), use_container_width=True)
            
        with c_tbl2:
            st.subheader("💎 الأكثر ربحية (كنوز المخزون)")
            top_profit = df_filtered.groupby(['StockName', 'StockCode'])[['Profit', 'Amount']].sum().reset_index().sort_values('Profit', ascending=False).head(10)
            # الآن ستعمل الألوان لأننا أضفنا matplotlib
            st.dataframe(top_profit.style.format({'Profit': '{:,.0f}', 'Amount': '{:,.0f}'}).background_gradient(subset=['Profit'], cmap='Greens'), use_container_width=True)

else:
    st.info("👈 بانتظار ملفاتك.. النظام جاهز!")
