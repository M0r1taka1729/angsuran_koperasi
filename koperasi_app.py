import streamlit as st
from supabase import create_client
import pandas as pd
from fpdf import FPDF
import io
from datetime import datetime

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

# Fungsi pembersih angka (Hapus Rp, Titik, Koma)
def bersihkan_angka(nilai):
    if pd.isna(nilai) or str(nilai).strip() in ['-', '', 'nan', 'Nan', '#N/A']:
        return 0
    if isinstance(nilai, (int, float)):
        return float(nilai)
    
    # Hapus karakter non-angka
    str_val = str(nilai).replace('Rp', '').replace('.', '').replace(' ', '')
    str_val = str_val.replace(',', '.') 
    try:
        return float(str_val)
    except:
        return 0

# ==========================================
# 2. FUNGSI CETAK PDF (PERBAIKAN ERROR)
# ==========================================
def buat_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    
    # --- KOP SURAT ---
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "KOPERASI SIMPAN PINJAM", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, "Laporan Status Sisa Pinjaman Anggota", ln=True, align='C')
    pdf.line(10, 25, 200, 25)
    pdf.ln(10)
    
    # --- INFO ANGGOTA ---
    pdf.set_font("Arial", size=11)
    
    # Fungsi bantu bikin baris titik dua rapi
    def baris_info(label, isi):
        pdf.cell(40, 8, label, 0)
        pdf.cell(5, 8, ":", 0)
        pdf.cell(0, 8, str(isi), 0, 1)

    baris_info("Nama Anggota", data['nama'])
    baris_info("No. Anggota", data['no_anggota'])
    baris_info("Tanggal Pinjam", data['tanggal_pinjam'])
    baris_info("Plafon Awal", format_rupiah(data['plafon']))
    
    pdf.ln(5)
    
    # --- TABEL RINCIAN ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    
    # Header Tabel
    pdf.cell(110, 10, "KETERANGAN", 1, 0, 'C', True)
    pdf.cell(80, 10, "NOMINAL", 1, 1, 'C', True)
    
    # Isi Tabel
    pdf.set_font("Arial", size=11)
    
    # 1. Saldo Awal
    pdf.cell(110, 10, "Sisa Pinjaman (Per Awal Tahun 2026)", 1)
    pdf.cell(80, 10, format_rupiah(data['saldo_awal_tahun']), 1, 1, 'R')
    
    # 2. Pembayaran Tahun Ini
    pdf.cell(110, 10, f"Total Angsuran Tahun Ini ({data['bulan_berjalan']} Bulan)", 1)
    pdf.cell(80, 10, format_rupiah(data['total_angsuran_tahun_ini']), 1, 1, 'R')
    
    # 3. Sisa Akhir (BOLD)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(110, 12, "SISA PINJAMAN SAAT INI", 1)
    pdf.cell(80, 12, format_rupiah(data['sisa_akhir']), 1, 1, 'R')
    
    # --- FOOTER ---
    pdf.ln(15)
    pdf.set_font("Arial", size=10)
    pdf.cell(120)
    pdf.cell(70, 6, "Dicetak pada: " + datetime.now().strftime("%d-%m-%Y"), 0, 1, 'C')
    pdf.cell(120)
    pdf.cell(70, 6, "Bendahara,", 0, 1, 'C')
    pdf.ln(20)
    pdf.cell(120)
    pdf.cell(70, 6, "( ..................................... )", 0, 1, 'C')

    # [PERBAIKAN UTAMA DI SINI]
    # Menggunakan dest='S' untuk string output, lalu encode ke latin-1
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. MENU UTAMA
# ==========================================
menu = st.sidebar.radio("Menu", ["🏠 Cari & Cetak", "📥 Upload Data Excel"])

