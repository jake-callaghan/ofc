export async function api(path, token, body, signal) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      credentials: 'same-origin',
      headers: {
        'X-OFC-Request': '1',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error(
      'Cannot reach the server. Check your connection and try again.',
    );
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error('The server is unavailable. Please try again.');
  }
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join('; ')
      : data.detail;
    const error = new Error(
      detail || 'Something went wrong. Please try again.',
    );
    error.status = response.status;
    if (response.status === 401 && !path.startsWith('/auth/'))
      window.dispatchEvent(new Event('ofc-session-expired'));
    throw error;
  }
  return data;
}
