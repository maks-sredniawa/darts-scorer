package app.dartsscorer.ui.support

/**
 * Everything about Help and feedback that differs from one app to the next — **the one file in
 * `ui/support/` that android-starter's `scripts/sync-support.py` never overwrites.** Every other
 * file in this package, and the `shared:support` block of each `strings.xml`, comes from
 * android-starter.
 *
 * Each constant is compiled into every build and frozen there for as long as a sideloaded copy
 * survives, so the address and the site sit on a domain we own, whose routing can move without a
 * release. The Play listing's contact field carries the same address —
 * `docs/DOD.md`, *Before the first upload*.
 */
object SupportConfig {
    const val SUPPORT_ADDRESS = "darts-scorer.support@maksforge.com"

    /**
     * The id Play knows this app by, as a literal rather than `BuildConfig.APPLICATION_ID`: debug
     * builds carry `applicationIdSuffix = ".debug"`, and Play has never heard of the suffixed id.
     */
    const val PLAY_PACKAGE = "com.maksforge.dartsscorer"

    /** The mail subject's prefix — "`<MAIL_TAG> #bug`" — which a mail filter sorts on. Never translated. */
    const val MAIL_TAG = "Darts Scorer"

    /** The app's page on maksforge.com; the privacy policy is `privacy-policy` beneath it. */
    const val SITE_URL = "https://maksforge.com/darts-scorer/"

    /**
     * What the build ships that Licensee never sees — a model or a data set fetched as a file — shown
     * on the Credits screen beside the dependencies.
     */
    val BUNDLED_CREDITS: List<LicensedArtifact> =
        // LiteRT's own artifact is in Licensee's list; these are compiled into its native library, or
        // trained into the model, where the dependency list cannot see them (ADR-0008, 2026-11-19).
        listOf(
            inLiteRt("libeigen", "eigen", "https://gitlab.com/libeigen/eigen", MPL_2_0),
            inLiteRt("google", "xnnpack", "https://github.com/google/XNNPACK", BSD_3_CLAUSE),
            inLiteRt("google", "ruy", "https://github.com/google/ruy", APACHE_2_0),
            inLiteRt("google", "gemmlowp", "https://github.com/google/gemmlowp", APACHE_2_0),
            inLiteRt("google", "flatbuffers", "https://github.com/google/flatbuffers", APACHE_2_0),
            inLiteRt("pytorch", "cpuinfo", "https://github.com/pytorch/cpuinfo", BSD_2_CLAUSE),
            inLiteRt("google", "pthreadpool", "https://github.com/google/pthreadpool", BSD_2_CLAUSE),
            inLiteRt("maratyszcza", "fp16", "https://github.com/Maratyszcza/FP16", MIT),
            inLiteRt("maratyszcza", "fxdiv", "https://github.com/Maratyszcza/FXdiv", MIT),
            LicensedArtifact(
                groupId = "ooura",
                artifactId = "fft2d",
                version = LITERT,
                name = "fft2d",
                source = "https://www.kurims.kyoto-u.ac.jp/~ooura/fft.html",
                unknownLicenses =
                    listOf(
                        UnknownLicence(
                            "Takuya Ooura's fft2d licence",
                            "https://github.com/tensorflow/tensorflow/blob/master/third_party/fft2d/LICENSE",
                        ),
                    ),
            ),
            LicensedArtifact(
                groupId = "McNally et al.",
                artifactId = "DeepDarts dataset",
                version = "2021",
                name = "DeepDarts dataset",
                source = "https://ieee-dataport.org/open-access/deepdarts-dataset",
                spdxLicenses = listOf(CC_BY_4_0),
            ),
        )

    /** People who helped with this app, shown on Credits under the creator; none hides the section. */
    val CONTRIBUTORS: List<Contributor> = emptyList()
}

// LiteRT builds these from TensorFlow's main branch at its release, which pins no upstream version
// of them, so the version names the LiteRT build that carries them.
private const val LITERT = "litert-1.4.2"

private val APACHE_2_0 = SpdxLicence("Apache-2.0", "Apache License 2.0", "https://www.apache.org/licenses/LICENSE-2.0")
private val BSD_2_CLAUSE =
    SpdxLicence("BSD-2-Clause", "BSD 2-Clause \"Simplified\" License", "https://opensource.org/licenses/BSD-2-Clause")
private val BSD_3_CLAUSE =
    SpdxLicence(
        "BSD-3-Clause",
        "BSD 3-Clause \"New\" or \"Revised\" License",
        "https://opensource.org/licenses/BSD-3-Clause",
    )
private val MIT = SpdxLicence("MIT", "MIT License", "https://opensource.org/licenses/MIT")
private val MPL_2_0 = SpdxLicence("MPL-2.0", "Mozilla Public License 2.0", "https://www.mozilla.org/MPL/2.0/")
private val CC_BY_4_0 =
    SpdxLicence(
        "CC-BY-4.0",
        "Creative Commons Attribution 4.0 International",
        "https://creativecommons.org/licenses/by/4.0/",
    )

private fun inLiteRt(
    owner: String,
    project: String,
    source: String,
    licence: SpdxLicence,
) = LicensedArtifact(
    groupId = owner,
    artifactId = project,
    version = LITERT,
    source = source,
    spdxLicenses = listOf(licence),
)
