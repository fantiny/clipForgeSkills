"""Literal captions with independent cue timing and bounded layout."""
from pathlib import Path
import platform


def default_font():
    return {'Windows': 'Microsoft YaHei', 'Darwin': 'Arial Unicode MS'}.get(platform.system(), 'Noto Sans CJK SC')


def timestamp(seconds, srt=False):
    unit = 1000 if srt else 100
    n = round(seconds * unit)
    hours, n = divmod(n, 3600 * unit)
    minutes, n = divmod(n, 60 * unit)
    secs, fraction = divmod(n, unit)
    return f"{hours:02}:{minutes:02}:{secs:02},{fraction:03}" if srt else f"{hours}:{minutes:02}:{secs:02}.{fraction:02}"


def literal_text(text):
    return text.replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}').replace('\n', '\\N').replace('\r', '')


def overlay_events(plan, canvas, scale):
    events = []
    for item in plan.get('overlays', []):
        b = item['box']
        x = round((b['x'] + b['width'] / 2) * canvas['width'])
        y = round((b['y'] + b['height'] / 2) * canvas['height'])
        rgb = item['color'][1:]
        color = rgb[4:6] + rgb[2:4] + rgb[:2]
        size = max(8, round(item['font_size'] * scale))
        fade_in, fade_out = (round(item.get(k, 0) * 1000) for k in ('fade_in', 'fade_out'))
        tags = f'{{\\an5\\pos({x},{y})\\fs{size}\\c&H{color}&\\b1\\q2\\fad({fade_in},{fade_out})}}'
        style = 'Panel' if item['kind'] == 'card' else 'Default'
        events.append(f"Dialogue: 2,{timestamp(item['start'])},{timestamp(item['end'])},{style},,0,0,0,,{tags}{literal_text(item['text'])}")
    return events


def write_captions(plan, work, canvas):
    scale = canvas["width"] / plan["canvas"]["width"]
    size = max(8, round(plan["style"]["font_size"] * scale))
    color = plan["style"]["color"].lstrip("#")
    bgr = color[4:6] + color[2:4] + color[0:2]
    font = plan["style"].get("font_name", default_font())
    margin = max(10, round(canvas["height"] * .15))
    ass = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {canvas['width']}",
           f"PlayResY: {canvas['height']}", "WrapStyle: 2", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
           f"Style: Default,{font},{size},&H00{bgr},&H00{bgr},&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,20,20,{margin},1",
           f"Style: Panel,{font},{size},&H00{bgr},&H00{bgr},&H40000000,&H80000000,0,0,0,0,100,100,0,0,3,8,0,5,20,20,{margin},1",
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    srt = []
    if plan['purpose'] == 'internal_review':
        duration = sum(c['end'] - c['start'] for c in plan['clips'])
        mark_size = max(12, round(canvas['width'] * .036))
        x, y = canvas['width'] // 2, round(canvas['height'] * .07)
        mark = f'{{\\an8\\pos({x},{y})\\fs{mark_size}\\c&HFFFFFF&\\bord2}}内部审阅 · 信息待确认'
        ass.append(f'Dialogue: 10,0:00:00.00,{timestamp(duration)},Default,,0,0,0,,{mark}')
    for i, cue in enumerate(plan["subtitles"], 1):
        literal = literal_text(cue['text'])
        ass.append(f"Dialogue: 0,{timestamp(cue['start'])},{timestamp(cue['end'])},Default,,0,0,0,,{literal}")
        srt.append(f"{i}\n{timestamp(cue['start'], True)} --> {timestamp(cue['end'], True)}\n{cue['text']}\n")
    ass.extend(overlay_events(plan, canvas, scale))
    work = Path(work)
    (work / "captions.ass").write_text("\n".join(ass), encoding="utf-8")
    (work / "captions.srt").write_text("\n".join(srt), encoding="utf-8")
