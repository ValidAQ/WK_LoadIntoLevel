"""
A packaging script for a Thunderstore mod that creates a distributable zip file.

This script reads the mod's .csproj file, copies required files, and packages them into a zip archive.
There's probably easier ways to do this, but none I know better than Python.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

# Assumes script is run from project root - which it will if run from VS Code task
PROJECT_ROOT = Path.cwd()
PROJECT_NAME = PROJECT_ROOT.name

# Relative path from project root to the folder containing the DLL
# Change if targeting a different .NET version or release variant
DLL_SOURCE_FOLDER = Path("bin", "Debug", "net472")


@dataclass
class FileSpec:
    path: Path
    required: bool
    rename_to: str | None = None


DEFAULT_FILESPEC = [
    FileSpec(path=PROJECT_ROOT / "manifest.json", required=True),
    FileSpec(path=PROJECT_ROOT / "img" / "icon.png", required=True, rename_to="icon.png"),
    FileSpec(path=PROJECT_ROOT / "README.md", required=True),
    FileSpec(path=PROJECT_ROOT / "CHANGELOG.md", required=False),  # Optional
]


def setup_logging() -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            # logging.FileHandler("packaging.log", mode="w"),
        ],
    )


def get_github_url() -> str:
    """
    Get the GitHub repository URL from the git remote.

    Used to populate the mod's manifest with the repository URL.
    If the remote is not set or does not point to GitHub, return an empty string.
    """
    try:
        process = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception for non-zero exit codes
        )
        if process.returncode == 0:
            result = process.stdout.strip()
            if result.startswith("https://github.com/"):
                return result
            if result.startswith("git@github.com:"):
                # Convert SSH URL to HTTPS
                return result.replace("git@github.com:", "https://github.com/")
            logging.warning("Cannot determine GitHub URL from remote: %s", result)
        else:
            logging.error(
                "Failed to get git remote URL. Exit code: %s, Error: %s",
                process.returncode,
                process.stderr.strip(),
            )
    except FileNotFoundError:
        logging.exception("Git command not found. Please ensure Git is installed and in your PATH.")
    return ""


def get_description() -> str:
    """
    Get the mod description from the README.md file.

    The Summary section of the README.md is used as the mod description.
    """
    readme_path = PROJECT_ROOT / "README.md"
    if readme_path.exists():
        with readme_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        # Look for a header line containing "Summary" - any header level
        summary_header_pattern = re.compile(r"^#+\s*Summary", re.IGNORECASE)

        summary_content = []
        in_summary_section = False
        for line in lines:
            if summary_header_pattern.match(line):
                in_summary_section = True
                continue  # Skip the header line itself
            if line.startswith("#") and in_summary_section:
                # Reached the next section
                break

            if in_summary_section:
                # Strip leading/trailing whitespace, newlines, and empty lines
                stripped_line = line.strip()
                if stripped_line:
                    summary_content.append(stripped_line)

        if summary_content:
            return " ".join(summary_content)
        logging.warning("Summary section not found in README.md.")
        return ""

    logging.warning("README.md not found.")
    return ""


class CsprojGetter:
    """
    A class to retrieve information from the mod's .csproj file.

    It loads the .csproj file, retrieves the DLL name, version, and mod name.

    Note that it makes some assumptions about the mod attributes -
    specifically that they are defined in the .csproj file, like in the default BepInEx template.
    """

    def __init__(self) -> None:
        self.csproj_root: ET.Element | None = None

    def load_csproj(self, csproj_path: Path) -> ET.Element:
        """Load and parse the mod .csproj file."""
        if self.csproj_root is None:
            try:
                tree = ET.parse(csproj_path)
                self.csproj_root = tree.getroot()
            except ET.ParseError:
                logging.exception("Failed to parse %s", csproj_path)
                sys.exit(1)
            except Exception:
                logging.exception("An unexpected error occurred while processing %s", csproj_path)
                sys.exit(1)
        return self.csproj_root

    def retreive_csproj_element(self, xml_path: str) -> str:
        root = self.load_csproj(PROJECT_ROOT / f"{PROJECT_NAME}.csproj")
        dll_name_element = root.find(xml_path)
        if dll_name_element is not None and dll_name_element.text:
            return dll_name_element.text
        logging.exception("Element %s not found in .csproj", xml_path)
        sys.exit(1)

    def get_dll_name(self) -> str:
        return self.retreive_csproj_element(".//PropertyGroup/AssemblyName") + ".dll"

    def get_dll_version(self) -> str:
        return self.retreive_csproj_element(".//PropertyGroup/Version")

    def get_mod_name(self) -> str:
        return self.retreive_csproj_element(".//PropertyGroup/Product")

    def get_dll_path(self) -> Path:
        dll_name = self.get_dll_name()
        return Path(PROJECT_ROOT) / DLL_SOURCE_FOLDER / dll_name


class FilePackager:
    """
    A class to handle the packaging of mod files into a zip archive.

    It prepares the file specifications, copies files to a temporary directory,
    and creates the final zip file.
    """

    def __init__(self) -> None:
        csproj = CsprojGetter()

        self.dll_name = csproj.get_dll_name()
        self.dll_source_path = csproj.get_dll_path()
        # The dist directory is where we build the package and the final zip file will be placed.
        self.dist_dir = Path(PROJECT_ROOT) / "dist"
        # Packaging is done in a temporary timestamped directory.
        timestamp = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d%H%M%S")
        self.temp_dir = self.dist_dir / f"temp_package_{timestamp}"
        self.zip_file_name = self.dist_dir / f"{csproj.get_mod_name()}-{csproj.get_dll_version()}.zip"

    def prepare_file_spec(self) -> list[FileSpec]:
        """Prepare the file list for packaging."""
        if not self.dist_dir.exists():
            self.dist_dir.mkdir(parents=True)

        # Should not happen with timestamp, but good practice
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        self.temp_dir.mkdir(parents=True)

        # The only thing that differs from the default file spec is the DLL path
        file_spec = DEFAULT_FILESPEC.copy()
        file_spec.append(
            FileSpec(path=self.dll_source_path, required=True, rename_to=self.dll_name),
        )
        return file_spec

    def copy_files(self, file_specs: list[FileSpec]) -> None:
        """Copy specified files to the temporary directory for processing."""
        logging.info("Copying files to %s", self.temp_dir)
        try:
            for file_spec in file_specs:
                source_file_path = PROJECT_ROOT / file_spec.path
                if source_file_path.exists():
                    destination_name = file_spec.rename_to or source_file_path.name
                    shutil.copy(source_file_path, self.temp_dir / destination_name)
                    logging.info("  Copied: %s", file_spec.path)
                elif file_spec.required:
                    logging.error(
                        "Required file not found: %s. "
                        "Please ensure the file exists or update its path in the packaging script. "
                        "If it's the DLL, ensure your project is built.",
                        source_file_path,
                    )
                    shutil.rmtree(self.temp_dir)
                    sys.exit(1)
                else:
                    logging.warning("Optional file not found, skipping: %s", source_file_path)
        except Exception:
            logging.exception("Error during file copying")
            shutil.rmtree(self.temp_dir)
            sys.exit(1)

    def zip_files(self) -> None:
        """Create the mod package file from the prepared files."""
        logging.info("Creating zip file: %s", self.zip_file_name)
        try:
            with zipfile.ZipFile(self.zip_file_name, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(self.temp_dir):
                    for file in files:
                        file_path = Path(root) / file
                        # Arcname is the name inside the zip, relative to temp_dir
                        arcname = file_path.relative_to(self.temp_dir)
                        zf.write(file_path, arcname)
        except Exception:
            logging.exception("Failed to create zip file.")
            sys.exit(1)
        finally:
            logging.info("Cleaning up temporary directory: %s", self.temp_dir)
            shutil.rmtree(self.temp_dir)
        logging.info("Mod package created successfully: %s", self.zip_file_name)

    def process(self) -> None:
        """Process the packaging steps."""
        file_spec = self.prepare_file_spec()
        self.copy_files(file_spec)
        self.zip_files()


def build_manifest() -> None:
    """Build the mod's manifest.json file."""
    manifest_dict: dict[str, str | list[str]] = {}
    csproj = CsprojGetter()

    manifest_dict["name"] = csproj.get_mod_name()
    manifest_dict["description"] = get_description()
    manifest_dict["version_number"] = csproj.get_dll_version()
    manifest_dict["website_url"] = get_github_url()
    manifest_dict["dependencies"] = ["BepInEx-BepInExPack-5.4.2100"]

    manifest_path = Path("manifest.json")
    with Path.open(manifest_path, "w") as manifest_file:
        json.dump(manifest_dict, manifest_file, indent=4, sort_keys=True)


def main() -> None:
    setup_logging()
    logging.info("Starting mod packaging process...")

    build_manifest()

    packager = FilePackager()

    packager.process()


if __name__ == "__main__":
    main()
