package app.dartsscorer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.w3c.dom.Element
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * A photo never leaves the phone: every backup rule set is include-only and names exactly the
 * preferences and AppCompat's locale record (ADR-0005, ADR-0002). It is what holds the
 * device-transfer restore, which no emulator drives.
 */
class BackupRulesTest {
    @Test
    fun `data extraction rules hold exactly one cloud-backup and one device-transfer`() {
        assertEquals(listOf(CLOUD_BACKUP, DEVICE_TRANSFER), children(root(DATA_EXTRACTION_RULES)).map { it.tagName })
    }

    @Test
    fun `cloud backup includes exactly the expected set`() = assertExpected(section(CLOUD_BACKUP), "<$CLOUD_BACKUP>")

    @Test
    fun `device transfer includes exactly the expected set`() =
        assertExpected(section(DEVICE_TRANSFER), "<$DEVICE_TRANSFER>")

    @Test
    fun `full backup content includes exactly the expected set`() = assertExpected(root(BACKUP_RULES), BACKUP_RULES)

    private fun assertExpected(
        rules: Element,
        label: String,
    ) {
        val rows = children(rules)
        assertTrue("$label has an <exclude> or another element besides <include>", rows.all { it.tagName == "include" })
        val includes = rows.map { "${it.getAttribute("domain")}:${it.getAttribute("path")}" }
        assertEquals("$label names an include twice", includes.size, includes.toSet().size)
        assertEquals(label, EXPECTED, includes.toSet())
        for (row in rows) {
            val path = row.getAttribute("path").trim()
            assertFalse("$label includes the root of ${row.getAttribute("domain")}", path in DOMAIN_ROOTS)
            assertFalse(
                "$label includes $path, a media directory",
                MEDIA_DIRECTORIES.any { path.trimStart('.', '/').startsWith(it) },
            )
        }
    }

    private fun section(tag: String): Element = children(root(DATA_EXTRACTION_RULES)).single { it.tagName == tag }

    private fun root(path: String): Element {
        val file = File(path)
        assertTrue("$path not found at ${file.absolutePath}", file.isFile)
        return DocumentBuilderFactory
            .newInstance()
            .newDocumentBuilder()
            .parse(file)
            .documentElement
    }

    private fun children(parent: Element): List<Element> =
        (0 until parent.childNodes.length).map { parent.childNodes.item(it) }.filterIsInstance<Element>()

    private companion object {
        const val DATA_EXTRACTION_RULES = "src/main/res/xml/data_extraction_rules.xml"
        const val BACKUP_RULES = "src/main/res/xml/backup_rules.xml"
        const val CLOUD_BACKUP = "cloud-backup"
        const val DEVICE_TRANSFER = "device-transfer"

        val EXPECTED =
            setOf(
                "file:datastore/",
                "file:androidx.appcompat.app.AppCompatDelegate.application_locales_record_file",
            )
        val DOMAIN_ROOTS = setOf("", ".", "/", "./")
        val MEDIA_DIRECTORIES = listOf("photos", "thumbnails", "documents")
    }
}
