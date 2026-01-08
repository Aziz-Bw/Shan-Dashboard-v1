import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET
import time

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="Shan Modern | شان الحديثة", 
    layout="wide", 
    page_icon="🏢",
    initial_sidebar_state="expanded"
)

# --- 🎨 التصميم (CSS - إصلاح الألوان النهائي) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
    }

    /* إجبار الخلفية العامة على لون فاتح لتقليل التباين القاسي */
    .stApp {
        background-color: #f8f9fa;
    }

    :root {
        --brand-blue: #034275;
        --card-white: #ffffff;
    }

    /* إخفاء العناصر */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* --- الصناديق والكروت (إجبار النصوص على السواد) --- */
    
    .content-box, .metric-card, .salesman-box, .filters-box {
        background-color: #ffffff !important; /* خلفية بيضاء */
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }

    /* هذا السطر هو الحل السحري: يجبر كل النصوص داخل الكروت أن تكون سوداء */
    .content-box *, .metric-card *, .salesman-box *, .filters-box * {
        color: #333333 !important;
    }

    /* تخصيصات إضافية للعناوين والأرقام */
    .content-title {
        color: #034275 !important;
        font-weight: 800 !important;
    }
    
    .metric-value {
        color: #034275 !important;
        font-size: 22px !important;
        font-weight: 900 !important;
        direction: ltr;
    }
    
    .metric-sub {
        color: #666 !important;
        font-size: 11px !important;
    }
    
    .s-name {
        color: #034275 !important;
        font-size: 18px !important;
        font-weight: 800 !important;
    }
    
    /* تنسيق الجداول */
    .s-row {
        border-bottom: 1px dashed #eee;
        padding-bottom: 5px;
        margin-bottom: 5px;
        display: flex;
        justify-content: space-between;
        direction: rtl;
    }

    /* تنسيق زر الرفع */
    .stFileUploader label {
        color: #333 !important;
        font-weight: bold;
    }

