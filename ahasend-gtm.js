(() => {
  const TAG_ID = 'GTM-KCQ9JNVZ';
  const CONSENT_KEY = 'cookieConsent';
  const CONSENT_GRANTED = 'true';
  const GTM_SRC_PREFIX = 'https://www.googletagmanager.com';
  const GTM_SCRIPT_SRC = `${GTM_SRC_PREFIX}/gtm.js?id=${TAG_ID}`;
  const NOSCRIPT_ID = 'ahasend-gtm-noscript';
  const SCRIPT_ID = 'ahasend-gtm-script';
  const DATA_LAYER_NAME = 'dataLayer';

  if (typeof window[DATA_LAYER_NAME] === 'undefined') {
    window[DATA_LAYER_NAME] = [];
  }

  if (typeof window.gtag !== 'function') {
    window.gtag = function () {
      window[DATA_LAYER_NAME].push(arguments);
    };
  }

  const pushConsentEvent = (granted) => {
    const status = granted ? 'granted' : 'denied';
    const dataLayer = (window[DATA_LAYER_NAME] = window[DATA_LAYER_NAME] || []);

    dataLayer.push({
      event: 'cookie_consent_analytics',
      consent_given: granted
    });

    if (typeof window.gtag === 'function') {
      window.gtag('consent', 'update', {
        analytics_storage: status,
      });
    }
  };

  const cookiesToClear = [
    '_ga',
    '_gid',
    '_gat',
    '_gcl_au',
    `_ga_${TAG_ID.replace('GTM-', '')}`
  ];

  const safeGetLocalStorage = (key) => {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  };

  const clearCookie = (name) => {
    const domain = window.location.hostname;
    document.cookie = `${name}=; Max-Age=0; path=/; domain=${domain}; SameSite=Lax;`;
    document.cookie = `${name}=; Max-Age=0; path=/; SameSite=Lax;`;
  };

  const removeNoscript = () => {
    const noscript = document.getElementById(NOSCRIPT_ID);
    if (noscript) {
      noscript.remove();
    }
  };

  const insertNoscript = () => {
    if (document.getElementById(NOSCRIPT_ID)) {
      return;
    }

    const iframe = document.createElement('iframe');
    iframe.src = `${GTM_SRC_PREFIX}/ns.html?id=${TAG_ID}`;
    iframe.height = 0;
    iframe.width = 0;
    iframe.style.display = 'none';
    iframe.style.visibility = 'hidden';

    const noscript = document.createElement('noscript');
    noscript.id = NOSCRIPT_ID;
    noscript.appendChild(iframe);

    if (document.body) {
      document.body.insertBefore(noscript, document.body.firstChild || null);
    } else {
      document.addEventListener(
        'DOMContentLoaded',
        () => {
          if (!document.getElementById(NOSCRIPT_ID)) {
            document.body.insertBefore(noscript, document.body.firstChild || null);
          }
        },
        { once: true }
      );
    }
  };

  const removeGtm = () => {
    pushConsentEvent(false);

    document
      .querySelectorAll(`script[src^="${GTM_SRC_PREFIX}/gtm.js"]`)
      .forEach((script) => script.remove());

    const managedScript = document.getElementById(SCRIPT_ID);
    if (managedScript) {
      managedScript.remove();
    }

    removeNoscript();

    cookiesToClear.forEach(clearCookie);
  };

  const loadGtm = () => {
    if (document.getElementById(SCRIPT_ID) || document.querySelector(`script[src="${GTM_SCRIPT_SRC}"]`)) {
      return;
    }

    window[DATA_LAYER_NAME].push({
      'gtm.start': Date.now(),
      event: 'gtm.js'
    });

    pushConsentEvent(true);

    const script = document.createElement('script');
    script.id = SCRIPT_ID;
    script.async = true;
    script.src = GTM_SCRIPT_SRC;
    document.head.appendChild(script);

    insertNoscript();
  };

  const applyConsentState = () => {
    const consent = safeGetLocalStorage(CONSENT_KEY);
    if (consent === CONSENT_GRANTED) {
      loadGtm();
    } else {
      removeGtm();
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
