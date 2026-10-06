English · [日本語](README.ja.md)

# agents-music-workbench

A toolkit that lets an AI agent (**Codex** / **Claude Code**) **compose BGM and sound effects, lets you audition them side by side in the browser**, and turns **the tracks you pick into REAPER projects with instruments already configured**. Use it for prototyping tracks and brainstorming ideas.

```
 ① Ask for compositions     ② Audition and pick                       ③ Ask for project generation
 "10 dialogue BGM tracks" → ★ tracks in data/library/index.html   →   generate-projects.bat
  WAV + MIDI are written     "Save ★ from all tabs / this tab"          per-instrument .rpp, preview WAV, overview
```

- The agent writes each composition as **note data (Python)**, so the per-part MIDI can be edited in REAPER as is.
- No composition skill is bundled. The intended companion is [music-composition-skills](https://github.com/jtydhr88/music-composition-skills) (ARR-SPEC workflow) or similar; add it as an agent skill before use.
- The audition catalog has one tab per composition session (batch) and is updated automatically each time you render.
- The REAPER version uses the stock ReaSynth (no extra instruments needed). Settings for Magical 8bit Plug 2 and MASSIVE are also included.

<img src="docs/readme/01_tool_ui.png" width="800" style="max-width: 100%; height: auto;" alt="Sound catalog screen">

## Requirements

| Software                         | Purpose                                              | Notes                                                    |
| -------------------------------- | ---------------------------------------------------- | -------------------------------------------------------- |
| Python 3.10+ and numpy           | Exporting note data, catalog, REAPER integration     | `pip install -r requirements.txt`                        |
| Codex or Claude Code             | The agent you ask to compose and generate projects   |                                                          |
| A browser such as Chrome / Edge  | Audition catalog                                     | Chrome / Edge can save the list directly to a folder     |
| [REAPER](https://www.reaper.fm/) | Project generation                                   | Tested with 7.x. The default synth, ReaSynth, ships with REAPER |

Optional instruments become selectable in the catalog and commands once installed.<br>
Tested on Windows 11 + REAPER 7.80. macOS / Linux are untested.

## Setup

```bash
git clone https://github.com/<you>/agents-music-workbench.git
cd agents-music-workbench
pip install -r requirements.txt
python python/cli.py doctor      # Check Python, REAPER, and instruments
```

If `doctor` can't find REAPER, or you want to change the default instruments (e.g. `["magical8bit", "massive"]`), copy `config.example.json` to `config.json` and edit it.

```json
{
  "reaper_path": "C:/Program Files/REAPER (x64)/reaper.exe",
  "profiles": ["reasynth"],
  "downloads_dir": "",
  "reaper_timeout_sec": 1800
}
```

### Preparing the agent

Just open this repository as the agent's working folder and the bundled skills are loaded.

| Agent       | Files loaded                   |
| ----------- | ------------------------------ |
| Codex       | `AGENTS.md`, `.agents/skills/` |
| Claude Code | `CLAUDE.md`, `.claude/skills/` |

The skills live in one place only: `.agents/skills/`. Claude Code reads only `.claude/skills/`, so that folder holds just a description and a pointer to the real skill (regenerate it with `python python/cli.py sync-skills`).

## Usage

### 1. Ask for compositions

Tell the agent the purpose and how many candidates you want.

> Make 10 retro-game-style BGM tracks for the dialogue parts of an explainer video. They'll be looped.

> Give me 8 sound effects of about 1 second for chapter headings, mostly bright ones.

The agent writes the tracks to `data/library/<date-name>/compose.py` and exports WAV and MIDI. When it finishes, open the audition catalog.

```
data/library/index.html   ← open directly in a browser (no server needed)
```

<img src="docs/readme/01_tool_ui.png" width="800" style="max-width: 100%; height: auto;" alt="Sound catalog screen">

### 2. Audition and pick

- Switch between **composition sessions (batches)** with the tabs at the top. Opening a tab also shows the request and design notes.

<img src="docs/readme/04_manual_tab.png" width="600" style="max-width: 100%; height: auto;" alt="Batch tabs in the sound catalog">

- Press **"☆ Add to list"** on tracks you like. ★ marks are shared across all batches and stored in the browser.
  - Tracks labeled "no note data" are audio-only material and can't become REAPER projects (audition and WAV download only).

<img src="docs/readme/05_manual_favorite.png" width="800" style="max-width: 100%; height: auto;" alt="Adding a track to the project generation list">

- Press a save button at the bottom of the screen.
  - **"Save ★ from all tabs"**: saves every track starred in any batch.
  - **"Save ★ from this tab"**: saves only tracks starred in the currently open batch tab (★ in other tabs stay, but are not added to the list).
  - The first time, a folder picker opens; choose this repository's **`data/project-lists`** folder. After that, one click saves to `data/project-lists/latest.json`.
  - In browsers that can't save directly, `project-list-latest.json` is downloaded (the Downloads folder is also searched automatically).

<img src="docs/readme/06_manual_generate.png" width="800" style="max-width: 100%; height: auto;" alt="Saving the project generation list from selected tracks">

### 3. Generate REAPER projects

No agent is needed for this step.<br>
Double-click **`generate-projects.bat`** in the repository (`./generate-projects.sh` on macOS / Linux). It reads the latest project generation list and builds REAPER projects with the instruments selected in the list.

- It simply runs `python python/cli.py project all`. Arguments are passed through (e.g. `generate-projects.bat --profiles reasynth magical8bit`).
- It automatically looks for a Python with numpy (`py -3` → `python` → `python3`). If none is found, set the environment variable `MUSIC_PYTHON` to the path of a python executable.
- You can also ask the agent "generate REAPER projects from the latest list" to get the same result. That's handy when you want it to investigate failures or tune instrument profiles.

If REAPER is running, a new tab is opened in that window for the work and closed afterwards. If it isn't running, it is launched automatically.<br>
The first track is used to verify saving, loading, and rendering for every instrument before moving on to the rest.

Results are collected in `data/projects/<datetime-name>/`, and the **"Generated projects"** tab of the audition catalog lets you compare the instrument versions by ear.<br>
Press **"Copy path"** on a project and paste it into the file name field of REAPER's "File → Open project" to open it.

| File                              | Contents                                                                                                                                                                                                                                              |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `<job>_overview.rpp`              | **Overview of all tracks.** Each track sits on its own track as a subproject (if you chose multiple instruments, each track's folder holds one track per instrument, which you can solo to compare). Double-click an item to open that track's editing project |
| `<track>/<instrument>/<track>_<instrument>.rpp` | Editing project with instruments configured (MIDI embedded)                                                                                                                                                                         |
| `<track>/score.mid`               | Shared per-part MIDI (Type 1 / 960 PPQ). Contains no instrument settings                                                                                                                                                                              |
| `<track>/<instrument>/preview_matched.wav` | Loudness-matched preview WAV (48 kHz / 24-bit)                                                                                                                                                                                               |
| `<track>/<instrument>/sound_settings.tsv`  | Record of the instrument parameters that were set                                                                                                                                                                                    |
| `README.md` / `delivery.json`     | List of deliverables and verification results                                                                                                                                                                                                         |

The overview project looks like this.

<img src="docs/readme/02_reaper_root_project.png" width="800" style="max-width: 100%; height: auto;" alt="REAPER project combining all tracks">

An individual track's project looks like this.<br>
Looping tracks are laid out three times; the middle repeat is the playback / render range (the others are for checking the tail). Sound effects have a 0.35-second tail margin.

<img src="docs/readme/03_reaper_unit_project.png" width="800" style="max-width: 100%; height: auto;" alt="Per-track REAPER editing project">

### Try it without an agent

You can walk through the whole flow with the sample composition data.

```bash
python python/cli.py new-batch demo --example    # Copy the sample to data/library/<date>-demo/
python python/cli.py render <date>-demo          # Export and update the catalog
# Open data/library/index.html, ★ tracks → "Save ★ from all tabs" or "Save ★ from this tab"
python python/cli.py project all                    # Generate with the default ReaSynth
```

## Commands

| Command                                                                           | Description                                                                          |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `python python/cli.py new-batch <name> [--example]`                               | Create a composition batch template                                                  |
| `python python/cli.py render <batch-id> [--force]`                                | Export WAV, MIDI, and list data, and update the catalog                              |
| `python python/cli.py catalog`                                                    | Rebuild the catalog (`data/library/index.html`)                                      |
| `python python/cli.py project-list [--file PATH]`                                 | Show the latest project generation list                                              |
| `python python/cli.py project all [--profiles ...] [--name NAME] [--stage pilot]` | Generate REAPER projects from the list                                               |
| `python python/cli.py project build [<job-id>] [--force]`                         | Resume / continue generation (already-built tracks are skipped)                      |
| `python python/cli.py doctor`                                                     | Check the environment                                                                |
| `python python/cli.py sync-skills`                                                | Rebuild the Claude Code pointers in `.claude/skills` from `.agents/skills` (the source) |
| `python -m unittest discover -s tests`                                            | Run tests                                                                            |

## Instrument profiles

How the REAPER version sounds is determined by the instrument profiles in `python/reaper/lua/profiles/`. Sounds are set per part role (melody, bass, chords, arpeggio, percussion).

| Name          | Instrument                 | Notes                                                                   |
| ------------- | -------------------------- | ----------------------------------------------------------------------- |
| `reasynth`    | ReaSynth (REAPER built-in) | **Default.** Works with no extra instruments. No noise source, so percussion is approximated |
| `magical8bit` | Magical 8bit Plug 2        | Optional. 8-bit sounds from pulse, triangle, and noise                  |
| `massive`     | Native Instruments MASSIVE | Optional. Sets wavetable, filter, and envelope per role                 |

The instruments to use are decided in this order. If you choose several, a project is built for each instrument so you can compare them.

1. `--profiles` on the command (e.g. `project all --profiles reasynth magical8bit`)
2. The instruments selected when saving in the audition catalog ("Instruments" at the bottom of the screen)
3. `profiles` in `config.json`
4. The default (`reasynth`)

### How sounds are determined

The REAPER version does not analyze and reproduce the timbre of the original preview WAV. **Notes are carried over exactly; timbre is rebuilt for each instrument.**

| Carried over                                                                                              | Not carried over                                                  |
| --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Pitch, timing, length, velocity, pan, glides, per-part volume balance, tempo and time signature           | The preview synth's timbre itself (harmonic content, decay speed) |

Timbre is determined as follows.

1. **Inputs**: the **role** and **timbre name** of each part in the composition data (`events.json`).
   - Role: `lead` (melody), `bass`, `pad` (chords), `arp` (arpeggio), `drum`. If not specified during composition, it is inferred from the part name (`Kick` `Hat` → drum, `Bass` → bass, etc.).
   - Timbre name: names specified during composition, such as `pulse`, `triangle`, `bell`, `hat`.
2. **Deciding values**: rules written in the instrument profile map role and timbre name to parameter values. For example, in Magical 8bit, timbre name `pulse` gives waveform Pulse/Square with 25% Duty, and role `drum` with timbre name `hat` gives waveform Noise with a short Decay.
3. **Setting the VST**: REAPER's scripting looks up the parameters the plugin exposes by name and sets them. Values are matched while checking in REAPER so they display as expected, such as "Triangle" or "25%".
4. **Verification and record**: the project is saved and reopened to confirm the set values persisted. The values actually set are recorded in each project's `sound_settings.tsv`.

Settings the plugin doesn't expose (e.g. MASSIVE's pitch bend range) can't be changed. To change the overall tendency of the sound, edit the rules in the instrument profile.

To add a new instrument, write one profile file. See [.agents/skills/create-reaper-project/references/profiles.md](.agents/skills/create-reaper-project/references/profiles.md) for how. Write parameter names and choices only after confirming the actual values in REAPER.

## Folder layout

```
generate-projects.bat     Generate REAPER projects (Windows; double-click to run)
generate-projects.sh      Same (macOS / Linux)
AGENTS.md / CLAUDE.md     Entry points for agents
.agents/skills/           The skills themselves (compose-music / create-reaper-project)
.claude/skills/           Pointers for Claude Code (just direct it to the real skills)
python/
  cli.py                  Entry point (the only thing you run)
  settings.py             Repository root, folder locations, config.json loading
  music/                  Note data format (Cue / Note / Scale), preview synth, MIDI, batch export
  catalog/                Audition catalog (HTML) and project generation list
  reaper/                 REAPER integration (lua/ runs inside REAPER, lua/profiles/ holds instrument profiles)
  tools/                  Environment check and skill sync
examples/demo_batch/      Sample composition data
tests/
data/                     Working data (contents are not tracked by Git)
  library/                Composition batches and audition catalog (index.html)
  project-lists/          Project generation lists (saved from the catalog)
  projects/               REAPER projects
```

Code and settings are kept apart from your own working data (`data/`). Since working data lives in the `data/` folder, backing up is just copying that folder.

## FAQ and limitations

- **The preview WAV and the REAPER version sound different**: the preview WAV is an approximation from a simple built-in synth. The REAPER version is an arrangement that replays the same notes on each instrument.
- **Generation stopped / timed out**: check whether REAPER is showing a dialog (license activation, evaluation notice, save confirmation, etc.). Close it, then resume with `project build <job-id>`. Logs are in `data/projects/<job>/logs/`.
- **A plugin won't load**: rescan in REAPER's "Options → Preferences → Plug-ins → VST", and check registration with `doctor`.
- **Glide range is wrong in MASSIVE**: MASSIVE doesn't let the host set the pitch bend range. Match it on the instrument side (recorded in `delivery.json` warnings).
- **Quality is not guaranteed**: automatic checks (silence, clipping, loop seams, MIDI match, project reload) are performed, but musical quality and the absence of similarity to existing songs are not guaranteed. Always check by ear.
- Please verify the usage rights of generated tracks on your own responsibility.
