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

# --- 🎨 تصميم الأنيميشن والهوية (Magic CSS) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        scroll-behavior: smooth;
    }

    :root {
        --brand-blue: #034275;
        --brand-accent: #27ae60;
        --bg-color: #f8f9fa;
    }

    /* إخفاء العناصر المزعجة */
    [data-testid="stSidebar"] {display: none;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* --- 🎥 تعريف حركات الأنيميشن (The Magic) --- */
    
    /* حركة الظهور الناعم من الأسفل (لصفوف الداشبورد) */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* حركة التلاشي (للترحيب) */
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    /* تطبيق الحركات بتأخير زمني (Lego Effect) */
    .row-1 { animation: fadeInUp 0.8s ease-out forwards; opacity: 0; animation-delay: 0.1s; } /* العنوان */
    .row-2 { animation: fadeInUp 0.8s ease-out forwards; opacity: 0; animation-delay: 0.3s; } /* الفلاتر */
    .row-3 { animation: fadeInUp 0.8s ease-out forwards; opacity: 0; animation-delay: 0.5s; } /* الأرقام */
    .row-4 { animation: fadeInUp 0.8s ease-out forwards; opacity: 0; animation-delay: 0.7s; } /* البائعين */
    .row-5 { animation: fadeInUp 0.8s ease-out forwards; opacity: 0; animation-delay: 0.9s; } /* الرسوم */
    .row-6 { animation: fadeInUp 0.8s ease-out forwards; opacity: 0; animation-delay: 1.1s; } /* الجداول */

    /* --- تصميم العناصر --- */

    /* حاوية الفلاتر */
    .filters-container {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
        border-top: 4px solid var(--brand-blue);
        margin-bottom: 25px;
    }

    /* البطاقات */
    .metric-container {
        background: white; border-radius: 12px; padding: 20px; text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.04); border: 1px solid #eee;
        height: 150px; display: flex; flex-direction: column; justify-content: center;
        transition: transform 0.3s ease;
    }
    .metric-container:hover { transform: translateY(-5px); box-shadow: 0 8px 20px rgba(0,0,0,0.08); }
    .metric-value { font-size: 28px; font-weight: 800; margin: 5px 0; color: var(--brand-blue); }
    .metric-label { font-size: 14px; color: #666; font-weight: bold; }
    
    /* بطاقات البائعين */
    .salesman-box {
        background: white; border-radius: 12px; padding: 20px; margin-bottom: 15px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.04); border-right: 5px solid var(--brand-blue);
        direction: rtl; transition: all 0.3s ease;
    }
    .salesman-box:hover { transform: scale(1.02); }

    /* شاشة الترحيب */
    .welcome-container {
        text-align: center; margin-top: 100px;
        animation: fadeIn 1.5s ease-in;
    }
    .input-container { max-width: 400px; margin: 0 auto; }

</style>
""", unsafe_allow_html=True)

# --- 2. إدارة الحالة (Session State) ---
# نستخدم هذا لتتبع "نحن في أي صفحة؟"
if 'page' not in st.session_state:
    st.session_state['page'] = 'login' # login -> upload -> dashboard

if 'uploaded_files' not in st.session_state:
    st.session_state['uploaded_files'] = None

# --- 3. الدوال المساعدة ---
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


# --- 4. محرك السيناريو (The Logic Engine) ---

# >> المشهد 1: تسجيل الدخول <<
if st.session_state['page'] == 'login':
    st.markdown("""
    <div class="welcome-container">
        <img src="https://cdn-icons-png.flaticon.com/512/3135/3135715.png" width="120">
        <h1 style="color:#034275; margin-top:20px;">شان الحديثة | Shan Modern</h1>
        <p style="color:#666;">نظام ذكاء الأعمال والتحليل المالي</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        password = st.text_input("🔒 كلمة المرور", type="password", placeholder="أدخل الرمز هنا...")
        if password:
            if password == st.secrets["PASSWORD"]:
                st.session_state['page'] = 'upload'
                st.rerun()
            else:
                st.error("رمز غير صحيح")

