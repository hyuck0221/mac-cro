# mac-cro

mac-cro is a small macOS keyboard macro recorder and player.

Current version: `0.1.0`

## Install

Run this command in Terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/hyuck0221/mac-cro/main/install.sh | bash
```

After installation, you can launch the app from any terminal:

```bash
mac-cro
```

The installer places the app in `~/.mac-cro`, creates a Python virtual environment, installs dependencies, and adds a launcher at `~/.local/bin/mac-cro`.

## Run

```bash
mac-cro
```

mac-cro checks for updates every time it starts. If a newer version is available on GitHub, it updates itself automatically before opening the app.

To skip the update check for one launch:

```bash
MAC_CRO_AUTO_UPDATE=0 mac-cro
```

## Update

Updates are automatic when you run `mac-cro`.

You can also force a reinstall/update with:

```bash
curl -fsSL https://raw.githubusercontent.com/hyuck0221/mac-cro/main/install.sh | bash
```

If mac-cro is already installed, the installer updates the existing checkout and refreshes the Python dependencies.

## Release Versioning

Before each release, update [VERSION](VERSION):

```txt
0.1.1
```

Then commit and push the change:

```bash
git add VERSION
git commit -m "Release 0.1.1"
git push
```

Installed copies will pick up the new version automatically the next time `mac-cro` runs.

## Manual Run

If you cloned the repository yourself:

```bash
git clone https://github.com/hyuck0221/mac-cro.git
cd mac-cro
./run.sh
```

For the same auto-update behavior used by installed copies, run:

```bash
./launch.sh
```

## macOS Permissions

mac-cro needs macOS privacy permissions to record and replay keyboard input.

Open System Settings and allow your terminal or Python process in:

- Privacy & Security > Input Monitoring
- Privacy & Security > Accessibility

Restart mac-cro after changing permissions.

## Uninstall

```bash
rm -rf ~/.mac-cro ~/.local/bin/mac-cro
```

If the installer added `~/.local/bin` to your shell profile, you can remove the `# mac-cro` block from `~/.zshrc` or `~/.profile`.

## Korean Guide

한국어 문서는 [README.ko.md](README.ko.md)를 참고하세요.
