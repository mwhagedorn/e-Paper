# Plan: Externally Triggered E-Paper Display

Status: **Draft, with open decisions** (see the end of this file)
Date: 2026-11-12
Reference: `RaspberryPi_JetsonNano/python/examples/main.py`

## Goal

Today the display only changes when `main.py` runs. Each run picks a random affirmation, draws it on the Mac System 6 desktop backdrop, pushes it to the 4.2" EPD (400x300) and exits. It is presumably run by cron.

The new design should let **external input decide when the screen updates and what it shows**. The current look and the random-affirmation behaviour stay as one kind of content among several.

## Current state (what we're starting from)

- One 300-line script that does everything: content selection, layout (`make_it_pretty`, `text_wrap`), backdrop drawing (`draw_desktop`, `draw_trash`, `draw_startup_disk`) and hardware output.
- The affirmations are hardcoded in `get_affirmations()`.
- `USE_EINK_DISPLAY` switches between the real EPD and `Image.show()`.
- No dependencies are declared in `pyproject.toml`. It asks for `requires-python >= 3.14`, which is probably newer than the Python on the Pi.

### Existing bugs to fix along the way

1. **Missing commas in the affirmation list.** Three affirmations are silently joined into one string: "I make bold moves…", "What I am capable of…" and "Say it over and over…".
2. **`Image.ANTIALIAS` was removed in Pillow 10.** `resize()` will crash if it is ever called. Use `Image.LANCZOS`.
3. **`epd` is unbound in the `KeyboardInterrupt` handler** if the interrupt arrives before init.
4. **`make_it_pretty` can loop forever** if no quote fits at any font size.
5. The `\w` regex is in a non-raw string, which gives a SyntaxWarning on newer Python versions.

## Architecture

Turn the one-shot script into a **long-running service**. The service owns the display and reacts to commands from one or more input adapters.

```
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │ MQTT         │   │ HTTP API     │   │ GPIO button  │   │ Scheduler    │
  │ adapter      │   │ (deferred)   │   │ (opt.)       │   │ (hourly)     │
  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
         └──────────────────┴────────┬─────────┴──────────────────┘
                                     ▼
                          Command queue (latest wins)
                                     ▼
                     ┌───────────────────────────────┐
                     │ Display worker (single thread) │
                     │  render(command) -> PIL Image  │
                     │  output.show(image)            │
                     └───────────────────────────────┘
                          │                     │
                    EpdOutput (Pi)       FileOutput (dev: PNG)
```

### Modules

| Module | Responsibility |
|---|---|
| `commands.py` | Command types: `ShowText(text)`, `ShowAffirmation()`, `ShowTemporary(source)`, `ShowImage(bytes)`, `Clear()`. These are plain dataclasses. |
| `content.py` | Loads and saves affirmations from a data file. Picks a random one, avoiding immediate repeats. |
| `render.py` | Pure function from a command (plus a timestamp) to a 400x300 1-bit `Image`. Holds the code extracted from `make_it_pretty`, `text_wrap` and the desktop/trash/disk drawing. No hardware imports, so it can be tested on a laptop. |
| `output.py` | `Output` protocol with two implementations. `EpdOutput` wraps `epd4in2`: init, display, sleep. `FileOutput` writes `last.png`. The choice is made by config or env var instead of the `USE_EINK_DISPLAY` constant. |
| `worker.py` | The single thread that owns the display. It drains the queue and coalesces bursts so only the latest command is drawn, renders, outputs, and records the current state. |
| `adapters/mqtt.py` | The external input (see the MQTT adapter section). |
| `adapters/scheduler.py` | Enqueues `ShowAffirmation` at the top of every hour. |
| `adapters/http.py`, `adapters/button.py` | Deferred. Only if wanted later. |
| `app.py` | Entry point. Reads config and wires the adapters, worker and output together. |

### Fast buffer conversion (replace `getbuffer()`)

`epd4in2.EPD.getbuffer()` (`lib/waveshare_epd/epd4in2.py:435`) turns the 400x300 image into panel bytes. It loops over all 120,000 pixels in pure Python. The affirmer calls it once per update (`examples/main.py:261`).

`EpdOutput` will produce the same bytes with Pillow's packed 1-bit encoding:

```python
buf = list(image.convert('1').tobytes())   # MSB-first, 1 = white, 0 = black; 400/8 = 50 bytes per row
```

