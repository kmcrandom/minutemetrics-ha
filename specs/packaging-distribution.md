# Packaging and Distribution Spec

## Purpose

MinuteMetrics should be usable by other people without editing source code or knowing the original household setup.

## Home Assistant App Distribution

Package as a Home Assistant app repository. Home Assistant previously called this surface "add-ons"; project docs should use "app" for current Home Assistant UI language.

Repository structure target:

```text
repository.yaml
minutemetrics/
  config.yaml
  Dockerfile
  run.sh
  README.md
  requirements.txt
  src/
```

App requirements:

- Initial published image support for `aarch64` so Home Assistant Yellow can install quickly.
- Future multi-architecture support for at least `aarch64` and `amd64` after each image is tested.
- Persistent data volume.
- Clear configuration schema.
- Ingress support for dashboard/admin UI if feasible.
- Local network access for iOS app sync.
- No `build.yaml`.
- Published installs should use the `image` field in `config.yaml` and pull a pre-built GHCR image.
- The Dockerfile must support local builds with `BUILD_ARCH` and `BUILD_VERSION` arguments.
- App options are read from `/data/options.json`.
- SQLite defaults to `/data/minutemetrics.sqlite`.

GitHub repository requirements:

- Root `repository.yaml` for Home Assistant repository metadata.
- Installable app directory named `minutemetrics/`.
- CI that runs backend tests and validates the Home Assistant image build.
- Publish workflow that pushes `ghcr.io/kmcrandom/minutemetrics-ha:<version>` for `aarch64`.
- Dependabot enabled for Python and GitHub Actions.
- License, contribution, and security policy files.
- `.gitignore` and Docker ignore rules exclude virtual environments, caches, SQLite databases, logs, and local Apple/Xcode state.

## iOS Distribution

Initial:

- Source build instructions.
- Xcode project.
- TestFlight-ready configuration notes.

Future:

- Public App Store release if the project matures.

Important:

- HealthKit entitlement setup must be documented.
- Privacy manifest and HealthKit usage description must be included.
- The app should not mention a specific household or participant.

## Documentation

Required docs:

- Quick start.
- Home Assistant app install.
- Participant setup.
- iOS app build/install.
- Reverse proxy/VPN guidance.
- Apple Health validation guide.
- Troubleshooting.
- Security and privacy notes.

Documentation tone:

- Public README files should use professional GitHub project language.
- Avoid household-specific setup notes, local machine paths, private network addresses, and throwaway prototype phrasing.
- Distinguish pre-release status from incomplete local notes.

## Versioning

Use semantic versioning:

- Home Assistant app API breaking changes require a major version bump.
- iOS app should send app version in sync payloads.
- API responses should include service version.

## Implementation Plan

1. Create Home Assistant app repository skeleton.
2. Create local development Docker workflow.
3. Create iOS project build instructions.
4. Add sample screenshots and setup flow docs.
5. Add release checklist.
6. Add contribution guide.

## Acceptance Criteria

- A new user can install the app from a repository URL.
- A new user can create participants without editing code.
- A participant can pair their iOS app using generated setup data.
- Documentation does not rely on names from the original installation.