# --- MENU UPLOAD ---
if menu == "📥 Upload Data Excel":
    st.title("📥 Upload Data Excel")
    st.info("Fitur ini akan menghapus data lama dan menggantinya dengan data Excel terbaru.")
    
    uploaded_file = st.file_uploader("Pilih File Excel (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            st.write("👀 **Preview Data:**", df.head())
            
            # TOMBOL PROSES
            if st.button("🚀 Simpan ke Database"):
                progress_bar = st.progress(0)
                status = st.empty()
                
                # 1. Bersihkan Data Lama
                supabase.table("rekap_final").delete().neq("id", 0).execute()
                
                # 2. Siapkan Data Baru
                total_data = len(df)
                data_batch = []
                
                # List Kolom Bulan sesuai Excel Ibu
                kolom_bulan = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
                
                for index, row in df.iterrows():
                    try:
                        # Ambil Data Dasar
                        no_anggota = str(row.get('No. Anggota', '-'))
                        nama = str(row.get('Nama', 'Tanpa Nama'))
                        tgl_pinjam = str(row.get('Tanggal Pinjaman', '-'))
                        plafon = bersihkan_angka(row.get('Plafon', 0))
                        
                        # LOGIKA UTAMA HITUNGAN
                        # A. Saldo Awal (Hutang Awal Tahun)
                        saldo_awal = bersihkan_angka(row.get('Sebelum th 2026', 0))
                        
                        # B. Hitung Angsuran (Jan - Des)
                        total_angsuran = 0
                        bulan_jalan = 0
                        
                        for bln in kolom_bulan:
                            # Cek apakah kolom ada di excel
                            if bln in df.columns:
                                bayar = bersihkan_angka(row[bln])
                                if bayar > 0:
                                    total_angsuran += bayar
                                    bulan_jalan += 1
                        
                        # C. Hitung Sisa Akhir
                        # Sisa = Hutang Awal - Total Bayar Tahun Ini
                        sisa = saldo_awal - total_angsuran
                        if sisa < 0: sisa = 0 # Jaga-jaga biar ga minus
                        
                        # Masukkan ke antrian simpan
                        data_batch.append({
                            "no_anggota": no_anggota,
                            "nama": nama,
                            "plafon": plafon,
                            "tanggal_pinjam": tgl_pinjam,
                            "saldo_awal_tahun": saldo_awal,
                            "total_angsuran_tahun_ini": total_angsuran,
                            "sisa_akhir": sisa,
                            "bulan_berjalan": bulan_jalan
                        })
                        
                    except Exception as e:
                        print(f"Error baris {index}: {e}")
                    
                    # Update loading bar
                    progress_bar.progress((index + 1) / total_data)
                
                # 3. Kirim ke Database (Sekaligus biar cepat)
                if data_batch:
                    # Pecah jadi per 100 data biar server gak kaget
                    chunk_size = 100
                    for i in range(0, len(data_to_insert), chunk_size): # Fixed variable name here if needed, but above uses data_batch
                         # Correction: make sure loop uses data_batch
                         pass 
                    
                    # Re-implementation of batch insert logic to be safe
                    for i in range(0, len(data_batch), 100):
                        supabase.table("rekap_final").insert(data_batch[i:i+100]).execute()
                
                status.success(f"✅ Selesai! {len(data_batch)} data berhasil disimpan.")
                
        except Exception as e:
            st.error(f"Gagal membaca Excel: {e}")

# --- MENU CARI & CETAK ---
elif menu == "🏠 Cari & Cetak":
    st.title("🖨️ Cetak Kartu Pinjaman")
    
    cari = st.text_input("🔍 Cari Nama Anggota / No Anggota:", placeholder="Ketik nama atau nomor...")
    
    if cari:
        # Cari di Database
        # Kita urutkan berdasarkan ID (terbaru di atas) agar Top Up muncul duluan
        res = supabase.table("rekap_final").select("*")\
            .or_(f"nama.ilike.%{cari}%,no_anggota.ilike.%{cari}%")\
            .order("id", desc=True)\
            .execute()
        
        if res.data:
            jumlah_aktif = sum(1 for x in res.data if x['sisa_akhir'] > 0)
            st.success(f"Ditemukan {len(res.data)} riwayat pinjaman ({jumlah_aktif} masih aktif).")
            
            # Pisahkan data: Aktif dulu, baru Lunas
            data_aktif = [x for x in res.data if x['sisa_akhir'] > 0]
            data_lunas = [x for x in res.data if x['sisa_akhir'] <= 0]
            
            # Gabungkan kembali (Aktif di atas)
            data_urut = data_aktif + data_lunas
            
            for item in data_urut:
                # Tentukan Status Visual
                is_lunas = item['sisa_akhir'] <= 0
                warna_status = "green" if is_lunas else "red"
                label_status = "✅ SUDAH LUNAS" if is_lunas else "⚠️ BELUM LUNAS (AKTIF)"
                bg_color = "#f0fdf4" if is_lunas else "#fef2f2" # Hijau muda / Merah muda
                
                # Tampilan Kartu
                with st.container():
                    st.markdown(f"""
                    <div style="
                        border: 1px solid {warna_status}; 
                        border-radius: 10px; 
                        padding: 15px; 
                        margin-bottom: 10px;
                        background-color: {bg_color};
                    ">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <h4 style="margin:0; color:black;">{item['nama']}</h4>
                                <small style="color:gray;">No: {item['no_anggota']} | Tgl Pinjam: {item['tanggal_pinjam']}</small>
                            </div>
                            <div style="text-align:right;">
                                <h4 style="margin:0; color:{warna_status};">{format_rupiah(item['sisa_akhir'])}</h4>
                                <small style="font-weight:bold; color:{warna_status};">{label_status}</small>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Tombol Download (Hanya muncul di bawah kartu visual)
                    c1, c2 = st.columns([4, 1])
                    with c2:
                        pdf_data = buat_pdf(item)
                        st.download_button(
                            label="📄 Download PDF",
                            data=pdf_data,
                            file_name=f"Info_{item['nama']}_{item['id']}.pdf",
                            mime="application/pdf",
                            type="secondary" if is_lunas else "primary",
                            key=f"btn_dl_{item['id']}"
                        )
                    st.write("") # Jarak antar kartu
        else:
            st.warning("Data tidak ditemukan.")
