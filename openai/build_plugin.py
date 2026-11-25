"""Validate the Dazzle ChatGPT plugin package against OpenAI's submission rules and build the upload ZIP."""

import argparse
import json
import re
import struct
import sys
import zipfile
from pathlib import Path
from typing import Any

PLUGIN_DIR = Path(__file__).resolve().parent / "plugin"
DIST_DIR = Path(__file__).resolve().parent / "dist"

CATEGORIES = {
    "Productivity",
    "Creativity",
    "Developer Tools",
    "Business & Operations",
    "Data & Analytics",
    "Communication",
    "Education & Research",
    "Security",
    "Finance",
    "Healthcare",
    "Travel",
    "Entertainment",
    "Other",
}
LISTING_URL_FIELDS = ("websiteURL", "supportURL", "privacyPolicyURL", "termsOfServiceURL")
ICON_FIELDS = ("composerIcon", "composerIconDark", "logo", "logoDark")
FORBIDDEN_OPENAI_KEYS = ("apps", "hooks")
FORBIDDEN_REVIEW_KEYS = ("test_credentials", "reviewer_instructions")
POSITIVE_CASE_FIELDS = ("description", "prompt", "tools_triggered", "expected_behavior")
NEGATIVE_CASE_FIELDS = ("description", "prompt")
REQUIRED_POSITIVE_CASES = 5
REQUIRED_NEGATIVE_CASES = 3
MAX_ICON_BYTES = 5 * 1024 * 1024
MAX_ZIP_BYTES = 100 * 1024 * 1024
MAX_ZIP_ENTRIES = 5000
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")