- **Measured on a laptop:** about 15 ms for `getbuffer()` vs about 0.9 ms for `tobytes()`. The output was byte-for-byte identical, including the default Floyd–Steinberg dithering. On a Pi Zero this should save roughly 0.3–0.6s per update (an estimate, not measured).
- **The vendored driver is not modified.** The conversion lives in our wrapper, which then calls `epd.display(buf)`.
- **Guard:** only use the fast path when the image is exactly `(epd.width, epd.height)`. Fall back to `epd.getbuffer()` for the rotated 300x400 case, which the driver handles by remapping pixels.
- **Test:** a unit test asserts `fast_buffer(img) == [b & 0xFF for b in reference_getbuffer(img)]` on a sample render. The reference is a copy of the driver's loop, so the test runs without hardware.
- **Context:** this is a modest win. The panel refresh itself (about 4s) dominates every update, and nothing in software can shorten it.

### Display constraints the design must respect

- **A full refresh takes about 4s and flashes the screen.** Only one thread may touch SPI/GPIO, so commands are serialized through the worker.
- **Coalesce commands.** If five requests arrive during a refresh, draw only the last one.
- **Rate limit.** Use a minimum interval between refreshes, for example 5s, to protect the panel and stop request spam.
- **Put the panel to sleep after every update.** This is already done today and should stay. Do not leave it powered.
- **Persist the current content** to a small state file, so a restart redraws the same thing instead of a random quote.

## MQTT adapter

MQTT is the **only external input** for now (HTTP is deferred). Each message is turned into a command and added to the worker's queue.

### Pieces

- **Broker:** Mosquitto, either on the Pi or an existing broker such as Home Assistant's.
- **Client:** `paho-mqtt` 2.x inside the service. `loop_start()` runs the network loop on a background thread and handles reconnecting automatically.
- **State listeners:** the worker calls a list of these after each successful refresh. The MQTT adapter is one of them and publishes the state. The worker stays independent of the adapters.

### Topics

`<device>` is a config value such as `office`, so more than one display can share a broker.

| Topic | Direction | Retained | Payload |
|---|---|---|---|
| `epaper/<device>/cmd/affirmation` | in | **no** | ignored |
| `epaper/<device>/cmd/temporary` | in | **no** | empty for the defaults, or `{"source": "alternates"}` |
| `epaper/<device>/cmd/text` | in | **no** | plain string, or `{"text": "..."}` |
| `epaper/<device>/cmd/image` | in | **no** | raw PNG/JPEG bytes |
| `epaper/<device>/cmd/clear` | in | **no** | ignored |
| `epaper/<device>/state` | out | yes | `{"type": "text", "text": "...", "shown_at": "..."}` |
| `epaper/<device>/availability` | out | yes | `online` / `offline` (last will) |
| `epaper/<device>/preview` | out | yes | PNG of what's currently on the panel (a few KB). This replaces the HTTP preview endpoint. |

Rules:
- **Never retain command topics.** A retained command would replay every time the Pi reconnects.
- **QoS 1 with `clean_session=False`:** commands sent while the Pi is offline are delivered when it reconnects, and the worker collapses them into one redraw.
- **Subscribe in `on_connect`**, not once at startup, so subscriptions survive broker restarts.
- **Invalid payloads are logged and dropped.** An exception must never escape the message callback.

### Sketch

```python
class MqttAdapter:
    def __init__(self, queue, cfg):
        self.queue, self.cfg = queue, cfg
        self.base = f"epaper/{cfg.device_id}"
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2,
                                  client_id=f"epaper-{cfg.device_id}",
                                  clean_session=False)
        if cfg.username:
            self.client.username_pw_set(cfg.username, cfg.password)
        self.client.will_set(f"{self.base}/availability", "offline", qos=1, retain=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def start(self):
        self.client.connect_async(self.cfg.host, self.cfg.port)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        client.subscribe(f"{self.base}/cmd/#", qos=1)
        client.publish(f"{self.base}/availability", "online", qos=1, retain=True)
        self._publish_discovery()            # optional, Home Assistant

    def _on_message(self, client, userdata, msg):
        action = msg.topic.rsplit("/", 1)[-1]
        try:
            match action:
                case "temporary":   self.queue.put(ShowTemporary(parse_source(msg.payload)))
                case "affirmation": self.queue.put(ShowAffirmation())
                case "clear":       self.queue.put(Clear())
                case "image":       self.queue.put(ShowImage(msg.payload))
                case "text":        self.queue.put(parse_text(msg.payload))  # JSON or plain string
                case _:             log.warning("unknown command %s", action)
        except Exception:
            log.exception("bad payload on %s", msg.topic)

    def publish_state(self, state: dict):    # registered as a worker state listener
        self.client.publish(f"{self.base}/state", json.dumps(state), qos=1, retain=True)
```

### Home Assistant discovery (optional)

