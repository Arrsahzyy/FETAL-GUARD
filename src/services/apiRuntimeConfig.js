const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1']);

const parseIPv4 = (hostname) => {
  const parts = hostname.split('.');
  if (parts.length !== 4) return null;
  const octets = parts.map((part) => Number(part));
  if (octets.some((octet) => !Number.isInteger(octet) || octet < 0 || octet > 255)) {
    return null;
  }
  return octets;
};

export const isLoopbackHttpUrl = (value) => {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' && LOOPBACK_HOSTS.has(url.hostname.toLowerCase());
  } catch {
    return false;
  }
};

export const isPrivateNetworkHttpUrl = (value) => {
  try {
    const url = new URL(value);
    if (url.protocol !== 'http:') return false;
    const octets = parseIPv4(url.hostname);
    if (!octets) return false;
    const [first, second] = octets;
    return first === 10
      || (first === 172 && second >= 16 && second <= 31)
      || (first === 192 && second === 168);
  } catch {
    return false;
  }
};

export const normalizePrivateNetworkApiBaseUrl = (value) => {
  try {
    const url = new URL(String(value || '').trim());
    if (
      !isPrivateNetworkHttpUrl(url.toString())
      || url.username
      || url.password
      || (url.pathname && url.pathname !== '/')
      || url.search
      || url.hash
    ) {
      return null;
    }
    return url.origin;
  } catch {
    return null;
  }
};

export const evaluateApiRuntimePolicy = ({
  configuredApiBaseUrl,
  isNativeRuntime,
  isProduction,
  mode,
  allowInsecureLocalApi,
}) => {
  const baseUrl = String(configuredApiBaseUrl || '').trim();
  const localAndroidDebugAllowed = isNativeRuntime
    && mode === 'android-local'
    && allowInsecureLocalApi === true
    && isPrivateNetworkHttpUrl(baseUrl);
  const usesHttp = baseUrl.toLowerCase().startsWith('http://');

  return {
    hasMissingNativeApiConfig: isProduction && isNativeRuntime && !baseUrl,
    hasUnsafeProductionApiConfig: isProduction
      && usesHttp
      && !isLoopbackHttpUrl(baseUrl)
      && !localAndroidDebugAllowed,
    localAndroidDebugAllowed,
  };
};
