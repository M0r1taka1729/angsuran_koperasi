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
    if pd.isna(nilai) or str(nilai).strip() in ['', 'nan', 'Nan', '#N/A', '-']:
        return 0
    if isinstance(nilai, (int, float)):
        return float(nilai)
    str_val = str(nilai).replace('Rp', '').replace('.', '').replace(' ', '').replace(',', '.')
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
    
    # Kop Surat
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "KOPERASI SIMPAN PINJAM", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, "Laporan Status Sisa Pinjaman Anggota", ln=True, align='C')
    pdf.line(10, 25, 200, 25)
    pdf.ln(10)
    
    # Info
    pdf.set_font("Arial", size=11)
    def baris_info(label, isi):
        pdf.cell(40, 8, label, 0)
        pdf.cell(5, 8, ":", 0)
        pdf.cell(0, 8, str(isi), 0, 1)

    baris_info("Nama Anggota", data['nama'])
    baris_info("No. Anggota", data['no_anggota'])
    baris_info("Tanggal Pinjam", data['tanggal_pinjam'])
    baris_info("Plafon Awal", format_rupiah(data['plafon']))
    pdf.ln(5)
    
    # Tabel
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(110, 10, "KETERANGAN", 1, 0, 'C', True)
    pdf.cell(80, 10, "NOMINAL", 1, 1, 'C', True)
    pdf.set_font("Arial", size=11)
    
    # Rincian
    pdf.cell(110, 10, "Saldo Awal (Pinjaman Baru / Sisa Lalu)", 1)
    pdf.cell(80, 10, format_rupiah(data['saldo_awal_tahun']), 1, 1, 'R')
    pdf.cell(110, 10, f"Total Angsuran Tahun Ini ({data['bulan_berjalan']} Bulan)", 1)
    pdf.cell(80, 10, format_rupiah(data['total_angsuran_tahun_ini']), 1, 1, 'R')
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(110, 12, "SISA PINJAMAN SAAT INI", 1)
    pdf.cell(80, 12, format_rupiah(data['sisa_akhir']), 1, 1, 'R')
    
    # TTD
    pdf.ln(15); pdf.set_font("Arial", size=10)
    pdf.cell(120); pdf.cell(70, 6, "Dicetak: " + datetime.now().strftime("%d-%m-%Y"), 0, 1, 'C')
    pdf.cell(120); pdf.cell(70, 6, "Bendahara,", 0, 1, 'C')
    pdf.ln(20)
    pdf.cell(120); pdf.cell(70, 6, "( ..................................... )", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. MENU UTAMA
# ==========================================
menu = st.sidebar.radio("Menu", ["🏠 Cari & Cetak", "📥 Upload Data Excel"])

if menu == "📥 Upload Data Excel":
    st.title("📥 Upload Data Excel")
    st.info("Logika: Jika kolom 'Sebelum th 2026' KOSONG atau 0, maka Saldo Awal = PLAFON.")
    
    uploaded_file = st.file_uploader("Pilih File Excel (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            
            # --- NORMALISASI NAMA KOLOM (Biar Plafon/plafon/PLAFON terbaca) ---
            df.columns = [c.strip() for c in df.columns] # Hapus spasi di nama kolom
            
            # Cari nama kolom yang benar di Excel User
            def cari_kolom(keyword_list):
                for col in df.columns:
                    for key in keyword_list:
                        if key.lower() == col.lower():
                            return col
                return None

            col_plafon = cari_kolom(['Plafon', 'plafon', 'jumlah pinjaman'])
            col_sebelum = cari_kolom(['Sebelum th 2026', 'sebelum', 'sisa lalu'])
            
            # --- PROSES SIMULASI DATA ---
            preview_list = []
            
            kolom_bulan = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
            
            for index, row in df.iterrows():
                try:
                    # Ambil Data
                    nama = str(row.get('Nama', 'Tanpa Nama'))
                    no_anggota = str(row.get('No. Anggota', '-'))
                    tgl = str(row.get('Tanggal Pinjaman', '-'))
                    
                    # Ambil Angka (Aman dari error)
                    plafon = bersihkan_angka(row.get(col_plafon, 0)) if col_plafon else 0
                    val_sebelum = bersihkan_angka(row.get(col_sebelum, 0)) if col_sebelum else 0
                    
                    # === LOGIKA PENENTUAN SALDO ===
                    if val_sebelum > 0:
                        saldo_basis = val_sebelum
                        ket = "Sisa Lama"
                    else:
                        saldo_basis = plafon
                        ket = "Pinjaman Baru (Pakai Plafon)"
                    
                    # Hitung Angsuran
                    total_angsuran = 0
                    bulan_jalan = 0
                    for bln in kolom_bulan:
                        # Cari kolom bulan yg cocok (case insensitive)
                        found_col = cari_kolom([bln])
                        if found_col:
                            bayar = bersihkan_angka(row[found_col])
                            if bayar > 0:
                                total_angsuran += bayar
                                bulan_jalan += 1
                    
                    sisa = saldo_basis - total_angsuran
                    if sisa < 0: sisa = 0

                    preview_list.append({
                        "no_anggota": no_anggota,
                        "nama": nama,
                        "plafon": plafon,
                        "tanggal_pinjam": tgl,
                        "saldo_awal_tahun": saldo_basis,
                        "total_angsuran_tahun_ini": total_angsuran,
                        "sisa_akhir": sisa,
                        "bulan_berjalan": bulan_jalan,
                        "keterangan": ket # Untuk cek preview
                    })
                except Exception as e:
                    pass

            # --- TAMPILKAN TABEL CEK ---
            st.subheader("🧐 Cek Dulu Hasil Perhitungannya")
            st.warning("Perhatikan kolom **'Saldo Awal'** dan **'Sisa Akhir'**. Jika sudah benar, baru klik Simpan.")
            
            df_preview = pd.DataFrame(preview_list)
            # Tampilkan kolom penting saja
            st.dataframe(df_preview[['nama', 'plafon', 'saldo_awal_tahun', 'total_angsuran_tahun_ini', 'sisa_akhir', 'keterangan']])
            
            # --- TOMBOL SIMPAN ---
            if st.button("✅ Data Sudah Benar, Simpan ke Database"):
                progress_bar = st.progress(0)
                
                # Hapus Data Lama
                supabase.table("rekap_final").delete().neq("id", 0).execute()
                
                # Simpan Batch
                chunk_size = 100
                data_to_save = df_preview.drop(columns=['keterangan']).to_dict('records')
                
                for i in range(0, len(data_to_save), chunk_size):
                    chunk = data_to_save[i:i+chunk_size]
                    supabase.table("rekap_final").insert(chunk).execute()
                    
                st.success(f"Sukses! {len(data_to_save)} data berhasil disimpan.")
                st.balloons()
                
        except Exception as e:
            st.error(f"Error: {e}")

elif menu == "🏠 Cari & Cetak":
    st.title("🖨️ Cetak Kartu Pinjaman")
    cari = st.text_input("🔍 Cari Nama:", placeholder="Ketik nama...")
    
    if cari:
        res = supabase.table("rekap_final").select("*").ilike("nama", f"%{cari}%").order("id", desc=True).execute()
        if res.data:
            st.success(f"Ditemukan {len(res.data)} data.")
            for item in res.data:
                is_lunas = item['sisa_akhir'] <= 100
                warna = "green" if is_lunas else "red"
                label = "✅ LUNAS" if is_lunas else "⚠️ BELUM LUNAS"
                bg = "#f0fdf4" if is_lunas else "#fef2f2"
                
                with st.container():
                    st.markdown(f"""
                    <div style="border:1px solid {warna}; padding:15px; border-radius:10px; background:{bg}; margin-bottom:10px;">
                        <h4>{item['nama']} ({item['no_anggota']})</h4>
                        <div style="display:flex; justify-content:space-between;">
                            <span>Sisa Pinjaman:</span>
                            <span style="font-weight:bold; color:{warna}; font-size:18px;">{format_rupiah(item['sisa_akhir'])}</span>
                        </div>
                        <div style="text-align:right; font-weight:bold; color:{warna};">{label}</div>
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
