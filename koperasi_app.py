import streamlit as st
from supabase import create_client
import pandas as pd
from fpdf import FPDF
from datetime import datetime, timedelta

# ==========================================
# 1. KONEKSI & FUNGSI BANTUAN
# ==========================================
st.set_page_config(page_title="Sistem Koperasi & Tagihan", page_icon="🏦", layout="wide")

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

def perbaiki_tanggal(nilai):
    if pd.isna(nilai) or str(nilai).strip() in ['', '-']: return "-"
    try:
        if isinstance(nilai, (int, float)) or (isinstance(nilai, str) and nilai.isdigit()):
            return (datetime(1899, 12, 30) + timedelta(days=float(nilai))).strftime("%d-%m-%Y")
        return pd.to_datetime(nilai).strftime("%d-%m-%Y")
    except: return str(nilai)

# ==========================================
# 2. PDF LAPORAN GABUNGAN (Landscape)
# ==========================================
def buat_pdf_tagihan(df):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    
    # KOP
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "REKAPITULASI TAGIHAN KOPERASI", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Periode: {datetime.now().strftime('%B %Y')}", ln=True, align='C')
    pdf.line(10, 25, 285, 25)
    pdf.ln(10)
    
    # HEADER
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(220, 230, 240)
    
    # Lebar Kolom
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
        
        # Kolom Total Bold
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(w_total, 8, format_rupiah(row['total_bayar']), 1, 1, 'R')
        pdf.set_font("Arial", size=9)
        
        total_all += row['total_bayar']
        no += 1
        
    # FOOTER TOTAL
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(w_no+w_nama+w_wajib+w_pokok+w_jasa, 12, "GRAND TOTAL SETORAN:", 1, 0, 'R')
    pdf.set_fill_color(255, 255, 0)
    pdf.cell(w_total, 12, format_rupiah(total_all), 1, 1, 'R', True)
    
    # TTD
    pdf.ln(15); pdf.set_font("Arial", size=10)
    pdf.cell(200); pdf.cell(70, 6, f"Bengkulu, {datetime.now().strftime('%d-%m-%Y')}", 0, 1, 'C')
    pdf.ln(20); pdf.cell(200); pdf.cell(70, 6, "( Bendahara )", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. MENU UTAMA
# ==========================================
menu = st.sidebar.radio("Navigasi", ["🏠 Upload Data Excel", "💰 Buat Tagihan", "🔍 Cek Per Orang"])

# ------------------------------------------
# MENU 1: UPLOAD (Update Anggota & Pinjaman)
# ------------------------------------------
if menu == "🏠 Upload Data Excel":
    st.title("📥 Upload & Sinkronisasi Data")
    st.info("Upload Excel untuk memperbarui data Pinjaman sekaligus Data Anggota.")
    
    uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = [c.strip() for c in df.columns] # Bersihkan spasi
            st.write("Preview:", df.head(3))
            
            if st.button("🚀 PROSES DATA"):
                progress = st.progress(0)
                
                # 1. UPDATE TABEL ANGGOTA (Agar Daftar Nama Lengkap untuk Simpanan Wajib)
                anggota_batch = []
                seen_anggota = set()
                
                # Kita ambil nama & no anggota unik dari Excel
                for _, row in df.iterrows():
                    nama = str(row.get('Nama', 'Tanpa Nama')).strip()
                    no = str(row.get('No. Anggota', '-')).strip()
                    key = f"{no}-{nama}"
                    
                    if key not in seen_anggota and nama != 'nan':
                        anggota_batch.append({"no_anggota": no, "nama": nama})
                        seen_anggota.add(key)
                
                # Upsert ke tabel anggota (Hapus dulu biar bersih/update)
                # Note: Idealnya upsert, tapi biar simpel kita delete all insert all untuk master anggota
                supabase.table("anggota").delete().neq("id", 0).execute()
                if anggota_batch:
                    for i in range(0, len(anggota_batch), 100):
                        supabase.table("anggota").insert(anggota_batch[i:i+100]).execute()
                
                # 2. UPDATE TABEL PINJAMAN (REKAP_FINAL)
                supabase.table("rekap_final").delete().neq("id", 0).execute()
                
                pinjaman_batch = []
                bln_list = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
                
                # Helper cari kolom
                def get_val(r, keys):
                    for k in keys:
                        for c in df.columns:
                            if k.lower() == c.lower(): return r[c]
                    return 0

                for _, row in df.iterrows():
                    try:
                        plafon = bersihkan_angka(get_val(row, ['Plafon']))
                        val_sebelum = bersihkan_angka(get_val(row, ['Sebelum th 2026', 'Sebelum']))
                        
                        # LOGIKA SALDO
                        if val_sebelum > 0: saldo = val_sebelum
                        else: saldo = plafon
                        
                        # Hitung Bayar
                        bayar = 0; cnt = 0
                        for b in bln_list:
                            v = bersihkan_angka(get_val(row, [b]))
                            if v > 0: bayar += v; cnt += 1
                        
                        sisa = saldo - bayar
                        if sisa < 0: sisa = 0
                        
                        pinjaman_batch.append({
                            "no_anggota": str(row.get('No. Anggota', '-')),
                            "nama": str(row.get('Nama', 'Tanpa Nama')),
                            "plafon": plafon,
                            "tanggal_pinjam": perbaiki_tanggal(row.get('Tanggal Pinjaman', '-')),
                            "saldo_awal_tahun": saldo,
                            "total_angsuran_tahun_ini": bayar,
                            "sisa_akhir": sisa,
                            "bulan_berjalan": cnt
                        })
                    except: pass
                
                if pinjaman_batch:
                    for i in range(0, len(pinjaman_batch), 100):
                        supabase.table("rekap_final").insert(pinjaman_batch[i:i+100]).execute()
                
                st.success("✅ Data Anggota & Pinjaman Berhasil Diperbarui!")
                st.balloons()
                
        except Exception as e: st.error(f"Error: {e}")

# ------------------------------------------
# MENU 2: TAGIHAN GABUNGAN (FITUR UTAMA)
# ------------------------------------------
elif menu == "💰 Buat Tagihan":
    st.title("💰 Rekap Tagihan Bulanan")
    st.markdown("""
    **Sistem akan menghitung 2 Komponen Tagihan:**
    1. **Simpanan Wajib:** Rp 150.000 (Untuk SEMUA nama di tabel Anggota).
    2. **Pinjaman:** (Plafon / 10) + Jasa 1% (Hanya untuk yang punya hutang di tabel Pinjaman).
    """)
    
    # 1. Ambil Semua Anggota (Untuk Simpanan Wajib)
    res_anggota = supabase.table("anggota").select("*").order("nama").execute()
    list_anggota = res_anggota.data if res_anggota.data else []
    
    # 2. Ambil Data Pinjaman (Untuk Angsuran & Jasa)
    res_pinjaman = supabase.table("rekap_final").select("*").gt("sisa_akhir", 0).execute()
    # Buat dictionary biar gampang dicari: { "Nama Anggota": DataPinjaman }
    dict_pinjaman = { item['nama'].strip().lower(): item for item in res_pinjaman.data } if res_pinjaman.data else {}
    
    if list_anggota:
        laporan_final = []
        
        for agg in list_anggota:
            nama_asli = agg['nama']
            nama_key = nama_asli.strip().lower()
            
            # A. HITUNG SIMPANAN WAJIB (Semua kena)
            tagihan_wajib = 150000
            
            # B. HITUNG PINJAMAN (Cek apakah dia punya hutang)
            if nama_key in dict_pinjaman:
                data_pinjam = dict_pinjaman[nama_key]
                plafon = data_pinjam['plafon']
                
                # Rumus Ibu: Tenor 10 bulan + Jasa 1%
                angsuran_pokok = plafon / 10
                jasa_koperasi = plafon * 0.01
            else:
                angsuran_pokok = 0
                jasa_koperasi = 0
            
            # C. TOTAL
            total = tagihan_wajib + angsuran_pokok + jasa_koperasi
            
            laporan_final.append({
                "nama": nama_asli,
                "wajib": tagihan_wajib,
                "pokok": angsuran_pokok,
                "jasa": jasa_koperasi,
                "total_bayar": total
            })
            
        # Tampilkan Tabel
        df_lap = pd.DataFrame(laporan_final)
        
        # Format tampilan biar cantik
        st.dataframe(df_lap.style.format({
            "wajib": "Rp {:,.0f}",
            "pokok": "Rp {:,.0f}",
            "jasa": "Rp {:,.0f}",
            "total_bayar": "Rp {:,.0f}"
        }))
        
        # Info Total Setoran
        total_duit = df_lap['total_bayar'].sum()
        st.success(f"💰 Total Uang Masuk ke Bendahara Bulan Ini: **{format_rupiah(total_duit)}**")
        
        # Download PDF
        st.download_button(
            label="🖨️ Cetak Laporan Tagihan (PDF Landscape)",
            data=buat_pdf_tagihan(df_lap),
            file_name="Laporan_Tagihan_Gabungan.pdf",
            mime="application/pdf",
            type="primary"
        )
        
    else:
        st.warning("Data Anggota Kosong. Silakan Upload Excel dulu di menu Upload.")

# ------------------------------------------
# MENU 3: CEK INDIVIDU
# ------------------------------------------
elif menu == "🔍 Cek Per Orang":
    st.title("🔍 Cek Kartu Pinjaman")
    cari = st.text_input("Ketik Nama:")
    
    if cari:
        res = supabase.table("rekap_final").select("*").ilike("nama", f"%{cari}%").execute()
        if res.data:
            for item in res.data:
                pokok = item['plafon'] / 10
                jasa = item['plafon'] * 0.01
                total_bln = pokok + jasa + 150000 # Termasuk wajib
                
                st.markdown(f"""
                <div style="border:1px solid #ccc; padding:15px; border-radius:10px; margin-bottom:10px; color:black;">
                    <h4>{item['nama']}</h4>
                    <p>Plafon: {format_rupiah(item['plafon'])} | Sisa: <b>{format_rupiah(item['sisa_akhir'])}</b></p>
                    <hr>
                    <b>Rincian Tagihan Bulan Ini:</b>
                    <ul>
                        <li>Simpanan Wajib: Rp 150.000</li>
                        <li>Angsuran Pokok: {format_rupiah(pokok)}</li>
                        <li>Jasa (1%): {format_rupiah(jasa)}</li>
                        <li><b>TOTAL: {format_rupiah(total_bln)}</b></li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("Tidak ditemukan data pinjaman untuk nama tersebut.")
