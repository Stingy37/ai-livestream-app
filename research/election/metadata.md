# YouTube metadata: election-night Senate streams (es / ja / zh), Tue 2026-11-03

Drafted 2026-11-03 for go-live at about 23:00 UTC. Nothing has been set on YouTube yet: no broadcast or video was
created or edited. Rules applied: `research/election/legal.md` 14-18, 23, 27, 42, 43 and 46. The thumbnail approach
follows `thumbnail-ctr-preference`: urgent hooks that are true.

## At a glance

| lang | recommended title | thumbnail |
|---|---|---|
| es | 🔴 EN VIVO \| Resultados elecciones medio término 2026: ¿quién controlará el Senado? Desde 7 PM ET | `output/election/thumbs/thumb_election_es.png` |
| ja | 【LIVE】米中間選挙2026 開票速報｜上院の主導権は？ 日本時間4日(水)朝9時〜｜テキサス・オハイオ・ミシガンなど6州 | `output/election/thumbs/thumb_election_ja.png` |
| zh | 【直播】2026美国中期选举开票｜参议院控制权花落谁家？新马·北京时间11月4日早8点起｜得州、俄亥俄、密歇根等6州 | `output/election/thumbs/thumb_election_zh.png` |

**Time hooks.** 7 PM ET (00:00 UTC Nov 4) is when the first states close all their polls (GA, KY, SC, VA). That
equals 6 PM in Mexico City, 09:00 JST and 08:00 in Singapore, Malaysia and Beijing. The stream shows its first
statuses and any relayed AP declarations from that time; Ohio's count follows at 7:30 PM ET.

Every hook is phrased "from X", so it stays true all night and the thumbnail never needs a re-upload. Kentucky's
Eastern-time counties close at 6 PM ET, but rule 27 keeps any state off screen until its last close, so the stream's
first results really are at 7 PM ET.

## 1. Competitor titles: what the market uses

**Sources.** The streams below come from the cached `measure.py` search results in `research/market/cache5`,
collected 2026-11-01. They are completed live streams with lifetime views; no YouTube API quota was spent tonight.
Three web searches found no announced 2026 streams. The only 2026 item found: SmartNews (with Kyodo) runs a 開票速報
page "from the morning of the 4th, JST".

**Japanese.** The bracket tag comes first: 【開票ライブ】 or 【LIVE】. Then アメリカ/米 + 中間選挙 or 大統領選挙, then
開票速報.
- TBS NEWS DIG (1.34M views, 2024): 【開票ライブ】アメリカ大統領選挙 リアルタイム開票速報…
- 日テレNEWS (1.59M, 2024): 【開票ライブ】『アメリカ大統領選挙』とことん開票…
- ニコニコニュース (177k, 2024): 【LIVE】トランプかハリスか…開票特番
- 2022 midterms, small channels: 山中泉 (20.7k) 中間選挙、開票速報; やすの米国株 (5.9k) [LIVE] 米国中間選挙。開票ライブ！; 旅野そら (61k, 2024) 【LIVE】アメリカ大統領選・開票速報！
- Pattern: front-loaded keywords, the topic as a question (勝敗は？, 誰が…?), named swing states.

**Simplified Chinese.** Titles use 美国中期选举 or 美国大选, then 开票直播 or 开票夜. Taiwan writes 期中選舉 in Traditional
characters; mainland, Singapore and Malaysia write 中期选举.
- FearNation (23.7k, 2024): [LIVE SPECIAL] 2024美国总统大选开票直播
- SinoVision 美国中文电视 (904k, 2024): 【直播完整版】2024美国大选开票夜直击
- 快点新闻 (13k, 2024): 开票了…2024美国大选开票直播
- 詢經問道 (11k, 2022): 美国2022中期选举直播：红潮涌动美利坚？ (红潮 is banned for us, rule 38)
- TVBS (Traditional): 參議院戰況拉鋸LIVE (2022). Its 2024 title 美參議院變天 is loaded, so we avoid it.

