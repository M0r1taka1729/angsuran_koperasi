import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import io

# ==========================================
# 1. KONFIGURASI
# ==========================================
st.set_page_config(page_title="Rekap Pinjaman Koperasi", page_icon="🖨️")

try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("⚠️ Database belum terkoneksi.")
    st.stop()

def format_rupiah(angka):
    return f"Rp {angka:,.0f}".replace(",", ".")

# --- FUNGSI MEMBERSIHKAN ANGKA EXCEL ---
def bersihkan_angka(nilai):
    if pd.isna(nilai) or str(nilai).strip() in ['-', '', 'nan']:
        return 0
    if isinstance(nilai, (int, float)):
        return float(nilai)
    # Hapus Rp, Titik, Spasi
    str_val = str(nilai).replace('Rp', '').replace('.', '').replace(' ', '')
    str_val = str_val.replace(',', '.') # Ganti koma jadi titik desimal
    try:
        return float(str_val)
    except:
        return 0

# --- FUNGSI MEMBUAT PDF ---
def buat_pdf_sisa(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # 1. KOP SURAT
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="KOPERASI SIMPAN PINJAM", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt="Laporan Status Pinjaman Anggota", ln=True, align='C')
    pdf.line(10, 30, 200, 30) # Garis bawah kop
    pdf.ln(15)
    
    # 2. DATA ANGGOTA
    pdf.set_font("Arial", size=12)
    pdf.cell(50, 10, txt="Nomor Anggota", border=0)
    pdf.cell(5, 10, txt=":", border=0)
    pdf.cell(0, 10, txt=str(data['no_anggota']), ln=True)
    
    pdf.cell(50, 10, txt="Nama Anggota", border=0)
    pdf.cell(5, 10, txt=":", border=0)
    pdf.cell(0, 10, txt=str(data['nama']), ln=True)
    
    pdf.cell(50, 10, txt="Tanggal Cetak", border=0)
    pdf.cell(5, 10, txt=":", border=0)
    pdf.cell(0, 10, txt=datetime.now().strftime("%d-%m-%Y"), ln=True)
    pdf.ln(10)
    
    # 3. TABEL RINCIAN (Kotak)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(100, 10, txt="Keterangan", border=1)
    pdf.cell(90, 10, txt="Nominal", border=1, ln=True, align='R')
    
    pdf.set_font("Arial", size=12)
    
    # Baris 1: Plafon (Info)
    pdf.cell(100, 10, txt="Plafon Pinjaman Awal", border=1)
    pdf.cell(90, 10, txt=format_rupiah(data['plafon']), border=1, ln=True, align='R')
    
    # Baris 2: Saldo Awal Tahun
    pdf.cell(100, 10, txt="Sisa Hutang (Awal Tahun)", border=1)
    pdf.cell(90, 10, txt=format_rupiah(data['saldo_awal_tahun']), border=1, ln=True, align='R')
    
    # Baris 3: Angsuran Berjalan
    pdf.cell(100, 10, txt=f"Total Angsuran Tahun Ini ({data['bulan_berjalan']}x Bayar)", border=1)
    pdf.cell(90, 10, txt=format_rupiah(data['total_angsuran']), border=1, ln=True, align='R')
    
    # Baris 4: SISA AKHIR (Bold)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_fill_color(230, 230, 230) # Warna abu-abu
    pdf.cell(100, 15, txt="SISA PINJAMAN SAAT INI", border=1, fill=True)
    pdf.cell(90, 15, txt=format_rupiah(data['sisa_pinjaman']), border=1, ln=True, align='R', fill=True)
    
    # 4. Tanda Tangan
    pdf.ln(20)
    pdf.set_font("Arial", size=10)
    pdf.cell(120) # Geser ke kanan
    pdf.cell(70, 10, txt="Mengetahui, Bendahara", ln=True, align='C')
    pdf.ln(20)
    pdf.cell(120)
    pdf.cell(70, 10, txt="( ...................................... )", ln=True, align='C')

    # Return PDF sebagai bytes
    return bytes(pdf.output())

# ==========================================
# 2. MENU APLIKASI
# ==========================================
menu = st.sidebar.radio("Menu", ["🏠 Cari & Cetak Data", "📥 Update Data dari Excel"])

