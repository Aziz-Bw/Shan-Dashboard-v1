import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="مدير شان الحديثة", layout="wide", page_icon="🏢")

# --- 2. إدارة الحالة ---
if 'uploaded_files' not in st.session_state: st.session_state['uploaded_files'] = None
if 'ledger_file' not in st.session_state: st.session_state['ledger_file'] = None

# --- 3. دوال المعالجة ---
@st.cache_data(ttl=3600)
def load_sales_data(file_header, file_items):
    try:
        file_header.seek(0); file_items.seek(0)
        tree_h = ET.parse(file_header); df_h = pd.DataFrame([{c.tag: c.text for c in r} for r in tree_h.getroot()])
        tree_i = ET.parse(file_items); df_i = pd.DataFrame([{c.tag: c.text for c in r} for r in tree_i.getroot()])
        
        if 'IsDelete' in df_h.columns: df_h = df_h[~df_h['IsDelete'].isin(['True', 'true', '1'])]
        df_h['Date'] = pd.to_datetime(pd.to_numeric(df_h['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
        df_i['Qty'] = pd.to_numeric(df_i['TotalQty'], errors='coerce').fillna(0)
        df_i['Amount'] = pd.to_numeric(df_i.get('TaxbleAmount', df_i.get('netStockAmount', 0)), errors='coerce').fillna(0)
        if 'netStockAmount' in df_i.columns and 'TaxbleAmount' not in df_i.columns: df_i['Amount'] = df_i['Amount'] / 1.15
        
        full_data = pd.merge(df_i, df_h[['TransCode', 'Date', 'InvoiceNo', 'SalesPerson', 'VoucherName']], on='TransCode', how='inner')
        full_data['SalesMan'] = full_data['SalesPerson'].fillna('عام')
        
        mask_ret = full_data['VoucherName'].str.contains('Return|مرتجع', case=False, na=False)
        full_data.loc[mask_ret, ['Amount', 'Qty']] *= -1
        full_data['Profit'] = full_data['Amount'] # تبسيط للربح في حال عدم وجود تكلفة
        
        return full_data
    except Exception as e: return None

# --- 4. القائمة الجانبية ---
with st.sidebar:
    st.header("لوحة التحكم")
    page = st.radio("الأقسام:", ["💰 المبيعات والأرباح", "💸 التحصيل والديون"])
    if page == "💰 المبيعات والأرباح":
        f1 = st.file_uploader("StockInvoiceDetails.xml", type=['xml'], key="f1")
        f2 = st.file_uploader("StockInvoiceRowItems.xml", type=['xml'], key="f2")
        if f1 and f2: st.session_state['uploaded_files'] = (f1, f2)
    else:
        f3 = st.file_uploader("LedgerBook.xml", type=['xml'], key="f3")
        if f3: st.session_state['ledger_file'] = f3

# --- 5. مديول المبيعات ---
if page == "💰 المبيعات والأرباح":
    if st.session_state['uploaded_files']:
        df = load_sales_data(st.session_state['uploaded_files'][0], st.session_state['uploaded_files'][1])
        if df is not None:
            sales = df['Amount'].sum()
            st.metric("صافي المبيعات", f"{sales:,.2f} ر.س")
            st.dataframe(df.head())
    else: st.warning("الرجاء رفع ملفات المبيعات.")

# --- 6. مديول التحصيل (التطابق التام) ---
elif page == "💸 التحصيل والديون":
    if st.session_state['ledger_file']:
        st.session_state['ledger_file'].seek(0)
        tree = ET.parse(st.session_state['ledger_file'])
        df_l = pd.DataFrame([{c.tag: c.text for c in r} for r in tree.getroot()])
        df_l['Dr'] = pd.to_numeric(df_l['Dr'], errors='coerce').fillna(0)
        df_l['Cr'] = pd.to_numeric(df_l['Cr'], errors='coerce').fillna(0)
        
        # الفلترة الذكية بناءً على AcLedger المستخلص من الـ PDF
        # نأخذ أي حساب يحتوي على "مبيعات" أو يبدأ بـ 113 أو 221
        valid_ledgers = df_l[df_l['AcLedger'].astype(str).str.startswith(('113', '221')) | 
                             df_l['AcLedger'].astype(str).str.contains('مبيعات', na=False)]
        
        debtors = valid_ledgers.groupby('LedgerName').agg({'Dr':'sum', 'Cr':'sum'}).reset_index()
        debtors['Balance'] = debtors['Dr'] - debtors['Cr']
        
        # استبعاد مصرف الراجحي والحسابات غير الصفرية
        exclude = ["مصرف الراجحي", "البنك الأهلي", "صندوق", "نقدية", "شبكة"]
        debtors = debtors[~debtors['LedgerName'].str.contains('|'.join(exclude), na=False)]
        debtors = debtors[debtors['Balance'] > 0.1].sort_values('Balance', ascending=False)
        
        total_debt = debtors['Balance'].sum()
        st.metric("إجمالي مديونية العملاء", f"{total_debt:,.2f} ر.س", help="يجب أن يطابق 218,789.96")
        st.subheader(f"عدد العملاء: {len(debtors)}")
        st.dataframe(debtors[['LedgerName', 'Balance']])
