const CACHE_NAME = "english-glossary-v1";

const STATIC_FILES = [
    "/",
    "/static/manifest.json"
];


self.addEventListener("install", event => {

    event.waitUntil(

        caches
            .open(CACHE_NAME)
            .then(cache => {

                return cache.addAll(STATIC_FILES);

            })

    );

    self.skipWaiting();

});


self.addEventListener("activate", event => {

    event.waitUntil(

        caches
            .keys()
            .then(cacheNames => {

                return Promise.all(

                    cacheNames
                        .filter(name => name !== CACHE_NAME)
                        .map(name => caches.delete(name))

                );

            })

    );

    self.clients.claim();

});


self.addEventListener("fetch", event => {

    /*
     * Para la API usamos siempre Internet.
     * Esto es importante porque las palabras
     * están almacenadas en GitHub.
     */

    if (
        event.request.url.includes("/api/")
    ) {
        return;
    }


    event.respondWith(

        fetch(event.request)

            .then(response => {

                const copy = response.clone();

                caches
                    .open(CACHE_NAME)
                    .then(cache => {
                        cache.put(
                            event.request,
                            copy
                        );
                    });

                return response;

            })

            .catch(() => {

                return caches.match(
                    event.request
                );

            })

    );

});