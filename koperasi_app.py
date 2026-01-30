import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
import time

# ==========================================
# 1. KONFIGURASI
# ==========================================
st.set_page_config(page_title="Sistem Koperasi Simpan Pinjam", page_icon="💰", layout="wide")

# Koneksi Database
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("⚠️ Database belum terkoneksi. Cek Secrets Anda.")
    st.stop()

# Fungsi Format Rupiah
def format_rupiah(angka):
    return f"Rp {angka:,.0f}".replace(",", ".")

# ==========================================
# 2. SIDEBAR MENU
# ==========================================
with st.sidebar:
    st.title("💰 Koperasi Jaya")
    st.write("Panel Bendahara")
    menu = st.radio("Menu Utama", [
        "📊 Dashboard",
        "👥 Data Anggota", 
        "📝 Buat Pinjaman Baru", 
        "💸 Bayar Angsuran",
        "📜 Riwayat Transaksi"
    ])

# ==========================================
# 3. FITUR-FITUR
# ==========================================

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Dashboard Keuangan")
    
    # Ambil Statistik
    try:
        # Total Pinjaman Aktif (Outstanding)
        res_pinjaman = supabase.table("pinjaman").select("sisa_tagihan").eq("status", "BERJALAN").execute()
        total_piutang = sum([x['sisa_tagihan'] for x in res_pinjaman.data])
        
        # Total Angsuran Masuk Hari Ini
        today = datetime.now().strftime('%Y-%m-%d')
        res_angsuran = supabase.table("angsuran").select("jumlah_bayar").eq("tanggal_bayar", today).execute()
        uang_masuk_hari_ini = sum([x['jumlah_bayar'] for x in res_angsuran.data])

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Total Piutang (Uang di Anggota)", format_rupiah(total_piutang))
        with c2:
            st.metric("Uang Masuk Hari Ini", format_rupiah(uang_masuk_hari_ini))
            
    except Exception as e:
        st.error(f"Gagal memuat data: {e}")

# --- DATA ANGGOTA ---
elif menu == "👥 Data Anggota":
    st.header("👥 Manajemen Anggota")
    
    tab1, tab2 = st.tabs(["➕ Tambah Anggota", "📋 Daftar Anggota"])
    
    with tab1:
        with st.form("add_member"):
            # Inputan dikurangi, hanya Nama dan No Anggota
            nama = st.text_input("Nama Lengkap")
            no_anggota = st.text_input("Nomor Anggota (Unik)")
            
            if st.form_submit_button("Simpan Anggota"):
                try:
                    # Data yang dikirim ke database hanya 2
                    data = {"nama": nama, "no_anggota": no_anggota}
                    supabase.table("anggota").insert(data).execute()
                    st.success("Anggota berhasil ditambahkan!")
                except Exception as e:
                    st.error(f"Gagal: {e}")

    with tab2:
        res = supabase.table("anggota").select("*").order("nama").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            # Tampilkan tabel yang lebih ringkas
            st.dataframe(df[['no_anggota', 'nama']], use_container_width=True)
        else:
            st.info("Belum ada data anggota.")

