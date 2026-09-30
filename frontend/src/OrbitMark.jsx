import "./orbit-mark.css";

const PETAL_COUNT = 16;

function petalPath(rTip = 62, rBase = 104, width = 13) {
  const bulgeY = -(rTip + (rBase - rTip) * 0.6);
  const capY = -rBase;
  return `M 0 ${-rTip}
    C ${width * 0.64} ${-rTip - (rBase - rTip) * 0.15}, ${width * 0.92} ${bulgeY + width * 0.48}, ${width * 0.74} ${capY + width * 0.6}
    C ${width * 0.48} ${capY}, ${-width * 0.48} ${capY}, ${-width * 0.74} ${capY + width * 0.6}
    C ${-width * 0.92} ${bulgeY + width * 0.48}, ${-width * 0.64} ${-rTip - (rBase - rTip) * 0.15}, 0 ${-rTip} Z`;
}

const PETAL_PATH = petalPath();

export default function OrbitMark({
  state = "idle",
  className = "",
  label,
}) {
  return (
    <span
      className={`orbit-ai-mark ${className}`.trim()}
      data-state={state}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <svg viewBox="0 0 220 220" focusable="false">
        <circle className="orbit-mark-outline" cx="110" cy="110" r="88" />
        <g transform="translate(110 110)">
          {Array.from({ length: PETAL_COUNT }, (_, index) => (
            <g
              className="orbit-mark-petal"
              transform={`rotate(${index * (360 / PETAL_COUNT)})`}
              key={index}
            >
              <path d={PETAL_PATH} style={{ "--petal-index": index }} />
            </g>
          ))}
        </g>
      </svg>
    </span>
  );
}
