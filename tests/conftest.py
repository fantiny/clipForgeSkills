"""Small, explicitly synthetic local media fixtures; no provider calls."""
from pathlib import Path
import pytest
from clipforge_skills.core import run
from clipforge_skills.library import Library


@pytest.fixture(scope="session")
def media_dir(tmp_path_factory):
    root = tmp_path_factory.mktemp("media") / "中文 素材"
    root.mkdir()
    for name, color, freq in [("first", "red", 440), ("second", "blue", 660)]:
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=320x480:r=30:d=3",
             "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", root / f"{name}.mp4"])
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=4", root / "narration.wav"])
    return root


@pytest.fixture
def library(tmp_path, media_dir):
    lib = Library(tmp_path / "data")
    result = lib.ingest(media_dir, {"sku": "test", "packaging": "not_applicable", "source_kind": "technical_fixture",
                                   "rights": {"status": "confirmed", "scopes": ["test"], "evidence": "Generated test signals in conftest.py"}})
    assert not result["errors"]
    return lib


@pytest.fixture
def plan(library):
    assets = library.records()
    vids = [a for a in assets if a["technical"]["has_video"]]
    aud = next(a for a in assets if not a["technical"]["has_video"])
    return {"schema_version": 1, "content_id": "test-story", "purpose": "technical_test",
            "brief": {"scenario": "service", "sku": "test", "audience": "test operators", "channel": "test", "cta": None},
            "canvas": {"width": 320, "height": 480, "fps": 30},
            "clips": [{"asset_id": a["asset_id"], "start": 0, "end": 2, "role": "body", "audio": "mute"} for a in vids],
            "subtitles": [{"start": .5, "end": 3.5, "text": "技术测试\n跨镜字幕", "fact_ids": []}],
            "audio": [{"asset_id": aud["asset_id"], "start": 0, "source_start": 0, "duration": 4, "gain_db": -6, "role": "narration"}],
            "fact_ids": [], "style": {"font_size": 24, "color": "#FFFFFF"}}
