const BACKEND = 'https://oxycode.duckdns.org';

export async function onRequest(context) {
  const url = new URL(context.request.url);

  // Handle CORS preflight
  if (context.request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '86400',
      },
    });
  }

  // Proxy API requests to VPS backend
  if (url.pathname.startsWith('/api/')) {
    const backendUrl = `${BACKEND}${url.pathname}${url.search}`;

    const headers = new Headers();
    for (const [key, value] of context.request.headers) {
      if (key !== 'host') headers.set(key, value);
    }

    try {
      const resp = await fetch(backendUrl, {
        method: context.request.method,
        headers,
        body: ['POST', 'PUT', 'PATCH'].includes(context.request.method)
          ? context.request.body
          : undefined,
      });

      const respHeaders = new Headers(resp.headers);
      respHeaders.set('Access-Control-Allow-Origin', '*');

      return new Response(resp.body, {
        status: resp.status,
        headers: respHeaders,
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: 'Backend unavailable' }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  }

  // Everything else: serve static files
  return context.next();
}
