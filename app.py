import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import xml.etree.ElementTree as ET

# --- 1. إعداد الصفحة والتصميم ---
st.set_page_config(page_title="مدير قطع الغيار الذكي", layout="wide", page_icon="⚙️")

# تصميم CSS لتحسين مظهر الأرقام
st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #0068c9;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. نظام الحماية ---
if "password" not in st.session_state:
    st.session_state["password"] = ""

if st.session_state["password"] != st.secrets["PASSWORD"]:
    st.title("🔒 تسجيل الدخول")
    password = st.text_input("أدخل كلمة المرور للمتابعة", type="password")
    if password == st.secrets["PASSWORD"]:
        st.session_state["password"] = password
        st.rerun()
    else:
        st.stop()

# --- 3. دالة المعالجة الذكية ---
@st.cache_data(ttl=3600)
def load_data(file_header, file_items):
    try:
        # قراءة ملف الفواتير
        tree_h = ET.parse(file_header)
        df_header = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_h.getroot()])
        
        # قراءة ملف الأصناف
        tree_i = ET.parse(file_items)
        df_items = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_i.getroot()])
        
        # --- تنظيف البيانات ---
        
        # 1. إصلاح التاريخ (الحل السحري باستخدام TransDateValue)
        # الرقم 45538 هو نظام إكسل، يبدأ العد من 30-12-1899
        df_header['Date'] = pd.to_datetime(
            pd.to_numeric(df_header['TransDateValue'], errors='coerce'), 
            unit='D', 
            origin='1899-12-30'
        )
        
        # تنظيف الأرقام
        df_header['GrandTotal'] = pd.to_numeric(df_header['InvoiceTotal'], errors='coerce').fillna(0)
        df_header['TaxTotal'] = pd.to_numeric(df_header['taxtotal'], errors='coerce').fillna(0)
        
        # 2. تنظيف الأصناف
        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        df_items['Amount'] = pd.to_numeric(df_items['netStockAmount'], errors='coerce').fillna(0)
        df_items['Cost'] = pd.to_numeric(df_items['CostFactor'], errors='coerce').fillna(0)
        
        # حساب الربح
        df_items['Profit'] = df_items['Amount'] - (df_items['Cost'] * df_items['Qty'])

        # 3. الدمج
        full_data = pd.merge(
            df_items, 
            df_header[['TransCode', 'Date', 'LedgerName', 'InvoiceNo', 'SalesMan']], 
            on='TransCode', 
            how='inner' # نستخدم inner لنضمن أن كل صنف له فاتورة وتاريخ
        )
        
        # حذف أي صفوف ليس لها تاريخ صحيح
        full_data = full_data.dropna(subset=['Date'])
        
        return full_data
        
    except Exception as e:
        st.error(f"حدث خطأ في معالجة الملفات: {e}")
        return None

# --- 4. الواجهة الرئيسية ---
st.title("📊 لوحة القيادة: تحليل نشاط قطع الغيار")
st.markdown("---")

with st.sidebar:
    st.header("📂 مركز البيانات")
    uploaded_header = st.file_uploader("1. ملف الفواتير (StockInvoiceDetails)", type=['xml'])
    uploaded_items = st.file_uploader("2. ملف الأصناف (StockInvoiceRowItems)", type=['xml'])
    
    st.markdown("---")
    st.write("©️ 2026 - الإصدار الخاص")

