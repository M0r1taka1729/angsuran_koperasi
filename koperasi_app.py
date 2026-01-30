import streamlit as st
from supabase import create_client
import pandas as pd
from fpdf import FPDF
from datetime import datetime, timedelta

# ==========================================
# 1. KONEKSI DATABASE
# ==========================================
st.set_page_config(page_title="Aplikasi Koperasi", page_icon="📒", layout="wide")

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

# FUNGSI PERBAIKAN TANGGAL (46050 -> 20-01-2026)
def perbaiki_tanggal(nilai):
    if pd.isna(nilai) or str(nilai).strip() in ['', '-']: return "-"
    try:
        # Jika format angka Excel (Serial Date)
        if isinstance(nilai, (int, float)) or (isinstance(nilai, str) and nilai.isdigit()):
            return (datetime(1899, 12, 30) + timedelta(days=float(nilai))).strftime("%d-%m-%Y")
        # Jika format tanggal standard
        return pd.to_datetime(nilai).strftime("%d-%m-%Y")
    except:
        return str(nilai) # Kembalikan apa adanya jika gagal

# ==========================================
# 2. FUNGSI CETAK PDF
# ==========================================
def buat_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    
    # KOP
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "KOPERASI SIMPAN PINJAM", ln=True, align='C')
    pdf.set_font("Arial", size=10); pdf.cell(0, 10, "Laporan Status Sisa Pinjaman Anggota", ln=True, align='C')
    pdf.line(10, 25, 200, 25); pdf.ln(10)
    
    # INFO
    pdf.set_font("Arial", size=11)
    def baris(lbl, val):
        pdf.cell(40, 8, lbl, 0); pdf.cell(5, 8, ":", 0); pdf.cell(0, 8, str(val), 0, 1)

    baris("Nama Anggota", data['nama'])
    baris("No. Anggota", data['no_anggota'])
    baris("Tanggal Pinjam", data['tanggal_pinjam'])
    baris("Plafon Awal", format_rupiah(data['plafon']))
    pdf.ln(5)
    
    # TABEL
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 11)
    pdf.cell(110, 10, "KETERANGAN", 1, 0, 'C', True); pdf.cell(80, 10, "NOMINAL", 1, 1, 'C', True)
    
    pdf.set_font("Arial", size=11)
    pdf.cell(110, 10, "Saldo Awal Perhitungan", 1); pdf.cell(80, 10, format_rupiah(data['saldo_awal_tahun']), 1, 1, 'R')
    pdf.cell(110, 10, f"Total Angsuran Tahun Ini ({data['bulan_berjalan']} Bulan)", 1); pdf.cell(80, 10, format_rupiah(data['total_angsuran_tahun_ini']), 1, 1, 'R')
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(110, 12, "SISA PINJAMAN", 1); pdf.cell(80, 12, format_rupiah(data['sisa_akhir']), 1, 1, 'R')
    
    # TTD
    pdf.ln(15); pdf.set_font("Arial", size=10)
    pdf.cell(120); pdf.cell(70, 6, "Dicetak: " + datetime.now().strftime("%d-%m-%Y"), 0, 1, 'C')
    pdf.ln(20); pdf.cell(120); pdf.cell(70, 6, "( Bendahara )", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. MENU UTAMA
# ==========================================
menu = st.sidebar.radio("Menu", ["🏠 Cari & Cetak", "📥 Upload Data Excel"])

if menu == "📥 Upload Data Excel":
    st.title("📥 Upload Data Excel")
    st.warning("⚠️ Pastikan nama kolom Excel SAMA PERSIS dengan: `No. Anggota`, `Nama`, `Plafon`, `Tanggal Pinjaman`, `Sebelum th 2026`, `Jan`, `Feb`...")
    
    uploaded_file = st.file_uploader("Upload File Excel (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            # Hapus spasi di nama kolom excel biar aman
            df.columns = [c.strip() for c in df.columns]
            
            st.write("Preview Data:", df.head(3))
            
            if st.button("🚀 PROSES DAN SIMPAN (REPLACE)"):
                progress = st.progress(0)
                
                # 1. HAPUS SEMUA DATA LAMA
                supabase.table("rekap_final").delete().neq("id", 0).execute()
                
                data_batch = []
                # List Bulan Wajib
                list_bln = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
                
                for index, row in df.iterrows():
                    try:
                        # Ambil Data (Pakai nama kolom persis dari request Anda)
                        no_anggota = str(row.get('No. Anggota', '-'))
                        nama = str(row.get('Nama', 'Tanpa Nama'))
                        
                        # Perbaikan Tanggal (46050 -> 20-01-2026)
                        tgl_mentah = row.get('Tanggal Pinjaman')
                        tgl_fix = perbaiki_tanggal(tgl_mentah)
                        
                        plafon = bersihkan_angka(row.get('Plafon', 0))
                        
                        # LOGIKA UTAMA: SISA LAMA VS BARU
                        val_sebelum = bersihkan_angka(row.get('Sebelum th 2026', 0))
                        
                        if val_sebelum > 0:
                            # Ada sisa lama
                            saldo_basis = val_sebelum
                        else:
                            # Tidak ada sisa lama -> ANGGAP BARU -> PAKAI PLAFON
                            saldo_basis = plafon
                            
                        # Hitung Angsuran
                        total_bayar = 0
                        bulan_jalan = 0
                        for bln in list_bln:
                            if bln in df.columns: # Cek jika kolom bulan ada
                                nilai = bersihkan_angka(row.get(bln, 0))
                                if nilai > 0:
                                    total_bayar += nilai
                                    bulan_jalan += 1
                        
                        sisa = saldo_basis - total_bayar
                        if sisa < 0: sisa = 0

                        data_batch.append({
                            "no_anggota": no_anggota,
                            "nama": nama,
                            "plafon": plafon,
                            "tanggal_pinjam": tgl_fix,
                            "saldo_awal_tahun": saldo_basis,
                            "total_angsuran_tahun_ini": total_bayar,
                            "sisa_akhir": sisa,
                            "bulan_berjalan": bulan_jalan
                        })
                    except: pass
                    
                # Simpan ke DB
                if data_batch:
                    # Pecah per 100 data
                    for i in range(0, len(data_batch), 100):
                        supabase.table("rekap_final").insert(data_batch[i:i+100]).execute()
                        
                st.success(f"✅ SUKSES! {len(data_batch)} data tersimpan.")
                
        except Exception as e:
            st.error(f"Error: {e}")

elif menu == "🏠 Cari & Cetak":
    st.title("🖨️ Cetak Kartu Pinjaman")
    cari = st.text_input("🔍 Cari Nama Anggota:")
    
    if cari:
        # Urut ID desc agar data terbaru muncul paling atas
        res = supabase.table("rekap_final").select("*").ilike("nama", f"%{cari}%").order("id", desc=True).execute()
        
        if res.data:
            st.success(f"Ditemukan {len(res.data)} data.")
            for item in res.data:
                # Logika Tampilan Lunas
                # Jika sisa < 1000 rupiah dianggap lunas (toleransi koma)
                is_lunas = item['sisa_akhir'] < 1000 
                warna = "green" if is_lunas else "#d93025"
                bg = "#e6fffa" if is_lunas else "#fff5f5"
                status_text = "✅ LUNAS" if is_lunas else "⚠️ BELUM LUNAS"

                with st.container():
                    st.markdown(f"""
                    <div style="border:1px solid {warna}; padding:15px; border-radius:10px; background:{bg}; margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between;">
                            <h4 style="margin:0;">{item['nama']} ({item['no_anggota']})</h4>
                            <small style="color:#555;">Tgl: {item['tanggal_pinjam']}</small>
                        </div>
                        <hr style="border-top: 1px dashed {warna};">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <small>Sisa Pinjaman:</small><br>
                                <span style="font-size:20px; font-weight:bold; color:{warna}">{format_rupiah(item['sisa_akhir'])}</span>
                            </div>
                            <div style="border:1px solid {warna}; color:{warna}; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:12px;">
                                {status_text}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.download_button(
                        "📄 Download PDF", 
                        buat_pdf(item), 
                        f"{item['nama']}.pdf", 
                        "application/pdf", 
                        key=f"btn_{item['id']}"
                    )
        else:
            st.warning("Tidak ditemukan.")
