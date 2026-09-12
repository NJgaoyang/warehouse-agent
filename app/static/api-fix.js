(() => {
  // Fetch Response body can only be consumed once. Read text once, then parse.
  window.api = async function api(url, opt = {}) {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(opt.headers || {})
      },
      ...opt
    });

    const raw = await response.text();
    let data = null;
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch (_) {
        data = raw;
      }
    }

    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      if (typeof data === 'string' && data.trim()) {
        message = data;
      } else if (data && typeof data === 'object') {
        const detail = data.detail;
        if (detail && typeof detail === 'object') {
          const operation = detail.operation ? `${detail.operation} · ` : '';
          const type = detail.error_type ? `${detail.error_type}: ` : '';
          message = `${operation}${type}${detail.message || JSON.stringify(detail)}`;
        } else {
          message = detail || data.message || JSON.stringify(data);
        }
      }
      throw new Error(`${url} · ${message}`);
    }
    return data;
  };
})();
