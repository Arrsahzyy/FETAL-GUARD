/**
 * useBluetooth Hook — Koneksi BLE (Mi Band Style)
 * ================================================
 * 
 * PENJELASAN:
 * Hook ini memudahkan kamu menggunakan Bluetooth LE di komponen React.
 * Bayangkan seperti "remote control" untuk koneksi Bluetooth:
 * - scan() → cari perangkat FETAL-GUARD di sekitar
 * - connect(deviceId) → hubungkan ke perangkat
 * - disconnect() → putuskan koneksi
 * 
 * CARA PAKAI:
 * ```jsx
 * function MonitoringScreen() {
 *   const { 
 *     isScanning, devices, connectedDevice, 
 *     sensorData, scan, connect, disconnect 
 *   } = useBluetooth();
 * 
 *   return (
 *     <div>
 *       <button onClick={scan}>Cari Perangkat</button>
 *       {devices.map(d => (
 *         <button onClick={() => connect(d.deviceId)}>{d.name}</button>
 *       ))}
 *       {sensorData && <p>FHR: {sensorData.fhr} bpm</p>}
 *     </div>
 *   );
 * }
 * ```
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// Konfigurasi default BLE
const DEFAULT_CONFIG = {
  // Nama prefix device yang akan di-scan
  // Device IoT kamu harus broadcast nama yang diawali prefix ini
  deviceNamePrefix: 'FETAL-GUARD',

  // UUID Service — identifier unik untuk "jenis layanan" BLE
  // Ini harus cocok dengan yang di-set di firmware ESP32/Arduino kamu
  serviceUUID: '0000ffe0-0000-1000-8000-00805f9b34fb',

  // UUID Characteristic — identifier untuk "data stream" spesifik
  characteristicUUID: '0000ffe1-0000-1000-8000-00805f9b34fb',

  // Timeout scan dalam milidetik (10 detik)
  scanTimeout: 10000,
};

export function useBluetooth(config = {}) {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  // ============================================
  // STATE — data yang bisa diakses di UI
  // ============================================

  /** Apakah sedang scanning perangkat */
  const [isScanning, setIsScanning] = useState(false);

  /** Daftar perangkat yang ditemukan saat scan */
  const [devices, setDevices] = useState([]);

  /** Perangkat yang sedang terkoneksi */
  const [connectedDevice, setConnectedDevice] = useState(null);

  /** Apakah sedang proses connecting */
  const [isConnecting, setIsConnecting] = useState(false);

  /** Data sensor terbaru dari perangkat */
  const [sensorData, setSensorData] = useState(null);

  /** Pesan error terakhir */
  const [error, setError] = useState(null);

  /** Apakah BLE tersedia di device ini */
  const [isAvailable, setIsAvailable] = useState(false);

  // Ref untuk BleClient (diload secara lazy/dinamis)
  const bleClientRef = useRef(null);

  // ============================================
  // INITIALIZE — cek apakah BLE tersedia
  // ============================================

  useEffect(() => {
    const initBLE = async () => {
      try {
        // Import BLE plugin secara dinamis
        // Ini agar app tetap bisa jalan di browser (tanpa BLE)
        const { BleClient } = await import('@capacitor-community/bluetooth-le');
        bleClientRef.current = BleClient;

        // Inisialisasi BLE
        await BleClient.initialize({ androidNeverForLocation: false });
        setIsAvailable(true);
        console.log('[useBluetooth] BLE initialized successfully');
      } catch (err) {
        console.warn('[useBluetooth] BLE not available:', err.message);
        setIsAvailable(false);
        // Tidak set error karena ini normal saat di browser
      }
    };

    initBLE();

    // Cleanup saat component unmount
    return () => {
      if (connectedDevice) {
        disconnect();
      }
    };
  }, []);

  // ============================================
  // SCAN — Cari perangkat di sekitar
  // ============================================

  const scan = useCallback(async () => {
    const BleClient = bleClientRef.current;
    if (!BleClient) {
      setError('Bluetooth tidak tersedia di perangkat ini');
      return;
    }

    setIsScanning(true);
    setDevices([]);
    setError(null);

    try {
      // Scan device yang namanya diawali "FETAL-GUARD"
      await BleClient.requestLEScan(
        {
          namePrefix: cfg.deviceNamePrefix,
          optionalServices: [cfg.serviceUUID],
        },
        (result) => {
          // Setiap device ditemukan, tambahkan ke list
          setDevices((prev) => {
            // Hindari duplikat berdasarkan deviceId
            const exists = prev.find((d) => d.deviceId === result.device.deviceId);
            if (exists) return prev;

            const newDevice = {
              deviceId: result.device.deviceId,
              name: result.device.name || result.localName || 'Unknown Device',
              rssi: result.rssi,  // Kekuatan sinyal (makin besar makin dekat)
            };

            console.log(`[useBluetooth] Found: ${newDevice.name} (${newDevice.deviceId})`);
            return [...prev, newDevice];
          });
        }
      );

      // Stop scan setelah timeout
      setTimeout(async () => {
        await BleClient.stopLEScan();
        setIsScanning(false);
      }, cfg.scanTimeout);

    } catch (err) {
      setError(`Gagal scan: ${err.message}`);
      setIsScanning(false);
    }
  }, [cfg]);

  // ============================================
  // CONNECT — Hubungkan ke perangkat yang dipilih
  // ============================================

  const connect = useCallback(async (deviceId) => {
    const BleClient = bleClientRef.current;
    if (!BleClient) return;

    setIsConnecting(true);
    setError(null);

    try {
      // 1. Connect ke device
      await BleClient.connect(deviceId, () => {
        // Callback saat device tiba-tiba disconnect
        console.log('[useBluetooth] Device disconnected unexpectedly');
        setConnectedDevice(null);
        setSensorData(null);
      });

      // 2. Set device yang terkoneksi
      const device = devices.find((d) => d.deviceId === deviceId);
      setConnectedDevice(device || { deviceId });

      // 3. Subscribe ke notifications — menerima data realtime dari sensor
      await BleClient.startNotifications(
        deviceId,
        cfg.serviceUUID,
        cfg.characteristicUUID,
        (value) => {
          // value = DataView dari BLE
          const parsed = decodeSensorData(value);
          setSensorData(parsed);
        }
      );

      console.log(`[useBluetooth] Connected and subscribed to ${deviceId}`);
    } catch (err) {
      setError(`Gagal connect: ${err.message}`);
      setConnectedDevice(null);
    } finally {
      setIsConnecting(false);
    }
  }, [devices, cfg]);

  // ============================================
  // DISCONNECT — Putuskan koneksi
  // ============================================

  const disconnect = useCallback(async () => {
    const BleClient = bleClientRef.current;
    if (!BleClient || !connectedDevice) return;

    try {
      await BleClient.stopNotifications(
        connectedDevice.deviceId,
        cfg.serviceUUID,
        cfg.characteristicUUID
      );
      await BleClient.disconnect(connectedDevice.deviceId);
    } catch (err) {
      console.warn('[useBluetooth] Disconnect error:', err);
    }

    setConnectedDevice(null);
    setSensorData(null);
  }, [connectedDevice, cfg]);

  // ============================================
  // HELPER — Decode data sensor dari BLE
  // ============================================

  /**
   * Decode data yang dikirim dari device IoT via BLE
   * Mendukung 2 format:
   * 1. JSON string — { "fhr": 142, "motherHR": 82, ... }
   * 2. Binary — byte array sesuai protokol yang kamu definisikan
   */
  function decodeSensorData(dataView) {
    try {
      // Coba parse sebagai JSON string dulu
      const decoder = new TextDecoder();
      const text = decoder.decode(dataView.buffer);
      return JSON.parse(text);
    } catch {
      // Fallback: parse sebagai binary data
      try {
        return {
          fhr: dataView.getUint16(0, true),
          motherHR: dataView.getUint16(2, true),
          signalQuality: dataView.getUint8(4),
          movements: dataView.getUint8(5),
          timestamp: new Date().toISOString(),
        };
      } catch {
        return { fhr: 0, error: 'decode_failed' };
      }
    }
  }

  // ============================================
  // RETURN — semua yang bisa diakses dari komponen
  // ============================================

  return {
    // State
    isAvailable,       // BLE tersedia di device?
    isScanning,        // Sedang scanning?
    isConnecting,      // Sedang connecting?
    devices,           // Daftar device ditemukan
    connectedDevice,   // Device yang terkoneksi
    sensorData,        // Data sensor terbaru
    error,             // Error message

    // Actions
    scan,              // Mulai scan
    connect,           // Connect ke device
    disconnect,        // Disconnect
  };
}

export default useBluetooth;
