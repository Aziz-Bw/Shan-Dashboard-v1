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

# --- 🎨 التصميم (CSS) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
    }

    :root {
        --brand-blue: #034275;
        --brand-dark: #2c3e50;
        --card-bg: #ffffff;
    }

    /* إخفاء العناصر المزعجة */
    [data-testid="stSidebar"] {display: none;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* الحاويات */
    .filters-box {
        background-color: var(--card-bg);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border-top: 4px solid var(--brand-blue);
        margin-bottom: 25px;
    }

    /* --- بطاقات المؤشرات (KPIs) - الصف العلوي --- */
    .metric-card {
        background-color: var(--card-bg) !important;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px 5px; /* تقليل الحواف الجانبية */
        text-align: center;
        box-shadow: 0 3px 6px rgba(0,0,0,0.05);
        height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-5px); }
    
    .metric-label {
        color: #666 !important;
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 5px;
        white-space: nowrap; /* منع التفاف النص */
    }
    
    .metric-value {
        color: var(--brand-blue) !important;
        font-size: 22px; /* تصغير الخط قليلاً ليسع 6 كروت */
        font-weight: 800;
        margin: 0;
        direction: ltr;
    }
    
    .metric-sub {
        color: #888 !important;
        font-size: 11px;
        margin-top: 5px;
        font-weight: bold;
    }

    /* --- بطاقات البائعين --- */
    .salesman-box {
        background-color: var(--card-bg) !important;
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        border-right: 5px solid var(--brand-blue);
        margin-bottom: 15px;
        direction: rtl;
    }

    .s-header {
        border-bottom: 1px solid #eee;
        padding-bottom: 10px;
        margin-bottom: 12px;
        text-align: right;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .s-name {
        color: var(--brand-blue) !important;
        font-size: 18px;
        font-weight: 800;
    }

    .s-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
        direction: rtl;
        border-bottom: 1px dashed #f5f5f5; /* خط خفيف بين الأسطر */
        padding-bottom: 4px;
    }
    .s-row:last-child { border-bottom: none; }
    
    .s-label { color: #555 !important; font-size: 13px; font-weight: 600; }
    .s-val { color: #333 !important; font-size: 14px; font-weight: 800; font-family: 'Tajawal', sans-serif; }

    /* أنيميشن */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .row-anim { animation: fadeInUp 0.8s ease-out forwards; opacity: 0; }
    .d-1 { animation-delay: 0.1s; }
    .d-2 { animation-delay: 0.3s; }
    .d-3 { animation-delay: 0.5s; }
    .d-4 { animation-delay: 0.7s; }
    .d-5 { animation-delay: 0.9s; }

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
        <div style="text-align: center; padding: 40px; animation: fadeIn 1.5s;">
            <img src="https://cdn-icons-png.flaticon.com/512/3135/3135715.png" width="100">
            <h1 style="color:#034275; margin-top:15px;">شان الحديثة | Shan Modern</h1>
            <p style="color:#666;">بوابة التحليل المالي الذكي</p>
        </div>
        """, unsafe_allow_html=True)
        password = st.text_input("🔑 رمز المرور", type="password")
        if password:
            if password == st.secrets["PASSWORD"]:
                st.session_state['page'] = 'upload'
                st.rerun()
            else:
                st.error("الرمز غير صحيح")

# >> صفحة الرفع <<
elif st.session_state['page'] == 'upload':
    st.markdown("""
    <div style="text-align: center; margin: 30px auto; max-width:600px; animation: fadeInUp 0.8s;">
        <h2 style="color:#034275;">📤 استيراد البيانات</h2>
        <p style="color:#555; line-height:1.6;">يرجى رفع ملفات XML المستخرجة من نظام المبيعات.</p>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        f1 = st.file_uploader("1. ملف الفواتير (StockInvoiceDetails.xml)", type=['xml'])
        f2 = st.file_uploader("2. ملف الأصناف (StockInvoiceRowItems.xml)", type=['xml'])
        
        if f1 and f2:
            st.session_state['uploaded_files'] = (f1, f2)
            st.session_state['page'] = 'dashboard'
            with st.spinner("جاري تحليل البيانات..."):
                time.sleep(1)
            st.rerun()

# >> الداشبورد <<
elif st.session_state['page'] == 'dashboard':
    f1, f2 = st.session_state['uploaded_files']
    df = load_auto_data(f1, f2)
    
    if df is not None:
        # Header Row (Lego 1)
        st.markdown('<div class="row-anim d-1">', unsafe_allow_html=True)
        h1, h2 = st.columns([8, 1])
        with h1:
            st.markdown("<h2 style='color:#034275; margin:0;'>📊 لوحة المعلومات المالية والفنية</h2>", unsafe_allow_html=True)
        with h2:
            with st.popover("⚙️"):
                if st.button("تسجيل الخروج"):
                    st.session_state['uploaded_files'] = None
                    st.session_state['page'] = 'login'
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Filters (Lego 2)
        st.markdown('<div class="row-anim d-2 filters-box">', unsafe_allow_html=True)
        min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
        fc1, fc2 = st.columns(2)
        with fc1: d_range = st.date_input("📅 الفترة الزمنية", [min_d, max_d])
        with fc2:
            s_list = ['الكل'] + sorted(list(df['SalesMan_Clean'].astype(str).unique()))
            s_filter = st.selectbox("👤 الموظف المسؤول", s_list)
        st.markdown('</div>', unsafe_allow_html=True)

        # Apply Filters
        df_filtered = df.copy()
        if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
            df_filtered = df_filtered[(df_filtered['Date'].dt.date >= d_range[0]) & (df_filtered['Date'].dt.date <= d_range[1])]
        if s_filter != 'الكل':
            df_filtered = df_filtered[df_filtered['SalesMan_Clean'] == s_filter]

        # Calculate KPIs
        net_sales = df_filtered['Amount'].sum()
        total_cost = df_filtered['TotalCost'].sum()
        total_profit = df_filtered['Profit'].sum()
        
        # المرتجعات (قيمة وعدد)
        returns_data = df_filtered[df_filtered['Amount'] < 0]
        returns_val = abs(returns_data['Amount'].sum())
        returns_count = returns_data['TransCode'].nunique()
        
        # عدد الفواتير (فقط المبيعات الموجبة)
        invoices_count = df_filtered[df_filtered['Amount'] > 0]['TransCode'].nunique()
        
        margin = (total_profit / net_sales * 100) if net_sales > 0 else 0
        days_diff = (d_range[1] - d_range[0]).days if isinstance(d_range, (list, tuple)) and len(d_range) == 2 else 1
        months_diff = max(days_diff / 30, 1)

        # KPIs Row (Lego 3) - توسيع لـ 6 أعمدة
        st.markdown('<div class="row-anim d-3">', unsafe_allow_html=True)
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        
        def metric_card(title, value, sub, color="#034275"):
            return f"""
            <div class="metric-card">
                <div class="metric-label">{title}</div>
                <div class="metric-value" style="color: {color} !important;">{value}</div>
                <div class="metric-sub">{sub}</div>
            </div>
            """

        with k1: st.markdown(metric_card("صافي المبيعات", f"{net_sales:,.0f}", "الإيراد الفعلي"), unsafe_allow_html=True)
        with k2: st.markdown(metric_card("صافي الربح", f"{total_profit:,.0f}", f"{margin:.1f}% هامش", "#27ae60"), unsafe_allow_html=True)
        with k3: st.markdown(metric_card("تكلفة البضاعة", f"{total_cost:,.0f}", "Cost"), unsafe_allow_html=True)
        with k4: st.markdown(metric_card("الإرجاعات", f"{returns_val:,.0f}", f"عدد: {returns_count}", "#c0392b"), unsafe_allow_html=True)
        with k5: st.markdown(metric_card("عدد الفواتير", f"{invoices_count}", "فاتورة مبيعات"), unsafe_allow_html=True)
        with k6: st.markdown(metric_card("متوسط المبيعات", f"{net_sales/months_diff:,.0f}", "للفترة (شهرياً)"), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Salesmen Row (Lego 4)
        st.markdown('<div class="row-anim d-4">', unsafe_allow_html=True)
        st.subheader("👥 أداء الفريق")
        
        unique_salesmen = [sm for sm in df_filtered['SalesMan_Clean'].unique() if sm != 'غير محدد']
        cols = st.columns(3)
        
        def draw_salesman(col, name, data, is_total=False):
            s_net_sales = data['Amount'].sum()
            s_profit = data['Profit'].sum()
            s_margin = (s_profit / s_net_sales * 100) if s_net_sales > 0 else 0
            
            # تفاصيل المرتجعات
            s_ret_data = data[data['Amount'] < 0]
            s_ret_val = abs(s_ret_data['Amount'].sum())
            s_ret_count = s_ret_data['TransCode'].nunique()
            
            # تفاصيل الفواتير
            s_inv_count = data[data['Amount'] > 0]['TransCode'].nunique()
            
            # نسبة الإرجاع من الإجمالي
            s_gross = data[data['Amount'] > 0]['Amount'].sum()
            s_ret_rate = (s_ret_val / s_gross * 100) if s_gross > 0 else 0
            
            border = "#27ae60" if is_total else "#034275"
            name_col = "#333" if is_total else "#034275"
            
            html = f"""
            <div class="salesman-box" style="border-right: 5px solid {border};">
                <div class="s-header">
                    <div class="s-name" style="color:{name_col} !important">{name}</div>
                    {'<span style="font-size:11px; background:#eee; padding:2px 6px; border-radius:4px;">الإجمالي</span>' if is_total else ''}
                </div>
                <div class="s-row"><span class="s-label">💰 المبيعات:</span><span class="s-val">{s_net_sales:,.0f}</span></div>
                <div class="s-row"><span class="s-label">📈 الربح:</span><span class="s-val" style="color:#27ae60 !important">{s_profit:,.0f} ({s_margin:.1f}%)</span></div>
                <div class="s-row"><span class="s-label">🧾 الفواتير:</span><span class="s-val">{s_inv_count}</span></div>
                <div class="s-row" style="border-top:1px dashed #ddd; margin-top:6px; padding-top:4px;">
                    <span class="s-label" style="color:#c0392b !important">↩️ الإرجاع:</span>
                    <span class="s-val" style="color:#c0392b !important">{s_ret_val:,.0f} ({s_ret_count})</span>
                </div>
            </div>
            """
            with col: st.markdown(html, unsafe_allow_html=True)

        idx = 0
        for sm in unique_salesmen:
            if idx < 2:
                draw_salesman(cols[idx], sm, df_filtered[df_filtered['SalesMan_Clean'] == sm])
                idx += 1
        draw_salesman(cols[2], "إجمالي الفريق", df_filtered, is_total=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Charts & Tables (Lego 5 & 6)
        st.markdown('<div class="row-anim d-5">', unsafe_allow_html=True)
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
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="row-anim d-6">', unsafe_allow_html=True)
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
        st.markdown('</div>', unsafe_allow_html=True)
