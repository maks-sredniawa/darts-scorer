# Vocabulary

<The words this app uses, and the ones it does not. Fill this in early — it is cheap now and
expensive later, because a name that is wrong in the model is wrong in the schema, the UI copy, every
translation of it, and the URL scheme.>

**The rule this file exists to enforce: one concept, one word, everywhere.** The entity, the DAO, the
route key, the string resource and the sentence in the UI all use it. When the domain word and the
user-facing word genuinely differ, both are written here with the difference stated.

## The domain

| Term | Means | Not |
| --- | --- | --- |
| **Board** | the regulation steel-tip dartboard (ADR-0008) | target, dartboard in code |
| **Dart** | one dart stuck in the board, as found in the photos | arrow, throw, hit |
| **Visit** | the darts one player throws in a turn, usually three, and their total | turn, round, throw |
| **Photo** | one picture of the board after a Visit; a Visit may need several | image, shot, frame |
| **Angle** | the direction a Photo is taken from. *Another angle* is what the app asks for when it is unsure | view, side |
| **Entry point** | where a Dart's shaft enters the Board; the only point that is scored | tip, hit point |
| **Calibration point** | a point on the Board's wires whose position is known, used to map a Photo onto the Board | keypoint, anchor, marker |
| **Score** | a Dart's value (e.g. *treble 20*, 60) or a Visit's total | points, result |
| **Tip** | a one-off payment to the developer through Google Play that **unlocks nothing** (ADR-0007). The home screen mentions it once per install; Help and feedback offers it for good | donation, support the project, premium, supporter |

## Words we deliberately avoid

<For example: "'delete' is reserved for something irreversible; anything recoverable is 'archived'."
The value here is in the distinctions, not the definitions.>

## Naming conventions in code

Some names in this codebase are deliberately generic — `AppDatabase`, `AppTheme`, `AppPreferences`,
`AppContainer`, `MainApplication`, `MainActivity`. They stay correct whatever the app is called, so
renaming the app is a package move rather than a repo-wide find-and-replace. Don't rename them to
match the product; name the *domain* types after the domain instead.
