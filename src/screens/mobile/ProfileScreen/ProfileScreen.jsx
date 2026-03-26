import React, { useState } from 'react';
import { t } from '../../../i18n';
import './ProfileScreen.css';

const ProfileScreen = ({ onBack, onSave, patientData, initialData }) => {
    // Support both prop names for flexibility
    const data = patientData || initialData || {};
    
    const [activeTab, setActiveTab] = useState('biodata');
    const [formData, setFormData] = useState({
        // Biodata
        fullName: data?.fullName || '',
        nik: data?.nik || '',
        birthDate: data?.birthDate || '',
        bloodType: data?.bloodType || '',
        address: data?.address || '',
        phone: data?.phone || '',
        emergencyContact: data?.emergencyContact || '',
        emergencyPhone: data?.emergencyPhone || '',
        
        // Medical Records
        pregnancyWeek: data?.pregnancyWeek || '',
        expectedDueDate: data?.expectedDueDate || '',
        lastMenstrualDate: data?.lastMenstrualDate || '',
        gravida: data?.gravida || '1', // Kehamilan ke-
        para: data?.para || '0', // Jumlah persalinan
        abortus: data?.abortus || '0', // Jumlah keguguran
        height: data?.height || '',
        weightBeforePregnancy: data?.weightBeforePregnancy || '',
        currentWeight: data?.currentWeight || '',
        
        // Medical History
        hasHypertension: data?.hasHypertension || false,
        hasDiabetes: data?.hasDiabetes || false,
        hasHeartDisease: data?.hasHeartDisease || false,
        hasAsthma: data?.hasAsthma || false,
        hasAllergies: data?.hasAllergies || false,
        allergiesDetail: data?.allergiesDetail || '',
        otherConditions: data?.otherConditions || '',
        currentMedications: data?.currentMedications || '',
        
        // Pregnancy History
        previousComplications: data?.previousComplications || '',
        previousDeliveryType: data?.previousDeliveryType || '',
    });

    const [isSaving, setIsSaving] = useState(false);

    const handleInputChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsSaving(true);
        
        // Simulate API call
        setTimeout(() => {
            setIsSaving(false);
            onSave?.(formData);
            alert('Data berhasil disimpan!');
        }, 1500);
    };

    const calculatePregnancyWeek = () => {
        if (!formData.lastMenstrualDate) return '';
        const lmp = new Date(formData.lastMenstrualDate);
        const today = new Date();
        const diffTime = Math.abs(today - lmp);
        const diffWeeks = Math.floor(diffTime / (1000 * 60 * 60 * 24 * 7));
        return diffWeeks;
    };

    const calculateDueDate = () => {
        if (!formData.lastMenstrualDate) return '';
        const lmp = new Date(formData.lastMenstrualDate);
        const dueDate = new Date(lmp);
        dueDate.setDate(dueDate.getDate() + 280); // 40 weeks
        return dueDate.toISOString().split('T')[0];
    };

    return (
        <div className="profile-screen">
            {/* Header */}
            <header className="profile-header">
                <button className="profile-header__back" onClick={onBack}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M19 12H5M12 19l-7-7 7-7" />
                    </svg>
                </button>
                <h1>Profil Pasien</h1>
                <button 
                    className="profile-header__save"
                    onClick={handleSubmit}
                    disabled={isSaving}
                >
                    {isSaving ? 'Menyimpan...' : 'Simpan'}
                </button>
            </header>

            {/* Tabs */}
            <div className="profile-tabs">
                <button 
                    className={`profile-tab ${activeTab === 'biodata' ? 'active' : ''}`}
                    onClick={() => setActiveTab('biodata')}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                    </svg>
                    Biodata
                </button>
                <button 
                    className={`profile-tab ${activeTab === 'pregnancy' ? 'active' : ''}`}
                    onClick={() => setActiveTab('pregnancy')}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 6v6l4 2" />
                    </svg>
                    Kehamilan
                </button>
                <button 
                    className={`profile-tab ${activeTab === 'medical' ? 'active' : ''}`}
                    onClick={() => setActiveTab('medical')}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <path d="M14 2v6h6M12 18v-6M9 15h6" />
                    </svg>
                    Rekam Medis
                </button>
            </div>

            <form className="profile-form" onSubmit={handleSubmit}>
                {/* Biodata Tab */}
                {activeTab === 'biodata' && (
                    <div className="profile-section">
                        <h2 className="profile-section__title">Data Pribadi</h2>
                        
                        <div className="profile-field">
                            <label>Nama Lengkap</label>
                            <input
                                type="text"
                                name="fullName"
                                value={formData.fullName}
                                onChange={handleInputChange}
                                placeholder="Masukkan nama lengkap"
                            />
                        </div>

                        <div className="profile-field">
                            <label>NIK</label>
                            <input
                                type="text"
                                name="nik"
                                value={formData.nik}
                                onChange={handleInputChange}
                                placeholder="16 digit NIK"
                                maxLength="16"
                            />
                        </div>

                        <div className="profile-row">
                            <div className="profile-field">
                                <label>Tanggal Lahir</label>
                                <input
                                    type="date"
                                    name="birthDate"
                                    value={formData.birthDate}
                                    onChange={handleInputChange}
                                />
                            </div>
                            <div className="profile-field">
                                <label>Golongan Darah</label>
                                <select
                                    name="bloodType"
                                    value={formData.bloodType}
                                    onChange={handleInputChange}
                                >
                                    <option value="">Pilih</option>
                                    <option value="A+">A+</option>
                                    <option value="A-">A-</option>
                                    <option value="B+">B+</option>
                                    <option value="B-">B-</option>
                                    <option value="AB+">AB+</option>
                                    <option value="AB-">AB-</option>
                                    <option value="O+">O+</option>
                                    <option value="O-">O-</option>
                                </select>
                            </div>
                        </div>

                        <div className="profile-field">
                            <label>Alamat</label>
                            <textarea
                                name="address"
                                value={formData.address}
                                onChange={handleInputChange}
                                placeholder="Alamat lengkap"
                                rows="3"
                            />
                        </div>

                        <div className="profile-field">
                            <label>Nomor Telepon</label>
                            <input
                                type="tel"
                                name="phone"
                                value={formData.phone}
                                onChange={handleInputChange}
                                placeholder="08xxxxxxxxxx"
                            />
                        </div>

                        <h2 className="profile-section__title">Kontak Darurat</h2>

                        <div className="profile-field">
                            <label>Nama Kontak Darurat</label>
                            <input
                                type="text"
                                name="emergencyContact"
                                value={formData.emergencyContact}
                                onChange={handleInputChange}
                                placeholder="Nama suami/keluarga"
                            />
                        </div>

                        <div className="profile-field">
                            <label>Nomor Telepon Darurat</label>
                            <input
                                type="tel"
                                name="emergencyPhone"
                                value={formData.emergencyPhone}
                                onChange={handleInputChange}
                                placeholder="08xxxxxxxxxx"
                            />
                        </div>
                    </div>
                )}

                {/* Pregnancy Tab */}
                {activeTab === 'pregnancy' && (
                    <div className="profile-section">
                        <h2 className="profile-section__title">Data Kehamilan</h2>

                        <div className="profile-field">
                            <label>Hari Pertama Haid Terakhir (HPHT)</label>
                            <input
                                type="date"
                                name="lastMenstrualDate"
                                value={formData.lastMenstrualDate}
                                onChange={handleInputChange}
                            />
                        </div>

                        <div className="profile-row">
                            <div className="profile-field">
                                <label>Usia Kehamilan (Minggu)</label>
                                <input
                                    type="number"
                                    name="pregnancyWeek"
                                    value={formData.pregnancyWeek || calculatePregnancyWeek()}
                                    onChange={handleInputChange}
                                    placeholder="Otomatis dari HPHT"
                                    min="1"
                                    max="42"
                                />
                                <span className="profile-field__hint">
                                    Dapat diisi manual atau otomatis dari HPHT
                                </span>
                            </div>
                            <div className="profile-field">
                                <label>Taksiran Persalinan</label>
                                <input
                                    type="date"
                                    name="expectedDueDate"
                                    value={formData.expectedDueDate || calculateDueDate()}
                                    onChange={handleInputChange}
                                />
                            </div>
                        </div>

                        <h3 className="profile-section__subtitle">Status Obstetri (G-P-A)</h3>
                        <div className="profile-row profile-row--three">
                            <div className="profile-field">
                                <label>Gravida (G)</label>
                                <input
                                    type="number"
                                    name="gravida"
                                    value={formData.gravida}
                                    onChange={handleInputChange}
                                    placeholder="Kehamilan ke-"
                                    min="1"
                                />
                                <span className="profile-field__hint">Kehamilan ke-</span>
                            </div>
                            <div className="profile-field">
                                <label>Para (P)</label>
                                <input
                                    type="number"
                                    name="para"
                                    value={formData.para}
                                    onChange={handleInputChange}
                                    placeholder="0"
                                    min="0"
                                />
                                <span className="profile-field__hint">Jumlah persalinan</span>
                            </div>
                            <div className="profile-field">
                                <label>Abortus (A)</label>
                                <input
                                    type="number"
                                    name="abortus"
                                    value={formData.abortus}
                                    onChange={handleInputChange}
                                    placeholder="0"
                                    min="0"
                                />
                                <span className="profile-field__hint">Jumlah keguguran</span>
                            </div>
                        </div>

                        <h3 className="profile-section__subtitle">Data Fisik</h3>
                        <div className="profile-row profile-row--three">
                            <div className="profile-field">
                                <label>Tinggi Badan (cm)</label>
                                <input
                                    type="number"
                                    name="height"
                                    value={formData.height}
                                    onChange={handleInputChange}
                                    placeholder="160"
                                />
                            </div>
                            <div className="profile-field">
                                <label>BB Sebelum Hamil (kg)</label>
                                <input
                                    type="number"
                                    name="weightBeforePregnancy"
                                    value={formData.weightBeforePregnancy}
                                    onChange={handleInputChange}
                                    placeholder="55"
                                />
                            </div>
                            <div className="profile-field">
                                <label>BB Saat Ini (kg)</label>
                                <input
                                    type="number"
                                    name="currentWeight"
                                    value={formData.currentWeight}
                                    onChange={handleInputChange}
                                    placeholder="60"
                                />
                            </div>
                        </div>

                        {formData.para > 0 && (
                            <>
                                <h3 className="profile-section__subtitle">Riwayat Kehamilan Sebelumnya</h3>
                                <div className="profile-field">
                                    <label>Jenis Persalinan Sebelumnya</label>
                                    <select
                                        name="previousDeliveryType"
                                        value={formData.previousDeliveryType}
                                        onChange={handleInputChange}
                                    >
                                        <option value="">Pilih</option>
                                        <option value="normal">Normal/Pervaginam</option>
                                        <option value="cesarean">Operasi Caesar</option>
                                        <option value="vacuum">Vacuum</option>
                                        <option value="forceps">Forceps</option>
                                    </select>
                                </div>
                                <div className="profile-field">
                                    <label>Komplikasi Sebelumnya</label>
                                    <textarea
                                        name="previousComplications"
                                        value={formData.previousComplications}
                                        onChange={handleInputChange}
                                        placeholder="Jelaskan jika ada komplikasi pada kehamilan/persalinan sebelumnya"
                                        rows="3"
                                    />
                                </div>
                            </>
                        )}
                    </div>
                )}

                {/* Medical Records Tab */}
                {activeTab === 'medical' && (
                    <div className="profile-section">
                        <h2 className="profile-section__title">Riwayat Penyakit</h2>
                        
                        <div className="profile-checklist">
                            <label className="profile-checkbox">
                                <input
                                    type="checkbox"
                                    name="hasHypertension"
                                    checked={formData.hasHypertension}
                                    onChange={handleInputChange}
                                />
                                <span className="profile-checkbox__mark"></span>
                                <span className="profile-checkbox__label">Hipertensi (Tekanan Darah Tinggi)</span>
                            </label>

                            <label className="profile-checkbox">
                                <input
                                    type="checkbox"
                                    name="hasDiabetes"
                                    checked={formData.hasDiabetes}
                                    onChange={handleInputChange}
                                />
                                <span className="profile-checkbox__mark"></span>
                                <span className="profile-checkbox__label">Diabetes Mellitus</span>
                            </label>

                            <label className="profile-checkbox">
                                <input
                                    type="checkbox"
                                    name="hasHeartDisease"
                                    checked={formData.hasHeartDisease}
                                    onChange={handleInputChange}
                                />
                                <span className="profile-checkbox__mark"></span>
                                <span className="profile-checkbox__label">Penyakit Jantung</span>
                            </label>

                            <label className="profile-checkbox">
                                <input
                                    type="checkbox"
                                    name="hasAsthma"
                                    checked={formData.hasAsthma}
                                    onChange={handleInputChange}
                                />
                                <span className="profile-checkbox__mark"></span>
                                <span className="profile-checkbox__label">Asma</span>
                            </label>

                            <label className="profile-checkbox">
                                <input
                                    type="checkbox"
                                    name="hasAllergies"
                                    checked={formData.hasAllergies}
                                    onChange={handleInputChange}
                                />
                                <span className="profile-checkbox__mark"></span>
                                <span className="profile-checkbox__label">Alergi</span>
                            </label>
                        </div>

                        {formData.hasAllergies && (
                            <div className="profile-field">
                                <label>Detail Alergi</label>
                                <textarea
                                    name="allergiesDetail"
                                    value={formData.allergiesDetail}
                                    onChange={handleInputChange}
                                    placeholder="Sebutkan jenis alergi (obat, makanan, dll)"
                                    rows="2"
                                />
                            </div>
                        )}

                        <div className="profile-field">
                            <label>Kondisi Kesehatan Lainnya</label>
                            <textarea
                                name="otherConditions"
                                value={formData.otherConditions}
                                onChange={handleInputChange}
                                placeholder="Sebutkan kondisi kesehatan lain yang relevan"
                                rows="3"
                            />
                        </div>

                        <h2 className="profile-section__title">Obat yang Dikonsumsi</h2>
                        <div className="profile-field">
                            <label>Obat/Suplemen Saat Ini</label>
                            <textarea
                                name="currentMedications"
                                value={formData.currentMedications}
                                onChange={handleInputChange}
                                placeholder="Sebutkan obat atau suplemen yang sedang dikonsumsi"
                                rows="3"
                            />
                        </div>

                        <div className="profile-info-card">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10" />
                                <path d="M12 16v-4M12 8h.01" />
                            </svg>
                            <p>Data rekam medis ini akan membantu sistem memberikan analisis yang lebih akurat dan notifikasi yang relevan dengan kondisi kesehatan Anda.</p>
                        </div>
                    </div>
                )}

                {/* Save Button - Fixed at bottom for mobile */}
                <div className="profile-actions">
                    <button 
                        type="submit" 
                        className="profile-save-btn"
                        disabled={isSaving}
                    >
                        {isSaving ? (
                            <>
                                <svg className="profile-spinner" viewBox="0 0 24 24">
                                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" fill="none" strokeDasharray="60" strokeLinecap="round" />
                                </svg>
                                Menyimpan...
                            </>
                        ) : (
                            <>
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                                    <polyline points="17 21 17 13 7 13 7 21" />
                                    <polyline points="7 3 7 8 15 8" />
                                </svg>
                                Simpan Semua Data
                            </>
                        )}
                    </button>
                </div>
            </form>
        </div>
    );
};

export default ProfileScreen;
