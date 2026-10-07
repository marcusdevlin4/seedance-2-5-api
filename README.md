# Seedance 2.5 API — $0.0874/s (480p) to $0.483/s (1080p)

**ByteDance Seedance 2.5 is live on [ArgoLink](https://argolink.io/gh-seedance-2-5-api)**: $0.0874/s at 480p, $0.196/s at 720p and $0.483/s at 1080p, 15% below the BytePlus list price. A prompt, frames, images, video and audio go in; one MP4 of 4–30 seconds with a generated soundtrack comes out.

[Model page](https://argolink.io/en/models/seedance-2.5) · [OpenAPI spec](./openapi.yaml) · [Endpoints](#endpoints) · [Request fields](#request-fields) · [Errors](#errors) · [FAQ](#faq)

This repository is an integration reference for the Seedance 2.5 video API: a machine-readable [OpenAPI 3.1 spec](./openapi.yaml), one request body per mode in [`examples/`](./examples), and the field, billing and error tables you need to integrate it. Every fact was checked against the live [model page](https://argolink.io/en/models/seedance-2.5) and [API guide](https://argolink.io/en/docs#/seedance).

<sub>Last checked: 2026-10-07. Where this page and the live documentation differ, the live documentation is right.</sub>

## At a glance

| | |
|---|---|
| Model ID | `seedance-2.5` (BytePlus ModelArk lists the same model as `dreamina-seedance-2-5-260628`) |
| Base URL | `https://argolink.io/v1` |
| Auth | `Authorization: Bearer <API key>` |
| Flow | asynchronous: submit → poll → download; no webhook |
| Modes | text · first frame · first + last frame · reference (images, video, audio) · video edit |
| Duration | 4–30 s in whole seconds, 5 if omitted |
| Resolution | 480p, 720p (default), 1080p; a 16:9 clip at 720p is 1280×720 |
| Aspect ratio | 21:9, 16:9 (default), 4:3, 1:1, 3:4, 9:16; frame modes use `adaptive` |
| References | ≤ 30 images, ≤ 10 videos, ≤ 10 audio clips, ≤ 50 in total; audio may be the only reference |
| Output | one 24 fps H.264 MP4 per request with an AAC stereo track (44.1 kHz) unless `generate_audio` is `false` |
| Request limits | prompt ≤ 40,000 bytes; JSON body < 1 MiB; HTTPS URLs only |
| Generation time | about 2–5 minutes for a 4–10 s clip, longer when the queue is busy |
| Parallel jobs | up to 50 per account |

## Endpoints

| Method | Path | Key | Success | Purpose |
|---|---|---|---|---|
| `POST` | `/v1/media/uploads` | yes | upload ticket | presigned PUT URL for a local file; free, creates no job |
| `POST` | `/v1/videos/generations` | yes | `202` `{"request_id": "…"}` | start a job |
| `GET` | `/v1/videos/{request_id}` | same user | `200` job object | status, progress, ETA, usage, error |
| `GET` | `/v1/videos/{request_id}/content` | same user | `200` `video/mp4` | stream the MP4; `Range` supported |
| `GET` | `/v1/models` | no | `200` list | public model list in the OpenAI shape |

Status and content lookups check ownership: a key of another user gets `404`, and so does a guessed ID.

## Pricing

Price per second of output for a request without video input, 16:9.

| Provider | How it bills | 480p | 720p | 1080p | 10 s at 720p |
|---|---|---:|---:|---:|---:|
| **[ArgoLink](https://argolink.io/en/models/seedance-2.5)** | per second | **$0.0874** | **$0.196** | **$0.483** | **$1.96** |
| [BytePlus ModelArk](https://docs.byteplus.com/en/docs/modelark/model-pricing) (official) | $10.70 per million tokens ($11.70 at 1080p) | $0.1028 | $0.2311 | $0.5686 | $2.31 |
| [Replicate](https://replicate.com/bytedance/seedance-2.5) | per second | $0.1028 | $0.2312 | — | $2.31 |
| [OpenRouter](https://openrouter.ai/bytedance/seedance-2.5) | BytePlus token rate, plus 5.5% on card top-ups | $0.1028 | $0.2311 | — | $2.31 + fee |
| [fal.ai](https://fal.ai/models/bytedance/seedance-2.5/text-to-video) | $0.0214 per 1,000 tokens ($0.0234 at 1080p) | $0.2205 | $0.4730 | $1.164 | $4.73 |

<sub>All pages read on 2026-10-07. BytePlus's per-second figures are its token price applied to a 16:9 frame at 24 fps; its own 5-second examples round them to $0.103, $0.231 and $0.569. Replicate's price list and OpenRouter's model FAQ cover 480p and 720p only. OpenRouter's fee is from its [FAQ](https://openrouter.ai/docs/faq). Prices change; re-read the linked pages before you budget.</sub>

### How a job is billed

- **Billed seconds = output seconds + reference-video seconds.** The output is rounded to whole seconds; reference videos are added up with any part of a second dropped. The total is multiplied by the rate of the resolution.
- **Reference images, reference audio and uploads are free.**
- **An edit counts its source twice**, as output and as a reference video: editing a 5 s clip at 720p bills 10 s, $1.96.
- **Leaving `duration` out** renders and bills 5 seconds.
- **Nothing is charged for a job that fails or expires.** The charge is made once, when the status first reads `done`, for `usage.billed_seconds`.

Worked examples at 720p: an 8 s text-to-video clip bills 8 × $0.196 = $1.568; a 4 s clip with a 3 s reference video bills 7 s, $1.372; a 30 s clip bills $5.88.

## Quick start

Create a key at [argolink.io/app/keys](https://argolink.io/app/keys), then:

```bash
export SEEDANCE_API_KEY=your-key
BASE=https://argolink.io/v1
AUTH="Authorization: Bearer $SEEDANCE_API_KEY"

# 1. Submit one of the bodies in examples/ (HTTP 202)
REQUEST_ID=$(curl -fsS "$BASE/videos/generations" -H "$AUTH" \
  -H "Content-Type: application/json" -d @examples/text-to-video.json | jq -r .request_id)

# 2. Poll every 10 s until the job leaves "pending"
while STATUS=$(curl -fsS "$BASE/videos/$REQUEST_ID" -H "$AUTH" | jq -r .status); [ "$STATUS" = pending ]; do
  sleep 10
done
[ "$STATUS" = done ] || { curl -fsS "$BASE/videos/$REQUEST_ID" -H "$AUTH" | jq .error; exit 1; }

# 3. Download
curl -fL "$BASE/videos/$REQUEST_ID/content" -H "$AUTH" -o boat.mp4
```

### Python

```python
import os
import time

import requests

BASE = "https://argolink.io/v1"
HEADERS = {"Authorization": f"Bearer {os.environ['SEEDANCE_API_KEY']}"}

submit = requests.post(f"{BASE}/videos/generations", headers=HEADERS, timeout=60, json={
    "model": "seedance-2.5",
    "prompt": "A paper boat drifts down a rain-filled gutter, macro lens, the camera follows it",
    "duration": 6,
    "resolution": "720p",
    "aspect_ratio": "9:16",
})
submit.raise_for_status()
request_id = submit.json()["request_id"]

while True:
    job = requests.get(f"{BASE}/videos/{request_id}", headers=HEADERS, timeout=30).json()
    if job["status"] != "pending":
        break
    print(f"{job.get('progress', 0)}%, about {job.get('estimated_seconds_remaining', '?')} s left")
    time.sleep(10)

if job["status"] != "done":
    raise SystemExit(f"{job['status']}: {job.get('error')}")

with requests.get(job["video"]["url"], headers=HEADERS, stream=True, timeout=600) as video:
    video.raise_for_status()
    with open("boat.mp4", "wb") as out:
        for chunk in video.iter_content(chunk_size=1 << 20):
            out.write(chunk)
print(job["usage"])  # {'billed_seconds': 6, 'output_seconds': 6, 'reference_video_seconds': 0}
```

### Node.js 18+

```js
// save as quickstart.mjs and run: node quickstart.mjs
import { writeFile } from "node:fs/promises";

const BASE = "https://argolink.io/v1";
const auth = { Authorization: `Bearer ${process.env.SEEDANCE_API_KEY}` };

const submit = await fetch(`${BASE}/videos/generations`, {
  method: "POST",
  headers: { ...auth, "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "seedance-2.5",
    prompt: "A hummingbird hovers at a red flower, slow motion, shallow depth of field",
    duration: 5,
    resolution: "480p",
  }),
});
if (!submit.ok) throw new Error(`${submit.status} ${await submit.text()}`);
const { request_id } = await submit.json();

let job;
do {
  await new Promise((resolve) => setTimeout(resolve, 10_000));
  job = await (await fetch(`${BASE}/videos/${request_id}`, { headers: auth })).json();
} while (job.status === "pending");
if (job.status !== "done") throw new Error(`${job.status}: ${JSON.stringify(job.error)}`);

const video = await fetch(job.video.url, { headers: auth });
if (!video.ok) throw new Error(`download failed: ${video.status}`);
await writeFile("hummingbird.mp4", Buffer.from(await video.arrayBuffer()));
console.log(job.usage);
```

## Request fields

| Field | Type | Default | Rules |
|---|---|---|---|
| `model` | string | — | `seedance-2.5` |
| `prompt` | string | — | required in every mode, ≤ 40,000 bytes UTF-8 |
| `duration` | integer | `5` | 4–30; leave it out of an edit |
| `resolution` | string | `720p` | `480p`, `720p` or `1080p` |
| `aspect_ratio` | string | `16:9` | `21:9` `16:9` `4:3` `1:1` `3:4` `9:16` for text and reference jobs; only `adaptive` with frames; leave it out of an edit |
| `size` | string | — | `WIDTHxHEIGHT` in place of resolution + ratio: `1280x720` is 720p 16:9; a resolution or ratio sent with it must agree |
| `start_image` | `{url}` | — | first frame; cannot be combined with reference lists |
| `end_image` | `{url}` | — | last frame; only together with `start_image` |
| `reference_images` | `[{url}]` | — | ≤ 30 |
| `reference_videos` | `[{url}]` | — | ≤ 10, 2–30 s each, 30 s together; billed like output |
| `reference_audios` | `[{url}]` | — | ≤ 10, 2–30 s each, 30 s together; free |
| `omni_reference_task_type` | string | — | `edit` edits `reference_videos[0]`; `auto` and `reference` change nothing; `extend` is rejected |
| `generate_audio` | boolean | `true` | `false` renders a silent clip |
| `n` | integer | `1` | only 1 |
| `seed`, `watermark: true` | — | — | not supported: `400` |

Requests written for fal or OpenRouter work unchanged: `image_url` and `end_image_url` stand for the two frames, `image_urls` / `video_urls` / `audio_urls` for the reference lists, `frame_images` and `input_references` for their OpenRouter equivalents, and `seconds` / `ratio` for `duration` / `aspect_ratio`. Give each input one name: two names for the same input with different values are rejected.

## Modes

The fields you send decide the mode. Each row links to a body you can post as it is.

| Mode | Send | `aspect_ratio` | Body |
|---|---|---|---|
| Text to video | `prompt` | fixed ratio | [text-to-video.json](./examples/text-to-video.json) |
| First frame | `start_image` | `adaptive` or omitted | [first-frame.json](./examples/first-frame.json) |
| First + last frame | `start_image` + `end_image` | `adaptive` or omitted | [first-last-frame.json](./examples/first-last-frame.json) |
| Reference | any mix of the three reference lists | fixed ratio | [reference.json](./examples/reference.json) |
| Audio-only reference | `reference_audios` alone | fixed ratio | [audio-reference.json](./examples/audio-reference.json) |
| Edit | `omni_reference_task_type: "edit"` + one `reference_videos` entry | from the source | [edit.json](./examples/edit.json) |

In the prompt, `@Image 2` means the second entry of `reference_images`, `@Video 1` the first reference video and `@Audio 1` the first audio clip. Unnamed references are still used. With `@`, a number past the end of its list is rejected. A first-frame video takes the ratio closest to its first frame; with two frames, the last one is adapted to the first.

## The job object

```json
{
  "request_id": "2f6c1d0e-8b1a-4c55-9f3e-6a0d7c9b5e21",
  "status": "done",
  "model": "seedance-2.5",
  "created_at": 1791370800,
  "progress": 100,
  "video": {"duration": 8, "url": "https://argolink.io/v1/videos/2f6c1d0e-8b1a-4c55-9f3e-6a0d7c9b5e21/content"},
  "usage": {"output_seconds": 8, "reference_video_seconds": 0, "billed_seconds": 8}
}
```

| `status` | Meaning | What to read |
|---|---|---|
| `pending` | queued or generating | `progress` 0–99 (it holds at 99 if the job runs past its forecast), `estimated_seconds_remaining` once there is a forecast |
| `done` | the MP4 is ready | `video.url`, `usage` |
| `failed` | nothing was produced, nothing is charged | `error.code`, `error.message`, `error.retryable`, `error.field` |
| `expired` | nothing was produced, nothing is charged | — |

Two clocks apply: a job that finds no capacity within 10 minutes of queueing fails with `capacity_unavailable`, and a job that has started generating ends with `generation_timeout` only after 24 hours.

## Errors

Request errors come back as `{"error": {"type", "code", "param", "message"}}`; `code` is stable and `param` names the offending field.

| HTTP | `type` / `code` | Cause | Retry? |
|---|---|---|---|
| 400 | `invalid_request_error` / `field_invalid`, `json_invalid` | malformed body: wrong type, neither a prompt nor media, `end_image` alone, frames mixed with references, a non-HTTPS URL | fix the request |
| 400 | `invalid_request_error` / `request_unsupported` | a valid shape the model does not take: resolution, duration, ratio, `seed`, asset counts, a mention past the end | fix the request |
| 401 | `authentication_error` | missing or wrong key | no |
| 402 / 403 | — | balance too low, or the key's group may not use video | top up or change key |
| 404 | `not_found_error` / `video_request_not_found` | unknown ID, or another user's job | no |
| 409 | `invalid_request_error` / `job_video_not_ready` | downloaded before `done` | yes, shortly |
| 424 | `invalid_request_error` / `job_failed` | downloaded a failed job | read the status |
| 429 | `rate_limit_error` | concurrency or rate limit | after running jobs finish |
| 503 | `overloaded_error` / `no_capacity`, or `api_error` | no capacity, or a temporary outage | after `Retry-After`; not charged |

A job that was accepted can still fail while it runs. Its status then carries one of these codes:

| `error.code` | `retryable` | Meaning |
|---|---|---|
| `invalid_input` | false | an asset is unusable (for example a reference clip outside 2–30 s); `field` names it |
| `content_policy_violation` | false | content review refused an input or the result |
| `copyright_violation` | true / false | true: the generated result (such as its audio) was flagged, so resubmit; false: an input was, so replace it |
| `generation_failed` | true / false | true when it is safe to resubmit, false when the outcome is unknown |
| `generation_timeout` | false | still unfinished after 24 hours |
| `capacity_unavailable` | true | nothing could take the job within 10 minutes |
| `internal_error` | true | the service failed before generation started |
| `cancelled` | false | the job was cancelled |

## Uploading local files

The generation body only takes HTTPS URLs. For a file on disk, ask for a ticket, `PUT` the bytes, and use the `media_url`:

```bash
FILE=dance.mp4
TICKET=$(curl -fsS "$BASE/media/uploads" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"model\":\"seedance-2.5\",\"type\":\"video\",\"content_type\":\"video/mp4\",\"size_bytes\":$(wc -c < "$FILE" | tr -d ' ')}")
curl -fsS -X PUT "$(jq -r .upload_url <<<"$TICKET")" -H "Content-Type: video/mp4" --data-binary @"$FILE"
jq -r .media_url <<<"$TICKET"   # goes into reference_videos[].url
```

`size_bytes` must equal the file size, the `PUT` must carry the declared `Content-Type`, `upload_url` works for 15 minutes and `media_url` stays readable for seven days.

| Asset | Format | Size | Other limits |
|---|---|---|---|
| image (frames, references) | JPEG, PNG | ≤ 20 MiB | 300–6000 px per side, width/height 0.4–2.5 |
| reference video | MP4, MOV | ≤ 100 MiB | 2–30 s each, 30 s in total; 300–6000 px per side, 409,600–8,295,044 pixels, width/height 0.4–2.5, 24–60 fps |
| reference audio | WAV, MP3 | ≤ 15 MB | 2–30 s each, 30 s in total |
| video to edit | MP4, MOV | ≤ 100 MiB | 4–30 s |

A clip outside these lengths fails the job with `invalid_input` before generation starts, and nothing is charged.

## Concurrency and rate limits

An ArgoLink account runs up to 50 Seedance 2.5 jobs at once, whatever it has spent. Past that the submit call answers `429`; when no capacity is free it answers `503` with `Retry-After`. Neither creates a charge, so both are safe to retry with backoff. For comparison, BytePlus's [Seedance 2.5 guide](https://docs.byteplus.com/en/docs/modelark/seedance-2-5) allows an individual account 3 concurrent tasks and 180 requests a minute (enterprise: 10 and 600), and fal's [concurrency limits](https://fal.ai/docs/documentation/model-apis/concurrency-limits) start a new account at 2 concurrent requests (both read 2026-10-07).

## Using the OpenAPI spec

[`openapi.yaml`](./openapi.yaml) describes all five operations, the request schema with its mode rules, the job object and every documented error. Import it into Postman, Insomnia or Bruno, or generate a client:

```bash
npx @openapitools/openapi-generator-cli generate -i openapi.yaml -g python -o seedance-client
npx openapi-typescript openapi.yaml -o seedance.d.ts
```

The tests check that the spec is internally consistent, that every body in `examples/` validates, and that requests the API rejects (a `seed`, 31 seconds, `4k`, frames mixed with references, an edit with an image, …) fail the schema too. They run offline:

```bash
pip install pytest pyyaml jsonschema
pytest
```

## FAQ

**What is the model ID for Seedance 2.5?**
`seedance-2.5`. `GET https://argolink.io/v1/models` lists it without a key, next to `seedance-2.0`, `seedance-2.0-fast` and `seedance-2.0-mini`, which share the same endpoint and make clips of up to 15 seconds.

**Is there a webhook, or do I have to poll?**
Poll. There is no callback field; reading `GET /v1/videos/{request_id}` every 10–15 seconds is the documented pattern, and only a finished video is billed.

**Why does the download return 409?**
The job is still `pending`. Wait for `status: done`, or retry the same URL; a failed job answers `424` instead.

**Can I send a base64 image or a multipart file?**
No. Media fields take public HTTPS URLs. Upload local files through `POST /v1/media/uploads` and pass the returned `media_url`.

**What does the shortest possible request produce?**
`{"model": "seedance-2.5", "prompt": "…"}` renders and bills 5 seconds at 720p, 16:9, with sound: 5 × $0.196 = $0.98.

**Is the Seedance 2.5 API stable enough for production?**
Yes. Jobs are admitted only when capacity is available, a job that cannot start fails with a retryable `capacity_unavailable`, and failed jobs are never billed.

## License

MIT. Seedance is a ByteDance model; this repository is an independent integration reference.
