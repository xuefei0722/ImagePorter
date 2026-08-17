# ImagePorter Brand Icons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce three comparable, project-local ImagePorter app-icon concepts, select a direction with the user, and turn the selected direction into macOS, Windows, and general brand assets.

**Architecture:** Treat the three concepts as independent raster masters under `assets/brand/concepts/`, then derive previews and platform exports without replacing the production `assets/icon.png` until the user selects a winner. Keep prompt specifications beside the outputs so every concept can be reproduced or revised.

**Tech Stack:** Built-in OpenAI image generation, PNG source assets, macOS `sips`/`iconutil`, Pillow for deterministic resize and ICO export, Markdown documentation.

## Global Constraints

- A and B must show a clear whale; C must retain a whale-tail or whale-body negative-space cue.
- Use modern native-desktop styling with restrained developer-tool character.
- Preserve the existing blue family, using cyan as the main accent and only limited electric purple in B.
- The mark must remain recognizable at 16–32 px and must not rely on text, fine strokes, complex transparency, or the outer border.
- Do not reproduce Docker's official whale trademark, use the letters `DC`, add watermarks, or place text inside the icon.
- First-round work stops at comparable concept masters and previews; full platform export begins only after user selection.

---

### Task 1: Generate three concept masters

**Files:**
- Create: `assets/brand/concepts/a-whale-cargo/master.png`
- Create: `assets/brand/concepts/a-whale-cargo/prompt.md`
- Create: `assets/brand/concepts/b-jump-whale/master.png`
- Create: `assets/brand/concepts/b-jump-whale/prompt.md`
- Create: `assets/brand/concepts/c-tail-beacon/master.png`
- Create: `assets/brand/concepts/c-tail-beacon/prompt.md`

**Interfaces:**
- Consumes: direction definitions from `docs/superpowers/specs/2026-08-17-imageporter-brand-icons-design.md`.
- Produces: three square 1024×1024 RGB/RGBA PNG masters and their exact generation prompts.

- [ ] **Step 1: Create the concept directories and prompt files**

  Record these structured `logo-brand` prompts verbatim, with only formatting normalization allowed:

  **A — Whale Cargo**

  ```text
  Use case: logo-brand
  Asset type: native desktop application icon concept for macOS and Windows
  Primary request: design a distinctive app icon for ImagePorter / 鲸舟, a developer tool that transports Docker container images to offline environments
  Subject: an original friendly whale in side profile forming the hull of a sturdy cargo vessel, carrying exactly three simplified isometric container cubes; integrate one subtle rightward transfer motion into the whale body or waterline
  Style/medium: premium vector-friendly geometric app icon, modern native desktop design, solid readable masses, restrained soft depth
  Composition/framing: centered single icon, balanced near-symmetrical weight, generous 14 percent safe-area padding, immediately readable at small size
  Color palette: cobalt blue to cyan, deep navy for contrast, no green-dominant palette
  Constraints: no letters or words inside the icon, no mockup scene, no external label, no watermark, no tiny decorative details, no thin outlines, no glass transparency, do not imitate the Docker whale trademark
  ```

  **B — Jump Whale**

  ```text
  Use case: logo-brand
  Asset type: native desktop application icon concept for macOS and Windows
  Primary request: design a dynamic app icon for ImagePorter / 鲸舟, a developer tool for exporting and transferring container images across architectures and offline systems
  Subject: an original whale in a bold three-quarter upward pose supporting one sealed geometric image package; exactly two short orbital transfer tracks wrap behind the whale and package to suggest export and cross-architecture movement
  Style/medium: premium vector-friendly geometric app icon, sharper and more technical than a mascot, solid readable silhouette, restrained dimensional depth
  Composition/framing: centered single icon with forward motion, generous 14 percent safe-area padding, package and whale remain distinct at 32 pixels
  Color palette: deep ocean blue, bright cyan, one limited electric-violet accent
  Constraints: no letters or words inside the icon, no mockup scene, no external label, no watermark, no stars or sparkles, no tiny decorative details, no thin outlines, do not imitate the Docker whale trademark
  ```

  **C — Tail Beacon**

  ```text
  Use case: logo-brand
  Asset type: minimal native desktop application icon concept for macOS and Windows
  Primary request: design an abstract geometric brand mark for ImagePorter / 鲸舟 that combines a whale-tail negative-space cue, a single rightward transfer arrow, and subtle I/P construction without drawing a literal mascot
  Subject: one compact continuous symbol with a stable outer silhouette; the whale-tail cue must be discoverable but the mark must read first as a professional developer-tool icon
  Style/medium: flat vector-friendly geometry, minimal, high contrast, no more than three major shapes, optimized for 16 to 32 pixels
  Composition/framing: centered single icon, generous 16 percent safe-area padding, strong balanced negative space
  Color palette: deep navy background with ice-blue and cyan symbol
  Constraints: no visible letters or words inside the icon, no mockup scene, no external label, no watermark, no tiny decorative details, no thin outlines, no gradients that reduce small-size contrast, do not imitate the Docker whale trademark
  ```

- [ ] **Step 2: Generate concept A**

  Use the built-in image generation tool with the A prompt. Save the selected result as `assets/brand/concepts/a-whale-cargo/master.png` and visually verify that the whale, cargo blocks, and transfer direction are legible.

