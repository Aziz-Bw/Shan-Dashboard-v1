import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="Shan Modern | شان الحديثة", 
    layout="wide", 
    page_icon="🏢"
)

# --- 🎨 تصميم الهوية وتصحيح التنسيق (CSS) ---
st.markdown("""
<style>
    /* استيراد خط تجوال العربي */
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
    }

    :root {
        --brand-blue: #034275;
        --brand-grey: #3D3D3D;
        --card-bg: #FFFFFF;
        --text-dark: #333333;
    }

    /* تحسين العناوين */
    h1, h2, h3 { color: var(--brand-blue) !important; }

    /* --- 1. تصميم بطاقات المؤشرات (الصف العلوي) --- */
    .metric-card {
        background-color: var(--card-bg);
        border-radius: 12px;
        padding: 20px 10px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        border-top: 6px solid var(--brand-blue);
        min-height: 160px; /* توحيد الارتفاع إجبارياً */
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        margin-bottom: 10px;
    }
    
    .metric-card h4 {
        color: var(--brand-grey) !important;
        font-size: 16px;
        margin: 0 0 10px 0;
        font-weight: 500;
    }
    
    .metric-card .value {
        color: var(--brand-blue);
        font-size: 26px;
        font-weight: 800;
        margin: 0;
    }
    
    .metric-card .sub-value {
        font-size: 14px;
        margin-top: 5px;
        font-weight: bold;
    }

    /* --- 2. تصميم بطاقات البائعين (RTL Fix) --- */
    .salesman-card {
        background-color: var(--card-bg);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        border-right: 6px solid var(--brand-blue);
        min-height: 220px; /* توحيد الارتفاع */
        direction: rtl; /* إجبار الاتجاه من اليمين لليسار */
    }

    .salesman-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
        border-bottom: 2px solid #f0f0f0;
        padding-bottom: 10px;
    }

    .salesman-name {
        color: var(--brand-blue);
        font-size: 20px;
        font-weight: 800;
        margin: 0;
    }

    /* تنسيق الصفوف داخل البطاقة */
    .stat-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        direction: rtl; /* تأكيد الاتجاه */
    }

    .stat-label {
        color: #666;
        font-size: 14px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .stat-value {
        color: var(--text-dark);
        font-size: 16px;
        font-weight: 700;
        font-family: 'Tajawal', sans-serif; /* لضمان شكل الأرقام */
    }

    /* إخفاء عناصر ستريم لت النمطية */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
</style>
""", unsafe_allow_html=True)

# --- 2. الحماية ---
if "password" not in st.session_state: st.session_state["password"] = ""
if st.session_state["password"] != st.secrets["PASSWORD"]:
    st.title("🔒 بوابة شان الحديثة"); password = st.text_input("رمز الدخول", type="password")
    if password == st.secrets["PASSWORD"]: st.session_state["password"] = password; st.rerun()
    else: st.stop()

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

# --- 4. الواجهة ---
st.title("🏢 شركة شان الحديثة التجارية")
st.markdown("<h5 style='color: #3D3D3D;'>لوحة المعلومات المالية والفنية | Financial Dashboard</h5>", unsafe_allow_html=True)
st.markdown("---")

with st.sidebar:
    st.header("📂 البيانات")
    f1 = st.file_uploader("1. ملف الفواتير (StockInvoiceDetails.xml)", type=['xml'])
    f2 = st.file_uploader("2. ملف الأصناف (StockInvoiceRowItems.xml)", type=['xml'])
    st.markdown("---")
    st.caption("Shan Modern Trading © 2026")

