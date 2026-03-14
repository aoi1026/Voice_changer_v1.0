# George Michael Voice Converter v1.0 — User Manual

This manual explains what the program does, how to use every part of it, and how to fix common issues. You can read it in order or jump to the section you need.

---

## Table of contents

1. [What this program does](#1-what-this-program-does)
2. [Basic structure of the program](#2-basic-structure-of-the-program)
3. [Installation and starting the program](#3-installation-and-starting-the-program)
4. [Single conversion (one file)](#4-single-conversion-one-file)
5. [Batch conversion (many files)](#5-batch-conversion-many-files)
6. [Advanced Settings (all options)](#6-advanced-settings-all-options)
7. [Output formats and where files are saved](#7-output-formats-and-where-files-are-saved)
8. [Folder structure](#8-folder-structure)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. What this program does

**George Michael Voice Converter** turns any vocal audio (speech or singing) into a version that sounds like it is sung or spoken in a **George Michael–style voice**. The voice model is built in and cannot be changed.

- You provide an audio file (or several).
- The program converts the voice and saves the result in the format you choose (e.g. MP3, WAV).
- It runs on your computer. After installation, it does **not** need the internet to convert.
- You can convert **one file at a time** (Single) or **many files in one go** (Batch).

---

## 2. Basic structure of the program

When you start the program you see:

- **Title:** “George Michael Voice Converter v1.0” at the top.
- **Two tabs:**
  - **Single** — convert one audio file.
  - **Batch** — convert several files at once.

In both tabs you will see:

- **Main controls** — upload/select files, choose where to save, and a **Convert** button.
- **Advanced Settings** — an optional section with extra options (pitch, effects, export format, etc.). You can leave these at their defaults if you prefer.

The program always uses the same built‑in George Michael voice. There are no menus to “choose a different voice” or “load a model”; everything is ready to use.

---

## 3. Installation and starting the program

### First-time installation

1. Unzip the project folder to a place you like (e.g. Desktop or Documents).
2. Double‑click **run-install.bat**.
3. Wait until the installer finishes. You only need to do this **once**.
4. Do **not** run the program as Administrator.

### Starting the program

- **Desktop window (recommended):** Double‑click **run-desktop.bat**. A window opens with the program. No browser needed.
- **In your browser:** Double‑click **run-michale_voice_changer.bat**. Your default browser will open and show the same interface.

If you see a message like “Please run run-install.bat first”, run **run-install.bat** once, then start the program again.

---

## 4. Single conversion (one file)

Use the **Single** tab when you want to convert one audio file.

### Step-by-step

1. **Upload your audio**
   - Click **Upload Audio** and choose a file from your computer (e.g. WAV, MP3, M4A).
   - The file will appear with a waveform. You can play it to check.

2. **Optional: choose where to save**
   - Under **Advanced Settings** you can open the **Output Path** box.
   - By default, the output is saved in the project’s `assets\audios` folder with a name like `YourFileName_output.wav` (or the format you choose).
   - You can type a path or click **Browse** to pick a folder and filename. The extension will match the **Export Format** (e.g. `.mp3`).

3. **Optional: change export format**
   - In **Advanced Settings**, find **Export Format**. Default is **MP3**. You can choose WAV, FLAC, OGG, or M4A instead.

4. **Convert**
   - Click the **Convert** button.
   - Wait until the conversion finishes. A message will appear and the **Export Audio** player will show the result. You can play it there and the file will also be saved to the path you set.

### Main controls (Single tab)

| Control | What it does |
|--------|------------------|
| **Upload Audio** | Choose the one file you want to convert. |
| **Convert** | Starts the conversion. Wait until it finishes. |
| **Output Information** | Shows a short message when conversion is done. |
| **Export Audio** | Lets you play the converted file in the program. |

### Advanced Settings (Single) — summary

- **Output Path** — Where to save the output file. **Browse** opens a dialog to pick folder and name.
- **Export Format** — MP3 (default), WAV, FLAC, OGG, or M4A.
- **Pitch** — Raise or lower the pitch (e.g. -24 to +24). Default 0.
- **Search Feature Ratio** — How much the “voice character” affects the result. Default 0.75.
- **Volume Envelope** — Blend with the output’s volume curve. Default 1.
- **Protect Voiceless Consonants** — Reduces artifacts on consonants. Default 0.5.
- **Split Audio** — Split long files into chunks before converting (can help quality on long tracks).
- **Autotune** — Soft pitch correction; useful for singing.
- **Proposed Pitch** — Adjust input pitch to suit the voice model.
- **Clean Audio** — Reduce noise; useful for speech.
- **Formant Shifting**, **Post-Process**, **Reverb**, **Pitch Shift**, **Limiter**, **Gain**, **Distortion**, **Chorus**, **Bitcrush**, **Clipping**, **Compressor**, **Delay** — Extra effects. Leave unchecked/unchanged unless you want to experiment.

You can ignore Advanced Settings and just use **Upload Audio** and **Convert**; the defaults are fine for most uses.

---

## 5. Batch conversion (many files)

Use the **Batch** tab when you want to convert several files in one go.

### Step-by-step

1. **Choose input files**
   - **Option A:** Click **Input Files** and select one or more audio files (you can select multiple in the dialog).
   - **Option B:** Put the audio files you want to convert into the folder:  
     `[Project folder]\assets\audios`  
     Then leave **Input Files** empty. The program will use all supported audio files in that folder.

2. **Choose output folder**
   - In **Output Folder**, type the path where you want the converted files to be saved, or click **Browse** to pick a folder.
   - Default is the project’s `assets\audios` folder. Each output file will be named like:  
     `OriginalFileName_output.mp3` (or the format you choose).

3. **Optional: change export format**
   - In **Advanced Settings**, **Export Format** is set to **MP3** by default. You can change it to WAV, FLAC, OGG, or M4A. All files in that batch will use the same format.

4. **Convert**
   - Click **Convert**.
   - The **Convert** button will be replaced by **Stop convert** while the batch runs. You can click **Stop convert** to cancel.
   - When all files are done, **Convert** appears again and a message confirms completion. Each converted file will be in the output folder you chose.

### Main controls (Batch tab)

| Control | What it does |
|--------|------------------|
| **Input Files** | Add the audio files to convert. You can select multiple. If you leave this empty, the program uses all audio files in `assets\audios`. |
| **Output Folder** | Folder where converted files will be saved. **Browse** opens a dialog to pick the folder. |
| **Convert** | Starts batch conversion. While running it changes to **Stop convert**. |
| **Stop convert** | Appears during batch conversion; click it to stop. |
| **Output / status** | Shows a message when the batch is finished. |

### Advanced Settings (Batch)

Same options as in Single (export format, pitch, effects, etc.). They apply to **all** files in the batch. Defaults are fine for most users.

---

## 6. Advanced Settings (all options)

These options are in an **Advanced Settings** section that you can open by clicking it. They are the same in Single and Batch (with “batch” in the name in the Batch tab).

### Saving and format

- **Output Path** (Single only) — Full path for the output file. Use **Browse** to pick folder and filename.
- **Output Folder** (Batch only) — Folder where all batch outputs are saved.
- **Export Format** — **MP3** (default), WAV, FLAC, OGG, or M4A. The saved file will have this format only (no extra WAV copy).

### Voice and pitch

- **Pitch** — Overall pitch shift (-24 to +24). 0 = no change.
- **Search Feature Ratio** — Influence of the voice character (0–1). Higher = stronger George Michael style; lower can reduce artifacts.
- **Volume Envelope** — How much the output’s volume curve is used (0–1).
- **Protect Voiceless Consonants** — Protects consonants and breath sounds (0–0.5).
- **Proposed Pitch** — Check to adjust input pitch to the model’s range. **Proposed Pitch Threshold** — e.g. 155 for male, 255 for female.

### Processing options

- **Split Audio** — Split long audio into chunks before converting. Can improve quality on long files.
- **Autotune** — Soft pitch correction (good for singing). **Autotune Strength** (0–1) controls how strong.
- **Clean Audio** — Reduce noise (good for speech). **Clean Strength** (0–1) controls how much.

### Effects (optional)

- **Formant Shifting** — Change tone character (e.g. male/female). Quefrency and Timbre sliders appear when enabled.
- **Post-Process** — Apply extra processing to the output.
- **Reverb** — Add reverb (room size, damping, wet/dry, width, freeze).
- **Pitch Shift** — Extra pitch shift in semitones.
- **Limiter** — Limit peak level (threshold, release).
- **Gain** — Volume change in dB.
- **Distortion** — Add distortion (gain control).
- **Chorus** — Chorus effect (rate, depth, delay, feedback, mix).
- **Bitcrush** — Lo-fi effect (bit depth).
- **Clipping** — Soft clipping (threshold).
- **Compressor** — Compression (threshold, ratio, attack, release).
- **Delay** — Delay effect (time, feedback, mix).

You can leave all of these off and use only the main controls; the program works well with defaults.

---

## 7. Output formats and where files are saved

### Export format

- Default is **MP3**. You can change it to **WAV**, **FLAC**, **OGG**, or **M4A** in Advanced Settings.
- Only **one** file per conversion is saved — the format you choose. There is no separate WAV copy.

### Where files are saved

- **Single:**  
  - Default: `[Project folder]\assets\audios\` with a name like `OriginalName_output.mp3`.  
  - You can change this with **Output Path** and **Browse**.

- **Batch:**  
  - The folder you set in **Output Folder** (default: `[Project folder]\assets\audios`).  
  - Each file: `OriginalFileName_output.mp3` (or the format you selected).

---

## 8. Folder structure

A quick overview of the main folders in the project:

| Folder / file | Purpose |
|---------------|--------|
| **assets\audios** | Default place for single outputs and, if you put files here, the default batch input folder. |
| **assets\gradio_temp** | Temporary files used by the program. You can ignore or delete old contents. |
| **logs\GeorgeMichael** | Built-in voice model files. Do not delete or rename. |
| **run-install.bat** | Run once to install. |
| **run-desktop.bat** | Start the program in a desktop window. |
| **run-michale_voice_changer.bat** | Start the program in your browser. |
| **README.md** | Short guide and quick start. |
| **MANUAL.md** | This full manual. |

---

## 9. Troubleshooting

### “Please run run-install.bat first”

- Run **run-install.bat** once and wait until it finishes. Then start the program again with **run-desktop.bat** or **run-michale_voice_changer.bat**.

### Program won’t start or window doesn’t appear

- Do **not** run as Administrator.
- Make sure you ran **run-install.bat** at least once.
- For desktop mode, wait a few seconds; the first start can be slow.
- If you use the browser version, allow the page to load fully.

### Conversion is very slow

- Long or high-quality files take more time. Batch conversion of many files can take several minutes. This is normal.

### No sound in the Export Audio player

- The file was still saved to the path you set. Play it from that folder with your usual media player. If the path was on another drive (e.g. `D:\`), the program still saves there but the in-app player may not be able to play it; use the saved file directly.

### I want to convert again with different settings

- Change the options in Advanced Settings and click **Convert** again. You can overwrite the previous file or choose a new path/folder.

### Batch: some files didn’t convert

- Check that the input files are in a supported format (e.g. WAV, MP3, M4A, FLAC). If you used **Input Files**, make sure they were selected correctly. If you used `assets\audios`, make sure the files are in that folder.

### Where is my converted file?

- **Single:** See **Output Path** in Advanced Settings, or look in `assets\audios` if you didn’t change it.
- **Batch:** See **Output Folder**; files are named `OriginalName_output.[format]`.

---

*George Michael Voice Converter v1.0 — User Manual. For personal use.*
