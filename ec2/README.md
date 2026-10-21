# EC2 broadcast server

One HTTPS server (`server.py`, Python 3.14 stdlib + boto3) on the dev instance
`ubuntu@54.221.147.143` (t3.micro, Ubuntu 26.04) does three jobs:

1. **Upload endpoint for ICRN** (`/api/v1/*`, bearer token): hands out short-lived presigned
   S3 PUT urls, then on `complete` downloads the package from S3, verifies it (sizes, sha256,
   wav headers, manifest rules) and atomically makes it the current package. A failed
   `complete` leaves the package on air untouched.
2. **Website** (`/` -> `html/champi-desk.html`): the Champi typhoon desk with the live layer
   that polls `/live/current.json` every 5 s, plays each scene's wav in playlist order, shows
   the scene headline in the lower third and the script as captions, and switches to a newer
   package at the next scene boundary.
3. **Package housekeeping**: keeps the `KEEP_PACKAGES` newest packages (never the one on air
   or the one the site reports playing), removes older ones locally and tries to delete them
   from S3. The dev instance role has no `s3:DeleteObject`, so S3 deletes are reported as
   `s3_delete_denied` until the policy is extended.

## Deploy / redeploy (from ICRN)

    bash ec2/deploy.sh          # or scripts/ec2_deploy.sh

Copies `server.py`, the unit and `html/`, keeps an existing API token / certificate (creates
them the first time), restarts `weather-livestream.service`, checks `/healthz`, and copies the
token and certificate back to `secrets/ec2_api_token` and `secrets/ec2_server.crt`.

## Reaching it

The security group `weather-livestream-dev-sg` currently only opens port 22, so the server is
reachable only through an SSH port forward until **inbound TCP 8443** is opened (and 443 if a
nicer url is wanted; the unit binds 8443):

    bash scripts/ec2_tunnel.sh                 # local https://127.0.0.1:18443/ -> EC2 :8443
    # or from a laptop:
    ssh -o IdentitiesOnly=yes -i ~/.ssh/weather-dev -L 8443:127.0.0.1:8443 ubuntu@54.221.147.143
    # then open https://localhost:8443/  (accept the self-signed certificate once)
    #   ?autoplay=1 for an OBS browser source, ?live=0 to disable the live layer, key L toggles it

`src/broadcast/publisher.py` tries the direct url first and starts the same tunnel by itself
when the direct url does not answer.

## Files on the instance

    /home/ubuntu/weather-livestream/server.py, html/      deployed code + site
    /etc/weather-livestream/env                           API_TOKEN, BUCKET, ... (owner ubuntu, 600)
    /etc/weather-livestream/tls/server.{crt,key}          self-signed, SANs: public IP, 127.0.0.1, public DNS, localhost
    /home/ubuntu/weather-livestream-data/packages/<id>/   downloaded packages (default stream)
    /home/ubuntu/weather-livestream-data/state.json       current / playing / retired (default stream)
    /home/ubuntu/weather-livestream-data/streams/<sid>/   the same layout for each named stream
    journalctl -u weather-livestream -f                   one log line per request

## API summary

    POST /api/v1/uploads                 {package_id, files:[{path, content_type, size, sha256}]} -> presigned PUT urls
    POST /api/v1/packages/<id>/complete  {manifest_key} -> {ok, activated, retired, s3_delete_denied} or 422 + problems
    GET  /api/v1/status                  current, playing, packages, retired, disk_free_mb
    POST /api/v1/retire                  {package_ids:[...]}
    GET  /healthz · GET /live/current.json · GET /live/<id>/<file> (Range ok) · POST /live/playback

Every route above also exists per stream: `/api/v1/streams/<sid>/...` and `/s/<sid>/live/...`.
`GET /streams.json` (public) lists the streams with something on air; `GET /api/v1/streams` (token) adds details.

## Streams (several broadcasts at once)

Each broadcast publishes into its own stream: packages, on-air package, retention (KEEP_PACKAGES each) and
desk.json are separate. The stream id is `[a-z0-9-]`, up to 32 characters; a stream appears the first time a
package or desk is published to it (MAX_STREAMS, default 16).

| | default stream | stream `japan` |
|---|---|---|
| page | `/` | `/s/japan/` (`?lang=ja` as usual) |
| live data | `/live/...` | `/s/japan/live/...` |
| api | `/api/v1/...` | `/api/v1/streams/japan/...` |
| S3 | `packages/<id>/` | `streams/japan/packages/<id>/` |
| on the instance | `weather-livestream-data/` | `weather-livestream-data/streams/japan/` |

The page uses relative urls, so the same champi-desk.html serves every stream. A stream that never published a
desk.json is served the default stream's: run one desk updater (no EC2_STREAM_ID) for a storm all streams cover,
or give a stream its own. Package S3 keys are always derived by the server from the file name inside the stream's
prefix (a manifest cannot point outside its stream). The instance role's `bucket/*` grant covers the new prefixes.

On ICRN, one launcher per stream, each with its own RUN_ID and EC2_STREAM_ID:

    EC2_STREAM_ID=japan RUN_ID=jp-1 CONFIG_PATH=saved_configs/japan.json bash scripts/run_livestream.sh
    EC2_STREAM_ID=taiwan RUN_ID=tw-1 CONFIG_PATH=saved_configs/taiwan.json bash scripts/run_livestream.sh
    python scripts/youtube_live.py --config saved_configs/japan.json --lang ja --stream japan

`--stream` (or EC2_STREAM_ID) points the encoder and the thumbnail at `/s/<sid>/`; each stream's encoder gets its
own virtual display, PulseAudio port and log folder (`.run/encoder/<sid>/`); stop one broadcast with
`touch .run/STOP_YOUTUBE_<sid>`. Watch one with `EC2_STREAM_ID=japan RUN_ID=jp-1 bash scripts/stream_watch.sh`.
GPU limits for several streams on one box: see the capacity notes (one shared vLLM; one Kokoro per stream per scene
worker is the bottleneck).
