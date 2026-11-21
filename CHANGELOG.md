# Changelog

## [0.2.0](https://github.com/maks-sredniawa/darts-scorer/compare/v0.1.0...v0.2.0) (2026-11-21)


### Features

* correct a Dart on a keypad, add and remove Darts, and enter a Visit by hand ([54aadaa](https://github.com/maks-sredniawa/darts-scorer/commit/54aadaa3598a1c4a9e32717568133ed213f01bb4))
* draw Dart markers as a thin ring with the number beside it, so the dart tip stays visible ([3189d7a](https://github.com/maks-sredniawa/darts-scorer/commit/3189d7a1b9bd0b707a9f715f7ef67b4e9f16f7ac))
* find the Board and Darts on the phone with a Kotlin port of locate() on LiteRT ([aa4339c](https://github.com/maks-sredniawa/darts-scorer/commit/aa4339cf9948e48af5389d769205eb21cdeebd13))
* keep each marked Visit in the debug build, and pull them with scripts/pull-marked.py ([da9b888](https://github.com/maks-sredniawa/darts-scorer/commit/da9b88878f40fdc845ad3ab4041763c00f4fec09))
* long-press a Dart's ring and move it onto the tip, keeping the model's point ([8b6a663](https://github.com/maks-sredniawa/darts-scorer/commit/8b6a6638f1f66e58ee6d428ae96ec50344a70488))
* move the tabs to a rail and drop the Visit title in a short window, so the Photo gets the height ([ae51c77](https://github.com/maks-sredniawa/darts-scorer/commit/ae51c77b08bbbe55384e8690b1afefd3620fdf24))
* score a Visit from one Photo of the Board ([6883611](https://github.com/maks-sredniawa/darts-scorer/commit/6883611a980658472d6f8c59fc40ee39ed8736b9))
* **support:** adopt the shared Help and feedback from android-starter ([d3c8174](https://github.com/maks-sredniawa/darts-scorer/commit/d3c8174610df8b5aab3838228d64146266906d60))
* **support:** link licence terms and show licence names on Credits ([c1eee10](https://github.com/maks-sredniawa/darts-scorer/commit/c1eee103788f5939d720a11833a103826f0d922a))
* **support:** open Credits with the people who made the app ([971f402](https://github.com/maks-sredniawa/darts-scorer/commit/971f4027e42ee858ceee84fba26fbd026045d5a1))
* **support:** re-sync Help and feedback with android-starter's address row and copy ([2fdd101](https://github.com/maks-sredniawa/darts-scorer/commit/2fdd10192ec53f09d816c666e03e30e6c014980f))
* the Fan launcher mark on a brass and charcoal palette ([7f84cd2](https://github.com/maks-sredniawa/darts-scorer/commit/7f84cd274a906afda8b9adaa828bc849bc9ff9ed))
* zoom and pan the Photo through accessibility actions, with no drag needed ([51eb964](https://github.com/maks-sredniawa/darts-scorer/commit/51eb964883173253e3eb6d1c07b7d51c8f49dc02))
* zoom and pan the Visit's Photo to check each Dart, with pinch and double-tap ([e3b9ef0](https://github.com/maks-sredniawa/darts-scorer/commit/e3b9ef085e6e8954aae522fc17d9912e8844c742))


### Bug Fixes

* credit pthreadpool, FP16 and FXdiv, and close LiteRT on a model it refuses ([86feef4](https://github.com/maks-sredniawa/darts-scorer/commit/86feef484a5d442d3546651d69a967cb9c10fc50))
* drop the deleted backup screen from the edge-to-edge scenes ([f280ce5](https://github.com/maks-sredniawa/darts-scorer/commit/f280ce52af14d1b55f1356b6f5c44121dd5d1058))
* give a stack an older build saved with Settings at its root its Visit back ([1feaeec](https://github.com/maks-sredniawa/darts-scorer/commit/1feaeec9c80c8b6f4952fae1e1dcf4e17afbf14f))
* give the rail no insets of its own, since the shell's Row already pads the cutout ([fce3724](https://github.com/maks-sredniawa/darts-scorer/commit/fce3724b7715e3674731b87b1e601f7327abeb09))
* keep a camera Photo the sweep raced, count each Photo once across process death, and survive a model failure ([a5085df](https://github.com/maks-sredniawa/darts-scorer/commit/a5085dfe86e97b290d6c8e51adcb4883bf04cdbb))
* keep a Miss set or added by hand on the Photo, drawn hollow ([266a5a8](https://github.com/maks-sredniawa/darts-scorer/commit/266a5a8d8f963474b4b223f6633cc2d7cf0e5724))
* keep the Visit on screen whenever the Visit screen stops, one record per Photo ([571d792](https://github.com/maks-sredniawa/darts-scorer/commit/571d79281d662972521b00784b8dd3ae859430c0))
* keep the Visit when Settings is opened, and return to it on Back ([f6a2f80](https://github.com/maks-sredniawa/darts-scorer/commit/f6a2f807898946ac1c7c804d033612e44994723f))
* **ml:** freeze only the BatchNorms --init loaded with train --freeze-norm, and refuse --freeze-norm without --init in train() ([0e9b484](https://github.com/maks-sredniawa/darts-scorer/commit/0e9b48420bdc20eff8fec0aa6be9c4294a561291))
* move a Dart's ring with the finger, and snap back only where it scores the app's reading ([6f5bc65](https://github.com/maks-sredniawa/darts-scorer/commit/6f5bc65397f84d775ce4d248870507d1c4a7c565))
* name the keypad's groups for TalkBack, wrap its labels, outline its keys, and return focus to Enter the Score yourself ([502531b](https://github.com/maks-sredniawa/darts-scorer/commit/502531b52eac179c2885338d6bf68da0c4b72f3e))
* open a Dart from a tap anywhere on its number badge, placed once for drawing and tapping ([0258582](https://github.com/maks-sredniawa/darts-scorer/commit/0258582201a080abf79ef5f179831a84da070219))
* pad the rail for a side cutout only, not the top one the Scaffold already cleared ([c03a590](https://github.com/maks-sredniawa/darts-scorer/commit/c03a5909adabb0af47d9537a5cf9ca41a4571b74))
* read each keypad key's own position to TalkBack ([5070634](https://github.com/maks-sredniawa/darts-scorer/commit/507063449f475d045ccb5cf5e0f92bba1c34c5e3))
* **scripts:** match whole string fields and check the base strings in aab-locale ([97e8108](https://github.com/maks-sredniawa/darts-scorer/commit/97e8108f294f600ef7631eb7e640d8aea8e565f0))
* scroll the whole Visit screen when it does not fit, mark keyboard focus, and give the empty title a heading ([ec1e5ab](https://github.com/maks-sredniawa/darts-scorer/commit/ec1e5ab66d068b1331ac807770d9f8398b72e630))
* store Photos in sRGB and read colour-profiled Photos as sRGB in ml, so phone and laptop agree ([1389de8](https://github.com/maks-sredniawa/darts-scorer/commit/1389de842ac13edcefb75afe51ee60631159dc7b))
* **support:** keep the helpers heading in release builds ([7a96a32](https://github.com/maks-sredniawa/darts-scorer/commit/7a96a3220b4f02b4abaab8c97dedf360e4dfb0ad))
* **support:** say when the language report finds no mail app, and keep the licence screen safe ([08ba11f](https://github.com/maks-sredniawa/darts-scorer/commit/08ba11f0a05604e7a3841099de7d0c7a505483e6))

## Changelog

Nothing released yet.
