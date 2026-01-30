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

def bersihkan_angka(nilai):
    # Ubah input menjadi angka murni (float)
    if pd.isna(nilai): return 0
    str_val = str(nilai).strip()
    if str_val in ['', '-', 'nan', 'Nan', '#N/A']: return 0
    
    # Hapus karakter sampah
    str_val = str_val.replace('Rp', '').replace('.', '').replace(' ', '').replace(',', '.')
    try:
        return float(str_val)
    except:
        return 0

# ==========================================
# 2. FUNGSI CETAK PDF
# ==========================================
def buat_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    
    # KOP SURAT
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "KOPERASI SIMPAN PINJAM", ln=True, align='C')
    pdf.set_font("Arial", size=10); pdf.cell(0, 10, "Laporan Status Sisa Pinjaman Anggota", ln=True, align='C')
    pdf.line(10, 25, 200, 25); pdf.ln(10)
    
    # INFO ANGGOTA
    pdf.set_font("Arial", size=11)
    def baris_info(label, isi):
        pdf.cell(40, 8, label, 0); pdf.cell(5, 8, ":", 0); pdf.cell(0, 8, str(isi), 0, 1)

    baris_info("Nama Anggota", data['nama'])
    baris_info("No. Anggota", data['no_anggota'])
    baris_info("Tanggal Pinjam", data['tanggal_pinjam'])
    baris_info("Plafon Awal", format_rupiah(data['plafon']))
    pdf.ln(5)
    
    # TABEL RINCIAN
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 11)
    pdf.cell(110, 10, "KETERANGAN", 1, 0, 'C', True); pdf.cell(80, 10, "NOMINAL", 1, 1, 'C', True)
    pdf.set_font("Arial", size=11)
    
    # Baris 1: Saldo Awal
    pdf.cell(110, 10, "Saldo Awal (Pinjaman Baru / Sisa Lama)", 1)
    pdf.cell(80, 10, format_rupiah(data['saldo_awal_tahun']), 1, 1, 'R')
    
    # Baris 2: Angsuran
    pdf.cell(110, 10, f"Total Angsuran Tahun Ini ({data['bulan_berjalan']} Bulan)", 1)
    pdf.cell(80, 10, format_rupiah(data['total_angsuran_tahun_ini']), 1, 1, 'R')
    
    # Baris 3: Sisa Akhir
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(110, 12, "SISA PINJAMAN SAAT INI", 1)
    pdf.cell(80, 12, format_rupiah(data['sisa_akhir']), 1, 1, 'R')
    
    # TTD
    pdf.ln(15); pdf.set_font("Arial", size=10)
    pdf.cell(120); pdf.cell(70, 6, "Dicetak: " + datetime.now().strftime("%d-%m-%Y"), 0, 1, 'C')
    pdf.cell(120); pdf.cell(70, 6, "Bendahara,", 0, 1, 'C')
    pdf.ln(20); pdf.cell(120); pdf.cell(70, 6, "( ..................................... )", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. MENU UTAMA
# ==========================================
menu = st.sidebar.radio("Menu", ["🏠 Cari & Cetak", "📥 Upload Data Excel"])

# --- MENU UPLOAD ---
if menu == "📥 Upload Data Excel":
    st.title("📥 Upload Data Excel")
    st.warning("Pastikan nama kolom di Excel: `Nama`, `No. Anggota`, `Plafon`, `Tanggal Pinjaman`, `Sebelum th 2026`.")
    
    uploaded_file = st.file_uploader("Pilih File Excel (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            
            # 1. BERSIHKAN NAMA KOLOM (Hapus spasi di depan/belakang nama kolom)
            df.columns = [c.strip() for c in df.columns]
            
            # 2. CARI KOLOM PENTING (Biar gak error kalau beda huruf besar/kecil)
            def cari_kolom(keyword_list):
                for col in df.columns:
                    if col.lower() in [k.lower() for k in keyword_list]: return col
                return None

            col_nama = cari_kolom(['Nama', 'Nama Anggota'])
            col_no = cari_kolom(['No. Anggota', 'No Anggota', 'Nomor'])
            col_plafon = cari_kolom(['Plafon', 'Jumlah Pinjaman'])
            col_sebelum = cari_kolom(['Sebelum th 2026', 'Sebelum', 'Saldo Awal'])
            col_tgl = cari_kolom(['Tanggal Pinjaman', 'Tgl', 'Tanggal'])
            
            # Preview Data
            st.write("Data Excel Terbaca:")
            preview_data = []
            
            kolom_bulan = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
            
            for index, row in df.iterrows():
                try:
                    # Ambil Data Mentah
                    nama = str(row.get(col_nama, 'Tanpa Nama'))
                    no_anggota = str(row.get(col_no, '-'))
                    tgl_pinjam = str(row.get(col_tgl, '-'))
                    
                    # Ambil Angka Penting
                    plafon = bersihkan_angka(row.get(col_plafon, 0))
                    val_sebelum = bersihkan_angka(row.get(col_sebelum, 0))
                    
                    # ====================================================
                    # 🔥 LOGIKA PERBAIKAN (SESUAI REQUEST) 🔥
                    # ====================================================
                    # Jika kolom 'Sebelum th 2026' isinya > 0, berarti Sisa Lama.
                    # Jika kolom 'Sebelum th 2026' isinya 0, berarti Pinjaman Baru -> AMBIL PLAFON.
                    
                    if val_sebelum > 0:
                        saldo_basis = val_sebelum
                        keterangan = "Sisa Lama"
                    else:
                        # Ini yang memperbaiki masalah Pak Endang tadi
                        saldo_basis = plafon 
                        keterangan = "Baru (Ambil Plafon)"
                    # ====================================================
                    
                    # Hitung Angsuran Jan-Des
                    total_angsuran = 0
                    bulan_jalan = 0
                    for bln in kolom_bulan:
                        found_col = cari_kolom([bln])
                        if found_col:
                            bayar = bersihkan_angka(row[found_col])
                            if bayar > 0:
                                total_angsuran += bayar
                                bulan_jalan += 1
                    
                    sisa = saldo_basis - total_angsuran
                    if sisa < 0: sisa = 0

                    preview_data.append({
                        "no_anggota": no_anggota,
                        "nama": nama,
                        "plafon": plafon,
                        "tanggal_pinjam": tgl_pinjam,
                        "saldo_awal_tahun": saldo_basis,
                        "total_angsuran_tahun_ini": total_angsuran,
                        "sisa_akhir": sisa,
                        "bulan_berjalan": bulan_jalan,
                        "keterangan": keterangan
                    })
                except: pass

            # TAMPILKAN TABEL CEK
            df_preview = pd.DataFrame(preview_data)
            st.subheader("🧐 Cek Hasil Perhitungan Sistem")
            st.dataframe(df_preview[['nama', 'plafon', 'saldo_awal_tahun', 'sisa_akhir', 'keterangan']])
            
            if st.button("🚀 Simpan ke Database"):
                progress = st.progress(0)
                
                # Hapus Data Lama
                supabase.table("rekap_final").delete().neq("id", 0).execute()
                
                # Simpan Data Baru
                data_fix = df_preview.drop(columns=['keterangan']).to_dict('records')
                chunk_size = 100
                
                for i in range(0, len(data_fix), chunk_size):
                    chunk = data_fix[i:i+chunk_size]
                    supabase.table("rekap_final").insert(chunk).execute()
                    
                st.success(f"Sukses! {len(data_fix)} data berhasil diperbarui.")
                st.balloons()
                
        except Exception as e:
            st.error(f"Error membaca Excel: {e}")

# --- MENU CARI ---
elif menu == "🏠 Cari & Cetak":
    st.title("🖨️ Cetak Kartu Pinjaman")
    cari = st.text_input("🔍 Cari Nama:", placeholder="Contoh: Endang")
    
    if cari:
        # Cari di Database
        res = supabase.table("rekap_final").select("*").ilike("nama", f"%{cari}%").order("id", desc=True).execute()
        
        if res.data:
            st.success(f"Ditemukan {len(res.data)} data.")
            for item in res.data:
                # Warna Warni Status
                is_lunas = item['sisa_akhir'] <= 100
                warna = "green" if is_lunas else "#d93025"
                bg = "#f0fdf4" if is_lunas else "#fff5f5"
                label = "✅ LUNAS" if is_lunas else "⚠️ BELUM LUNAS"
                
                with st.container():
                    st.markdown(f"""
                    <div style="border:1px solid {warna}; padding:15px; border-radius:10px; background:{bg}; margin-bottom:10px;">
                        <h4 style="margin:0;">{item['nama']} ({item['no_anggota']})</h4>
                        <p style="margin:0; font-size:14px; color:gray;">Tgl Pinjam: {item['tanggal_pinjam']}</p>
                        <hr style="margin:5px 0; border-top: 1px dashed {warna};">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <small>Sisa Pinjaman:</small><br>
                                <span style="font-weight:bold; font-size:20px; color:{warna};">{format_rupiah(item['sisa_akhir'])}</span>
                            </div>
                            <div style="font-weight:bold; color:{warna}; border:1px solid {warna}; padding:2px 8px; border-radius:5px; font-size:12px;">
                                {label}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.download_button(
                        label="📄 Download PDF", 
                        data=buat_pdf(item), 
                        file_name=f"{item['nama']}.pdf", 
                        mime="application/pdf", 
                        key=f"btn_{item['id']}"
                    )
        else:
            st.warning("Tidak ditemukan.")