</style>
""", unsafe_allow_html=True)

# --- 2. إدارة الحالة ---
if 'uploaded_files' not in st.session_state: st.session_state['uploaded_files'] = None
if 'ledger_file' not in st.session_state: st.session_state['ledger_file'] = None

# --- 3. المعالجة ---
def normalize_salesman_name(name):
    if pd.isna(name) or name == 'nan' or name == 'غير محدد': return 'غير محدد'
    name = str(name).strip()
    if 'سعيد' in name: return 'سعيد'
    if 'عبد' in name and 'الله' in name: return 'عبد الله'
    return name

@st.cache_data(ttl=3600)
def load_sales_data(file_header, file_items):
    try:
        file_header.seek(0); file_items.seek(0)
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

# --- دالة قراءة ملف التحصيل (Inspect) ---
@st.cache_data(ttl=3600)
def inspect_ledger_file(file_ledger):
    try:
        file_ledger.seek(0)
        tree = ET.parse(file_ledger)
        df = pd.DataFrame([{child.tag: child.text for child in row} for row in tree.getroot()])
        return df
    except Exception as e:
        st.error(f"خطأ في قراءة ملف التحصيل: {e}")
        return None

# --- 4. القائمة الجانبية ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=70)
    st.markdown("### شان الحديثة | Shan Modern")
    st.markdown("---")
    
    selected_page = st.radio(
        "القائمة الرئيسية",
        ["💰 المبيعات (Sales)", "💸 التحصيل والديون"],
        index=0
    )
    
    st.markdown("---")
    
    if selected_page == "💰 المبيعات (Sales)":
        st.info("📁 **ملفات المبيعات**")
        f1 = st.file_uploader("1. StockInvoiceDetails.xml", type=['xml'], key="f1")
        f2 = st.file_uploader("2. StockInvoiceRowItems.xml", type=['xml'], key="f2")
        if f1 and f2: st.session_state['uploaded_files'] = (f1, f2)
        
    elif selected_page == "💸 التحصيل والديون":
        st.info("📁 **ملف التحصيل**")
        f3 = st.file_uploader("3. LedgerBook.xml", type=['xml'], key="f3")
        if f3: st.session_state['ledger_file'] = f3

# --- 5. الصفحة: المبيعات ---
if selected_page == "💰 المبيعات (Sales)":
    
    if st.session_state['uploaded_files']:
        f1, f2 = st.session_state['uploaded_files']
        df = load_sales_data(f1, f2)
        
        if df is not None:
            # Header
            st.markdown("""
            <div class="content-box">
                <h2 class="content-title">💰 تحليل المبيعات والأداء</h2>
                <p>لوحة المعلومات المالية والفنية</p>
            </div>
            """, unsafe_allow_html=True)

            # Filters
            st.markdown('<div class="filters-box">', unsafe_allow_html=True)
            min_d, max_d = df['Date'].min().date(), df['Date'].max().date()
            fc1, fc2 = st.columns(2)
            with fc1: d_range = st.date_input("📅 الفترة الزمنية", [min_d, max_d])
            with fc2:
                s_list = ['الكل'] + sorted(list(df['SalesMan_Clean'].astype(str).unique()))
                s_filter = st.selectbox("👤 موظف المبيعات", s_list)
            st.markdown('</div>', unsafe_allow_html=True)

            # Logic
            df_filtered = df.copy()
            if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
                df_filtered = df_filtered[(df_filtered['Date'].dt.date >= d_range[0]) & (df_filtered['Date'].dt.date <= d_range[1])]
            if s_filter != 'الكل':
                df_filtered = df_filtered[df_filtered['SalesMan_Clean'] == s_filter]

            # Calcs
            net_sales = df_filtered['Amount'].sum()
            total_cost = df_filtered['TotalCost'].sum()
            total_profit = df_filtered['Profit'].sum()
            
            returns_data = df_filtered[df_filtered['Amount'] < 0]
            returns_val = abs(returns_data['Amount'].sum())
            returns_count = returns_data['TransCode'].nunique()
            
            invoices_count = df_filtered[df_filtered['Amount'] > 0]['TransCode'].nunique()
            
            margin = (total_profit / net_sales * 100) if net_sales > 0 else 0
            days_diff = (d_range[1] - d_range[0]).days if isinstance(d_range, (list, tuple)) and len(d_range) == 2 else 1
            months_diff = max(days_diff / 30, 1)

            # KPIs (Row 3)
            k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
            
            def metric_card(title, value, sub):
                return f"""<div class="metric-card"><div class="metric-label">{title}</div><div class="metric-value">{value}</div><div class="metric-sub">{sub}</div></div>"""

            with k1: st.markdown(metric_card("صافي المبيعات", f"{net_sales:,.0f}", "الإيراد الفعلي"), unsafe_allow_html=True)
            with k2: st.markdown(metric_card("صافي الربح", f"{total_profit:,.0f}", f"{margin:.1f}% هامش"), unsafe_allow_html=True)
            with k3: st.markdown(metric_card("تكلفة البضاعة", f"{total_cost:,.0f}", "المباعة للفترة"), unsafe_allow_html=True)
            with k4: st.markdown(metric_card("الإرجاعات", f"{returns_val:,.0f}", f"عدد: {returns_count} مرتجع"), unsafe_allow_html=True)
            with k5: st.markdown(metric_card("عدد الفواتير", f"{invoices_count}", "فاتورة مبيعات"), unsafe_allow_html=True)
            with k6: st.markdown(metric_card("متوسط المبيعات", f"{net_sales/months_diff:,.0f}", "شهرياً"), unsafe_allow_html=True)
            with k7: st.markdown(metric_card("متوسط الربح", f"{total_profit/months_diff:,.0f}", f"شهرياً ({margin:.1f}%)"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Salesmen (Row 4)
            st.subheader("👥 أداء فريق المبيعات")
            unique_salesmen = [sm for sm in df_filtered['SalesMan_Clean'].unique() if sm != 'غير محدد']
            cols = st.columns(3)
            
            def draw_salesman(col, name, data, is_total=False):
                s_net = data['Amount'].sum()
                s_prof = data['Profit'].sum()
                s_marg = (s_prof / s_net * 100) if s_net > 0 else 0
                s_ret_v = abs(data[data['Amount'] < 0]['Amount'].sum())
                s_ret_c = data[data['Amount'] < 0]['TransCode'].nunique()
                s_inv = data[data['Amount'] > 0]['TransCode'].nunique()
                border = "5px solid #27ae60" if is_total else "5px solid #034275"
                
                html = f"""<div class="salesman-box" style="border-right: {border};"><div class="s-header"><div class="s-name">{name}</div></div><div class="s-row"><span class="s-label">💰 المبيعات:</span><span class="s-val">{s_net:,.0f}</span></div><div class="s-row"><span class="s-label">📈 الربح:</span><span class="s-val">{s_prof:,.0f} ({s_marg:.1f}%)</span></div><div class="s-row"><span class="s-label">🧾 الفواتير:</span><span class="s-val">{s_inv}</span></div><div class="s-row" style="border-top:1px dashed #eee;"><span class="s-label" style="color:#c0392b !important">↩️ الإرجاع:</span><span class="s-val" style="color:#c0392b !important">{s_ret_v:,.0f} ({s_ret_c})</span></div></div>"""
                with col: st.markdown(html, unsafe_allow_html=True)

            idx = 0
            for sm in unique_salesmen:
                if idx < 2:
                    draw_salesman(cols[idx], sm, df_filtered[df_filtered['SalesMan_Clean'] == sm])
                    idx += 1
            draw_salesman(cols[2], "إجمالي الفريق", df_filtered, is_total=True)

            # Charts
            st.markdown("---")
            t1, t2 = st.tabs(["التدفق الزمني", "توزيع الماركات"])
            with t1:
                dly = df_filtered.groupby('Date')[['Amount', 'Profit']].sum().reset_index()
                fig = px.line(dly, x='Date', y=['Amount', 'Profit'], markers=True, color_discrete_map={'Amount': '#034275', 'Profit': '#27ae60'})
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", font=dict(color="black"), xaxis=dict(showgrid=True, gridcolor='#f0f0f0'), yaxis=dict(showgrid=True, gridcolor='#f0f0f0'))
                st.plotly_chart(fig, use_container_width=True)
            with t2:
                gp = df_filtered.groupby('stockgroup')[['Amount', 'Profit']].sum().reset_index().sort_values('Profit', ascending=False).head(10)
                fig_pie = px.pie(gp, values='Profit', names='stockgroup', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
                st.plotly_chart(fig_pie, use_container_width=True)

            # Table
            st.markdown("---")
            c1, c2 = st.columns([3, 1])
            with c1: st.subheader("📦 تقرير المخزون")
            items_sum = df_filtered.groupby(['StockName', 'StockCode', 'stockgroup']).agg(الكمية=('Qty', 'sum'), المبيعات=('Amount', 'sum'), الربح=('Profit', 'sum')).reset_index()
            items_sum['هامش_%'] = (items_sum['الربح'] / items_sum['المبيعات'] * 100).fillna(0)
            items_sum['تصريف_شهري'] = items_sum['الكمية'] / months_diff
            items_sum = items_sum.sort_values('الربح', ascending=False)
            with c2:
                csv = items_sum.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 تحميل التقرير", data=csv, file_name="Shan_Report.csv", mime="text/csv")
            st.dataframe(items_sum, use_container_width=True, height=600)
            
    else:
        st.warning("⚠️ الرجاء رفع ملفات الفواتير من القائمة الجانبية لعرض المبيعات.")

# ==========================
# صفحة 2: التحصيل والديون
# ==========================
elif selected_page == "💸 التحصيل والديون":
    
    # عنوان الصفحة
    st.markdown("""
    <div class="content-box">
        <h2 class="content-title">💸 مراقبة الديون والتحصيل</h2>
        <p>تحليل أرصدة العملاء والديون القائمة (Credit Control)</p>
    </div>
    """, unsafe_allow_html=True)
    
    # التأكد من وجود الملف
    if not st.session_state['ledger_file']:
        st.warning("⚠️ الرجاء رفع ملف LedgerBook.xml من القائمة الجانبية للبدء.")
    else:
        # قراءة الملف
        df_ledger = inspect_ledger_file(st.session_state['ledger_file'])
        
        if df_ledger is not None:
            # --- 1. معالجة البيانات (Data Processing) ---
            # تحويل الأرقام
            df_ledger['Dr'] = pd.to_numeric(df_ledger['Dr'], errors='coerce').fillna(0)
            df_ledger['Cr'] = pd.to_numeric(df_ledger['Cr'], errors='coerce').fillna(0)
            
            # تجميع البيانات حسب اسم العميل/الحساب
            # نجمع كل الحركات (فواتير + سندات) لكل شخص
            customers_summary = df_ledger.groupby('LedgerName').agg(
                Total_Debit=('Dr', 'sum'),  # إجمالي ما أخذه (مدين)
                Total_Credit=('Cr', 'sum'), # إجمالي ما سدده (دائن)
                Transactions=('TransCode', 'count') # عدد الحركات
            ).reset_index()
            
            # حساب الرصيد الحالي (الديون)
            # الرصيد = المدين - الدائن
            customers_summary['Balance'] = customers_summary['Total_Debit'] - customers_summary['Total_Credit']
            
            # --- الفلترة الذكية (استبعاد الموردين والأرصدة الصفرية) ---
            # نفترض أن العميل هو من عليه دين (رصيد موجب أكبر من 1 ريال)
            # هذا سيخفي الموردين (رصيد سالب) والمخلصين (رصيد صفر)
            debtors = customers_summary[customers_summary['Balance'] > 10].sort_values('Balance', ascending=False)
            
            # --- 2. المؤشرات العامة (KPIs) ---
            total_debt = debtors['Balance'].sum() # إجمالي الديون في السوق
            total_collected = debtors['Total_Credit'].sum() # ما تم تحصيله من هؤلاء
            collection_rate = (total_collected / (total_collected + total_debt) * 100) if total_debt > 0 else 0
            debtors_count = debtors['LedgerName'].nunique()
            
            # عرض الكروت
            k1, k2, k3, k4 = st.columns(4)
            
            # دالة الكرت (نفس التصميم السابق)
            def metric_card(title, value, sub, color="#034275"):
                return f"""<div class="metric-card"><div class="metric-label">{title}</div><div class="metric-value" style="color: {color} !important;">{value}</div><div class="metric-sub">{sub}</div></div>"""

            with k1: st.markdown(metric_card("إجمالي الديون (لكم)", f"{total_debt:,.0f}", "رصيد قائم بالسوق", "#c0392b"), unsafe_allow_html=True)
            with k2: st.markdown(metric_card("إجمالي التحصيل", f"{total_collected:,.0f}", "دفعات مستلمة", "#27ae60"), unsafe_allow_html=True)
            with k3: st.markdown(metric_card("نسبة التحصيل", f"{collection_rate:.1f}%", "معدل السداد"), unsafe_allow_html=True)
            with k4: st.markdown(metric_card("عدد المديونيات", f"{debtors_count}", "عميل عليه رصيد"), unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- 3. الرسم البياني (أعلى 10 ديون) ---
            c1, c2 = st.columns([2, 1])
            
            with c1:
                st.subheader("📊 أعلى 10 عملاء عليهم مديونيات")
                top_10_debtors = debtors.head(10)
                fig = px.bar(top_10_debtors, x='LedgerName', y='Balance', text_auto='.2s',
                             title="", color='Balance', color_continuous_scale='Reds')
                fig.update_layout(
                    plot_bgcolor="white", paper_bgcolor="white", font=dict(color="black"),
                    xaxis_title="العميل", yaxis_title="المبلغ المتبقى (ر.س)"
                )
                st.plotly_chart(fig, use_container_width=True)
                
            with c2:
                st.subheader("🥧 توزيع الديون")
                # تصنيف الديون (كبار، متوسط، صغير)
                def categorize_debt(amount):
                    if amount > 50000: return 'ديون ضخمة (>50k)'
                    elif amount > 10000: return 'ديون متوسطة (10k-50k)'
                    else: return 'ديون صغيرة (<10k)'
                
                debtors['Category'] = debtors['Balance'].apply(categorize_debt)
                pie_data = debtors.groupby('Category')['Balance'].sum().reset_index()
                
                fig_pie = px.pie(pie_data, values='Balance', names='Category', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                st.plotly_chart(fig_pie, use_container_width=True)

            # --- 4. الجدول التفصيلي ---
            st.markdown("### 📋 كشف أرصدة العملاء التفصيلي")
            
            # تنسيق الجدول
            st.dataframe(
                debtors[['LedgerName', 'Total_Debit', 'Total_Credit', 'Balance', 'Transactions']],
                column_config={
                    "LedgerName": "اسم العميل",
                    "Total_Debit": st.column_config.NumberColumn("إجمالي المسحوبات", format="%d"),
                    "Total_Credit": st.column_config.NumberColumn("إجمالي السداد", format="%d"),
                    "Balance": st.column_config.NumberColumn("الرصيد المتبقى (الدين)", format="%d"),
                    "Transactions": "عدد الحركات"
                },
                use_container_width=True,
                height=600
            )
