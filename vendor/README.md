# Vendored files

Three variable fonts and one map file, with their licences, pinned as bytes in this repository. The site makes
no request to any third party: nothing is loaded from a font service or a map server, and there is no chart
library here (the charts are SVG drawn by `src/charts.js`).

The stylesheet loads each font with a path relative to itself, `../vendor/...` from `styles/tokens.css`, and
`index.html` preloads two of them with `vendor/...`. The site is served from
`https://nathancouturier.github.io/voyage-tce-model/`, a subpath, so a leading slash in any of those URLs would
break it; `tools/check-paths.mjs` fails on one.

## Where the bytes came from

Copied byte for byte on 2026-10-29 from the sibling repository `jkm-ttf-arbitrage`, whose `vendor/README.md`
records the same hashes and the original fetch (Google Fonts' own `latin` cuts for the faces; the world-atlas
package for the land). Nothing was subset, converted or renamed. The same bytes in the sibling repositories mean
the sites draw the same letters.

| Path | Bytes | sha256 |
|---|---|---|
| `fraunces/fraunces.v1.000.latin.woff2` | 67,304 | `7234ed860a9cc83045413c4faee63c960a8f2d1917adcf728119307d56e0d783` |
| `fraunces/LICENSE` | 4,391 | `bdf4c22802eaf804f998195871c6b8938aac2ac14b2d78a8bd66a6f1eced833b` |
| `jetbrains-mono/jetbrains-mono.v2.211.latin.woff2` | 40,404 | `18be452724bfdc236c074ca94a249a7f41a86752c7d04ab258ce9ed5651f6a7e` |
| `jetbrains-mono/LICENSE` | 4,399 | `b2fe5e8987594e9ffd1d2ca52a2f5d73eb8335243893c5d6254b5ad69269591d` |
| `figtree/figtree.v2.002.latin.woff2` | 20,156 | `4ba7d3d096695818fe0686be4f1e82c6b05134e18a22260336130335027462dd` |
| `figtree/LICENSE` | 4,388 | `140d37233e7f3ce7313798befa9600893bcceaf41a55fa0fa5ad52f7f657a268` |
| `world-atlas/land-110m.json` | 55,207 | `ead5f68119c49a9250902e7da303bcb209341bbb8fefe7369a439b48b704658a` |
| `world-atlas/LICENSE` | 734 | `8048290dfdb6e83fbed17e8985c8cfc4ce9da9b842642f3d3e497280790cfa31` |

To check again: `sha256sum vendor/*/*`.

| File | Version | Licence | Upstream |
|---|---|---|---|
| Fraunces | 1.000 | SIL Open Font License 1.1, copyright 2018 The Fraunces Project Authors | `https://github.com/undercasetype/Fraunces` |
| JetBrains Mono | 2.211 | SIL Open Font License 1.1, copyright 2020 The JetBrains Mono Project Authors | `https://github.com/JetBrains/JetBrainsMono` |
| Figtree | 2.002 | SIL Open Font License 1.1, copyright 2022 The Figtree Project Authors | `https://github.com/erikdkennedy/figtree` |
| world-atlas land 110m | 2.0.2 | ISC, copyright Michael Bostock; Natural Earth data in the public domain | `https://github.com/topojson/world-atlas` |

The OFL allows bundling and redistribution with software provided the licence travels with the font, which is
why each `LICENSE` sits beside its file. The land file is read at build time only, by `src/voyage/routemap.py`,
which projects it into the paths of `data/map.json`; the page never requests it.

## Roles and traps

| Face | Used for | Weights set in CSS |
|---|---|---|
| Fraunces | view titles and the verdict | 400 verdict, 500 view titles |
| Figtree | every word, figures inside a sentence, the overview's three facts | 400, 500, 600 |
| JetBrains Mono | figures in table cells and tick values on axes, nothing else | 400, 600 for totals |

1. Fraunces' default instance is Black 900 at optical size 9, so every rule that names it sets `font-weight`,
   and `font-variation-settings` is never written.
2. Figtree's default instance is Light 300 with proportional digits: the body sets weight 400, and every element
   that can hold a figure in running text sets `font-variant-numeric: tabular-nums lining-nums`.
3. None of the three carries the sun or moon of the theme toggle, or U+FE0E; the toggle uses the system face.

Body text is set in Figtree, an open licensed stand in for Satoshi, the portfolio's face, whose licence does not
allow a copy in a public repository.
