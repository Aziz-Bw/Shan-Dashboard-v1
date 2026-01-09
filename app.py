import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

# --- 1. الإعدادات الأساسية (بدون تخصيص ألوان معقد) ---
st.set_page_config(page_title="مدير شان الحديثة", layout="wide", page_icon="🏢")

# --- 2. إدارة الذاكرة المستمرة ---
if 'f1' not in st.session_state: st.session_state.f1 = None
if 'f2' not in st.session_state: st.session_state.f2 = None
if 'f3' not in st.session_state: st.session_state.f3 = None

# --- 3. دوال القراءة المضمونة ---
def get_df(file):
    if file is None: return None
    file.seek(0) # إعادة الشريط للبداية
    tree = ET.parse(file)
    return pd.DataFrame([{c.tag: c.text for c in r} for r in tree.getroot()])

# --- 4. القائمة الجانبية (مركز العمليات) ---
with st.sidebar:
    st.title("🏢 نظام شان")
    page = st.radio("القائمة الرئيسية:", ["💰 المبيعات", "💸 التحصيل"])
    st.divider()
    
    # قسم الرفع دائم الظهور في السايدبار لضمان الاستقرار
    st.subheader("📁 رفع الملفات")
    up1 = st.file_uploader("StockInvoiceDetails", type=['xml'])
    up2 = st.file_uploader("StockInvoiceRowItems", type=['xml'])
    up3 = st.file_uploader("LedgerBook", type=['xml'])
    
    if up1: st.session_state.f1 = up1
    if up2: st.session_state.f2 = up2
    if up3: st.session_state.f3 = up3
    
    if st.button("🗑️ تفريغ الذاكرة"):
        st.session_state.clear()
        st.rerun()

# --- 5. مديول المبيعات ---
if page == "💰 المبيعات":
    st.header("💰 تحليل المبيعات")
    if st.session_state.f1 and st.session_state.f2:
        df_h = get_df(st.session_state.f1)
        df_i = get_df(st.session_state.f2)
        
        try:
            # معالجة سريعة للربط
            df_h['Date'] = pd.to_datetime(pd.to_numeric(df_h['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
            df_i['Amount'] = pd.to_numeric(df_i.get('TaxbleAmount', df_i.get('netStockAmount', 0)), errors='coerce').fillna(0)
            if 'netStockAmount' in df_i.columns and 'TaxbleAmount' not in df_i.columns: df_i['Amount'] /= 1.15
            
            full = pd.merge(df_i, df_h[['TransCode', 'Date', 'InvoiceNo', 'VoucherName']], on='TransCode')
            mask_ret = full['VoucherName'].str.contains('Return|مرتجع', na=False)
            full.loc[mask_ret, 'Amount'] *= -1
            
            st.metric("صافي المبيعات", f"{full['Amount'].sum():,.2f} ر.س")
            st.dataframe(full[['Date', 'InvoiceNo', 'Amount']].head(15), use_container_width=True)
        except:
            st.error("خطأ في البيانات المرفوعة. تأكد من صحة الملفات.")
    else:
        st.info("الرجاء رفع ملفات المبيعات من القائمة الجانبية.")

# --- 6. مديول التحصيل (تطابق PDF) ---
elif page == "💸 التحصيل":
    st.header("💸 مديونية العملاء")
    if st.session_state.f3:
        df_l = get_df(st.session_state.f3)
        df_l['Dr'] = pd.to_numeric(df_l['Dr'], errors='coerce').fillna(0)
        df_l['Cr'] = pd.to_numeric(df_l['Cr'], errors='coerce').fillna(0)
        
        # الفلترة الذكية (113 و 221)
        debtors = df_l.groupby('LedgerName').agg({'Dr':'sum', 'Cr':'sum', 'AcLedger':'first'}).reset_index()
        debtors['Balance'] = debtors['Dr'] - debtors['Cr']
        
        exclude = ["مصرف الراجحي", "البنك الأهلي", "صندوق", "نقدية", "شبكة"]
        final = debtors[
            (debtors['AcLedger'].astype(str).str.startswith(('113', '221'))) & 
            (~debtors['LedgerName'].str.contains('|'.join(exclude), na=False)) &
            (debtors['Balance'] > 0.01)
        ].sort_values('Balance', ascending=False)
        
        st.metric("إجمالي المديونية المطابقة", f"{final['Balance'].sum():,.2f} ر.س", help="يجب أن يطابق 218,789.96")
        st.subheader(f"عدد العملاء: {len(final)} (المستهدف 40)")
        st.dataframe(final[['LedgerName', 'Balance']], use_container_width=True)
    else:
        st.info("الرجاء رفع ملف LedgerBook من القائمة الجانبية.")
