import streamlit as st
from supabase import create_client
import pandas as pd
from fpdf import FPDF
from datetime import datetime, timedelta

# ==========================================
# 1. KONEKSI & FUNGSI BANTUAN
# ==========================================
st.set_page_config(page_title="Sistem Koperasi", page_icon="🏦", layout="wide")

try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("⚠️ Koneksi Database Gagal. Cek file .streamlit/secrets.toml")
    st.stop()

def format_rupiah(angka):
    if angka is None: return "Rp 0"
    return f"Rp {angka:,.0f}".replace(",", ".")

def bersihkan_angka(nilai):
    if pd.isna(nilai) or str(nilai).strip() in ['', '-', 'nan', 'Nan', '#N/A']: return 0
    if isinstance(nilai, (int, float)): return float(nilai)
    str_val = str(nilai).replace('Rp', '').replace('.', '').replace(' ', '').replace(',', '.')
    try: return float(str_val)
    except: return 0

def proses_tanggal(nilai):
    if pd.isna(nilai) or str(nilai).strip() in ['', '-', 'nan']: return "-", 0
    try:
        if isinstance(nilai, (int, float)) or (isinstance(nilai, str) and nilai.isdigit()):
            py_date = datetime(1899, 12, 30) + timedelta(days=float(nilai))
            return py_date.strftime("%d-%m-%Y"), py_date.year
        py_date = pd.to_datetime(nilai)
        return py_date.strftime("%d-%m-%Y"), py_date.year
    except: return str(nilai), 0

