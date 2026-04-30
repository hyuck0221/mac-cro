# mac-cro

mac-cro is a small macOS keyboard macro recorder and player.

## Install

Run this command in Terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/shimhyuck/mac-cro/main/install.sh | bash
```

After installation, you can launch the app from any terminal:

```bash
mac-cro
```

The installer places the app in `~/.mac-cro`, creates a Python virtual environment, installs dependencies, and adds a launcher at `~/.local/bin/mac-cro`.

## Update

Run the install command again:

```bash
curl -fsSL https://raw.githubusercontent.com/shimhyuck/mac-cro/main/install.sh | bash
```

If mac-cro is already installed, the installer updates the existing checkout and refreshes the Python dependencies.

## Manual Run

If you cloned the repository yourself:

```bash
git clone https://github.com/shimhyuck/mac-cro.git
cd mac-cro
./run.sh
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