# >> المشهد 2: رفع الملفات <<
elif st.session_state['page'] == 'upload':
    st.markdown("""
    <div class="welcome-container" style="margin-top:50px;">
        <h2 style="color:#034275;">📤 استيراد البيانات</h2>
        <p style="font-size:16px; color:#555; max-width:600px; margin:0 auto; line-height:1.6;">
            يرجى رفع ملفات XML المستخرجة من النسخ الاحتياطي لنظام المبيعات الخاص بشركة شان.
            سيتم معالجة البيانات وبناء لوحة المعلومات تلقائياً.
        </p>
        <br>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        f1 = st.file_uploader("1. ملف الفواتير (StockInvoiceDetails.xml)", type=['xml'])
        f2 = st.file_uploader("2. ملف الأصناف (StockInvoiceRowItems.xml)", type=['xml'])
        
        if f1 and f2:
            st.session_state['uploaded_files'] = (f1, f2)
            st.session_state['page'] = 'dashboard'
            with st.spinner("جاري بناء لوحة المعلومات..."):
                time.sleep(1.5) # تأثير بسيط للتشويق
            st.rerun()

# >> المشهد 3: الداشبورد الفخم (The Dashboard) <<
elif st.session_state['page'] == 'dashboard':
    
    f1, f2 = st.session_state['uploaded_files']
    df = load_auto_data(f1, f2)
    
    if df is not None:
        
        # --- زر الإعدادات المخفي (الترس) ---
        # يظهر في الأعلى لإعادة الرفع إذا لزم الأمر
        with st.container():
             c_title, c_gear = st.columns([9, 1])
             with c_gear:
                 with st.popover("⚙️ إعدادات"):
                     st.write("إعادة ضبط البيانات:")
                     if st.button("تسجيل الخروج / إعادة الرفع"):
                         st.session_state['uploaded_files'] = None
                         st.session_state['page'] = 'upload'
                         st.rerun()

        # --- الصف 1: العنوان والشعار (Lego Row 1) ---
        st.markdown('<div class="row-1">', unsafe_allow_html=True)
        h_col1, h_col2 = st.columns([1, 8])
        with h_col1:
            st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=70)
        with h_col2:
            st.markdown("<h2 style='margin:0; padding-top:10px;'>لوحة المعلومات المالية والفنية</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color:grey;'>Shan Modern Trading Co. | Live Data View</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- الصف 2: الفلاتر (Lego Row 2) ---
        st.markdown('<div class="row-2">', unsafe_allow_html=True)
        st.markdown('<div class="filters-container">', unsafe_allow_html=True)
        
        min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
        f_c1, f_c2 = st.columns(2)
        with f_c1:
            d_range = st.date_input("📅 الفترة الزمنية", [min_d, max_d])
        with f_c2:
            salesman_list = ['الكل'] + sorted(list(df['SalesMan_Clean'].astype(str).unique()))
            salesman_filter = st.selectbox("👤 الموظف المسؤول", salesman_list)
        
        st.markdown('</div></div>', unsafe_allow_html=True)

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

        # --- الصف 3: المؤشرات (Lego Row 3) ---
        st.markdown('<div class="row-3">', unsafe_allow_html=True)
        k1, k2, k3, k4, k5 = st.columns(5)
        
        def metric_card(title, value, sub, color="#034275"):
            return f"""
            <div class="metric-container">
                <div class="metric-label">{title}</div>
                <div class="metric-value" style="color: {color} !important;">{value}</div>
                <div class="metric-sub">{sub}</div>
            </div>
            """

        with k1: st.markdown(metric_card("صافي المبيعات", f"{net_sales:,.0f}", "الإيراد الفعلي"), unsafe_allow_html=True)
        with k2: st.markdown(metric_card("تكلفة البضاعة", f"{total_cost:,.0f}", "Cost of Goods"), unsafe_allow_html=True)
        with k3: st.markdown(metric_card("إجمالي الإرجاعات", f"{returns_val:,.0f}", "مخصومة", "#c0392b"), unsafe_allow_html=True)
        with k4: st.markdown(metric_card("صافي الأرباح", f"{total_profit:,.0f}", f"{margin:.1f}% هامش", "#27ae60"), unsafe_allow_html=True)
        with k5: st.markdown(metric_card("المتوسط الشهري", f"{net_sales/months_diff:,.0f}", "معدل الأداء"), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- الصف 4: البائعين (Lego Row 4) ---
        st.markdown('<div class="row-4">', unsafe_allow_html=True)
        st.subheader("👥 أداء الفريق")
        
        unique_salesmen = [sm for sm in df_filtered['SalesMan_Clean'].unique() if sm != 'غير محدد']
        cols = st.columns(3)
        
        def draw_salesman_box(col, name, data, is_total=False):
            s_sales = data['Amount'].sum()
            s_profit = data['Profit'].sum()
            s_margin = (s_profit / s_sales * 100) if s_sales > 0 else 0
            s_ret_val = abs(data[data['Amount'] < 0]['Amount'].sum())
            s_gross = data[data['Amount'] > 0]['Amount'].sum()
            s_ret_rate = (s_ret_val / s_gross * 100) if s_gross > 0 else 0
            
            border_color = "#27ae60" if is_total else "#034275"
            name_color = "#333" if is_total else "#034275"
            
            with col:
                st.markdown(f"""
                <div class="salesman-box" style="border-right: 5px solid {border_color};">
                    <div class="s-header">
                        <div class="s-name" style="color: {name_color};">{name}</div>
                        {'<span style="font-size:12px; background:#eee; padding:2px 6px; border-radius:4px;">الإجمالي</span>' if is_total else ''}
                    </div>
                    <div class="s-row"><span style="color:#555;">💰 المبيعات:</span><span class="s-val">{s_sales:,.0f}</span></div>
                    <div class="s-row"><span style="color:#555;">📈 الربح:</span><span class="s-val" style="color:#27ae60">{s_profit:,.0f} ({s_margin:.1f}%)</span></div>
                    <div class="s-row" style="border-top:1px dashed #ddd; padding-top:5px; margin-top:5px;">
                        <span style="color:#c0392b">↩️ الإرجاع:</span>
                        <span class="s-val" style="color:#c0392b">{s_ret_val:,.0f} ({s_ret_rate:.1f}%)</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        curr_idx = 0
        for sm in unique_salesmen:
            if curr_idx < 2:
                draw_salesman_box(cols[curr_idx], sm, df_filtered[df_filtered['SalesMan_Clean'] == sm])
                curr_idx += 1
        draw_salesman_box(cols[2], "إجمالي الفريق", df_filtered, is_total=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- الصف 5: الرسوم (Lego Row 5) ---
        st.markdown('<div class="row-5">', unsafe_allow_html=True)
        st.markdown("---")
        tab1, tab2 = st.tabs(["التدفق الزمني", "توزيع الماركات"])
        with tab1:
            daily = df_filtered.groupby('Date')[['Amount', 'Profit']].sum().reset_index()
            fig = px.line(daily, x='Date', y=['Amount', 'Profit'], markers=True, color_discrete_map={'Amount': '#034275', 'Profit': '#27ae60'})
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            gp = df_filtered.groupby('stockgroup')[['Amount', 'Profit']].sum().reset_index().sort_values('Profit', ascending=False).head(10)
            fig_pie = px.pie(gp, values='Profit', names='stockgroup', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
            st.plotly_chart(fig_pie, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- الصف 6: الجداول (Lego Row 6) ---
        st.markdown('<div class="row-6">', unsafe_allow_html=True)
        st.markdown("---")
        c1, c2 = st.columns([3, 1])
        with c1: st.subheader("📦 تقرير المخزون الشامل")
        
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
            st.download_button("📥 تحميل التقرير (Excel)", data=csv, file_name="Shan_Report.csv", mime="text/csv")

        st.dataframe(items_sum, use_container_width=True, height=600)
        st.markdown('</div>', unsafe_allow_html=True)