# --- BUAT PINJAMAN BARU ---
elif menu == "📝 Buat Pinjaman Baru":
    st.header("📝 Pengajuan Pinjaman")
    
    # Pilih Anggota
    res_anggota = supabase.table("anggota").select("id, nama, no_anggota").execute()
    if not res_anggota.data:
        st.warning("Tambahkan data anggota terlebih dahulu!")
        st.stop()
        
    pilihan_anggota = {f"{m['no_anggota']} - {m['nama']}": m['id'] for m in res_anggota.data}
    pilih = st.selectbox("Pilih Anggota", list(pilihan_anggota.keys()))
    id_anggota = pilihan_anggota[pilih]
    
    with st.form("form_pinjaman"):
        col1, col2 = st.columns(2)
        with col1:
            pokok = st.number_input("Jumlah Pinjaman (Pokok)", min_value=100000, step=50000)
            tenor = st.number_input("Tenor (Bulan)", min_value=1, value=12)
        with col2:
            bunga_persen = st.number_input("Bunga per Bulan (%)", min_value=0.0, value=1.5, step=0.1)
            tgl_cair = st.date_input("Tanggal Pencairan")
            
        # Hitung Simulasi
        total_bunga_rp = int(pokok * (bunga_persen/100) * tenor)
        total_tagihan = pokok + total_bunga_rp
        cicilan_per_bulan = total_tagihan / tenor
        
        st.info(f"""
        **Simulasi:**
        - Total Bunga: {format_rupiah(total_bunga_rp)}
        - Total Harus Dibayar: **{format_rupiah(total_tagihan)}**
        - Angsuran per Bulan: **{format_rupiah(cicilan_per_bulan)}**
        """)
        
        if st.form_submit_button("✅ Setujui & Cairkan Dana"):
            try:
                data_pinjaman = {
                    "anggota_id": id_anggota,
                    "jumlah_pokok": pokok,
                    "bunga_persen": bunga_persen,
                    "tenor_bulan": tenor,
                    "total_tagihan": total_tagihan,
                    "sisa_tagihan": total_tagihan, # Awal pinjam, sisa = total
                    "status": "BERJALAN",
                    "tanggal_pinjam": tgl_cair.isoformat()
                }
                supabase.table("pinjaman").insert(data_pinjaman).execute()
                st.success("Pinjaman berhasil dicatat!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# --- BAYAR ANGSURAN ---
elif menu == "💸 Bayar Angsuran":
    st.header("💸 Input Pembayaran Angsuran")
    
    # 1. Cari Anggota yang punya hutang
    # Query: Join tabel pinjaman & anggota agak kompleks di supabase-py raw, 
    # jadi kita ambil pinjaman aktif dulu lalu filter.
    
    res_active = supabase.table("pinjaman").select("*, anggota(nama, no_anggota)").eq("status", "BERJALAN").execute()
    
    if not res_active.data:
        st.success("Tidak ada pinjaman berjalan. Semua lunas! 🎉")
    else:
        # Mapping data untuk dropdown
        # Format: "NoPinjaman | Nama | Sisa Tagihan"
        opsi_pinjaman = {}
        for p in res_active.data:
            label = f"ID:{p['id']} | {p['anggota']['nama']} | Sisa: {format_rupiah(p['sisa_tagihan'])}"
            opsi_pinjaman[label] = p
            
        pilih_bayar = st.selectbox("Pilih Pinjaman", list(opsi_pinjaman.keys()))
        data_p = opsi_pinjaman[pilih_bayar]
        
        st.write("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Tagihan Awal", format_rupiah(data_p['total_tagihan']))
        c2.metric("Sisa Tagihan", format_rupiah(data_p['sisa_tagihan']))
        estimasi_cicilan = data_p['total_tagihan'] / data_p['tenor_bulan']
        c3.metric("Estimasi Cicilan/Bulan", format_rupiah(estimasi_cicilan))
        
        with st.form("bayar_form"):
            nominal_bayar = st.number_input("Jumlah Bayar", min_value=1000, value=int(estimasi_cicilan), step=1000)
            tgl_bayar = st.date_input("Tanggal Bayar")
            angsuran_ke_input = st.number_input("Angsuran Ke-", min_value=1, value=1)
            catatan = st.text_input("Catatan (Opsional)")
            
            if st.form_submit_button("💾 Simpan Pembayaran"):
                if nominal_bayar > data_p['sisa_tagihan']:
                    st.error("❌ Jumlah bayar melebihi sisa tagihan!")
                else:
                    try:
                        # 1. Catat di tabel angsuran
                        supabase.table("angsuran").insert({
                            "pinjaman_id": data_p['id'],
                            "angsuran_ke": angsuran_ke_input,
                            "jumlah_bayar": nominal_bayar,
                            "tanggal_bayar": tgl_bayar.isoformat(),
                            "catatan": catatan
                        }).execute()
                        
                        # 2. Update sisa tagihan di tabel pinjaman
                        sisa_baru = data_p['sisa_tagihan'] - nominal_bayar
                        status_baru = "LUNAS" if sisa_baru <= 0 else "BERJALAN"
                        
                        supabase.table("pinjaman").update({
                            "sisa_tagihan": sisa_baru,
                            "status": status_baru
                        }).eq("id", data_p['id']).execute()
                        
                        st.success("Pembayaran diterima!")
                        if status_baru == "LUNAS":
                            st.balloons()
                            st.success("🎉 PINJAMAN LUNAS!")
                        
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

# --- RIWAYAT ---
elif menu == "📜 Riwayat Transaksi":
    st.header("📜 Log Transaksi Masuk")
    
    # Ambil data angsuran join dengan pinjaman -> anggota
    # Supabase join syntax: select("*, pinjaman(anggota(nama))")
    res = supabase.table("angsuran").select("*, pinjaman(id, anggota(nama))").order("id", desc=True).limit(50).execute()
    
    if res.data:
        # Rapikan data untuk tabel
        data_tabel = []
        for r in res.data:
            data_tabel.append({
                "Tanggal": r['tanggal_bayar'],
                "Nama Anggota": r['pinjaman']['anggota']['nama'],
                "Ke-": r['angsuran_ke'],
                "Nominal": format_rupiah(r['jumlah_bayar']),
                "Catatan": r['catatan']
            })
        st.table(data_tabel)
    else:
        st.info("Belum ada transaksi.")
