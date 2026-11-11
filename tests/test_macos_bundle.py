"""Regression checks for macOS distribution artifacts."""
from pathlib import Path


def assert_macos_distribution(root: Path) -> None:
    """A macOS deliverable must be a launchable .app or a mountable .dmg."""
    apps = list(root.glob("*.app"))
    dmgs = list(root.glob("*.dmg"))
    assert apps or dmgs, f"no .app or .dmg under {root}"
    for app in apps:
        assert (app / "Contents" / "Info.plist").is_file(), f"invalid .app: {app}"
        assert (app / "Contents" / "MacOS").is_dir(), f"missing MacOS dir: {app}"
        assert any((app / "Contents" / "MacOS").iterdir()), f"missing launcher: {app}"
    for dmg in dmgs:
        assert dmg.stat().st_size > 1024, f"empty .dmg: {dmg}"


def test_macos_spec_builds_app_bundle():
    spec = (Path(__file__).resolve().parent.parent /
            "packaging" / "samt-desktop-macos.spec").read_text("utf-8")
    assert "app = BUNDLE(" in spec, "macOS spec must create an .app bundle"
    assert "bundle_identifier" in spec, "macOS app bundle needs an identifier"


def test_macos_workflow_packages_dmg():
    workflow = (Path(__file__).resolve().parent.parent /
                ".github" / "workflows" / "build.yml").read_text("utf-8")
    assert "hdiutil create" in workflow, "CI must create a .dmg"
    assert "SAMT-Desktop-macOS-arm64.dmg" in workflow, "CI must name the .dmg"
