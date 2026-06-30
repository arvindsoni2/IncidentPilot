# Third-party static assets

## HTMX

- File: `agent/static/htmx-2.0.8.min.js`
- Version: 2.0.8
- Upstream: `https://unpkg.com/htmx.org@2.0.8/dist/htmx.min.js`
- License: BSD 2-Clause
- SHA-256: `22283ef68cb7545914f0a88a1bdedc7256a703d1d580c1d255217d0a50d31313`

The asset is committed so the localhost dashboard and its partial updates do
not depend on internet access. To verify a replacement before committing it:

```bash
sha256sum agent/static/htmx-2.0.8.min.js
```
