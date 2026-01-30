import streamlit as st
from supabase import create_client
import pandas as pd
from fpdf import FPDF
from datetime import datetime, timedelta

# ==========================================
# 1. KONFIGURASI & DATABASE
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
# 2. PDF: LAPORAN TAGIHAN KOLEKTIF (BENDAHARA)
# ==========================================
def buat_pdf_tagihan(df_tagihan):
    pdf = FPDF(orientation='L', unit='mm', format='A4') # Landscape
    pdf.add_page()
    
    # KOP
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "KOPERASI SIMPAN PINJAM - LAPORAN TAGIHAN", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    bulan_ini = datetime.now().strftime("%B %Y")
    pdf.cell(0, 10, f"Daftar Potongan Gaji Anggota - Periode {bulan_ini}", ln=True, align='C')
    pdf.line(10, 25, 285, 25)
    pdf.ln(10)
    
    # HEADER TABEL
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(200, 220, 255)
    
    # Definisi Lebar Kolom (Total sktr 275mm)
    w_no=10; w_nama=60; w_pokok=35; w_jasa=35; w_tot_pinj=40; w_wajib=35; w_total=60
    
    pdf.cell(w_no, 10, "No", 1, 0, 'C', True)
    pdf.cell(w_nama, 10, "Nama Anggota", 1, 0, 'C', True)
    pdf.cell(w_pokok, 10, "Angsuran Pokok", 1, 0, 'C', True)
    pdf.cell(w_jasa, 10, "Jasa (1%)", 1, 0, 'C', True)
    pdf.cell(w_tot_pinj, 10, "Subtotal Pinjaman", 1, 0, 'C', True)
    pdf.cell(w_wajib, 10, "Simp. Wajib", 1, 0, 'C', True)
    pdf.cell(w_total, 10, "TOTAL POTONG GAJI", 1, 1, 'C', True)
    
    # ISI TABEL
    pdf.set_font("Arial", size=9)
    no = 1
    grand_total = 0
    
    for _, row in df_tagihan.iterrows():
        pdf.cell(w_no, 8, str(no), 1, 0, 'C')
        pdf.cell(w_nama, 8, str(row['nama'])[:25], 1, 0, 'L') # Potong nama biar ga panjang
        pdf.cell(w_pokok, 8, format_rupiah(row['pokok']), 1, 0, 'R')
        pdf.cell(w_jasa, 8, format_rupiah(row['jasa']), 1, 0, 'R')
        pdf.cell(w_tot_pinj, 8, format_rupiah(row['total_pinjaman']), 1, 0, 'R')
        pdf.cell(w_wajib, 8, format_rupiah(row['wajib']), 1, 0, 'R')
        
        # Kolom Total (Bold)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(w_total, 8, format_rupiah(row['total_tagihan']), 1, 1, 'R')
        pdf.set_font("Arial", size=9) # Balikin normal
        
        grand_total += row['total_tagihan']
        no += 1
        
    # TOTAL AKHIR
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(w_no+w_nama+w_pokok+w_jasa+w_tot_pinj+w_wajib, 12, "GRAND TOTAL YANG HARUS DISETOR:", 1, 0, 'R')
    pdf.set_fill_color(255, 255, 0) # Kuning
    pdf.cell(w_total, 12, format_rupiah(grand_total), 1, 1, 'R', True)
    
    # TTD
    pdf.ln(15); pdf.set_font("Arial", size=10)
    pdf.cell(200); pdf.cell(70, 6, f"Bengkulu, {datetime.now().strftime('%d-%m-%Y')}", 0, 1, 'C')
    pdf.cell(200); pdf.cell(70, 6, "Bendahara Koperasi,", 0, 1, 'C')
    pdf.ln(20)
    pdf.cell(200); pdf.cell(70, 6, "( ..................................... )", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. PDF: KARTU SISA PINJAMAN (INDIVIDU)
# ==========================================
def buat_pdf_individu(data):
    # Hitung ulang rincian untuk ditampilkan di PDF individu
    pokok = data['plafon'] / 10
    jasa = data['plafon'] * 0.01
    wajib = 150000
    total_bln = pokok + jasa + wajib

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "KOPERASI SIMPAN PINJAM", ln=True, align='C')
    pdf.set_font("Arial", size=10); pdf.cell(0, 10, "Kartu Sisa Pinjaman & Rincian Tagihan", ln=True, align='C')
    pdf.line(10, 25, 200, 25); pdf.ln(10)
    
    pdf.set_font("Arial", size=11)
    def baris(lbl, val):
        pdf.cell(50, 8, lbl, 0); pdf.cell(5, 8, ":", 0); pdf.cell(0, 8, str(val), 0, 1)

    baris("Nama Anggota", data['nama'])
    baris("No. Anggota", data['no_anggota'])
    baris("Plafon Pinjaman", format_rupiah(data['plafon']))
    pdf.ln(5)
    
    # TABEL SISA
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "STATUS SISA PINJAMAN", 1, 1, 'C', True)
    
    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, "Saldo Awal Tahun", 1); pdf.cell(90, 8, format_rupiah(data['saldo_awal_tahun']), 1, 1, 'R')
    pdf.cell(100, 8, "Total Angsuran Masuk (Jan-Des)", 1); pdf.cell(90, 8, format_rupiah(data['total_angsuran_tahun_ini']), 1, 1, 'R')
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(100, 10, "SISA PINJAMAN SAAT INI", 1); pdf.cell(90, 10, format_rupiah(data['sisa_akhir']), 1, 1, 'R')
    
    pdf.ln(10)
    
    # TABEL RINCIAN TAGIHAN BULANAN
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "RINCIAN POTONGAN GAJI BULANAN (Tenor 10 Bulan)", 1, 1, 'C', True)
    
    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, "1. Angsuran Pokok (Plafon / 10)", 1); pdf.cell(90, 8, format_rupiah(pokok), 1, 1, 'R')
    pdf.cell(100, 8, "2. Jasa Koperasi (1%)", 1); pdf.cell(90, 8, format_rupiah(jasa), 1, 1, 'R')
    pdf.cell(100, 8, "3. Simpanan Wajib", 1); pdf.cell(90, 8, format_rupiah(wajib), 1, 1, 'R')
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 12, "TOTAL TAGIHAN PER BULAN", 1); pdf.cell(90, 12, format_rupiah(total_bln), 1, 1, 'R')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. MENU UTAMA
# ==========================================
menu = st.sidebar.radio("Menu Utama", ["🏠 Cari & Cetak Kartu", "💰 Tagihan Bendahara", "📥 Upload Data Excel"])

