# Cyclone Murasu: Telugu and English streams

This patch makes the India desk follow Cyclone Murasu, and adds an English stream with an Indian English voice.
It applies on top of `typhoon_champi` (5f7a25c) and changes nothing else.

| Stream | Config | Voice | Status |
|---|---|---|---|
| Telugu | `saved_configs/india_te.json` | MMS-TTS Telugu (unchanged) | Ready |
| English | `saved_configs/india_en.json` | Indic Parler-TTS "Thoma" (Indian English) | Needs the voice installed and a test clip heard |

## What changed

- **Storm name follows the desk.** The Telugu and Tamil narration, the page title and the YouTube title, description and tags
  used to say "Arnab" everywhere. They now take `desk.json` storm.name and its Telugu / Tamil spelling from a small
  table, kept the same in three places: `IN_STORM` (`src/desk/bulletin.py`), `STORM_LOCAL` (`html/india-desk.html`) and
  `INDIA_STORM` (`scripts/youtube_live.py`). A storm missing from the table is called just "the cyclone", never a wrong name.
- **English narration** (`in_en_*` in `src/desk/bulletin.py`): the same IMD bulletin fields as the Telugu and Tamil
  streams, with IMD's own English place names, fixed wording, and no model writing it. Warnings cover Andhra Pradesh, Yanam and
  Telangana, like the Telugu stream.
- **Indian English voice** (`src/models/tts_indicparler.py`, engine `indic-parler` in `src/audio/audio.py`): AI4Bharat Indic
  Parler-TTS, voice "Thoma", brisk delivery with a sense of urgency. The landfall and warnings scenes use `Thoma:urgent`
  (faster and more emphatic). Numbers, units and dates are written out the way a newsreader says them.
- **English page**: `html/india-desk.html?lang=en`, with the Andhra Pradesh map, radars and district board.
- **IMD parser fixes for Murasu's bulletins** (`src/desk/sources_nio.py`, both streams): Murasu's bulletins word things
  Arnab's did not ("lay centered at 0230 hours IST", "Latitude", "moved nearly northwestwards with speed of", "100 to 110
  kmph gusting 120 kmph", "midnight (2330 Hrs IST) of 2nd to early hours (0400 Hrs IST) of 3rd"). Without the fixes the
  narration lost the storm's position, motion, landfall winds and landfall time, and called it a Cyclonic Storm after IMD had
  upgraded it ("intensified into a severe cyclonic storm"). IMD's "midnight of 2nd" now means 23:00 on the 2nd, not 00:00 (a day
  early, which would have flipped the thumbnail to its after-landfall words while the storm was still at sea).
- **Thumbnails** (`html/thumb-in.html`, the Arnab engine): English (`lang=en`), Murasu's towns (Ongole, Nellore, Narsapur,
  Bapatla, Kavali), and the landfall marker on IMD's "near" town from desk.json instead of a fixed Kakinada. Words per stream in
  `saved_configs/thumb_murasu_te.json` and `thumb_murasu_en.json` (below).
- **YouTube metadata**: an India-English title, description and tags (`scripts/youtube_live.py`, same pattern as Telugu), so the
  English stream needs no `YOUTUBE_TITLE` (which turns off the hourly thumbnail refresh). The Telugu tags use IMD's landfall
  town (Ongole) instead of Arnab's Kakinada and Yanam.
- Tests: `tests/desk/test_india_en.py` (10 tests, offline), including Murasu's 0500 IST 2 Nov bulletin as a fixture.

## 1. Before anything goes live

1. Apply the patch on a fresh branch, never on the running checkout:
   `git checkout -b murasu typhoon_champi && git apply indian_english_voice.patch`
2. Telugu spelling of Murasu: మురసు (checked by a Telugu speaker; Tamil முரசு). To change it, edit all three tables listed above.
3. Run the tests: `PYTHONPATH=src $PY -m pytest -q tests/desk/test_india_en.py tests/desk/test_nio.py`
4. Follow Murasu, not Arnab: `DESK_STORM=MURASU DESK_JTWC_ID=io0426` (JTWC 04B). Use the same desk setup as for Arnab
   (`DESK_REGION=nio`). IMD (0500 IST 2 Nov): landfall between Nellore and Narsapur, close to Ongole, 2330 IST 2 Nov to 0400
   IST 3 Nov, 100-110 km/h gusting 120. Check the page shows Ongole, not Kakinada.

