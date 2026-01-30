import streamlit as st
from supabase import create_client
import pandas as pd
from fpdf import FPDF
from datetime import datetime, timedelta

# ==========================================
# 1. KONEKSI & FUNGSI
# ==========================================
st.set_page_config(page_title="Sistem Koperasi", page_icon="🏦", layout="wide")

try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("⚠️ Koneksi Database Gagal.")
    st.stop()

def format_rupiah(angka):
    if angka is None: return "Rp 0"
    return f"Rp {angka:,.0f}".replace(",", ".")

def bersihkan_angka(nilai):
    if pd.isna(nilai) or str(nilai).strip() in ['', '-', 'nan']: return 0
    if isinstance(nilai, (int, float)): return float(nilai)
    str_val = str(nilai).replace('Rp', '').replace('.', '').replace(' ', '').replace(',', '.')
    try: return float(str_val)
    except: return 0

def perbaiki_tanggal(nilai):
    if pd.isna(nilai) or str(nilai).strip() in ['', '-']: return "-"
    try:
        if isinstance(nilai, (int, float)) or (isinstance(nilai, str) and nilai.isdigit()):
            return (datetime(1899, 12, 30) + timedelta(days=float(nilai))).strftime("%d-%m-%Y")
        return pd.to_datetime(nilai).strftime("%d-%m-%Y")
    except: return str(nilai)

