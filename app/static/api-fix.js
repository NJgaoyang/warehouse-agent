(() => {
  // The original prototype tried response.json() and then response.text() on
  // parse failure.  A Fetch Response body is a one-shot stream, so the second
  // read raised: "body stream already read".  Read once, then parse locally.
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
        message = data.detail || data.message || JSON.stringify(data);
      }
      throw new Error(message);
    }
    return data;
  };
})();
