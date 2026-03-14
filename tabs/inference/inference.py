import datetime
import json
import os
import shutil
import sys

import gradio as gr
import regex as re
import torch

from assets.i18n.i18n import I18nAuto
from core import run_batch_infer_script, run_infer_script
from rvc.lib.utils import format_title

i18n = I18nAuto()

now_dir = os.getcwd()
sys.path.append(now_dir)

CONFIG_FILE = os.path.join(now_dir, "assets", "config.json")


def load_config_filter():
    try:
        with open(CONFIG_FILE, "r", encoding="utf8") as f:
            cfg = json.load(f)
        return bool(cfg.get("model_index_filter", False))
    except Exception:
        return False


def stop_infer():
    pid_file_path = os.path.join(now_dir, "assets", "infer_pid.txt")
    try:
        with open(pid_file_path, "r") as pid_file:
            pids = [int(pid) for pid in pid_file.readlines()]
        for pid in pids:
            os.kill(pid, 9)
        os.remove(pid_file_path)
    except Exception:
        pass

model_root = os.path.join(now_dir, "logs")
audio_root = os.path.join(now_dir, "assets", "audios")
custom_embedder_root = os.path.join(
    now_dir, "rvc", "models", "embedders", "embedders_custom"
)

FORMANTSHIFT_DIR = os.path.join(now_dir, "assets", "formant_shift")

os.makedirs(custom_embedder_root, exist_ok=True)
os.makedirs(audio_root, exist_ok=True)

custom_embedder_root_relative = os.path.relpath(custom_embedder_root, now_dir)
model_root_relative = os.path.relpath(model_root, now_dir)
audio_root_relative = os.path.relpath(audio_root, now_dir)

sup_audioext = {
    "wav",
    "mp3",
    "flac",
    "ogg",
    "opus",
    "m4a",
    "mp4",
    "aac",
    "alac",
    "wma",
    "aiff",
    "webm",
    "ac3",
}


def normalize_path(p):
    return os.path.normpath(p).replace("\\", "/").lower()


# BASE model/index folder names for many latin languages (legacy: zips = models)
MODEL_FOLDER = re.compile(r"^(?:model.{0,4}|mdl(?:s)?|weight.{0,4}|zip(?:s)?)$")
INDEX_FOLDER = re.compile(r"^(?:ind.{0,4}|idx(?:s)?)$")


def is_mdl_alias(name: str) -> bool:
    return bool(MODEL_FOLDER.match(name))


def is_idx_alias(name: str) -> bool:
    return bool(INDEX_FOLDER.match(name))


def alias_score(path: str, want_model: bool) -> int:
    """
    Handles duplicate files, compare file type to path and assign a score:
    2 = Path contains correct alias  (e.g., model file in 'modelos/' folder)
    1 = Path contains opposite alias (e.g., model file in 'index/' folder)
    0 = Path contains no recognized aliases
    """
    parts = normalize_path(os.path.dirname(path)).split("/")
    has_mdl = any(is_mdl_alias(p) for p in parts)
    has_idx = any(is_idx_alias(p) for p in parts)
    if want_model:
        return 2 if has_mdl else (1 if has_idx else 0)
    else:
        return 2 if has_idx else (1 if has_mdl else 0)


def get_files(type="model"):
    assert type in ("model", "index"), "Invalid type for get_files (models or index)"
    is_model = type == "model"
    exts = (".pth", ".onnx") if is_model else (".index",)
    exclude_prefixes = ("G_", "D_") if is_model else ()
    exclude_substr = None if is_model else "trained"

    best = {}
    order = 0

    for root, _, files in os.walk(model_root_relative, followlinks=True):
        for file in files:
            if not file.endswith(exts):
                continue
            if any(file.startswith(p) for p in exclude_prefixes):
                continue
            if exclude_substr and exclude_substr in file:
                continue

            full = os.path.join(root, file)
            real = os.path.realpath(full)
            score = alias_score(full, is_model)

            prev = best.get(real)
            if (
                prev is None
            ):  # Prefer higher score; if equal score, use first encountered
                best[real] = (score, order, full)
            else:
                prev_score, prev_order, _ = prev
                if score > prev_score:
                    best[real] = (score, prev_order, full)
            order += 1

    return [t[2] for t in sorted(best.values(), key=lambda x: x[1])]


# Fixed George Michael voice model (single-voice app)
GEORGE_MICHAEL_DIR = os.path.join(model_root_relative, "GeorgeMichael")


def _first_file_in_dir(relative_folder, exts):
    folder_abs = os.path.join(now_dir, relative_folder)
    if not os.path.isdir(folder_abs):
        return None
    for f in os.listdir(folder_abs):
        if f.startswith(("G_", "D_")):
            continue
        if any(f.endswith(ext) for ext in exts):
            return os.path.join(relative_folder, f)
    return None


GEORGE_MICHAEL_PTH = _first_file_in_dir(GEORGE_MICHAEL_DIR, (".pth", ".onnx")) or os.path.join(
    GEORGE_MICHAEL_DIR, "GeorgeMichael_350e_10850s.pth"
)
GEORGE_MICHAEL_INDEX = _first_file_in_dir(GEORGE_MICHAEL_DIR, (".index",)) or os.path.join(
    GEORGE_MICHAEL_DIR, "GeorgeMichael.index"
)

audio_paths = [
    os.path.join(root, name)
    for root, _, files in os.walk(audio_root_relative, topdown=False)
    for name in files
    if name.endswith(tuple(sup_audioext))
    and root == audio_root_relative
    and "_output" not in name
]

custom_embedders = [
    os.path.join(dirpath, dirname)
    for dirpath, dirnames, _ in os.walk(custom_embedder_root_relative)
    for dirname in dirnames
]


def update_sliders_formant(preset):
    with open(
        os.path.join(FORMANTSHIFT_DIR, f"{preset}.json"), "r", encoding="utf-8"
    ) as json_file:
        values = json.load(json_file)
    return (
        values["formant_qfrency"],
        values["formant_timbre"],
    )


def list_json_files(directory):
    return [f.rsplit(".", 1)[0] for f in os.listdir(directory) if f.endswith(".json")]


def output_path_fn(input_audio_path):
    original_name_without_extension = os.path.basename(input_audio_path).rsplit(".", 1)[
        0
    ]
    new_name = original_name_without_extension + "_output.wav"
    output_path = os.path.join(os.path.dirname(input_audio_path), new_name)
    return output_path


def _path_allowed_for_gradio(path):
    """Return True if path is under cwd or system temp (Gradio's allowed_paths)."""
    if not path or not os.path.isfile(path):
        return True
    abs_path = os.path.abspath(path)
    abs_cwd = os.path.abspath(now_dir)
    abs_temp = os.path.abspath(os.environ.get("GRADIO_TEMP_DIR", os.environ.get("TEMP", "")))
    if abs_cwd and abs_path.startswith(abs_cwd):
        return True
    if abs_temp and abs_path.startswith(abs_temp):
        return True
    return False


