# Darts Scorer

Darts Scorer counts your darts score from a few photos of the board, taken from different angles,
as few as it needs, so you don't have to tally the darts by hand.

The photos never leave the phone: finding the board and the darts runs on the device, offline. Free,
no ads, no account.

## Status

Just bootstrapped from [android-starter](https://github.com/maks-sredniawa/android-starter). The release
pipeline and quality gates are real; the screens are still the template's placeholder app. Nothing
is on Play yet.

## Contributing

Darts Scorer is source-available, not open source: read it, verify it, file issues. Pull requests are not
accepted — see [LICENSE](LICENSE).

## Build

```bash
./gradlew assembleDebug          # build
./gradlew installDebug           # build + install on the connected phone
./gradlew test                   # JVM unit tests
./gradlew connectedAndroidTest   # instrumented tests — needs a device
./gradlew spotlessApply          # format (the CI gate is spotlessCheck)
python3 scripts/project.py       # what the toolchain thinks this app is called
```

Commit subjects are [Conventional Commits](https://www.conventionalcommits.org); release-please
derives the version and `CHANGELOG.md` from them. See [docs/RELEASING.md](docs/RELEASING.md).
