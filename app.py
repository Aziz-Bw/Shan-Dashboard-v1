import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET

# --- 1. إعدادات الصفحة والهوية ---
st.set_page_config(
    page_title="Shan Modern | شان الحديثة", 
    layout="wide", 
    page_icon="🏢"
)

# --- 🎨 تصميم الهوية البصرية (Shan Modern Identity) ---
st.markdown("""
<style>
    /* استيراد خطوط عربية جميلة */
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
    }

    /* الألوان الأساسية للهوية */
    :root {
        --brand-blue: #034275;
        --brand-grey: #3D3D3D;
        --card-bg: #FFFFFF;
    }

    /* تحسين العناوين الرئيسية */
    h1, h2, h3 {
        color: var(--brand-blue) !important;
    }

    /* تصميم البطاقات الذكية (Smart Cards)
       هذه البطاقات خلفيتها بيضاء دائماً لضمان قراءة النصوص
       سواء كان وضع الجهاز ليلي أو نهاري
    */
    .metric-card {
        background-color: var(--card-bg);
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 10px;
        border-top: 5px solid var(--brand-blue); /* لمسة الهوية */
    }
    
    .metric-card h4 {
        color: var(--brand-grey) !important;
        font-size: 16px;
        margin-bottom: 5px;
    }
    
    .metric-card h2 {
        color: var(--brand-blue) !important;
        font-size: 28px;
        font-weight: bold;
        margin: 0;
    }

    /* بطاقات البائعين */
    .salesman-card {
        background-color: var(--card-bg);
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        border-right: 5px solid var(--brand-blue); /* شريط جانبي أزرق */
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* إجبار النصوص داخل البطاقات تكون بألوان الهوية لتكون واضحة دائماً */
    .salesman-card h3 { color: var(--brand-blue) !important; margin-bottom: 10px; }
    .salesman-card span { color: var(--brand-grey) !important; font-weight: 500; }
    .salesman-card b { color: #000000 !important; }
    
    /* إخفاء القوائم الافتراضية المزعجة */
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

# --- 3. المعالجة والمنطق ---
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

# --- 4. الواجهة الرسمية ---
st.title("🏢 شركة شان الحديثة التجارية")
st.markdown("<h5 style='color: #3D3D3D;'>لوحة المعلومات المالية والفنية | Financial Dashboard</h5>", unsafe_allow_html=True)
st.markdown("---")

with st.sidebar:
    st.header("📂 مركز البيانات")
    f1 = st.file_uploader("1. ملف الفواتير (StockInvoiceDetails.xml)", type=['xml'])
    f2 = st.file_uploader("2. ملف الأصناف (StockInvoiceRowItems.xml)", type=['xml'])
    
    st.markdown("---")
    st.markdown("**Shan Modern Trading Co.**")
    st.caption("© 2026 Dashboard v2.0")

if f1 and f2:
    df = load_auto_data(f1, f2)
    
    if df is not None:
        # الفلاتر
        st.sidebar.markdown("### 🔍 أدوات التصفية")
        min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
        d_range = st.sidebar.date_input("📅 النطاق الزمني", [min_d, max_d])
        
        salesman_list = ['الكل'] + sorted(list(df['SalesMan_Clean'].astype(str).unique()))
        salesman_filter = st.sidebar.selectbox("👤 البائع", salesman_list)

        df_filtered = df.copy()
        if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
            df_filtered = df_filtered[(df_filtered['Date'].dt.date >= d_range[0]) & (df_filtered['Date'].dt.date <= d_range[1])]
        
        if salesman_filter != 'الكل':
            df_filtered = df_filtered[df_filtered['SalesMan_Clean'] == salesman_filter]

        # --- 1. البطاقات العائمة (KPIs) ---
        # نستخدم HTML مخصص بدلاً من st.metric لضمان الألوان
        total_sales = df_filtered['Amount'].sum()
        total_profit = df_filtered['Profit'].sum()
        total_cost = df_filtered['TotalCost'].sum()
        margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
        days_diff = (d_range[1] - d_range[0]).days if isinstance(d_range, (list, tuple)) and len(d_range) == 2 else 1
        months_diff = max(days_diff / 30, 1)

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        with kpi1:
            st.markdown(f"""<div class="metric-card"><h4>صافي المبيعات</h4><h2>{total_sales:,.0f}</h2></div>""", unsafe_allow_html=True)
        with kpi2:
            st.markdown(f"""<div class="metric-card"><h4>تكلفة البضاعة</h4><h2>{total_cost:,.0f}</h2></div>""", unsafe_allow_html=True)
        with kpi3:
            st.markdown(f"""<div class="metric-card"><h4>صافي الأرباح</h4><h2 style='color:#27ae60 !important;'>{total_profit:,.0f}</h2><span style='color:grey'>{margin:.1f}%</span></div>""", unsafe_allow_html=True)
        with kpi4:
            st.markdown(f"""<div class="metric-card"><h4>المتوسط الشهري</h4><h2>{total_sales/months_diff:,.0f}</h2></div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- 2. بطاقات الفريق ---
        st.subheader("👥 أداء الفريق")
        
        salesmen_stats = []
        for sm in df_filtered['SalesMan_Clean'].unique():
            if sm == 'غير محدد': continue
            sm_data = df_filtered[df_filtered['SalesMan_Clean'] == sm]
            net_sales = sm_data['Amount'].sum()
            net_profit = sm_data['Profit'].sum()
            sm_margin = (net_profit / net_sales * 100) if net_sales > 0 else 0
            
            returns_only = sm_data[sm_data['Amount'] < 0]
            return_val = abs(returns_only['Amount'].sum())
            return_count = returns_only['TransCode'].nunique()
            
            salesmen_stats.append({
                'البائع': sm, 'المبيعات': net_sales, 'الربح': net_profit, 'النسبة': sm_margin,
                'قيمة المرتجعات': return_val, 'عدد المرتجعات': return_count
            })
            
        cols = st.columns(len(salesmen_stats)) if len(salesmen_stats) > 0 else []
        for i, stat in enumerate(salesmen_stats):
            with cols[i]:
                st.markdown(f"""
                <div class="salesman-card">
                    <h3>{stat['البائع']}</h3>
                    <div style="display:flex; justify-content:space-between;"><span>💰 مبيعات:</span><b>{stat['المبيعات']:,.0f}</b></div>
                    <div style="display:flex; justify-content:space-between;"><span>📈 ربح:</span><b style="color:#27ae60 !important">{stat['الربح']:,.0f} ({stat['النسبة']:.0f}%)</b></div>
                    <hr style="margin:8px 0; border-color:#eee;">
                    <div style="display:flex; justify-content:space-between;"><span style="color:#c0392b !important">↩️ مرتجع:</span><b>{stat['قيمة المرتجعات']:,.0f}</b></div>
                </div>
                """, unsafe_allow_html=True)

        # --- 3. الرسوم البيانية ---
        st.markdown("---")
        tab1, tab2 = st.tabs(["التدفق الزمني", "توزيع الماركات"])
        with tab1:
            daily_data = df_filtered.groupby('Date')[['Amount', 'Profit']].sum().reset_index()
            # استخدام ألوان الهوية في الرسم البياني
            fig = px.line(daily_data, x='Date', y=['Amount', 'Profit'], markers=True, 
                          color_discrete_map={'Amount': '#034275', 'Profit': '#27ae60'})
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)") # خلفية شفافة
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            group_perf = df_filtered.groupby('stockgroup')[['Amount', 'Profit']].sum().reset_index().sort_values('Profit', ascending=False).head(10)
            fig_pie = px.pie(group_perf, values='Profit', names='stockgroup', hole=0.5, 
                             color_discrete_sequence=px.colors.sequential.Blues_r)
            st.plotly_chart(fig_pie, use_container_width=True)

        # --- 4. التقرير والتصدير ---
        st.markdown("---")
        c1, c2 = st.columns([3, 1])
        with c1: st.subheader("📦 تقرير المخزون الشامل")
        
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
            st.download_button("📥 تحميل التقرير (Excel)", data=csv, file_name="Shan_Full_Report.csv", mime="text/csv")

        st.dataframe(
            items_summary,
            column_config={
                "StockName": "اسم الصنف",
                "stockgroup": "المجموعة",
                "المبيعات": st.column_config.NumberColumn(format="%d"),
                "الربح": st.column_config.NumberColumn(format="%d"),
                "هامش_%": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
                "تصريف_شهري": st.column_config.NumberColumn(format="%.1f حبة"),
            },
            use_container_width=True,
            height=600
        )

else:
    # شاشة الترحيب
    st.info("👋 مرحباً بك في نظام شان الحديثة.. الرجاء رفع ملفات البيانات.")