## 2. Telugu stream

Launch it the same way as the Arnab Telugu stream, with Murasu's desk variables from step 1.4. Following `ec2/README.md`:

```bash
DESK_REGION=nio DESK_STORM=MURASU DESK_JTWC_ID=io0426 EC2_STREAM_ID=india-te RUN_ID=murasu-te \
  CONFIG_PATH=saved_configs/india_te.json bash scripts/run_livestream.sh
THUMB_STYLE=tw THUMB_TW_TEXT=saved_configs/thumb_murasu_te.json \
  $PY scripts/youtube_live.py --config saved_configs/india_te.json --lang te --stream india-te
```

Check the YouTube title says "Cyclone Murasu LIVE 🔴 దూసుకొస్తున్న మురసు తుఫాన్.. | ...", and that the page shows మురసు తుఫాన్.

## 3. English stream

**Hugging Face token (once, one person).** The model is AI4Bharat's (IIT Madras) and gated: Hugging Face shares the
downloader's username and email with AI4Bharat. The token is only for the download; the streams then load it offline.
1. Sign in at huggingface.co, open https://huggingface.co/ai4bharat/indic-parler-tts and click "Agree and access repository".
2. https://huggingface.co/settings/tokens → Create new token → type **Read** → copy it (`hf_...`, shown once).
   Already have a token? It works once the same account has done step 1. A classic Read token is fine; a fine-grained
   token needs "Read access to contents of all public gated repos you can access" ticked, or the download fails with 401/403.
3. Use it in the download command below. Never commit or share it; delete it on the same page once the model is downloaded.
The downloaded folder (Apache 2.0) can be copied to other machines; no one else needs an account.

