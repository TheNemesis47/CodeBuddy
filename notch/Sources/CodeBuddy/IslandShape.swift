import SwiftUI

/// The black island shape.
/// topRadius > 0 → convex rounded top corners; < 0 → concave "ears" that flare into the menu
/// bar (|topRadius| = ear radius; the body is |topRadius| narrower on each side); = 0 → sharp. Animatable, so the island morphs between
/// states.
/// Adapted from Coucou's island shape (MIT, © 2026 Louis Raillé, see THIRD_PARTY.md); the ear
/// variant is redrawn so the top edge is flush with the screen.
struct IslandShape: Shape {
    var width: CGFloat
    var height: CGFloat
    var cornerRadius: CGFloat
    var topRadius: CGFloat

    var animatableData: AnimatablePair<AnimatablePair<AnimatablePair<CGFloat, CGFloat>, CGFloat>, CGFloat> {
        get { .init(.init(.init(width, height), cornerRadius), topRadius) }
        set {
            width = newValue.first.first.first
            height = newValue.first.first.second
            cornerRadius = newValue.first.second
            topRadius = newValue.second
        }
    }

    func path(in rect: CGRect) -> Path {
        let cr = max(0, min(cornerRadius, height / 2))
        var p = Path()
        if topRadius >= 0 {
            let tr = min(topRadius, min(width / 2, height / 2))
            p.move(to: CGPoint(x: tr, y: 0))
            p.addLine(to: CGPoint(x: width - tr, y: 0))
            p.addArc(center: CGPoint(x: width - tr, y: tr), radius: tr,
                     startAngle: .degrees(270), endAngle: .degrees(0), clockwise: false)
            p.addLine(to: CGPoint(x: width, y: height - cr))
            p.addArc(center: CGPoint(x: width - cr, y: height - cr), radius: cr,
                     startAngle: .degrees(0), endAngle: .degrees(90), clockwise: false)
            p.addLine(to: CGPoint(x: cr, y: height))
            p.addArc(center: CGPoint(x: cr, y: height - cr), radius: cr,
                     startAngle: .degrees(90), endAngle: .degrees(180), clockwise: false)
            p.addLine(to: CGPoint(x: 0, y: tr))
            p.addArc(center: CGPoint(x: tr, y: tr), radius: tr,
                     startAngle: .degrees(180), endAngle: .degrees(270), clockwise: false)
        } else {
            // Concave ears: the top edge runs flush along the screen edge, and the outer top
            // corners curve inward, so the body (width - 2·er) hangs from the menu bar.
            let er = min(-topRadius, width / 4)
            p.move(to: CGPoint(x: 0, y: 0))
            p.addLine(to: CGPoint(x: width, y: 0))
            p.addArc(center: CGPoint(x: width, y: er), radius: er,
                     startAngle: .degrees(270), endAngle: .degrees(180), clockwise: true)
            p.addLine(to: CGPoint(x: width - er, y: height - cr))
            p.addArc(center: CGPoint(x: width - er - cr, y: height - cr), radius: cr,
                     startAngle: .degrees(0), endAngle: .degrees(90), clockwise: false)
            p.addLine(to: CGPoint(x: er + cr, y: height))
            p.addArc(center: CGPoint(x: er + cr, y: height - cr), radius: cr,
                     startAngle: .degrees(90), endAngle: .degrees(180), clockwise: false)
            p.addLine(to: CGPoint(x: er, y: er))
            p.addArc(center: CGPoint(x: 0, y: er), radius: er,
                     startAngle: .degrees(0), endAngle: .degrees(270), clockwise: true)
        }
        p.closeSubpath()
        return p
    }
}
