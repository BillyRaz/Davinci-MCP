# Parameterized LUT Engine

The LUT engine converts a strict, versioned grade profile into deterministic
Resolve-compatible RGB `.cube` bytes. Responsibilities are separated across
`resolve/lut`: profile modeling, pure transforms, generation, validation,
technical analysis, registry, installation, and locked-target application.

This LUT engine performs global color treatment only. It does not identify
people, clothing, skin, backgrounds, or objects.

## Color pipeline

V1 accepts and emits display-referred `rec709_gamma24`. It uses an explicit
gamma-2.4 power-law decode and encode and performs treatment in `linear_rec709`:

1. decode encoded lattice RGB;
2. multiply exposure by `2 ** stops`;
3. apply restrained creative RGB temperature/tint gains;
4. apply linear contrast around the declared pivot;
5. apply smooth monotonic toe and shoulder functions;
6. apply global saturation using Rec.709 luma coefficients;
7. smoothly weight shadow/highlight saturation by squared luma weights;
8. apply optional cosine-weighted teal, magenta, and gold hue sectors;
9. compress out-of-gamut excursions toward luma;
10. map black floor and white ceiling;
11. encode gamma 2.4 and safely bound output to 0–1.

Temperature/tint is not camera metadata white balance or chromatic adaptation.
Hue sectors are mathematical hue weights, not semantic detection. Basic gamut
compression monotonically reduces individual channel excursions before final
bounding but is not a perceptual gamut-mapping system.

## Profile schema and controls

Profiles reject unknown fields, unsupported schema versions/color spaces,
non-finite values, unsupported cube sizes, and unsafe ranges. V1 implements:
exposure, temperature, tint, contrast, pivot, toe, shoulder, global/shadow/
highlight saturation, teal preservation, magenta preservation, gold warmth,
gamut compression, black floor, white ceiling, and final output bounding.

Supported sizes are 17 (diagnostic), 33 (production), and 65 (optional,
larger/slower). Generation uses red-fastest sample ordering, nine decimal
places, LF endings, deterministic bytes, and versioned filenames.

## CLI

```text
davinci-grade lut generate PROFILE.json --output DIRECTORY
davinci-grade lut validate LOOK.cube --metadata LOOK.json
davinci-grade lut inspect LOOK.cube --metadata LOOK.json
davinci-grade lut analyze LOOK.cube
davinci-grade lut compare BEFORE.png AFTER.png
davinci-grade lut register LOOK.cube --metadata LOOK.json
davinci-grade lut list
davinci-grade lut install PROFILE_NAME [--dry-run]
```

Use `--json` for structured output. Offline generation, inspection, analysis,
and dry runs never connect to or mutate Resolve.

## Resolve installation and application

The installer copies atomically into `DavinciMCP/Generated` under Resolve's LUT
root, verifies SHA-256, refuses different-content overwrites, and never deletes
user LUTs. macOS and Windows paths are selected from platform conventions.
Resolve installation calls `Project.RefreshLUTList`; failure is explicit.

MCP exposes profile generation/validation/analysis, registry listing/state,
installation, capture comparison, and locked-target prepare/apply/restore.
Application has no active-clip fallback. It requires the session-local
TimelineItem lock, current unique-ID resolution, a verified readable DRX backup,
and a registered unchanged LUT. It records the original version/graph
fingerprint, creates a uniquely named disposable local version, verifies one
owned empty node, and applies only there. SetLUT/GetLUT mismatch or identity
drift restores the original and deletes the disposable version.

Successful versions are preserved only through an explicit later approval
decision. Failures restore immediately. Visible no-ops and configurable
technical thresholds are represented separately from warnings.

## Capture and technical analysis

Image comparison reports hashes, dimensions, mean absolute RGB difference,
per-channel mean change, luma and saturation changes, changed pixels, near-black
and near-white populations, highlight clipping increase, and shadow-crush
increase. These measurements do not replace human visual approval.

LUT analysis samples neutral/color ramps plus cyan, magenta, gold, teal,
skin-like warm/cool colors, and near-black/near-white saturated colors. It
reports neutral cast and monotonicity, clipping, extrema, hue/saturation
changes, maximum/average sample delta, and identity distance. It is not an
artistic-quality score.

## Deferred capabilities

LUTs cannot make spatially selective corrections, recognize subjects, repair
individual objects, or track motion. DCTL remains deferred because this phase
establishes the simpler deterministic `.cube` backend first. Masks and tracking
remain deferred because they require spatial data absent from a 3D LUT. After
Effects remains a separate later phase with a different application and
automation contract. No mouse-driven node creation or UI automation is used.
