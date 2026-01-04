import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import uuid
import subprocess
from catboxpy.catbox import CatboxClient
import functools

# -----------------------------
# CONFIG
# -----------------------------
TOKEN = "nuh uh"
GUILD_ID = replaceme
TEMP_DIR = "temp"
LOG_FILE = "FFMPEGLog.log"

os.makedirs(TEMP_DIR, exist_ok=True)

# -----------------------------
# PRESETS
# -----------------------------
PRESETS = {
    "custom": {},
    "bgm74": {
        "video": "negate,hue=h=180,lenscorrection=0.5:0.5:0.3:0.9,lenscorrection=0.5:0.5:-0.1:-0.3,lenscorrection=0.5:0.5:-0.1:-0.3",
        "audio": "[0:a]rubberband=formant=634:pitch=2^(-3/12)[a1];"
                 "[0:a]rubberband=formant=634:pitch=2^(2/12)[a2];"
                 "[a1][a2]amix=2,volume=1.75,atrim=0.01[outa]",
        "audio_label": "outa"
    },
    "reverse": {"video": "-vf reverse", "audio": "-af areverse"},
    "v916": {"video": "scale='min(1080,iw)':-1:force_original_aspect_ratio=decrease,pad=1080:1920:(1080-iw)/2:(1920-ih)/2", "audio": ""},
    "v169": {"video": "scale='min(1920,iw)':-1:force_original_aspect_ratio=decrease,pad=1920:1080:(1920-iw)/2:(1080-ih)/2", "audio": ""},
    "v11": {"video": "scale='min(1080,iw)':-1:force_original_aspect_ratio=decrease,pad=1080:1080:(1080-iw)/2:(1080-ih)/2", "audio": ""},
    "xm159": {
        "video": "split=3[a][b][t];[a]format=gray,curves=r=0/1 0.5/1 1/0:g=0/1 0.5/0 1/0:b=0/1 0.5/1 1/0[aa];"
                 "[b]format=gray,curves=all=0/1 0.5/1 1/1[bb];[aa][bb]alphamerge[c];[t][c]overlay,format=yuv420p",
        "audio": "[0:a]rubberband=pitch=2^(7/12):window=short:"  
                 "transients=crisp:detector=2.14748e+09/4.9[a1];"
                 "[0:a]rubberband=pitch=2^(-5/12):window=short:"
                 "transients=crisp:detector=2.14748e+09/4.9[a2];"
                 "[a1][a2]amix=2,volume=2,atrim=0.02[outa]",
        "audio_label": "outa"
    },
    "pgrender": {"video": "colorspace=iall=bt470bg:all=bt470bg:space=bt709,format=yuvj420p", "audio": ""},
    "nsb_ffmpeg1": {
        "video": "colorchannelmixer=0:0:1:0:0:1:0:0:1:0:0:0:0.0:0:1,hue=h=100",
        "audio": "[0:a]rubberband=pitch=2^(-4.5/12):window=short:"
                 "transients=crisp:detector=2.14748e+09/4.9:pitchq=consistency[a1];"
                 "[0:a]rubberband=pitch=2^(4.5/12):window=short:"
                 "transients=crisp:detector=2.14748e+09/4.9:pitchq=consistency[a2];"
                 "[a1][a2]amix=2,volume=2[outa]",
        "audio_label": "outa"
    },
    "corruption": {"video": "scale=480:320,setsar=1:1", "audio": "volume=50dB"},
    "gm100": {
        "video": "colorchannelmixer=0:0:1:0:0:1:0:0:1:0:0:0,hue=h=100,"
                 "crop=iw/2:ih:0:0,split[left][tmp];"
                 "[tmp]hflip[right];[left][right]hstack,format=yuv444p,scale=640:-1,"
                 "geq='p(X+sin(0/10+Y/30)*27,(Y+sin(0/10+X*1.8/100)*15))',"
                 "scale=iw:ih,format=yuv420p",
        "audio": "[0:a]rubberband=pitch=2^(-5/12):window=short:"
                 "transients=crisp:detector=2.14748e+09/4.9[a1];"
                 "[0:a]rubberband=pitch=2^(-1/12):window=short:"
                 "transients=crisp:detector=2.14748e+09/4.9[a2];"
                 "[a1][a2]amix=2,volume=2,atrim=0.02[outa]",
        "audio_label": "outa"
    },
    "gm16": {
        "video": "movie=hslhue_-150.ppm,[in]haldclut,huesaturation=-0.12:strength=100,negate,hflip",
        "audio": "[0:a]rubberband=pitch=2^(0/12):window=short:"
                 "transients=crisp:detector=2.14748e+09/4.9,atrim=-0.01[a1];"
                 "[0:a]rubberband=pitch=2^(-3/12):window=short:"
                 "transients=crisp:detector=2.14748e+09/4.9[a2];"
                 "[a1][a2]amix=2,volume=1.5,atrim=0.02,highpass=f=20[outa]",
        "audio_label": "outa"
    },
    "autovocoding": {"video": None, "audio": None, "audio_label": "outa"}
}

