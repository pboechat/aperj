# Apê RJ (`aperj`)

<p align="center">
  <img src="assets/logo.png" alt="Apê RJ logo" width="200">
</p>


**🏠 Apartment & flat listings scraper for the Marvelous City**

`aperj` searches across 15 Brazilian real-estate websites simultaneously, collects apartment/flat listings, and presents results in a beautiful rich-text table on the terminal or exports them to CSV.

---

## Features

- **15 sources** scraped in parallel using `asyncio` + `aiohttp`
- Beautiful **rich-text** terminal output via the `rich` library
- **CSV export** for spreadsheet analysis
- YAML-based **configuration** with sensible defaults
- **Per-source cookies** for sites that require authentication
- Modular, extensible architecture - one module per source
- CLI powered by `argparse`

> **🗺️ Not in Rio?** Although `aperj` was designed with Rio de Janeiro in mind, it can
> search for apartments in **any location in Brazil**. Just edit `config.yml` to change
> the `region` field (e.g. `"São Paulo, SP"`), disable sources that are exclusive to Rio
> (such as `portalrjimoveis`, `judicearaujo`, or `patrimovel`), and optionally add
> real-estate source modules for your state. That's it — the nationwide sources (ZAP,
> VivaReal, OLX, Mercado Livre, …) will work anywhere.

## Supported Sources

| #  | Source             | Website                                        |
|----|--------------------|------------------------------------------------|
| 1  | ZAP Imóveis        | https://www.zapimoveis.com.br                  |
| 2  | VivaReal           | https://www.vivareal.com.br                    |
| 3  | ImovelWeb          | https://www.imovelweb.com.br                   |
| 4  | OLX                | https://www.olx.com.br                         |
| 5  | Nuroa              | https://www.nuroa.com.br                       |
| 6  | Nestoria           | https://www.nestoria.com.br                    |
| 7  | Portal RJ Imóveis  | http://www.portalrjimoveis.com.br              |
| 8  | Imoveis.net        | https://www.imoveis.net                        |
| 9  | Mercado Livre      | https://imoveis.mercadolivre.com.br            |
| 10 | Judice & Araujo    | https://www.judicearaujo.com.br                |
| 11 | Lopes              | https://www.lopes.com.br                       |
| 12 | Patrimóvel         | https://www.patrimovel.com.br                  |
| 13 | Cyrela             | https://www.cyrela.com.br                      |
| 14 | Even               | https://www.even.com.br                        |
| 15 | MRV                | https://www.mrv.com.br                         |

## Installation

```bash
# Clone and install in editable mode
git clone <repo-url> && cd aperj
pip install -e ".[dev]"
```

### Pre-commit hooks

```bash
pre-commit install
```

## Quick Start

### 1. Initialise the configuration

```bash
aperj --init-config
```

This creates:

- `~/.config/aperj/config.yml` - main configuration file
- `~/.config/aperj/cookies/` - directory for per-source cookie files

### 2. (Optional) Edit the configuration

```yaml
# ~/.config/aperj/config.yml
keywords: []

region: "Rio de Janeiro, RJ"
max_results_per_source: 200

output:
  format: rich
  csv_path: apes.csv

sources:
  zapimoveis:
    enabled: true
  vivareal:
    enabled: true
  # … etc.

auth:
  # source_name:
  #   username: you@example.com
  #   password: secret
```

### 3. Run a search

```bash
# Uses keywords from config
aperj

# Override / add keywords from CLI
aperj --keywords "cobertura duplex" "zona sul"

# Only specific sources
aperj --sources zapimoveis vivareal olx

# Export to CSV
aperj --export apes.csv

# Verbose (INFO-level logging)
aperj -v

# Debug-level logging
aperj -vv
```

## CLI Reference

```
usage: aperj [-h] [--version] [--init-config] [--config CONFIG]
             [--keywords KEYWORDS [KEYWORDS ...]]
             [--sources SOURCES [SOURCES ...]]
             [--export FILE] [--no-rich] [--max-results MAX_RESULTS]
             [--verbose] [--flaresolverr URL]
             [--min-price BRL] [--max-price BRL]
             [--min-condo BRL] [--max-condo BRL]
             [--min-iptu BRL] [--max-iptu BRL]
             [--min-area-m2 M2] [--max-area-m2 M2]
             [--min-bedrooms N] [--max-bedrooms N]
             [--min-suites N] [--max-suites N]
             [--min-bathrooms N] [--max-bathrooms N]
             [--min-parking N] [--max-parking N]
             [--listing-type {venda,aluguel}]
             [--property-type TYPE [TYPE ...]]
             [--neighborhood NAME [NAME ...]]

Options:
  --version             Show version and exit
  --init-config         Create a default config file and exit
  --config CONFIG       Path to config file (default: ~/.config/aperj/config.yml)
  -k, --keywords ...    Search keywords (merged with config keywords)
  -s, --sources ...     Only scrape these sources (by name)
  --export FILE         Write results to a CSV file
  --no-rich             Suppress pretty-printed table output
  --max-results N       Override max results per source
  -v, --verbose         Increase logging verbosity (-v INFO, -vv DEBUG)
  --flaresolverr URL    FlareSolverr endpoint for Cloudflare-protected sites

Filters (post-scrape):
  --min-price BRL       Minimum price in BRL (e.g. 200000)
  --max-price BRL       Maximum price in BRL (e.g. 800000)
  --min-condo BRL       Minimum condo fee in BRL
  --max-condo BRL       Maximum condo fee in BRL
  --min-iptu BRL        Minimum IPTU in BRL
  --max-iptu BRL        Maximum IPTU in BRL
  --min-area-m2 M2      Minimum area in square metres
  --max-area-m2 M2      Maximum area in square metres
  --min-bedrooms N      Minimum number of bedrooms
  --max-bedrooms N      Maximum number of bedrooms
  --min-suites N        Minimum number of suites
  --max-suites N        Maximum number of suites
  --min-bathrooms N     Minimum number of bathrooms
  --max-bathrooms N     Maximum number of bathrooms
  --min-parking N       Minimum number of parking spots
  --max-parking N       Maximum number of parking spots
  --listing-type TYPE   Keep only venda (sale) or aluguel (rent)
  --property-type TYPE  Keep only these property types (e.g. apartamento cobertura)
  --neighborhood NAME   Keep only listings in these neighborhoods (substring match)
```