**Spanish.**
- Most titles lead with 🔴 EN VIVO, then Resultados / elecciones de medio término + EE.UU. or Estados Unidos.
- Mexican outlets say "intermedias"; Spain and AP en español say "mitad de mandato".
- Examples:
  - N+ Univision (138k, 2022): 🔴 En vivo: Cobertura especial en la noche de las elecciones de medio término en EEUU
  - Univision Orlando (7.8k, 2024): 🔴 EN VIVO | Comienzan a fluir los resultados de las Elecciones de Estados Unidos 2024
  - Univision LA (3.3k, 2022): 🔴 EN VIVO: Elecciones Medio Término 2022 California
  - Voz de América (626k, 2024): EN VIVO | Cierre de centros y resultados de elecciones Estados Unidos 2024…
- Telemundo's 2022 title carries its brand "Decisión 2022" (the NBC "Decision" mark, rule 16), so "Decisión 2026" is off
  limits.
- Several small 2024 channels used "Impactantes" or "FOX NEWS PROYECTA". Both are banned for us (rules 16, 38, 43).

## 2. Titles (3 options each; ★ = recommended)

Lengths are UTF-16 units, the way `scripts/youtube_live.py` checks them; YouTube's limit is 100. Phones cut a title at
about 40 characters, so every option puts LIVE, the election name and results first.

**Spanish**
- ★ `🔴 EN VIVO | Resultados elecciones medio término 2026: ¿quién controlará el Senado? Desde 7 PM ET` (97)
- `EN VIVO: Elecciones de medio término 2026 | Resultados del Senado en Texas, Ohio, Míchigan y más` (96)
- `Resultados EN VIVO: ¿Quién controlará el Senado de EE.UU.? Elecciones de medio término 2026` (91)

Why ★: it matches the Univision search pattern, puts the Senate-control question to viewers and carries the true start
time. Option 2 is the alternative if Texas interest is the bigger draw.

**Japanese**
- ★ `【LIVE】米中間選挙2026 開票速報｜上院の主導権は？ 日本時間4日(水)朝9時〜｜テキサス・オハイオ・ミシガンなど6州` (62)
- `【開票ライブ】米中間選挙 上院選｜11/4(水)9時から順次締め切り｜テキサス・アラスカ・カンザス・メーン・オハイオ・ミシガン` (63)
- `米中間選挙2026 開票速報【LIVE】上院の過半数はどちらに？ 各州選挙当局の集計を随時更新｜AI音声解説` (54)

Why ★: the first 40 characters hold 【LIVE】 + 米中間選挙 + 開票速報 + the Senate-control question. It also names the
Japanese-daytime hook and familiar states.

**Simplified Chinese**
- ★ `【直播】2026美国中期选举开票｜参议院控制权花落谁家？新马·北京时间11月4日早8点起｜得州、俄亥俄、密歇根等6州` (58)
- `2026美国中期选举开票直播｜参议院六州计票：得州、阿拉斯加、堪萨斯、缅因、俄亥俄、密歇根｜持续更新` (50)
- `【LIVE】美国中期选举开票直播 参议院多数党之争｜新马·北京时间4日(周三)早8点起｜各州选举机构计票` (52)

