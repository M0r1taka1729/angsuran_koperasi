import streamlit as st
from supabase import create_client
import pandas as pd
from fpdf import FPDF
import io
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
    if pd.isna(nilai) or str(nilai).strip() in ['', 'nan', 'Nan', '#N/A', '-']: return 0
    if isinstance(nilai, (int, float)): return float(nilai)
    str_val = str(nilai).replace('Rp', '').replace('.', '').replace(' ', '').replace(',', '.')
    try: return float(str_val)
    except: return 0

# --- FUNGSI PINTAR: UBAH TANGGAL EXCEL (46050 -> 2026) ---
def normalisasi_tanggal(nilai):
    if pd.isna(nilai) or str(nilai).strip() in ['-', '']:
        return datetime.now().date(), 2026 # Default hari ini
    
    try:
        # Cek jika formatnya angka Excel (misal: 46050)
        if isinstance(nilai, (int, float)) or (isinstance(nilai, str) and nilai.isdigit()):
            serial = float(nilai)
            # Rumus konversi angka excel ke python date
            tgl = datetime(1899, 12, 30) + timedelta(days=serial)
            return tgl.date(), tgl.year
        
        # Cek jika formatnya string tanggal (2026-01-20)
        tgl = pd.to_datetime(nilai).date()
        return tgl, tgl.year
    except:
        return datetime.now().date(), 2026

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
    def baris_info(label, isi):
        pdf.cell(40, 8, label, 0); pdf.cell(5, 8, ":", 0); pdf.cell(0, 8, str(isi), 0, 1)

    baris_info("Nama Anggota", data['nama'])
    baris_info("No. Anggota", data['no_anggota'])
    baris_info("Tanggal Pinjam", data['tanggal_pinjam'])
    baris_info("Plafon Awal", format_rupiah(data['plafon']))
    pdf.ln(5)
    
    # TABEL
    pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 11)
    pdf.cell(110, 10, "KETERANGAN", 1, 0, 'C', True); pdf.cell(80, 10, "NOMINAL", 1, 1, 'C', True)
    pdf.set_font("Arial", size=11)
    
    pdf.cell(110, 10, "Saldo Awal (Pinjaman Baru / Sisa Lama)", 1)
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
    pdf.ln(20); pdf.cell(120); pdf.cell(70, 6, "( ..................................... )", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. MENU UTAMA
# ==========================================
menu = st.sidebar.radio("Menu", ["🏠 Cari & Cetak", "📥 Upload Data Excel"])

if menu == "📥 Upload Data Excel":
    st.title("📥 Upload Data Excel")
    st.info("Logika Baru: Jika Tahun Pinjam >= 2026, sistem otomatis memakai PLAFON sebagai Saldo Awal.")
    
    uploaded_file = st.file_uploader("Pilih File Excel (.xlsx)", type=['xlsx'])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = [c.strip() for c in df.columns]
            
            def cari_kolom(kunci):
                for c in df.columns:
                    if c.lower() in [k.lower() for k in kunci]: return c
                return None

            col_plafon = cari_kolom(['Plafon', 'jumlah pinjaman'])
            col_sebelum = cari_kolom(['Sebelum th 2026', 'sebelum'])
            col_tgl = cari_kolom(['Tanggal Pinjaman', 'tgl'])
            
            preview_list = []
            kolom_bulan = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Ags', 'Sep', 'Okt', 'Nov', 'Des']
            
            for index, row in df.iterrows():
                try:
                    nama = str(row.get('Nama', 'Tanpa Nama'))
                    no_agg = str(row.get('No. Anggota', '-'))
                    
                    # 1. CEK TANGGAL (PENTING!)
                    raw_tgl = row.get(col_tgl)
                    obj_tgl, tahun_pinjam = normalisasi_tanggal(raw_tgl)
                    str_tgl = obj_tgl.strftime("%d-%m-%Y") # Format jadi cantik
                    
                    plafon = bersihkan_angka(row.get(col_plafon, 0))
                    val_sebelum = bersihkan_angka(row.get(col_sebelum, 0))
                    
                    # ====================================================
                    # 🔥 LOGIKA SAKTI: BEDAKAN LAMA VS BARU BY TAHUN
                    # ====================================================
                    if tahun_pinjam >= 2026:
                        # Jika Pinjaman Tahun 2026 (Baru) -> Pakai Plafon
                        saldo_basis = plafon
                        ket = "Pinjaman Baru 2026"
                    else:
                        # Jika Pinjaman Lama (< 2026) -> Pakai kolom Sisa Excel
                        saldo_basis = val_sebelum
                        ket = "Sisa Lama"
                    # ====================================================
                    
                    # Hitung Angsuran
                    total_angsuran = 0
                    bulan_jalan = 0
                    for bln in kolom_bulan:
                        found = cari_kolom([bln])
                        if found:
                            bayar = bersihkan_angka(row[found])
                            if bayar > 0:
                                total_angsuran += bayar
                                bulan_jalan += 1
                    
                    sisa = saldo_basis - total_angsuran
                    if sisa < 0: sisa = 0

                    preview_list.append({
                        "no_anggota": no_agg, "nama": nama, "plafon": plafon,
                        "tanggal_pinjam": str_tgl,
                        "saldo_awal_tahun": saldo_basis,
                        "total_angsuran_tahun_ini": total_angsuran,
                        "sisa_akhir": sisa,
                        "bulan_berjalan": bulan_jalan,
                        "keterangan": ket
                    })
                except Exception: pass

            st.subheader("🧐 Cek Hasil Deteksi")
            st.warning("Perhatikan kolom **Keterangan**. Farhan yang baru harusnya 'Pinjaman Baru 2026'.")
            
            df_prev = pd.DataFrame(preview_list)
            st.dataframe(df_prev[['nama', 'tanggal_pinjam', 'plafon', 'sisa_akhir', 'keterangan']])
            
            if st.button("✅ Data Benar, Simpan!"):
                progress_bar = st.progress(0)
                supabase.table("rekap_final").delete().neq("id", 0).execute()
                
                chunk = 100
                data_save = df_prev.drop(columns=['keterangan']).to_dict('records')
                for i in range(0, len(data_save), chunk):
                    supabase.table("rekap_final").insert(data_save[i:i+chunk]).execute()
                    
                st.success(f"Sukses! {len(data_save)} data tersimpan.")
                st.balloons()
                
        except Exception as e: st.error(f"Error: {e}")

elif menu == "🏠 Cari & Cetak":
    st.title("🖨️ Cetak Kartu Pinjaman")
    cari = st.text_input("🔍 Cari Nama:", placeholder="Ketik nama...")
    
    if cari:
        # Urutkan ID desc agar yang baru diatas
        res = supabase.table("rekap_final").select("*").ilike("nama", f"%{cari}%").order("id", desc=True).execute()
        if res.data:
            st.success(f"Ditemukan {len(res.data)} data.")
            for item in res.data:
                is_lunas = item['sisa_akhir'] <= 100
                warna = "green" if is_lunas else "#d93025"
                bg = "#e6fffa" if is_lunas else "#ffeceb"
                label = "✅ LUNAS" if is_lunas else "⚠️ BELUM LUNAS"
                
                with st.container():
                    st.markdown(f"""
                    <div style="border:1px solid {warna}; padding:15px; border-radius:10px; background:{bg}; margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between;">
                            <h4 style="margin:0;">{item['nama']} ({item['no_anggota']})</h4>
                            <span style="font-size:12px; font-weight:bold; color:#555;">Tgl: {item['tanggal_pinjam']}</span>
                        </div>
                        <hr style="margin:5px 0; border-top: 1px dashed {warna};">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <small>Sisa Pinjaman:</small><br>
                                <span style="font-weight:bold; font-size:20px; color:{warna};">{format_rupiah(item['sisa_akhir'])}</span>
                            </div>
                            <div style="text-align:right; font-weight:bold; color:{warna}; border:1px solid {warna}; padding:2px 8px; border-radius:5px; font-size:12px;">
                                {label}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.download_button("📄 Download PDF", buat_pdf(item), f"{item['nama']}.pdf", "application/pdf", key=f"btn_{item['id']}")
        else: st.warning("Tidak ditemukan.")