**If someone else downloads it for you** (no account or token on your side):
- They run, on their own account (`uvx` is uv's runner; any Python with `huggingface_hub` works too):
  `HF_TOKEN=hf_... uvx --from huggingface_hub hf download ai4bharat/indic-parler-tts --local-dir ~/pre-models/indic-parler-tts`
  then share the folder (about 3.5 GB): make it readable on this machine
  (`chmod o+x ~ ~/pre-models && chmod -R o+rX ~/pre-models/indic-parler-tts`), or send it by rsync / shared drive.
- You copy it into place and run the script below **without** `HF_TOKEN`: it sees the model, skips the gated download,
  installs parler-tts and saves the public description tokenizer.
  `cp -r /home/<them>/pre-models/indic-parler-tts /home/andyshi2/pre-models/`

**3a. Install the voice in a separate environment.** `parler-tts` pins its own `transformers` version, and installing it
into `ai-livestream` could break vLLM and the MMS voice for the Telugu stream.

```bash
conda create -y --clone ai-livestream -n ai-livestream-parler
PY=/home/andyshi2/.conda/envs/ai-livestream-parler/bin/python
# accept the terms once at https://huggingface.co/ai4bharat/indic-parler-tts, then with a read token:
PY=$PY HF_TOKEN=hf_... bash scripts/indic_parler_download.sh       # model into ~/pre-models/indic-parler-tts (about 3.5 GB)
# or, with the folder already copied in: PY=$PY bash scripts/indic_parler_download.sh   (no token)
```

**3b. Listen to a test clip** (both deliveries) before going live:

```bash
PYTHONPATH=src $PY - <<'EOF'
import soundfile as sf
from models import tts_indicparler as T
text = ("Severe Cyclonic Storm Murasu is centred about 330 km southeast of Ongole. The India Meteorological Department expects "
        "it to cross the coast near Ongole, between 11:30 pm on 2 November and 4 am IST on 3 November. Winds could reach 100-110 km/h.")
for voice in ("Thoma", "Thoma:urgent"):
    audio, rate = T.synthesize(text, "en", voice=voice)
    sf.write(f"murasu_{voice.replace(':', '_')}.wav", audio, rate)
EOF
```

Check how long generation takes and how much GPU memory is used (`nvidia-smi`) while vLLM is up. vLLM takes 62% of the
slice; on a 32 GB slice that leaves about 12 GB, and the voice needs about 4 GB plus working memory.

**3c. Run it**, with the new environment's Python:

```bash
PY=$PY DESK_REGION=nio DESK_STORM=MURASU DESK_JTWC_ID=io0426 EC2_STREAM_ID=india-en RUN_ID=murasu-en \
  CONFIG_PATH=saved_configs/india_en.json bash scripts/run_livestream.sh
THUMB_STYLE=tw THUMB_TW_TEXT=saved_configs/thumb_murasu_en.json THUMB_CDP_PORT=9334 \
  $PY scripts/youtube_live.py --config saved_configs/india_en.json --lang en --stream india-en
```

The title comes out as "Cyclone Murasu LIVE 🔴 Heads For Andhra | Winds Up To 120 km/h | Ongole Landfall | IMD Updates 2/11".
Don't set `YOUTUBE_TITLE`: it turns off the hourly thumbnail refresh, and the countdown would freeze.
`THUMB_CDP_PORT=9334` keeps its headless browser apart from the Telugu launcher's (9333) when both render at once.
Open the page once with `?lang=en` and check that the map, numbers and district board show.

## 4. Thumbnails

Same engine as Arnab's (`html/thumb-in.html`, news look): tonight's Himawari infrared, Andhra Pradesh in red, a marker on IMD's
landfall town (Ongole) and two big lines. `#H` (hours to IMD's landfall time), `#GUST` (IMD's landfall gust) and `#RED`
(red-alert districts) are filled from desk.json at every hourly refresh, never typed.

| | Before landfall | From IMD's landfall time (2330 IST 2 Nov) |
|---|---|---|
| Telugu | IMD: #H గంటల్లో తీరం దాటే అవకాశం / దూసుకొస్తున్న మురసు తుఫాన్.. / గంటకు #GUST కి.మీ వేగంతో గాలులు.. | IMD తాజా బులెటిన్ • LIVE / తీరం వద్ద మురసు తుఫాన్.. |
| English | IMD: LANDFALL IN #H HOURS / CYCLONE MURASU HEADS FOR ANDHRA / WINDS UP TO #GUST KM/H | IMD: LATEST BULLETIN • LIVE / CYCLONE MURASU AT ANDHRA COAST |

The after-landfall words say "at the coast", not "has crossed": the switch happens at the start of IMD's window, and the
crossing is IMD's to announce. When IMD says it has crossed, edit `a_l1` in the two JSON files (the next refresh picks it up).
Wording rules from `research/market/thumbnails_india.md`: only IMD's numbers, no "hits" before it has, no stock disaster art.

To preview a thumbnail before going live: `THUMB_STYLE=tw THUMB_TW_TEXT=saved_configs/thumb_murasu_en.json EC2_STREAM_ID=india-en
$PY scripts/youtube_thumbnail.py --lang en` (writes `output/youtube/thumb_en.jpg`).

**If the voice fails tonight:** in `saved_configs/india_en.json` set `"tts_model": "kokoro"`. The English narration stays,
read with Kokoro's default voice (American accent; the Thoma voice names fall back to it automatically).

## Not tested yet

- The Indic Parler-TTS voice has not produced audio (the model is gated; no token on the machine the patch was written on).
- The English page has been syntax-checked, not viewed in a browser with live data.
- The thumbnails were rendered from live data (IMD's 0500 IST 2 Nov bulletin, Himawari 0130 UTC) in a headless Chromium on
  another machine, not through `youtube_thumbnail.py` and the encoder container.
- No full run of either stream with this patch.

Notes: the Telugu voice (MMS-TTS) is licensed CC-BY-NC (non-commercial). Indic Parler-TTS is Apache 2.0.
