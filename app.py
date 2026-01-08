import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="مدير قطع الغيار الآلي", layout="wide", page_icon="🚀")

# CSS
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
    st.title("🔒 تسجيل الدخول"); password = st.text_input("كلمة المرور", type="password")
    if password == st.secrets["PASSWORD"]: st.session_state["password"] = password; st.rerun()
    else: st.stop()

# --- دالة تنظيف أسماء البائعين (جديد) ---
def normalize_salesman_name(name):
    if pd.isna(name) or name == 'nan' or name == 'غير محدد':
        return 'غير محدد'
    
    name = str(name).strip()
    
    # توحيد "سعيد" و "السعيد"
    if 'سعيد' in name:
        return 'سعيد'
    
    # توحيد "عبد الله" و "عبدالله"
    if 'عبد' in name and 'الله' in name:
        return 'عبد الله'
        
    return name

# --- 3. المعالجة الآلية ---
@st.cache_data(ttl=3600)
def load_auto_data(file_header, file_items):
    try:
        # قراءة الملفات
        tree_h = ET.parse(file_header); df_header = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_h.getroot()])
        tree_i = ET.parse(file_items); df_items = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_i.getroot()])
        
        # 1. فلترة المحذوفات
        if 'IsDelete' in df_header.columns:
            df_header = df_header[~df_header['IsDelete'].isin(['True', 'true', '1'])]

        # 2. الفرز الآلي للسندات
        sales_keywords = ['بيع', 'Sale', 'Invoice', 'Cash', 'Credit']
        exclude_keywords = ['شراء', 'Purchase', 'Quot', 'عرض', 'Order', 'طلب']
        
        def classify_voucher(v_name):
            v_str = str(v_name).lower()
            if any(x.lower() in v_str for x in exclude_keywords): return 'Ignore'
            if any(x.lower() in v_str for x in sales_keywords): return 'Keep'
            return 'Ignore'

        df_header['Action'] = df_header['VoucherName'].apply(classify_voucher)
        df_header = df_header[df_header['Action'] == 'Keep']

        # 3. تنظيف التاريخ
        df_header['Date'] = pd.to_datetime(pd.to_numeric(df_header['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
        
        # --- معالجة البائع (التحسين الجديد) ---
        # نجهز اسم البائع في الفاتورة
        if 'SalesPerson' in df_header.columns:
            df_header['Header_SalesMan'] = df_header['SalesPerson'].fillna('')
        else:
            df_header['Header_SalesMan'] = ''

        # 4. معالجة الأصناف
        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        
        # المبيعات (الصافي)
        if 'TaxbleAmount' in df_items.columns:
            df_items['Amount'] = pd.to_numeric(df_items['TaxbleAmount'], errors='coerce').fillna(0)
        elif 'BasicStockAmount' in df_items.columns:
            df_items['Amount'] = pd.to_numeric(df_items['BasicStockAmount'], errors='coerce').fillna(0)
        else:
            df_items['Amount'] = pd.to_numeric(df_items['netStockAmount'], errors='coerce').fillna(0) / 1.15

        # التكلفة (PresetRate)
        cost_col = 'PresetRate'
        if cost_col in df_items.columns:
            df_items['CostUnit'] = pd.to_numeric(df_items[cost_col], errors='coerce').fillna(0)
        elif 'PresetRate2' in df_items.columns:
             df_items['CostUnit'] = pd.to_numeric(df_items['PresetRate2'], errors='coerce').fillna(0)
        else:
            df_items['CostUnit'] = 0
            
        df_items['TotalCost'] = df_items['CostUnit'] * df_items['Qty']
        
        # تنظيف الأعمدة المكررة ما عدا SalesMan في الأصناف
        cols_to_drop = ['VoucherName', 'SalesPerson', 'Action'] # أزلنا SalesMan من هنا لنحتفظ به
        for col in cols_to_drop:
            if col in df_items.columns: df_items = df_items.drop(columns=[col])

        # 5. الدمج
        full_data = pd.merge(df_items, df_header[['TransCode', 'Date', 'LedgerName', 'InvoiceNo', 'Header_SalesMan', 'VoucherName']], on='TransCode', how='inner')
        
        # --- المنطق الذكي لاسم البائع ---
        # إذا وجدنا اسم في ملف الأصناف نأخذه، وإلا نأخذ من الفاتورة
        if 'SalesMan' in full_data.columns:
            full_data['Final_SalesMan'] = full_data['SalesMan'].fillna(full_data['Header_SalesMan'])
        else:
            full_data['Final_SalesMan'] = full_data['Header_SalesMan']
            
        # تطبيق التوحيد (سعيد = السعيد)
        full_data['SalesMan_Clean'] = full_data['Final_SalesMan'].apply(normalize_salesman_name)

        # 6. المرتجعات
        mask_return = full_data['VoucherName'].str.contains('Return|مرتجع', case=False, na=False)
        full_data.loc[mask_return, 'Amount'] = full_data.loc[mask_return, 'Amount'] * -1
        full_data.loc[mask_return, 'TotalCost'] = full_data.loc[mask_return, 'TotalCost'] * -1
        
        full_data['Profit'] = full_data['Amount'] - full_data['TotalCost']
        
        if 'stockgroup' not in full_data.columns: full_data['stockgroup'] = 'عام'

        return full_data.dropna(subset=['Date'])
    except Exception as e: st.error(f"خطأ فني: {e}"); return None

# --- 4. الواجهة ---
st.title("🚀 لوحة القيادة الآلية (إصلاح البائعين)")
st.caption("تم ضبط الأسماء: (سعيد + السعيد) | (عبدالله + عبد الله)")

with st.sidebar:
    st.header("📂 الملفات")
    f1 = st.file_uploader("1. ملف الفواتير (StockInvoiceDetails)", type=['xml'])
    f2 = st.file_uploader("2. ملف الأصناف (StockInvoiceRowItems)", type=['xml'])

if f1 and f2:
    df = load_auto_data(f1, f2)
    
    if df is not None:
        # الفلاتر
        st.sidebar.markdown("---")
        min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
        c1, c2 = st.columns(2)
        with c1: d_range = st.date_input("📅 الفترة", [min_d, max_d])
        with c2: 
            # استخدام الاسم المنظف
            salesman_list = ['الكل'] + sorted(list(df['SalesMan_Clean'].astype(str).unique()))
            salesman_filter = st.selectbox("👤 البائع", salesman_list)

        df_filtered = df.copy()
        if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
            df_filtered = df_filtered[(df_filtered['Date'].dt.date >= d_range[0]) & (df_filtered['Date'].dt.date <= d_range[1])]
        
        if salesman_filter != 'الكل':
            df_filtered = df_filtered[df_filtered['SalesMan_Clean'] == salesman_filter]

        st.markdown("---")

        # KPIs
        total_sales = df_filtered['Amount'].sum()
        total_profit = df_filtered['Profit'].sum()
        total_cost = df_filtered['TotalCost'].sum()
        margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
        inv_count = df_filtered['TransCode'].nunique()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 صافي المبيعات", f"{total_sales:,.0f} ر.س")
        k2.metric("📉 التكلفة", f"{total_cost:,.0f} ر.س")
        k3.metric("📈 صافي الربح", f"{total_profit:,.0f} ر.س", delta=f"{margin:.1f}%")
        k4.metric("🧾 العمليات", f"{inv_count}")

        # Charts
        st.markdown("### 📊 التحليل")
        tab1, tab2, tab3 = st.tabs(["يومياً", "بائعين", "مجموعات"])
        
        with tab1:
            daily_data = df_filtered.groupby('Date')[['Amount', 'Profit']].sum().reset_index()
            st.plotly_chart(px.line(daily_data, x='Date', y=['Amount', 'Profit'], markers=True), use_container_width=True)
            
        with tab2:
            # الرسم البياني يستخدم الاسم النظيف الآن
            salesman_perf = df_filtered.groupby('SalesMan_Clean')[['Amount', 'Profit']].sum().reset_index().sort_values('Amount', ascending=False)
            st.plotly_chart(px.bar(salesman_perf, x='SalesMan_Clean', y=['Amount', 'Profit'], barmode='group', text_auto='.2s'), use_container_width=True)
            
        with tab3:
            group_perf = df_filtered.groupby('stockgroup')[['Amount', 'Profit']].sum().reset_index().sort_values('Profit', ascending=False).head(10)
            st.plotly_chart(px.pie(group_perf, values='Profit', names='stockgroup', hole=0.4), use_container_width=True)

        # Tables
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🔥 الأكثر مبيعاً")
            top_qty = df_filtered.groupby(['StockName', 'StockCode'])[['Qty', 'Amount']].sum().reset_index().sort_values('Qty', ascending=False).head(10)
            st.dataframe(top_qty.style.format({'Amount': '{:,.0f}'}), use_container_width=True)
        with c2:
            st.subheader("💎 الأكثر ربحية")
            top_profit = df_filtered.groupby(['StockName', 'StockCode'])[['Profit', 'Amount']].sum().reset_index().sort_values('Profit', ascending=False).head(10)
            st.dataframe(top_profit.style.format({'Profit': '{:,.0f}', 'Amount': '{:,.0f}'}).background_gradient(subset=['Profit'], cmap='Greens'), use_container_width=True)

else:
    st.info("👈 ارفع الملفات.. وتمتع بالأرقام الصحيحة!")