### Filtering Examples

```bash
# Apartments up to R$ 800k with at least 2 bedrooms
aperj --max-price 800000 --min-bedrooms 2

# Rentals only, in Copacabana or Ipanema, area ≥ 60 m²
aperj --listing-type aluguel --neighborhood Copacabana Ipanema --min-area-m2 60

# Only coberturas (penthouses) with parking
aperj --property-type cobertura --min-parking 1

# Combine filters: 2–3 bedrooms, price between R$ 400k and R$ 700k
aperj --min-price 400000 --max-price 700000 --min-bedrooms 2 --max-bedrooms 3
```

> **Note:** Filters are applied *after* scraping. Listings where the filtered field is
> unknown (`None`) are excluded — if a source doesn't report an area, for instance,
> `--min-area-m2` will drop those listings.

## Authentication & Cookies

Some sources may require authentication. You can provide credentials in `config.yml`:

```yaml
auth:
  zapimoveis:
    username: you@example.com
    password: yourpassword
```

For sites that need browser cookies (e.g. after an SSO / Google login):

1. Log in to the site in your browser.
2. Export the cookies (e.g. with a browser extension like *EditThisCookie*).
3. Save them to `~/.config/aperj/cookies/<source_name>` in Netscape/curl format or simple `key=value` lines.

```
# Example: ~/.config/aperj/cookies/zapimoveis
session_id=abc123
csrf_token=xyz789
```

## Adding a New Source

1. Create `aperj/sources/mysite.py` with a class inheriting from `BaseSource`.
2. Implement `_do_scrape(self, keywords: list[str]) -> list[Listing]`.
3. Register the class in `aperj/sources/__init__.py`.
4. Add a `mysite` entry under `sources:` in the default config.

```python
from aperj.models import Listing
from aperj.sources.base import BaseSource

class MySiteSource(BaseSource):
    name = "mysite"
    base_url = "https://www.mysite.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        async with self._build_session() as session:
            html = await self._fetch(session, f"{self.base_url}/search?q={'+'.join(keywords)}")
        soup = self._soup(html)
        # … parse and return list[Listing]
        return []
```

## Cloudflare-Protected Sources & FlareSolverr

Some sources (notably **ImovelWeb**) are behind Cloudflare managed challenges that block automated requests. When `aperj` encounters a 403 response it already tries two levels of fallback automatically:

1. **aiohttp** — standard HTTP request
2. **curl_cffi** — retries with a real browser TLS fingerprint (bypasses basic bot detection)

However, sites with aggressive Cloudflare protection will block both approaches, especially from cloud/data-centre IPs. For these sources you need a third layer: **[FlareSolverr](https://github.com/FlareSolverr/FlareSolverr)**, a proxy server that runs a real browser to solve Cloudflare challenges on your behalf.

### Running FlareSolverr with Docker

The easiest way to run FlareSolverr is via Docker:

```bash
docker run -d \
  --name flaresolverr \
  -p 8191:8191 \
  -e LOG_LEVEL=info \
  --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest
```

Verify it's running:

```bash
curl http://localhost:8191/
```

### Configuring `aperj` to use FlareSolverr

You can point `aperj` at your FlareSolverr instance in two ways:

**Option 1 — CLI flag (one-off):**

```bash
aperj --flaresolverr http://localhost:8191/v1
```

**Option 2 — Configuration file (persistent):**

Add the `flaresolverr_url` key to `~/.config/aperj/config.yml`:

```yaml
flaresolverr_url: "http://localhost:8191/v1"
```

With FlareSolverr configured, the fallback chain becomes:

1. **aiohttp** → 403? →
2. **curl_cffi** (TLS impersonation) → still 403? →
3. **FlareSolverr** (real browser solves the challenge)

Without FlareSolverr configured, Cloudflare-protected sources will simply fail gracefully and the remaining sources will continue to work normally.