# --- MENU 1: CARI DAN CETAK ---
if menu == "🏠 Cari & Cetak Data":
    st.title("🖨️ Cetak Info Sisa Pinjaman")
    
    # Kotak Pencarian
    keyword = st.text_input("🔍 Cari Nama / No Anggota:", placeholder="Ketik nama...")
    
    if keyword:
        # Cari di Database
        res = supabase.table("rekap_pinjaman").select("*").or_(f"nama.ilike.%{keyword}%,no_anggota.ilike.%{keyword}%").execute()
        
        if res.data:
            st.write(f"Ditemukan {len(res.data)} data:")
            
            for item in res.data:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        st.write(f"**{item['nama']}**")
                        st.caption(f"No: {item['no_anggota']}")
                    with c2:
                        st.metric("Sisa Pinjaman", format_rupiah(item['sisa_pinjaman']))
                    with c3:
                        # TOMBOL CETAK PDF
                        pdf_data = buat_pdf_sisa(item)
                        st.download_button(
                            label="🖨️ Cetak PDF",
                            data=pdf_data,
                            file_name=f"Sisa_Pinjaman_{item['nama']}.pdf",
                            mime="application/pdf",
                            type="primary"
                        )
        else:
            st.warning("Data tidak ditemukan.")

# --- MENU 2: IMPORT EXCEL ---
elif menu == "📥 Update Data dari Excel":
    st.title("📥 Update Database")
    st.info("Upload Excel terbaru untuk memperbarui data sisa pinjaman seluruh anggota.")
    
    uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.write("Preview Data:", df.head(3))
        
        if st.button("🚀 Mulai Sinkronisasi"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Hapus data lama dulu (Supaya bersih dan tidak duplikat)
            # Karena supabase-py limit delete, kita pakai cara 'delete all' sederhana
            # (Hati-hati: ini akan mengosongkan tabel rekap_pinjaman lalu isi ulang)
            supabase.table("rekap_pinjaman").delete().neq("id", 0).execute() 
            
            total_rows = len(df)
            data_to_insert = []
            
            for index, row in df.iterrows():
                try:
                    # 1. BACA DATA DASAR
                    no_agg = str(row['No. Anggota']).strip()
                    nama = str(row['Nama']).strip()
                    plafon = bersihkan_angka(row.get('Plafon', 0))
                    
                    # 2. HITUNG SALDO AWAL (Kolom 'sebelum th 2026')
                    saldo_awal = bersihkan_angka(row.get('sebelum th 2026', 0))
                    
                    # 3. HITUNG ANGSURAN (Jan - Des)
                    # Otomatis cari kolom bulan yang ada angkanya
                    total_bayar = 0
                    bulan_count = 0
                    list_bulan = ['jan', 'feb', 'mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
                    
                    for bln in list_bulan:
                        if bln in df.columns:
                            val = bersihkan_angka(row[bln])
                            if val > 0:
                                total_bayar += val
                                bulan_count += 1
                    
                    # 4. HITUNG SISA
                    # Rumus Ibu: Sisa = Saldo Awal (Hutang) - Total Bayar Tahun Ini
                    sisa = saldo_awal - total_bayar
                    if sisa < 0: sisa = 0 # Mencegah minus
                    
                    # Siapkan data untuk disimpan
                    data_to_insert.append({
                        "no_anggota": no_agg,
                        "nama": nama,
                        "plafon": plafon,
                        "saldo_awal_tahun": saldo_awal,
                        "total_angsuran": total_bayar,
                        "sisa_pinjaman": sisa,
                        "bulan_berjalan": bulan_count
                    })
                    
                except Exception as e:
                    print(f"Skip baris {index}: {e}")
                
                progress_bar.progress((index + 1) / total_rows)
            
            # 5. MASUKKAN KE SUPABASE (Batch Insert biar cepat)
            if data_to_insert:
                # Insert per 100 baris agar tidak error jika data banyak
                chunk_size = 100
                for i in range(0, len(data_to_insert), chunk_size):
                    chunk = data_to_insert[i:i+chunk_size]
                    supabase.table("rekap_pinjaman").insert(chunk).execute()
            
            status_text.success(f"✅ Selesai! Data {len(data_to_insert)} anggota berhasil diperbarui.")