def _ensure_output_path_for_gradio(message, output_path):
    """If output is outside Gradio allowed dirs, copy to gradio_temp and return path for playback."""
    if not output_path or _path_allowed_for_gradio(output_path):
        return message, output_path
    gradio_temp = os.path.join(now_dir, "assets", "gradio_temp")
    os.makedirs(gradio_temp, exist_ok=True)
    base = os.path.basename(output_path)
    dest = os.path.join(gradio_temp, base)
    try:
        shutil.copy2(output_path, dest)
        return message, dest
    except Exception:
        return message, output_path


def browse_output_path(current_path, export_format):
    """Open a save-as dialog and return the chosen path, or current_path if cancelled."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return current_path
    root = tk.Tk()
    root.wm_attributes("-topmost", 1)
    root.withdraw()
    ext = ("." + export_format.lower()) if export_format else ".wav"
    filetypes = [
        (i18n("WAV files"), "*.wav"),
        (i18n("MP3 files"), "*.mp3"),
        (i18n("FLAC files"), "*.flac"),
        (i18n("OGG files"), "*.ogg"),
        (i18n("M4A files"), "*.m4a"),
        (i18n("All files"), "*.*"),
    ]
    initialdir = None
    initialfile = "output" + ext
    if current_path and current_path.strip():
        p = os.path.abspath(current_path)
        d = os.path.dirname(p)
        if os.path.isdir(d):
            initialdir = d
        if os.path.basename(p):
            initialfile = os.path.basename(p)
    path = filedialog.asksaveasfilename(
        defaultextension=ext,
        filetypes=filetypes,
        initialdir=initialdir,
        initialfile=initialfile,
        title=i18n("Save output audio as"),
    )
    root.destroy()
    return path if path else current_path


def browse_output_folder(current_path):
    """Open a directory dialog and return the chosen folder, or current_path if cancelled."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return current_path
    root = tk.Tk()
    root.wm_attributes("-topmost", 1)
    root.withdraw()
    initialdir = None
    if current_path and current_path.strip():
        p = os.path.abspath(current_path)
        if os.path.isdir(p):
            initialdir = p
        elif os.path.isdir(os.path.dirname(p)):
            initialdir = os.path.dirname(p)
    path = filedialog.askdirectory(
        initialdir=initialdir,
        title=i18n("Select output folder"),
    )
    root.destroy()
    return path if path else current_path


def change_choices(model):
    if model:
        speakers = get_speakers_id(model)
    else:
        speakers = [0]

    models_list = get_files("model")
    indexes_list = sorted(get_files("index"))

    audio_paths = [
        os.path.join(root, name)
        for root, _, files in os.walk(audio_root_relative, topdown=False)
        for name in files
        if name.endswith(tuple(sup_audioext))
        and root == audio_root_relative
        and "_output" not in name
    ]

    return (
        {"choices": sorted(models_list), "__type__": "update"},
        {"choices": sorted(indexes_list), "__type__": "update"},
        {"choices": sorted(audio_paths), "__type__": "update"},
        {
            "choices": (
                sorted(speakers)
                if speakers is not None and isinstance(speakers, (list, tuple))
                else [0]
            ),
            "__type__": "update",
        },
        {
            "choices": (
                sorted(speakers)
                if speakers is not None and isinstance(speakers, (list, tuple))
                else [0]
            ),
            "__type__": "update",
        },
    )


def extract_model_and_epoch(path):
    base_name = os.path.basename(path)
    match = re.match(r"(.+?)_(\d+)e_", base_name)
    if match:
        model, epoch = match.groups()
        return model, int(epoch)
    return "", 0


def save_to_wav(record_button):
    if record_button is None:
        pass
    else:
        path_to_file = record_button
        new_name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".wav"
        target_path = os.path.join(audio_root_relative, os.path.basename(new_name))

        shutil.move(path_to_file, target_path)
        return target_path, output_path_fn(target_path)


def save_to_wav2(upload_audio):
    file_path = upload_audio
    formated_name = format_title(os.path.basename(file_path))
    target_path = os.path.join(audio_root_relative, formated_name)

    if os.path.exists(target_path):
        os.remove(target_path)

    shutil.copy(file_path, target_path)
    return target_path, output_path_fn(target_path)


def folders_same(
    a: str, b: str
) -> bool:  # Used to "pair" index and model folders based on path names
    """
    True if:
      1) The two normalized paths are totally identical..OR
      2) One lives under a MODEL_FOLDER and the other lives
         under an INDEX_FOLDER, at the same relative subpath
         i.e.  logs/models/miku  and  logs/index/miku  =  "SAME FOLDER"
    """
    a = normalize_path(a)
    b = normalize_path(b)
    if a == b:
        return True

    def split_after_alias(p):
        parts = p.split("/")
        for i, part in enumerate(parts):
            if is_mdl_alias(part) or is_idx_alias(part):
                base = part
                rel = "/".join(parts[i + 1 :])
                return base, rel
        return None, None

    base_a, rel_a = split_after_alias(a)
    base_b, rel_b = split_after_alias(b)

    if rel_a is None or rel_b is None:
        return False

    if rel_a == rel_b and (
        (is_mdl_alias(base_a) and is_idx_alias(base_b))
        or (is_idx_alias(base_a) and is_mdl_alias(base_b))
    ):
        return True
    return False


def match_index(model_file_value):
    if not model_file_value:
        return ""

    # Derive the information about the model's name and path for index matching
    model_folder = normalize_path(os.path.dirname(model_file_value))
    model_name = os.path.basename(model_file_value)
    base_name = os.path.splitext(model_name)[0]
    common = re.sub(r"[_\-\.\+](?:e|s|v|V)\d.*$", "", base_name)
    prefix_match = re.match(r"^(.*?)[_\-\.\+]", base_name)
    prefix = prefix_match.group(1) if prefix_match else None

    same_count = 0
    last_same = None
    same_substr = None
    same_prefixed = None
    external_exact = None
    external_substr = None
    external_pref = None

    for idx in get_files("index"):
        idx_folder = os.path.dirname(idx)
        idx_folder_n = normalize_path(idx_folder)
        idx_name = os.path.basename(idx)
        idx_base = os.path.splitext(idx_name)[0]

        in_same = folders_same(model_folder, idx_folder_n)
        if in_same:
            same_count += 1
            last_same = idx

            # 1) EXACT match to loaded model name and folders_same = True
            if idx_base == base_name:
                return idx

            # 2) Substring match to model name and folders_same
            if common in idx_base and same_substr is None:
                same_substr = idx

            # 3) Prefix match to model name and folders_same
            if prefix and idx_base.startswith(prefix) and same_prefixed is None:
                same_prefixed = idx

        # If it's NOT in a paired folder (folders_same = False) we look elseware:
        else:
            # 4) EXACT match to model name in external directory
            if idx_base == base_name and external_exact is None:
                external_exact = idx

            # 5) Substring match to model name in ED
            if common in idx_base and external_substr is None:
                external_substr = idx

            # 6) Prefix match to model name in ED
            if prefix and idx_base.startswith(prefix) and external_pref is None:
                external_pref = idx

    # Fallback: If there is exactly one index file in the same (or paired) folder,
    # we should assume that's the intended index file even if the name doesnt match
    if same_count == 1:
        return last_same

    # Then by remaining priority queue:
    if same_substr:
        return same_substr
    if same_prefixed:
        return same_prefixed
    if external_exact:
        return external_exact
    if external_substr:
        return external_substr
    if external_pref:
        return external_pref

    return ""


