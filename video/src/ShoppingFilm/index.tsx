import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  FONT,
  PALETTE,
  SCENES,
  SHOPPING_FILM_DURATION,
} from "./constants";
import { SHOPPING_RESULTS, VOICE_CAPTURE_TEXT } from "./storyboard";

type LightState = "green" | "red";

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

const ease = Easing.bezier(0.16, 1, 0.3, 1);
const PHONE_FONT = "Arial, Helvetica, sans-serif";

const useEntrance = (delaySeconds = 0, durationSeconds = 1) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return interpolate(
    frame,
    [delaySeconds * fps, (delaySeconds + durationSeconds) * fps],
    [0, 1],
    { ...clamp, easing: ease },
  );
};

const Stage: React.FC<{ children: React.ReactNode; tone?: "black" | "white" }> = ({
  children,
  tone = "black",
}) => {
  const frame = useCurrentFrame();
  const glow = interpolate(frame, [0, SHOPPING_FILM_DURATION], [0, 1], clamp);
  const bg =
    tone === "white"
      ? `linear-gradient(180deg, #f7f7f2 0%, #e8e8e3 100%)`
      : `linear-gradient(180deg, ${PALETTE.black} 0%, #101012 58%, #030303 100%)`;

  return (
    <AbsoluteFill style={{ background: bg, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: tone === "white" ? 0.26 : 0.18,
          backgroundImage:
            "linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px)",
          backgroundSize: "96px 96px",
          transform: `translateX(${glow * -40}px)`,
        }}
      />
      {children}
    </AbsoluteFill>
  );
};

