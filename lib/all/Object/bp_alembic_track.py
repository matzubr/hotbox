#label:Last Alembic Track
#package:blackpoint
#textcolor:#a0ceff
#icon:SOP_alembic

import re
from pathlib import Path

import hou

VERSION_PATTERN = re.compile(r"v(\d+)")


def main():
    job = hou.getenv("JOB")
    if not job:
        hou.ui.displayMessage("$JOB is not set")
        return

    publish_folder = Path(job, "track", "publish")
    if not publish_folder.is_dir():
        hou.ui.displayMessage(f"No folder found:\n{publish_folder.as_posix()}")
        return

    # Latest version by number (iterdir order is arbitrary, and v10 sorts before v9 as text)
    versions = [(int(m.group(1)), x) for x in publish_folder.iterdir() if x.is_dir() and (m := VERSION_PATTERN.search(x.name))]
    if not versions:
        hou.ui.displayMessage("no track folder found")
        return
    track_folder = max(versions)[1]

    alembics = sorted(x for x in track_folder.iterdir() if x.suffix == ".abc")
    if not alembics:
        hou.ui.displayMessage(f"no alembics found in {track_folder.as_posix()}")
        return

    network_panetab = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    network = network_panetab.pwd()

    null = network.createNode("null", "scale")
    null.parm("scale").set(0.01)
    null.setDisplayFlag(False)
    null.setSelectableInViewport(False)
    null.setPosition(network_panetab.cursorPosition())
    null.setColor(hou.Color(0.1, 0.1, 0.1))
    null.setSelected(True, clear_all_selected=True, show_asset_if_selected=False)

    alembic_file = alembics[0]
    alembic = null.createOutputNode("alembicarchive", alembic_file.stem)
    alembic.parm("fileName").set(alembic_file.as_posix().replace(Path(job).as_posix(), "$JOB"))
    alembic.setSelectableInViewport(False)
    alembic.parm("buildHierarchy").pressButton()
    alembic.setSelected(True, clear_all_selected=False, show_asset_if_selected=False)


main()