# -----------------------------
# LOGGING
# -----------------------------
def append_log(cmd, stderr):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\nCOMMAND: {' '.join(cmd)}\n")
        f.write(stderr.decode(errors="ignore"))
        f.write("\n" + "="*80 + "\n")

# -----------------------------
# Build FFmpeg Command
# -----------------------------
def build_ffmpeg_cmd(input_path, output_path, preset_name, custom_args=None, export_length=None):
    cmd = ["ffmpeg", "-y", "-i", input_path,
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-threads", "0"]

    # duration if specified
    if export_length is not None:
        cmd += ["-t", str(export_length)]

    # custom raw args override
    if preset_name == "custom":
        if not custom_args:
            raise ValueError("Custom args required for preset=custom")
        cmd += custom_args.strip().split(" ")
    elif preset_name == "autovocoding":
        # download LUT
        tmp_lut = os.path.join(TEMP_DIR, f"{uuid.uuid4()}_lut.cube")
        lut_url = ("https://cdn.discordapp.com/attachments/1406347956755497091/"
                   "1446178917760106597/Autovocoding.cube"
                   "?ex=69345c12&is=69330a92&hm=6eb9e6fea0eca48833148656c756498907510fe21ad9cd51437db6a1606667a8&")
        subprocess.run(["curl", "-s", lut_url, "-o", tmp_lut], check=True)

        abs_lut = os.path.abspath(tmp_lut).replace("\\", "/")
        drive, rest = abs_lut.split(":/", 1)
        escaped_lut = f"{drive}\\:/{rest}"

        cmd += ["-vf", f"lut3d=file={escaped_lut},format=yuv420p"]
    else:
        preset = PRESETS.get(preset_name)
        if preset and preset.get("video"):
            cmd += ["-vf", preset["video"]]
        if preset and preset.get("audio"):
            cmd += ["-filter_complex", preset["audio"]]
            cmd += ["-map", "0:v", "-map", f"[{preset['audio_label']}]"]

    cmd += [output_path]
    return cmd

async def run_ffmpeg(input_path, output_path, preset_name, custom_args=None, export_length=None):
    cmd = build_ffmpeg_cmd(input_path, output_path, preset_name, custom_args, export_length)
    proc = await asyncio.create_subprocess_exec(*cmd,
                                                stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    append_log(cmd, stderr)
    if proc.returncode != 0:
        raise RuntimeError("FFmpeg failed — see log.")

# -----------------------------
# Catbox Upload
# -----------------------------
async def upload_to_catbox(path: str) -> str:
    def do_upload(p):
        client = CatboxClient()
        return client.upload(p)
    try:
        url = await asyncio.get_event_loop().run_in_executor(None, functools.partial(do_upload, path))
    except Exception as e:
        return f"❌ Upload failed: {e}"
    return url

# -----------------------------
# CREATE BOT
# -----------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} online! Syncing slash commands…")

    guild = discord.Object(id=GUILD_ID)

    # Clear only the *guild* commands
    bot.tree.clear_commands(guild=guild)

    # Sync the updated commands to that guild
    await bot.tree.sync(guild=guild)

    print("Slash commands synced.")

# -----------------------------
# /ffmpeg_any (with custom)
# -----------------------------
@bot.tree.command(name="ffmpeg_any", description="Run an FFmpeg preset (or custom args)")
@app_commands.describe(
    preset="Choose a preset (or custom)",
    file="Upload video/audio",
    custom="Custom raw FFmpeg args (when preset=custom)"
)
@app_commands.choices(preset=[app_commands.Choice(name=k, value=k) for k in PRESETS.keys()])
async def ffmpeg_any(
    interaction: discord.Interaction,
    preset: app_commands.Choice[str],
    file: discord.Attachment,
    custom: str = None
):
    await interaction.response.defer(thinking=True)

    uid = str(uuid.uuid4())
    in_path = os.path.join(TEMP_DIR, f"{uid}_{file.filename}")
    out_path = os.path.join(TEMP_DIR, f"{uid}_out.mp4")
    await file.save(in_path)

    try:
        await run_ffmpeg(in_path, out_path, preset.value, custom)
    except Exception:
        await interaction.followup.send(file=discord.File(LOG_FILE))
        try: os.remove(in_path)
        except: pass
        return

    size = os.path.getsize(out_path)
    if size < 8 * 1024 * 1024:
        await interaction.followup.send(file=discord.File(out_path))
    else:
        link = await upload_to_catbox(out_path)
        await interaction.followup.send(f"📦 Catbox: {link}")

    try: os.remove(in_path); os.remove(out_path)
    except: pass

# -----------------------------
# /ihtx (with custom)
# -----------------------------
@bot.tree.command(name="ihtx", description="Run IHTX effect (can use custom ffmpeg)")
@app_commands.describe(
    preset="Choose a preset (or custom)",
    file="Upload video/audio",
    export_length="Length of each segment (seconds)",
    powers="Number of powers",
    custom="Custom raw FFmpeg args (when preset=custom)"
)
@app_commands.choices(preset=[app_commands.Choice(name=k, value=k) for k in PRESETS.keys()])
async def ihtx(
    interaction: discord.Interaction,
    preset: app_commands.Choice[str],
    file: discord.Attachment,
    export_length: float,
    powers: int,
    custom: str = None
):
    await interaction.response.defer(thinking=True)

    uid = str(uuid.uuid4())
    orig = os.path.join(TEMP_DIR, f"{uid}_orig_{file.filename}")
    await file.save(orig)

    segments = []
    for i in range(powers):
        seg_out = os.path.join(TEMP_DIR, f"{uid}_seg_{i}.mp4")
        try:
            await run_ffmpeg(orig if i == 0 else segments[-1],
                             seg_out, preset.value, custom, export_length)
        except Exception:
            await interaction.followup.send(file=discord.File(LOG_FILE))
            try: os.remove(orig)
            except: pass
            return
        segments.append(seg_out)

    # write concat list
    list_file = os.path.join(TEMP_DIR, f"{uid}_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for seg in segments:
            abs_path = os.path.abspath(seg).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")

    final_out = os.path.join(TEMP_DIR, f"{uid}_final.mp4")
    concat_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", final_out]
    proc = await asyncio.create_subprocess_exec(*concat_cmd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    append_log(concat_cmd, stderr)

    size = os.path.getsize(final_out)
    if size < 8 * 1024 * 1024:
        await interaction.followup.send(file=discord.File(final_out))
    else:
        link = await upload_to_catbox(final_out)
        await interaction.followup.send(f"📦 Catbox: {link}")

    for p in [orig, list_file, final_out] + segments:
        try: os.remove(p)
        except: pass

bot.run('MTQ1NjU4NDYxNjUzMzI5OTM0Mw.GkLrAi.MZH_rqkAZs6DMS0WbfEZub32AghMvPIADsar_w')

