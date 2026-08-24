const VPS_HOST = '153.75.247.105';
const VPS_PORT = '8000';

function addCORS(headers: Headers): Headers {
  const newHeaders = new Headers(headers);
  newHeaders.set('Access-Control-Allow-Origin', '*');
  newHeaders.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  newHeaders.set('Access-Control-Allow-Headers', '*');
  return newHeaders;
}

export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: addCORS(new Headers()),
      });
    }

    // Handle WebSocket upgrade
    if (request.headers.get('Upgrade') === 'websocket') {
      const wsUrl = `ws://${VPS_HOST}:${VPS_PORT}${url.pathname}${url.search}`;
      try {
        return fetch(wsUrl, {
          method: request.method,
          headers: request.headers,
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: 'WebSocket proxy error', details: String(e) }), {
          status: 502,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }

    // Handle HTTP proxy
    const backendUrl = `http://${VPS_HOST}:${VPS_PORT}${url.pathname}${url.search}`;
    try {
      const response = await fetch(backendUrl, {
        method: request.method,
        headers: request.headers,
        body: request.body,
      });

      const newHeaders = addCORS(response.headers);
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: newHeaders,
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: 'Backend unreachable', details: String(e) }), {
        status: 502,
        headers: { 'Content-Type': 'application/json', ...Object.fromEntries(addCORS(new Headers())) },
      });
    }
  },
};
