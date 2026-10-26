# Local SearXNG for the scraper

The scraper searches through a SearXNG instance's JSON API
(`/search?q=...&format=json`). Most public instances turn the JSON API off
(`search.formats` has no `json`) or rate-limit it, so running your own is the
reliable option. It takes about a minute with Docker.

## Run it

1. Add a random secret and the URL to the repo's `.env` (never commit `.env`):

   ```sh
   echo "SEARXNG_SECRET=$(openssl rand -hex 32)" >> .env
   echo "SEARXNG_URL=http://localhost:8888" >> .env
   ```

   No openssl? `python -c "import secrets; print(secrets.token_hex(32))"` works too.

2. Start it from the repo root:

   ```sh
   docker compose --env-file .env -f src/scraper/searxng/docker-compose.yml up -d
   ```

3. Check that JSON works:

   ```sh
   curl "http://localhost:8888/search?q=typhoon&format=json"
   ```

   A `403 Forbidden` means `json` is missing from `search.formats` in `settings.yml`.

Stop it with `docker compose -f src/scraper/searxng/docker-compose.yml down`.

## Without SearXNG

If `SEARXNG_URL` is unset or the instance fails, the scraper logs a warning and
searches with DuckDuckGo through the `ddgs` package instead. Scenes that list
their own `sources` never search at all.
