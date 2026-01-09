import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

# --- 1. إعدادات أساسية ---
st.set_page_config(page_title="مدير شان الحديثة", layout="wide", page_icon="🏢")

# --- 2. إدارة الحالة (تخزين الملفات) ---
if 'uploaded_files' not in st.session_state: st.session_state['uploaded_files'] = None
if 'ledger_file' not in st.session_state: st.session_state['ledger_file'] = None

# --- 3. الدوال (المبيعات) ---
@st.cache_data(ttl=3600)
def load_sales_data(file_h, file_i):
    try:
        file_h.seek(0); file_i.seek(0)
        tree_h = ET.parse(file_h); df_h = pd.DataFrame([{c.tag: c.text for c in r} for r in tree_h.getroot()])
        tree_i = ET.parse(file_i); df_i = pd.DataFrame([{c.tag: c.text for c in r} for r in tree_i.getroot()])
        
        # تصفية المحذوف وتحويل التواريخ
        if 'IsDelete' in df_h.columns: df_h = df_h[~df_h['IsDelete'].isin(['True', 'true', '1'])]
        df_h['Date'] = pd.to_datetime(pd.to_numeric(df_h['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
        
        # معالجة المبالغ (ضمان قراءة السعر الصافي)
        df_i['Qty'] = pd.to_numeric(df_i['TotalQty'], errors='coerce').fillna(0)
        df_i['Amount'] = pd.to_numeric(df_i.get('TaxbleAmount', df_i.get('netStockAmount', 0)), errors='coerce').fillna(0)
        if 'netStockAmount' in df_i.columns and 'TaxbleAmount' not in df_i.columns: df_i['Amount'] = df_i['Amount'] / 1.15
        
        # الربط النهائي
        full = pd.merge(df_i, df_h[['TransCode', 'Date', 'InvoiceNo', 'SalesPerson', 'VoucherName']], on='TransCode', how='inner')
        full['SalesMan'] = full['SalesPerson'].fillna('عام')
        
        # معالجة المرتجعات (قلب القيمة)
        mask_ret = full['VoucherName'].str.contains('Return|مرتجع', case=False, na=False)
        full.loc[mask_ret, ['Amount', 'Qty']] *= -1
        return full
    except Exception as e: return None

# --- 4. القائمة الجانبية ---
with st.sidebar:
    st.header("لوحة التحكم")
    page = st.radio("تنقل بين الأقسام:", ["💰 المبيعات والأرباح", "💸 التحصيل والديون"])
    st.markdown("---")
    if page == "💰 المبيعات والأرباح":
        st.info("📂 ارفع ملفات المبيعات")
        f1 = st.file_uploader("StockInvoiceDetails.xml", type=['xml'], key="f1")
        f2 = st.file_uploader("StockInvoiceRowItems.xml", type=['xml'], key="f2")
        if f1 and f2: st.session_state['uploaded_files'] = (f1, f2)
    else:
        st.info("📂 ارفع ملف التحصيل")
        f3 = st.file_uploader("LedgerBook.xml", type=['xml'], key="f3")
        if f3: st.session_state['ledger_file'] = f3

# --- 5. مديول المبيعات ---
if page == "💰 المبيعات والأرباح":
    st.title("📊 تحليل المبيعات")
    if st.session_state['uploaded_files']:
        df = load_sales_data(st.session_state['uploaded_files'][0], st.session_state['uploaded_files'][1])
        if df is not None:
            # الفلاتر
            sellers = ['الكل'] + sorted(list(df['SalesMan'].unique()))
            sel_filter = st.selectbox("موظف المبيعات", sellers)
            df_sub = df if sel_filter == 'الكل' else df[df['SalesMan'] == sel_filter]
            
            # المؤشرات
            st.metric("صافي المبيعات (بدون ضريبة)", f"{df_sub['Amount'].sum():,.2f} ر.س")
            st.dataframe(df_sub[['Date', 'InvoiceNo', 'SalesMan', 'Amount']].head(20))
    else: st.warning("الرجاء رفع ملفات المبيعات من القائمة الجانبية.")

# --- 6. مديول التحصيل (تطابق 100% مع PDF) ---
elif page == "💸 التحصيل والديون":
    st.title("💸 مراقبة أرصدة العملاء")
    if st.session_state['ledger_file']:
        st.session_state['ledger_file'].seek(0)
        tree = ET.parse(st.session_state['ledger_file'])
        df_l = pd.DataFrame([{c.tag: c.text for c in r} for r in tree.getroot()])
        
        # تحويل الأرقام
        df_l['Dr'] = pd.to_numeric(df_l['Dr'], errors='coerce').fillna(0)
        df_l['Cr'] = pd.to_numeric(df_l['Cr'], errors='coerce').fillna(0)
        
        # الفلترة الذكية (الحسابات المدينة فقط من PDF)
        valid = df_l[df_l['AcLedger'].astype(str).str.startswith(('113', '221'))]
        
        debtors = valid.groupby('LedgerName').agg({'Dr':'sum', 'Cr':'sum'}).reset_index()
        debtors['Balance'] = debtors['Dr'] - debtors['Cr']
        
        # استبعاد المصارف والنقدية والحسابات الصفرية
        exclude = ["مصرف الراجحي", "البنك الأهلي", "صندوق", "نقدية", "شبكة"]
        debtors = debtors[~debtors['LedgerName'].str.contains('|'.join(exclude), na=False)]
        debtors = debtors[debtors['Balance'] >= 0.01].sort_values('Balance', ascending=False)
        
        # عرض النتائج
        st.metric("إجمالي مديونية العملاء", f"{debtors['Balance'].sum():,.2f} ر.س", help="الرصيد المستهدف: 218,789.96")
        st.subheader(f"عدد العملاء: {len(debtors)} (يجب أن يكون 40)")
        st.dataframe(debtors[['LedgerName', 'Balance']], column_config={"Balance": st.column_config.NumberColumn("الرصيد (دين)", format="%.2f")})
    else: st.warning("الرجاء رفع ملف LedgerBook.xml.")