- [ ] **Step 3: Generate concept B**

  Use the built-in image generation tool with the B prompt. Save the selected result as `assets/brand/concepts/b-jump-whale/master.png` and visually verify that the whale, package, and motion tracks remain distinct from concept A.

- [ ] **Step 4: Generate concept C**

  Use the built-in image generation tool with the C prompt. Save the selected result as `assets/brand/concepts/c-tail-beacon/master.png` and visually verify that the geometric mark contains a readable whale-tail cue and one stable silhouette.

- [ ] **Step 5: Validate the masters**

  Run `file` and `sips -g pixelWidth -g pixelHeight -g hasAlpha` on all three files. Expected: three PNG files, each exactly 1024×1024, with no generation text or watermark visible during image inspection.

- [ ] **Step 6: Commit the concept masters**

```bash
git add assets/brand/concepts
git commit -m "design: add ImagePorter icon concepts"
```

### Task 2: Build comparison and small-size previews

**Files:**
- Create: `assets/brand/previews/concepts-compare.png`
- Create: `assets/brand/previews/small-size-check.png`

**Interfaces:**
- Consumes: the three `master.png` files from Task 1.
- Produces: a labeled visual comparison for user review and an unlabeled 16/24/32/64 px legibility check.

- [ ] **Step 1: Build the comparison board**

  Use Pillow to place A, B, and C on a neutral light canvas at equal 360×360 display size with labels outside the icon artwork. Do not alter the master files.

- [ ] **Step 2: Build the small-size board**

  Resize each master using Lanczos to 16, 24, 32, and 64 px, then place nearest-neighbor enlarged copies on a neutral checker-free canvas so silhouette loss is easy to inspect.

- [ ] **Step 3: Inspect both boards**

  Confirm equal sizing, no cropping, no label overlap, and clearly visible differences between A, B, and C. Reject and regenerate any concept whose core metaphor disappears at 32 px.

- [ ] **Step 4: Commit the previews**

```bash
git add assets/brand/previews
git commit -m "design: add icon comparison previews"
```

### Task 3: User selection and targeted revision

**Files:**
- Modify when needed: `assets/brand/concepts/<selected-direction>/master.png`
- Modify when needed: `assets/brand/concepts/<selected-direction>/prompt.md`
- Modify: `assets/brand/previews/concepts-compare.png`
- Modify: `assets/brand/previews/small-size-check.png`

**Interfaces:**
- Consumes: user choice and concrete revision notes against the comparison boards.
- Produces: one approved 1024×1024 master suitable for platform derivation.

- [ ] **Step 1: Present both preview boards**

  Ask the user to choose A, B, C, or identify specific elements to combine; keep the unselected masters unchanged.

- [ ] **Step 2: Apply one targeted revision round**

  Update the selected concept prompt with only the requested changes, regenerate non-destructively, and retain the prior master as `master-v1.png` before promoting the revision to `master.png`.

- [ ] **Step 3: Rebuild and inspect previews**

  Repeat Task 2's comparison and small-size checks, then obtain explicit approval of the selected master.

- [ ] **Step 4: Commit the approved master**

```bash
git add assets/brand/concepts assets/brand/previews
git commit -m "design: refine selected ImagePorter icon"
```

### Task 4: Export the approved platform and brand assets

**Files:**
- Create: `assets/brand/final/icon-1024.png`
- Create: `assets/brand/final/icon.icns`
- Create: `assets/brand/final/icon.ico`
- Create: `assets/brand/final/png/icon-{16,24,32,48,64,128,256,512,1024}.png`
- Create: `assets/brand/final/mark-light.png`
- Create: `assets/brand/final/mark-dark.png`
- Create: `assets/brand/final/lockup-zh-en-light.png`
- Create: `assets/brand/final/lockup-zh-en-dark.png`

**Interfaces:**
- Consumes: the explicitly approved master from Task 3.
- Produces: complete macOS, Windows, and general-use brand deliverables; does not replace `assets/icon.png` without separate user approval.

- [ ] **Step 1: Export deterministic PNG sizes**

  Use Pillow with Lanczos resampling to export 16, 24, 32, 48, 64, 128, 256, 512, and 1024 px PNG files. Verify every output dimension programmatically.

- [ ] **Step 2: Create the Windows ICO**

  Save `icon.ico` with embedded 16, 24, 32, 48, 64, 128, and 256 px frames. Reopen it with Pillow and assert that all required frames are present.

- [ ] **Step 3: Create the macOS ICNS**

  Build a valid `.iconset` from the approved master using the standard 16, 32, 128, 256, 512, and 1024 representations, then run `iconutil -c icns`. Verify `iconutil` exits successfully and `file` recognizes the result as Apple Icon Image format.

- [ ] **Step 4: Create transparent marks and lockups**

  Derive light/dark transparent-background marks and render the exact names `鲸舟` and `ImagePorter` outside the icon using a locally available CJK-capable system font. Verify text accuracy and alpha-channel presence.

- [ ] **Step 5: Run final visual checks**

  Inspect the 1024 px icon, 16/32 px exports, both marks, and both lockups against light and dark backgrounds. Confirm no cropping, halos, misspelled text, third-party marks, or illegible small detail.

- [ ] **Step 6: Commit the final asset package**

```bash
git add assets/brand/final
git commit -m "design: add ImagePorter platform brand assets"
```