# ------------------------------------------
# MENU 1: UPLOAD (DATA SOURCE)
# ------------------------------------------
if menu == "📥 Upload Data Excel":
    st.title("📥 Upload Data Excel")
    st.info("Upload Excel berisi data Plafon dan Pembayaran Jan-Des.")
    
    uploaded_file = st.file_uploader("Upload File (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = [c.strip() for c in df.columns]
            
            def cari_col(keys):
                for c in df.columns:
                    if c.lower() in [k.lower() for k in keys]: return c
                return None

            c_nama = cari_col(['Nama', 'Nama Anggota'])
            c_no = cari_col(['No. Anggota', 'No'])
            c_plafon = cari_col(['Plafon'])
            c_sebelum = cari_col(['Sebelum th 2026', 'Sebelum'])
            c_tgl = cari_col(['Tanggal Pinjaman', 'Tgl'])
            
            if st.button("🚀 PROSES & SIMPAN DATABASE"):
                progress = st.progress(0)
                supabase.table("rekap_final").delete().neq("id", 0).execute()
                
                batch = []
                bln_list = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
                
                for i, row in df.iterrows():
                    try:
                        plafon = bersihkan_angka(row.get(c_plafon, 0))
                        val_sebelum = bersihkan_angka(row.get(c_sebelum, 0))
                        
                        # LOGIKA SALDO AWAL
                        if val_sebelum > 0: saldo = val_sebelum
                        else: saldo = plafon
                        
                        # LOGIKA ANGSURAN
                        bayar = 0
                        cnt = 0
                        for b in bln_list:
                            c = cari_col([b])
                            if c:
                                val = bersihkan_angka(row[c])
                                if val > 0: bayar += val; cnt += 1
                        
                        sisa = saldo - bayar
                        if sisa < 0: sisa = 0

                        batch.append({
                            "no_anggota": str(row.get(c_no, '-')),
                            "nama": str(row.get(c_nama, 'Tanpa Nama')),
                            "plafon": plafon,
                            "tanggal_pinjam": perbaiki_tanggal(row.get(c_tgl, '-')),
                            "saldo_awal_tahun": saldo,
                            "total_angsuran_tahun_ini": bayar,
                            "sisa_akhir": sisa,
                            "bulan_berjalan": cnt
                        })
                    except: pass
                
                for k in range(0, len(batch), 100):
                    supabase.table("rekap_final").insert(batch[k:k+100]).execute()
                    
                st.success(f"✅ Berhasil import {len(batch)} data.")
        except Exception as e: st.error(str(e))

# ------------------------------------------
# MENU 2: TAGIHAN BENDAHARA (FITUR BARU)
# ------------------------------------------
elif menu == "💰 Tagihan Bendahara":
    st.title("💰 Rekap Tagihan Potong Gaji")
    st.markdown("""
    Halaman ini menghitung otomatis tagihan untuk diserahkan ke Bendahara Kantor.
    * **Angsuran Pokok:** Plafon / 10
    * **Jasa:** Plafon x 1%
    * **Simpanan Wajib:** Rp 150.000
    """)
    
    # Ambil data dari database
    res = supabase.table("rekap_final").select("*").order("nama").execute()
    
    if res.data:
        data_tagihan = []
        for item in res.data:
            # Hanya buat tagihan jika SISA HUTANG MASIH ADA (> 0)
            # ATAU jika Ibu mau semua anggota kena simpanan wajib, hapus if ini.
            # Asumsi: Hanya yang punya pinjaman aktif yang dihitung angsuran, 
            # tapi Simpanan Wajib mungkin untuk semua.
            # Disini saya buat: Jika sisa > 0 hitung angsuran, jika lunas angsuran 0 tapi wajib tetap ada.
            
            sisa = item['sisa_akhir']
            plafon = item['plafon']
            
            if sisa > 100: # Kalau masih punya hutang
                pokok = plafon / 10
                jasa = plafon * 0.01
            else: # Sudah lunas
                pokok = 0
                jasa = 0
            
            wajib = 150000
            total = pokok + jasa + wajib
            
            data_tagihan.append({
                "nama": item['nama'],
                "pokok": pokok,
                "jasa": jasa,
                "total_pinjaman": pokok + jasa,
                "wajib": wajib,
                "total_tagihan": total
            })
            
        df_tagihan = pd.DataFrame(data_tagihan)
        
        # Tampilkan Tabel di Layar
        st.dataframe(df_tagihan.style.format({
            "pokok": "Rp {:,.0f}", 
            "jasa": "Rp {:,.0f}",
            "total_pinjaman": "Rp {:,.0f}",
            "wajib": "Rp {:,.0f}",
            "total_tagihan": "Rp {:,.0f}"
        }))
        
        col1, col2 = st.columns([2,1])
        with col1:
            total_setor = df_tagihan['total_tagihan'].sum()
            st.metric("Total Setoran ke Koperasi Bulan Ini", format_rupiah(total_setor))
            
        with col2:
            pdf_bytes = buat_pdf_tagihan(df_tagihan)
            st.download_button(
                label="🖨️ Download Laporan PDF (Landscape)",
                data=pdf_bytes,
                file_name=f"Tagihan_Bendahara_{datetime.now().strftime('%Y_%m')}.pdf",
                mime="application/pdf",
                type="primary"
            )
    else:
        st.info("Belum ada data anggota. Silakan Upload Excel dulu.")

# ------------------------------------------
# MENU 3: CARI & CETAK KARTU (VISUAL UPDATE)
# ------------------------------------------
elif menu == "🏠 Cari & Cetak Kartu":
    st.title("🖨️ Kartu Sisa Pinjaman")
    cari = st.text_input("🔍 Cari Nama:", placeholder="Ketik nama...")
    
    if cari:
        res = supabase.table("rekap_final").select("*").ilike("nama", f"%{cari}%").order("id", desc=True).execute()
        if res.data:
            for item in res.data:
                # Hitung Rincian untuk ditampilkan di layar
                pokok = item['plafon'] / 10
                jasa = item['plafon'] * 0.01
                tagihan_bln = pokok + jasa + 150000
                
                is_lunas = item['sisa_akhir'] <= 100
                warna = "green" if is_lunas else "#d93025"
                label = "LUNAS" if is_lunas else "AKTIF"
                
                with st.container():
                    st.markdown(f"""
                    <div style="border:1px solid {warna}; padding:15px; border-radius:10px; margin-bottom:10px; color:#333;">
                        <div style="display:flex; justify-content:space-between;">
                            <h4 style="margin:0; color:#000;">{item['nama']}</h4>
                            <span style="background:{warna}; color:white; padding:2px 8px; border-radius:4px; font-size:12px;">{label}</span>
                        </div>
                        <p style="margin:0; font-size:13px; color:#555;">Plafon: {format_rupiah(item['plafon'])} | Tenor 10 Bulan</p>
                        <hr>
                        <div style="display:flex; justify-content:space-between;">
                            <div>
                                <small>Sisa Pinjaman:</small><br>
                                <b style="font-size:18px; color:{warna}">{format_rupiah(item['sisa_akhir'])}</b>
                            </div>
                            <div style="text-align:right;">
                                <small>Tagihan Bulanan (Gaji):</small><br>
                                <b>{format_rupiah(tagihan_bln)}</b>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.download_button("📄 Download PDF", buat_pdf_individu(item), f"{item['nama']}.pdf", "application/pdf", key=f"btn_{item['id']}")
        else: st.warning("Tidak ditemukan.")