if f1 and f2:
    df = load_auto_data(f1, f2)
    
    if df is not None:
        min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
        st.sidebar.markdown("### 🔍 الفلاتر")
        d_range = st.sidebar.date_input("📅 الفترة", [min_d, max_d])
        salesman_list = ['الكل'] + sorted(list(df['SalesMan_Clean'].astype(str).unique()))
        salesman_filter = st.sidebar.selectbox("👤 البائع", salesman_list)

        df_filtered = df.copy()
        if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
            df_filtered = df_filtered[(df_filtered['Date'].dt.date >= d_range[0]) & (df_filtered['Date'].dt.date <= d_range[1])]
        
        if salesman_filter != 'الكل':
            df_filtered = df_filtered[df_filtered['SalesMan_Clean'] == salesman_filter]

        # --- الحسابات الرئيسية ---
        # 1. المبيعات (الموجبة فقط قبل الخصم للإجمالي) لفهم حجم العمل
        gross_sales = df_filtered[df_filtered['Amount'] > 0]['Amount'].sum()
        
        # 2. المرتجعات (السالبة نقلبها موجب للعرض)
        returns_val = abs(df_filtered[df_filtered['Amount'] < 0]['Amount'].sum())
        
        # 3. الصافي
        net_sales = df_filtered['Amount'].sum() # (المبيعات - المرتجعات)
        
        total_profit = df_filtered['Profit'].sum()
        total_cost = df_filtered['TotalCost'].sum()
        margin = (total_profit / net_sales * 100) if net_sales > 0 else 0
        
        days_diff = (d_range[1] - d_range[0]).days if isinstance(d_range, (list, tuple)) and len(d_range) == 2 else 1
        months_diff = max(days_diff / 30, 1)

        # --- 1. الصف الأول: 5 بطاقات متساوية ---
        k1, k2, k3, k4, k5 = st.columns(5)
        
        with k1:
            st.markdown(f"""
            <div class="metric-card">
                <h4>صافي المبيعات</h4>
                <div class="value">{net_sales:,.0f}</div>
                <div class="sub-value" style="color:grey">الإيراد الفعلي</div>
            </div>""", unsafe_allow_html=True)
            
        with k2:
            st.markdown(f"""
            <div class="metric-card">
                <h4>تكلفة البضاعة</h4>
                <div class="value">{total_cost:,.0f}</div>
                <div class="sub-value" style="color:grey">Cost</div>
            </div>""", unsafe_allow_html=True)
            
        with k3: # كرت الإرجاعات الجديد
            st.markdown(f"""
            <div class="metric-card">
                <h4>إجمالي الإرجاعات</h4>
                <div class="value" style="color:#c0392b !important;">{returns_val:,.0f}</div>
                <div class="sub-value" style="color:#c0392b">مخصومة من المبيعات</div>
            </div>""", unsafe_allow_html=True)
            
        with k4:
            st.markdown(f"""
            <div class="metric-card">
                <h4>صافي الأرباح</h4>
                <div class="value" style="color:#27ae60 !important;">{total_profit:,.0f}</div>
                <div class="sub-value" style="color:#27ae60">{margin:.1f}% هامش</div>
            </div>""", unsafe_allow_html=True)
            
        with k5:
            st.markdown(f"""
            <div class="metric-card">
                <h4>المتوسط الشهري</h4>
                <div class="value">{net_sales/months_diff:,.0f}</div>
                <div class="sub-value" style="color:grey">معدل الأداء</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- 2. بطاقات الفريق (3 أعمدة متناسقة) ---
        st.subheader("👥 أداء الفريق")
        
        # نجهز قائمة البائعين + الإجمالي
        unique_salesmen = [sm for sm in df_filtered['SalesMan_Clean'].unique() if sm != 'غير محدد']
        
        # إنشاء الأعمدة (عبدالله، سعيد، الإجمالي)
        # نستخدم columns(3) ليكون العرض موحداً
        cols = st.columns(3)
        
        # دالة مساعدة لرسم البطاقة
        def draw_salesman_card(col, name, data_df, is_total=False):
            # الحسابات
            s_sales = data_df['Amount'].sum()
            s_profit = data_df['Profit'].sum()
            s_margin = (s_profit / s_sales * 100) if s_sales > 0 else 0
            
            # الإرجاع
            s_returns_val = abs(data_df[data_df['Amount'] < 0]['Amount'].sum())
            # نسبة الإرجاع من إجمالي ما تم بيعه (Gross Sales)
            s_gross = data_df[data_df['Amount'] > 0]['Amount'].sum()
            s_return_rate = (s_returns_val / s_gross * 100) if s_gross > 0 else 0
            
            # لون الاسم
            name_color = "#034275" if not is_total else "#2c3e50"; 
            bg_style = "border-right: 6px solid #27ae60;" if is_total else "" # تمييز كرت الإجمالي بالأخضر
            
            with col:
                st.markdown(f"""
                <div class="salesman-card" style="{bg_style}">
                    <div class="salesman-header">
                        <div class="salesman-name" style="color:{name_color}">{name}</div>
                        {'<div style="font-size:12px; background:#eee; padding:2px 8px; border-radius:10px;">الإجمالي</div>' if is_total else ''}
                    </div>
                    
                    <div class="stat-row">
                        <div class="stat-label">💰 المبيعات (الصافي)</div>
                        <div class="stat-value">{s_sales:,.0f}</div>
                    </div>
                    
                    <div class="stat-row">
                        <div class="stat-label">📈 صافي الربح</div>
                        <div class="stat-value" style="color:#27ae60">{s_profit:,.0f} ({s_margin:.1f}%)</div>
                    </div>
                    
                    <div class="stat-row">
                        <div class="stat-label">↩️ قيمة الإرجاع</div>
                        <div class="stat-value" style="color:#c0392b">{s_returns_val:,.0f}</div>
                    </div>
                    
                    <div class="stat-row" style="border-top: 1px dashed #ddd; padding-top:8px;">
                        <div class="stat-label">⚠️ نسبة الإرجاع</div>
                        <div class="stat-value" style="color:#c0392b">{s_return_rate:.1f}%</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # رسم كروت البائعين (سعيد وعبدالله)
        current_col_idx = 0
        for sm in unique_salesmen:
            if current_col_idx < 2: # أول عمودين للبائعين
                sm_data = df_filtered[df_filtered['SalesMan_Clean'] == sm]
                draw_salesman_card(cols[current_col_idx], sm, sm_data)
                current_col_idx += 1
        
        # رسم كرت الإجمالي في العمود الثالث
        draw_salesman_card(cols[2], "إجمالي الفريق", df_filtered, is_total=True)

        # --- 3. الرسوم البيانية ---
        st.markdown("---")
        tab1, tab2 = st.tabs(["التدفق الزمني", "توزيع الماركات"])
        with tab1:
            daily_data = df_filtered.groupby('Date')[['Amount', 'Profit']].sum().reset_index()
            fig = px.line(daily_data, x='Date', y=['Amount', 'Profit'], markers=True, 
                          color_discrete_map={'Amount': '#034275', 'Profit': '#27ae60'})
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            group_perf = df_filtered.groupby('stockgroup')[['Amount', 'Profit']].sum().reset_index().sort_values('Profit', ascending=False).head(10)
            fig_pie = px.pie(group_perf, values='Profit', names='stockgroup', hole=0.5, 
                             color_discrete_sequence=px.colors.sequential.Blues_r)
            st.plotly_chart(fig_pie, use_container_width=True)

        # --- 4. الجدول ---
        st.markdown("---")
        c1, c2 = st.columns([3, 1])
        with c1: st.subheader("📦 تقرير الأصناف")
        
        items_summary = df_filtered.groupby(['StockName', 'StockCode', 'stockgroup']).agg(
            الكمية=('Qty', 'sum'),
            المبيعات=('Amount', 'sum'),
            الربح=('Profit', 'sum'),
            عدد_مرات_البيع=('TransCode', 'nunique')
        ).reset_index()
        
        items_summary['هامش_%'] = (items_summary['الربح'] / items_summary['المبيعات'] * 100).fillna(0)
        items_summary['تصريف_شهري'] = items_summary['الكمية'] / months_diff
        items_summary = items_summary.sort_values('الربح', ascending=False)
        
        with c2:
            csv = items_summary.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 تصدير (Excel)", data=csv, file_name="Shan_Report.csv", mime="text/csv")

        st.dataframe(items_summary, use_container_width=True, height=600)

else:
    st.info("👋 مرحباً.. الرجاء رفع الملفات.")
