import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET

# --- 1. إعدادات الهوية والبناء ---
st.set_page_config(
    page_title="شان الحديثة | لوحة المعلومات", 
    layout="wide", 
    page_icon="🏢"
)

# --- 🎨 تصميم الهوية البصرية (Custom CSS) ---
st.markdown("""
<style>
    /* 1. خلفية التطبيق */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* 2. تحسين العناوين */
    h1, h2, h3 {
        color: #2c3e50; /* كحلي غامق */
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* 3. تصميم بطاقات البائعين */
    .salesman-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        border-left: 5px solid #2c3e50; /* حدود بلون الهوية */
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }
    .salesman-card:hover {
        transform: translateY(-5px);
    }
    
    /* 4. تصميم الأرقام الكبيرة (KPIs) */
    [data-testid="stMetricValue"] {
        font-size: 28px;
        color: #2980b9; /* أزرق مؤسسي */
        font-weight: bold;
    }
    
    /* 5. الشريط الجانبي */
    [data-testid="stSidebar"] {
        background-color: #f1f3f6;
        border-right: 1px solid #ddd;
    }
    
    /* 6. الجداول */
    .stDataFrame {
        border: 1px solid #ddd;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. الحماية ---
if "password" not in st.session_state: st.session_state["password"] = ""
if st.session_state["password"] != st.secrets["PASSWORD"]:
    st.title("🔒 بوابة شان الحديثة"); password = st.text_input("رمز الدخول المصرح به", type="password")
    if password == st.secrets["PASSWORD"]: st.session_state["password"] = password; st.rerun()
    else: st.stop()

# --- دالة توحيد الأسماء (نفس اللوجيك الناجح) ---
def normalize_salesman_name(name):
    if pd.isna(name) or name == 'nan' or name == 'غير محدد': return 'غير محدد'
    name = str(name).strip()
    if 'سعيد' in name: return 'سعيد'
    if 'عبد' in name and 'الله' in name: return 'عبد الله'
    return name

# --- 3. المعالجة الآلية ---
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
    except Exception as e: st.error(f"خطأ فني: {e}"); return None

# --- 4. الواجهة الرسمية ---
st.title("🏢 لوحة المعلومات المالية والفنية لشركة شان الحديثة")
st.markdown("---")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80) # أيقونة مؤقتة حتى نضع الشعار
    st.header("📂 مركز البيانات")
    f1 = st.file_uploader("1. ملف الفواتير (Invoice)", type=['xml'])
    f2 = st.file_uploader("2. ملف الأصناف (Items)", type=['xml'])
    
    st.markdown("---")
    st.caption("Shan Modern Trading Co. © 2026")

if f1 and f2:
    df = load_auto_data(f1, f2)
    
    if df is not None:
        # الفلاتر
        min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
        st.sidebar.markdown("### 🔍 تصفية العرض")
        d_range = st.sidebar.date_input("📅 النطاق الزمني", [min_d, max_d])
        
        salesman_list = ['الكل'] + sorted(list(df['SalesMan_Clean'].astype(str).unique()))
        salesman_filter = st.sidebar.selectbox("👤 الموظف المسؤول", salesman_list)

        df_filtered = df.copy()
        if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
            df_filtered = df_filtered[(df_filtered['Date'].dt.date >= d_range[0]) & (df_filtered['Date'].dt.date <= d_range[1])]
        
        if salesman_filter != 'الكل':
            df_filtered = df_filtered[df_filtered['SalesMan_Clean'] == salesman_filter]

        # 1. شريط الأرقام المؤسسية (KPIs)
        total_sales = df_filtered['Amount'].sum()
        total_profit = df_filtered['Profit'].sum()
        total_cost = df_filtered['TotalCost'].sum()
        margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
        
        days_diff = (d_range[1] - d_range[0]).days if isinstance(d_range, (list, tuple)) and len(d_range) == 2 else 1
        months_diff = max(days_diff / 30, 1)

        # تصميم كلاسيكي للأرقام
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("صافي الإيرادات", f"{total_sales:,.0f} ر.س", "المبيعات المحققة")
        col2.metric("تكلفة البضاعة", f"{total_cost:,.0f} ر.س", "Cost of Goods")
        col3.metric("صافي الأرباح", f"{total_profit:,.0f} ر.س", f"{margin:.1f}% هامش فعلي")
        col4.metric("المتوسط الشهري", f"{total_sales/months_diff:,.0f} ر.س", "أداء المبيعات")

        st.markdown("---")

        # 2. بطاقات الفريق (التصميم الجديد)
        st.subheader("👥 أداء فريق المبيعات")
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
                'البائع': sm,
                'المبيعات': net_sales,
                'الربح': net_profit,
                'النسبة': sm_margin,
                'قيمة المرتجعات': return_val,
                'عدد المرتجعات': return_count
            })
            
        cols = st.columns(len(salesmen_stats)) if len(salesmen_stats) > 0 else []
        for i, stat in enumerate(salesmen_stats):
            with cols[i]:
                # HTML Card Design
                st.markdown(f"""
                <div class="salesman-card">
                    <h4 style="margin:0; color:#2c3e50;">👤 {stat['البائع']}</h4>
                    <div style="height: 2px; background-color: #eee; margin: 10px 0;"></div>
                    <div style="display:flex; justify-content:space-between; font-size:14px;">
                        <span style="color:#7f8c8d;">المبيعات:</span>
                        <span style="font-weight:bold; color:#2c3e50;">{stat['المبيعات']:,.0f}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:14px; margin-top:5px;">
                        <span style="color:#7f8c8d;">الربح:</span>
                        <span style="font-weight:bold; color:#27ae60;">{stat['الربح']:,.0f} ({stat['النسبة']:.0f}%)</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:12px; margin-top:8px; color:#c0392b;">
                        <span>↩️ مرتجع:</span>
                        <span>{stat['قيمة المرتجعات']:,.0f}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # 3. الرسوم البيانية (Charts)
        st.markdown("### 📊 المؤشرات البيانية")
        tab1, tab2 = st.tabs(["التدفق اليومي", "توزيع الماركات"])
        with tab1:
            daily_data = df_filtered.groupby('Date')[['Amount', 'Profit']].sum().reset_index()
            # تعديل ألوان الرسم لتناسب الهوية
            fig = px.line(daily_data, x='Date', y=['Amount', 'Profit'], markers=True, 
                          color_discrete_map={'Amount': '#2980b9', 'Profit': '#27ae60'})
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            group_perf = df_filtered.groupby('stockgroup')[['Amount', 'Profit']].sum().reset_index().sort_values('Profit', ascending=False).head(10)
            fig_pie = px.pie(group_perf, values='Profit', names='stockgroup', hole=0.5, color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_pie, use_container_width=True)

        # 4. التقرير التفصيلي (Table)
        st.markdown("---")
        c1, c2 = st.columns([3, 1])
        with c1: st.subheader("📦 تقرير المخزون: التحليل المالي والفني للأصناف")
        
        # التجميع النهائي
        items_summary = df_filtered.groupby(['StockName', 'StockCode', 'stockgroup']).agg(
            الكمية=('Qty', 'sum'),
            المبيعات=('Amount', 'sum'),
            الربح=('Profit', 'sum'),
            عدد_مرات_البيع=('TransCode', 'nunique')
        ).reset_index()
        
        items_summary['هامش_%'] = (items_summary['الربح'] / items_summary['المبيعات'] * 100).fillna(0)
        items_summary['تصريف_شهري'] = items_summary['الكمية'] / months_diff
        items_summary['ربح_شهري'] = items_summary['الربح'] / months_diff
        items_summary = items_summary.sort_values('الربح', ascending=False)
        
        # زر التصدير
        with c2:
            csv = items_summary.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 تصدير التقرير (Excel)", data=csv, file_name="Shan_Report.csv", mime="text/csv")

        # الجدول
        st.dataframe(
            items_summary,
            column_config={
                "StockName": "اسم الصنف",
                "stockgroup": "المجموعة",
                "StockCode": "رقم القطعة",
                "المبيعات": st.column_config.NumberColumn(format="%d"),
                "الربح": st.column_config.NumberColumn(format="%d"),
                "هامش_%": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
                "تصريف_شهري": st.column_config.NumberColumn(format="%.1f حبة"),
            },
            use_container_width=True,
            height=600
        )

else:
    st.info("👋 مرحباً بك في نظام شان الحديثة.. الرجاء رفع ملفات البيانات لبدء الجلسة.")
