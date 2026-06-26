// Fixed (not random) positions/timings so server and client render identically —
// no hydration mismatch. Pure CSS animation; the global prefers-reduced-motion
// rule in globals.css freezes all of this automatically.

const ORBS = [
  { top: "-8%", left: "10%", size: 420, color: "var(--aurora-to)", anim: "ambient-drift-a", duration: "32s" },
  { top: "55%", left: "82%", size: 360, color: "var(--aurora-from)", anim: "ambient-drift-b", duration: "38s" },
  { top: "80%", left: "5%", size: 320, color: "var(--aurora-to)", anim: "ambient-drift-c", duration: "44s" },
];

const STARS = [
  [4, 12], [9, 38], [14, 71], [18, 22], [22, 90], [27, 55], [31, 8], [35, 66],
  [40, 33], [44, 81], [48, 17], [52, 60], [57, 44], [61, 92], [65, 5], [69, 28],
  [73, 75], [77, 49], [81, 14], [85, 87], [89, 36], [93, 63], [97, 20], [12, 95],
].map(([top, left], i) => ({ top: `${top}%`, left: `${left}%`, delay: `${(i % 7) * 0.6}s`, size: i % 3 === 0 ? 2 : 1 }));

export function AmbientBackground() {
  return (
    <div className="fixed inset-0 z-0 overflow-hidden" aria-hidden="true">
      {ORBS.map((orb, i) => (
        <div
          key={i}
          className="ambient-orb"
          style={{
            top: orb.top,
            left: orb.left,
            width: orb.size,
            height: orb.size,
            background: orb.color,
            opacity: 0.16,
            animation: `${orb.anim} ${orb.duration} ease-in-out infinite`,
          }}
        />
      ))}
      {STARS.map((star, i) => (
        <div
          key={i}
          className="ambient-star"
          style={{
            top: star.top,
            left: star.left,
            width: star.size,
            height: star.size,
            animation: `ambient-twinkle ${3 + (i % 4)}s ease-in-out infinite`,
            animationDelay: star.delay,
          }}
        />
      ))}
    </div>
  );
}
