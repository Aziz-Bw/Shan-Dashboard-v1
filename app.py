import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

# --- 1. الإعدادات الأساسية (الوضع الافتراضي الواضح) ---
st.set_page_config(page_title="مدير شان الحديثة", layout="wide", page_icon="🏢")

# --- 2. إدارة الذاكرة (Session State) ---
# نستخدم أسماء فريدة لكل ملف لضمان عدم التداخل
if 'f_sales_h' not in st.session_state: st.session_state.f_sales_h = None
if 'f_sales_i' not in st.session_state: st.session_state.f_sales_i = None
if 'f_ledger' not in st.session_state: st.session_state.f_ledger = None

# --- 3. دوال المعالجة الآمنة ---
def safe_read_xml(file):
    if file is None: return None
    try:
        file.seek(0) # إعادة مؤشر القراءة للبداية دائماً
        tree = ET.parse(file)
        return pd.DataFrame([{c.tag: child.text for child in row} for row in tree.getroot()])
    except:
        return None

# --- 4. القائمة الجانبية (ثابتة ومنظمة) ---
with st.sidebar:
    st.title("🏢 إدارة شان الحديثة")
    page = st.radio("انتقل بين الأقسام:", ["💰 المبيعات والأرباح", "💸 التحصيل والديون"])
    st.divider()
    
    if page == "💰 المبيعات والأرباح":
        st.subheader("📁 ملفات المبيعات")
        u1 = st.file_uploader("StockInvoiceDetails", type=['xml'], key="u1")
        u2 = st.file_uploader("StockInvoiceRowItems", type=['xml'], key="u2")
        if u1: st.session_state.f_sales_h = u1
        if u2: st.session_state.f_sales_i = u2
    else:
        st.subheader("📁 ملف التحصيل")
        u3 = st.file_uploader("LedgerBook", type=['xml'], key="u3")
        if u3: st.session_state.f_ledger = u3

    if st.button("🗑️ إعادة ضبط النظام"):
        st.session_state.clear()
        st.rerun()

# ========================================================
# صفحة المبيعات (النسخة التي كانت تعمل بكفاءة)
# ========================================================
if page == "💰 المبيعات والأرباح":
    st.header("📊 تحليل المبيعات والأرباح")
    
    if st.session_state.f_sales_h and st.session_state.f_sales_i:
        df_h = safe_read_xml(st.session_state.f_sales_h)
        df_i = safe_read_xml(st.session_state.f_sales_i)
        
        if df_h is not None and df_i is not None:
            try:
                # معالجة التواريخ
                df_h['Date'] = pd.to_datetime(pd.to_numeric(df_h['TransDateValue'], errors='coerce'), unit='D', origin='1899-12-30')
                # معالجة المبالغ
                df_i['Qty'] = pd.to_numeric(df_i['TotalQty'], errors='coerce').fillna(0)
                df_i['Amount'] = pd.to_numeric(df_i.get('TaxbleAmount', df_i.get('netStockAmount', 0)), errors='coerce').fillna(0)
                if 'netStockAmount' in df_i.columns and 'TaxbleAmount' not in df_i.columns:
                    df_i['Amount'] = df_i['Amount'] / 1.15
                
                # الربط (Merge)
                full = pd.merge(df_i, df_h[['TransCode', 'Date', 'InvoiceNo', 'VoucherName', 'SalesPerson']], on='TransCode')
                
                # المرتجعات
                mask_ret = full['VoucherName'].str.contains('Return|مرتجع', na=False)
                full.loc[mask_ret, 'Amount'] *= -1
                
                # عرض المبيعات
                total_sales = full['Amount'].sum()
                st.metric("صافي المبيعات (بدون ضريبة)", f"{total_sales:,.2f} ر.س")
                st.dataframe(full[['Date', 'InvoiceNo', 'Amount']].head(20), use_container_width=True)
            except Exception as e:
                st.error(f"حدث خطأ في عرض البيانات: {e}")
    else:
        st.info("الرجاء رفع ملفات المبيعات من القائمة الجانبية.")

# ========================================================
# صفحة التحصيل (النسخة المطابقة لتقرير PDF)
# ========================================================
elif page == "💸 التحصيل والديون":
    st.header("💸 مديونية العملاء (التحصيل)")
    
    if st.session_state.f_ledger:
        df_l = safe_read_xml(st.session_state.f_ledger)
        
        if df_l is not None:
            try:
                df_l['Dr'] = pd.to_numeric(df_l['Dr'], errors='coerce').fillna(0)
                df_l['Cr'] = pd.to_numeric(df_l['Cr'], errors='coerce').fillna(0)
                
                # التجميع حسب العميل
                debtors = df_l.groupby('LedgerName').agg({
                    'Dr': 'sum', 
                    'Cr': 'sum', 
                    'AcLedger': 'first'
                }).reset_index()
                
                debtors['Balance'] = debtors['Dr'] - debtors['Cr']
                
                # الفلترة الذهبية (113 و 221) بناءً على PDF
                exclude = ["مصرف الراجحي", "البنك الأهلي", "صندوق", "نقدية", "شبكة"]
                
                final = debtors[
                    (debtors['AcLedger'].astype(str).str.startswith(('113', '221'))) & 
                    (~debtors['LedgerName'].str.contains('|'.join(exclude), na=False)) &
                    (debtors['Balance'] > 0.05)
                ].sort_values('Balance', ascending=False)
                
                # عرض النتائج
                st.metric("إجمالي المديونية (المطابقة للبرنامج)", f"{final['Balance'].sum():,.2f} ر.س")
                st.subheader(f"عدد العملاء: {len(final)} (المستهدف 40)")
                st.dataframe(final[['LedgerName', 'Balance']], use_container_width=True)
            except Exception as e:
                st.error(f"حدث خطأ في معالجة ملف التحصيل: {e}")
    else:
        st.info("الرجاء رفع ملف LedgerBook من القائمة الجانبية.")
