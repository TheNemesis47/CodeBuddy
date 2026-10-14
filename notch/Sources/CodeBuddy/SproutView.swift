import CodeBuddyKit
import SwiftUI

/// Sprout, placeholder version (G8 has the real design): a seed that grows a stem and two leaves
/// while the buddy is thinking, and stays sprouted when the answer is done.
/// Drawn in Canvas at 60 fps with no images, in a unit space of 100×100.
struct SproutView: View {
    let mood: SproutMood
    var size: CGFloat = 22

    @State private var growth: Double = 0

    private var targetGrowth: Double {
        switch mood {
        case .idle: 0
        case .thinking: 0.6
        case .happy: 1
        case .worried: 0.25
        }
    }

    var body: some View {
        TimelineView(.animation) { timeline in
            let t = timeline.date.timeIntervalSinceReferenceDate
            Canvas { context, canvasSize in
                context.scaleBy(x: canvasSize.width / 100, y: canvasSize.height / 100)
                SproutDrawing(growth: growth, mood: mood, time: t).draw(in: &context)
            }
        }
        .frame(width: size, height: size)
        .onAppear { growth = targetGrowth }
        .onChange(of: mood) { _, _ in
            withAnimation(.spring(response: 0.6, dampingFraction: 0.6)) { growth = targetGrowth }
        }
        .accessibilityLabel("Sprout")
    }
}

/// Pure drawing so it can be reasoned about apart from the view.
struct SproutDrawing {
    let growth: Double  // 0 = seed, 1 = full sprout
    let mood: SproutMood
    let time: TimeInterval

    static let seed = Color(red: 0.78, green: 0.56, blue: 0.33)
    static let seedShade = Color(red: 0.55, green: 0.37, blue: 0.20)
    static let leaf = Color(red: 0.42, green: 0.80, blue: 0.42)
    static let stem = Color(red: 0.30, green: 0.62, blue: 0.32)

    func draw(in context: inout GraphicsContext) {
        let breathe = 1 + 0.035 * sin(time * 2.2)
        let wobble = mood == .thinking ? 6 * sin(time * 5) : 2 * sin(time * 1.3)
        let g = max(0, min(1, growth))

        // Stem and leaves grow out of the top of the seed.
        let stemTop = CGPoint(x: 50 + wobble * 0.4, y: 52 - 34 * g)
        if g > 0.02 {
            var stem = Path()
            stem.move(to: CGPoint(x: 50, y: 56))
            stem.addQuadCurve(to: stemTop, control: CGPoint(x: 50 + wobble, y: 56 - 18 * g))
            context.stroke(stem, with: .color(Self.stem), style: StrokeStyle(lineWidth: 5, lineCap: .round))
            let leafSize = 20 * g
            drawLeaf(&context, at: stemTop, size: leafSize, angle: -35 + wobble)
            drawLeaf(&context, at: stemTop, size: leafSize * 0.85, angle: 215 + wobble)
        }

        // The seed: a slightly tilted oval with a darker belly.
        let w = 48 * breathe, h = 40 / breathe
        let seedRect = CGRect(x: 50 - w / 2, y: 92 - h, width: w, height: h)
        context.fill(Path(ellipseIn: seedRect), with: .color(Self.seed))
        context.fill(Path(ellipseIn: seedRect.insetBy(dx: 6, dy: 10).offsetBy(dx: 2, dy: 8)),
                     with: .color(Self.seedShade.opacity(0.35)))

        // Eyes: blink every few seconds; worried = slanted.
        let blink = (time.truncatingRemainder(dividingBy: 4.2)) < 0.12
        let eyeY = seedRect.midY - 2
        for dx in [-9.0, 9.0] {
            let eye = CGRect(x: 50 + dx - 3, y: eyeY - (blink ? 0.8 : 4), width: 6, height: blink ? 1.6 : 8)
            context.fill(Path(roundedRect: eye, cornerRadius: 3), with: .color(.black.opacity(0.85)))
        }
        if mood == .worried {
            var brow = Path()
            brow.move(to: CGPoint(x: 37, y: eyeY - 9)); brow.addLine(to: CGPoint(x: 45, y: eyeY - 6))
            brow.move(to: CGPoint(x: 63, y: eyeY - 9)); brow.addLine(to: CGPoint(x: 55, y: eyeY - 6))
            context.stroke(brow, with: .color(.black.opacity(0.7)), lineWidth: 2.5)
        } else if mood == .happy {
            var smile = Path()
            smile.addArc(center: CGPoint(x: 50, y: eyeY + 7), radius: 5,
                         startAngle: .degrees(20), endAngle: .degrees(160), clockwise: false)
            context.stroke(smile, with: .color(.black.opacity(0.7)), lineWidth: 2.2)
        }
    }

    private func drawLeaf(_ context: inout GraphicsContext, at base: CGPoint, size: CGFloat, angle: Double) {
        guard size > 0.5 else { return }
        var leaf = Path()
        leaf.move(to: .zero)
        leaf.addQuadCurve(to: CGPoint(x: size, y: 0), control: CGPoint(x: size * 0.5, y: -size * 0.55))
        leaf.addQuadCurve(to: .zero, control: CGPoint(x: size * 0.5, y: size * 0.55))
        let transform = CGAffineTransform(translationX: base.x, y: base.y)
            .rotated(by: angle * .pi / 180)
        context.fill(leaf.applying(transform), with: .color(Self.leaf))
    }
}