When Home Assistant is available, publish retained discovery configs on connect so the display shows up as a device with no YAML on the HA side:

| Discovery topic | Entity | Wiring |
|---|---|---|
| `homeassistant/button/epaper_<device>_next/config` | "Next affirmation" button | `command_topic: epaper/<device>/cmd/affirmation` |
| `homeassistant/text/epaper_<device>_message/config` | Message text box (HA max 255 chars) | `command_topic: epaper/<device>/cmd/text` |
| `homeassistant/sensor/epaper_<device>_state/config` | Currently displayed content | `state_topic: epaper/<device>/state`, `value_template` |

All three share one `device` block and point at `availability_topic: epaper/<device>/availability`.

### Config

`mqtt.enabled`, `mqtt.host`, `mqtt.port`, `mqtt.username`, `mqtt.password` (from an env var), `mqtt.device_id`, `mqtt.ha_discovery`.

### Manual testing

```bash
mosquitto_sub -h broker.local -t 'epaper/#' -v
mosquitto_pub -h broker.local -t epaper/office/cmd/affirmation -m ''
mosquitto_pub -h broker.local -t epaper/office/cmd/temporary -m ''
mosquitto_pub -h broker.local -t epaper/office/cmd/text -m '{"text":"Ship it."}'
mosquitto_pub -h broker.local -t epaper/office/cmd/image -f photo.png
```

Automated tests: call `_on_message` directly with fake messages and assert on the queue. No broker is needed.

### MQTT vs HTTP

| | MQTT | HTTP |
|---|---|---|
| Needs | A broker | Nothing extra |
| Network | Pi makes the connection out, no open port on the Pi | Pi listens on a port |
| Feedback | Asynchronous: watch `state` for the result | Immediate response, including errors |
| Home Assistant / automations | Native, with discovery | `rest_command` setup |
| Ad-hoc use from a phone or curl | Needs an MQTT client | Easiest |
| Offline buffering | Broker queues commands (QoS 1) | Request fails |

Decision: **MQTT only for now.** HTTP can be added later (see "Deferred: HTTP API").

## Hourly rotation and the temporary display

### Hourly rotation (existing behaviour, kept)

- The service's scheduler replaces cron. At the **top of every hour** (`hh:00`) it enqueues `ShowAffirmation`, which renders a new random affirmation as the **base** frame.

### Temporary display (the external trigger)

- An external trigger, sent over MQTT (`cmd/temporary`), shows a random string from a **separate alternate list**, independent of the affirmations.
- That screen stays for **5 minutes** and **cannot be interrupted**. Afterwards the original view is restored.

```
 showing base ──trigger──▶ LOCKED (showing temp) ──5 min──▶ restore
                              │                               │
                              │                    hour boundary crossed while locked?
                              │                      no  → redraw cached base frame (same pixels)
                              │                      yes → render a new affirmation as the base
                              │
                              └─ every command during the lock is rejected, including
                                 another trigger, custom text and the hourly tick
```

Rules:
- **The cached base frame** (`base.png` plus metadata) is what gets restored. Restoring redraws the exact pixels, with no re-render and no new random pick. The temporary frame is not kept.
- **Commands during the lock are rejected, not queued.** The rejection is logged, and the retained `state` topic includes `locked_until`, so senders can see why nothing happened.
- **An hour boundary crossed while locked** means the restore shows a **fresh affirmation** instead of the cached base. This needs no extra flag. At restore time, compare `base.shown_at` with the most recent top of the hour:
  ```python
  last_hour = now().replace(minute=0, second=0, microsecond=0)
  if state.base.shown_at < last_hour:
      state.base = render_frame(ShowAffirmation())   # rotation was due
  output.show(state.base.image)
  ```
  The same check runs on startup, so an hour missed while the service was down is caught up too.
- **A restart during the lock:** `locked_until` is saved in `state.json`. On startup the service waits out the remaining time, or restores right away if the lock has already expired.
- **Cost:** a trigger means two full refreshes (about 8s of flashing in total). The hourly refresh that falls inside a window is merged into the restore, so there's no extra flash.

### Worker sketch

```python
while True:
    timeout = seconds_until(state.locked_until)          # None when unlocked
    try:
        cmd = queue.get(timeout=timeout)
    except Empty:                                         # lock expired
        restore()                                         # cached base, or fresh affirmation if an hour passed
        continue

    if state.locked_until:
        log_rejected(cmd, state.locked_until)             # dropped; state topic shows locked_until
        continue

    match cmd:
        case ShowTemporary(source):
            frame = render_frame(pick(source))
            output.show(frame.image)                      # base stays untouched
            state.locked_until = now() + TEMP_DURATION
        case _:                                           # hourly tick, custom text, ...
            state.base = render_frame(cmd)
            output.show(state.base.image)
    save_state(state)
```

