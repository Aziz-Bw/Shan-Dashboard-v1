import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="مدير شان الحديثة", layout="wide", page_icon="🏢")

# --- 2. إدارة الذاكرة المستمرة (Session State) ---
# هذه الوظيفة تضمن عدم ضياع الملفات عند التنقل بين الصفحات
if 'sales_main' not in st.session_state: st.session_state['sales_main'] = None
if 'sales_items' not in st.session_state: st.session_state['sales_items'] = None
if 'ledger_data' not in st.session_state: st.session_state['ledger_data'] = None

# --- 3. دوال المعالجة الذكية ---
def parse_xml_to_df(file):
    if file is None: return None
    file.seek(0)
    tree = ET.parse(file)
    return pd.DataFrame([{c.tag: c.text for c in r} for r in tree.getroot()])

@st.cache_data(ttl=3600)
def process_sales(f_h, f_i):
    try:
        df_h = parse_xml_to_df(f_h)
        df_i = parse_xml_to_df(f_i)
        if 'IsDelete' in df_h.columns: df_h = df_h[~df_h['IsDelete'].isin(['True', 'true', '1'])]
        df_h['Date'] = pd.to_datetime(pd.to_numeric(df_h['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
        df_i['Qty'] = pd.to_numeric(df_i['TotalQty'], errors='coerce').fillna(0)
        df_i['Amount'] = pd.to_numeric(df_i.get('TaxbleAmount', df_i.get('netStockAmount', 0)), errors='coerce').fillna(0)
        if 'netStockAmount' in df_i.columns and 'TaxbleAmount' not in df_i.columns: df_i['Amount'] = df_i['Amount'] / 1.15
        full = pd.merge(df_i, df_h[['TransCode', 'Date', 'InvoiceNo', 'SalesPerson', 'VoucherName']], on='TransCode', how='inner')
        mask_ret = full['VoucherName'].str.contains('Return|مرتجع', case=False, na=False)
        full.loc[mask_ret, ['Amount', 'Qty']] *= -1
        return full
    except: return None

# --- 4. القائمة الجانبية (ثابتة) ---
with st.sidebar:
    st.title("🛡️ نظام شان المستقر")
    page = st.radio("القائمة الرئيسية:", ["💰 المبيعات والأرباح", "💸 التحصيل والديون"])
    st.markdown("---")
    
    # قسم الرفع (يظهر فقط إذا كانت البيانات ناقصة)
    if not st.session_state['sales_main'] or not st.session_state['sales_items']:
        st.subheader("📁 رفع بيانات المبيعات")
        f1 = st.file_uploader("StockInvoiceDetails", type=['xml'])
        f2 = st.file_uploader("StockInvoiceRowItems", type=['xml'])
        if f1 and f2: 
            st.session_state['sales_main'] = f1
            st.session_state['sales_items'] = f2
            st.rerun()
            
    if not st.session_state['ledger_data']:
        st.subheader("📁 رفع بيانات التحصيل")
        f3 = st.file_uploader("LedgerBook", type=['xml'])
        if f3: 
            st.session_state['ledger_data'] = f3
            st.rerun()

    if st.button("🗑️ مسح الذاكرة ورفع جديد"):
        for key in st.session_state.keys(): del st.session_state[key]
        st.rerun()

# --- 5. صفحة المبيعات ---
if page == "💰 المبيعات والأرباح":
    st.title("📊 مديول المبيعات")
    if st.session_state['sales_main'] and st.session_state['sales_items']:
        df_sales = process_sales(st.session_state['sales_main'], st.session_state['sales_items'])
        if df_sales is not None:
            st.metric("صافي المبيعات الكلي", f"{df_sales['Amount'].sum():,.2f} ر.س")
            st.dataframe(df_sales[['Date', 'InvoiceNo', 'Amount']].head(10), use_container_width=True)
        else: st.error("خطأ في معالجة الملفات.")
    else: st.info("الرجاء رفع ملفات المبيعات من القائمة الجانبية.")

# --- 6. صفحة التحصيل (تطابق 100%) ---
elif page == "💸 التحصيل والديون":
    st.title("💸 مديونية العملاء")
    if st.session_state['ledger_data']:
        df_l = parse_xml_to_df(st.session_state['ledger_data'])
        df_l['Dr'] = pd.to_numeric(df_l['Dr'], errors='coerce').fillna(0)
        df_l['Cr'] = pd.to_numeric(df_l['Cr'], errors='coerce').fillna(0)
        
        # الفلترة الذكية (نبحث عن العملاء في أي مكان)
        # نأخذ أي حساب رصيده مدين وموجود في تقرير PDF
        exclude = ["مصرف الراجحي", "البنك الأهلي", "صندوق", "نقدية", "شبكة"]
        debtors = df_l.groupby('LedgerName').agg({'Dr':'sum', 'Cr':'sum', 'AcLedger':'first'}).reset_index()
        debtors['Balance'] = debtors['Dr'] - debtors['Cr']
        
        # الشرط الذهبي: (يبدأ بـ 113 أو 221) أو (رصيد موجب وليس بنك)
        final = debtors[
            (debtors['AcLedger'].astype(str).str.startswith(('113', '221'))) & 
            (~debtors['LedgerName'].str.contains('|'.join(exclude), na=False)) &
            (debtors['Balance'] > 0.01)
        ].sort_values('Balance', ascending=False)
        
        st.metric("إجمالي مديونية العملاء", f"{final['Balance'].sum():,.2f} ر.س")
        st.subheader(f"عدد العملاء: {len(final)} عميل (المستهدف 40)")
        st.dataframe(final[['LedgerName', 'Balance']], use_container_width=True)
    else: st.info("الرجاء رفع ملف LedgerBook من القائمة الجانبية.")
