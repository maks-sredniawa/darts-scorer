# Darts Scorer

Darts Scorer scores a darts visit from one photo of the board, so you don't have to tally the darts
by hand. It finds the board and each dart, marks them on the photo and adds up the visit; a dart it
is unsure of is marked *Check* for you to correct. Combining photos taken from several angles, asking
for another only when a dart is hidden or unclear, is phase 2 of [`docs/PLAN.md`](docs/PLAN.md) and
not built yet.

The photos never leave the phone unless the player chooses to share one, from version 1.0
(`docs/PLAN.md`, phase S): finding the board and the darts runs on the device, offline. Free, no
ads, no account.

## Status

On Google Play's internal testing track since 0.2.0 (2026-11-22); closed testing, production and
1.0 follow. It still gets darts wrong, most often on boards with printed decorations around the
numbers.

## Contributing

Darts Scorer is source-available, not open source: read it, verify it, file issues. Pull requests are not
accepted — see [LICENSE](LICENSE).

The model in `app/src/main/assets/model/` is trained on the
[DeepDarts dataset](https://ieee-dataport.org/open-access/deepdarts-dataset) (McNally et al.),
under CC BY 4.0, which the app credits on its Credits screen with the licence text in
`app/src/main/assets/licences/` ([ADR-0008](docs/adr/0008-darts-are-found-by-an-on-device-keypoint-model-and-a-homography.md)).

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
