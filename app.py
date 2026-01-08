import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET
import time

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="Shan Modern | شان الحديثة", 
    layout="wide", 
    page_icon="🏢",
    initial_sidebar_state="collapsed"
)

# --- 🎨 التصميم (CSS) - إصلاح الألوان والتباين ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800&display=swap');

    /* تطبيق الخط وتوحيد الأساسيات */
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
    }

    /* تعريف الألوان الصلبة (لا تتأثر بوضع الجهاز) */
    :root {
        --brand-blue: #034275;
        --brand-dark: #2c3e50;
        --brand-text: #333333; /* لون نص غامق ثابت */
        --card-bg: #ffffff;    /* خلفية بيضاء ثابتة */
    }

    /* إخفاء العناصر المزعجة */
    [data-testid="stSidebar"] {display: none;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* --- تنسيق الحاويات --- */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* حاوية الفلاتر العلوية */
    .filters-box {
        background-color: var(--card-bg);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border-top: 4px solid var(--brand-blue);
        margin-bottom: 25px;
    }

    /* --- تصميم البطاقات (KPIs) --- */
    /* نستخدم !important لإجبار الألوان وتجاهل الوضع الليلي */
    .metric-card {
        background-color: var(--card-bg) !important;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    
    .metric-label {
        color: #666666 !important;
        font-size: 14px;
        font-weight: bold;
        margin-bottom: 8px;
    }
    
    .metric-value {
        color: var(--brand-blue) !important;
        font-size: 24px;
        font-weight: 800;
        margin: 0;
        direction: ltr; /* لضمان ظهور الأرقام بشكل صحيح */
    }
    
    .metric-sub {
        color: #888888 !important;
        font-size: 12px;
        margin-top: 5px;
    }

    /* --- بطاقات البائعين (Salesman) --- */
    .salesman-box {
        background-color: var(--card-bg) !important;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        border-right: 5px solid var(--brand-blue);
        margin-bottom: 15px;
        direction: rtl;
    }

    .s-header {
        border-bottom: 1px solid #eee;
        padding-bottom: 10px;
        margin-bottom: 15px;
        text-align: right;
    }
    
    .s-name {
        color: var(--brand-blue) !important;
        font-size: 18px;
        font-weight: 800;
    }

    /* صفوف البيانات داخل البطاقة */
    .s-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
        direction: rtl;
    }
    
    /* إجبار النصوص داخل البطاقة على اللون الغامق */
    .s-label {
        color: #555555 !important;
        font-size: 14px;
        font-weight: 500;
    }
    
    .s-val {
        color: #333333 !important;
        font-size: 15px;
        font-weight: 700;
        font-family: 'Tajawal', sans-serif;
    }

    /* أنيميشن الدخول */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-in {
        animation: fadeIn 0.6s ease-out forwards;
    }

</style>
""", unsafe_allow_html=True)

# --- 2. إدارة الحالة ---
if 'page' not in st.session_state: st.session_state['page'] = 'login'
if 'uploaded_files' not in st.session_state: st.session_state['uploaded_files'] = None

# --- 3. المعالجة ---
def normalize_salesman_name(name):
    if pd.isna(name) or name == 'nan' or name == 'غير محدد': return 'غير محدد'
    name = str(name).strip()
    if 'سعيد' in name: return 'سعيد'
    if 'عبد' in name and 'الله' in name: return 'عبد الله'
    return name

@st.cache_data(ttl=3600)
def load_auto_data(file_header, file_items):
    try:
        tree_h = ET.parse(file_header); df_header = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_h.getroot()])
        tree_i = ET.parse(file_items); df_items = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_i.getroot()])
        
        if 'IsDelete' in df_header.columns: df_header = df_header[~df_header['IsDelete'].isin(['True', 'true', '1'])]

        sales_keywords = ['بيع', 'Sale', 'Invoice', 'Cash', 'Credit']
        exclude_keywords = ['شراء', 'Purchase', 'Quot', 'عرض', 'Order', 'طلب']
        
        def classify_voucher(v_name):
            v_str = str(v_name).lower()
            if any(x.lower() in v_str for x in exclude_keywords): return 'Ignore'
            if any(x.lower() in v_str for x in sales_keywords): return 'Keep'
            return 'Ignore'

        df_header['Action'] = df_header['VoucherName'].apply(classify_voucher)
        df_header = df_header[df_header['Action'] == 'Keep']
        df_header['Date'] = pd.to_datetime(pd.to_numeric(df_header['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
        
        if 'SalesPerson' in df_header.columns: df_header['Header_SalesMan'] = df_header['SalesPerson'].fillna('')
        else: df_header['Header_SalesMan'] = ''

        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        if 'TaxbleAmount' in df_items.columns: df_items['Amount'] = pd.to_numeric(df_items['TaxbleAmount'], errors='coerce').fillna(0)
        elif 'BasicStockAmount' in df_items.columns: df_items['Amount'] = pd.to_numeric(df_items['BasicStockAmount'], errors='coerce').fillna(0)
        else: df_items['Amount'] = pd.to_numeric(df_items['netStockAmount'], errors='coerce').fillna(0) / 1.15

        cost_col = 'PresetRate'
        if cost_col in df_items.columns: df_items['CostUnit'] = pd.to_numeric(df_items[cost_col], errors='coerce').fillna(0)
        elif 'PresetRate2' in df_items.columns: df_items['CostUnit'] = pd.to_numeric(df_items['PresetRate2'], errors='coerce').fillna(0)
        else: df_items['CostUnit'] = 0
            
        df_items['TotalCost'] = df_items['CostUnit'] * df_items['Qty']
        
        cols_to_drop = ['VoucherName', 'SalesPerson', 'Action']
        for col in cols_to_drop:
            if col in df_items.columns: df_items = df_items.drop(columns=[col])

        full_data = pd.merge(df_items, df_header[['TransCode', 'Date', 'LedgerName', 'InvoiceNo', 'Header_SalesMan', 'VoucherName']], on='TransCode', how='inner')
        
        if 'SalesMan' in full_data.columns: full_data['Final_SalesMan'] = full_data['SalesMan'].fillna(full_data['Header_SalesMan'])
        else: full_data['Final_SalesMan'] = full_data['Header_SalesMan']
            
        full_data['SalesMan_Clean'] = full_data['Final_SalesMan'].apply(normalize_salesman_name)

        mask_return = full_data['VoucherName'].str.contains('Return|مرتجع', case=False, na=False)
        full_data.loc[mask_return, 'Amount'] = full_data.loc[mask_return, 'Amount'] * -1
        full_data.loc[mask_return, 'TotalCost'] = full_data.loc[mask_return, 'TotalCost'] * -1
        full_data['Profit'] = full_data['Amount'] - full_data['TotalCost']
        
        if 'stockgroup' not in full_data.columns: full_data['stockgroup'] = 'عام'

        return full_data.dropna(subset=['Date'])
    except Exception as e: st.error(f"Error: {e}"); return None

# --- 4. واجهة المستخدم ---

# >> صفحة الدخول <<
if st.session_state['page'] == 'login':
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("""
        <div style="text-align: center; padding: 40px;">
            <h1 style="color:#034275;">شان الحديثة | Shan Modern</h1>
            <p style="color:#666;">نظام ذكاء الأعمال المتقدم</p>
        </div>
        """, unsafe_allow_html=True)
        password = st.text_input("🔑 أدخل رمز المرور", type="password")
        if password:
            if password == st.secrets["PASSWORD"]:
                st.session_state['page'] = 'upload'
                st.rerun()
            else:
                st.error("الرمز غير صحيح")

# >> صفحة الرفع <<
elif st.session_state['page'] == 'upload':
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;" class="animate-in">
        <h2 style="color:#034275;">📂 استيراد البيانات</h2>
        <p style="color:#555;">يرجى رفع ملفات XML من النسخ الاحتياطي للنظام</p>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        f1 = st.file_uploader("1. ملف الفواتير (StockInvoiceDetails.xml)", type=['xml'])
        f2 = st.file_uploader("2. ملف الأصناف (StockInvoiceRowItems.xml)", type=['xml'])
        
        if f1 and f2:
            st.session_state['uploaded_files'] = (f1, f2)
            st.session_state['page'] = 'dashboard'
            st.success("تم التحقق من الملفات.. جاري بناء اللوحة")
            time.sleep(1)
            st.rerun()

# >> الداشبورد <<
elif st.session_state['page'] == 'dashboard':
    f1, f2 = st.session_state['uploaded_files']
    df = load_auto_data(f1, f2)
    
    if df is not None:
        # رأس الصفحة مع زر الإعدادات
        head_c1, head_c2 = st.columns([10, 1])
        with head_c1:
            st.markdown("<h2 style='color:#034275; margin:0;'>📊 لوحة المعلومات المالية</h2>", unsafe_allow_html=True)
        with head_c2:
            with st.popover("⚙️"):
                if st.button("تسجيل الخروج"):
                    st.session_state['uploaded_files'] = None
                    st.session_state['page'] = 'login'
                    st.rerun()

        # الفلاتر العلوية
        st.markdown('<div class="filters-box animate-in">', unsafe_allow_html=True)
        min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
        fc1, fc2 = st.columns(2)
        with fc1:
            d_range = st.date_input("📅 الفترة الزمنية", [min_d, max_d])
        with fc2:
            salesman_list = ['الكل'] + sorted(list(df['SalesMan_Clean'].astype(str).unique()))
            salesman_filter = st.selectbox("👤 الموظف", salesman_list)
        st.markdown('</div>', unsafe_allow_html=True)

        # تطبيق الفلاتر
        df_filtered = df.copy()
        if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
            df_filtered = df_filtered[(df_filtered['Date'].dt.date >= d_range[0]) & (df_filtered['Date'].dt.date <= d_range[1])]
        if salesman_filter != 'الكل':
            df_filtered = df_filtered[df_filtered['SalesMan_Clean'] == salesman_filter]

        # الحسابات
        gross_sales = df_filtered[df_filtered['Amount'] > 0]['Amount'].sum()
        returns_val = abs(df_filtered[df_filtered['Amount'] < 0]['Amount'].sum())
        net_sales = df_filtered['Amount'].sum()
        total_profit = df_filtered['Profit'].sum()
        total_cost = df_filtered['TotalCost'].sum()
        margin = (total_profit / net_sales * 100) if net_sales > 0 else 0
        days_diff = (d_range[1] - d_range[0]).days if isinstance(d_range, (list, tuple)) and len(d_range) == 2 else 1
        months_diff = max(days_diff / 30, 1)

        # 1. المؤشرات (Cards)
        k1, k2, k3, k4, k5 = st.columns(5)
        
        # HTML نظيف جداً لتجنب الأخطاء
        def card_html(label, value, sub, color="#034275"):
            return f"""
            <div class="metric-card animate-in">
                <div class="metric-label">{label}</div>
                <div class="metric-value" style="color: {color} !important;">{value}</div>
                <div class="metric-sub">{sub}</div>
            </div>
            """

        with k1: st.markdown(card_html("صافي المبيعات", f"{net_sales:,.0f}", "الإيراد الفعلي"), unsafe_allow_html=True)
        with k2: st.markdown(card_html("تكلفة البضاعة", f"{total_cost:,.0f}", "Cost"), unsafe_allow_html=True)
        with k3: st.markdown(card_html("إجمالي الإرجاعات", f"{returns_val:,.0f}", "مخصومة", "#c0392b"), unsafe_allow_html=True)
        with k4: st.markdown(card_html("صافي الأرباح", f"{total_profit:,.0f}", f"{margin:.1f}% هامش", "#27ae60"), unsafe_allow_html=True)
        with k5: st.markdown(card_html("المتوسط الشهري", f"{net_sales/months_diff:,.0f}", "معدل الأداء"), unsafe_allow_html=True)

        st.markdown("---")

        # 2. أداء الفريق
        st.subheader("👥 أداء الفريق")
        unique_salesmen = [sm for sm in df_filtered['SalesMan_Clean'].unique() if sm != 'غير محدد']
        cols = st.columns(3)
        
        def draw_salesman(col, name, data, is_total=False):
            s_sales = data['Amount'].sum()
            s_profit = data['Profit'].sum()
            s_margin = (s_profit / s_sales * 100) if s_sales > 0 else 0
            s_ret = abs(data[data['Amount'] < 0]['Amount'].sum())
            s_gross = data[data['Amount'] > 0]['Amount'].sum()
            s_ret_rate = (s_ret / s_gross * 100) if s_gross > 0 else 0
            
            border = "#27ae60" if is_total else "#034275"
            name_col = "#333" if is_total else "#034275"
            
            # HTML بدون مسافات بادئة زائدة لتجنب مشاكل التفسير
            html_content = f"""
            <div class="salesman-box" style="border-right: 5px solid {border};">
                <div class="s-header">
                    <div class="s-name" style="color:{name_col} !important">{name}</div>
                </div>
                <div class="s-row">
                    <span class="s-label">المبيعات:</span>
                    <span class="s-val">{s_sales:,.0f}</span>
                </div>
                <div class="s-row">
                    <span class="s-label">الربح:</span>
                    <span class="s-val" style="color:#27ae60 !important">{s_profit:,.0f} ({s_margin:.1f}%)</span>
                </div>
                <div class="s-row" style="border-top:1px dashed #ddd; margin-top:8px; padding-top:5px;">
                    <span class="s-label" style="color:#c0392b !important">الإرجاع:</span>
                    <span class="s-val" style="color:#c0392b !important">{s_ret:,.0f} ({s_ret_rate:.1f}%)</span>
                </div>
            </div>
            """
            with col:
                st.markdown(html_content, unsafe_allow_html=True)

        curr_idx = 0
        for sm in unique_salesmen:
            if curr_idx < 2:
                draw_salesman(cols[curr_idx], sm, df_filtered[df_filtered['SalesMan_Clean'] == sm])
                curr_idx += 1
        draw_salesman(cols[2], "إجمالي الفريق", df_filtered, is_total=True)

        # 3. الرسوم والجداول
        st.markdown("---")
        tab1, tab2 = st.tabs(["التدفق الزمني", "توزيع الماركات"])
        with tab1:
            daily = df_filtered.groupby('Date')[['Amount', 'Profit']].sum().reset_index()
            fig = px.line(daily, x='Date', y=['Amount', 'Profit'], markers=True, color_discrete_map={'Amount': '#034275', 'Profit': '#27ae60'})
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", font={'color': '#333'})
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            gp = df_filtered.groupby('stockgroup')[['Amount', 'Profit']].sum().reset_index().sort_values('Profit', ascending=False).head(10)
            fig_pie = px.pie(gp, values='Profit', names='stockgroup', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
            st.plotly_chart(fig_pie, use_container_width=True)

        # 4. التقرير
        st.markdown("---")
        c1, c2 = st.columns([3, 1])
        with c1: st.subheader("📦 تقرير المخزون")
        
        items_sum = df_filtered.groupby(['StockName', 'StockCode', 'stockgroup']).agg(
            الكمية=('Qty', 'sum'),
            المبيعات=('Amount', 'sum'),
            الربح=('Profit', 'sum')
        ).reset_index()
        items_sum['هامش_%'] = (items_sum['الربح'] / items_sum['المبيعات'] * 100).fillna(0)
        items_sum['تصريف_شهري'] = items_sum['الكمية'] / months_diff
        items_sum = items_sum.sort_values('الربح', ascending=False)
        
        with c2:
            csv = items_sum.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 تحميل التقرير", data=csv, file_name="Shan_Report.csv", mime="text/csv")

        st.dataframe(items_sum, use_container_width=True, height=600)
