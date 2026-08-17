export function Watermark() {
  return (
    <div className="watermark" aria-label="推断场,非真实影像">
      INFERENCE FIELD — NOT A CAMERA IMAGE
      <span className="watermark-zh">艺术化信号解释,非真实影像</span>
    </div>
  );
}

export function Legend() {
  const items = [
    { key: "measured", label: "measured 测量", className: "legend-measured" },
    { key: "inferred", label: "inferred 推断", className: "legend-inferred" },
    { key: "generated", label: "generated 生成", className: "legend-generated" },
    { key: "simulated", label: "simulated 模拟", className: "legend-simulated" },
  ];
  return (
    <ul className="legend" aria-label="数据来源图例">
      {items.map((item) => (
        <li key={item.key} className={`legend-item ${item.className}`}>
          <span className="legend-dot" aria-hidden="true" />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
