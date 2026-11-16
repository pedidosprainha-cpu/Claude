// Service worker: deixa o app instalável e abrindo rápido, mesmo com internet ruim.
const CACHE = "maquina-v1";
const ARQUIVOS = ["/", "/static/estilo.css", "/static/app.js", "/static/icone-192.png", "/static/icone-512.png", "/manifest.webmanifest"];
const NAO_GUARDAR = ["/api/", "/p/", "/ir/", "/webhooks/", "/privacidade"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARQUIVOS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || NAO_GUARDAR.some((p) => url.pathname.startsWith(p))) return;
  // Rede primeiro (sempre a versão mais nova); cache só se estiver sem internet.
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        if (r.ok) { const copia = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copia)); }
        return r;
      })
      .catch(() => caches.match(e.request))
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window" }).then((ws) => (ws.length ? ws[0].focus() : self.clients.openWindow("/"))));
});
