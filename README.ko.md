# mac-cro

mac-cro는 macOS용 키보드 매크로 기록 및 재생 앱입니다.

현재 버전: `0.1.0`

## 설치

터미널에서 아래 명령어를 실행하세요.

```bash
curl -fsSL https://raw.githubusercontent.com/hyuck0221/mac-cro/main/install.sh | bash
```

설치 후에는 어디서든 아래 명령어로 실행할 수 있습니다.

```bash
mac-cro
```

설치 스크립트는 앱을 `~/.mac-cro`에 내려받고, Python 가상환경을 만든 뒤, 실행 명령어를 `~/.local/bin/mac-cro`에 생성합니다.

## 실행

```bash
mac-cro
```

mac-cro는 실행할 때마다 GitHub에 새 버전이 있는지 확인합니다. 새 버전이 있으면 앱을 열기 전에 자동으로 업데이트합니다.

한 번만 자동 업데이트를 건너뛰려면 아래처럼 실행하세요.

```bash
MAC_CRO_AUTO_UPDATE=0 mac-cro
```

## 업데이트

`mac-cro`를 실행할 때 자동으로 업데이트됩니다.

강제로 다시 설치하거나 업데이트하려면 아래 명령어를 실행하세요.

```bash
curl -fsSL https://raw.githubusercontent.com/hyuck0221/mac-cro/main/install.sh | bash
```

이미 설치되어 있으면 기존 앱을 최신 코드로 업데이트하고 Python 의존성을 다시 정리합니다.

## 배포 버전 관리

배포할 때마다 [VERSION](VERSION) 파일의 버전을 올리세요.

```txt
0.1.1
```

그다음 커밋하고 push합니다.

```bash
git add VERSION
git commit -m "Release 0.1.1"
git push
```

설치된 앱은 다음에 `mac-cro`를 실행할 때 새 버전을 자동으로 받아옵니다.

## 직접 실행

저장소를 직접 클론해서 실행하려면 아래 명령어를 사용하세요.

```bash
git clone https://github.com/hyuck0221/mac-cro.git
cd mac-cro
./run.sh
```

설치 버전과 같은 자동 업데이트 흐름으로 실행하려면 아래 명령어를 사용하세요.

```bash
./launch.sh
```

## macOS 권한 설정

키 입력 기록과 재생을 위해 macOS 개인정보 보호 권한이 필요합니다.

시스템 설정에서 사용 중인 터미널 또는 Python 프로세스를 허용하세요.

- 개인정보 보호 및 보안 > 입력 모니터링
- 개인정보 보호 및 보안 > 손쉬운 사용

권한을 변경한 뒤에는 mac-cro를 다시 실행하세요.

## 삭제

```bash
rm -rf ~/.mac-cro ~/.local/bin/mac-cro
```

설치 스크립트가 shell 설정 파일에 `~/.local/bin` 경로를 추가했다면, `~/.zshrc` 또는 `~/.profile`에서 `# mac-cro` 블록을 삭제하면 됩니다.

## English Guide

English documentation is available in [README.md](README.md).
