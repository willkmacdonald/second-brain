import { useEffect, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { theme } from "../constants/theme";
import {
  fetchSpineStatus,
  SegmentStatus,
  SpineSegment,
  SPINE_WEB_URL,
} from "../lib/spine";

const COLOR: Record<SegmentStatus, string> = {
  green: theme.colors.ok,
  yellow: theme.colors.warn,
  red: theme.colors.err,
  stale: theme.colors.textMuted,
};

/** Border color per status — hairline default, tinted for warn/err. */
function tileBorderColor(status: SegmentStatus): string {
  if (status === "red") return theme.colors.err + "44";
  if (status === "yellow") return theme.colors.warn + "33";
  return theme.colors.hairline;
}

interface Props {
  segmentId: string;
}

export function SpineStatusTile({ segmentId }: Props) {
  const [segment, setSegment] = useState<SpineSegment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchSpineStatus();
        if (cancelled) return;
        const found = data.segments.find((s) => s.id === segmentId) ?? null;
        setSegment(found);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      }
    }
    load();
    const id = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [segmentId]);

  function handlePress() {
    if (!SPINE_WEB_URL) return;
    Linking.openURL(`${SPINE_WEB_URL}/segment/${segmentId}`);
  }

  if (error) {
    return (
      <View style={[styles.tile, { borderColor: theme.colors.hairline }]}>
        <Text style={styles.title}>Spine unreachable</Text>
        <Text style={styles.role}>{error}</Text>
      </View>
    );
  }

  if (!segment) {
    return (
      <View style={[styles.tile, { borderColor: theme.colors.hairline }]}>
        <Text style={styles.title}>Loading…</Text>
      </View>
    );
  }

  return (
    <Pressable onPress={handlePress} style={[styles.tile, { borderColor: tileBorderColor(segment.status) }]}>
      <View style={styles.row}>
        <Text style={styles.title}>{segment.name}</Text>
        <View style={styles.dotRow}>
          <View
            style={[
              styles.dot,
              { backgroundColor: COLOR[segment.status] },
              segment.status === "green" && styles.dotGlow,
            ]}
          />
        </View>
      </View>
      <Text style={styles.role}>{segment.headline}</Text>
      <Text style={styles.statusLine}>{segment.freshness_seconds}s ago</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tile: {
    padding: 12,
    backgroundColor: theme.colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 12,
    marginBottom: 8,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    fontSize: 12.5,
    fontWeight: "500",
    fontFamily: theme.fonts.bodyMedium,
    letterSpacing: -0.15,
    color: theme.colors.text,
  },
  dotRow: {
    alignItems: "center",
    justifyContent: "center",
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  dotGlow: {
    shadowColor: theme.colors.ok,
    shadowRadius: 3,
    shadowOpacity: 0.22,
    shadowOffset: { width: 0, height: 0 },
  },
  role: {
    color: theme.colors.textMuted,
    fontSize: 10.5,
    fontFamily: theme.fonts.body,
    marginTop: 4,
    lineHeight: 14,
  },
  statusLine: {
    fontFamily: theme.fonts.mono,
    fontSize: 10.5,
    color: theme.colors.textDim,
    marginTop: 6,
  },
});