# ==========================================
# 2. PDF GENERATOR
# ==========================================
def buat_pdf_tagihan(df, judul_laporan):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    
    # KOP
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "KOPERASI SIMPAN PINJAM", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, judul_laporan.upper(), ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, f"Periode: {datetime.now().strftime('%B %Y')}", ln=True, align='C')
    pdf.line(10, 35, 285, 35)
    pdf.ln(10)
    
    # HEADER
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(220, 230, 240)
    w_no=10; w_nama=60; w_wajib=35; w_pokok=35; w_jasa=35; w_total=50
    
    pdf.cell(w_no, 10, "No", 1, 0, 'C', True)
    pdf.cell(w_nama, 10, "Nama Anggota", 1, 0, 'C', True)
    pdf.cell(w_wajib, 10, "Simp. Wajib", 1, 0, 'C', True)
    pdf.cell(w_pokok, 10, "Angsuran Pokok", 1, 0, 'C', True)
    pdf.cell(w_jasa, 10, "Jasa (1%)", 1, 0, 'C', True)
    pdf.cell(w_total, 10, "TOTAL TAGIHAN", 1, 1, 'C', True)
    
    # ISI
    pdf.set_font("Arial", size=9)
    no = 1
    sum_wajib = 0; sum_pinjaman = 0; sum_grand = 0
    
    for _, row in df.iterrows():
        sum_wajib += row['wajib']
        sum_pinjaman += (row['pokok'] + row['jasa'])
        sum_grand += row['total_bayar']
        
        pdf.cell(w_no, 8, str(no), 1, 0, 'C')
        pdf.cell(w_nama, 8, str(row['nama'])[:30], 1, 0, 'L')
        pdf.cell(w_wajib, 8, format_rupiah(row['wajib']), 1, 0, 'R')
        pdf.cell(w_pokok, 8, format_rupiah(row['pokok']), 1, 0, 'R')
        pdf.cell(w_jasa, 8, format_rupiah(row['jasa']), 1, 0, 'R')
        
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(w_total, 8, format_rupiah(row['total_bayar']), 1, 1, 'R')
        pdf.set_font("Arial", size=9)
        no += 1
        
    # FOOTER
    pdf.ln(5)
    if pdf.get_y() > 150: pdf.add_page()
    
    pdf.set_x(180)
    pdf.set_font("Arial", '', 10)
    pdf.cell(60, 8, "Total Simpanan Wajib", 1, 0, 'L')
    pdf.cell(40, 8, format_rupiah(sum_wajib), 1, 1, 'R')
    
    pdf.set_x(180)
    pdf.cell(60, 8, "Total Angsuran + Jasa", 1, 0, 'L')
    pdf.cell(40, 8, format_rupiah(sum_pinjaman), 1, 1, 'R')
    
    pdf.set_x(180)
    pdf.set_font("Arial", 'B', 11)
    pdf.set_fill_color(255, 255, 0)
    pdf.cell(60, 10, "GRAND TOTAL", 1, 0, 'L', True)
    pdf.cell(40, 10, format_rupiah(sum_grand), 1, 1, 'R', True)
    
    if pdf.get_y() > 160: pdf.add_page()
    pdf.ln(15)
    pdf.set_font("Arial", size=10)
    pdf.cell(200)
    pdf.cell(70, 6, f"Bengkulu, {datetime.now().strftime('%d-%m-%Y')}", 0, 1, 'C')
    pdf.ln(20)
    pdf.cell(200)
    pdf.cell(70, 6, "( Bendahara )", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. MENU UTAMA
# ==========================================
menu = st.sidebar.radio("Navigasi", ["🏠 Upload Data Excel", "💰 Buat Tagihan (Pisah)", "🔍 Cek Per Orang"])

# --- MENU UPLOAD ---
if menu == "🏠 Upload Data Excel":
    st.title("📥 Upload & Sinkronisasi")
    st.markdown("""
    **Fitur Pintar:**
    1. Otomatis menghapus duplikat nama di data anggota.
    2. Memisahkan Pinjaman Lama (Lunas) dan Pinjaman Baru (Top Up) berdasarkan Tahun.
    """)
    
    uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = [c.strip() for c in df.columns]
            
            if st.button("🚀 PROSES DATA"):
                # ========================================================
                # 1. UPDATE TABEL ANGGOTA (DENGAN PENYARING DUPLIKAT)
                # ========================================================
                
                # Kita pakai Dictionary agar No Anggota jadi KUNCI UNIK
                # Jika No. 4 muncul 2x, yang kedua akan menimpa yg pertama (Jadi tetap 1 data)
                anggota_unique_dict = {}
                
                for _, row in df.iterrows():
                    nm = str(row.get('Nama', 'Tanpa Nama')).strip()
                    no = str(row.get('No. Anggota', '-')).strip()
                    
                    if no not in ['-', '', 'nan']:
                        anggota_unique_dict[no] = {"no_anggota": no, "nama": nm}
                
                # Ubah dictionary kembali jadi list untuk diinsert
                anggota_batch = list(anggota_unique_dict.values())
                
                # Hapus data lama dan insert yang baru (yang sudah bersih dari duplikat)
                supabase.table("anggota").delete().neq("id", 0).execute()
                if anggota_batch:
                    # Insert per 100 data
                    for i in range(0, len(anggota_batch), 100):
                        supabase.table("anggota").insert(anggota_batch[i:i+100]).execute()
                
                # ========================================================
                # 2. UPDATE TABEL PINJAMAN (SEMUA DATA MASUK)
                # ========================================================
                supabase.table("rekap_final").delete().neq("id", 0).execute()
                pinjaman_batch = []
                bln_list = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
                
                def get_val(r, k):
                    for x in k:
                        for c in df.columns:
                            if x.lower() == c.lower(): return r[c]
                    return 0
                
                def get_metode(r):
                    for c in df.columns:
                        if c.lower() in ['metode bayar', 'keterangan', 'cara bayar']:
                            val = str(r[c]).lower()
                            if 'sendiri' in val or 'tunai' in val: return 'SENDIRI'
                    return 'KANTOR'

                for _, row in df.iterrows():
                    try:
                        plafon = bersihkan_angka(get_val(row, ['Plafon']))
                        val_sebelum = bersihkan_angka(get_val(row, ['Sebelum th 2026', 'Sebelum']))
                        
                        raw_tgl = row.get('Tanggal Pinjaman', '-')
                        tgl_str, tahun_pinjam = proses_tanggal(raw_tgl)
                        
                        # LOGIKA SALDO (TAHUN)
                        if val_sebelum > 0:
                            saldo = val_sebelum
                        else:
                            # Jika Saldo 0/Kosong, Cek Tahun
                            if tahun_pinjam >= 2026:
                                saldo = plafon  # Baru
                            else:
                                saldo = 0       # Lunas
                        
                        bayar = 0; cnt = 0
                        for b in bln_list:
                            v = bersihkan_angka(get_val(row, [b]))
                            if v > 0: bayar += v; cnt += 1
                        
                        sisa = saldo - bayar
                        if sisa < 0: sisa = 0
                        
                        jenis = get_metode(row)
                        
                        pinjaman_batch.append({
                            "no_anggota": str(row.get('No. Anggota', '-')),
                            "nama": str(row.get('Nama', 'Tanpa Nama')),
                            "plafon": plafon,
                            "tanggal_pinjam": tgl_str,
                            "saldo_awal_tahun": saldo,
                            "total_angsuran_tahun_ini": bayar,
                            "sisa_akhir": sisa,
                            "bulan_berjalan": cnt,
                            "jenis_bayar": jenis
                        })
                    except: pass
                
                if pinjaman_batch:
                    for i in range(0, len(pinjaman_batch), 100):
                        supabase.table("rekap_final").insert(pinjaman_batch[i:i+100]).execute()
                
                st.success("✅ SUKSES! Data Anggota Ganda sudah dibersihkan otomatis.")
                st.balloons()
                
        except Exception as e: st.error(f"Error: {e}")

# --- MENU TAGIHAN ---
elif menu == "💰 Buat Tagihan (Pisah)":
    st.title("💰 Rekap Tagihan Bulanan")
    
    res_agg = supabase.table("anggota").select("*").order("nama").execute()
    list_agg = res_agg.data if res_agg.data else []
    
    # Ambil Pinjaman AKTIF saja (Sisa > 100)
    res_pinj = supabase.table("rekap_final").select("*").gt("sisa_akhir", 100).execute()
    dict_pinj = { item['nama'].strip().lower(): item for item in res_pinj.data } if res_pinj.data else {}
    
    if list_agg:
        data_kantor = []
        data_sendiri = []
        
        for agg in list_agg:
            nama = agg['nama']
            key = nama.strip().lower()
            
            wajib = 150000
            pokok = 0
            jasa = 0
            metode = 'KANTOR'
            
            if key in dict_pinj:
                pinj = dict_pinj[key]
                pokok = pinj['plafon'] / 10
                jasa = pinj['plafon'] * 0.01
                metode = pinj.get('jenis_bayar', 'KANTOR')
            
            item = {
                "nama": nama,
                "wajib": wajib,
                "pokok": pokok,
                "jasa": jasa,
                "total_bayar": wajib + pokok + jasa
            }
            
            if metode == 'SENDIRI':
                data_sendiri.append(item)
            else:
                data_kantor.append(item)
        
        tab1, tab2 = st.tabs(["🏢 Tagihan KANTOR", "👤 Tagihan MANDIRI"])
        
        with tab1:
            st.subheader("📋 Daftar Potong Gaji")
            if data_kantor:
                df1 = pd.DataFrame(data_kantor)
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Wajib", format_rupiah(df1['wajib'].sum()))
                c2.metric("Total Pinjaman", format_rupiah(df1['pokok'].sum() + df1['jasa'].sum()))
                c3.metric("Grand Total", format_rupiah(df1['total_bayar'].sum()))
                
                st.dataframe(df1.style.format({"wajib":"Rp {:,.0f}", "pokok":"Rp {:,.0f}", "jasa":"Rp {:,.0f}", "total_bayar":"Rp {:,.0f}"}))
                st.download_button("🖨️ Download PDF", buat_pdf_tagihan(df1, "DAFTAR POTONGAN GAJI PEGAWAI"), "Tagihan_Kantor.pdf", "application/pdf", type="primary")
            else: st.info("Tidak ada data.")
            
        with tab2:
            st.subheader("📋 Daftar Penagihan Manual")
            if data_sendiri:
                df2 = pd.DataFrame(data_sendiri)
                st.dataframe(df2.style.format({"wajib":"Rp {:,.0f}", "pokok":"Rp {:,.0f}", "jasa":"Rp {:,.0f}", "total_bayar":"Rp {:,.0f}"}))
                st.download_button("🖨️ Download PDF", buat_pdf_tagihan(df2, "DAFTAR TAGIHAN SETOR MANDIRI"), "Tagihan_Mandiri.pdf", "application/pdf")
            else: st.info("Tidak ada data.")
            
    else: st.warning("Data kosong.")

elif menu == "🔍 Cek Per Orang":
    st.title("🔍 Cek Anggota")
    cari = st.text_input("Ketik Nama:")
    if cari:
        res = supabase.table("rekap_final").select("*").ilike("nama", f"%{cari}%").execute()
        if res.data:
            for item in res.data:
                pokok = item['plafon'] / 10; jasa = item['plafon'] * 0.01; total = pokok + jasa + 150000
                jenis = item.get('jenis_bayar', 'KANTOR')
                bg = "orange" if jenis == 'SENDIRI' else "blue"
                
                st.markdown(f"""
                <div style="border:1px solid #ddd; padding:15px; border-radius:10px; color:black;">
                    <div style="display:flex; justify-content:space-between;">
                        <h4>{item['nama']} ({item['no_anggota']})</h4>
                        <span style="background:{bg}; color:white; padding:2px 8px; border-radius:4px;">BAYAR: {jenis}</span>
                    </div>
                    <p>Sisa Pinjaman: <b>{format_rupiah(item['sisa_akhir'])}</b></p>
                    <hr>
                    <b>Tagihan Bulan Ini:</b> {format_rupiah(total)}
                </div>
                """, unsafe_allow_html=True)