The scheduler is one more input adapter. It only enqueues `ShowAffirmation` at `hh:00`, and the worker decides what happens to it.

## Data

- Move the affirmations into `affirmations.txt` (one per line, with `\n` for line breaks) or `affirmations.yaml`.
- Put the alternate list for the temporary display in its own file, for example `alternates.txt`, in the same format.
- Rewrite the files atomically if remote editing is added later.
- **State** lives in `state.json` plus `base.png`: the base frame's source and `shown_at`, and `locked_until`.

## Deployment

- Replace the cron job with a systemd unit `affirmer.service` that sets `Restart=on-failure` and runs as a user in the `spi` and `gpio` groups.
- Set config through env vars or `config.toml`: MQTT host, credentials and device ID, output type, data paths.
- **MQTT security:** give the device its own broker username and password, with an ACL limiting it to `epaper/<device>/#`. Use TLS if the broker is reachable from outside the LAN.
- Fix `pyproject.toml`: set a realistic `requires-python` that matches the Pi's Python, and declare `pillow`, `paho-mqtt`, and `RPi.GPIO`/`spidev` (Pi only).
- Logging should go to journald or stdout instead of `quotes.log` in the cwd.

## Phases

1. **Refactor without changing behaviour.** Split `main.py` into `render`, `content`, `output` and a CLI entry point that does what `main.py` does today. Fix the bugs listed above. Swap in the fast buffer conversion in `EpdOutput`. Add render tests that use `FileOutput`, such as golden images or "it fits" assertions.
2. **Service and MQTT.** Add the worker, the queue, the hourly scheduler, the temporary display with its 5-minute lock and restore, and the MQTT adapter (command topics, retained state, availability, preview). Run it locally with `FileOutput` against a local Mosquitto.
3. **Pi deployment.** Add the systemd unit and broker credentials, then retire the cron job.
4. **Extras, as decided.** Home Assistant discovery, image upload, managing the affirmation and alternate lists, a GPIO button, the HTTP API.

## Open decisions

1. ~~Trigger mechanisms~~ **Decided:** MQTT only. HTTP is deferred, and a GPIO button is still possible later.
1a. **Broker and Home Assistant.** Is a broker or Home Assistant already running? Where should Mosquitto live? Do you want HA discovery?
2. **Content types.** Custom text, next affirmation, image upload, remote affirmation editing: which are in scope?
3. ~~Schedule~~ **Decided:** keep the hourly rotation at `hh:00`. The temporary display lasts 5 minutes, can't be interrupted and then restores the original. If an hour boundary falls inside the window, the restore shows a fresh affirmation instead.
4. **What publishes the trigger?** Home Assistant, a phone MQTT app, another script? The answer affects the broker ACLs and whether HA discovery is worth doing.
5. **Pi model and Python version.** These affect `requires-python`.
6. **Layout.** Should the code stay under `python/examples/`, or move into its own package such as `affirmer/` at the repo root, leaving the Waveshare example code untouched?

## Deferred: HTTP API

**Out of scope for now.** MQTT is the only external input. This section is kept so HTTP can be added later as another adapter that enqueues the same commands, with no change to the worker.

| Method | Path | Body | Effect |
|---|---|---|---|
| `POST` | `/display/temporary` | `{"source": "alternates"}`? | Show a random alternate for 5 min (locked), then restore. Returns `409` if already locked. |
| `POST` | `/display/text` | `{"text": "..."}` | Show custom text as the new base. Returns `409` while locked. |
| `POST` | `/display/affirmation` | none | Show the next random affirmation. |
| `POST` | `/display/image` | multipart image | Resize and dither the image to 400x300, then show it. |
| `POST` | `/display/clear` | none | Clear the screen to white. |
| `GET` | `/display` | none | Current state as JSON: content type, text, and when it was shown. |
| `GET` | `/display/preview.png` | none | The image currently on the panel, which is handy remotely. |
| `GET/POST/DELETE` | `/affirmations` | none | List, add or remove affirmations. |

- Triggering an update is then a one-liner: `curl -X POST pi.local:8080/display/affirmation`. That works from iOS Shortcuts, Home Assistant `rest_command`, cron on another machine, and so on.
- **Auth:** a shared bearer token from an env var, and the server binds to the LAN only.
- **Framework:** FastAPI + uvicorn is recommended (validation, auto docs at `/docs`). A lighter alternative is Flask or the stdlib `http.server`, if Pi resources are tight.