Why ★: it uses the mainland and Singapore/Malaysia spelling 中期选举 and a neutral question (花落谁家 = "who will it go
to"). The local-time hook targets the Singapore and Malaysia audience.

**Checked against the rules:**
- No winner, no "projected / proyecta / 当確", no network or brand names, no "Official / 公式 / oficial" (rules 16, 18,
  43).
- No banned hype words (rule 38).
- I left out "real-time" (リアルタイム / 实时): scenes show a data snapshot and only the ticker is newer, so 随時更新 /
  持续更新 is the honest wording.
- After AP declares a race, any title change must use AP-attributed wording (rule 3), or simply leave the title alone.

## 3. Descriptions (rule 46: sources, AI disclosure, unofficial results, not affiliated, corrections)

### es

```
Resultados en vivo de las elecciones al Senado de EE.UU. del martes 3 de noviembre de 2026. Empezamos con el mapa nacional y el balance de poder, y seguimos con Texas, Alaska, Kansas, Maine, Ohio y Míchigan: votos contados, mapas por condado (en Alaska, por distrito) y la comparación con 2024.

Antes de la elección, el Senado tiene 53 republicanos, 45 demócratas y 2 independientes que votan con los demócratas; hay 35 escaños en juego. La mayoría es de 51 escaños (o 50 más el voto de desempate del vicepresidente).

Cierre de urnas (hora del Este; en Ciudad de México, una hora menos): Ohio 7:30 PM · Maine 8 PM · Texas, Kansas y Míchigan: la mayoría a las 8 PM y las últimas a las 9 PM · Alaska 1 AM del miércoles. No mostramos cifras de un estado hasta que cierran todas sus urnas. Maine y Alaska votan por orden de preferencia: mostramos los votos de primera preferencia.

■ Fuentes
• Votos: las oficinas electorales de cada estado (Secretaría de Estado de Texas, División de Elecciones de Alaska, Secretaría de Estado de Kansas, Secretaría de Estado de Maine, Secretaría de Estado de Ohio, Oficina de Elecciones de Míchigan). Si un estado no publica su conteo o no podemos acceder a él, lo decimos en pantalla.
• Ganadores: solo cuando The Associated Press (AP) declara un ganador, según informes de prensa publicados y con atribución en pantalla. No hacemos proyecciones propias.
• Historial: resultados certificados (oficinas estatales, Comisión Federal de Elecciones, MIT Election Data + Science Lab). Mapas: Oficina del Censo de EE.UU. Composición del Senado: senate.gov.

■ Aviso
Guion escrito con IA y leído por una voz sintética. Resultados no oficiales de las oficinas electorales estatales; solo son definitivos cuando se certifican. Sin afiliación con ningún medio, campaña ni gobierno.

■ Correcciones
Ninguna por ahora. Si cometemos un error, lo corregimos en la siguiente pasada de esa sección y lo anotamos aquí con la hora (ET).

#EleccionesEEUU #MedioTérmino #Senado
```

### ja

```
2026年米中間選挙（現地11月3日投票）の上院選を、各州選挙当局の集計をもとにライブでお伝えします。全米の上院の勢力図から、テキサス、アラスカ、カンザス、メーン、オハイオ、ミシガンの6州へ。得票数、郡ごとの地図（アラスカは選挙区ごと）、2024年大統領選との比較を随時更新します。

選挙前の上院は共和党53、民主党45、民主党と会派を組む無所属2。改選は35議席です。過半数は51議席（50議席でも副大統領の決定票で多数派となります）。

投票締め切り（日本時間11月4日）：オハイオ 9:30／メーン 10:00／テキサス・カンザス・ミシガン 大部分10:00、全域11:00／アラスカ 15:00。各州の投票がすべて締め切られるまで、その州の数字は表示しません。メーンとアラスカは順位付け投票のため、第1希望の票数をお伝えします。

■ 出典
・得票数：各州の選挙当局（テキサス州務長官室、アラスカ州選挙管理局、カンザス州務長官室、メーン州務長官室、オハイオ州務長官室、ミシガン州選挙局）。集計が公表されていない、または取得できない州は、その旨を画面でお伝えします。
・当選：AP通信が当選を伝えた場合のみ、公表された報道をもとに出典を明示してお伝えします。独自の当選判定はしません。
・過去の結果：各州・米連邦選挙委員会・MIT Election Data + Science Lab の確定結果。地図：米国勢調査局。上院の構成：senate.gov。

■ ご注意
原稿はAIが作成し、合成音声で読み上げています。数字は各州選挙当局の非公式開票結果です（各州の認定で確定します）。報道機関・陣営・政府とは無関係です。

■ 訂正
現在、訂正はありません。誤りがあった場合は、その州の次の回の解説で訂正し、ここに時刻（日本時間）とともに記載します。

#米中間選挙 #開票速報 #上院選
```

### zh (Simplified)

```
2026年美国中期选举（美国当地时间11月3日投票）参议院开票直播。先看全美参议院地图与席位分布，再看得州、阿拉斯加州、堪萨斯州、缅因州、俄亥俄州、密歇根州六州：已计票数、各县地图（阿拉斯加为选区），以及与2024年的比较。

选前参议院：共和党53席、民主党45席、与民主党结盟的独立人士2席；本次改选35席。过半数为51席（50席加上副总统的决定票亦可掌控参议院）。

各州投票截止（新马·北京时间11月4日；美东时间为减13小时）：俄亥俄 8:30｜缅因 9:00｜得州、堪萨斯、密歇根 大部分9:00、全部10:00｜阿拉斯加 14:00。各州投票全部截止前，不显示该州数字。缅因和阿拉斯加采用排序复选制，直播显示第一选择票数。

■ 数据来源
· 票数：各州选举机构（得州州务卿办公室、阿拉斯加州选举处、堪萨斯州州务卿办公室、缅因州州务卿办公室、俄亥俄州州务卿办公室、密歇根州选举局）。如某州未公布计票或无法取得，画面上会说明。
· 胜选：仅在美联社（AP）宣布胜选时，依据已发表的新闻报道转述并注明出处。本节目不作任何胜选预测。
· 历史数据：各州、美国联邦选举委员会及 MIT Election Data + Science Lab 的认证结果；地图：美国人口普查局；参议院构成：senate.gov。

■ 声明
本节目由AI撰稿、合成语音播报。数据为各州选举机构公布的非正式计票结果（以各州认证为准）。与任何新闻机构、竞选阵营或政府无关。

■ 更正
目前无更正。如有错误，将在该州下一轮播报中更正，并在此注明时间。

#美国中期选举 #开票直播 #参议院
```

**Checks on the descriptions:**
- Disclosure: the AI-disclosure sentences are the legal.md s6b strings.
- Poll-closing times: they come from `data/election/races.json`, converted to the viewers' zones:
  - JST = ET+14
  - SGT/MYT/CST = ET+13
  - Mexico City = ET-1 (no DST since 2022)
- Unreachable counts: KS, MI and ME counts may stay unreachable (`docs/ELECTION.md`), so each description says the
  screen will say so.

## 4. Tags

Tag lengths are counted as len+2 against YouTube's 500 limit, the same way `scripts/youtube_live.py` counts them.
Candidate names are all-or-none: Spanish lists all 12 card candidates; Japanese and Chinese list none.

- **es** (478): elecciones de medio término, elecciones de medio término 2026, elecciones intermedias Estados Unidos,
  elecciones de mitad de mandato, resultados elecciones Estados Unidos, elecciones EE.UU. 2026, Senado de Estados Unidos,
  control del Senado, Texas, Alaska, Kansas, Maine, Ohio, Míchigan, Ken Paxton, James Talarico, Dan S. Sullivan,
  Mary Peltola, Roger Marshall, Adam Hamilton, Susan Collins, Troy Jackson, Jon Husted, Sherrod Brown, Mike Rogers,
  Abdul El-Sayed, midterms 2026
- **ja** (159): 米中間選挙, 中間選挙, アメリカ中間選挙, 米中間選挙2026, 中間選挙 開票速報, 開票速報, 開票ライブ, 上院選, アメリカ上院,
  上院 過半数, テキサス州, アラスカ州, カンザス州, メーン州, オハイオ州, ミシガン州, ライブ, US midterms 2026, Senate results
- **zh** (152): 美国中期选举, 2026美国中期选举, 中期选举, 期中选举, 美国中期选举开票, 开票直播, 美国参议院, 参议院选举, 参议院控制权,
  美国大选, 得州, 德州, 阿拉斯加, 堪萨斯, 缅因, 俄亥俄, 密歇根, 密西根, 直播, US midterms 2026, Senate results
  - 德州 and 密西根 are the Singapore/Taiwan spellings, included for search. On screen we use `races.json` zh_hans.

## 5. Thumbnails

**Files** (1280x720 PNG, about 0.5 MB each; YouTube's limit is 2 MB):
- `output/election/thumbs/thumb_election_es.png`
- `output/election/thumbs/thumb_election_ja.png`
- `output/election/thumbs/thumb_election_zh.png`

**Template and configs.** The template is `html/thumb-election.html`. The words live in
`saved_configs/thumb_election_<lang>.json` and are passed to the page as query parameters.

| element | es | ja | zh |
|---|---|---|---|
| big word | ● EN VIVO | 開票速報 | 开票直播 |
| Senate control | CONTROL DEL SENADO | 上院の主導権は？ | 参议院控制权 |
| time box | PRIMEROS RESULTADOS 7 PM ET / 6 PM CDMX | 日本時間 11/4(水) 9:00〜 | 新马·北京时间 11月4日 早8点起 |
| bar | DEMÓCRATAS · MAYORÍA: 51 · REPUBLICANOS | 民主党 · 過半数 51 · 共和党 | 民主党 · 过半数 51席 · 共和党 |

**Design.**
- **Ground and map.** Navy background. The US map comes from `html/election/geo/us-states.json`, drawn in Albers with
  Alaska and Hawaii insets.
  - States with a 2026 Senate race are lighter slate; the rest are darker.
  - The six featured states are gold and named in the stream's language.
- **Party colours.** Red and blue appear only in the balance bar, as two equal halves with a legend, Democrats on the
  left as in `visual_style.md`. The "51" mark sits in the middle. The bar shows no seat counts, so no side looks ahead.
- **Excluded.** No photos or faces, no AI art, no logos, no check marks and no network-style alert banners. The red
  LIVE chip is the generic YouTube convention.

**Checked:**
- **Phone sizes.** I viewed 320x180 and 168x94 contact sheets. The big word, the Senate-control line and the time box
  stay readable. The map labels don't at 168 px, but the gold states still show the six regions.
- **Corner badge.** I raised the bar clear of the bottom-right corner, so YouTube's LIVE/duration badge can't cover the
  red half.
- **Overflow guard.** The page refuses to render (it sets `data-thumb-error`) if the left column would hit the bar or a
  map label would leave the frame.

**How to re-render.** The page fetches `election/geo/us-states.json` relative to itself, so it must be served over HTTP
from `html/`. `scripts/youtube_thumbnail.py` has no election style, and I didn't change it. I rendered with the same
DevTools-protocol flow, in the yt-encoder container's headless Chromium at 1280x720:

```
/home/andyshi2/.conda/envs/ai-livestream/bin/python /tmp/claude-1338340/-home-andyshi2-ai-livestream-app/e5e82793-229a-44b9-a0ae-a7c064805d7f/scratchpad/render_election_thumbs.py [ja zh es]
```

The script uses HTTP port 8197 and DevTools port 9347. It is a session scratch file; copy it into `scripts/` if the
team wants to keep it.

## 6. Before publishing (reminders, not done here)

- Set `status.containsSyntheticMedia=true` with `videos.update` on each broadcast id (rule 24). Resend `privacyStatus`
  in the same call.
- If wording ever has to change mid-stream, ask first (performing title or thumbnail = frozen). The hooks above never
  go stale, so no refresh is planned.
- On a correction, add a timestamped line under ■ Correcciones / ■ 訂正 / ■ 更正 (rule 34).