if uploaded_header and uploaded_items:
    
    df_merged = load_data(uploaded_header, uploaded_items)
    
    if df_merged is not None and not df_merged.empty:
        
        # --- الفلاتر ---
        col_fil1, col_fil2, col_fil3 = st.columns(3)
        with col_fil1:
            # التأكد من وجود تواريخ صالحة قبل إنشاء الفلتر
            min_date = df_merged['Date'].min().date()
            max_date = df_merged['Date'].max().date()
            date_range = st.date_input("الفترة الزمنية", [min_date, max_date])
        
        with col_fil2:
            salesmen = ['الكل'] + list(df_merged['SalesMan'].unique())
            selected_salesman = st.selectbox("اختر البائع", salesmen)
            
        with col_fil3:
            groups = ['الكل'] + list(df_merged['stockgroup'].unique())
            selected_group = st.selectbox("مجموعة الأصناف", groups)

        # تطبيق الفلاتر
        filtered_df = df_merged.copy()
        
        # فلتر التاريخ (حماية من الأخطاء)
        if isinstance(date_range, tuple) and len(date_range) == 2:
             filtered_df = filtered_df[
                (filtered_df['Date'].dt.date >= date_range[0]) & 
                (filtered_df['Date'].dt.date <= date_range[1])
            ]
        elif isinstance(date_range, list) and len(date_range) == 2: # أحياناً يرجع قائمة
             filtered_df = filtered_df[
                (filtered_df['Date'].dt.date >= date_range[0]) & 
                (filtered_df['Date'].dt.date <= date_range[1])
            ]
        
        if selected_salesman != 'الكل':
            filtered_df = filtered_df[filtered_df['SalesMan'] == selected_salesman]
            
        if selected_group != 'الكل':
            filtered_df = filtered_df[filtered_df['stockgroup'] == selected_group]

        # --- مؤشرات الأداء ---
        st.markdown("### 📌 نظرة عامة مالية")
        
        total_sales = filtered_df['Amount'].sum()
        total_profit = filtered_df['Profit'].sum()
        total_cost = (filtered_df['Cost'] * filtered_df['Qty']).sum()
        profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
        total_inv_count = filtered_df['TransCode'].nunique()

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("إجمالي المبيعات", f"{total_sales:,.0f} ر.س", delta="الإيرادات")
        kpi2.metric("إجمالي الربح التقديري", f"{total_profit:,.0f} ر.س", delta=f"{profit_margin:.1f}% هامش ربح")
        kpi3.metric("قيمة التكلفة", f"{total_cost:,.0f} ر.س", delta="تكلفة البضاعة", delta_color="inverse")
        kpi4.metric("عدد الفواتير", f"{total_inv_count}", delta="حركة")

        st.markdown("---")

        # --- الرسوم البيانية ---
        chart_row1_1, chart_row1_2 = st.columns(2)
        
        with chart_row1_1:
            st.subheader("📈 نمو المبيعات (يومياً)")
            sales_trend = filtered_df.groupby('Date')['Amount'].sum().reset_index()
            fig_trend = px.line(sales_trend, x='Date', y='Amount', markers=True)
            st.plotly_chart(fig_trend, use_container_width=True)
            
        with chart_row1_2:
            st.subheader("📦 أفضل المجموعات مبيعاً")
            group_sales = filtered_df.groupby('stockgroup')['Amount'].sum().reset_index().sort_values('Amount', ascending=False).head(7)
            fig_pie = px.pie(group_sales, values='Amount', names='stockgroup', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        chart_row2_1, chart_row2_2 = st.columns(2)
        
        with chart_row2_1:
            st.subheader("🏆 أداء البائعين")
            salesman_perf = filtered_df.groupby('SalesMan')['Amount'].sum().reset_index().sort_values('Amount', ascending=False)
            fig_bar = px.bar(salesman_perf, x='SalesMan', y='Amount', text_auto='.2s', color='Amount')
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with chart_row2_2:
            st.subheader("👥 كبار العملاء")
            top_customers = filtered_df.groupby('LedgerName')['Amount'].sum().reset_index().sort_values('Amount', ascending=False).head(10)
            fig_cust = px.bar(top_customers, y='LedgerName', x='Amount', orientation='h', text_auto='.2s')
            fig_cust.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_cust, use_container_width=True)

        # --- الجداول ---
        st.markdown("---")
        col_tbl1, col_tbl2 = st.columns(2)
        
        with col_tbl1:
            st.subheader("📦 الأصناف الأكثر مبيعاً")
            top_items = filtered_df.groupby(['StockName', 'stockgroup'])[['Qty', 'Amount']].sum().reset_index().sort_values('Qty', ascending=False).head(10)
            st.dataframe(top_items, use_container_width=True)
            
        with col_tbl2:
            st.subheader("⚠️ أصناف منخفضة الربحية")
            low_margin = filtered_df.groupby('StockName')[['Amount', 'Profit']].sum().reset_index()
            low_margin = low_margin[low_margin['Profit'] <= 0].sort_values('Profit')
            if not low_margin.empty:
                st.dataframe(low_margin.head(10), use_container_width=True)
            else:
                st.success("ممتاز! لا توجد أصناف خاسرة.")

    elif df_merged is not None:
        st.warning("⚠️ الملفات سليمة ولكن لم نجد بيانات تواريخ صالحة. تأكد أن الملفات تحتوي على بيانات.")

else:
    st.info("👈 ابدأ برفع ملفات الفواتير والأصناف.")
