import CoreGraphics

/// Resting island size, using the physical notch only when the screen has one.
/// Adapted from Coucou's screen geometry (MIT, © 2026 Louis Raillé, see THIRD_PARTY.md).
public struct IslandScreenGeometry: Equatable, Sendable {
    public static let fallbackNotchWidth: CGFloat = 184
    static let noNotchWidth: CGFloat = 80
    static let noNotchHeight: CGFloat = 24

    public let hasNotch: Bool
    public let width: CGFloat
    public let height: CGFloat

    public init(screenWidth: CGFloat, safeAreaTop: CGFloat,
                auxiliaryLeftWidth: CGFloat?, auxiliaryRightWidth: CGFloat?,
                menuBarHeight: CGFloat) {
        hasNotch = safeAreaTop > 0
        if hasNotch {
            if let left = auxiliaryLeftWidth, let right = auxiliaryRightWidth {
                let measured = screenWidth - left - right
                width = measured > 0 && measured < screenWidth ? measured : Self.fallbackNotchWidth
            } else {
                width = Self.fallbackNotchWidth
            }
            height = safeAreaTop
        } else {
            width = Self.noNotchWidth
            height = min(Self.noNotchHeight, menuBarHeight)
        }
    }
}

/// Island size and corner shape for each state.
public struct IslandLayout: Equatable, Sendable {
    public static let earWidth: CGFloat = 76
    public static let expandedWidth: CGFloat = 520
    public static let expandedHeight: CGFloat = 380
    /// Peek with a hint: a line of text under the notch.
    public static let previewWidth: CGFloat = 460
    public static let previewHeight: CGFloat = 30

    public let width: CGFloat
    public let height: CGFloat
    /// Bottom corner radius.
    public let cornerRadius: CGFloat
    /// > 0: convex top corners; < 0: concave "ears" that melt into the menu bar (see IslandShape).
    public let topRadius: CGFloat

    public init(state: IslandStateMachine.State, notch: IslandScreenGeometry, preview: Bool = false) {
        switch state {
        case .hidden:
            self.init(width: notch.width, height: notch.height, cornerRadius: 8, topRadius: -6)
        case .peek where preview:
            self.init(width: max(Self.previewWidth, notch.width + 2 * Self.earWidth),
                      height: notch.height + Self.previewHeight, cornerRadius: 14, topRadius: -6)
        case .peek:
            self.init(width: notch.width + 2 * Self.earWidth, height: notch.height,
                      cornerRadius: 10, topRadius: -6)
        case .expanded:
            self.init(width: max(Self.expandedWidth, notch.width + 2 * Self.earWidth),
                      height: Self.expandedHeight, cornerRadius: 24, topRadius: -10)
        }
    }

    public init(width: CGFloat, height: CGFloat, cornerRadius: CGFloat, topRadius: CGFloat) {
        self.width = width
        self.height = height
        self.cornerRadius = cornerRadius
        self.topRadius = topRadius
    }
}
