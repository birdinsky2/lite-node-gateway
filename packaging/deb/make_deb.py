from __future__ import annotations

import argparse
import gzip
import io
import os
import pathlib
import stat
import tarfile


def normalized_name(path: pathlib.Path) -> str:
    return "./" + path.as_posix().lstrip("./")


def tar_mode(path: pathlib.Path, relative: pathlib.Path, control: bool) -> int:
    if path.is_dir():
        return 0o755
    if control and relative.name in {"postinst", "prerm", "postrm", "preinst"}:
        return 0o755
    if relative.as_posix().startswith("opt/lite-node-gateway/bin/"):
        return 0o755
    if relative.suffix == ".sh":
        return 0o755
    current_mode = stat.S_IMODE(path.stat().st_mode)
    if current_mode & 0o111:
        return 0o755
    return 0o644


def add_path(tar: tarfile.TarFile, root: pathlib.Path, path: pathlib.Path, control: bool) -> None:
    relative = path.relative_to(root)
    info = tar.gettarinfo(str(path), arcname=normalized_name(relative))
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0
    info.mode = tar_mode(path, relative, control)
    if path.is_file():
        with path.open("rb") as handle:
            tar.addfile(info, handle)
    else:
        tar.addfile(info)


def build_tar_gz(root: pathlib.Path, paths: list[pathlib.Path], control: bool) -> bytes:
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gzip_file:
        with tarfile.open(fileobj=gzip_file, mode="w") as tar:
            for path in paths:
                add_path(tar, root, path, control)
    return raw.getvalue()


def iter_tree(root: pathlib.Path) -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for current, dirnames, filenames in os.walk(root):
        current_path = pathlib.Path(current)
        dirnames.sort()
        filenames.sort()
        for dirname in dirnames:
            paths.append(current_path / dirname)
        for filename in filenames:
            paths.append(current_path / filename)
    return paths


def ar_member(name: str, data: bytes) -> bytes:
    encoded_name = (name + "/").encode("ascii")
    if len(encoded_name) > 16:
        raise ValueError(f"ar member name is too long: {name}")
    header = b"".join(
        [
            encoded_name.ljust(16, b" "),
            b"0".ljust(12, b" "),
            b"0".ljust(6, b" "),
            b"0".ljust(6, b" "),
            b"100644".ljust(8, b" "),
            str(len(data)).encode("ascii").ljust(10, b" "),
            b"`\n",
        ]
    )
    if len(data) % 2:
        data += b"\n"
    return header + data


def write_deb(package_root: pathlib.Path, output: pathlib.Path) -> None:
    control_root = package_root / "DEBIAN"
    if not (control_root / "control").exists():
        raise FileNotFoundError(f"Missing control file: {control_root / 'control'}")

    control_paths = iter_tree(control_root)
    data_paths = [path for path in iter_tree(package_root) if "DEBIAN" not in path.relative_to(package_root).parts]

    control_tar = build_tar_gz(control_root, control_paths, control=True)
    data_tar = build_tar_gz(package_root, data_paths, control=False)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        handle.write(b"!<arch>\n")
        handle.write(ar_member("debian-binary", b"2.0\n"))
        handle.write(ar_member("control.tar.gz", control_tar))
        handle.write(ar_member("data.tar.gz", data_tar))


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a simple Debian package.")
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    write_deb(pathlib.Path(args.package_root).resolve(), pathlib.Path(args.output).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