# ==========================================
# 2. PDF GENERATOR
# ==========================================
def buat_pdf_tagihan(df, judul_laporan):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    
    # KOP
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "KOPERASI PENGAYOMAAN", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, judul_laporan.upper(), ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Periode: {datetime.now().strftime('%B %Y')}", ln=True, align='C')
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
    total_all = 0
    
    for _, row in df.iterrows():
        pdf.cell(w_no, 8, str(no), 1, 0, 'C')
        pdf.cell(w_nama, 8, str(row['nama'])[:30], 1, 0, 'L')
        pdf.cell(w_wajib, 8, format_rupiah(row['wajib']), 1, 0, 'R')
        pdf.cell(w_pokok, 8, format_rupiah(row['pokok']), 1, 0, 'R')
        pdf.cell(w_jasa, 8, format_rupiah(row['jasa']), 1, 0, 'R')
        
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(w_total, 8, format_rupiah(row['total_bayar']), 1, 1, 'R')
        pdf.set_font("Arial", size=9)
        
        total_all += row['total_bayar']
        no += 1
        
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(w_no+w_nama+w_wajib+w_pokok+w_jasa, 12, "TOTAL:", 1, 0, 'R')
    pdf.set_fill_color(255, 255, 0)
    pdf.cell(w_total, 12, format_rupiah(total_all), 1, 1, 'R', True)
    
    pdf.ln(15); pdf.set_font("Arial", size=10)
    pdf.cell(200); pdf.cell(70, 6, f"Bengkulu, {datetime.now().strftime('%d-%m-%Y')}", 0, 1, 'C')
    pdf.ln(20); pdf.cell(200); pdf.cell(70, 6, "( Bendahara )", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. MENU UTAMA
# ==========================================
menu = st.sidebar.radio("Navigasi", ["🏠 Upload Data Excel", "💰 Buat Tagihan (Pisah)", "🔍 Cek Per Orang"])

# --- MENU UPLOAD ---
if menu == "🏠 Upload Data Excel":
    st.title("📥 Upload & Sinkronisasi")
    st.info("Tips: Tambahkan kolom 'Metode Bayar' di Excel. Isi dengan 'Sendiri' jika anggota bayar tunai.")
    
    uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = [c.strip() for c in df.columns]
            
            if st.button("🚀 PROSES DATA"):
                # 1. UPDATE ANGGOTA
                anggota_batch = []
                seen = set()
                for _, row in df.iterrows():
                    nm = str(row.get('Nama', 'Tanpa Nama')).strip()
                    no = str(row.get('No. Anggota', '-')).strip()
                    if f"{no}-{nm}" not in seen and nm != 'nan':
                        anggota_batch.append({"no_anggota": no, "nama": nm})
                        seen.add(f"{no}-{nm}")
                
                supabase.table("anggota").delete().neq("id", 0).execute()
                if anggota_batch:
                    for i in range(0, len(anggota_batch), 100):
                        supabase.table("anggota").insert(anggota_batch[i:i+100]).execute()
                
                # 2. UPDATE PINJAMAN
                supabase.table("rekap_final").delete().neq("id", 0).execute()
                pinjaman_batch = []
                bln_list = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
                
                def get_val(r, k):
                    for x in k:
                        for c in df.columns:
                            if x.lower() == c.lower(): return r[c]
                    return 0
                
                # Cari kolom metode bayar
                def get_metode(r):
                    for c in df.columns:
                        if c.lower() in ['metode bayar', 'keterangan', 'cara bayar']:
                            val = str(r[c]).lower()
                            if 'sendiri' in val or 'tunai' in val: return 'SENDIRI'
                    return 'KANTOR' # Default

                for _, row in df.iterrows():
                    try:
                        plafon = bersihkan_angka(get_val(row, ['Plafon']))
                        val_sebelum = bersihkan_angka(get_val(row, ['Sebelum th 2026', 'Sebelum']))
                        
                        if val_sebelum > 0: saldo = val_sebelum
                        else: saldo = plafon
                        
                        bayar = 0; cnt = 0
                        for b in bln_list:
                            v = bersihkan_angka(get_val(row, [b]))
                            if v > 0: bayar += v; cnt += 1
                        
                        sisa = saldo - bayar
                        if sisa < 0: sisa = 0
                        
                        # DETEKSI CARA BAYAR
                        jenis = get_metode(row)
                        
                        pinjaman_batch.append({
                            "no_anggota": str(row.get('No. Anggota', '-')),
                            "nama": str(row.get('Nama', 'Tanpa Nama')),
                            "plafon": plafon,
                            "tanggal_pinjam": perbaiki_tanggal(row.get('Tanggal Pinjaman', '-')),
                            "saldo_awal_tahun": saldo,
                            "total_angsuran_tahun_ini": bayar,
                            "sisa_akhir": sisa,
                            "bulan_berjalan": cnt,
                            "jenis_bayar": jenis # Kolom Baru
                        })
                    except: pass
                
                if pinjaman_batch:
                    for i in range(0, len(pinjaman_batch), 100):
                        supabase.table("rekap_final").insert(pinjaman_batch[i:i+100]).execute()
                
                st.success("✅ Data Berhasil Diupdate! Sistem sudah memisahkan 'Kantor' vs 'Sendiri'.")
                
        except Exception as e: st.error(f"Error: {e}")

# --- MENU TAGIHAN (PISAH TAB) ---
elif menu == "💰 Buat Tagihan (Pisah)":
    st.title("💰 Rekap Tagihan Bulanan")
    
    # Ambil Data
    res_agg = supabase.table("anggota").select("*").order("nama").execute()
    list_agg = res_agg.data if res_agg.data else []
    
    res_pinj = supabase.table("rekap_final").select("*").gt("sisa_akhir", 0).execute()
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
            metode = 'KANTOR' # Default kalau tidak punya hutang, dianggap kantor (potong gaji untuk wajib)
            
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
        
        # TAMPILAN TAB
        tab1, tab2 = st.tabs(["🏢 Tagihan ke KANTOR", "👤 Tagihan SETOR SENDIRI"])
        
        with tab1:
            st.subheader("📋 Daftar Potong Gaji (Diserahkan ke Bendahara)")
            if data_kantor:
                df1 = pd.DataFrame(data_kantor)
                st.dataframe(df1.style.format({"wajib":"Rp {:,.0f}", "pokok":"Rp {:,.0f}", "jasa":"Rp {:,.0f}", "total_bayar":"Rp {:,.0f}"}))
                st.download_button("🖨️ Download PDF (Untuk Kantor)", buat_pdf_tagihan(df1, "DAFTAR POTONGAN GAJI PEGAWAI"), "Tagihan_Kantor.pdf", "application/pdf", type="primary")
            else: st.info("Tidak ada data tagihan kantor.")
            
        with tab2:
            st.subheader("📋 Daftar Penagihan Manual (Pegangan Ibu)")
            st.warning("Anggota ini TIDAK dimasukkan ke laporan kantor. Ibu harus menagih sendiri.")
            if data_sendiri:
                df2 = pd.DataFrame(data_sendiri)
                st.dataframe(df2.style.format({"wajib":"Rp {:,.0f}", "pokok":"Rp {:,.0f}", "jasa":"Rp {:,.0f}", "total_bayar":"Rp {:,.0f}"}))
                st.download_button("🖨️ Download PDF (Manual)", buat_pdf_tagihan(df2, "DAFTAR TAGIHAN SETOR MANDIRI"), "Tagihan_Mandiri.pdf", "application/pdf")
            else: st.info("Tidak ada anggota yang setor sendiri.")
            
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
                badge_color = "orange" if jenis == 'SENDIRI' else "blue"
                
                st.markdown(f"""
                <div style="border:1px solid #ddd; padding:15px; border-radius:10px; color:black;">
                    <div style="display:flex; justify-content:space-between;">
                        <h4>{item['nama']}</h4>
                        <span style="background:{badge_color}; color:white; padding:2px 8px; border-radius:4px;">BAYAR: {jenis}</span>
                    </div>
                    <p>Sisa Pinjaman: <b>{format_rupiah(item['sisa_akhir'])}</b></p>
                    <hr>
                    <b>Tagihan Bulan Ini:</b> {format_rupiah(total)}
                </div>
                """, unsafe_allow_html=True)
