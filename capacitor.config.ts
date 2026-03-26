import type { CapacitorConfig } from '@capacitor/cli';

/**
 * Capacitor Configuration
 * =======================
 * File ini mengatur konfigurasi app Android yang di-generate dari web app.
 * 
 * PENJELASAN:
 * - appId: "com.fetalguard.app" → ini seperti "alamat" unik app kamu di Google Play
 * - appName: nama yang muncul di layar HP user
 * - webDir: "dist" → folder hasil `npm run build` yang akan dibungkus jadi app
 * - plugins: konfigurasi untuk fitur native (status bar, notifikasi, dll)
 */

const config: CapacitorConfig = {
  appId: 'com.fetalguard.app',
  appName: 'FETAL-GUARD',
  webDir: 'dist',

  // Server config — saat development, kamu bisa arahkan ke dev server
  // Uncomment baris di bawah saat development:
  // server: {
  //   url: 'http://192.168.x.x:5173',  // Ganti dengan IP komputer kamu
  //   cleartext: true
  // },

  plugins: {
    // Status Bar — mengatur warna bar atas HP
    StatusBar: {
      backgroundColor: '#FF6B9A',  // Warna primary pink FETAL-GUARD
      style: 'LIGHT',              // Text putih di status bar
      overlaysWebView: false       // Jangan tumpang tindih dengan konten
    },

    // Local Notifications — untuk alert darurat FHR abnormal
    LocalNotifications: {
      smallIcon: 'ic_stat_heart',     // Icon kecil di notification bar
      iconColor: '#FF6B9A',           // Warna icon notifikasi
      sound: 'alert_sound.wav'        // Suara khusus untuk alert kritis
    },

    // Bluetooth LE — untuk koneksi ke device IoT (Mi Band style)
    BluetoothLe: {
      // Android: minta izin lokasi untuk scan BLE
      displayStrings: {
        scanning: 'Mencari perangkat FETAL-GUARD...',
        cancel: 'Batal',
        availableDevices: 'Perangkat Tersedia',
        noDeviceFound: 'Tidak ada perangkat ditemukan'
      }
    }
  },

  // Android-specific settings
  android: {
    backgroundColor: '#F6F8FB',       // Background saat loading
    allowMixedContent: true,          // Izinkan HTTP + HTTPS (untuk MQTT)
    captureInput: true,               // Capture keyboard input
    webContentsDebuggingEnabled: true  // Debug via Chrome DevTools (matikan saat production!)
  }
};

export default config;
