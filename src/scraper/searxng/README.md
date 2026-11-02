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

## Search order: SearXNG, then Tavily, then ddgs

Cheap first, paid only when needed. For each query the scraper tries:

1. **SearXNG** (free) at `SEARXNG_URL`.
2. **Tavily** (paid, 1 credit per search), only if `TAVILY_API_KEY` is set in
   `.env`, and only for queries SearXNG failed or found nothing for. A wrong key
   or a spent plan (HTTP 401/432/433) switches Tavily off for the rest of the run.
3. **ddgs** (free, last resort), which scrapes public search engines and may be
   rate-limited.

Every switch is logged, and each run logs how many Tavily credits it used.
Results are cached for an hour whichever step answered, so the same query is
never paid for twice. Scenes that list their own `sources` never search at all.
