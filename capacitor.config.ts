import type { CapacitorConfig } from '@capacitor/cli';

const devServerUrl = process.env.CAPACITOR_DEV_SERVER_URL;
const isNativeDevServerEnabled = Boolean(devServerUrl);
const isLocalCleartextApiEnabled =
  process.env.CAPACITOR_ALLOW_LOCAL_CLEARTEXT_API === 'true';

const config: CapacitorConfig = {
  appId: 'com.fetalguard.app',
  appName: 'FETAL-GUARD',
  webDir: 'dist',

  ...(devServerUrl
    ? {
        server: {
          url: devServerUrl,
          cleartext: true,
        },
      }
    : {}),

  plugins: {
    StatusBar: {
      backgroundColor: '#FF6B9A',
      style: 'LIGHT',
      overlaysWebView: false,
    },

    BluetoothLe: {
      displayStrings: {
        scanning: 'Mencari perangkat FETAL-GUARD...',
        cancel: 'Batal',
        availableDevices: 'Perangkat Tersedia',
        noDeviceFound: 'Tidak ada perangkat ditemukan',
      },
    },
  },

  android: {
    backgroundColor: '#F6F8FB',
    allowMixedContent: isNativeDevServerEnabled || isLocalCleartextApiEnabled,
    captureInput: true,
    webContentsDebuggingEnabled: isNativeDevServerEnabled || isLocalCleartextApiEnabled,
  },
};

export default config;
