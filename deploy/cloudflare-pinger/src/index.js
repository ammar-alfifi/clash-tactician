// Cloudflare Worker cron trigger used to keep the Render free web service
// awake (Render spins a free service down after 15 minutes without traffic).
// Deploy with: npx wrangler deploy

async function ping(target) {
  try {
    const response = await fetch(target, { method: "GET" });
    return response.ok;
  } catch (error) {
    console.log(`ping failed: ${error}`);
    return false;
  }
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(ping(env.TARGET_URL));
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/ping") {
      const ok = await ping(env.TARGET_URL);
      return Response.json({ ok });
    }
    return new Response("clash-tactician keep-alive worker\n");
  },
};
