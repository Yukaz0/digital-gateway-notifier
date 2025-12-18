import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

// =================================================================
// --- KOMPONEN BARU: Halaman Login & Register ---
// =================================================================
const AuthPage = ({ onLoginSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (isLogin) {
      // --- Proses Login ---
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      try {
        const response = await fetch('/api/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData,
        });

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || 'Username atau password salah.');
        }

        const data = await response.json();
        onLoginSuccess(data.access_token);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    } else {
      // --- Proses Register ---
      try {
        const response = await fetch('/api/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || 'Gagal mendaftar.');
        }

        // Setelah berhasil register, arahkan untuk login
        alert('Registrasi berhasil! Silakan login.');
        setIsLogin(true);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-form-wrapper">
        <h2>{isLogin ? 'Login Dashboard Gateway Digital' : 'Registrasi Akun Baru'}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" className="auth-button" disabled={loading}>
            {loading ? 'Memproses...' : (isLogin ? 'Login' : 'Register')}
          </button>
        </form>
        <p className="auth-toggle">
          {isLogin ? "Belum punya akun? " : "Sudah punya akun? "}
          <span onClick={() => setIsLogin(!isLogin)}>
            {isLogin ? 'Register di sini' : 'Login di sini'}
          </span>
        </p>
      </div>
    </div>
  );
};


// =================================================================
// --- Komponen Modal (untuk Tambah & Edit Pelanggan) - FIXED ---
// =================================================================
const Modal = ({ show, mode, onClose, onSubmit, currentData, setCurrentData }) => {
  const isEditMode = mode === 'edit';
  const classes = [1, 2, 3, 4]; // Opsi kelas notifikasi

  // FIX: Pindahkan Hook ke atas sebelum return kondisional untuk mematuhi Rules of Hooks
  useEffect(() => {
    // Pastikan kelas_notifikasi selalu berupa array
    if (currentData && !Array.isArray(currentData.kelas_notifikasi)) {
      // Jika data lama adalah single number, ubah ke array
      setCurrentData(prev => ({ ...prev, kelas_notifikasi: prev.kelas_notifikasi ? [prev.kelas_notifikasi] : [] }));
    } else if (currentData && currentData.kelas_notifikasi === undefined) {
      // Jika belum ada kelas_notifikasi, inisialisasi sebagai array kosong
      setCurrentData(prev => ({ ...prev, kelas_notifikasi: [] }));
    }
  }, [currentData, setCurrentData]);


  if (!show) {
    return null;
  }

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;

    if (name === "kelas_notifikasi") {
      // Handle perubahan checkbox untuk kelas notifikasi
      const kelasValue = parseInt(value, 10);
      setCurrentData(prev => {
        const currentKelasNotifikasi = prev.kelas_notifikasi || []; // Pastikan ini array
        let newKelasNotifikasi;
        if (checked) {
          // Tambahkan kelas jika belum ada
          newKelasNotifikasi = [...currentKelasNotifikasi, kelasValue].sort((a,b) => a-b);
        } else {
          // Hapus kelas jika ada
          newKelasNotifikasi = currentKelasNotifikasi.filter(k => k !== kelasValue);
        }
        return { ...prev, kelas_notifikasi: newKelasNotifikasi };
      });
    } else {
      // Handle perubahan input lainnya (nomor_hp, nama, whatsapp, telegram)
      setCurrentData(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    }
  };


  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>{isEditMode ? 'Edit Pelanggan' : 'Tambah Pelanggan Baru'}</h2>
        <form onSubmit={onSubmit}>
          <div className="form-group">
            <label>Nomor HP (Wajib, format: +62...)</label>
            <input type="text" name="nomor_hp" value={currentData?.nomor_hp || ''} onChange={handleChange} placeholder="+6281234567890" required disabled={isEditMode} />
          </div>
          <div className="form-group">
            <label>Nama</label>
            <input type="text" name="nama" value={currentData?.nama || ''} onChange={handleChange} placeholder="Nama Lengkap" />
          </div>

          <div className="form-group">
            <label>Pilih Kelas Notifikasi:</label>
            <div className="checkbox-options">
              {classes.map(kelas => (
                <label key={kelas}>
                  <input
                    type="checkbox"
                    name="kelas_notifikasi"
                    value={kelas}
                    checked={currentData?.kelas_notifikasi?.includes(kelas) || false}
                    onChange={handleChange}
                  />
                  Kelas {kelas}
                </label>
              ))}
            </div>
          </div>

          <div className="form-group-checkbox">
            <label>Preferensi Notifikasi:</label>
            <div className="checkbox-options">
              <label><input type="checkbox" name="whatsapp" checked={currentData?.whatsapp || false} onChange={handleChange} /> WhatsApp</label>
              <label><input type="checkbox" name="telegram" checked={currentData?.telegram || false} onChange={handleChange} /> Telegram</label>
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" onClick={onClose} className="btn-cancel">Batal</button>
            <button type="submit" className="btn-submit">Simpan</button>
          </div>
        </form>
      </div>
    </div>
  );
};