const SceneTitle: React.FC<{
  eyebrow: string;
  title: string;
  subtitle?: string;
  darkText?: boolean;
  maxWidth?: number;
}> = ({ eyebrow, title, subtitle, darkText = false, maxWidth = 980 }) => {
  const enter = useEntrance(0.1, 0.9);
  return (
    <div
      style={{
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [28, 0])}px)`,
      }}
    >
      <div
        style={{
          fontFamily: FONT.mono,
          fontSize: 19,
          color: darkText ? "#636366" : PALETTE.muted,
          textTransform: "uppercase",
          letterSpacing: 0,
          marginBottom: 18,
        }}
      >
        {eyebrow}
      </div>
      <h1
        style={{
          fontFamily: FONT.sans,
          fontSize: 78,
          lineHeight: 0.96,
          fontWeight: 700,
          color: darkText ? "#111113" : PALETTE.white,
          margin: 0,
          maxWidth,
          letterSpacing: 0,
        }}
      >
        {title}
      </h1>
      {subtitle ? (
        <p
          style={{
            fontFamily: FONT.text,
            fontSize: 29,
            lineHeight: 1.35,
          color: darkText ? "#4b4b4f" : PALETTE.softWhite,
          margin: "26px 0 0",
          maxWidth: Math.min(maxWidth, 780),
        }}
      >
          {subtitle}
        </p>
      ) : null}
    </div>
  );
};

const PhoneFrame: React.FC<{
  children: React.ReactNode;
  scale?: number;
  x?: number;
  y?: number;
  rotate?: number;
}> = ({ children, scale = 1, x = 0, y = 0, rotate = 0 }) => (
  <div
    style={{
      width: 404,
      height: 824,
      borderRadius: 64,
      padding: 14,
      background:
        "linear-gradient(145deg, #f4f4ee 0%, #76777d 24%, #171719 58%, #f1f1ec 100%)",
      boxShadow:
        "0 44px 120px rgba(0,0,0,0.56), inset 0 0 0 1px rgba(255,255,255,0.55)",
      transform: `translate(${x}px, ${y}px) rotate(${rotate}deg) scale(${scale})`,
    }}
  >
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        borderRadius: 52,
        overflow: "hidden",
        background: "#080811",
        fontFamily: PHONE_FONT,
      }}
    >
      {children}
    </div>
  </div>
);

const SegmentedCaptureControl: React.FC = () => (
  <div
    style={{
      margin: "18px 14px 0",
      height: 54,
      borderRadius: 13,
      background: "#151420",
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      padding: 10,
      color: "#f6f5fa",
      fontSize: 15,
      fontWeight: 690,
      boxShadow: "0 10px 22px rgba(0,0,0,0.22)",
    }}
  >
    <div
      style={{
        borderRadius: 9,
        background: "#201f30",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      Voice
    </div>
    <div
      style={{
        color: "#87838f",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      Text
    </div>
  </div>
);

const BottomTabs: React.FC<{ active?: "Capture" | "Inbox" | "Tasks" | "Status" }> = ({
  active = "Capture",
}) => (
  <div
    style={{
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      height: 88,
      background: "#30303a",
      borderTop: "1px solid rgba(255,255,255,0.09)",
      display: "grid",
      gridTemplateColumns: "repeat(4, 1fr)",
      color: "#85838e",
      fontSize: 13,
      paddingTop: 17,
    }}
  >
    {[
      ["mic", "Capture"],
      ["tray", "Inbox"],
      ["check", "Tasks"],
      ["spark", "Status"],
    ].map(([icon, label]) => (
      <div
        key={label}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 6,
          color: label === active ? "#ffffff" : "#85838e",
        }}
      >
        <TabIcon kind={icon} active={label === active} />
        <div>{label}</div>
      </div>
    ))}
  </div>
);

const TabIcon: React.FC<{ kind: string; active?: boolean }> = ({
  kind,
  active = false,
}) => {
  const color = active ? "#ffffff" : "#85838e";
  if (kind === "mic") {
    return (
      <div style={{ position: "relative", width: 20, height: 24 }}>
        <div
          style={{
            position: "absolute",
            left: 6,
            top: 0,
            width: 8,
            height: 15,
            borderRadius: 8,
            border: `2px solid ${color}`,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 2,
            top: 9,
            width: 16,
            height: 9,
            border: `2px solid ${color}`,
            borderTop: 0,
            borderRadius: "0 0 10px 10px",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 9,
            top: 19,
            width: 2,
            height: 5,
            background: color,
          }}
        />
      </div>
    );
  }

  if (kind === "tray") {
    return (
      <div
        style={{
          width: 21,
          height: 16,
          border: `2px solid ${color}`,
          borderRadius: 4,
          borderTopColor: "transparent",
          transform: "skewX(-8deg)",
        }}
      />
    );
  }

  if (kind === "check") {
    return (
      <div
        style={{
          position: "relative",
          width: 21,
          height: 21,
          border: `2px solid ${color}`,
          borderRadius: 4,
        }}
      >
        <div
          style={{
            position: "absolute",
            left: 4,
            top: 7,
            width: 10,
            height: 5,
            borderLeft: `2px solid ${color}`,
            borderBottom: `2px solid ${color}`,
            transform: "rotate(-45deg)",
          }}
        />
      </div>
    );
  }

  return (
    <div style={{ position: "relative", width: 24, height: 24 }}>
      {[0, 45, 90, 135].map((rotation) => (
        <div
          key={rotation}
          style={{
            position: "absolute",
            left: 11,
            top: 2,
            width: 2,
            height: 20,
            borderRadius: 2,
            background: color,
            transform: `rotate(${rotation}deg)`,
          }}
        />
      ))}
    </div>
  );
};

const RecordButton: React.FC<{ active?: boolean }> = ({ active = false }) => {
  const frame = useCurrentFrame();
  const pulse = interpolate(frame % 44, [0, 22, 44], [0, 1, 0], clamp);
  return (
    <div
      style={{
        position: "relative",
        width: active ? 88 : 86,
        height: active ? 88 : 86,
        borderRadius: 99,
        background: active ? "#ff5860" : "#f4f4f8",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: active
          ? `0 0 0 ${8 + pulse * 6}px rgba(255,88,96,0.22)`
          : "0 18px 46px rgba(0,0,0,0.24)",
      }}
    >
      {active ? (
        <div
          style={{
            width: 24,
            height: 24,
            borderRadius: 5,
            background: "#f4f4f8",
          }}
        />
      ) : (
        <div
          style={{
            width: 25,
            height: 25,
            borderRadius: 99,
            background: "#080811",
          }}
        />
      )}
    </div>
  );
};

const ClassifyingSpinner: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "relative", width: 44, height: 44 }}>
      {Array.from({ length: 12 }).map((_, index) => {
        const opacity = 0.18 + (((frame / 3 + index) % 12) / 12) * 0.82;
        return (
          <div
            key={index}
            style={{
              position: "absolute",
              left: 20,
              top: 3,
              width: 4,
              height: 12,
              borderRadius: 4,
              background: "#5f67c8",
              opacity,
              transformOrigin: "2px 19px",
              transform: `rotate(${index * 30}deg)`,
            }}
          />
        );
      })}
    </div>
  );
};

const AppHealthPill: React.FC<{ state: LightState; label: string }> = ({
  state,
  label,
}) => {
  const color = state === "green" ? PALETTE.green : PALETTE.red;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        color: "#d8d7dd",
        fontFamily: PHONE_FONT,
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      <div
        style={{
          width: 12,
          height: 12,
          borderRadius: 99,
          background: color,
          boxShadow: `0 0 20px ${color}`,
        }}
      />
      {label}
    </div>
  );
};

const SecondBrainPhoneScreen: React.FC<{
  phase:
    | "capture"
    | "inbox"
    | "tasks"
    | "shoppingTasks"
    | "chewy"
    | "eval"
    | "status"
    | "investigate"
    | "investigateQuick"
    | "investigateEvalStart"
    | "investigateEvalResults";
  captureState?: "idle" | "listening" | "classifying" | "results";
}> = ({ phase, captureState }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const derivedCaptureState =
    captureState ??
    (frame < 1.4 * fps
      ? "idle"
      : frame < 12.4 * fps
        ? "listening"
        : frame < 14.8 * fps
          ? "classifying"
          : "results");
  const requestProgress = interpolate(frame, [1.8 * fps, 11.8 * fps], [0, 1], clamp);
  if (phase === "status") {
    return <StatusPhoneScreen />;
  }

  if (phase === "investigate") {
    return <InvestigatePhoneScreen mode="evalResults" />;
  }

  if (phase === "investigateQuick") {
    return <InvestigatePhoneScreen mode="quickActions" />;
  }

  if (phase === "investigateEvalStart") {
    return <InvestigatePhoneScreen mode="evalStart" />;
  }

  if (phase === "investigateEvalResults") {
    return <InvestigatePhoneScreen mode="evalResults" />;
  }

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        background: "#080811",
        color: "#f7f7fb",
        fontFamily: PHONE_FONT,
      }}
    >
      {phase === "capture" || phase === "chewy" || phase === "eval" ? (
        <SegmentedCaptureControl />
      ) : null}
      <BottomTabs
        active={
          phase === "inbox"
            ? "Inbox"
            : phase === "tasks" || phase === "shoppingTasks"
              ? "Tasks"
              : "Capture"
        }
      />

      {phase === "capture" ? (
        <>
          {derivedCaptureState === "idle" ? (
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: 330,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 25,
              }}
            >
              <RecordButton />
              <div style={{ color: "#34333c", fontSize: 16 }}>Tap to record</div>
            </div>
          ) : null}

          {derivedCaptureState === "listening" ? (
            <>
              <div
                style={{
                  position: "absolute",
                  left: 22,
                  top: 228,
                  fontFamily: PHONE_FONT,
                  fontSize: 25,
                  fontWeight: 500,
                  color: "#f4f2f7",
                  lineHeight: 1.2,
                  maxWidth: 310,
                }}
              >
                {requestProgress < 0.28
                  ? "Listening..."
                  : VOICE_CAPTURE_TEXT.slice(
                      0,
                      Math.max(
                        12,
                        Math.floor(VOICE_CAPTURE_TEXT.length * requestProgress),
                      ),
                    )}
              </div>
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  right: 0,
                top: 430,
                  display: "flex",
                  justifyContent: "center",
                }}
              >
                <RecordButton active />
              </div>
            </>
          ) : null}

          {derivedCaptureState === "classifying" ? (
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: 338,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 18,
              }}
            >
              <ClassifyingSpinner />
              <div style={{ color: "#b8b5c1", fontSize: 19 }}>Classifying...</div>
            </div>
          ) : null}

          {derivedCaptureState === "results" ? (
            <div
              style={{
                position: "absolute",
                left: 18,
                right: 18,
                top: 168,
                display: "grid",
                gap: 11,
              }}
            >
              <AppHealthPill state="green" label="Healthy" />
              {SHOPPING_RESULTS.slice(0, 5).map((result, index) => (
                <div
                  key={result.item}
                  style={{
                    opacity: interpolate(
                      frame,
                      [(6.3 + index * 0.16) * fps, (6.7 + index * 0.16) * fps],
                      [0, 1],
                      clamp,
                    ),
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderRadius: 16,
                    background: "#171722",
                    border: "1px solid rgba(255,255,255,0.06)",
                    padding: "13px 15px",
                    color: "#f6f5fa",
                    fontSize: 15,
                    fontWeight: 650,
                  }}
                >
                  <span>{result.item}</span>
                  <span style={{ color: "#a09ca8", fontSize: 12 }}>
                    {result.destination}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : null}

      {phase === "inbox" ? (
        <div style={{ position: "absolute", left: 18, right: 18, top: 34 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
            }}
          >
            <div
              style={{
                fontFamily: PHONE_FONT,
                fontSize: 38,
                color: "#f7f7fb",
                fontWeight: 500,
              }}
            >
              Inbox
            </div>
            <div
              style={{
                fontFamily: PHONE_FONT,
                fontSize: 12,
                letterSpacing: 0,
                color: "#85838e",
              }}
            >
              12 ITEMS
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
            {["All", "People", "Projects", "Ideas", "Admin"].map((filter) => (
              <div
                key={filter}
                style={{
                  padding: "9px 12px",
                  borderRadius: 10,
                  background: filter === "Admin" ? "#272538" : "transparent",
                  border:
                    filter === "Admin"
                      ? "1px solid rgba(255,255,255,0.04)"
                      : "1px solid rgba(255,255,255,0.025)",
                  color: filter === "Admin" ? "#f7f7fb" : "#6f6c78",
                  fontSize: 13,
                  fontWeight: 650,
                }}
              >
                {filter}
              </div>
            ))}
          </div>
          <div
            style={{
              marginTop: 34,
              paddingBottom: 22,
              borderBottom: "1px solid rgba(255,255,255,0.04)",
            }}
          >
            <div style={{ color: "#f7f7fb", fontSize: 18 }}>Shopping list</div>
            <div
              style={{
                marginTop: 10,
                display: "flex",
                gap: 12,
                color: "#8d8a96",
                fontFamily: PHONE_FONT,
                fontSize: 12,
              }}
            >
              <span>admin</span>
              <span>just now</span>
            </div>
          </div>
        </div>
      ) : null}

      {phase === "tasks" ? (
        <TasksProcessingScreen />
      ) : null}

      {phase === "shoppingTasks" ? (
        <FinalShoppingTasksScreen />
      ) : null}

      {phase === "chewy" ? (
        <div style={{ position: "absolute", left: 20, right: 20, top: 104 }}>
          <AppHealthPill state="green" label="Healthy" />
          <div
            style={{
              marginTop: 24,
              borderRadius: 28,
              background: "#171722",
              padding: 26,
              color: "#f6f5fa",
              border: "1px solid rgba(255,255,255,0.08)",
              boxShadow: "0 30px 70px rgba(0,0,0,0.28)",
            }}
          >
            <div style={{ fontSize: 15, color: "#9b98a5", marginBottom: 20 }}>
              Chewy
            </div>
            <div style={{ fontFamily: PHONE_FONT, fontSize: 34, fontWeight: 740 }}>
              Cat food ordered
            </div>
            <div style={{ marginTop: 10, fontSize: 18, color: "#bab7c2" }}>
              Preferred cat food
            </div>
            <div
              style={{
                marginTop: 28,
                padding: "18px 20px",
                borderRadius: 18,
                background: "rgba(53,208,127,0.13)",
                color: "#71e3a4",
                fontWeight: 700,
                fontSize: 18,
              }}
            >
              Automatic order placed
            </div>
          </div>
          <div
            style={{
              marginTop: 24,
              borderRadius: 20,
              background: "#0d0d14",
              color: "#d4d1dc",
              padding: 22,
              lineHeight: 1.45,
              fontSize: 17,
            }}
          >
            Order event written with the capture trace ID for back-office review.
          </div>
        </div>
      ) : null}

      {phase === "eval" ? (
        <div style={{ position: "absolute", left: 20, right: 20, top: 108 }}>
          <AppHealthPill state="red" label="Eval queued" />
          <div
            style={{
              marginTop: 34,
              color: "#f7f7fb",
              fontFamily: PHONE_FONT,
              fontSize: 28,
              fontWeight: 740,
              lineHeight: 1.05,
            }}
          >
            Run an eval on shopping auto-purchase routing.
          </div>
          <div
            style={{
              marginTop: 26,
              borderRadius: 20,
              background: "#171722",
              color: "#f7f7fb",
              padding: 24,
              fontSize: 16,
              lineHeight: 1.45,
            }}
          >
            Eval request accepted. Check back when the run is scored.
          </div>
          <div
            style={{
              marginTop: 22,
              borderRadius: 20,
              background: "#f4f4f8",
              color: "#111113",
              padding: 24,
              boxShadow: "0 18px 40px rgba(0,0,0,0.12)",
            }}
          >
            <div style={{ color: "#6e6e73", fontSize: 15 }}>Later</div>
            <div style={{ marginTop: 8, fontSize: 26, fontWeight: 750 }}>
              94% pass rate
            </div>
            <div style={{ marginTop: 8, color: "#5f6065", fontSize: 16 }}>
              2 policy improvements proposed
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

const ProcessingCaptureBanner: React.FC = () => (
  <div
    style={{
      margin: "0 14px 18px",
      borderRadius: 18,
      background: "#202448",
      color: "#8fb0ff",
      display: "flex",
      alignItems: "center",
      gap: 14,
      padding: "18px 20px",
      fontSize: 18,
      fontWeight: 500,
    }}
  >
    <ClassifyingSpinner />
    <span>Processing 1 new capture...</span>
  </div>
);

const TasksProcessingScreen: React.FC = () => (
  <div style={{ position: "absolute", left: 0, right: 0, top: 34 }}>
    <div
      style={{
        fontFamily: PHONE_FONT,
        fontSize: 38,
        color: "#f7f7fb",
        fontWeight: 500,
        marginLeft: 18,
        marginBottom: 30,
      }}
    >
      Tasks
    </div>
    <ProcessingCaptureBanner />
    <TaskGroup title="Jewel-Osco" count="1" items={[]} collapsed />
    <TaskGroup title="Tasks" count="2" items={[]} collapsed />
  </div>
);

const TaskGroup: React.FC<{
  title: string;
  count: string;
  items: string[];
  collapsed?: boolean;
  badge?: string;
  compact?: boolean;
}> = ({ title, count, items, collapsed = false, badge, compact = false }) => (
  <div style={{ marginBottom: compact ? 5 : 9 }}>
    <div
      style={{
        height: compact ? 34 : 52,
        background: "#151420",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 18px",
        borderTop: "1px solid rgba(255,255,255,0.03)",
        borderBottom: "1px solid rgba(0,0,0,0.5)",
      }}
    >
      <div
        style={{
          color: "#f7f7fb",
          fontSize: compact ? 15 : 20,
          fontWeight: 760,
        }}
      >
        {title}{" "}
        {badge ? (
          <span
            style={{
              marginLeft: 7,
              borderRadius: 8,
              background: "#28305b",
              color: "#9eb7ff",
              padding: "3px 8px",
              fontFamily: PHONE_FONT,
              fontSize: 11,
              letterSpacing: 1.8,
            }}
          >
            {badge}
          </span>
        ) : null}{" "}
        <span style={{ color: "#7c7984", fontSize: 13, fontFamily: PHONE_FONT }}>
          ({count})
        </span>
      </div>
      <div style={{ color: "#7c7984", fontSize: 18 }}>{collapsed ? "›" : "⌄"}</div>
    </div>
    {!collapsed ? (
      <div style={{ padding: compact ? "1px 14px 0" : "2px 14px 0" }}>
      {items.map((item) => (
        <div
          key={item}
          style={{
            marginTop: compact ? 4 : 7,
            borderRadius: compact ? 9 : 12,
            background: "#151420",
            color: "#f7f7fb",
            padding: compact ? "9px 14px" : "18px 16px",
            fontSize: compact ? 13 : 16,
            lineHeight: 1.25,
            boxShadow: "0 8px 18px rgba(0,0,0,0.18)",
          }}
        >
          {item}
        </div>
      ))}
      </div>
    ) : null}
  </div>
);

const FinalShoppingTasksScreen: React.FC = () => (
  <div style={{ position: "absolute", left: 0, right: 0, top: 22 }}>
    <div
      style={{
        fontFamily: PHONE_FONT,
        fontSize: 28,
        color: "#f7f7fb",
        fontWeight: 500,
        marginLeft: 18,
        marginBottom: 16,
      }}
    >
      Tasks
    </div>
    <TaskGroup
      title="Jewel-Osco"
      count="5"
      items={["milk", "onions", "garlic", "cilantro", "milk"]}
      compact
    />
    <TaskGroup title="CVS" count="1" items={["tylenol"]} compact />
    <TaskGroup title="Agora" count="1" items={["steak"]} compact />
    <TaskGroup title="Chewy" count="1" badge="ONLINE" items={["cat food"]} compact />
    <TaskGroup title="Tasks" count="2" items={[]} collapsed compact />
  </div>
);

const StatusMetricCard: React.FC<{ label: string; value: string }> = ({
  label,
  value,
}) => (
  <div
    style={{
      borderRadius: 14,
      background: "#151420",
      border: "1px solid rgba(255,255,255,0.05)",
      padding: "17px 12px",
      minHeight: 76,
    }}
  >
    <div
      style={{
        color: "#7b7784",
        fontSize: 11,
        letterSpacing: 2.5,
        textTransform: "uppercase",
      }}
    >
      {label}
    </div>
    <div style={{ marginTop: 12, color: "#f7f7fb", fontSize: 24 }}>{value}</div>
  </div>
);

const StatusSegmentRow: React.FC<{
  title: string;
  detail: string;
  status?: LightState;
}> = ({ title, detail, status = "green" }) => {
  const color = status === "green" ? PALETTE.green : PALETTE.red;
  return (
    <div
      style={{
        borderRadius: 16,
        background: "#151420",
        border: "1px solid rgba(255,255,255,0.05)",
        padding: "15px 18px",
        position: "relative",
      }}
    >
      <div style={{ color: "#f7f7fb", fontSize: 17, fontWeight: 700 }}>
        {title}
      </div>
      <div style={{ marginTop: 6, color: "#777482", fontSize: 12 }}>{detail}</div>
      <div style={{ marginTop: 9, color: "#8f8b98", fontSize: 12 }}>20s ago</div>
      <div
        style={{
          position: "absolute",
          right: 16,
          top: 22,
          width: 14,
          height: 14,
          borderRadius: 99,
          background: color,
          boxShadow: `0 0 14px ${color}`,
        }}
      />
    </div>
  );
};

const StatusPhoneScreen: React.FC = () => (
  <div
    style={{
      position: "relative",
      width: "100%",
      height: "100%",
      background: "#080811",
      color: "#f7f7fb",
      fontFamily: PHONE_FONT,
      overflow: "hidden",
    }}
  >
    <BottomTabs active="Status" />
    <div style={{ position: "absolute", left: 18, right: 18, top: 32 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ fontSize: 38, fontWeight: 500 }}>Status</div>
        <div style={{ display: "flex", gap: 14, color: "#9b98a5", fontSize: 24 }}>
          <span>⚙</span>
          <span>⌕</span>
        </div>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 10,
          marginTop: 26,
        }}
      >
        <StatusMetricCard label="Captures (24h)" value="3" />
        <StatusMetricCard label="Success Rate" value="100%" />
        <StatusMetricCard label="Errors (24h)" value="None" />
      </div>
      <div style={{ display: "grid", gap: 11, marginTop: 22 }}>
        <StatusSegmentRow title="Backend API" detail="155 ops, 0 failures in last 5min" />
        <StatusSegmentRow title="Classifier" detail="2 ops, 0 failures in last 15min" />
        <StatusSegmentRow title="Admin Agent" detail="Idle (no recent operations)" />
        <StatusSegmentRow title="Cosmos DB" detail="Idle (no recent operations)" />
        <StatusSegmentRow title="External Services" detail="Idle (no recent operations)" />
        <StatusSegmentRow title="Mobile Capture" detail="2 ops, 0 failures in last 15min" />
      </div>
    </div>
  </div>
);

type InvestigateMode = "quickActions" | "evalStart" | "evalResults";

const InvestigatePhoneScreen: React.FC<{ mode: InvestigateMode }> = ({ mode }) => (
  <div
    style={{
      position: "relative",
      width: "100%",
      height: "100%",
      background: "#101020",
      color: "#f7f7fb",
      overflow: "hidden",
      fontFamily: PHONE_FONT,
    }}
  >
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: 0,
        height: 90,
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 24,
        fontWeight: 760,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 16,
          top: 22,
          borderRadius: 32,
          background: "#1a1a2c",
          border: "1px solid rgba(255,255,255,0.08)",
          padding: "12px 20px",
          color: "#f7f7fb",
          fontSize: 18,
          fontWeight: 720,
        }}
      >
        ‹ (tabs)
      </div>
      Investigate
      <div
        style={{
          position: "absolute",
          right: 22,
          top: 22,
          borderRadius: 28,
          background: "#1a1a2c",
          border: "1px solid rgba(255,255,255,0.08)",
          padding: "12px 18px",
          color: "#5d97dd",
          fontSize: 16,
          fontWeight: 720,
        }}
      >
        New
      </div>
    </div>
    {mode === "quickActions" ? (
      <div
        style={{
          position: "absolute",
          left: 24,
          right: 24,
          top: 340,
          textAlign: "center",
        }}
      >
        <div style={{ color: "#8d8a96", fontSize: 18, marginBottom: 22 }}>
          Quick actions
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          {["Recent errors", "Today's captures", "System health"].map((action) => (
            <div
              key={action}
              style={{
                borderRadius: 24,
                border: "1px solid #5b93d8",
                color: "#75a6ef",
                padding: "10px 14px",
                fontSize: 15,
              }}
            >
              {action}
            </div>
          ))}
        </div>
      </div>
    ) : null}
    {mode === "evalStart" ? (
      <div style={{ position: "absolute", left: 22, right: 22, top: 260 }}>
        <ChatBubble mine>Do an email run on classifier</ChatBubble>
        <ChatBubble>
          I can trigger a classifier evaluation run using the golden dataset. Run classifier eval as a background process to test the system accuracy?
        </ChatBubble>
        <ChatBubble mine>Yes</ChatBubble>
        <ChatBubble>
          The classifier evaluation run has been started. It takes approximately
          3-5 minutes to complete. You can check progress and see results once
          it is finished.
        </ChatBubble>
      </div>
    ) : null}
    {mode === "evalResults" ? (
      <div style={{ position: "absolute", left: 22, right: 22, top: 154 }}>
        <ChatBubble mine>Show eval results</ChatBubble>
        <ChatBubble>
          The classifier evaluation run has completed. Here are the results:
          <br />
          <br />
          <strong>Overall Accuracy:</strong> 96.15% (25 out of 26 correct)
          <br />
          <strong>Dataset Size:</strong> 26 entries
          <br />
          <strong>Model Deployment:</strong> gpt-4o
          <br />
          <br />
          <strong>Precision by Bucket:</strong> Admin 1.00 · Ideas 1.00 · People
          0.86 · Projects 1.00
          <br />
          <strong>Calibration:</strong> confidence bins align with actual accuracy.
        </ChatBubble>
      </div>
    ) : null}
    <div
      style={{
        position: "absolute",
        left: 14,
        right: 14,
        bottom: 16,
        height: 58,
        borderRadius: 29,
        background: "#080811",
        color: "#62606c",
        padding: "17px 22px",
        fontSize: 17,
      }}
    >
      {mode === "evalStart" ? "Do an email run on classifier" : "Ask about your system..."}
      <div
        style={{
          position: "absolute",
          right: -2,
          top: -1,
          width: 60,
          height: 60,
          borderRadius: 99,
          background: "#3a3835",
          color: "#ffffff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 28,
        }}
      >
        ↑
      </div>
    </div>
  </div>
);

const ChatBubble: React.FC<{ mine?: boolean; children: React.ReactNode }> = ({
  mine = false,
  children,
}) => (
  <div
    style={{
      maxWidth: mine ? 260 : 338,
      marginLeft: mine ? "auto" : 0,
      marginBottom: 16,
      borderRadius: 20,
      background: mine ? "#5b93d8" : "#1c1c30",
      color: "#f7f7fb",
      padding: mine ? "17px 20px" : "20px 18px",
      fontSize: mine ? 18 : 15,
      lineHeight: 1.36,
      boxShadow: "0 10px 24px rgba(0,0,0,0.18)",
    }}
  >
    {children}
  </div>
);

const GlassPanel: React.FC<{
  children: React.ReactNode;
  width?: number | string;
  height?: number | string;
  dark?: boolean;
}> = ({ children, width = "auto", height = "auto", dark = true }) => (
  <div
    style={{
      width,
      height,
      borderRadius: 34,
      border: `1px solid ${dark ? PALETTE.hairline : "rgba(0,0,0,0.08)"}`,
      background: dark ? PALETTE.glass : "rgba(255,255,255,0.82)",
      boxShadow: dark
        ? "0 40px 110px rgba(0,0,0,0.32)"
        : "0 34px 90px rgba(0,0,0,0.12)",
      backdropFilter: "blur(24px)",
      overflow: "hidden",
    }}
  >
    {children}
  </div>
);

const OpeningScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const title = interpolate(frame, [0.2 * fps, 1.4 * fps], [0, 1], {
    ...clamp,
    easing: ease,
  });
  const phone = interpolate(frame, [1.3 * fps, 3.2 * fps], [0, 1], {
    ...clamp,
    easing: ease,
  });

  return (
    <Stage>
      <div
        style={{
          position: "absolute",
          left: 138,
          top: 150,
          opacity: title,
          transform: `translateY(${interpolate(title, [0, 1], [38, 0])}px)`,
        }}
      >
        <SceneTitle
          eyebrow="Second Brain demo"
          title="One capture. Every next action."
          subtitle="A simulated walkthrough of voice capture, autonomous commerce, traceability, and eval-driven improvement."
        />
      </div>
      <div
        style={{
          position: "absolute",
          right: 230,
          top: 128,
          opacity: phone,
          transform: `translateY(${interpolate(phone, [0, 1], [80, 0])}px)`,
        }}
      >
        <PhoneFrame scale={0.94} rotate={-4}>
          <SecondBrainPhoneScreen phase="capture" />
        </PhoneFrame>
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 100,
          height: 2,
          background:
            "linear-gradient(90deg, transparent, rgba(255,255,255,0.42), transparent)",
          opacity: 0.72,
        }}
      />
    </Stage>
  );
};

const PhoneCaptureScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = useEntrance(0.1, 0.9);
  const captureOpacity =
    1 -
    interpolate(frame, [13.6 * fps, 14.3 * fps], [0, 1], {
      ...clamp,
      easing: Easing.in(Easing.cubic),
    });
  const inboxOpacity =
    interpolate(frame, [13.8 * fps, 14.5 * fps], [0, 1], {
      ...clamp,
      easing: ease,
    }) -
    interpolate(frame, [16.2 * fps, 16.9 * fps], [0, 1], {
      ...clamp,
      easing: Easing.in(Easing.cubic),
    });
  const tasksOpacity = interpolate(frame, [16.4 * fps, 17.1 * fps], [0, 1], {
    ...clamp,
    easing: ease,
  }) -
    interpolate(frame, [18.6 * fps, 19.2 * fps], [0, 1], {
      ...clamp,
      easing: Easing.in(Easing.cubic),
    });
  const shoppingTasksOpacity = interpolate(
    frame,
    [18.8 * fps, 19.5 * fps],
    [0, 1],
    {
      ...clamp,
      easing: ease,
    },
  );

  return (
    <Stage tone="white">
      <div
        style={{
          position: "absolute",
          left: 126,
          top: 128,
          color: "#111113",
        }}
      >
        <SceneTitle
          darkText
          eyebrow="Voice to structured intent"
          title="The phone stays calm."
          subtitle="It captures the request and shows only what the user needs: confirmation and operational health."
        />
      </div>
      <div
        style={{
          position: "absolute",
          right: 260,
          top: 96,
          opacity: enter,
          transform: `translateX(${interpolate(enter, [0, 1], [90, 0])}px)`,
        }}
      >
        <PhoneFrame scale={1.02}>
          <div style={{ position: "absolute", inset: 0, opacity: captureOpacity }}>
            <SecondBrainPhoneScreen phase="capture" />
          </div>
          <div style={{ position: "absolute", inset: 0, opacity: inboxOpacity }}>
            <SecondBrainPhoneScreen phase="inbox" />
          </div>
          <div style={{ position: "absolute", inset: 0, opacity: tasksOpacity }}>
            <SecondBrainPhoneScreen phase="tasks" />
          </div>
          <div
            style={{ position: "absolute", inset: 0, opacity: shoppingTasksOpacity }}
          >
            <SecondBrainPhoneScreen phase="shoppingTasks" />
          </div>
        </PhoneFrame>
      </div>
    </Stage>
  );
};

const CommerceScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const phoneIn = interpolate(frame, [0, 0.8 * fps], [0, 1], {
    ...clamp,
    easing: ease,
  });

  return (
    <Stage>
      <div style={{ position: "absolute", left: 128, top: 120 }}>
        <SceneTitle
          eyebrow="Autonomous commerce"
          title="Local errands split from online purchase."
          subtitle="Chewy is shown as a simulated commerce connector for automatic cat food ordering."
        />
      </div>
      <div
        style={{
          position: "absolute",
          left: 184,
          bottom: 126,
          display: "flex",
          gap: 18,
        }}
      >
        {[
          {
            destination: "Jewel-Osco",
            item: "Onions, garlic, cilantro, milk",
            mode: "Errand",
          },
          { destination: "CVS", item: "Tylenol", mode: "Errand" },
          { destination: "Agora", item: "Steak", mode: "Errand" },
          { destination: "Chewy", item: "Cat food", mode: "Automatic order" },
        ].map((result, index) => (
          <GlassPanel key={result.destination} width={244} dark>
            <div
              style={{
                padding: 24,
                opacity: interpolate(
                  frame,
                  [(1.2 + index * 0.22) * fps, (1.7 + index * 0.22) * fps],
                  [0, 1],
                  clamp,
                ),
              }}
            >
              <div style={{ fontFamily: FONT.mono, fontSize: 13, color: PALETTE.muted }}>
                {result.mode}
              </div>
              <div
                style={{
                  marginTop: 20,
                  fontFamily: FONT.sans,
                  fontSize: 30,
                  fontWeight: 740,
                  color: PALETTE.white,
                }}
              >
                {result.item}
              </div>
              <div style={{ marginTop: 10, color: PALETTE.softWhite, fontSize: 18 }}>
                {result.destination}
              </div>
            </div>
          </GlassPanel>
        ))}
      </div>
      <div
        style={{
          position: "absolute",
          right: 210,
          top: 112,
          opacity: phoneIn,
          transform: `translateY(${interpolate(phoneIn, [0, 1], [60, 0])}px)`,
        }}
      >
        <PhoneFrame scale={0.98} rotate={4}>
          <SecondBrainPhoneScreen phase="chewy" />
        </PhoneFrame>
      </div>
    </Stage>
  );
};

const FlowNode: React.FC<{
  label: string;
  detail: string;
  color: string;
  index: number;
}> = ({ label, detail, color, index }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = interpolate(
    frame,
    [(0.5 + index * 0.22) * fps, (1.2 + index * 0.22) * fps],
    [0, 1],
    { ...clamp, easing: ease },
  );
  return (
    <div
      style={{
        opacity: enter,
        transform: `translateY(${interpolate(enter, [0, 1], [24, 0])}px)`,
        width: 230,
        minHeight: 136,
        borderRadius: 28,
        border: `1px solid ${PALETTE.hairline}`,
        background: "rgba(255,255,255,0.08)",
        padding: 22,
        color: PALETTE.white,
      }}
    >
      <div
        style={{
          width: 12,
          height: 12,
          borderRadius: 99,
          background: color,
          boxShadow: `0 0 24px ${color}`,
          marginBottom: 20,
        }}
      />
      <div style={{ fontFamily: FONT.sans, fontSize: 25, fontWeight: 740 }}>
        {label}
      </div>
      <div style={{ marginTop: 9, color: PALETTE.softWhite, fontSize: 16, lineHeight: 1.35 }}>
        {detail}
      </div>
    </div>
  );
};

const FoundryAgentsPanel: React.FC = () => (
  <GlassPanel width={780} height={338}>
    <div
      style={{
        padding: 22,
        color: PALETTE.white,
        fontFamily: FONT.text,
      }}
    >
      <div style={{ fontSize: 17, color: PALETTE.softWhite }}>
        Microsoft Foundry / second-brain / Agents
      </div>
      <div
        style={{
          marginTop: 18,
          fontFamily: FONT.sans,
          fontSize: 31,
          fontWeight: 760,
        }}
      >
        Create and debug your agents
      </div>
      <div
        style={{
          marginTop: 22,
          display: "grid",
          gridTemplateColumns: "1.2fr 1.8fr 0.7fr",
          color: PALETTE.muted,
          fontSize: 14,
          paddingBottom: 10,
          borderBottom: `1px solid ${PALETTE.hairline}`,
        }}
      >
        <div>My agents</div>
        <div>ID</div>
        <div>Model</div>
      </div>
      {[
        ["OB-classifier", "asst_6qq6Ehlg7CLnkUv3RP2XWmM3", "gpt-4o"],
        ["InvestigationAgent", "asst_5feSWWTMA8rBSUyQo6aSCsEJ", "gpt-4o"],
        ["AdminAgent", "asst_17oFXNHNq7kzmspQGMUrgERM", "gpt-4o"],
        ["Classifier", "asst_Fnjkq5RVrvdFIOSqbreAwxuq", "gpt-4o"],
      ].map(([name, id, model]) => (
        <div
          key={name}
          style={{
            display: "grid",
            gridTemplateColumns: "1.2fr 1.8fr 0.7fr",
            padding: "13px 0",
            borderBottom: "1px solid rgba(255,255,255,0.05)",
            fontSize: 15,
            color: PALETTE.softWhite,
          }}
        >
          <div>{name}</div>
          <div style={{ color: PALETTE.muted }}>{id}</div>
          <div>{model}</div>
        </div>
      ))}
    </div>
  </GlassPanel>
);

const TechFlowScene: React.FC = () => {
  const nodes = [
    ["Mobile capture", "trace starts", PALETTE.green],
    ["AI Foundry", "agent run", PALETTE.violet],
    ["Classifier Agent", "bucket + confidence", PALETTE.cyan],
    ["Admin Agent", "task routing", PALETTE.blue],
    ["Cosmos DB", "documents + IDs", PALETTE.gold],
    ["Chewy connector", "order event", PALETTE.green],
  ] as const;

  return (
    <Stage>
      <div style={{ position: "absolute", left: 120, top: 104 }}>
        <SceneTitle
        eyebrow="Technical flow"
        title="The phone request becomes a traceable transaction."
        subtitle="Each capture carries trace context from the mobile app through agents, storage, and commerce connectors."
        maxWidth={640}
      />
      </div>
      <div style={{ position: "absolute", right: 96, top: 84 }}>
        <FoundryAgentsPanel />
      </div>
      <div
        style={{
          position: "absolute",
          left: 120,
          right: 120,
          bottom: 178,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        {nodes.map(([label, detail, color], index) => (
          <React.Fragment key={label}>
            <FlowNode label={label} detail={detail} color={color} index={index} />
            {index < nodes.length - 1 ? (
              <div
                style={{
                  width: 50,
                  height: 1,
                  background:
                    "linear-gradient(90deg, rgba(255,255,255,0.12), rgba(255,255,255,0.58))",
                }}
              />
            ) : null}
          </React.Fragment>
        ))}
      </div>
    </Stage>
  );
};

const FoundryInstructionsPanel: React.FC<{
  agent: "classifier" | "admin";
}> = ({ agent }) => {
  const isClassifier = agent === "classifier";

  return (
  <GlassPanel dark={false} width={850} height={720}>
    <div
      style={{
        padding: 26,
        color: "#111113",
        fontFamily: FONT.text,
      }}
    >
      <div style={{ display: "grid", gap: 18 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 10 }}>
            Agent name
          </div>
          <div
            style={{
              border: "1px solid rgba(0,0,0,0.25)",
              borderRadius: 6,
              background: "#f4f4f4",
              padding: "13px 16px",
              fontSize: 20,
            }}
          >
            {isClassifier ? "Classifier" : "AdminAgent"}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 10 }}>
            Deployment
          </div>
          <div
            style={{
              border: "1px solid rgba(0,0,0,0.25)",
              borderRadius: 6,
              background: "#ffffff",
              padding: "13px 16px",
              fontSize: 20,
            }}
          >
            gpt-4o (version:2024-08-06)
          </div>
        </div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 10 }}>
            Agent instructions
          </div>
          <div
            style={{
              height: 386,
              border: "1px solid rgba(0,0,0,0.25)",
              borderRadius: 8,
              background: "#f7f7f5",
              padding: 20,
              fontSize: 19,
              lineHeight: 1.42,
              overflow: "hidden",
            }}
          >
            {isClassifier ? (
              <>
                You are Will&apos;s second brain classifier. Your job is to classify
                captured text into the appropriate bucket(s) and file it using the
                file_capture tool.
                <br />
                <br />
                <strong>## Buckets</strong>
                <br />
                <strong>People:</strong> relationships, interactions, social context.
                <br />
                <strong>Projects:</strong> multi-step endeavors with goals, deadlines,
                and deliverables.
                <br />
                <strong>Ideas:</strong> thoughts to revisit later, reflections, creative
                notes.
                <br />
                <strong>Admin:</strong> errands, purchases, forms, scheduling, household
                tasks, and operational follow-up.
              </>
            ) : (
              <>
                You are Will&apos;s second brain admin agent. Your job is to turn Admin
                captures into concrete tasks, store destinations, and commerce actions.
                <br />
                <br />
                <strong>## Rules</strong>
                <br />
                Split shopping items by destination and preserve the original capture
                trace ID.
                <br />
                Route grocery and pharmacy items as errands.
                <br />
                Route cat food to Chewy when the connector is available.
                <br />
                Use automatic order placement only when the item matches a trusted
                purchase preference and the order can be written back with evidence.
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  </GlassPanel>
  );
};

const ClassifierScene: React.FC = () => (
  <Stage tone="white">
    <div style={{ position: "absolute", left: 112, top: 104 }}>
      <SceneTitle
        darkText
        eyebrow="Classifier agent"
        title="Instructions, checks, and filing are visible."
        subtitle="Foundry-managed policy defines buckets and requires the file_capture tool for traceable classification."
        maxWidth={720}
      />
    </div>
    <div
      style={{
        position: "absolute",
        right: 92,
        top: 116,
      }}
    >
      <FoundryInstructionsPanel agent="classifier" />
    </div>
  </Stage>
);

const AdminAgentScene: React.FC = () => (
  <Stage tone="white">
    <div style={{ position: "absolute", left: 112, top: 104 }}>
      <SceneTitle
        darkText
        eyebrow="Admin agent"
        title="Routing rules become concrete actions."
        subtitle="The Admin Agent turns the classified request into store tasks, a Chewy order, and evidence written with the same trace ID."
        maxWidth={720}
      />
    </div>
    <div
      style={{
        position: "absolute",
        right: 92,
        top: 116,
      }}
    >
      <FoundryInstructionsPanel agent="admin" />
    </div>
  </Stage>
);

const TraceRow: React.FC<{
  segment: string;
  evidence: string;
  status: LightState;
  index: number;
}> = ({ segment, evidence, status, index }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = interpolate(
    frame,
    [(0.9 + index * 0.18) * fps, (1.3 + index * 0.18) * fps],
    [0, 1],
    clamp,
  );
  const color = status === "green" ? PALETTE.green : PALETTE.red;
  return (
    <div
      style={{
        opacity: enter,
        display: "grid",
        gridTemplateColumns: "220px 1fr 110px",
        alignItems: "center",
        gap: 22,
        padding: "18px 22px",
        borderBottom: `1px solid ${PALETTE.hairline}`,
        color: PALETTE.white,
        fontFamily: FONT.text,
      }}
    >
      <div style={{ fontSize: 20, fontWeight: 720 }}>{segment}</div>
      <div style={{ color: PALETTE.softWhite, fontSize: 17 }}>{evidence}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: 99,
            background: color,
            boxShadow: `0 0 22px ${color}`,
          }}
        />
        <span style={{ color }}>{status}</span>
      </div>
    </div>
  );
};

const MiniChart: React.FC<{
  color: string;
  fill?: boolean;
  values: number[];
}> = ({ color, fill = false, values }) => {
  const width = 170;
  const height = 72;
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - value * height;
      return `${x},${y}`;
    })
    .join(" ");
  const fillPoints = `0,${height} ${points} ${width},${height}`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {[0.25, 0.5, 0.75].map((line) => (
        <line
          key={line}
          x1={0}
          x2={width}
          y1={height * line}
          y2={height * line}
          stroke="rgba(0,0,0,0.16)"
          strokeWidth={1}
        />
      ))}
      {fill ? (
        <polygon points={fillPoints} fill={`${color}55`} stroke="none" />
      ) : null}
      <polyline points={points} fill="none" stroke={color} strokeWidth={4} />
    </svg>
  );
};

const AppInsightsPanel: React.FC = () => (
  <GlassPanel width={910} height={316} dark={false}>
    <div style={{ padding: 22, color: "#1f1f1f", fontFamily: FONT.text }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontSize: 25, fontWeight: 760 }}>second-brain-insights</div>
          <div style={{ color: "#5d5d5d", fontSize: 14 }}>Application Insights</div>
        </div>
        <div style={{ color: "#0078d4", fontSize: 16 }}>Logs · Monitor resource group</div>
      </div>
      <div
        style={{
          marginTop: 20,
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr 1fr",
          gap: 16,
        }}
      >
        {[
          {
            title: "Failed requests",
            value: "0",
            color: "#e3008c",
            values: [0.02, 0.02, 0.02, 0.02, 0.02],
          },
          {
            title: "Server response time",
            value: "99.61ms",
            color: "#0078d4",
            values: [0.15, 0.28, 0.18, 0.84, 0.24, 0.65, 0.21],
          },
          {
            title: "Server requests",
            value: "769",
            color: "#0078d4",
            fill: true,
            values: [0.26, 0.08, 0.14, 0.12, 0.72, 0.35, 0.45],
          },
          {
            title: "Availability",
            value: "--",
            color: "#49a010",
            values: [0.04, 0.04, 0.04, 0.04, 0.04],
          },
        ].map((chart) => (
          <div
            key={chart.title}
            style={{
              border: "1px solid rgba(0,0,0,0.12)",
              borderRadius: 4,
              padding: 14,
              minHeight: 170,
              background: "#ffffff",
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 700 }}>{chart.title}</div>
            <div style={{ marginTop: 12 }}>
              <MiniChart
                color={chart.color}
                fill={chart.fill}
                values={chart.values}
              />
            </div>
            <div style={{ marginTop: 8, color: "#4b4b4b", fontSize: 13 }}>
              {chart.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  </GlassPanel>
);

const ObservabilityScene: React.FC = () => (
  <Stage>
    <div style={{ position: "absolute", left: 104, top: 86 }}>
      <SceneTitle
        eyebrow="Web observability"
        title="Trace one request from front to back."
        subtitle="The phone only shows green or red. The web UI shows why."
        maxWidth={690}
      />
    </div>
    <div style={{ position: "absolute", left: 150, top: 360 }}>
      <PhoneFrame scale={0.54} rotate={-2}>
        <SecondBrainPhoneScreen phase="status" />
      </PhoneFrame>
    </div>
    <div style={{ position: "absolute", right: 92, top: 70 }}>
      <AppInsightsPanel />
    </div>
    <div style={{ position: "absolute", right: 92, bottom: 76 }}>
      <GlassPanel width={910} height={442}>
        <div style={{ padding: "26px 28px", borderBottom: `1px solid ${PALETTE.hairline}` }}>
          <div style={{ color: PALETTE.muted, fontFamily: FONT.mono, fontSize: 14 }}>
            CAPTURE TRACE
          </div>
          <div
            style={{
              color: PALETTE.white,
              fontSize: 32,
              fontWeight: 760,
              marginTop: 10,
              fontFamily: FONT.sans,
            }}
          >
            txn_9f42 · Shopping auto-purchase
          </div>
        </div>
        {[
          ["Mobile Capture", "client event, app status, captureTraceId", "green"],
          ["Classifier", "Foundry run, tool call, confidence, bucket", "green"],
          ["Admin Agent", "task split, commerce rule, order evidence", "green"],
          ["Cosmos DB", "request charge, activity ID, write latency", "green"],
          ["Chewy Connector", "purchase preference, order ID, confirmation", "green"],
        ].map(([segment, evidence, status], index) => (
          <TraceRow
            key={segment}
            segment={segment}
            evidence={evidence}
            status={status as LightState}
            index={index}
          />
        ))}
      </GlassPanel>
    </div>
  </Stage>
);

const EvalsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const web = interpolate(frame, [2.1 * fps, 3 * fps], [0, 1], {
    ...clamp,
    easing: ease,
  });
  const quick = 1 - interpolate(frame, [4.2 * fps, 5 * fps], [0, 1], clamp);
  const start =
    interpolate(frame, [4.4 * fps, 5.2 * fps], [0, 1], clamp) -
    interpolate(frame, [10 * fps, 10.8 * fps], [0, 1], clamp);
  const results = interpolate(frame, [10.2 * fps, 11.2 * fps], [0, 1], clamp);

  return (
    <Stage tone="white">
      <div
        style={{
          position: "absolute",
          left: 110,
          top: 94,
          zIndex: 2,
        }}
      >
        <SceneTitle
          darkText
          eyebrow="Evals"
          title="Ask from the phone. Inspect the run later."
          subtitle="Eval requests travel through the same observable backend, then return as a concise phone result."
          maxWidth={690}
        />
      </div>
      <div style={{ position: "absolute", left: 94, bottom: -92, zIndex: 3 }}>
        <PhoneFrame scale={0.58} rotate={-3}>
          <div style={{ position: "absolute", inset: 0, opacity: quick }}>
            <SecondBrainPhoneScreen phase="investigateQuick" />
          </div>
          <div style={{ position: "absolute", inset: 0, opacity: start }}>
            <SecondBrainPhoneScreen phase="investigateEvalStart" />
          </div>
          <div style={{ position: "absolute", inset: 0, opacity: results }}>
            <SecondBrainPhoneScreen phase="investigateEvalResults" />
          </div>
        </PhoneFrame>
      </div>
      <div
        style={{
          position: "absolute",
          right: 108,
          bottom: 106,
          opacity: web,
          transform: `translateX(${interpolate(web, [0, 1], [80, 0])}px)`,
        }}
      >
        <GlassPanel dark={false} width={920}>
          <div style={{ padding: 32 }}>
            <div style={{ fontFamily: FONT.mono, color: "#6e6e73", fontSize: 14 }}>
              EVAL RUN · SHOPPING AUTO-PURCHASE ROUTING
            </div>
            <div
              style={{
                marginTop: 18,
                display: "grid",
                gridTemplateColumns: "1fr 1fr 1fr",
                gap: 16,
              }}
            >
              {[
                ["Golden cases", "128"],
                ["Regression gate", "Passed"],
                ["Self improvement", "2 proposals"],
              ].map(([title, value]) => (
                <div
                  key={title}
                  style={{
                    borderRadius: 24,
                    background: "#ffffff",
                    padding: 22,
                    boxShadow: "0 14px 38px rgba(0,0,0,0.08)",
                  }}
                >
                  <div style={{ color: "#6e6e73", fontSize: 15 }}>{title}</div>
                  <div
                    style={{
                      marginTop: 10,
                      color: "#111113",
                      fontSize: 29,
                      fontWeight: 760,
                    }}
                  >
                    {value}
                  </div>
                </div>
              ))}
            </div>
            <div
              style={{
                marginTop: 24,
                borderRadius: 26,
                background: "#111113",
                color: PALETTE.white,
                padding: 24,
                fontSize: 18,
                lineHeight: 1.45,
              }}
            >
              Failures become reviewable changes to instructions, routing rules, and
              connector guardrails before the next release.
            </div>
          </div>
        </GlassPanel>
      </div>
    </Stage>
  );
};

const CloseScene: React.FC = () => {
  const enter = useEntrance(0.1, 1);
  return (
    <Stage>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          opacity: enter,
          transform: `translateY(${interpolate(enter, [0, 1], [30, 0])}px)`,
        }}
      >
        <div>
          <div
            style={{
              fontFamily: FONT.sans,
              fontSize: 84,
              color: PALETTE.white,
              fontWeight: 760,
              letterSpacing: 0,
            }}
          >
            Capture becomes action.
          </div>
          <div
            style={{
              marginTop: 24,
              fontFamily: FONT.text,
              fontSize: 31,
              color: PALETTE.softWhite,
            }}
          >
            Action becomes evidence. Evidence improves the system.
          </div>
        </div>
      </div>
    </Stage>
  );
};

export const SecondBrainShoppingFilm: React.FC = () => (
  <>
    <Audio src={staticFile("fortive-demo-intro.mp3")} />
    <Sequence
      from={SCENES.opening.start}
      durationInFrames={SCENES.opening.duration}
      premountFor={30}
    >
      <OpeningScene />
    </Sequence>
    <Sequence
      from={SCENES.phoneCapture.start}
      durationInFrames={SCENES.phoneCapture.duration}
      premountFor={30}
    >
      <PhoneCaptureScene />
    </Sequence>
    <Sequence
      from={SCENES.commerce.start}
      durationInFrames={SCENES.commerce.duration}
      premountFor={30}
    >
      <CommerceScene />
    </Sequence>
    <Sequence
      from={SCENES.techFlow.start}
      durationInFrames={SCENES.techFlow.duration}
      premountFor={30}
    >
      <TechFlowScene />
    </Sequence>
    <Sequence
      from={SCENES.classifier.start}
      durationInFrames={SCENES.classifier.duration}
      premountFor={30}
    >
      <ClassifierScene />
    </Sequence>
    <Sequence
      from={SCENES.adminAgent.start}
      durationInFrames={SCENES.adminAgent.duration}
      premountFor={30}
    >
      <AdminAgentScene />
    </Sequence>
    <Sequence
      from={SCENES.observability.start}
      durationInFrames={SCENES.observability.duration}
      premountFor={30}
    >
      <ObservabilityScene />
    </Sequence>
    <Sequence
      from={SCENES.evals.start}
      durationInFrames={SCENES.evals.duration}
      premountFor={30}
    >
      <EvalsScene />
    </Sequence>
    <Sequence
      from={SCENES.close.start}
      durationInFrames={SCENES.close.duration}
      premountFor={30}
    >
      <CloseScene />
    </Sequence>
  </>
);
