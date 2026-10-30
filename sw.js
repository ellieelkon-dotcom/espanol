// Offline support. App shell: cache first. Word lists (data/): network first, cached copy when offline.
const VERSION="v6";
const SHELL="practica-shell-"+VERSION, DATA="practica-data", FONTS="practica-fonts";
const SHELL_FILES=["./","index.html","manifest.webmanifest","icons/icon-180.png","icons/icon-192.png","icons/icon-512.png"];
const DATA_FILES=["data/deck.json","data/grammar.json","data/clips.json"];
self.addEventListener("install",e=>{
  e.waitUntil(Promise.all([
    caches.open(SHELL).then(c=>c.addAll(SHELL_FILES)),
    caches.open(DATA).then(c=>c.addAll(DATA_FILES))
  ]).then(()=>self.skipWaiting()));
});
self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k.startsWith("practica-shell-")&&k!==SHELL).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener("fetch",e=>{
  const req=e.request; if(req.method!=="GET") return;
  const url=new URL(req.url);
  if(url.origin===location.origin&&url.pathname.includes("/data/")){
    e.respondWith(fetch(req,{cache:"no-cache"}).then(r=>{ if(r.ok){ const cp=r.clone(); caches.open(DATA).then(c=>c.put(req,cp)); } return r; })
      .catch(()=>caches.match(req,{ignoreSearch:true})));
    return;
  }
  if(url.hostname.endsWith("fonts.googleapis.com")||url.hostname.endsWith("fonts.gstatic.com")){
    e.respondWith(caches.open(FONTS).then(c=>c.match(req).then(hit=>hit||fetch(req).then(r=>{ c.put(req,r.clone()); return r; }).catch(()=>hit))));
    return;
  }
  if(url.origin===location.origin){
    e.respondWith(caches.match(req,{ignoreSearch:true}).then(hit=>{
      const net=fetch(req).then(r=>{ if(r.ok){ const cp=r.clone(); caches.open(SHELL).then(c=>c.put(req,cp)); } return r; });
      return hit||net.catch(()=>caches.match("index.html"));
    }));
  }
});