// =================================================================
// --- Komponen Log Notifikasi Real-Time - TIDAK BERUBAH ---
// =================================================================
const NotificationLog = ({ logs }) => {
  return (
    <div className="log-container">
      <h2>Log Notifikasi Real-Time</h2>
      <div className="log-feed">
        {logs.length === 0 && <p className="log-empty">Menunggu notifikasi baru...</p>}
        {logs.map((log, index) => (
          <div key={index} className="log-item">
            <span className="log-time">{new Date(log.time).toLocaleTimeString('id-ID')}</span>
            <span className={`log-channel log-channel-${log.channel.toLowerCase()}`}>{log.channel}</span>
            <span className="log-message">Pesan terkirim ke {log.recipient}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// =================================================================
// --- Komponen Utama App - TIDAK BERUBAH ---
// =================================================================
function App() {
  const [token, setToken] = useState(localStorage.getItem('accessToken'));
  const [pelanggan, setPelanggan] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add');
  const [currentPelanggan, setCurrentPelanggan] = useState(null);
  const [notificationLogs, setNotificationLogs] = useState([]);

  const API_URL = '/api/pelanggan';
  const WS_URL = `ws://${window.location.host}/api/ws/notifications`;

  const initialFormState = {
    nama: '', nomor_hp: '', kelas_notifikasi: [],
    whatsapp: false, telegram: false, sms: false,
  };

  const fetchPelanggan = useCallback(async () => {
    if (!token) {
      setLoading(false); // Pastikan loading berhenti jika tidak ada token
      return;
    }
    try {
      setLoading(true);
      const response = await fetch(API_URL, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.status === 401) {
        handleLogout();
        throw new Error('Sesi Anda telah berakhir. Silakan login kembali.');
      }
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data = await response.json();
      setPelanggan(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchPelanggan();
  }, [fetchPelanggan]);

  useEffect(() => {
    if (!token) return; // Jangan hubungkan WebSocket jika tidak login

    const connectWebSocket = () => {
      const ws = new WebSocket(WS_URL);
      ws.onopen = () => console.log('Terhubung ke WebSocket Notifikasi');
      ws.onmessage = (event) => {
        try {
          const newLog = JSON.parse(event.data);
          setNotificationLogs(prevLogs => [newLog, ...prevLogs.slice(0, 9)]);
        } catch (error) {
          console.error("Gagal parsing pesan WebSocket:", error);
        }
      };
      ws.onclose = () => {
        console.log('Terputus dari WebSocket Notifikasi, mencoba terhubung kembali dalam 5 detik...');
        setTimeout(connectWebSocket, 5000);
      };
      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        ws.close();
      };
      return () => ws.close();
    };

    const cleanup = connectWebSocket();
    return cleanup;
  }, [WS_URL, token]);

  const handleLoginSuccess = (newToken) => {
    localStorage.setItem('accessToken', newToken);
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('accessToken');
    setToken(null);
  };

  const handleOpenAddModal = () => {
    setModalMode('add');
    setCurrentPelanggan(initialFormState);
    setModalOpen(true);
  };

  const handleOpenEditModal = (p) => {
    setModalMode('edit');
    setCurrentPelanggan({
      ...p,
      kelas_notifikasi: Array.isArray(p.kelas_notifikasi) ? p.kelas_notifikasi : (p.kelas_notifikasi ? [p.kelas_notifikasi] : [])
    });
    setModalOpen(true);
  };

  const handleCloseModal = () => {
    setModalOpen(false);
    setCurrentPelanggan(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const url = modalMode === 'add' ? API_URL : `${API_URL}/${currentPelanggan.nomor_hp}`;
    const method = modalMode === 'add' ? 'POST' : 'PUT';

    try {
      const response = await fetch(url, {
        method: method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(currentPelanggan),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Gagal ${modalMode === 'add' ? 'menambahkan' : 'mengupdate'} pic.`);
      }
      fetchPelanggan();
      handleCloseModal();
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleDelete = async (nomorHp) => {
    if (window.confirm(`Apakah Anda yakin ingin menghapus pic dengan nomor HP ${nomorHp}?`)) {
      try {
        const response = await fetch(`${API_URL}/${nomorHp}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Gagal menghapus pelanggan.');
        }
        fetchPelanggan();
      } catch (err) {
        alert(`Error: ${err.message}`);
      }
    }
  };

  if (!token) {
    return <AuthPage onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Dashboard PIC Notifikasi</h1>
        <div>
          <button className="add-button" onClick={handleOpenAddModal}>+ Tambah PIC</button>
          <button className="logout-button" onClick={handleLogout}>Logout</button>
        </div>
      </header>

      <div className="main-layout">
        <div className="pelanggan-section">
          <main className="app-main">
            {loading && <p className="loading-text">Memuat data PIC...</p>}
            {error && <p className="error-text">Gagal memuat data: {error}</p>}
            {!loading && !error && (
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Nama</th>
                      <th>Nomor HP</th>
                      <th className="kelas">Kelas</th>
                      <th className="notifikasi">Notifikasi Aktif</th>
                      <th className="aksi-header">Aksi</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pelanggan.map((p) => (
                      <tr key={p.id}>
                        <td>{p.nama || '-'}</td>
                        <td>{p.nomor_hp}</td>
                        <td className="kelas">
                          {(Array.isArray(p.kelas_notifikasi) ? p.kelas_notifikasi : (p.kelas_notifikasi ? [p.kelas_notifikasi] : [])).join(', ')}
                        </td>
                        <td className="notifikasi">
                          <div className="checkbox-display">
                            <div className="checkbox-item" title="WhatsApp">
                              <span>WA</span>
                              <input type="checkbox" checked={p.whatsapp} readOnly />
                            </div>
                            <div className="checkbox-item" title="Telegram">
                              <span>TG</span>
                              <input type="checkbox" checked={p.telegram} readOnly />
                            </div>
                          </div>
                        </td>
                        <td className="actions-cell">
                          <div className="button-group">
                            <button className="action-button btn-edit" onClick={() => handleOpenEditModal(p)}>Edit</button>
                            <button className="action-button btn-delete" onClick={() => handleDelete(p.nomor_hp)}>Hapus</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </main>
        </div>
        <div className="log-section">
          <NotificationLog logs={notificationLogs} />
        </div>
      </div>

      {isModalOpen && (
        <Modal
          show={isModalOpen}
          mode={modalMode}
          onClose={handleCloseModal}
          onSubmit={handleSubmit}
          currentData={currentPelanggan}
          setCurrentData={setCurrentPelanggan}
        />
      )}
    </div>
  );
}

export default App;