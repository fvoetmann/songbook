import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = ROOT / "downloads"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest


# A handful of real, previously-downloaded UG pages that exercise different
# save formats (plain saved page vs. browser view-source dump) and content
# shapes (chords, tab, multi-section).
SAMPLE_UG_FILES = [
    "the-cure_just-like-heaven-chords-39230.html",
    "view-source_https___tabs.ultimate-guitar.com_tab_683498.html",
    "JULIA CHORDS (ver 2) by The Beatles @ Ultimate-Guitar.Com.html",
]


@pytest.fixture(params=SAMPLE_UG_FILES)
def ug_sample_path(request):
    path = DOWNLOADS_DIR / request.param
    if not path.exists():
        pytest.skip(f"fixture-fil mangler: {path}")
    return path
