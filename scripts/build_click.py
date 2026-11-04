#!/usr/bin/env python3
"""
Build script for Joplin UT Click package.
Produces a compliant Debian binary .click package with valid permissions and
metadata ready for submission to the OpenStore.
"""

import hashlib
import io
import json
import math
import os
import pathlib
import subprocess
import tarfile
import tempfile
import time

def build_click():
    root = pathlib.Path(__file__).resolve().parent.parent
    manifest_data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    version = manifest_data["version"]
    pkg_name = manifest_data["name"]
    maintainer = manifest_data["maintainer"]
    title = manifest_data["title"]

    click_filename = f"{pkg_name}_{version}_all.click"

    # Source files to pack
    files_to_pack = [
        "assets/logo.svg",
        "assets/logo-512.png",
        "joplin-ut.apparmor",
        "joplin-ut.desktop",
        "qml/Main.qml",
        "qml/components/NotebookDrawer.qml",
        "qml/pages/NoteEditPage.qml",
        "qml/pages/NotesListPage.qml",
        "qml/pages/SettingsPage.qml",
        "src/__init__.py",
        "src/config.py",
        "src/db.py",
        "src/joplin_parser.py",
        "src/main.py",
        "src/sync.py",
        "src/webdav.py",
    ]

    # Dirs needed in data.tar.gz
    dirs_to_create = [
        ".",
        "assets",
        "qml",
        "qml/components",
        "qml/pages",
        "src",
    ]

    total_bytes = sum((root / rel).stat().st_size for rel in files_to_pack)
    installed_kb = max(1, math.ceil(total_bytes / 1024))
    manifest_data["installed-size"] = str(installed_kb)

    md5_lines = []
    for rel in files_to_pack:
        h = hashlib.md5((root / rel).read_bytes()).hexdigest()
        md5_lines.append(f"{h}  {rel}")
    md5sums_content = "\n".join(md5_lines) + "\n"

    control_content = (
        f"Package: {pkg_name}\n"
        f"Version: {version}\n"
        f"Click-Version: 0.4\n"
        f"Architecture: all\n"
        f"Maintainer: {maintainer}\n"
        f"Installed-Size: {installed_kb}\n"
        f"Description: {title}\n"
    )

    manifest_content = json.dumps(manifest_data, indent=4, sort_keys=True) + "\n"
    preinst_content = (
        "#! /bin/sh\n"
        "echo \"Click packages may not be installed directly using dpkg.\"\n"
        "echo \"Use 'click install' instead.\"\n"
        "exit 1\n"
    )

    fixed_mtime = int(time.time())

    def reset_tarinfo(ti, is_dir=False, mode=None):
        ti.uid = 0
        ti.gid = 0
        ti.uname = "root"
        ti.gname = "root"
        ti.mtime = fixed_mtime
        if mode is not None:
            ti.mode = mode
        elif is_dir:
            ti.mode = 0o755
        else:
            ti.mode = 0o644
        return ti

    with tempfile.TemporaryDirectory() as td:
        tpath = pathlib.Path(td)

        # 1. debian-binary
        (tpath / "debian-binary").write_bytes(b"2.0\n")

        # 2. _click-binary
        (tpath / "_click-binary").write_bytes(b"0.4\n")

        # 3. control.tar.gz (must NOT include "." root entry, otherwise tar fails with File exists)
        ctrl_buf = io.BytesIO()
        with tarfile.open(fileobj=ctrl_buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
            def add_tar_data(name, data, mode=0o644):
                raw = data.encode("utf-8") if isinstance(data, str) else data
                ti = tarfile.TarInfo(name=name)
                ti.size = len(raw)
                tar.addfile(reset_tarinfo(ti, mode=mode), io.BytesIO(raw))

            add_tar_data("./control", control_content)
            add_tar_data("./manifest", manifest_content)
            add_tar_data("./md5sums", md5sums_content)
            add_tar_data("./preinst", preinst_content, mode=0o755)

        (tpath / "control.tar.gz").write_bytes(ctrl_buf.getvalue())

        # 4. data.tar.gz
        data_buf = io.BytesIO()
        with tarfile.open(fileobj=data_buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
            for d in dirs_to_create:
                dname = "." if d == "." else f"./{d}"
                ti_d = tarfile.TarInfo(name=dname)
                tar.addfile(reset_tarinfo(ti_d, is_dir=True))

            for rel in files_to_pack:
                file_path = root / rel
                raw = file_path.read_bytes()
                ti = tarfile.TarInfo(name=f"./{rel}")
                ti.size = len(raw)
                tar.addfile(reset_tarinfo(ti, mode=0o644), io.BytesIO(raw))

        (tpath / "data.tar.gz").write_bytes(data_buf.getvalue())

        # Pack into .click using 'ar'
        built_click = tpath / click_filename
        subprocess.run(
            ["ar", "rcs", str(built_click), "debian-binary", "_click-binary", "control.tar.gz", "data.tar.gz"],
            cwd=td,
            check=True
        )

        # Destination directories:
        # 1. store/
        store_dir = root / "store"
        store_dir.mkdir(parents=True, exist_ok=True)
        dest_store = store_dir / click_filename
        dest_store.write_bytes(built_click.read_bytes())

        # 2. build/all/app/
        build_dir = root / "build" / "all" / "app"
        build_dir.mkdir(parents=True, exist_ok=True)
        dest_build = build_dir / click_filename
        dest_build.write_bytes(built_click.read_bytes())

        # Remove older .click packages in build and store if they exist
        for old_click in store_dir.glob("*.click"):
            if old_click.name != click_filename:
                print(f"Removing old click from store: {old_click.name}")
                old_click.unlink()
        for old_click in build_dir.glob("*.click"):
            if old_click.name != click_filename:
                print(f"Removing old click from build: {old_click.name}")
                old_click.unlink()

        print(f"Successfully built: {dest_store} ({dest_store.stat().st_size} bytes)")
        print(f"Successfully mirrored to: {dest_build}")

        # Validate with dpkg-deb -I and dpkg-deb -c
        subprocess.check_output(["dpkg-deb", "-I", str(dest_store)], text=True)
        res = subprocess.check_output(["dpkg-deb", "-c", str(dest_store)], text=True)
        print("\nPackage verified with dpkg-deb -I and dpkg-deb -c:")
        for line in res.splitlines():
            print(f"  {line}")

if __name__ == "__main__":
    build_click()
