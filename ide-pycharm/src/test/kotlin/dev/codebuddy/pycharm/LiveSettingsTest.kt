package dev.codebuddy.pycharm

import com.intellij.openapi.options.ConfigurationException
import com.intellij.testFramework.PlatformTestUtil
import com.intellij.testFramework.fixtures.BasePlatformTestCase
import java.awt.Component
import java.awt.Container
import java.awt.image.BufferedImage
import java.io.File
import javax.imageio.ImageIO

/**
 * The settings page against a real brain (`buddy serve` with BUDDY_PORT/BUDDY_HOME/BUDDY_CONFIG
 * set to a scratch folder). Only with -Pe2e; it saves the page as a PNG in
 * `-Dcodebuddy.shotDir` (default build/) so a person can look at it.
 */
class LiveSettingsTest : BasePlatformTestCase() {
    private fun open(): CodeBuddyConfigurable {
        val page = CodeBuddyConfigurable()
        val component = page.createComponent()
        val deadline = System.currentTimeMillis() + 15_000
        while (page.status.text == CodeBuddyConfigurable.LOADING && System.currentTimeMillis() < deadline) {
            PlatformTestUtil.dispatchAllEventsInIdeEventQueue()
            Thread.sleep(20)
        }
        component.setSize(component.preferredSize.width.coerceAtLeast(700), component.preferredSize.height)
        layout(component)
        return page.also { shot(component, "settings-page.png") }
    }

    private fun layout(component: Component) {
        component.doLayout()
        if (component is Container) component.components.forEach(::layout)
    }

    private fun shot(component: Component, name: String) {
        val image = BufferedImage(component.width, component.height, BufferedImage.TYPE_INT_RGB)
        val g = image.createGraphics()
        g.color = component.background
        g.fillRect(0, 0, component.width, component.height)
        component.printAll(g)
        g.dispose()
        val dir = File(System.getProperty("codebuddy.shotDir") ?: "build")
        dir.mkdirs()
        ImageIO.write(image, "png", File(dir, name))
    }

    fun testTheRealBrainLoadsRefusesAndSaves() {
        val page = open()
        assertTrue(page.status.text, page.status.text.contains("config.toml"))
        assertEquals(Provider.CLAUDE_CODE, page.provider.selectedItem)

        // A server on another machine without allow_remote: the brain refuses, saves nothing.
        page.provider.selectedItem = Provider.OPENAI_COMPATIBLE
        page.url.text = "http://10.0.0.2:8080"
        page.allowRemote.isSelected = false
        val refused = try {
            page.apply()
            null
        } catch (e: ConfigurationException) {
            e
        }
        assertTrue(refused?.message.orEmpty(), refused?.message.orEmpty().contains("allow_remote"))

        // Allowed: saved, and the page shows what the brain saved.
        page.allowRemote.isSelected = true
        page.autoOffset.isSelected = false
        page.offset.value = 30
        page.apply()
        assertEquals(Provider.OPENAI_COMPATIBLE, page.provider.selectedItem)
        assertFalse(page.isModified)
        val reopened = open()
        assertEquals("http://10.0.0.2:8080", reopened.url.text)
        assertFalse(reopened.autoOffset.isSelected)
    }
}
