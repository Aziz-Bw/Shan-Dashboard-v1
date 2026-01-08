import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET

# --- 1. إعدادات الصفحة (التصميم الافتراضي النظيف) ---
st.set_page_config(
    page_title="مدير شان الحديثة",
    layout="wide",
    page_icon="🏢",
    initial_sidebar_state="expanded"
)

# --- CSS بسيط فقط لضبط الاتجاه (RTL) والخط ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        direction: rtl;
    }
    /* تعديل بسيط لعنوان القوائم ليكون يمين */
    .stSelectbox label, .stTextInput label, .stDateInput label {
        text-align: right;
    }
    /* إخفاء القوائم غير المهمة */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 2. إدارة الحالة ---
if 'uploaded_files' not in st.session_state: st.session_state['uploaded_files'] = None
if 'ledger_file' not in st.session_state: st.session_state['ledger_file'] = None

# --- 3. دوال المعالجة ---
def normalize_name(name):
    if pd.isna(name): return "غير محدد"
    return str(name).strip()

@st.cache_data(ttl=3600)
def load_sales_data(file_header, file_items):
    try:
        file_header.seek(0); file_items.seek(0)
        tree_h = ET.parse(file_header); df_header = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_h.getroot()])
        tree_i = ET.parse(file_items); df_items = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_i.getroot()])
        
        if 'IsDelete' in df_header.columns: df_header = df_header[~df_header['IsDelete'].isin(['True', 'true', '1'])]

        df_header['Date'] = pd.to_datetime(pd.to_numeric(df_header['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
        if 'SalesPerson' in df_header.columns: df_header['Header_SalesMan'] = df_header['SalesPerson'].fillna('عام')
        else: df_header['Header_SalesMan'] = 'عام'

        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        if 'TaxbleAmount' in df_items.columns: df_items['Amount'] = pd.to_numeric(df_items['TaxbleAmount'], errors='coerce').fillna(0)
        else: df_items['Amount'] = pd.to_numeric(df_items['netStockAmount'], errors='coerce').fillna(0) / 1.15

        cost_col = 'PresetRate' if 'PresetRate' in df_items.columns else 'PresetRate2'
        df_items['CostUnit'] = pd.to_numeric(df_items.get(cost_col, 0), errors='coerce').fillna(0)
        df_items['TotalCost'] = df_items['CostUnit'] * df_items['Qty']
        
        full_data = pd.merge(df_items, df_header[['TransCode', 'Date', 'InvoiceNo', 'Header_SalesMan', 'VoucherName']], on='TransCode', how='inner')
        full_data['SalesMan'] = full_data['Header_SalesMan'].apply(normalize_name)
        
        mask_return = full_data['VoucherName'].str.contains('Return|مرتجع', case=False, na=False)
        full_data.loc[mask_return, 'Amount'] *= -1
        full_data.loc[mask_return, 'TotalCost'] *= -1
        full_data['Profit'] = full_data['Amount'] - full_data['TotalCost']
        
        if 'stockgroup' not in full_data.columns: full_data['stockgroup'] = 'عام'
        return full_data
    except Exception as e: return None

@st.cache_data(ttl=3600)
def load_ledger_data(file_ledger):
    try:
        file_ledger.seek(0)
        tree = ET.parse(file_ledger)
        df = pd.DataFrame([{child.tag: child.text for child in row} for row in tree.getroot()])
        
        # تحويل الأرقام
        df['Dr'] = pd.to_numeric(df['Dr'], errors='coerce').fillna(0)
        df['Cr'] = pd.to_numeric(df['Cr'], errors='coerce').fillna(0)
        return df
    except: return None

# --- 4. القائمة الجانبية ---
with st.sidebar:
    st.header("لوحة التحكم")
    page = st.radio("تنقل بين الأقسام:", ["💰 المبيعات", "💸 التحصيل والديون"])
    
    st.markdown("---")
    if page == "💰 المبيعات":
        st.info("ارفع ملفات المبيعات")
        f1 = st.file_uploader("StockInvoiceDetails.xml", type=['xml'], key="f1")
        f2 = st.file_uploader("StockInvoiceRowItems.xml", type=['xml'], key="f2")
        if f1 and f2: st.session_state['uploaded_files'] = (f1, f2)
    else:
        st.info("ارفع ملف التحصيل")
        f3 = st.file_uploader("LedgerBook.xml", type=['xml'], key="f3")
        if f3: st.session_state['ledger_file'] = f3

# ========================================================
# الصفحة 1: المبيعات (التصميم الأصلي النظيف)
# ========================================================
if page == "💰 المبيعات":
    st.title("💰 المبيعات والأداء المالي")
    
    if st.session_state['uploaded_files']:
        f1, f2 = st.session_state['uploaded_files']
        df = load_sales_data(f1, f2)
        
        if df is not None:
            # الفلاتر
            c1, c2 = st.columns(2)
            with c1:
                min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
                d_range = st.date_input("الفترة الزمنية", [min_d, max_d])
            with c2:
                sellers = ['الكل'] + sorted(list(df['SalesMan'].unique()))
                sel_filter = st.selectbox("الموظف", sellers)
            
            # تطبيق الفلاتر
            df_sub = df.copy()
            if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
                df_sub = df_sub[(df_sub['Date'].dt.date >= d_range[0]) & (df_sub['Date'].dt.date <= d_range[1])]
            if sel_filter != 'الكل':
                df_sub = df_sub[df_sub['SalesMan'] == sel_filter]
                
            st.markdown("---")
            
            # المؤشرات (Metrics) - التصميم الافتراضي الجميل
            # نحسب القيم
            sales = df_sub['Amount'].sum()
            profit = df_sub['Profit'].sum()
            cost = df_sub['TotalCost'].sum()
            margin = (profit / sales * 100) if sales > 0 else 0
            
            ret_val = abs(df_sub[df_sub['Amount']<0]['Amount'].sum())
            ret_count = df_sub[df_sub['Amount']<0]['TransCode'].nunique()
            inv_count = df_sub[df_sub['Amount']>0]['TransCode'].nunique()
            
            # الصف الأول
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("صافي المبيعات", f"{sales:,.0f} ر.س")
            m2.metric("صافي الربح", f"{profit:,.0f} ر.س", f"{margin:.1f}%")
            m3.metric("تكلفة البضاعة", f"{cost:,.0f} ر.س")
            m4.metric("قيمة المرتجعات", f"{ret_val:,.0f} ر.س", f"عدد: {ret_count}")
            
            st.markdown("---")
            
            # الرسوم البيانية
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("تحليل البائعين")
                # تجميع حسب البائع
                s_perf = df_sub.groupby('SalesMan')[['Amount', 'Profit']].sum().reset_index()
                fig = px.bar(s_perf, x='SalesMan', y=['Amount', 'Profit'], barmode='group', title="المبيعات والربح لكل بائع")
                st.plotly_chart(fig, use_container_width=True)
                
            with g2:
                st.subheader("الأكثر مبيعاً")
                # تجميع حسب الصنف
                top_items = df_sub.groupby('StockName')['Qty'].sum().reset_index().sort_values('Qty', ascending=False).head(10)
                st.dataframe(top_items, use_container_width=True, hide_index=True)

    else:
        st.warning("الرجاء رفع ملفات المبيعات من القائمة الجانبية.")

# ========================================================
# الصفحة 2: التحصيل والديون (المنطق الذكي الجديد)
# ========================================================
elif page == "💸 التحصيل والديون":
    st.title("💸 مراقبة الديون والعملاء")
    
    if st.session_state['ledger_file']:
        df_ledger = load_ledger_data(st.session_state['ledger_file'])
        
        if df_ledger is not None:
            # --- الخوارزمية الذكية لكشف العملاء ---
            # 1. البحث عن الحسابات التي تعاملت في "ايرادات المبيعات"
            # نبحث عن كلمة "مبيعات" في عمود AcLedger (كما اكتشفت أنت)
            
            target_keyword = "مبيعات" # كلمة مفتاحية
            
            if 'AcLedger' in df_ledger.columns:
                # نحدد من هم العملاء؟ هم الذين ظهر اسمهم في عمليات المبيعات
                sales_transactions = df_ledger[df_ledger['AcLedger'].astype(str).str.contains(target_keyword, na=False)]
                valid_customers_list = sales_transactions['LedgerName'].unique()
                
                if len(valid_customers_list) > 0:
                    st.success(f"✅ تم التعرف على {len(valid_customers_list)} عميل من خلال سجلات المبيعات.")
                    
                    # 2. تصفية الجدول الكامل لهؤلاء العملاء فقط
                    # (عشان نحسب رصيدهم الكامل بما فيه السندات والمدفوعات اللي ممكن تكون تحت مسميات أخرى)
                    customers_full_data = df_ledger[df_ledger['LedgerName'].isin(valid_customers_list)]
                    
                    # 3. التجميع والحساب
                    cust_summary = customers_full_data.groupby('LedgerName').agg(
                        Total_Debit=('Dr', 'sum'),
                        Total_Credit=('Cr', 'sum')
                    ).reset_index()
                    
                    cust_summary['Balance'] = cust_summary['Total_Debit'] - cust_summary['Total_Credit']
                    
                    # تصفية الديون (أكبر من 10 ريال)
                    debtors = cust_summary[cust_summary['Balance'] > 10].sort_values('Balance', ascending=False)
                    
                    # --- عرض النتائج ---
                    total_debt = debtors['Balance'].sum()
                    count_debtors = len(debtors)
                    
                    k1, k2 = st.columns(2)
                    k1.metric("إجمالي الديون (في السوق)", f"{total_debt:,.0f} ر.س")
                    k2.metric("عدد العملاء المدينين", f"{count_debtors} عميل")
                    
                    st.markdown("### 📊 تفاصيل الديون")
                    
                    # رسم بياني لأعلى 15 عميل
                    top_15 = debtors.head(15)
                    fig = px.bar(top_15, x='LedgerName', y='Balance', text_auto='.2s', title="أعلى 15 مديونية")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # الجدول التفصيلي
                    st.dataframe(
                        debtors,
                        column_config={
                            "LedgerName": "اسم العميل",
                            "Total_Debit": st.column_config.NumberColumn("المسحوبات", format="%d"),
                            "Total_Credit": st.column_config.NumberColumn("المدفوعات", format="%d"),
                            "Balance": st.column_config.NumberColumn("الرصيد المتبقي (دين)", format="%d"),
                        },
                        use_container_width=True,
                        height=600
                    )
                    
                else:
                    st.warning("لم يتم العثور على عمليات تحتوي كلمة 'مبيعات' في عمود AcLedger.")
            else:
                st.error("لم يتم العثور على عمود AcLedger في الملف.")
    else:
        st.warning("الرجاء رفع ملف LedgerBook.xml من القائمة الجانبية.")