def create_folder_and_move_files(folder_name, bin_file, config_file):
    if not folder_name:
        return "Folder name must not be empty."

    folder_name = os.path.basename(folder_name)
    target_folder = os.path.join(custom_embedder_root, folder_name)

    normalize_pathd_target_folder = os.path.abspath(target_folder)
    normalize_pathd_custom_embedder_root = os.path.abspath(custom_embedder_root)

    if not normalize_pathd_target_folder.startswith(
        normalize_pathd_custom_embedder_root
    ):
        return "Invalid folder name. Folder must be within the custom embedder root directory."

    os.makedirs(target_folder, exist_ok=True)

    if bin_file:
        shutil.copy(bin_file, os.path.join(target_folder, os.path.basename(bin_file)))
    if config_file:
        shutil.copy(
            config_file, os.path.join(target_folder, os.path.basename(config_file))
        )

    return f"Files moved to folder {target_folder}"


def refresh_formant():
    json_files = list_json_files(FORMANTSHIFT_DIR)
    return gr.update(choices=json_files)


def refresh_embedders_folders():
    custom_embedders = [
        os.path.join(dirpath, dirname)
        for dirpath, dirnames, _ in os.walk(custom_embedder_root_relative)
        for dirname in dirnames
    ]
    return custom_embedders


def get_speakers_id(model):
    if model:
        try:
            model_data = torch.load(
                os.path.join(now_dir, model), map_location="cpu", weights_only=True
            )
            speakers_id = model_data.get("speakers_id")
            if speakers_id:
                return list(range(speakers_id))
            else:
                return [0]
        except Exception as e:
            return [0]
    else:
        return [0]


def filter_dropdowns(filter_text):
    ft = (filter_text or "").lower()
    all_models = sorted(get_files("model"), key=extract_model_and_epoch)
    all_indexes = sorted(get_files("index"))
    filtered_models = [m for m in all_models if ft in m.lower()]
    filtered_indexes = [i for i in all_indexes if ft in i.lower()]
    return (gr.update(choices=filtered_models), gr.update(choices=filtered_indexes))


