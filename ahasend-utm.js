(() => {
  const CONSENT_KEY = 'cookieConsent';
  const CONSENT_GRANTED = 'true';
  const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];
  const UTM_COOKIE_NAME = 'ahasend_utm';
  const UTM_COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

  const safeGetLocalStorage = (key) => {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  };

  const captureUTMs = () => {
    const params = new URLSearchParams(window.location.search);
    const utmData = {};

    UTM_KEYS.forEach((key) => {
      if (params.has(key)) {
        utmData[key] = params.get(key);
      }
    });

    if (Object.keys(utmData).length > 0) {
      const cookieValue = encodeURIComponent(JSON.stringify(utmData));
      document.cookie = `${UTM_COOKIE_NAME}=${cookieValue}; Domain=ahasend.com; Path=/; Max-Age=${UTM_COOKIE_MAX_AGE}; SameSite=Lax; Secure`;
    }
  };

  const applyConsentState = () => {
    if (safeGetLocalStorage(CONSENT_KEY) === CONSENT_GRANTED) {
      captureUTMs();
    }
  };

  window.addEventListener('storage', (event) => {
    if (event.key === CONSENT_KEY) {
      applyConsentState();
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      applyConsentState();
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyConsentState, { once: true });
  } else {
    applyConsentState();
  }
})();
