import CoreGraphics
import Testing
@testable import CodeBuddyKit

struct GeometryTests {
    @Test func notchWidthComesFromTheAuxiliaryAreas() {
        let g = IslandScreenGeometry(screenWidth: 1512, safeAreaTop: 32, auxiliaryLeftWidth: 664,
                                     auxiliaryRightWidth: 663, menuBarHeight: 32)
        #expect(g.hasNotch)
        #expect(g.width == 185)
        #expect(g.height == 32)
    }

    @Test func notchWithoutAuxiliaryAreasFallsBack() {
        let g = IslandScreenGeometry(screenWidth: 1512, safeAreaTop: 32, auxiliaryLeftWidth: nil,
                                     auxiliaryRightWidth: nil, menuBarHeight: 32)
        #expect(g.width == IslandScreenGeometry.fallbackNotchWidth)
    }

    @Test func noNotchGetsASmallBar() {
        let g = IslandScreenGeometry(screenWidth: 2560, safeAreaTop: 0, auxiliaryLeftWidth: nil,
                                     auxiliaryRightWidth: nil, menuBarHeight: 22)
        #expect(!g.hasNotch)
        #expect(g.width == 80)
        #expect(g.height == 22)
    }

    @Test func layoutGrowsWithTheState() {
        let notch = IslandScreenGeometry(screenWidth: 1512, safeAreaTop: 32, auxiliaryLeftWidth: 664,
                                         auxiliaryRightWidth: 663, menuBarHeight: 32)
        let hidden = IslandLayout(state: .hidden, notch: notch)
        let peek = IslandLayout(state: .peek, notch: notch)
        let expanded = IslandLayout(state: .expanded, notch: notch)
        #expect(hidden.width == notch.width && hidden.height == notch.height)
        #expect(peek.width == notch.width + 2 * IslandLayout.earWidth && peek.height == notch.height)
        #expect(expanded.width >= peek.width && expanded.height > peek.height)
    }
}