# Inference tab
def inference_tab():
    with gr.Column():
        model_file = gr.State(GEORGE_MICHAEL_PTH)
        index_file = gr.State(GEORGE_MICHAEL_INDEX)

    # Single inference tab
    with gr.Tab(i18n("Single")):
        with gr.Column():
            upload_audio = gr.Audio(
                label=i18n("Upload Audio"), type="filepath", editable=False
            )
            # Internal dropdown used to store the selected/last uploaded audio path.
            # Kept hidden from the UI so users only see the upload widget.
            audio = gr.Dropdown(
                label=i18n("Select Audio"),
                info=i18n("Select the audio to convert."),
                choices=sorted(audio_paths),
                value=audio_paths[0] if audio_paths else "",
                interactive=True,
                allow_custom_value=True,
                visible=False,
            )

        with gr.Accordion(i18n("Advanced Settings"), open=False):
            with gr.Column():
                with gr.Row():
                    output_path = gr.Textbox(
                        label=i18n("Output Path"),
                        placeholder=i18n("Enter output path"),
                        info=i18n(
                            "The path where the output audio will be saved, by default in assets/audios/output.wav"
                        ),
                        value=(
                            output_path_fn(audio_paths[0])
                            if audio_paths
                            else os.path.join(now_dir, "assets", "audios", "output.wav")
                        ),
                        interactive=True,
                        scale=4,
                    )
                    browse_output_btn = gr.Button(i18n("Browse"), scale=0)
                export_format = gr.Radio(
                    label=i18n("Export Format"),
                    info=i18n("Select the format to export the audio."),
                    choices=["WAV", "MP3", "FLAC", "OGG", "M4A"],
                    value="MP3",
                    interactive=True,
                )
                sid = gr.State(0)
                split_audio = gr.Checkbox(
                    label=i18n("Split Audio"),
                    info=i18n(
                        "Split the audio into chunks for inference to obtain better results in some cases."
                    ),
                    visible=True,
                    value=False,
                    interactive=True,
                )
                autotune = gr.Checkbox(
                    label=i18n("Autotune"),
                    info=i18n(
                        "Apply a soft autotune to your inferences, recommended for singing conversions."
                    ),
                    visible=True,
                    value=False,
                    interactive=True,
                )
                autotune_strength = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Autotune Strength"),
                    info=i18n(
                        "Set the autotune strength - the more you increase it the more it will snap to the chromatic grid."
                    ),
                    visible=False,
                    value=1,
                    interactive=True,
                )
                proposed_pitch = gr.Checkbox(
                    label=i18n("Proposed Pitch"),
                    info=i18n(
                        "Adjust the input audio pitch to match the voice model range."
                    ),
                    visible=True,
                    value=False,
                    interactive=True,
                )
                proposed_pitch_threshold = gr.Slider(
                    minimum=50.0,
                    maximum=1200.0,
                    label=i18n("Proposed Pitch Threshold"),
                    info=i18n(
                        "Male voice models typically use 155.0 and female voice models typically use 255.0."
                    ),
                    visible=False,
                    value=155.0,
                    interactive=True,
                )
                clean_audio = gr.Checkbox(
                    label=i18n("Clean Audio"),
                    info=i18n(
                        "Clean your audio output using noise detection algorithms, recommended for speaking audios."
                    ),
                    visible=True,
                    value=False,
                    interactive=True,
                )
                clean_strength = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Clean Strength"),
                    info=i18n(
                        "Set the clean-up level to the audio you want, the more you increase it the more it will clean up, but it is possible that the audio will be more compressed."
                    ),
                    visible=False,
                    value=0.5,
                    interactive=True,
                )
                formant_shifting = gr.Checkbox(
                    label=i18n("Formant Shifting"),
                    info=i18n(
                        "Enable formant shifting. Used for male to female and vice-versa convertions."
                    ),
                    value=False,
                    visible=True,
                    interactive=True,
                )
                post_process = gr.Checkbox(
                    label=i18n("Post-Process"),
                    info=i18n("Post-process the audio to apply effects to the output."),
                    value=False,
                    interactive=True,
                )
                with gr.Row(visible=False) as formant_row:
                    formant_preset = gr.Dropdown(
                        label=i18n("Browse presets for formanting"),
                        info=i18n(
                            "Presets are located in /assets/formant_shift folder"
                        ),
                        choices=list_json_files(FORMANTSHIFT_DIR),
                        visible=False,
                        interactive=True,
                    )
                    formant_refresh_button = gr.Button(
                        value=i18n("Refresh"),
                        visible=False,
                    )
                formant_qfrency = gr.Slider(
                    value=1.0,
                    info=i18n("Default value is 1.0"),
                    label=i18n("Quefrency for formant shifting"),
                    minimum=0.0,
                    maximum=16.0,
                    step=0.1,
                    visible=False,
                    interactive=True,
                )
                formant_timbre = gr.Slider(
                    value=1.0,
                    info=i18n("Default value is 1.0"),
                    label=i18n("Timbre for formant shifting"),
                    minimum=0.0,
                    maximum=16.0,
                    step=0.1,
                    visible=False,
                    interactive=True,
                )
                reverb = gr.Checkbox(
                    label=i18n("Reverb"),
                    info=i18n("Apply reverb to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                reverb_room_size = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Room Size"),
                    info=i18n("Set the room size of the reverb."),
                    value=0.5,
                    interactive=True,
                    visible=False,
                )
                reverb_damping = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Damping"),
                    info=i18n("Set the damping of the reverb."),
                    value=0.5,
                    interactive=True,
                    visible=False,
                )
                reverb_wet_gain = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Wet Gain"),
                    info=i18n("Set the wet gain of the reverb."),
                    value=0.33,
                    interactive=True,
                    visible=False,
                )
                reverb_dry_gain = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Dry Gain"),
                    info=i18n("Set the dry gain of the reverb."),
                    value=0.4,
                    interactive=True,
                    visible=False,
                )
                reverb_width = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Width"),
                    info=i18n("Set the width of the reverb."),
                    value=1.0,
                    interactive=True,
                    visible=False,
                )
                reverb_freeze_mode = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Freeze Mode"),
                    info=i18n("Set the freeze mode of the reverb."),
                    value=0.0,
                    interactive=True,
                    visible=False,
                )
                pitch_shift = gr.Checkbox(
                    label=i18n("Pitch Shift"),
                    info=i18n("Apply pitch shift to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                pitch_shift_semitones = gr.Slider(
                    minimum=-12,
                    maximum=12,
                    label=i18n("Pitch Shift Semitones"),
                    info=i18n("Set the pitch shift semitones."),
                    value=0,
                    interactive=True,
                    visible=False,
                )
                limiter = gr.Checkbox(
                    label=i18n("Limiter"),
                    info=i18n("Apply limiter to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                limiter_threshold = gr.Slider(
                    minimum=-60,
                    maximum=0,
                    label=i18n("Limiter Threshold dB"),
                    info=i18n("Set the limiter threshold dB."),
                    value=-6,
                    interactive=True,
                    visible=False,
                )
                limiter_release_time = gr.Slider(
                    minimum=0.01,
                    maximum=1,
                    label=i18n("Limiter Release Time"),
                    info=i18n("Set the limiter release time."),
                    value=0.05,
                    interactive=True,
                    visible=False,
                )
                gain = gr.Checkbox(
                    label=i18n("Gain"),
                    info=i18n("Apply gain to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                gain_db = gr.Slider(
                    minimum=-60,
                    maximum=60,
                    label=i18n("Gain dB"),
                    info=i18n("Set the gain dB."),
                    value=0,
                    interactive=True,
                    visible=False,
                )
                distortion = gr.Checkbox(
                    label=i18n("Distortion"),
                    info=i18n("Apply distortion to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                distortion_gain = gr.Slider(
                    minimum=-60,
                    maximum=60,
                    label=i18n("Distortion Gain"),
                    info=i18n("Set the distortion gain."),
                    value=25,
                    interactive=True,
                    visible=False,
                )
                chorus = gr.Checkbox(
                    label=i18n("Chorus"),
                    info=i18n("Apply chorus to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                chorus_rate = gr.Slider(
                    minimum=0,
                    maximum=100,
                    label=i18n("Chorus Rate Hz"),
                    info=i18n("Set the chorus rate Hz."),
                    value=1.0,
                    interactive=True,
                    visible=False,
                )
                chorus_depth = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Chorus Depth"),
                    info=i18n("Set the chorus depth."),
                    value=0.25,
                    interactive=True,
                    visible=False,
                )
                chorus_center_delay = gr.Slider(
                    minimum=7,
                    maximum=8,
                    label=i18n("Chorus Center Delay ms"),
                    info=i18n("Set the chorus center delay ms."),
                    value=7,
                    interactive=True,
                    visible=False,
                )
                chorus_feedback = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Chorus Feedback"),
                    info=i18n("Set the chorus feedback."),
                    value=0.0,
                    interactive=True,
                    visible=False,
                )
                chorus_mix = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Chorus Mix"),
                    info=i18n("Set the chorus mix."),
                    value=0.5,
                    interactive=True,
                    visible=False,
                )
                bitcrush = gr.Checkbox(
                    label=i18n("Bitcrush"),
                    info=i18n("Apply bitcrush to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                bitcrush_bit_depth = gr.Slider(
                    minimum=1,
                    maximum=32,
                    label=i18n("Bitcrush Bit Depth"),
                    info=i18n("Set the bitcrush bit depth."),
                    value=8,
                    interactive=True,
                    visible=False,
                )
                clipping = gr.Checkbox(
                    label=i18n("Clipping"),
                    info=i18n("Apply clipping to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                clipping_threshold = gr.Slider(
                    minimum=-60,
                    maximum=0,
                    label=i18n("Clipping Threshold"),
                    info=i18n("Set the clipping threshold."),
                    value=-6,
                    interactive=True,
                    visible=False,
                )
                compressor = gr.Checkbox(
                    label=i18n("Compressor"),
                    info=i18n("Apply compressor to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                compressor_threshold = gr.Slider(
                    minimum=-60,
                    maximum=0,
                    label=i18n("Compressor Threshold dB"),
                    info=i18n("Set the compressor threshold dB."),
                    value=0,
                    interactive=True,
                    visible=False,
                )
                compressor_ratio = gr.Slider(
                    minimum=1,
                    maximum=20,
                    label=i18n("Compressor Ratio"),
                    info=i18n("Set the compressor ratio."),
                    value=1,
                    interactive=True,
                    visible=False,
                )
                compressor_attack = gr.Slider(
                    minimum=0.0,
                    maximum=100,
                    label=i18n("Compressor Attack ms"),
                    info=i18n("Set the compressor attack ms."),
                    value=1.0,
                    interactive=True,
                    visible=False,
                )
                compressor_release = gr.Slider(
                    minimum=0.01,
                    maximum=100,
                    label=i18n("Compressor Release ms"),
                    info=i18n("Set the compressor release ms."),
                    value=100,
                    interactive=True,
                    visible=False,
                )
                delay = gr.Checkbox(
                    label=i18n("Delay"),
                    info=i18n("Apply delay to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                delay_seconds = gr.Slider(
                    minimum=0.0,
                    maximum=5.0,
                    label=i18n("Delay Seconds"),
                    info=i18n("Set the delay seconds."),
                    value=0.5,
                    interactive=True,
                    visible=False,
                )
                delay_feedback = gr.Slider(
                    minimum=0.0,
                    maximum=1.0,
                    label=i18n("Delay Feedback"),
                    info=i18n("Set the delay feedback."),
                    value=0.0,
                    interactive=True,
                    visible=False,
                )
                delay_mix = gr.Slider(
                    minimum=0.0,
                    maximum=1.0,
                    label=i18n("Delay Mix"),
                    info=i18n("Set the delay mix."),
                    value=0.5,
                    interactive=True,
                    visible=False,
                )
                pitch = gr.Slider(
                    minimum=-24,
                    maximum=24,
                    step=1,
                    label=i18n("Pitch"),
                    info=i18n(
                        "Set the pitch of the audio, the higher the value, the higher the pitch."
                    ),
                    value=0,
                    interactive=True,
                )
                index_rate = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Search Feature Ratio"),
                    info=i18n(
                        "Influence exerted by the index file; a higher value corresponds to greater influence. However, opting for lower values can help mitigate artifacts present in the audio."
                    ),
                    value=0.75,
                    interactive=True,
                )
                rms_mix_rate = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Volume Envelope"),
                    info=i18n(
                        "Substitute or blend with the volume envelope of the output. The closer the ratio is to 1, the more the output envelope is employed."
                    ),
                    value=1,
                    interactive=True,
                )
                protect = gr.Slider(
                    minimum=0,
                    maximum=0.5,
                    label=i18n("Protect Voiceless Consonants"),
                    info=i18n(
                        "Safeguard distinct consonants and breathing sounds to prevent electro-acoustic tearing and other artifacts. Pulling the parameter to its maximum value of 0.5 offers comprehensive protection. However, reducing this value might decrease the extent of protection while potentially mitigating the indexing effect."
                    ),
                    value=0.5,
                    interactive=True,
                )
                # Pitch extraction fixed to rmvpe (no UI)
                f0_method = gr.State("rmvpe")
                # Embedder fixed to spin-v2 (no UI)
                embedder_model = gr.State("spin-v2")
                embedder_model_custom = gr.State(None)

        def enforce_terms(*args):
            msg, out_path = run_infer_script(*args)
            return _ensure_output_path_for_gradio(msg, out_path)

        def enforce_terms_batch(*args):
            # Insert default input folder (batch has no Input Folder UI)
            default_input_folder = os.path.join(now_dir, "assets", "audios")
            full_args = args[:5] + (default_input_folder,) + args[5:]
            message = run_batch_infer_script(*full_args)
            # Restore Convert / hide Stop when batch completes
            return (
                message,
                gr.update(visible=True),
                gr.update(visible=False),
            )

        convert_button1 = gr.Button(i18n("Convert"))

        with gr.Row():
            vc_output1 = gr.Textbox(
                label=i18n("Output Information"),
                info=i18n("The output information will be displayed here."),
            )
            vc_output2 = gr.Audio(label=i18n("Export Audio"))

    # Batch inference tab
    with gr.Tab(i18n("Batch")):
        with gr.Row():
            with gr.Column():
                input_files_batch = gr.File(
                    label=i18n("Input Files"),
                    type="filepath",
                    file_count="multiple",
                    interactive=True,
                )
                with gr.Row():
                    output_folder_batch = gr.Textbox(
                        label=i18n("Output Folder"),
                        info=i18n(
                            "Select the folder where the output audios will be saved."
                        ),
                        placeholder=i18n("Enter output path"),
                        value=os.path.join(now_dir, "assets", "audios"),
                        interactive=True,
                        scale=4,
                    )
                    browse_output_folder_btn = gr.Button(i18n("Browse"), scale=0)
        with gr.Accordion(i18n("Advanced Settings"), open=False):
            with gr.Column():
                export_format_batch = gr.Radio(
                    label=i18n("Export Format"),
                    info=i18n("Select the format to export the audio."),
                    choices=["WAV", "MP3", "FLAC", "OGG", "M4A"],
                    value="MP3",
                    interactive=True,
                )
                sid_batch = gr.State(0)
                split_audio_batch = gr.Checkbox(
                    label=i18n("Split Audio"),
                    info=i18n(
                        "Split the audio into chunks for inference to obtain better results in some cases."
                    ),
                    visible=True,
                    value=False,
                    interactive=True,
                )
                autotune_batch = gr.Checkbox(
                    label=i18n("Autotune"),
                    info=i18n(
                        "Apply a soft autotune to your inferences, recommended for singing conversions."
                    ),
                    visible=True,
                    value=False,
                    interactive=True,
                )
                autotune_strength_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Autotune Strength"),
                    info=i18n(
                        "Set the autotune strength - the more you increase it the more it will snap to the chromatic grid."
                    ),
                    visible=False,
                    value=1,
                    interactive=True,
                )
                proposed_pitch_batch = gr.Checkbox(
                    label=i18n("Proposed Pitch"),
                    info=i18n(
                        "Adjust the input audio pitch to match the voice model range."
                    ),
                    visible=True,
                    value=False,
                    interactive=True,
                )
                proposed_pitch_threshold_batch = gr.Slider(
                    minimum=50.0,
                    maximum=1200.0,
                    label=i18n("Proposed Pitch Threshold"),
                    info=i18n(
                        "Male voice models typically use 155.0 and female voice models typically use 255.0."
                    ),
                    visible=False,
                    value=155.0,
                    interactive=True,
                )
                clean_audio_batch = gr.Checkbox(
                    label=i18n("Clean Audio"),
                    info=i18n(
                        "Clean your audio output using noise detection algorithms, recommended for speaking audios."
                    ),
                    visible=True,
                    value=False,
                    interactive=True,
                )
                clean_strength_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Clean Strength"),
                    info=i18n(
                        "Set the clean-up level to the audio you want, the more you increase it the more it will clean up, but it is possible that the audio will be more compressed."
                    ),
                    visible=False,
                    value=0.5,
                    interactive=True,
                )
                formant_shifting_batch = gr.Checkbox(
                    label=i18n("Formant Shifting"),
                    info=i18n(
                        "Enable formant shifting. Used for male to female and vice-versa convertions."
                    ),
                    value=False,
                    visible=True,
                    interactive=True,
                )
                post_process_batch = gr.Checkbox(
                    label=i18n("Post-Process"),
                    info=i18n("Post-process the audio to apply effects to the output."),
                    value=False,
                    interactive=True,
                )
                with gr.Row(visible=False) as formant_row_batch:
                    formant_preset_batch = gr.Dropdown(
                        label=i18n("Browse presets for formanting"),
                        info=i18n(
                            "Presets are located in /assets/formant_shift folder"
                        ),
                        choices=list_json_files(FORMANTSHIFT_DIR),
                        visible=False,
                        interactive=True,
                    )
                    formant_refresh_button_batch = gr.Button(
                        value=i18n("Refresh"),
                        visible=False,
                    )
                formant_qfrency_batch = gr.Slider(
                    value=1.0,
                    info=i18n("Default value is 1.0"),
                    label=i18n("Quefrency for formant shifting"),
                    minimum=0.0,
                    maximum=16.0,
                    step=0.1,
                    visible=False,
                    interactive=True,
                )
                formant_timbre_batch = gr.Slider(
                    value=1.0,
                    info=i18n("Default value is 1.0"),
                    label=i18n("Timbre for formant shifting"),
                    minimum=0.0,
                    maximum=16.0,
                    step=0.1,
                    visible=False,
                    interactive=True,
                )
                reverb_batch = gr.Checkbox(
                    label=i18n("Reverb"),
                    info=i18n("Apply reverb to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                reverb_room_size_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Room Size"),
                    info=i18n("Set the room size of the reverb."),
                    value=0.5,
                    interactive=True,
                    visible=False,
                )
                reverb_damping_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Damping"),
                    info=i18n("Set the damping of the reverb."),
                    value=0.5,
                    interactive=True,
                    visible=False,
                )
                reverb_wet_gain_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Wet Gain"),
                    info=i18n("Set the wet gain of the reverb."),
                    value=0.33,
                    interactive=True,
                    visible=False,
                )
                reverb_dry_gain_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Dry Gain"),
                    info=i18n("Set the dry gain of the reverb."),
                    value=0.4,
                    interactive=True,
                    visible=False,
                )
                reverb_width_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Width"),
                    info=i18n("Set the width of the reverb."),
                    value=1.0,
                    interactive=True,
                    visible=False,
                )
                reverb_freeze_mode_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Reverb Freeze Mode"),
                    info=i18n("Set the freeze mode of the reverb."),
                    value=0.0,
                    interactive=True,
                    visible=False,
                )
                pitch_shift_batch = gr.Checkbox(
                    label=i18n("Pitch Shift"),
                    info=i18n("Apply pitch shift to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                pitch_shift_semitones_batch = gr.Slider(
                    minimum=-12,
                    maximum=12,
                    label=i18n("Pitch Shift Semitones"),
                    info=i18n("Set the pitch shift semitones."),
                    value=0,
                    interactive=True,
                    visible=False,
                )
                limiter_batch = gr.Checkbox(
                    label=i18n("Limiter"),
                    info=i18n("Apply limiter to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                limiter_threshold_batch = gr.Slider(
                    minimum=-60,
                    maximum=0,
                    label=i18n("Limiter Threshold dB"),
                    info=i18n("Set the limiter threshold dB."),
                    value=-6,
                    interactive=True,
                    visible=False,
                )
                limiter_release_time_batch = gr.Slider(
                    minimum=0.01,
                    maximum=1,
                    label=i18n("Limiter Release Time"),
                    info=i18n("Set the limiter release time."),
                    value=0.05,
                    interactive=True,
                    visible=False,
                )
                gain_batch = gr.Checkbox(
                    label=i18n("Gain"),
                    info=i18n("Apply gain to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                gain_db_batch = gr.Slider(
                    minimum=-60,
                    maximum=60,
                    label=i18n("Gain dB"),
                    info=i18n("Set the gain dB."),
                    value=0,
                    interactive=True,
                    visible=False,
                )
                distortion_batch = gr.Checkbox(
                    label=i18n("Distortion"),
                    info=i18n("Apply distortion to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                distortion_gain_batch = gr.Slider(
                    minimum=-60,
                    maximum=60,
                    label=i18n("Distortion Gain"),
                    info=i18n("Set the distortion gain."),
                    value=25,
                    interactive=True,
                    visible=False,
                )
                chorus_batch = gr.Checkbox(
                    label=i18n("Chorus"),
                    info=i18n("Apply chorus to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                chorus_rate_batch = gr.Slider(
                    minimum=0,
                    maximum=100,
                    label=i18n("Chorus Rate Hz"),
                    info=i18n("Set the chorus rate Hz."),
                    value=1.0,
                    interactive=True,
                    visible=False,
                )
                chorus_depth_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Chorus Depth"),
                    info=i18n("Set the chorus depth."),
                    value=0.25,
                    interactive=True,
                    visible=False,
                )
                chorus_center_delay_batch = gr.Slider(
                    minimum=7,
                    maximum=8,
                    label=i18n("Chorus Center Delay ms"),
                    info=i18n("Set the chorus center delay ms."),
                    value=7,
                    interactive=True,
                    visible=False,
                )
                chorus_feedback_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Chorus Feedback"),
                    info=i18n("Set the chorus feedback."),
                    value=0.0,
                    interactive=True,
                    visible=False,
                )
                chorus_mix_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Chorus Mix"),
                    info=i18n("Set the chorus mix."),
                    value=0.5,
                    interactive=True,
                    visible=False,
                )
                bitcrush_batch = gr.Checkbox(
                    label=i18n("Bitcrush"),
                    info=i18n("Apply bitcrush to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                bitcrush_bit_depth_batch = gr.Slider(
                    minimum=1,
                    maximum=32,
                    label=i18n("Bitcrush Bit Depth"),
                    info=i18n("Set the bitcrush bit depth."),
                    value=8,
                    interactive=True,
                    visible=False,
                )
                clipping_batch = gr.Checkbox(
                    label=i18n("Clipping"),
                    info=i18n("Apply clipping to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                clipping_threshold_batch = gr.Slider(
                    minimum=-60,
                    maximum=0,
                    label=i18n("Clipping Threshold"),
                    info=i18n("Set the clipping threshold."),
                    value=-6,
                    interactive=True,
                    visible=False,
                )
                compressor_batch = gr.Checkbox(
                    label=i18n("Compressor"),
                    info=i18n("Apply compressor to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                compressor_threshold_batch = gr.Slider(
                    minimum=-60,
                    maximum=0,
                    label=i18n("Compressor Threshold dB"),
                    info=i18n("Set the compressor threshold dB."),
                    value=0,
                    interactive=True,
                    visible=False,
                )
                compressor_ratio_batch = gr.Slider(
                    minimum=1,
                    maximum=20,
                    label=i18n("Compressor Ratio"),
                    info=i18n("Set the compressor ratio."),
                    value=1,
                    interactive=True,
                    visible=False,
                )
                compressor_attack_batch = gr.Slider(
                    minimum=0.0,
                    maximum=100,
                    label=i18n("Compressor Attack ms"),
                    info=i18n("Set the compressor attack ms."),
                    value=1.0,
                    interactive=True,
                    visible=False,
                )
                compressor_release_batch = gr.Slider(
                    minimum=0.01,
                    maximum=100,
                    label=i18n("Compressor Release ms"),
                    info=i18n("Set the compressor release ms."),
                    value=100,
                    interactive=True,
                    visible=False,
                )
                delay_batch = gr.Checkbox(
                    label=i18n("Delay"),
                    info=i18n("Apply delay to the audio."),
                    value=False,
                    interactive=True,
                    visible=False,
                )
                delay_seconds_batch = gr.Slider(
                    minimum=0.0,
                    maximum=5.0,
                    label=i18n("Delay Seconds"),
                    info=i18n("Set the delay seconds."),
                    value=0.5,
                    interactive=True,
                    visible=False,
                )
                delay_feedback_batch = gr.Slider(
                    minimum=0.0,
                    maximum=1.0,
                    label=i18n("Delay Feedback"),
                    info=i18n("Set the delay feedback."),
                    value=0.0,
                    interactive=True,
                    visible=False,
                )
                delay_mix_batch = gr.Slider(
                    minimum=0.0,
                    maximum=1.0,
                    label=i18n("Delay Mix"),
                    info=i18n("Set the delay mix."),
                    value=0.5,
                    interactive=True,
                    visible=False,
                )
                pitch_batch = gr.Slider(
                    minimum=-24,
                    maximum=24,
                    step=1,
                    label=i18n("Pitch"),
                    info=i18n(
                        "Set the pitch of the audio, the higher the value, the higher the pitch."
                    ),
                    value=0,
                    interactive=True,
                )
                index_rate_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Search Feature Ratio"),
                    info=i18n(
                        "Influence exerted by the index file; a higher value corresponds to greater influence. However, opting for lower values can help mitigate artifacts present in the audio."
                    ),
                    value=0.75,
                    interactive=True,
                )
                rms_mix_rate_batch = gr.Slider(
                    minimum=0,
                    maximum=1,
                    label=i18n("Volume Envelope"),
                    info=i18n(
                        "Substitute or blend with the volume envelope of the output. The closer the ratio is to 1, the more the output envelope is employed."
                    ),
                    value=1,
                    interactive=True,
                )
                protect_batch = gr.Slider(
                    minimum=0,
                    maximum=0.5,
                    label=i18n("Protect Voiceless Consonants"),
                    info=i18n(
                        "Safeguard distinct consonants and breathing sounds to prevent electro-acoustic tearing and other artifacts. Pulling the parameter to its maximum value of 0.5 offers comprehensive protection. However, reducing this value might decrease the extent of protection while potentially mitigating the indexing effect."
                    ),
                    value=0.5,
                    interactive=True,
                )
                # Pitch extraction fixed to rmvpe (no UI)
                f0_method_batch = gr.State("rmvpe")
                # Embedder fixed to spin-v2 (no UI)
                embedder_model_batch = gr.State("spin-v2")
                embedder_model_custom_batch = gr.State(None)

        convert_button_batch = gr.Button(i18n("Convert"))
        stop_button = gr.Button(i18n("Stop convert"), visible=False)
        stop_button.click(fn=stop_infer, inputs=[], outputs=[])

        with gr.Row():
            vc_output3 = gr.Textbox(
                label=i18n("Output Information"),
                info=i18n("The output information will be displayed here."),
            )

    def toggle_visible(checkbox):
        return {"visible": checkbox, "__type__": "update"}

    def enable_stop_convert_button():
        return {"visible": False, "__type__": "update"}, {
            "visible": True,
            "__type__": "update",
        }

    def disable_stop_convert_button():
        return {"visible": True, "__type__": "update"}, {
            "visible": False,
            "__type__": "update",
        }

    def toggle_visible_formant_shifting(checkbox):
        if checkbox:
            return (
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
            )
        else:
            return (
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )

    def update_visibility(checkbox, count):
        return [gr.update(visible=checkbox) for _ in range(count)]

    def post_process_visible(checkbox):
        return update_visibility(checkbox, 10)

    def reverb_visible(checkbox):
        return update_visibility(checkbox, 6)

    def limiter_visible(checkbox):
        return update_visibility(checkbox, 2)

    def chorus_visible(checkbox):
        return update_visibility(checkbox, 6)

    def compress_visible(checkbox):
        return update_visibility(checkbox, 4)

    def delay_visible(checkbox):
        return update_visibility(checkbox, 3)

    autotune.change(
        fn=toggle_visible,
        inputs=[autotune],
        outputs=[autotune_strength],
    )
    proposed_pitch.change(
        fn=toggle_visible,
        inputs=[proposed_pitch],
        outputs=[proposed_pitch_threshold],
    )
    proposed_pitch_batch.change(
        fn=toggle_visible,
        inputs=[proposed_pitch_batch],
        outputs=[proposed_pitch_threshold_batch],
    )
    clean_audio.change(
        fn=toggle_visible,
        inputs=[clean_audio],
        outputs=[clean_strength],
    )
    formant_shifting.change(
        fn=toggle_visible_formant_shifting,
        inputs=[formant_shifting],
        outputs=[
            formant_row,
            formant_preset,
            formant_refresh_button,
            formant_qfrency,
            formant_timbre,
        ],
    )
    formant_shifting_batch.change(
        fn=toggle_visible_formant_shifting,
        inputs=[formant_shifting],
        outputs=[
            formant_row_batch,
            formant_preset_batch,
            formant_refresh_button_batch,
            formant_qfrency_batch,
            formant_timbre_batch,
        ],
    )
    formant_refresh_button.click(
        fn=refresh_formant,
        inputs=[],
        outputs=[formant_preset],
    )
    formant_preset.change(
        fn=update_sliders_formant,
        inputs=[formant_preset],
        outputs=[
            formant_qfrency,
            formant_timbre,
        ],
    )
    formant_preset_batch.change(
        fn=update_sliders_formant,
        inputs=[formant_preset_batch],
        outputs=[
            formant_qfrency,
            formant_timbre,
        ],
    )
    post_process.change(
        fn=post_process_visible,
        inputs=[post_process],
        outputs=[
            reverb,
            pitch_shift,
            limiter,
            gain,
            distortion,
            chorus,
            bitcrush,
            clipping,
            compressor,
            delay,
        ],
    )
    reverb.change(
        fn=reverb_visible,
        inputs=[reverb],
        outputs=[
            reverb_room_size,
            reverb_damping,
            reverb_wet_gain,
            reverb_dry_gain,
            reverb_width,
            reverb_freeze_mode,
        ],
    )
    pitch_shift.change(
        fn=toggle_visible,
        inputs=[pitch_shift],
        outputs=[pitch_shift_semitones],
    )
    limiter.change(
        fn=limiter_visible,
        inputs=[limiter],
        outputs=[limiter_threshold, limiter_release_time],
    )
    gain.change(
        fn=toggle_visible,
        inputs=[gain],
        outputs=[gain_db],
    )
    distortion.change(
        fn=toggle_visible,
        inputs=[distortion],
        outputs=[distortion_gain],
    )
    chorus.change(
        fn=chorus_visible,
        inputs=[chorus],
        outputs=[
            chorus_rate,
            chorus_depth,
            chorus_center_delay,
            chorus_feedback,
            chorus_mix,
        ],
    )
    bitcrush.change(
        fn=toggle_visible,
        inputs=[bitcrush],
        outputs=[bitcrush_bit_depth],
    )
    clipping.change(
        fn=toggle_visible,
        inputs=[clipping],
        outputs=[clipping_threshold],
    )
    compressor.change(
        fn=compress_visible,
        inputs=[compressor],
        outputs=[
            compressor_threshold,
            compressor_ratio,
            compressor_attack,
            compressor_release,
        ],
    )
    delay.change(
        fn=delay_visible,
        inputs=[delay],
        outputs=[delay_seconds, delay_feedback, delay_mix],
    )
    post_process_batch.change(
        fn=post_process_visible,
        inputs=[post_process_batch],
        outputs=[
            reverb_batch,
            pitch_shift_batch,
            limiter_batch,
            gain_batch,
            distortion_batch,
            chorus_batch,
            bitcrush_batch,
            clipping_batch,
            compressor_batch,
            delay_batch,
        ],
    )
    reverb_batch.change(
        fn=reverb_visible,
        inputs=[reverb_batch],
        outputs=[
            reverb_room_size_batch,
            reverb_damping_batch,
            reverb_wet_gain_batch,
            reverb_dry_gain_batch,
            reverb_width_batch,
            reverb_freeze_mode_batch,
        ],
    )
    pitch_shift_batch.change(
        fn=toggle_visible,
        inputs=[pitch_shift_batch],
        outputs=[pitch_shift_semitones_batch],
    )
    limiter_batch.change(
        fn=limiter_visible,
        inputs=[limiter_batch],
        outputs=[limiter_threshold_batch, limiter_release_time_batch],
    )
    gain_batch.change(
        fn=toggle_visible,
        inputs=[gain_batch],
        outputs=[gain_db_batch],
    )
    distortion_batch.change(
        fn=toggle_visible,
        inputs=[distortion_batch],
        outputs=[distortion_gain_batch],
    )
    chorus_batch.change(
        fn=chorus_visible,
        inputs=[chorus_batch],
        outputs=[
            chorus_rate_batch,
            chorus_depth_batch,
            chorus_center_delay_batch,
            chorus_feedback_batch,
            chorus_mix_batch,
        ],
    )
    bitcrush_batch.change(
        fn=toggle_visible,
        inputs=[bitcrush_batch],
        outputs=[bitcrush_bit_depth_batch],
    )
    clipping_batch.change(
        fn=toggle_visible,
        inputs=[clipping_batch],
        outputs=[clipping_threshold_batch],
    )
    compressor_batch.change(
        fn=compress_visible,
        inputs=[compressor_batch],
        outputs=[
            compressor_threshold_batch,
            compressor_ratio_batch,
            compressor_attack_batch,
            compressor_release_batch,
        ],
    )
    delay_batch.change(
        fn=delay_visible,
        inputs=[delay_batch],
        outputs=[delay_seconds_batch, delay_feedback_batch, delay_mix_batch],
    )
    autotune_batch.change(
        fn=toggle_visible,
        inputs=[autotune_batch],
        outputs=[autotune_strength_batch],
    )
    clean_audio_batch.change(
        fn=toggle_visible,
        inputs=[clean_audio_batch],
        outputs=[clean_strength_batch],
    )
    audio.change(
        fn=output_path_fn,
        inputs=[audio],
        outputs=[output_path],
    )
    browse_output_btn.click(
        fn=browse_output_path,
        inputs=[output_path, export_format],
        outputs=[output_path],
    )
    upload_audio.upload(
        fn=save_to_wav2,
        inputs=[upload_audio],
        outputs=[audio, output_path],
    )
    upload_audio.stop_recording(
        fn=save_to_wav,
        inputs=[upload_audio],
        outputs=[audio, output_path],
    )
    convert_button1.click(
        fn=enforce_terms,
        inputs=[
            pitch,
            index_rate,
            rms_mix_rate,
            protect,
            f0_method,
            audio,
            output_path,
            model_file,
            index_file,
            split_audio,
            autotune,
            autotune_strength,
            proposed_pitch,
            proposed_pitch_threshold,
            clean_audio,
            clean_strength,
            export_format,
            embedder_model,
            embedder_model_custom,
            formant_shifting,
            formant_qfrency,
            formant_timbre,
            post_process,
            reverb,
            pitch_shift,
            limiter,
            gain,
            distortion,
            chorus,
            bitcrush,
            clipping,
            compressor,
            delay,
            reverb_room_size,
            reverb_damping,
            reverb_wet_gain,
            reverb_dry_gain,
            reverb_width,
            reverb_freeze_mode,
            pitch_shift_semitones,
            limiter_threshold,
            limiter_release_time,
            gain_db,
            distortion_gain,
            chorus_rate,
            chorus_depth,
            chorus_center_delay,
            chorus_feedback,
            chorus_mix,
            bitcrush_bit_depth,
            clipping_threshold,
            compressor_threshold,
            compressor_ratio,
            compressor_attack,
            compressor_release,
            delay_seconds,
            delay_feedback,
            delay_mix,
            sid,
        ],
        outputs=[vc_output1, vc_output2],
    )
    browse_output_folder_btn.click(
        fn=browse_output_folder,
        inputs=[output_folder_batch],
        outputs=[output_folder_batch],
    )
    convert_button_batch.click(
        fn=enforce_terms_batch,
        inputs=[
            pitch_batch,
            index_rate_batch,
            rms_mix_rate_batch,
            protect_batch,
            f0_method_batch,
            output_folder_batch,
            model_file,
            index_file,
            split_audio_batch,
            autotune_batch,
            autotune_strength_batch,
            proposed_pitch_batch,
            proposed_pitch_threshold_batch,
            clean_audio_batch,
            clean_strength_batch,
            export_format_batch,
            embedder_model_batch,
            embedder_model_custom_batch,
            formant_shifting_batch,
            formant_qfrency_batch,
            formant_timbre_batch,
            post_process_batch,
            reverb_batch,
            pitch_shift_batch,
            limiter_batch,
            gain_batch,
            distortion_batch,
            chorus_batch,
            bitcrush_batch,
            clipping_batch,
            compressor_batch,
            delay_batch,
            reverb_room_size_batch,
            reverb_damping_batch,
            reverb_wet_gain_batch,
            reverb_dry_gain_batch,
            reverb_width_batch,
            reverb_freeze_mode_batch,
            pitch_shift_semitones_batch,
            limiter_threshold_batch,
            limiter_release_time_batch,
            gain_db_batch,
            distortion_gain_batch,
            chorus_rate_batch,
            chorus_depth_batch,
            chorus_center_delay_batch,
            chorus_feedback_batch,
            chorus_mix_batch,
            bitcrush_bit_depth_batch,
            clipping_threshold_batch,
            compressor_threshold_batch,
            compressor_ratio_batch,
            compressor_attack_batch,
            compressor_release_batch,
            delay_seconds_batch,
            delay_feedback_batch,
            delay_mix_batch,
            sid_batch,
            input_files_batch,
        ],
        outputs=[vc_output3, convert_button_batch, stop_button],
    )
    convert_button_batch.click(
        fn=enable_stop_convert_button,
        inputs=[],
        outputs=[convert_button_batch, stop_button],
    )
    stop_button.click(
        fn=disable_stop_convert_button,
        inputs=[],
        outputs=[convert_button_batch, stop_button],
    )