class Validator:
    """Collects validation errors for the plugin package."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def text(self, value: Any, field: str, max_len: int, single_line: bool = False) -> None:
        if not isinstance(value, str) or not value.strip():
            self.errors.append(f"{field} must be a non-empty string")
            return
        self.check(len(value) <= max_len, f"{field} is {len(value)} chars; max {max_len}")
        if single_line:
            self.check("\n" not in value, f"{field} must be a single line")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data: dict[str, Any] = json.load(f)
    return data


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_relative_luminance(a), _relative_luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _png_size(path: Path) -> tuple[int, int] | None:
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def _validate_icon(v: Validator, field: str, rel_path: Any) -> None:
    if not isinstance(rel_path, str) or not rel_path.startswith("./"):
        v.errors.append(f"interface.{field} must be a relative path starting with ./")
        return
    path = PLUGIN_DIR / rel_path
    if not path.is_file():
        v.errors.append(f"interface.{field} file not found: {rel_path}")
        return
    v.check(path.stat().st_size <= MAX_ICON_BYTES, f"interface.{field} exceeds 5 MiB")
    size = _png_size(path)
    if size is None:
        v.errors.append(f"interface.{field} must be a PNG for this validator: {rel_path}")
        return
    width, height = size
    v.check(width == height, f"interface.{field} must be square; got {width}x{height}")
    v.check(48 <= width <= 4096, f"interface.{field} must be 48-4096 px; got {width}")


def _validate_interface(v: Validator, interface: dict[str, Any]) -> None:
    v.text(interface.get("displayName"), "interface.displayName", 30, single_line=True)
    v.text(interface.get("shortDescription"), "interface.shortDescription", 30, single_line=True)
    v.text(interface.get("longDescription"), "interface.longDescription", 4000)
    v.text(interface.get("developerName"), "interface.developerName", 80, single_line=True)
    v.check(interface.get("category") in CATEGORIES, f"interface.category must be one of {sorted(CATEGORIES)}")

    capabilities = interface.get("capabilities", [])
    v.check(isinstance(capabilities, list) and len(capabilities) <= 20, "interface.capabilities: max 20 entries")
    for i, capability in enumerate(capabilities):
        v.text(capability, f"interface.capabilities[{i}]", 120, single_line=True)

    for field in LISTING_URL_FIELDS:
        url = interface.get(field)
        v.check(
            isinstance(url, str) and url.startswith("https://") and len(url) <= 1024,
            f"interface.{field} must be an HTTPS URL of at most 1024 chars",
        )

    prompts = interface.get("defaultPrompt", [])
    v.check(isinstance(prompts, list) and len(prompts) <= 3, "interface.defaultPrompt: max 3 prompts")
    normalized = [" ".join(p.split()).casefold() for p in prompts if isinstance(p, str)]
    v.check(len(set(normalized)) == len(normalized), "interface.defaultPrompt entries must be unique")
    for i, prompt in enumerate(prompts):
        v.text(prompt, f"interface.defaultPrompt[{i}]", 128, single_line=True)
        v.check("@" not in str(prompt), f"interface.defaultPrompt[{i}] must not contain @mentions")

    for field, background in (("brandColor", "#FFFFFF"), ("brandColorDark", "#212121")):
        color = interface.get(field)
        if color is None and field == "brandColorDark":
            continue
        if not isinstance(color, str) or not HEX_COLOR_PATTERN.match(color):
            v.errors.append(f"interface.{field} must be #RRGGBB")
            continue
        ratio = _contrast(color, background)
        v.check(ratio >= 2.0, f"interface.{field} contrast vs {background} is {ratio:.2f}; min 2.0")

    v.check(bool(interface.get("logo") or interface.get("composerIcon")), "interface needs a logo or composerIcon")
    for field in ICON_FIELDS:
        if field in interface:
            _validate_icon(v, field, interface[field])


def _validate_review(v: Validator, review: dict[str, Any], for_submission: bool) -> None:
    for key in FORBIDDEN_REVIEW_KEYS:
        v.check(key not in review, f"review.{key} is rejected in the ZIP; enter it in the portal")
    cases = review.get("test_cases") or {}
    positive = cases.get("positive", [])
    negative = cases.get("negative", [])
    v.check(len(positive) == REQUIRED_POSITIVE_CASES, f"need exactly {REQUIRED_POSITIVE_CASES} positive test cases")
    v.check(len(negative) == REQUIRED_NEGATIVE_CASES, f"need exactly {REQUIRED_NEGATIVE_CASES} negative test cases")
    for kind, items, fields in (
        ("positive", positive, POSITIVE_CASE_FIELDS),
        ("negative", negative, NEGATIVE_CASE_FIELDS),
    ):
        for i, case in enumerate(items):
            for field in fields:
                v.check(
                    isinstance(case.get(field), str) and bool(case[field].strip()),
                    f"review.test_cases.{kind}[{i}].{field} is required",
                )
            v.check(len(str(case.get("description", ""))) <= 4000, f"review.test_cases.{kind}[{i}].description > 4000")
    v.check(isinstance(review.get("commerce"), bool), "review.commerce must be a boolean")
    if for_submission:
        url = review.get("demo_recording_url")
        v.check(
            isinstance(url, str) and url.startswith("https://"),
            "review.demo_recording_url is required for submission",
        )


def _validate_skill(v: Validator, rel_path: Any) -> None:
    if not isinstance(rel_path, str) or not rel_path.startswith("./"):
        v.errors.append("onboardingSkill must be a relative path starting with ./")
        return
    path = PLUGIN_DIR / rel_path
    if not path.is_file():
        v.errors.append(f"onboardingSkill not found: {rel_path}")
        return
    match = re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.S)
    if not match:
        v.errors.append(f"{rel_path} must start with YAML frontmatter")
        return
    frontmatter = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
    for key in ("name", "description"):
        value = frontmatter.get(key, "").strip()
        v.check(bool(value), f"{rel_path} frontmatter needs {key}")
        v.check(len(value) <= 1024, f"{rel_path} frontmatter {key} > 1024 chars")


def _validate_mcp(v: Validator, mcp: dict[str, Any]) -> None:
    servers = mcp.get("mcpServers", {})
    v.check(len(servers) == 1, "mcp.json must declare exactly one MCP server")
    for name, server in servers.items():
        v.check(server.get("type") == "streamable-http", f"mcpServers.{name}.type must be streamable-http")
        v.check(str(server.get("url", "")).startswith("https://"), f"mcpServers.{name}.url must be HTTPS")
        v.check(not server.get("headers"), f"mcpServers.{name}.headers must be empty")
        auth = server.get("extensions", {}).get("com.openai", {}).get("auth", {})
        v.check("clientSecret" not in auth.get("client", {}), f"mcpServers.{name} auth must not contain clientSecret")
        v.check(auth.get("type") in ("none", "oauth", "mixed"), f"mcpServers.{name} auth.type must be none|oauth|mixed")


def validate(for_submission: bool) -> list[str]:
    """Return every rule violation in the plugin package; empty when it is ready to upload."""
    v = Validator()
    manifest = _load_json(PLUGIN_DIR / "plugin.json")
    mcp = _load_json(PLUGIN_DIR / "mcp.json")

    name = manifest.get("name", "")
    v.check(len(name) <= 64 and bool(NAME_PATTERN.match(name)), "name must be kebab-case, max 64 chars")
    v.check(bool(SEMVER_PATTERN.match(manifest.get("version", ""))), "version must be semver")
    v.text(manifest.get("description"), "description", 1024)
    author = manifest.get("author", {})
    v.text(author.get("name"), "author.name", 120)

    openai = manifest.get("extensions", {}).get("com.openai", {})
    for key in FORBIDDEN_OPENAI_KEYS:
        v.check(key not in openai, f"extensions.com.openai.{key} makes the plugin ineligible for the directory")
    _validate_interface(v, openai.get("interface", {}))
    _validate_review(v, openai.get("review", {}), for_submission)
    _validate_skill(v, openai.get("onboardingSkill"))
    _validate_mcp(v, mcp)

    countries = openai.get("publication", {}).get("countries", [])
    for country in countries:
        v.check(bool(COUNTRY_PATTERN.match(country)), f"publication.countries entry {country!r} must be ISO alpha-2")
    v.check(len(set(countries)) == len(countries), "publication.countries has duplicates")

    secret_pattern = re.compile(r"(client_secret|api[_-]?key|password)\s*[:=]", re.I)
    for path in PLUGIN_DIR.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".md", ".yaml", ".yml"):
            v.check(not secret_pattern.search(path.read_text()), f"possible secret in {path.relative_to(PLUGIN_DIR)}")
    return v.errors


def build_zip(output: Path) -> Path:
    """Zip the plugin directory with plugin.json at the archive root."""
    files = sorted(p for p in PLUGIN_DIR.rglob("*") if p.is_file() and not p.name.startswith("."))
    if len(files) > MAX_ZIP_ENTRIES:
        raise SystemExit(f"too many files: {len(files)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(PLUGIN_DIR).as_posix())
    if output.stat().st_size > MAX_ZIP_BYTES:
        raise SystemExit(f"ZIP exceeds 100 MB: {output.stat().st_size} bytes")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", action="store_true", help="also require fields needed to submit for review")
    parser.add_argument("--zip", action="store_true", help="build the upload ZIP into distribution/openai/dist/")
    args = parser.parse_args()

    errors = validate(for_submission=args.submission)
    if errors:
        print("Plugin package is invalid:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    print("Plugin package is valid.")

    if args.zip:
        version = _load_json(PLUGIN_DIR / "plugin.json")["version"]
        output = build_zip(DIST_DIR / f"dazzle-photo-intelligence-{version}.zip")
        print(f"Wrote {output}")


if __name__ == "__main__":
    main()
